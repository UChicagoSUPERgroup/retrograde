import json
from random import choice

import pandas as pd
import numpy as np
import operator
import dill
import math

from scipy.stats import zscore, f_oneway, chi2_contingency
from sklearn.base import ClassifierMixin
from aif360.sklearn.postprocessing import CalibratedEqualizedOdds, PostProcessingMeta
from pandas.api.types import is_numeric_dtype

from .storage import load_dfs
from .string_compare import check_for_protected
from .sortilege import is_categorical

import json # REMOVE BEFORE PUSHING

PVAL_CUTOFF = 0.25 # cutoff for thinking that column is a proxy for a sensitive column
STD_DEV_CUTOFF = 0.1 # cutoff for standard deviation change that triggers difference in OutliersNotes


class Notification:
    """Abstract base class for all notifications"""
    def __init__(self, db):
        self._feasible = False
        self.db = db
        self.data = {}

        # data format is cell id -> {note info}

    def feasible(self, cell_id, env, dfs, ns):
        """is it feasible to send this notification?"""
        ret_value = self.check_feasible(cell_id, env, dfs, ns)
        self._feasible = ret_value 
        return ret_value
   
    def times_sent(self):
        """the number of times this notification has been sent"""
        return 0 

    def make_response(self, env, kernel_id, cell_id):
        """form and store the response to send to the frontend""" 
        if not self._feasible:
            raise Exception("Cannot call make_response on notification that is not feasible")
    
    def on_cell(self, cell_id):
        """has this note been associated with the cell with this id?"""
        return cell_id in self.data

    def get_response(self, cell_id): 
        """what response was associated with this cell, return None if no response"""
        return self.data.get(cell_id)
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

    def check_feasible(self, cell_id, env, dfs, ns):

        # are there any dataframes that we haven't examined?
        df_cols = {}
        
        for df_name, df in dfs.items():
            if df_name not in self.df_protected_cols:
                df_cols[df_name] = [col for col in df.columns] 

        for df_name, cols in df_cols.items():

            protected_columns = check_for_protected(cols)
            self.df_protected_cols[df_name] = protected_columns

        if df_cols:
            return True
        return False
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
        noted_dfs = self._noted_dfs("resemble")

        for df_name in self.df_protected_cols.keys():
            if df_name not in noted_dfs:

                resp = self._make_resp_entry(df_name)
                if cell_id not in self.data:
                    self.data[cell_id] = []
                self.data[cell_id].append(resp)

    def _make_resp_entry(self, df_name):

        protected_columns_string = ', '.join([p["original_name"] for p in self.df_protected_cols[df_name]])
        protected_values_string = ', '.join([p["protected_value"] for p in self.df_protected_cols[df_name]]) 

        resp = {"type" : "resemble"}
        resp["df"] = df_name
        resp["col"] = protected_columns_string
        resp["category"] = protected_values_string
        resp["col_names"] = [p["original_name"] for p in self.df_protected_cols[df_name]]

        return resp

    def update(self, env, kernel_id, cell_id, dfs, ns):
        # pylint: disable=too-many-arguments
        new_data = {}
        for cell, note_list in self.data.items():
            new_notes = []
            for note in note_list:
                if note["type"] == "resemble":

                    df_name = note["df"]
                    
                    if df_name in dfs:

                        protected_cols = check_for_protected(dfs[df_name].columns)
                        self.df_protected_cols[df_name] = protected_cols
                        new_notes.append(self._make_resp_entry(df_name))
                else:
                    new_notes.append(note)
            new_data[cell] = new_notes

        env.log.debug("[ProtectedColumnNote] updated responses")

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
        super().check_feasible(cell_id, env, dfs, ns) # populates self.df_protected_cols
        # note that we don't care about return value because even if there are no 
        # new dfs, the columns may have changed
 
        self.avail_dfs = {}

        # find dfs that have not had notes issued on them already
        noted_dfs = self._noted_dfs("proxy")

        for df_name in self.df_protected_cols:
            if df_name not in noted_dfs:
                sense_col_names = [c["original_name"] for c in self.df_protected_cols[df_name]]
                non_sensitive_cols = [c for c in dfs[df_name].columns if c not in sense_col_names]
                if len(non_sensitive_cols) != 0 and len(sense_col_names) != 0: 
                    self.avail_dfs[df_name] = {
                        "df" : dfs[df_name],    
                        "sens_cols" : sense_col_names,
                        "non_sense_cols" : non_sensitive_cols
                    }
        return len(self.avail_dfs) > 0

    def make_response(self, env, kernel_id, cell_id):
        # pylint: disable=too-many-locals
        # This just checks to make sure that the note is feasible
        # It will cause an error if not
        Notification.make_response(self, env, kernel_id, cell_id)
        
        resp = {"type" : "proxy"}
        
        combos = {"categorical" : [], "numeric" : []}
 
        for df_name, df_obj in self.avail_dfs.items():

            df = df_obj["df"]
            sense_cols = df_obj["sens_cols"]
            non_sens_cols = df_obj["non_sense_cols"]

            for col in non_sens_cols:
                if is_categorical(df[col]):
                    for sense_col in sense_cols:
                        combos["categorical"].append((df_name, sense_col, col))
                elif is_numeric_dtype(df[col]):
                    for sense_col in sense_cols:
                        combos["numeric"].append((df_name, sense_col, col))
                else:
                    env.log.debug("[ProxyNote] ProxyNote.make_response encountered column {0} of uncertain type {1} in {2}".format(col, df[col].dtypes, df_name))

            results = []
            # for numeric, apply one way ANOVA to see if sensitive category -> difference in numeric variable
            for num_combos in combos["numeric"]:
                env.log.debug("[ProxyNote] make_response : analyzing column {0} as numeric".format(num_combos[2]))
                results.append({"df" : num_combos[0], 
                                "sensitive_col_name" : num_combos[1],
                                "proxy_col_name" : num_combos[2],
                                "p" : self._apply_ANOVA(df, num_combos[1], num_combos[2])}) 
            # if proxy candidate is categorical, use chi square test
            for num_combos in combos["categorical"]:
                env.log.debug("[ProxyNote] make_response : analyzing column {0} as categorical".format(num_combos[2]))
                results.append({"df" : num_combos[0], 
                                "sensitive_col_name" : num_combos[1],
                                "proxy_col_name" : num_combos[2],
                                "p" : self._apply_chisq(df, num_combos[1], num_combos[2])})

            results.sort(key = lambda x: x["p"]) 
            env.log.debug("[ProxyNote] ProxyNote.make_response, there are {0} possible combinations, min value {1}, max {2}".format(len(results), results[0], results[-1]))

            for result in results:
                if result["p"] <= PVAL_CUTOFF:
                    resp = {"type" : "proxy"}
                    resp.update(result)
                    if cell_id not in self.data:
                        self.data[cell_id] = []
                    self.data[cell_id].append(resp)
          
    def _apply_ANOVA(self, df, sense_col, num_col):

        # pylint: disable=no-self-use

        # slight preference for keeping this as self-method just b/c
        # of code organization

        sense_col_values = df[sense_col].dropna().unique()
        value_cols = [df[num_col][df[sense_col] == v].dropna() for v in sense_col_values]
 
        result = f_oneway(*value_cols)

        return result[1] # this returns the p-value
 
    def _apply_chisq(self, df, sense_col, cat_col):
        # pylint: disable=no-self-use
        # contingency table
        table = pd.crosstab(df[sense_col], df[cat_col])
        result = chi2_contingency(table.to_numpy())

        return result[1] # returns the p-value 

    def update(self, env, kernel_id, cell_id, dfs, ns):
        # pylint: disable=too-many-arguments
        """
        Check if dataframe still defined, if proxy col and sensitive col
        still in dataframe. If so, recompute, if not remove note
        """
        
        live_resps = {}

        for cell in self.data:
            live_resps[cell] = []
            for note in self.data[cell]:

                df_name = note["df"]
                proxy_col = note["proxy_col_name"]
                sense_col = note["sensitive_col_name"]

                if df_name not in dfs:
                    continue
                df = dfs[df_name]
                if proxy_col not in df.columns or sense_col not in df.columns:
                    continue
                if is_categorical(df[proxy_col]):
                    p = self._apply_chisq(df, sense_col, proxy_col)
                elif is_numeric_dtype(df[proxy_col]):
                    p = self._apply_ANOVA(df, sense_col, proxy_col)
                else:
                    continue
                if p > PVAL_CUTOFF:
                    continue

                new_note = note
                new_note["p"] = p 
                live_resps[cell].append(new_note)

        self.data = live_resps

