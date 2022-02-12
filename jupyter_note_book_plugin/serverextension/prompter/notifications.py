"""
notifications.py implements the Abstract base class of Notification
as well as implementing sub-classes. 

These are the classes that handle detecting when a notification may be
sent, what its response is composed of, and updating response contents
when relevant
"""
from random import choice

import math
import operator

import pandas as pd
from pandas.api.types import is_numeric_dtype, is_unsigned_integer_dtype, is_integer_dtype, is_signed_integer_dtype
import numpy as np
import dill

from scipy.stats import f_oneway, chi2_contingency, spearmanr
from sklearn.base import ClassifierMixin
from pandas.api.types import is_numeric_dtype

from .string_compare import check_for_protected, guess_protected
from .sortilege import is_categorical
from .slice_finder import err_slices

PVAL_CUTOFF = 0.25 # cutoff for thinking that column is a proxy for a sensitive column

class Notification:
    """Abstract base class for all notifications"""
    def __init__(self, db):
        self._feasible = False
        self.db = db
        self.data = {}

        # data format is note specific

    def feasible(self, cell_id, env, dfs, ns):
        """is it feasible to send this notification?"""
        ret_value = self.check_feasible(cell_id, env, dfs, ns)
        self._feasible = ret_value 
        return ret_value
   
    def times_sent(self):
        """the number of times this notification has been sent"""
        # pylint: disable=no-self-use
        return 0 

    def make_response(self, env, kernel_id, cell_id):
        """form and store the response to send to the frontend""" 
        # pylint: disable=unused-argument
        if not self._feasible:
            raise Exception("Cannot call make_response on notification that is not feasible")
    
    def update(self, env, kernel_id, cell_id, dfs, ns):
        """check whether the note on this cell needs to be updated"""
        raise NotImplementedError
    def check_feasible(self, cell_id, env, dfs, ns):
        """check feasibility of implementing class"""
        raise NotImplementedError("check_feasible must be overridden") 

class ProtectedColumnNote(Notification):

    """
    a class that indicates whether a protected column is present in
    an active dataframe.

    data format is {"type" : "resemble", 
                    "col" : <comma-delimited string with suspect columns>,
                    "category" : <comma-delimited string with categories columns may fall into>,
                    "col_names" : [list of column names]
                    "df" : <df name or "unnamed">}
    """
    def __init__(self, db):

        super().__init__(db)
        self.df_protected_cols = {}
        self.df_not_protected_cols = {}

    def check_feasible(self, cell_id, env, dfs, ns):

        # are there any dataframes that we haven't examined?
        self.df_protected_cols = {}
        self.df_not_protected_cols = {}

        # pylint: disable=protected-access
        poss_cols = self.db.get_unmarked_columns(env._kernel_id)

        for df_name, cols in poss_cols.items():

            protected_columns = check_for_protected(cols)
            protected_columns.extend(guess_protected(dfs[df_name][cols]))
      
            env.log.debug("[ProtectedColumnNote] protected columns are {0}".format(protected_columns))
  
            if protected_columns != []:

                protected_col_names = [c["original_name"] for c in protected_columns]
                self.df_protected_cols[df_name] = protected_columns        
                self.df_not_protected_cols[df_name] = [c for c in cols if c not in protected_col_names]

        return self.df_protected_cols != {}

    def _noted_dfs(self, note_type):
        """return list of df names that have had notes issued on them already""" 
        notes = [note for note_set in self.data.values() for note in note_set]
        note_subset = [note for note in notes if note["type"] == note_type]
        noted_dfs = [note["df"] for note in note_subset]
        
        return noted_dfs

    def make_response(self, env, kernel_id, cell_id):

        super().make_response(env, kernel_id, cell_id)

        #using protected columns found in csv build string to display in notification
        # find if there are dfs without notes generated on them

        input_data = {}

        for df_name in self.df_protected_cols:

            resp = self._make_resp_entry(df_name)
            if len(resp["columns"]) == 0:
                continue

            self.data[resp["df"]] = [resp]

            if resp["df"] not in input_data:
                input_data[resp["df"]] = {}
            env.log.debug("[ProtectedColumn] resp {0}".format(resp))
            for col_name, col_info in resp["columns"].items():
                input_data[resp["df"]][col_name] = {"is_sensitive": col_info["sensitive"], 
                                                    "user_specified" : False, "fields" : col_info["field"]}
        self.db.update_marked_columns(kernel_id, input_data)

    def _make_resp_entry(self, df_name):

        resp = {"type" : "resemble"}
        resp["df"] = df_name

        resp["columns"] = {}

        for col in self.df_protected_cols[df_name]:
            resp["columns"][col["original_name"]] = {"sensitive" : True, "field" : col["protected_value"]}
        for col in self.df_not_protected_cols[df_name]:
            resp["columns"][col] = {"sensitive" : False, "field" : None}
        return resp

    def update(self, env, kernel_id, cell_id, dfs, ns):
        # pylint: disable=too-many-arguments

        # if df has been reloaded with new columns, then captured
        # in the check_feasible step

        # so check 1. that the noted dfs are still defined, 2. that
        # noted defined df still has columns 3. that columns in
        # noted defined dfs are still of the same value 

        # Also should check that judgments about columns in noted defined
        # df have not changed. 

        new_data = {}
        update_data = {}
        new_df_names = list(self.df_protected_cols.keys())

        for df_name, note_list in self.data.items():

            if df_name not in dfs:
                continue
            if df_name in new_df_names: # if df is in here, then note was *just* generated
                new_data[df_name] = note_list
                continue

            protected_cols = guess_protected(dfs[df_name])
            self.df_protected_cols[df_name] = protected_cols
            protected_col_names = [col["original_name"] for col in protected_cols]
            self.df_not_protected_cols[df_name] = [col for col in dfs[df_name].columns if col not in protected_col_names]

            env.log.debug("[ProtectedColumnNote] protected columns {0}".format(self.df_protected_cols[df_name]))
            env.log.debug("[ProtectedColumnNote] not protected columns {0}".format(self.df_not_protected_cols[df_name]))

            new_data[df_name] = [self._make_resp_entry(df_name)]
            # TODO: for some reason, on this call, the not_protected columns are not being sent
            update_data[df_name] = {}

            for col_name, col_info in new_data[df_name][0]["columns"].items():
                update_data[df_name][col_name] = {"is_sensitive": col_info["sensitive"],
                                                  "user_specified" : False, "fields" : col_info["field"]}

        self.db.update_marked_columns(kernel_id, update_data)

        self.data = new_data

