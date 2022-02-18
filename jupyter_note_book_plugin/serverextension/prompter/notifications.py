"""
notifications.py implements the Abstract base class of Notification
as well as implementing sub-classes. 

These are the classes that handle detecting when a notification may be
sent, what its response is composed of, and updating response contents
when relevant
"""

import math
import operator

import pandas as pd
import numpy as np

from scipy.stats import f_oneway, chi2_contingency, spearmanr
from pandas.api.types import is_numeric_dtype

from .string_compare import check_for_protected, guess_protected
from .sortilege import is_categorical
from .slice_finder import err_slices

PVAL_CUTOFF = 0.25 # cutoff for thinking that column is a proxy for a sensitive column
STD_DEV_CUTOFF = 0.1 # cutoff for standard deviation change that triggers difference in OutliersNotes

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

        # Grab user-defined columns and puts them in a usable structure
        # format:
        # most_recent_cols[<df names>][<col names>] = {"user_specified": ..., "fields":..., etc.}
        """
        most_recent_cols_from_db = self.db.get_recent_cols(env._kernel_id)
        most_recent_cols = {}
        for db_record in most_recent_cols_from_db:
            if db_record["name"] not in most_recent_cols:
                most_recent_cols[db_record["name"]] = {}
            most_recent_cols[db_record["name"]][db_record["col_name"]] = {
                "sensitive": db_record["is_sensitive"] == 1,
                "user_specified" : db_record["user_specified"] == 1, "field" : db_record["fields"]
            }
        """
        # original part of the function; given the columns within a dataframe, it updates whether they
        # are sensitive or not and their fields
        for col in self.df_protected_cols[df_name]:
            resp["columns"][col["original_name"]] = {"user_specified": False, "sensitive" : True, "field" : col["protected_value"]}
        for col in self.df_not_protected_cols[df_name]:
            resp["columns"][col] = {"user_specified": False, "sensitive" : False, "field" : None}

        # compares old data to determine if any needs to be overwritten (ignore auto classification)
        # if self.protected_columns has this column, override it with the data that the user entered
        """
        if df_name in most_recent_cols:
                for col_name, old_col_info in most_recent_cols[df_name].items():
                    if old_col_info["user_specified"]:
                        if col_name in resp["columns"]:
                            resp["columns"][col_name] = old_col_info
        """
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
        recent_cols = self.db.get_recent_cols(env._kernel_id)

        col_prev = {}

        for col_entry in recent_cols:

            df_name = col_entry["name"]
            col_name = col_entry["col_name"]
            is_sensitive = col_entry["is_sensitive"]
            user_specified = col_entry["user_specified"]
            fields = col_entry["fields"]

            if df_name not in col_prev:
                col_prev[df_name] = {}
            if col_name  not in col_prev[df_name]:
                col_prev[df_name][col_name] = {}
            col_prev[df_name][col_name] = {"sensitive" : is_sensitive, "user_specified" : user_specified, "fields" : fields}


        for df_name, old_protected_columns in self.data.items():

            if df_name not in dfs:
                continue
            if df_name in new_df_names: # if df is in here, then note was *just* generated
                new_data[df_name] = old_protected_columns
                continue

            # check columns AND values
            protected_cols = guess_protected(dfs[df_name])
            self.df_protected_cols[df_name] = protected_cols

            protected_col_names = [col["original_name"] for col in protected_cols]
            self.df_not_protected_cols[df_name] = [col for col in dfs[df_name].columns if col not in protected_col_names]

            env.log.debug("[ProtectedColumnNote] protected columns {0}".format(self.df_protected_cols[df_name]))
            env.log.debug("[ProtectedColumnNote] not protected columns {0}".format(self.df_not_protected_cols[df_name]))

            df_entry = self._make_resp_entry(df_name)
            update_data[df_name] = {}

            new_entry = {"type" : "resemble", "df" : df_name, "columns" : {}}
            for col_name, col_info in df_entry["columns"].items():
                if col_prev[df_name][col_name]["user_specified"]:
                    # TODO: in v2.0, we should align naming conventions for note data instances
                    # across all ecosystem components. 
                    new_entry["columns"][col_name] = col_prev[df_name][col_name]
                    new_entry["columns"][col_name]["field"] = new_entry["columns"][col_name]["fields"]

                    update_data[df_name][col_name] = col_prev[df_name][col_name]
                    update_data[df_name][col_name]["is_sensitive"] = update_data[df_name][col_name]["sensitive"]

                elif col_prev[df_name][col_name]["sensitive"] and col_info["sensitive"]:

                    field = col_info["field"]
                    if not field:
                        field = col_prev[df_name][col_name]["fields"]

                    update_data[df_name][col_name] = {"is_sensitive": True, "user_specified" : False,
                                                      "fields" : field}
                    new_entry["columns"][col_name] = {"sensitive" : True, "user_specified" : False, "field" : field}

                elif col_info["sensitive"] or col_prev[df_name][col_name]["sensitive"]:

                    field = col_info["field"]
                    if not field:
                        field = col_prev[df_name][col_name]["fields"]

                    update_data[df_name][col_name] = {"is_sensitive": True,
                                                      "user_specified" : False, "fields" : field}
                    new_entry["columns"][col_name] = {"sensitive" : True, "user_specified" : False, "field" : field} 
                else:
                    new_entry["columns"][col_name] = {"is_sensitive" : False,
                                                      "user_specified" : False,
                                                      "field" : None}
            new_data[df_name] = [new_entry]
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
        if len(sense_col_values) < 2:
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
    Feasible when there are defined dataframes that have both sensitive columns and columns
    with *explicitly* missing values (ie filler values like -99 or "NaN" or string typed will
    not be detected)

    {"type" : "missing",
     "df" : df_name,
     "missing_columns" : {
        missing_col_name : { 
            "number_missing" : number of missing entries in column,
            "total_length" : length of column,
            "sens_cols" : {
                sens_col_name : {"largest_missing_value" : value of column in sens_col with largest number of missing instances in missing_col,
                                 "largest_percent" : percent of values composed by largest missing value,
                                }...}
    }
    """

    def __init__(self, db):
        super().__init__(db)

        # cache of columns to be checked
        self.missing_col_lists = {}
        self.missing_sent = 0

    def check_feasible(self, cell_id, env, dfs, ns):
        """check feasibility of sending a missing data note"""
        if not super().check_feasible(cell_id, env, dfs, ns):
            return False

        recent_cols = self.db.get_recent_cols(env._kernel_id)
        df_names = {} 
        for col in recent_cols:

            df_name = col["name"]
            if df_name not in df_names:
                df_names[df_name] = []
            df_names[df_name].append(col)

        for df_name in df_names:
            if df_name not in dfs:
                continue

            has_missing = dfs[df_name].isna().any().any()
            has_sensitive = any([col["is_sensitive"] for col in df_names[df_name]])

            if has_missing and has_sensitive: 
                self.missing_col_lists[df_name] = (dfs[df_name], df_names[df_name])
        return self.missing_col_lists != {}
         
   
    # some sort of internal variable
    def times_sent(self):
        """the number of times this notification has been sent"""
        return self.missing_sent

    # the main missing data check loop that takes in an arbitrary list of
    # dataframe names to check
    def _formulate_df_report_missing(self, env):
        dfs = []
        # loop through all dataframes with protected data
        for df_name in self.missing_col_lists:
            # get some pointers to useful stuff for code readability
            df = self.missing_col_lists[df_name][0]
            cols = self.missing_col_lists[df_name][1]

            missing_cols = df.columns[df.isna().any()]
            sense_cols = [col for col in cols if col["is_sensitive"]]
           
            df_report = {"type" : "missing", "df" : df_name, "missing_columns" : {}}
 
            for missing_col in missing_cols:

                is_na_col = df[missing_col].isna()

                df_report["missing_columns"][missing_col] = {
                    "number_missing" : int(is_na_col.sum()),
                    "total_length" : len(is_na_col)}

                sens_col_dict = {}

                for sens_col in sense_cols:
                    if sens_col == missing_col:
                        continue
                    sens_col_name = sens_col["col_name"]
                    missing_counts = df[sens_col_name][is_na_col].value_counts()
                     
                    # largest missing value
                    lmv = str(missing_counts.idxmax())

                    # largest percent
                    env.log.debug("[MissingDataNote] missing counts {0}".format(missing_counts))
                    lp  = math.floor(100.0 * (missing_counts[missing_counts.idxmax()]/missing_counts.sum()))
                    
                    sens_col_dict[sens_col_name] = {"largest_missing_value" : lmv, "largest_percent" : lp}
   
                df_report["missing_columns"][missing_col]["sens_col"] = sens_col_dict
            dfs.append(df_report)
 
        return dfs

    # self.df_protected_cols should already be populated from a previous
    # check_feasible call (?)
    def make_response(self, env, kernel_id, cell_id):
        """form and store the response to send to the frontend"""
#        super().make_response(env, kernel_id, cell_id)

        df_reports = self._formulate_df_report_missing(env)
        # export the result to a cell
        for df_report in df_reports:
            self.data[df_report["df"]] = [df_report]
        #    self.data[df_name]["type"] = "missing"
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
#        env.log.debug("[MissingDataNote] updated responses")
        self.data = new_data

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