# TODO: inheret from ProxyColumnNote, and check both protected and proxy columns
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
                    sensitive = sensitive["protected_value"]
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
        if cell_id not in self.data:
            self.data[cell_id] = []
        self.data[cell_id].append(df_report)

        # counter
        self.missing_sent += 1


    # loop through all the missing data notes
    def update(self, env, kernel_id, cell_id, dfs, ns):
        """check whether the note on this cell needs to be updated"""
        new_data = {}
        for cell, note_list in self.data.items():
            new_notes = []
            for note in note_list:
                if note["type"] == "missing":
                    # grab the dfs that are in the missing note and are flagged to up updated
                    df_update_list = [df_name for df_name in note['dfs'].keys() if df_name in dfs]
                    # generate an updated autopsy report based on those dfs only
                    updated_report = self._formulate_df_report_missing(df_update_list)
                    # append this note to new_notes
                    new_notes.append(updated_report)

                    # counter
                    self.missing_sent += 1
                else:
                    # the note stays the same
                    new_notes.append(note)
            new_data[cell] = new_notes
        env.log.debug("[MissingDataNote] updated responses")
        self.data = new_data


class OutliersNote(Notification):
    """
    A note that computes whether there are outliers in a numeric column
    defined in a dataframe

    format is {"type" : "outliers", "col_name" : <name of column with outliers>,
               "value" : <max outlier value>, "std_dev" : <std_dev of value>,
               "df_name" : <name of dataframe column belongs to>}
    """
    def __init__(self, db):
        super().__init__(db)
        self.numeric_cols = []

    def check_feasible(self, cell_id, env, dfs, ns):

        numeric_cols = []
        for df_name, df in dfs.items():
            for col in df.columns:
                if not is_categorical(df[col]) and is_numeric_dtype(df[col]):
                    numeric_cols.append({"df_name" : df_name,  "col_name" : col})
        if len(numeric_cols) > 0: 
            self.numeric_cols = numeric_cols
            return True
        return False

    def make_response(self, env, kernel_id, cell_id):
    
        super().make_response(env, kernel_id, cell_id)

        curr_ns = self.db.recent_ns()
        dfs = load_dfs(curr_ns)

        resp = {"type" : "outliers"}
        outlier_cols = []
 
        for num_col in self.numeric_cols:

            df = dfs[num_col["df_name"]]                         
            col = num_col["col_name"]
            value, std_dev = self._compute_outliers(df, col)
            outlier_cols.append({
                "df_name" : num_col["df_name"],
                "col_name" : col,
                "value" : value,
                "std_dev" : std_dev})
        outlier_cols.sort(key = lambda x: x["std_dev"], reverse=True)

        env.log.debug("[OutlierNote] outlier columns {0}".format(outlier_cols))

        resp.update(outlier_cols[0])
 
        self.data[cell_id] = [resp]

    def _compute_outliers(self, df, col_name):
        # pylint: disable=no-self-use 
        col = df[col_name].dropna()  
        scores = np.absolute(zscore(col))
        index = np.argmax(scores)

        return float(col.iloc[index]), float(scores[index])

    def update(self, env, kernel_id, cell_id, dfs, ns):
        """
        Check that df is still defined, still has outlier column in it,
        and zscore is still similar
       
        If not, then remove and reset 
        """
        # pylint: disable=too-many-arguments
        live_notes = []
 
        for note in self.data[cell_id]:

            df_name = note["df_name"]
            col_name = note["col_name"]
            std_dev = note["std_dev"]
 
            if df_name not in dfs.keys():
                continue
            if col_name not in dfs[df_name].columns:
                continue
            new_value, new_std_dev = self._compute_outliers(dfs[df_name], col_name)
            if abs(new_std_dev - std_dev)/std_dev >= STD_DEV_CUTOFF:
                continue
            live_notes.append({
                "df_name" : df_name,
                "col_name" : col_name,
                "std_dev" : new_std_dev,
                "value" : new_value}) 
        if len(live_notes) == 0:
            # pylint: disable=attribute-defined-outside-init
            self.sent = False
        self.data[cell_id] = live_notes