class ProxyColumnNote(ProtectedColumnNote):
    """
    A notification that measures whether there exists a column that is a proxy
    for a protected column.

    Note that this requires that sensitive columns actually be present in the
    dataframe. 

    format is {"type" : "proxy", "df_name" : <name of df>, 
               "sensitive_col_name" :  <name of sensitive column>,
               "proxy_col_name" : <name of proxy column>,
              }
    """
    def __init__(self, db):
        super().__init__(db)
        self.avail_dfs = {} # df_name -> {df: <df>, sense_cols : [], non_sense_cols: []}
 
    def check_feasible(self, cell_id, env, dfs, ns):

        # note is feasible if there are columns of most recent
        # data versions, which are sensitive, and there are columns
        # in most recent data versions which are not sensitive

        # note that by using DB, we only issue notes when a Protected
        # note has already been sent.
  
        self.avail_dfs = {}

        # find dfs that have not had notes issued on them already
        noted_dfs = self._noted_dfs("proxy")
        # pylint: disable=protected-access
        recent_cols = self.db.get_recent_cols(env._kernel_id)
        candidates = {}

        for col in recent_cols:

            df_name = col["name"]
            if df_name in noted_dfs or df_name not in dfs:
                continue
            if df_name not in candidates:
                candidates[df_name] = {
                    "df" : dfs[df_name],
                    "sens_cols" : [],
                    "non_sense_cols" : []
                }
            if col["checked"] and col["is_sensitive"]:
                candidates[df_name]["sens_cols"].append(col["col_name"])
            elif col["checked"]:
                candidates[df_name]["non_sense_cols"].append(col["col_name"])
        self.avail_dfs = {k : v for k,v in candidates.items() if v["sens_cols"] != [] and v["non_sense_cols"] != []}

        env.log.debug("[ProxyNote] available dfs {0}".format(self.avail_dfs))
        return len(self.avail_dfs) > 0

    def _test_combo(self, df, sens_col, not_sense_col):
       
        sens_col_type = resolve_col_type(df[sens_col])
        not_sense_col_type = resolve_col_type(df[not_sense_col])
        
        if sens_col_type == "unknown" or not_sense_col_type == "unknown":
            return None
        if sens_col_type == "categorical" and not_sense_col_type == "numeric":
            p = self._apply_ANOVA(df, sens_col, not_sense_col)
            if p < PVAL_CUTOFF:
                return {"sensitive_col_name" : sens_col, 
                        "proxy_col_name" : not_sense_col, "p" : p}
        if sens_col_type == "categorical" and not_sense_col_type == "categorical":
            p = self._apply_chisq(df, sens_col, not_sense_col)
            if p < PVAL_CUTOFF:
                return {"sensitive_col_name" : sens_col,
                        "proxy_col_name" : not_sense_col, "p" : p}
        if sens_col_type == "numeric" and not_sense_col_type == "numeric":
            p = self._apply_spearman(df, sens_col, not_sense_col)
            if p < PVAL_CUTOFF:
                return {"sensitive_col_name" : sens_col,
                        "proxy_col_name" : not_sense_col, "p" : p} 
        if sens_col_type == "numeric" and not_sense_col_type == "categorical":
            p = self._apply_ANOVA(df, not_sense_col, sens_col)
            if p < PVAL_CUTOFF:
                return {"sensitive_col_name" : sens_col,
                        "proxy_col_name" : not_sense_col, "p" : p} 
        return None
    def make_response(self, env, kernel_id, cell_id):
        # pylint: disable=too-many-locals
        # This just checks to make sure that the note is feasible
        # It will cause an error if not
        Notification.make_response(self, env, kernel_id, cell_id)
        
        resp = {"type" : "proxy"}
        
        for df_name, df_obj in self.avail_dfs.items():

            df = df_obj["df"]
            sense_cols = df_obj["sens_cols"]
            non_sens_cols = df_obj["non_sense_cols"]

            for sens_col in sense_cols:
                for non_sens_col in non_sens_cols:
                    result = self._test_combo(df, sens_col, non_sens_col)
                    if result:
                        resp = {"type" : "proxy", "df" : df_name}
                        resp.update(result)
 
                        if df_name not in self.data:
                            self.data[df_name] = []
                        self.data[df_name].append(resp)

    def update(self, env, kernel_id, cell_id, dfs, ns):
        # pylint: disable=too-many-arguments
        """
        Check if dataframe still defined, if proxy col and sensitive col
        still in dataframe. If so, recompute, if not remove note
        """
        
        live_resps = {}
        recent_cols = self.db.get_recent_cols(kernel_id)
        updated_cols = {}

        for col in recent_cols:
            if col["name"] not in updated_cols:
                updated_cols[col["name"]] = {"sensitive" : [], "not_sensitive" : []}
            if col["checked"] and col["is_sensitive"]:
                updated_cols[col["name"]]["sensitive"].append(col["col_name"])
            elif col["checked"]:
                updated_cols[col["name"]]["not_sensitive"].append(col["col_name"])

        env.log.debug("[ProxyNote] updating {0}".format(updated_cols))
        checked_dfs = []

        for df_name in self.data:

            if df_name not in dfs or df_name not in updated_cols:
                continue
            if df_name in checked_dfs:
                continue
            df = dfs[df_name]

            # check if sensitive column is still sensitive
            # and check if there are other columns that were 
            # not sensitive, and are sensitive now

            for sens_col in updated_cols[df_name]["sensitive"]:
                for non_sens_col in updated_cols[df_name]["not_sensitive"]:
                    result = self._test_combo(df, sens_col, non_sens_col)                        
                    if result:
                        resp = {"type" : "proxy", "df" : df_name}
                        resp.update(result)
                        if df_name not in live_resps:
                            live_resps[df_name] = []
                        live_resps[df_name].append(resp)

            checked_dfs.append(df_name)

        self.data = live_resps

    def _apply_ANOVA(self, df, sense_col, num_col):

        # pylint: disable=no-self-use

        # slight preference for keeping this as self-method just b/c
        # of code organization

        sense_col_values = df[sense_col].dropna().unique()

        if len(df[num_col].dropna().unique()) < 2: # f test is not defined if values are uniform
            return 1.0

        value_cols = [df[num_col][df[sense_col] == v].dropna() for v in sense_col_values]
 
        result = f_oneway(*value_cols)

        return result[1] # this returns the p-value
 
    def _apply_chisq(self, df, sense_col, cat_col):
        # pylint: disable=no-self-use
        # contingency table
        table = pd.crosstab(df[sense_col], df[cat_col])
        result = chi2_contingency(table.to_numpy())

        return result[1] # returns the p-value 

    def _apply_spearman(self, df, sens_col, not_sens_col):
        # pylint: disable=no-self-use
        result = spearmanr(df[sens_col], df[not_sens_col], nan_policy="omit")
        return result[1]

class MissingDataNote(ProtectedColumnNote):
    """
    A notification that measures whether there exists columns with missing data.

    Note that this requires that sensitive/protected columns actually be present in the
    dataframe. 

    data format is - 
    {
        "type" : "missing",
        "dfs" : {
            "<df_name1>" : {
                "missing_columns" : <list of all columns with missing data>,
                "<missing_col1>" : {
                    "<sensitive_col1>" : {
                        "largest_missing_value" : <the value of the sensitive column most likely to be 
                                                    missing when the missing column has missing data>,
                        "largest_percent"       : <floor(100 * (largest_missing_value / total missing data))>
                    }
                    "<sensitive_col2>" : {...}
                    "<sensitive_col3>" : {...}
                    ...
                }
            }
            "<df_name2>" : {...}
            "<df_name3>" : {...}
            ...
        }
    }
    """

    def __init__(self, db):
        super().__init__(db)
        self.missing_col_lists = {}
        self.missing_sent = 0

    # basically, if it was feasible to send a protected note and we have
    # missing data, we should be good to send a missing data note if
    # either condition is not met, don't bother
    def check_feasible(self, cell_id, env, dfs, ns):
        """check feasibility of sending a missing data note"""
        if not super().check_feasible(cell_id, env, dfs, ns):
            return False
        else:
            for df_name, df in dfs.items():
                ret = False
                if df.isnull().values.any():
                    ret = True
                    # store a pointer to the dataframe, as well as the columns with missing data
                    self.missing_col_lists[df_name] = (df, df.columns[df.isna().any()].tolist())
            return ret
         
   
    # some sort of internal variable
    def times_sent(self):
        """the number of times this notification has been sent"""
        return self.missing_sent

    # the main missing data check loop that takes in an arbitrary list of
    # dataframe names to check
    def _formulate_df_report_missing(self, df_list):
        df_report = {}

        df_report['type'] = 'missing'
        df_report['dfs'] = {}

        # loop through all dataframes with protected data
        for df_name in df_list:
            # if this dataframe also has missing data
            if df_name in self.missing_col_lists.keys():
                # get some pointers to useful stuff for code readability
                this_df_ptr = self.missing_col_lists[df_name][0]
                these_missing_cols = self.missing_col_lists[df_name][1]
                these_sensitive_cols = self.df_protected_cols[df_name]

                # initialize this dataframe entry in the dfs dictionary
                df_report['dfs'][df_name] = {}
                df_report['dfs'][df_name]['missing_columns'] = these_missing_cols.copy()

                # initialize every missing column dictionary
                for missing_col in these_missing_cols:
                    df_report['dfs'][df_name][missing_col] = {}

                # for every sensitive column
                for sensitive in these_sensitive_cols:
                    sensitive = sensitive["original_name"]
                    # for every column with missing data
                    for missing_col in these_missing_cols:
                        sensitive_frequency = {}
                        if(missing_col == sensitive): continue # prevents the same column from being compared
                        for i in range(len(this_df_ptr[missing_col])):
                            try:
                                numeric_number = float(this_df_ptr[missing_col][i])
                                if math.isnan(numeric_number):
                                    key = str(this_df_ptr[sensitive][i])
                                    if this_df_ptr[sensitive][i] in sensitive_frequency:
                                        sensitive_frequency[this_df_ptr[sensitive][i]] += 1
                                    else:
                                        sensitive_frequency[this_df_ptr[sensitive][i]] = 1
                            except ValueError:
                                pass
                        # largest missing value
                        lmv = max(sensitive_frequency.items(), key=operator.itemgetter(1))[0]
                        lmv = str(lmv) # security cast
                        # largest percent
                        lp  = math.floor(100.0 * (sensitive_frequency[lmv] / this_df_ptr[missing_col].isna().sum()))
                        
                        if not str(lp).isnumeric():
                            lp = 'NaN'

                        df_report['dfs'][df_name][missing_col][sensitive] = {}
                        df_report['dfs'][df_name][missing_col][sensitive]['largest_missing_value'] = lmv
                        df_report['dfs'][df_name][missing_col][sensitive]['largest_percent']       = lp
                for missing_col in these_missing_cols:
                    df_report['dfs'][df_name][missing_col]['number_missing'] = int(this_df_ptr[missing_col].isna().sum())
                    df_report['dfs'][df_name][missing_col]['total_length'] = len(this_df_ptr[missing_col])
                        
        return df_report

    # self.df_protected_cols should already be populated from a previous
    # check_feasible call (?)
    def make_response(self, env, kernel_id, cell_id):
        """form and store the response to send to the frontend"""
        super().make_response(env, kernel_id, cell_id)

        df_report = self._formulate_df_report_missing(self.df_protected_cols.keys())

        # export the result to a cell
        for df_name in df_report["dfs"]:
            self.data[df_name] = df_report["dfs"][df_name] 
            self.data[df_name]["type"] = "missing"
        # counter
        self.missing_sent += 1


    # loop through all the missing data notes
    def update(self, env, kernel_id, cell_id, dfs, ns):
        """check whether the note on this cell needs to be updated"""
        # pylint: disable=too-many-arguments
        new_data = {}
        for df_name, report in self.data.items():
            if df_name not in dfs:
                continue
            if df_name in self.missing_col_lists: 
                # because check_feasible just looks at all dfs with missing
                # data, data will already have been recomputed for already
                # issued notes
                new_data[df_name] = report
                self.missing_sent += 1
        env.log.debug("[MissingDataNote] updated responses")
        self.data = new_data