class EqualizedOddsNote(Notification):
    """
    A note that takes models trained in the namespace and tries applying
    the AIF post-processing correction to the model.
    
    Fomat: {"type" : "eq_odds", "model_name" : <name of model>,
            "acc_orig" : <original training acc>,
            "acc_corr" : <training accuracy, when correction is applied>,
            "eq" : <"fpr" or "fnr", the metric being equalized>,
            "num_changed" : <number of different predictions after correction applied>,
            "groups" : <the group the metric is equalized w.r.t.>}
    """
    def __init__(self, db):
        super().__init__(db)
        self.aligned_models = {} # candidates for using correction

        # mapping of model name -> (x,y), used so that when doing update
        # we don't need to redo the alignment testing
        self.columns = {}

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
        
        non_dfs_ns = dill.loads(ns["namespace"])

        models = self._get_new_models(cell_id, env, non_dfs_ns)
        defined_dfs = dfs
        
        models_with_dfs = check_call_dfs(defined_dfs, non_dfs_ns, models)
        aligned_models = {}

        for model_name in models_with_dfs:
            match_name, match_cols, match_indexer = search_for_sensitive_cols(models_with_dfs[model_name]["x"], model_name, defined_dfs)
            if not match_name:
                continue
            aligned_models[model_name] = models_with_dfs[model_name]
            aligned_models[model_name]["match"] = {"cols" : match_cols, 
                                                   "indexer" : match_indexer,
                                                   "name" : match_name}
        if len(aligned_models) > 0:
            self.aligned_models = aligned_models
            return True                            
        return False

    def make_response(self, env, kernel_id, cell_id):
        # pylint: disable=too-many-locals,too-many-statements
        super().make_response(env, kernel_id, cell_id)
        
        model_name = choice(list(self.aligned_models.keys()))
        resp = {"type" : "eq_odds", "model_name" : model_name}


        X = self.aligned_models[model_name]["x"]
        y = self.aligned_models[model_name]["y"]
        model = self.aligned_models[model_name]["model"]

        match_cols = self.aligned_models[model_name]["match"]["cols"]
        match_indexer = self.aligned_models[model_name]["match"]["indexer"]

        col_names = [col.name for col in match_cols]

        # do the alignment of the data if necessary
        if match_indexer is not None:

            X = align_index(X, match_indexer["values"], match_indexer["loc"])
            y = align_index(y, match_indexer["values"], match_indexer["loc"])

            match_cols = [align_index(col, match_indexer["values"], match_indexer["o_loc"]) for col in match_cols]

        match_cols = [bin_col(col) for col in match_cols]
        # create the properly indexed dataframes
        if isinstance(X.index, pd.MultiIndex):
            flat_index = X.index.to_flat_index()
            arrs = [[idx[i] for idx in flat_index] for i in range(len(flat_index[0]))]
            X_index = pd.MultiIndex.from_arrays(arrs + match_cols, names=X.index.names + col_names)
        else: 
            X_index = pd.MultiIndex.from_arrays([X.index] + match_cols, names= [X.index.name] + col_names)
        X.index = X_index

        if isinstance(y, (pd.Series, pd.DataFrame)):
            y.index = X_index
        else:
            y = pd.Series({"y" : y}, index=X_index)
              
        # get acc_orig on indexed/subsetted df
        acc_orig = model.score(X, y)
        orig_preds = model.predict(X)

        # apply correction
        corrections = []

        env.log.debug("[EqOddsNote] Using input \n{0}".format(X.head()))

        for grp in col_names:
            for constraint in ["fpr", "fnr"]:
             
                pp = CalibratedEqualizedOdds(grp, cost_constraint=constraint)
                ceo = PostProcessingMeta(estimator=model, postprocessor=pp)
                ceo.fit(X, y)
                acc = ceo.score(X, y)
                preds = ceo.predict(X)

                corrections.append({"grp" : grp, "constraint": constraint, 
                                    "acc" : acc, "preds" : sum(preds != orig_preds)})

        # get acc_corr
        # select the group that negatively impacts original accuracy the least
        # we could also try selecting the change that would affect the smallest number of predictions
        env.log.debug("[EqOddsNote] possible corrections are {0}".format(corrections)) 
        inv = max(corrections, key = lambda corr: corr["acc"])

        resp["acc_corr"] = inv["acc"]
        resp["eq"] = inv["constraint"]
        resp["num_changed"] = int(inv["preds"])
        resp["groups"] = inv["grp"]
        resp["acc_orig"] = acc_orig

        env.log.debug("[EqOddsNote] response is {0}".format(resp))

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
        If model is still defined, recalculate EqOdds correction for grp
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

            X,y = self.columns[resp["model_name"]][cell_id]
            model = non_dfs_ns[resp["model_name"]]
            grp = resp["groups"]
            constraint = resp["eq"]

            acc_orig = model.score(X,y)
            pred_orig = model.predict(X)
 
            pp = CalibratedEqualizedOdds(grp, cost_constraint=constraint)
            ceo = PostProcessingMeta(estimator=model, postprocessor=pp)
            ceo.fit(X,y)
            acc = ceo.score(X,y)
            preds = ceo.predict(X)

            resp["acc_corr"] = acc
            resp["acc_orig"] = acc_orig
            resp["num_changed"] = int(sum(pred_orig != preds))


        # remember to clean up non-live elements of self.columns
        live_names = [resp["model_name"] for resp in live_resps]
        old_names = [resp["model_name"] for resp in self.data[cell_id] if resp["model_name"]  not in live_names]
       
        for old_name in old_names:
            del self.columns[old_name][cell_id]
         
        self.data[cell_id] = live_resps

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
    
    returns name of matched df, possibly empty list of columns that are potentially sensitive, as well as a 
    selector if alignment based on indices or None if alignment based on length
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
        return df_name, [df_ns[df_name][p["original_name"]] for p in dfs_with_prot_attr[df_name]], None

    # then try to match based on column overlap and index

    index_overlaps = {}
    for df_name in overlapped_cols_dfs:
        df_index = df_ns[df_name].index
        index_overlaps[df_name] = len(df.index.intersection(df_index))/float(len(df_index))
    df_name = max(index_overlaps.keys(), key = lambda x: index_overlaps[x])
    if index_overlaps[df_name] > 0 and index_overlaps[df_name] < 1:
        # intuition here is that we are testing if df is a subset of rows or columns of df_name
        return df_name, [df_ns[df_name][p["original_name"]] for p in dfs_with_prot_attr[df_name]], make_align(df.index, df_ns[df_name].index)

    # then just on length
    if len(matched_len_dfs) > 0:
        # at this point, no way to distinguish
        df_name = matched_len_dfs.pop()
        return df_name, [df_ns[df_name][p["original_name"]] for p in dfs_with_prot_attr[df_name]], None

    # then just on index
    for df_name in dfs_with_prot_attr:

        df_index = df_ns[df_name].index
        index_overlaps[df_name] = len(df.index.intersection(df_index))/float(len(df_index))

    df_name = max(index_overlaps.keys(), key=lambda key: index_overlaps[key])
    if index_overlaps[df_name] > 0:
        return df_name, [df_ns[df_name][p["original_name"]] for p in dfs_with_prot_attr[df_name]], make_align(df.index, df_ns[df_name].index)
    return None, [], None