class ModelReportNote(Notification):
    """
    A notification that, similar to ErrorSliceNote, tests to see if any classifier models
    that have been trained perform poorly (FPR, FNR, Precision, Recall, F-Score)
    on certain columns from the original data that may have been excluded from the
    training set.
    
    Format: {"type" : "model_report", "model_name" : <name of model>,
            "acc_orig" : <original training acc>,
            "groups" : <the group the metric is checked w.r.t.>,
            "error_rates" : <dict of groups with error rates separated by member (another dict)>,
            "k_highest_error_rates" : <dict of groups with highest error rates>
            }
            error_rates format is {<group_name> : {<member_name>: error rates} }
            error_rates are given in a tuple that looks like (precision, recall, f1score, fpr, fnr)
    """
    def __init__(self, db):
        super().__init__(db)
        self.aligned_models = {} # candidates for using correction
        # self.aligned_ancestors = [] # aligned ancestor dfs
        # mapping of model name -> (x,y), used so that when doing update
        # we don't need to redo the alignment testing
        self.columns = {}
        self.k = 2 #Q? what should k be? how can user change k? (this is k highest error rates to display)

    def _get_new_models(self, cell_id, env, non_dfs_ns): 
        """
        return dictionary of model names in cell that are defined in the namespace
        and that do not already have a note issued about them
        """  
        poss_models = env.get_models()
        models = {model_name : model_info for model_name, model_info in poss_models.items() if model_name in non_dfs_ns.keys()} 

        if cell_id in self.data:
            cell_models = [model.get("model_name") for model in self.data.get(cell_id)]
        else:
            cell_models = []
       
        return {model_name : model_info for model_name, model_info in models.items() if model_name not in cell_models}


    def check_feasible(self, cell_id, env, dfs, ns):
        
        if "namespace" in ns:
            non_dfs_ns = dill.loads(ns["namespace"])
        else:
            non_dfs_ns = ns

        models = self._get_new_models(cell_id, env, non_dfs_ns)
        defined_dfs = dfs
        
        models_with_dfs = check_call_dfs(defined_dfs, non_dfs_ns, models, env)
        aligned_models = {}

        for model_name in models_with_dfs:
            match_name, match_cols, match_indexer = search_for_sensitive_cols(models_with_dfs[model_name]["x"], model_name, defined_dfs)
            if not match_name:
                continue
            env.log.debug("[ModelReportNote] model {0} has match {1}, additional info: {2}".format(model_name, match_name, models_with_dfs[model_name]))
            aligned_models[model_name] = models_with_dfs[model_name]
            df_name = models_with_dfs[model_name]["x_name"]
            aligned_models[model_name]["match"] = {"cols" : match_cols, 
                                                   "indexer" : match_indexer,
                                                   "name" : match_name,
                                                   "x_ancestor" : None,
                                                   "x_ancestor_name" : None}
            # self.aligned_ancestors = self.align_ancestor_data(env, aligned_models[model_name]["x"])
        if len(aligned_models) > 0:
            self.aligned_models = aligned_models
            return True                            
        return False

    def get_ancestor_data(self, env, curr_df_name, kernel_id):
        """
        Gets the ancestor's dataframe object with correct version
        Returns :
            ancestor_df : dataframe object
            ancestor_df_name : string name of dataframe in notebook
        """
        env.log.debug("[ModelReport] has env.ancestors = {0}".format(env.ancestors))
        for child_name, child_version in env.ancestors.keys(): # iterate because we don't know version yet
            if child_name == curr_df_name:
                ancestor_set = env.ancestors[child_name, child_version]
        ancestor_df_name, ancestor_df_version = max(ancestor_set, key=lambda x:x[1]) # return highest version (most recent)
        # first param of below is expecting dict
        # of { "name" : df_name,
        #      "kernel" : kernel_id
        #    }
        data = {
            "name" : ancestor_df_name,
            "kernel" : kernel_id
        }
        env.log.debug("[ModelReport] looking for {0}".format(data))

        ###### error handling
        try:
            ancestor_df = self.db.get_dataframe_version(data, ancestor_df_version) # load the dataframe
        except KeyError as e:
            ancestor_df = None

        if not isinstance(ancestor_df, pd.DataFrame):
            env.log.error("[ModelReport] get_dataframe_version did not find an ancestor_df.")
            env.log.debug("[ModelReport] data {0} and data version {1}".format(data, ancestor_df_version))
            return None

        env.log.debug("[ModelReport] found df: {0} with columns {1}".format(ancestor_df_name, ancestor_df.columns))
        ###### error handling
        return ancestor_df, ancestor_df_name
        
    def get_ancestor_prot_info(self, ancestor_df):
        prot_cols = guess_protected(ancestor_df)
        prot_col_names = [col["original_name"] for col in prot_cols]
        prot_cols_df = [ancestor_df[col] for col in prot_col_names]
        return prot_col_names, prot_cols_df
    def group_based_error_rates(self, env, prot_group, df, y_true, y_pred):
        """
        Compute precision, recall and f1score for a protected group in the df

        Returns: error rates for member in group : Dict{<member_value_from_group>: (precision, recall, f1score, fpr, fnr)}
        """
        error_rates_by_member = {} 

        env.log.debug("[ModelReport] prot_group: {0}".format(prot_group))
        if prot_group in df.columns:
            group_col = df[prot_group]
            env.log.debug("[ModelReport] prot_group datatypes: {0}".format(group_col.dtypes))

            # if binary
            unique_values = group_col.unique().shape[0]
            dtype = group_col.dtype
            if unique_values <= 2:
                # do binary
                mask = group_col == 1
                if not isinstance(y_true, pd.Series):
                    y_true = pd.Series(y_true)
                y_true_member = y_true.where(mask).dropna()
                # do same for preds
                if not isinstance(y_pred, pd.Series):
                    y_pred = pd.Series(y_pred)
                y_pred_member = y_pred.where(mask).dropna()

                # try:
                error_rates_by_member[prot_group] = error_rates(*acc_measures(y_true_member, y_pred_member))
                # except ZeroDivisionError as e:
                #     env.log.error("[ModelReport] Error for binary protected group {0}\nError: {1}\nlen(y_true)={2},len(y_pred)={3}".format(prot_group, e, len(y_true_member), len(y_pred_member)))
            # elif categorical
            elif unique_values > 2 and (is_unsigned_integer_dtype(dtype) or is_integer_dtype(dtype) or is_signed_integer_dtype(dtype)):
                # do categorical
                for member in group_col.unique():
                    # boolean masking
                    member_mask = group_col == member
                    member = int(member)
                    if isinstance(y_true, (pd.Series, pd.DataFrame)):
                        # y_true_member = y_true[member_indices]
                        y_true_member = y_true.where(member_mask).dropna()
                        # y_true_member = y_true.loc[member_mask.index]
                    else:
                        y_true_series = pd.Series(y_true)
                        y_true_member = y_true_series.where(member_mask).dropna()

                    # do same for y_pred
                    if isinstance(y_pred, (pd.Series, pd.DataFrame)):
                        # y_pred_member = y_pred[member_indices]
                        y_pred_member = y_pred.where(member_mask).dropna()
                        # y_pred_member = y_pred[member_mask.index]
                    else:
                        y_pred_series = pd.Series(y_pred)
                        y_pred_member = y_pred_series.where(member_mask).dropna()
                        
                    # try:
                    error_rates_by_member[member] = error_rates(*acc_measures(y_true_member, y_pred_member))
                    # except ValueError as e:
                        # env.log.error("[ModelReport] ValueError for member {0} in group {1}\nError: {2}".format(member, prot_group, e))
            # elif ordered numeric
            elif unique_values > 2 and is_numeric_dtype(type):
                # do numeric (ordered)
                # TODO: make ranges of numeric values
                pass
            else:
                env.log.error("[ModelReport] Group column is not binary, categorical or numeric. Cannot compute error rates.")
                return {}
        else:
            env.log.error("[ModelReport] prot_group: {0} not in df: {1}".format(prot_group, df.columns))
        return error_rates_by_member
    
    def sort_error_rates(self, error_rates_by_group):
        """
        Sort the error rates by the highest error rate
        sort in order of f1score, fpr, fnr, precision, recall
        Returns: error_rates_by_group = {
                                            group : 
                                                {
                                                    member :(precision, recall, f1score, fpr, fnr)
                                                }    
                                        } 
        """
        sorted_error_rates_by_group = {}
        for group_key in error_rates_by_group.keys():
            group = error_rates_by_group[group_key]
            sorting_key = lambda x: (x[1][2], x[1][3], x[1][4], x[1][0], x[1][1])
            sorted_error_rates_by_group[group_key] = dict(sorted(group.items(), key=sorting_key, reverse=True))
        return sorted_error_rates_by_group

    def get_sorted_k_highest_error_rates(self, env, col_names, model_name, x_parent_df, X, y, preds):
        """
        Method that handles getting all the error rates for the model on groups 
        specififed in `col_names`
        """
        all_error_rates = {} # {group_name : error_rates_by_member}
        for group in col_names: # list of columns identified as protected by search_for_sensitive_cols
            group_error_rates = self.group_based_error_rates(env, group, x_parent_df, y, preds)
            if group_error_rates: 
                # log the error rates
                for member in group_error_rates:
                    precision, recall, f1score, fpr, fnr = group_error_rates[member]
                    env.log.debug("[ModelReportNote] has computed these error rates for member, {4}, in group: {0}\nPrecision: {1:.4g}\nRecall: {2:.4g}\nF1Score: {3:.4g}\nFalse Positive Rate: {5:.4g}\nFalse Negative Rate: {6:.4g}"\
                                    .format(group, precision, recall, f1score, member, fpr, fnr))
                # save them
                all_error_rates[group] = group_error_rates
            else:
                env.log.debug("[ModelReportNote] has failed to compute error ratees for this group: {0}".format(group))
        sorted_error_rates = self.sort_error_rates(all_error_rates)
        # sort most important k error_rates (this is relative, no normative judgment here)
        k_highest_rates = {key: val for n, (key, val) in enumerate(sorted_error_rates.items()) if n < self.k}
        return sorted_error_rates, k_highest_rates

    def make_response(self, env, kernel_id, cell_id):
        # pylint: disable=too-many-locals,too-many-statements
        super().make_response(env, kernel_id, cell_id)

        env.log.debug("[ModelReportNote] has received a request to make a response")
        
        # Q?: why random choice?
        model_name = choice(list(self.aligned_models.keys()))
        resp = {"type" : "model_report", "model_name" : model_name}


        X = self.aligned_models[model_name]["x"]
        y = self.aligned_models[model_name]["y"]
        model = self.aligned_models[model_name]["model"]

        curr_df_name = self.aligned_models[model_name]["x_name"]
        # get ancestor df here 
        self.aligned_models[model_name]["match"]["x_ancestor"], \
            self.aligned_models[model_name]["match"]["x_ancestor_name"] \
                = self.get_ancestor_data(env, curr_df_name, kernel_id)
        if isinstance(self.aligned_models[model_name]["match"]["x_ancestor"], pd.DataFrame):
            x_ancestor = self.aligned_models[model_name]["match"]["x_ancestor"]
            x_ancestor_name = self.aligned_models[model_name]["match"]["x_ancestor"]
            # env.log.debug("[ModelReportNote] has found an ancestor of type: {0}".format( 
            #                 type(self.aligned_models[model_name]["match"]["x_ancestor"])))
            env.log.debug("[ModelReportNote] has found an ancestor df. shape: {1}, cols: {0}".format(
                            x_ancestor.columns, x_ancestor.shape))
        else:
            env.log.error("[ModelReportNote] ancestors not found")
            return

        # get acc_orig on indexed/subsetted df
        acc_orig = model.score(X, y)
        orig_preds = model.predict(X)
        orig_preds = pd.Series(orig_preds, index=X.index)

        prot_col_names, prot_cols = self.get_ancestor_prot_info(x_ancestor)
        # Find error rates for protected groups
        if prot_col_names is None or len(prot_col_names) == 0: 
            # exit? nothing to do if no groups
            env.log.debug("[ModelReportNote] has no groups to compute error rates for")
            return
        else:
            env.log.debug("[ModelReportNote] (make_response) is retrieving error rates for these columns: {0}."
                .format(prot_col_names))
            sorted_error_rates, k_highest_rates = self.get_sorted_k_highest_error_rates(env, 
                                                                                        prot_col_names, 
                                                                                        model_name, 
                                                                                        x_ancestor, 
                                                                                        X, y, 
                                                                                        orig_preds)      
        resp["acc_orig"] = acc_orig
        resp["groups"] = prot_col_names
        # TODO: check if empty?
        resp["error_rates"] = sorted_error_rates
        resp["k_highest_rates"] = k_highest_rates

        env.log.debug("[ModelReportNote] response is \n{0}".format(resp))

        if resp["model_name"] not in self.columns:
            self.columns[resp["model_name"]] = {cell_id : (X,y)}
        else:
            self.columns[resp["model_name"]][cell_id] = (X, y)
 
        if cell_id in self.data:
            self.data[cell_id].append(resp)
        else:
            self.data[cell_id] = [resp]

    def update(self, env, kernel_id, cell_id, dfs, ns):
        """
        Check if model is still defined, if not, remove note
        If model is still defined, recalculate ModelReport correction for grp
        """
        # pylint: disable=too-many-locals,too-many-arguments
        ns = self.db.recent_ns()
        non_dfs_ns = dill.loads(ns["namespace"])
        
        def check_if_defined(resp):

            if resp["model_name"] not in non_dfs_ns:
                return False

            X, y = self.columns.get(resp["model_name"]).get(cell_id)
            model = non_dfs_ns.get(resp["model_name"])

            if X is None or y is None or model is None:
                return False
            if not isinstance(model, ClassifierMixin):
                return False
            try: 
                # there's no universal way to test whether the input and 
                # output shapes match the trained model in sklearn, so this
                # is easiest
                model.score(X,y)
            except ValueError:
                return False
            return True

        live_resps = [resp for resp in self.data[cell_id] if check_if_defined(resp)]

        for resp in live_resps:
            # TODO: Might be helpful to show a diff? or at least just show the last result so the user can see what has changed
            # TODO: Implement a check if different than previous probably
            X,y = self.columns[resp["model_name"]][cell_id]
            model_name = resp["model_name"]
            model = non_dfs_ns[model_name]
            # groups = resp["groups"]
            curr_df_name = self.aligned_models[model_name]["x_name"]
            # get ancestor df here 
            self.aligned_models[model_name]["match"]["x_ancestor"], \
                self.aligned_models[model_name]["match"]["x_ancestor_name"] \
                    = self.get_ancestor_data(env, curr_df_name, kernel_id)
            x_ancestor = self.aligned_models[model_name]["match"]["x_ancestor"]
            prot_col_names, prot_cols = self.get_ancestor_prot_info(x_ancestor)
            new_preds = model.predict(X)
            new_preds = pd.Series(new_preds, index=X.index)
            new_acc = model.score(X, y)

            if prot_cols is None: 
                # exit? nothing to do if no groups
                env.log.debug("[ModelReportNote] has no groups to compute error rates for")
                return
            else:
                env.log.debug("[ModelReportNote] (update) is retrieving error rates for these columns: {0}."
                    .format(prot_col_names))    
                sorted_error_rates, k_highest_error_rates = self.get_sorted_k_highest_error_rates(env, 
                                                                                              prot_col_names, 
                                                                                              model_name, 
                                                                                              x_ancestor, 
                                                                                              X, y, 
                                                                                              new_preds)
            resp["acc_orig"] = new_acc
            resp["groups"] = prot_col_names
            resp["error_rates"] = sorted_error_rates
            resp["k_highest_error_rates"] = k_highest_error_rates

            env.log.debug("[ModelReportNote] response is \n{0}".format(resp))


        # remember to clean up non-live elements of self.columns
        live_names = [resp["model_name"] for resp in live_resps]
        old_names = [resp["model_name"] for resp in self.data[cell_id] if resp["model_name"]  not in live_names]
       
        for old_name in old_names:
            del self.columns[old_name][cell_id]
         
        self.data[cell_id] = live_resps

class ErrorSliceNote(Notification):
    """
    A notification that tests to see if any classifier models that have been
    trained perform particularly poorly (either FPR or FNR) on certain columns
    
    The return format is {"type" : "error", "model_name" : <name of model>,
                          "metric_name" : <"fpr" or "fnr">, "pos_value" : <value treated as +>,
                          "neg_value" : <value treated as ->, "slice" : [(col_name, value),...],
                          "metric_in" : <metric within the slice>, "metric_out" : <metric outside the slice>,
                          "n" : slice size}

    """
    def __init__(self, db):
        super().__init__(db)
        self.candidate_models = {}

    def _get_noted_models(self):
        return self.data.keys()

    def check_feasible(self, cell_id, env, dfs, ns):

        poss_models = env.get_models()
        old_model_names = self._get_noted_models()

        new_models = {model_name : model_info for model_name, model_info in poss_models.items() if model_name not in old_model_names}
        env.log.debug("[ErrorSliceNote] dfs {0} ns {1}".format(dfs.keys(), ns.keys()))

        defined_new_models = check_call_dfs(dfs, ns, new_models, env)

        self.candidate_models = defined_new_models # note that this has a parent df type
        env.log.debug(
            "[ErrorSliceNote] there are {0} new models out of {1} poss_models with {2} old models".format(
                len(defined_new_models), len(poss_models), len(old_model_names)))

        return self.candidate_models != {}

    def make_response(self, env, kernel_id, cell_id):
        for model, model_data in self.candidate_models.items():

            env.log.debug("[ErrorSliceNote] Making error slices for {0}".format(model))

            slices, pos_val, neg_val = self._make_slices(model_data, env)
            self._write_slices(model, slices, pos_val, neg_val)

    def update(self, env, kernel_id, cell_id, dfs, ns):
        """
        checks whether to update entries.

        update happens if 1. model is still defined in notebook and 2.
        model note was not just generated by a call to make_response

        """
        # pylint: disable=too-many-locals,too-many-arguments
        poss_models = env.get_models()
        old_model_names = self._get_noted_models()

        old_models = {model_name : model_info for model_name, model_info in poss_models.items()
                            if model_name in old_model_names and\
                               model_name not in self.candidate_models}

        models_with_dataframes = check_call_dfs(dfs, ns, old_models, env)

        for model, slice_list in self.data.items():
            if model in self.candidate_models:
                self.data[model] = slice_list
                continue
            if model not in models_with_dataframes:
                del self.data[model]
                continue

            model_data = models_with_dataframes[model]
            slices, pos_val, neg_val = self._make_slices(model_data, env)
            self._write_slices(model, slices, pos_val, neg_val)

        env.log.debug("[ErrorSliceNote] updated responses")
        # self.data = new_data # removed until update is processed, as this overwrites notes.
    def _write_slices(self, model, slices, pos_val, neg_val):
        """write to key = model, the information about slices"""
        if model not in self.data:
            self.data[model] = []
        for slice_data in slices:
            slice_data["model_name"]  = model
            slice_data["pos_value"] = str(pos_val)
            slice_data["neg_value"] = str(neg_val)
            slice_data["type"] = "error"
            slice_data["slice"] = [(sl[0], str(sl[1])) for sl in slice_data["slice"]]
            slice_data["n"] = int(slice_data["n"])

            self.data[model].append(slice_data)

    def _make_slices(self, model_data, env):
        """return slice list"""
        # pylint: disable=no-self-use
        pos_val = model_data["model"].classes_[0]
        neg_val = model_data["model"].classes_[1]
        true = (model_data["y"] == pos_val)
        predictions = model_data["model"].predict(model_data["x_parent"])
        preds = ( predictions == pos_val)
        slices = err_slices(model_data["x_parent"], preds, true, env)

        return slices, pos_val, neg_val