def get_cols(df, cols):
    """parse columns -> get subset of df"""
    if not cols:
        return None
    if all([f in df.columns for f in cols]):
        if len(cols) == 1:
            return df[cols[0]]
    return df[cols]

def check_call_dfs(dfs, non_dfs_ns, models):
    """
    filter models by whether we can find dataframes assassociated with model.fit call 
    """
    defined_models = {}
    
    for model_name, model_info in models.items():

        features_col_names = model_info.get("x")
        labels_col_names = model_info.get("y")
        
        labels_df_name = model_info.get("y_df") # if none, then cannot proceed
        features_df_name = model_info.get("x_df") # if none, then cannot proceed 
        
        if (features_df_name in dfs.keys()) and\
           ((labels_df_name in dfs.keys()) or labels_df_name in non_dfs_ns.keys()):

            feature_df = get_cols(dfs[features_df_name], features_col_names)
            
            labels_obj = dfs.get(labels_df_name)

            if not labels_obj:
                labels_obj = non_dfs_ns.get(labels_df_name)
            if isinstance(labels_obj, pd.DataFrame):
                labels_df = get_cols(labels_obj, labels_col_names)
            else:
                labels_df = labels_obj
            defined_models[model_name] = {
                "x" : feature_df,
                "y" : labels_df,
                "model" : non_dfs_ns[model_name],
                "model_name" : model_name,
                "x_parent" : dfs[features_df_name], 
                "y_parent" : labels_obj 
            } 
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

class NewNote(Notification):
    """
    A note that computes whether there are outliers in a numeric column
    defined in a dataframe

    format is {"type" : "outliers", "col_name" : <name of column with outliers>,
               "value" : <max outlier value>, "std_dev" : <std_dev of value>,
               "df_name" : <name of dataframe column belongs to>}
    """
    def __init__(self, db):
        super().__init__(db)

    def check_feasible(self, cell_id, env, dfs, ns):
        # are there any dataframes that we haven't examined?
        df_cols = {}
        
        for df_name, df in dfs.items():
            if df.isnull().values.any(): return True

        return False

    def make_response(self, env, kernel_id, cell_id):
        env.log.debug("[NewNote] Debug 2")    
        curr_ns = self.db.recent_ns()
        dfs = load_dfs(curr_ns)
        super().make_response(env, kernel_id, cell_id)
        self.sent = True
        resp = {
            "type" : "missing",
            "dfs": {}
        }

        # Format
        # {
        #     "df_name": "loans",
        #     "length-of-df": 2000
        #     "columns": {
        #         "income": {
        #           "count": <int of how many times a null value exists>,
        #           "mode": [
        #               [<column name>, <column mode>, <times the mode exists within the shortened df>, <length of the shortened df>]
        #           ]}
        #     }
        # }
        # Collecting data
        df_cols = {} 
        dfs_callable = {}
        
        for df_name, df in dfs.items():
            dfs_callable[df_name] =  df
            df_cols[df_name] = [col for col in df.columns]
            resp["dfs"][df_name] = {
                "df_name": df_name,
                "columns": {},
                "total_length": len(dfs_callable[df_name])
            }

        for df_name, cols in df_cols.items():
            for col_name in cols:
                # Get the actual dataframe w/ the columns & count # of rows null
                df = dfs_callable[df_name]
                df_col = df[col_name]
                amount_null = df_col.isnull().sum()
                if amount_null == 0: continue
                # Get the entire dataframe where this specific column is null
                df_col_with_column_null = df[df[col_name].isnull()][df.columns].astype(str)
                # Iterate over each column and find it's mode
                null_column_correlation = []
                for column in df_col_with_column_null:
                    if column == col_name: continue
                    mode_raw = df_col_with_column_null[column].mode(dropna=False)
                    if len(mode_raw) >= 1:
                        mode = mode_raw[0]
                    else:
                        mode = np.nan
                    if mode == np.nan or mode == "nan" or pd.isna(mode): 
                        specific_col = df_col_with_column_null[column]
                        mode_count = specific_col.isnull().sum()
                        mode = "NaN"
                    else: mode_count = df_col_with_column_null[column].value_counts(dropna=False)[mode]
                    null_column_correlation.append([column, mode, int(mode_count), len(df_col_with_column_null)])
                resp["dfs"][df_name]["columns"][col_name] = {
                    "count": int(amount_null),
                    "mode": null_column_correlation
                }

        if cell_id in self.data:
            self.data[cell_id].append(resp)
        else:
            self.data[cell_id] = [resp]


    def update(self, env, kernel_id, cell_id, dfs, ns):
        """
        Check that df is still defined, still has outlier column in it,
        and zscore is still similar
       
        If not, then remove and reset 
        """
        # Commented out until update logic is worked out
        # resp = {"type" : "TESTING",
        #     "to do": "something2"}
        # if cell_id in self.data:
        #     self.data[cell_id].append(resp)
        # else:
        #     self.data[cell_id] = [resp]