def align_index(obj, values, locs):
    """given a list of index values or row indices, get subset of obj's rows"""
    if isinstance(obj, (pd.Series, pd.DataFrame)):
        if len(obj.index.intersection(values)) > 0:
            if len(obj.shape) == 1:
                return obj.loc[values]
            return obj.loc[values,:]
        # then no intersection, try to use locations
        if len(obj.shape) == 1:
            return obj.iloc[locs]
        return obj.iloc[locs,:]
    # then it's either a list or an np array
    return np.take(obj, locs)

def error_rates(tp, fp, tn, fn):
    """Returns precision, recall, f1score, false positive rate and false negative rate """
    if tp < 0:
        return -1, -1, -1, -1, -1
    try:
        precision = tp / (tp+fp)
    except ZeroDivisionError:
        precision = 0

    try:
        recall = tp / (tp+fn)
    except ZeroDivisionError:
        recall = 0

    try:
        f1score = 2*(precision*recall) / (precision+recall)
    except ZeroDivisionError:
        f1score = 0

    try:
        fpr = fp / (fp+tn)
    except ZeroDivisionError:
        fpr = 0

    try:
        fnr = fn / (fn+tp)
    except ZeroDivisionError:
        fnr = 0

    return float(precision), float(recall), float(f1score), float(fpr), float(fnr)

def acc_measures(y_true, y_pred):
    """
    Computes accuracy measures for a given set of predictions and true values.

    Returns: tp, fp, tn, fn
    """
    tp = 0
    fp = 0
    tn = 0
    fn = 0
    if len(y_true) != len(y_pred):
        raise ValueError("y_true: {0} and y_pred: {1} must be the same length".format(len(y_true), len(y_pred)))
        return -1,-1,-1,-1
    for i in range(len(y_true)):
        if y_true.iloc[i] == y_pred.iloc[i]:
            if y_true.iloc[i] == 1:
                tp += 1
            else:
                tn += 1
        else:
            if y_true.iloc[i] == 1:
                fn += 1
            else:
                fp += 1
    return tp, fp, tn, fn
def make_align(index, other_index):
    """
    Return array of row indices so that df[index] will be a subset of rows of other_index

    returns an array of index values for dataframes/series with shared indices, and an array
    of locations in index for accessing numpy arrays
    """

    index_subset = index.intersection(other_index)
    index_map = {index_value : index.get_loc(index_value) for index_value in index_subset}
    other_map = {index_value : other_index.get_loc(index_value) for index_value in index_subset}

    return {"values" : index_subset,
            "loc" : index_subset.map(index_map),
            "o_loc" : index_subset.map(other_map)}

def search_for_sensitive_cols(df, df_name_to_match, df_ns):
    """
    search through dataframes to see if there are sensitive columns that
    can be associated with the inputs

    returns name of matched df, possibly empty list of columns that are potentially
    sensitive, as well as a selector if alignment based on indices or None if alignment
    based on length
    """
    # pylint: disable=too-many-branches
    # first look in df inputs themself
    protected_cols = check_for_protected(df.columns)

    if len(protected_cols) > 0:
        return df_name_to_match, [df[p["original_name"]] for p in protected_cols], None


    dfs_with_prot_attr = {}
    for df_name, df_obj in df_ns.items():
        protected_cols = check_for_protected(df_obj.columns)
        if len(protected_cols) > 0:
            dfs_with_prot_attr[df_name] = protected_cols

    # then try to match based on length and column overlap
    overlapped_cols_dfs = set()
    matched_len_dfs = set()

    for df_name in dfs_with_prot_attr:
        df_obj = df_ns[df_name]
        if any([col_name in df.columns for col_name in df_obj]):
            overlapped_cols_dfs.add(df_name)
        if len(df_obj) == len(df):
            matched_len_dfs.add(df_name)

    if len(overlapped_cols_dfs & matched_len_dfs) > 0:
        # return the df cols from the df with the highest column overlap
        overlaps = {}
        for df_name in overlapped_cols_dfs & matched_len_dfs:
            overlaps[df_name] = sum([col_name in df.columns for col_name in df_ns[df_name].columns])
        df_name = max(overlaps.keys(), key= lambda x: overlaps[x])
        names = [df_ns[df_name][p["original_name"]] for p in dfs_with_prot_attr[df_name]]
        return df_name, names, None

    # then try to match based on column overlap and index

    index_overlaps = {}
    for df_name in overlapped_cols_dfs:
        df_index = df_ns[df_name].index
        index_overlaps[df_name] = len(df.index.intersection(df_index))/float(len(df_index))
    df_name = max(index_overlaps.keys(), key = lambda x: index_overlaps[x])
    if index_overlaps[df_name] > 0 and index_overlaps[df_name] < 1:
        # intuition here is that we are testing if df is a subset of rows or columns of df_name
        names = [df_ns[df_name][p["original_name"]] for p in dfs_with_prot_attr[df_name]]
        return df_name, names, make_align(df.index, df_ns[df_name].index)

    # then just on length
    if len(matched_len_dfs) > 0:
        # at this point, no way to distinguish
        df_name = matched_len_dfs.pop()
        names = [df_ns[df_name][p["original_name"]] for p in dfs_with_prot_attr[df_name]]
        return df_name, names, None

    # then just on index
    for df_name in dfs_with_prot_attr:

        df_index = df_ns[df_name].index
        index_overlaps[df_name] = len(df.index.intersection(df_index))/float(len(df_index))

    df_name = max(index_overlaps.keys(), key=lambda key: index_overlaps[key])
    if index_overlaps[df_name] > 0:
        names = [df_ns[df_name][p["original_name"]] for p in dfs_with_prot_attr[df_name]]
        return df_name, names, make_align(df.index, df_ns[df_name].index)
    return None, [], None
def get_cols(df, cols):
    """parse columns -> get subset of df"""
    if not cols:
        return None
    if all([f in df.columns for f in cols]):
        if len(cols) == 1:
            return df[cols[0]]
    return df[cols]

def check_call_dfs(dfs, non_dfs_ns, models, env):
    """
    filter models by whether we can find dataframes assassociated with model.fit call
    """
    defined_models = {}

    for model_name, model_info in models.items():

        env.log.debug("[check_call_dfs] processing {0}".format(model_name))

        features_col_names = model_info.get("x")
        labels_col_names = model_info.get("y")

        labels_df_name = model_info.get("y_df") # if none, then cannot proceed
        features_df_name = model_info.get("x_df") # if none, then cannot proceed

        env.log.debug("[check_call_dfs] {0} in dfs {1}".format(
                                                            features_df_name,
                                                            features_df_name in dfs.keys()))
        env.log.debug("[check_call_dfs] {0} in dfs {1}".format(
                                                            labels_df_name,
                                                            labels_df_name in dfs.keys()))
        env.log.debug("[check_call_dfs] {0} in non_dfs {1}".format(
                                                            labels_df_name,
                                                            labels_df_name in non_dfs_ns.keys()))

        if (features_df_name in dfs.keys()) and\
           ((labels_df_name in dfs.keys()) or labels_df_name in non_dfs_ns.keys()):
            env.log.debug("[check_call_df] feature head")
            dfs[features_df_name].head()
            # see: https://stackoverflow.com/questions/14984119/python-pandas-remove-duplicate-columns
            features_df = dfs[features_df_name]
            features_df = features_df.loc[:,~features_df.columns.duplicated()]
            feature_df = get_cols(features_df, features_col_names)

            labels_obj = dfs.get(labels_df_name)

            if not labels_obj:
                labels_obj = non_dfs_ns.get(labels_df_name)
            if isinstance(labels_obj, pd.DataFrame):
                labels_df = get_cols(labels_obj, labels_col_names)
            else:
                labels_df = labels_obj
            defined_models[model_name] = {
                "x" : feature_df,
                "x_name" : features_df_name,
                "y" : labels_df,
                "model" : non_dfs_ns[model_name],
                "model_name" : model_name,
                "x_parent" : dfs[features_df_name],
                "y_parent" : labels_obj
            }
            env.log.debug("[check_call_df] defined model {0}".format(defined_models[model_name]))

    return defined_models

def bin_col(col):
    """
    this takes a column and bins it into two groups. Whichever has the highest
    count, that is the 1 and the rest are 0.
    """
    counts = col.value_counts(sort=True)
    max_val = counts.index.tolist()[0]

    new_col = (col != max_val).astype(int)

    return new_col

def resolve_col_type(column):
    """return whether column is categorical, numeric or other"""
    if is_numeric_dtype(column):
        return "numeric"
    if is_categorical(column):
        return "categorical"
    return "unknown"
