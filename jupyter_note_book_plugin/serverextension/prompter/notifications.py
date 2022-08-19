"""
notifications.py implements the Abstract base class of Notification
as well as implementing sub-classes. 

These are the classes that handle detecting when a notification may be
sent, what its response is composed of, and updating response contents
when relevant
"""
from random import choice, sample, random as random_number
from re import compile
from difflib import SequenceMatcher
from itertools import combinations
import math
import operator
from ast import literal_eval


import pandas as pd
from pandas.api.types import is_numeric_dtype
import numpy as np
import dill
import json

from scipy.stats import f_oneway, chi2_contingency, spearmanr, chisquare
from scipy.stats.contingency import association
from sklearn.base import ClassifierMixin

from .string_compare import check_for_protected, guess_protected, set_env
from .sortilege import is_categorical
from .slice_finder import err_slices
from .storage import clean_json, NpEncoder

PVAL_CUTOFF = 0.25 # cutoff for thinking that column is a proxy for a sensitive column

class Notification:
    """Abstract base class for all notifications"""
    def __init__(self, db):
        self.started = False # has note started being considered?
        self.displayed = False # is note being displayed?
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
    def expunge(self, dfs, non_dfs, logger=None):
        """Remove any entries that are stale"""
        pass
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
        self._suppresed = {}
        self.ncounter = 0

    def expunge(self, dfs, non_dfs, logger=None):
        """
        If df not in dfs, remove it

        TODO: this currently causes inconsistent state
        in the frontend. If df_name removed is the only one, the note
        is not updated
        """
        if logger:
            logger.debug(f"[ProtectedColumnNote.expunge] dfs are {list(dfs.keys())}")
        removed_keys = []
        for df_name in self.data:
            if df_name not in dfs:
                self._suppresed[df_name] = self.data[df_name].copy()
                if logger:
                   logger.debug(f"[ProtectedColumnNote.expunge] removing {df_name}") 
                removed_keys.append(df_name)
        for df_name in removed_keys:
            del self.data[df_name]
        if logger:
            logger.debug(f"[ProtectedColumnNote.expunge] suppresed {self._suppresed}") 
    def _check_restore(self, dfs):
        """
        if suppressed df name in dfs and not in 
        protected_cols, add it back to the data
        """

        for df_name in self._suppresed:
            if df_name not in self.df_protected_cols and df_name in dfs:
                self.data[df_name] = self._suppresed[df_name]

    def check_feasible(self, cell_id, env, dfs, ns):

        # are there any dataframes that we haven't examined?
        self.df_protected_cols = {}
        self.df_not_protected_cols = {}

        # pylint: disable=protected-access
        poss_cols = self.db.get_unmarked_columns(env._kernel_id)

        env.log.debug(f"[ProtectedColumnNote.check_feasible] dfs with unmarked_cols {poss_cols}")
        env.log.debug(f"[ProtectedColumnNote.check_feasible] suppresed dfs {self._suppresed}")

        for df_name, cols in poss_cols.items():
            if df_name not in dfs:
                continue # sometimes dfs are in database, but have been deleted
            protected_columns = check_for_protected(cols)
            # env.log.debug("[ProtectedColumnNote] ({1}) protected by name columns are {0}".format(protected_columns, self.ncounter))
            guessed_columns = guess_protected(dfs[df_name][cols])
            # env.log.debug("[ProtectedColumnNote] ({1}) protected by guess columns are {0}".format(guessed_columns, self.ncounter))
            protected_columns = self._merge_protected(protected_columns, guessed_columns)
      
            env.log.debug("[ProtectedColumnNote] ({1}) {2} protected columns are {0}".format(protected_columns, self.ncounter, df_name))
              
            protected_col_names = [c["original_name"] for c in protected_columns]
            self.df_protected_cols[df_name] = protected_columns        
            self.df_not_protected_cols[df_name] = [c for c in cols if c not in protected_col_names]
            
            self.ncounter += 1

        return self.df_protected_cols != {}

    def _noted_dfs(self, note_type):
        """return list of df names that have had notes issued on them already""" 
        notes = [note for note_set in self.data.values() for note in note_set]
        note_subset = [note for note in notes if note["type"] == note_type]
        noted_dfs = [note["df"] for note in note_subset]
        
        return noted_dfs

    
    # basically we want this function to merge with preference for 
    # detection by name
    def _merge_protected(self, by_name, by_guess):
        name_originals = [v["original_name"] for v in by_name]
        res = []
        res.extend(by_name)
        for v in by_guess:
            # if this was already guessed by name, skip
            if v["original_name"] in name_originals:
                continue
            # otherwise, include this
            res.append(v)
        return res


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
        env.log.debug(f"[ProtectedColumnNote.make_response] suppresed dfs {self._suppresed}")
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
    def _make_col_info(self, df):
        """
        return a dictionary mapping column names to type and size
        """
        col_info = {}

        for col in df.columns:
            col_info[col] = {}
            col_info[col]["size"] = len(df[col])
            col_info[col]["type"] = str(df[col].dtypes)
        return col_info
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

        self._check_restore(dfs)
        env.log.debug(f"[ProtectedColumnNote.update] suppresed dfs {self._suppresed}, {new_df_names}")
        env.log.debug(f"[ProtectedColumnNote.update] note has {list(self.data.keys())}")

        for df_name, old_protected_columns in self.data.items():

            if df_name not in dfs:
                continue
            if df_name in new_df_names: # if df is in here, then note was *just* generated
                env.log.debug(f"[ProtectedColumnNote.update] note for {df_name} was already generated")
                new_data[df_name] = old_protected_columns
                continue

            protected_cols = guess_protected(dfs[df_name])
            self.df_protected_cols[df_name] = protected_cols

            col_data = self._make_col_info(dfs[df_name]) 
            df_version = self.db.get_data_version(df_name, col_data, env._kernel_id) 

            if not df_version:
                env.log.warning(f"""[ProtectedColumnNote] no older version of {df_name} (this should never happen)""")
                continue

            col_prev = {}
            prev_cols =  self.db.get_columns(env._kernel_id, df_name, df_version)

            for col in prev_cols:
                col_prev[col["col_name"]] = {"sensitive" : bool(col["is_sensitive"]), 
                                             "user_specified" : bool(col["user_specified"]), 
                                             "fields" : col["fields"]}

            protected_col_names = [col["original_name"] for col in protected_cols]
            self.df_not_protected_cols[df_name] = [col for col in dfs[df_name].columns if col not in protected_col_names]

            env.log.debug("[ProtectedColumnNote] protected columns {0}".format(self.df_protected_cols[df_name]))
            env.log.debug("[ProtectedColumnNote] not protected columns {0}".format(self.df_not_protected_cols[df_name]))

            df_entry = self._make_resp_entry(df_name)
            update_data[df_name] = {}

            new_entry = {"type" : "resemble", "df" : df_name, "columns" : {}}
            for col_name, col_info in df_entry["columns"].items():
                if col_prev[col_name]["user_specified"]:
                    # TODO: in v2.0, we should align naming conventions for note data instances
                    # across all ecosystem components. 
                    new_entry["columns"][col_name] = col_prev[col_name]
                    new_entry["columns"][col_name]["field"] = new_entry["columns"][col_name]["fields"]

                    update_data[df_name][col_name] = col_prev[col_name]
                    update_data[df_name][col_name]["is_sensitive"] = update_data[df_name][col_name]["sensitive"]

                elif col_prev[col_name]["sensitive"] and col_info["sensitive"]:

                    field = col_info["field"]
                    if not field:
                        field = col_prev[df_name][col_name]["fields"]

                    update_data[df_name][col_name] = {"is_sensitive": True, "user_specified" : False,
                                                      "fields" : field}
                    new_entry["columns"][col_name] = {"sensitive" : True, "user_specified" : False, "field" : field}

                elif col_info["sensitive"] or col_prev[col_name]["sensitive"]:

                    field = col_info["field"]
                    if not field:
                        field = col_prev[col_name]["fields"]

                    update_data[df_name][col_name] = {"is_sensitive": True,
                                                      "user_specified" : False, "fields" : field}
                    new_entry["columns"][col_name] = {"sensitive" : True, "user_specified" : False, "field" : field} 
                else:
                    new_entry["columns"][col_name] = {"sensitive" : False,
                                                      "user_specified" : False,
                                                      "field" : None}
            new_data[df_name] = [new_entry]
        env.log.debug(f"[ProtectedColumnNote.update] updating {list(update_data.keys())}")
        self.db.update_marked_columns(kernel_id, update_data)

        self.data = new_data

class WelcomeNote(Notification):
    def __init__(self, db):
        super().__init__(db)
        self.sent = False
    
    def check_feasible(self, cell_id, env, dfs, ns):
        return not self.sent # Don't want it to be sent >1 time

    def make_response(self, env, kernel_id, cell_id):
        env.log.debug("[WelcomeNote] Making response")
        resp = {"dummy": [{"type": "welcome"}]}
        self.sent = True
        self.data = resp    
    
    def update(self, env, kernel_id, cell_id, dfs, ns):
        self.data = self.data

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

        # pre-calculate the pearson correlation coefficent for the dataframe
        
        if sens_col_type == "unknown" or not_sense_col_type == "unknown":
            return None
        if sens_col_type == "categorical" and not_sense_col_type == "numeric":
            coeff,p = self._apply_ANOVA(df, sens_col, not_sense_col)
            if not pd.isna(coeff) and p < PVAL_CUTOFF:
                return {"sensitive_col_name" : sens_col, "stat_name" : "F",
                        "proxy_col_name" : not_sense_col, "p" : p,
                        "coefficient" : round(coeff, 2)}
        if sens_col_type == "categorical" and not_sense_col_type == "categorical":
            coeff,p = self._apply_chisq(df, sens_col, not_sense_col)
            if not pd.isna(coeff) and p < PVAL_CUTOFF:
                return {"sensitive_col_name" : sens_col, "stat_name" : "Chisq",
                        "proxy_col_name" : not_sense_col, "p" : p,
                        "coefficient" : round(coeff, 2)}
        if sens_col_type == "numeric" and not_sense_col_type == "numeric":
            coeff,p = self._apply_spearman(df, sens_col, not_sense_col)
            if not pd.isna(coeff) and p < PVAL_CUTOFF:
                return {"sensitive_col_name" : sens_col, "stat_name" : "Rho",
                        "proxy_col_name" : not_sense_col, "p" : p,
                        "coefficient" : round(coeff, 2)} 
        if sens_col_type == "numeric" and not_sense_col_type == "categorical":
            coeff,p = self._apply_ANOVA(df, not_sense_col, sens_col)
            if not pd.isna(coeff) and p < PVAL_CUTOFF:
                return {"sensitive_col_name" : sens_col, "stat_name" : "F",
                        "proxy_col_name" : not_sense_col, "p" : p,
                        "coefficient" : round(coeff, 2)} 
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
            return None,1.0
        if len(sense_col_values) < 2:
            return None,1.0
        value_cols = [df[num_col][df[sense_col] == v].dropna() for v in sense_col_values]

        result = f_oneway(*value_cols)

        return result[0],result[1] # this returns the p-value
 
    def _apply_chisq(self, df, sense_col, cat_col):
        # pylint: disable=no-self-use
        # contingency table
        table = pd.crosstab(df[sense_col], df[cat_col])
        result = chi2_contingency(table.to_numpy())

        return result[0],result[1] # returns the p-value 

    def _apply_spearman(self, df, sens_col, not_sens_col):
        # pylint: disable=no-self-use
        coeff,pval = spearmanr(df[sens_col], df[not_sens_col], nan_policy="omit") 
        # spearmanr requires non constant input 
        coeff, pval = (0, 10000) if pd.isna(coeff) else (coeff, pval)
        return coeff, pval

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

        recent_cols = self.db.get_recent_cols(env._kernel_id)
        df_names = {} 
        for col in recent_cols:

            df_name = col["name"]
            if df_name not in df_names:
                df_names[df_name] = []
            df_names[df_name].append(col)
        env.log.debug(f"""[MissingDataNote] checking {df_names.keys()}""")
        for df_name in df_names:
            if df_name not in dfs:
                continue

            has_missing = dfs[df_name].isna().any().any()
            has_sensitive = any([col["is_sensitive"] for col in df_names[df_name]])

            if has_missing and has_sensitive: 
                self.missing_col_lists[df_name] = (dfs[df_name], df_names[df_name])
        env.log.debug(f"""[MissingDataNote] found {self.missing_col_lists.keys()}""")
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

            # what we want: when sens_col == x, x% are missing
            # when <sens_col> is <lmv>, missing <largest_percent>

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
                    pr_missing = sum(is_na_col)/len(is_na_col)

                    null_exp = pr_missing*df[sens_col_name].value_counts()
                    missing_count_full = pd.Series(0, index=null_exp.index)
                    missing_counts = df[sens_col_name][is_na_col].value_counts()

                    missing_count_full.loc[missing_counts.index] = missing_counts

                    diff = (missing_count_full.sum() - null_exp.sum())/len(null_exp)
                    null_exp = null_exp + diff
 
                    if missing_counts.sum() == 0:
                        continue
                    # chisquare takes as input observed differences, and expected
                    # null expectation is that missing is dist. unif. at random
                    # across each category
                    env.log.debug(f"[MissingDataNote] {missing_count_full.sum()}, {null_exp.sum()}")

                    _,p = chisquare(missing_count_full, null_exp)                    
                    # largest missing value
                    env.log.debug(f"[MissingDataNote] for {sens_col_name}, p value is {p}")
                    if p > PVAL_CUTOFF:
                        continue
                    max_value = missing_counts.idxmax()
                    lmv = str(max_value)
                    is_max_value = (df[sens_col_name] == missing_counts.idxmax())
                    is_max_and_missing = (is_max_value & is_na_col)

                    lp  = math.floor(100.0 *(sum(is_max_and_missing)/sum(is_max_value))) 
                    num_missing = sum(is_max_and_missing)
                    num_max = sum(is_max_value) 

                    sens_col_dict[sens_col_name] = {"largest_missing_value" : lmv, 
                                                    "largest_percent" : lp,
                                                    "n_missing" : str(num_missing),
                                                    "n_max" : str(num_max)}
                if len(sens_col_dict) > 0:
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
            error_rates are given in a tuple that looks like (precision, recall, f1score, fpr, fnr, n)
    """
    def __init__(self, db):
        super().__init__(db)
        self.aligned_models = {} # candidates for tabulating error types
        self._info_cache = {} # cache of notes used for generated note updating
        self.columns = {}
        self.k = 3
        self.BOUND = 0.1 # how much above/below median must a metric be to be highlighted
        self.GROUP_LIMIT = 0.01 # what fraction of data must a subgroup be before being highlighted?

    def _get_new_models(self, cell_id, env, non_dfs_ns): 
        """
        return dictionary of model names in cell that are defined in the namespace
        and that do not already have a note issued about them
        """  
        poss_models = env.get_models()
        models = {model_name : model_info for model_name, model_info in poss_models.items() if model_name in non_dfs_ns.keys()} 
        old_models = list(self.data.keys())
        
        return {model_name : model_info for model_name, model_info in models.items() if model_name not in old_models}

    def check_feasible(self, cell_id, env, dfs, ns):
        
        if "namespace" in ns:
            non_dfs_ns = dill.loads(ns["namespace"])
        else:
            non_dfs_ns = ns

        models = self._get_new_models(cell_id, env, non_dfs_ns)
        defined_dfs = dfs
        
        models_with_dfs = check_call_dfs(defined_dfs, non_dfs_ns, models, env)
        aligned_models = {}
        prot_anc_found = False

        for model_name in models_with_dfs:
            match_name, match_cols, match_indexer = search_for_sensitive_cols(env, models_with_dfs[model_name]["x"], model_name, defined_dfs)
            if not match_name:
                continue
            env.log.debug("[ModelReportNote] model {0} has match {1}, additional info: {2}".format(model_name, match_name, models_with_dfs[model_name]))
            aligned_models[model_name] = models_with_dfs[model_name]
            df_name = models_with_dfs[model_name]["x_name"]
            prot_anc_found, x_ancestor, x_ancestor_name, prot_col_names, prot_cols = self.prot_ancestors_found(env, df_name, dfs, env._kernel_id)
            if not prot_anc_found:
                continue
            aligned_models[model_name]["match"] = {"cols" : match_cols, 
                                                   "indexer" : match_indexer,
                                                   "name" : match_name,
                                                   "x_ancestor" : x_ancestor,
                                                   "x_ancestor_name" : x_ancestor_name,
                                                   "prot_col_names" : prot_col_names,
                                                   "prot_cols" : prot_cols}
        if len(aligned_models) > 0 and prot_anc_found:
            self.aligned_models = aligned_models
            return prot_anc_found                            
        return False
    def _get_prot_ancestor(self, env, df_name, dfs, kernel_id):
        """
        Find ancestor of df_name with sensitive columns
        """
        col_info = ProtectedColumnNote._make_col_info(self, dfs[df_name])
        df_version = self.db.get_data_version(df_name, col_info, kernel_id)
        
        q = [(df_name, df_version)]
        seen = set() # since there may be cycles, want to avoid infinite loops

        prot_cat_cols_list = []
        df_list = []
        version_list = []
        last_seen_prot = (prot_cat_cols_list, df_list, version_list)
        env.log.debug(f"[ModelReportNote._get_prot_ancestor] all ancestors: {env.ancestors}")
        while q != []:

            df, version = q.pop()
            # if (df, version) in env.ancestors:
            #     env.log.debug(f"[ModelReportNote._get_prot_ancestor] df:{df} version:{version} was found in env.ancestors:{env.ancestors[(df, version)]}")
                
            protected_cols = self._check_prot(df, version, kernel_id)
            protected_cat_cols = [col for col in protected_cols if is_categorical(dfs[df][col])]

            if protected_cat_cols != []:
                env.log.debug(f"[ModelReportNote._get_prot_ancestor] found new ancestor for {df_name} -> df:{df}, version:{version}, prot_cat_cols:{protected_cat_cols}")
                # find nearest ancestor with prot, then continue for other ancestors with dif prot values represented
                # resolve collisions of prot cols
                new_prot_results = check_for_protected(protected_cat_cols)
                val_to_remove = set()
                if len(prot_cat_cols_list) > 0:
                    old_prot_results = check_for_protected(prot_cat_cols_list[-1])
                    for idx, new_res in enumerate(new_prot_results):
                        for old_res in old_prot_results:
                            if new_res['protected_value'] == old_res['protected_value']:
                                col_name = new_res['original_name']
                                val_to_remove.add(col_name)
                
                for val in val_to_remove:
                    protected_cat_cols.remove(val)
                
                # save the good ones to a list
                if len(protected_cat_cols) > 0:
                    env.log.debug(f"[ModelReportNote._get_prot_ancestor] df:{df} version:{version} was found in env.ancestors:{env.ancestors[(df, version)]}")
                    prot_cat_cols_list.append(protected_cat_cols)
                    df_list.append(df)
                    version_list.append(version)
                # return protected_cat_cols, df, version

            seen.add((df, version))

            if (df, version) in env.ancestors:
                parents = env.ancestors[(df, version)]
                q.extend(list(parents - seen))
        return last_seen_prot

    def _check_prot(self, df, version, kernel):

        cols = self.db.get_columns(kernel, df, version)
        prot_col_names = []

        for col in cols:    
            if col["is_sensitive"] == 1:
                prot_col_names.append(col["col_name"])
        return prot_col_names

    def get_prot_from_aligned(self, model_name):
        '''
        Returns x_ancestor (List<DataFrame>), x_ancestor_name (List<string>), prot_col_names (List<list>), prot_cols (List<List<Series>>)
        '''
        if model_name in self.aligned_models:
            match = self.aligned_models[model_name]["match"]
            return match["x_ancestor"], match["x_ancestor_name"], match["prot_col_names"], match["prot_cols"]
        # return None, None, None, None
        return [], [], [], []

    def prot_ancestors_found(self, env, curr_df_name, dfs, kernel_id):
        '''
        Returns prot_anc_found (bool), x_ancestor (List<DataFrame>), x_ancestor_name (List<string>), prot_col_names (List<List<string>>), prot_cols (List<DataFrame or Series>)
        '''
        # Query DB for ancestor df object
        prot_col_names, ancestor_dfs, versions = self._get_prot_ancestor(env, curr_df_name, dfs, kernel_id)
        
        if prot_col_names is None or len(prot_col_names) == 0: 
            env.log.debug("[ModelReportNote] has no groups to compute error rates for")
            return False, [], [], [], []

        # get df objects
        x_ancestor = []
        for ancestor_df, version in zip(ancestor_dfs, versions):
            x_ancestor.append(self.db.get_dataframe_version({"name" : ancestor_df, "kernel" : kernel_id}, version))

        # log df objects
        for x_a in x_ancestor:
            env.log.debug("[ModelReportNote] has found an ancestor df. shape: {1}, cols: {0}".format(x_a.columns, x_a.shape))

        # prot_cols is a list of series corresponding to each df in x_ancestor
        prot_cols = []
        for prot_col_list, x_a in zip(prot_col_names, x_ancestor):
            prot_cols.append([x_a[col] for col in prot_col_list])

        # remove numerical prot_cols from prot_col sets
#        removed = []
#        for idx, prot in enumerate(prot_cols):
#            if is_numeric_dtype(prot):
#                prot_col_names.pop(idx)
#                removed.append(idx)
        # remove from prot_cols as well
#        env.log.debug(f"[ModelReportNote] {removed}, {prot_cols}")
#        for idx in removed:
#            prot_cols.remove(idx)
        # if there are only numerical prot_cols => return None
        if len(prot_col_names) == 0 or len(prot_cols) == 0:
            return False, [], [], [], []
            
        return True, x_ancestor, ancestor_dfs, prot_col_names, prot_cols

        
    def group_based_error_rates(self, env, prot_group, df, y_true, y_pred):
        """
        Compute precision, recall and f1score for a protected group in the df

        Returns: error rates for member in group : Dict{<member_value_from_group>: (precision, recall, f1score, fpr, fnr, N)}
        """
        error_rates_by_member = {} 
        df_size = len(df)
        # check if member in group is some percent of the df
        env.log.debug("[ModelReport] prot_group: {0}".format(prot_group))
        if prot_group in df.columns:
            group_col = df[prot_group]
            env.log.debug("[ModelReport] prot_group datatypes: {0}".format(group_col.dtypes))

            # if binary
            unique_values = group_col.unique().shape[0]
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
            elif unique_values > 2 and not is_numeric_dtype(group_col.dtype):
                # do categorical
                for member in group_col.unique():
                    # boolean masking
                    member_mask = group_col == member
                    if is_numeric_dtype(group_col.dtype):
                        member = int(member)
                    else:
                        member = str(member)
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
            # # TODO: add different functionality for numeric dtypes (fine as is) (postponed indefinitely)
            elif unique_values > 2 and is_numeric_dtype(group_col.dtype):
                # ideas for numeric
                # - make ranges of numeric values?
                #   - form some sort of distribution and bin the groups? 
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
        


        one_hot = {}
        cat = {}
        for group, members in error_rates_by_group.items():
            if len(members) < 2: # one hot encoding
                one_hot.update(members)
            else:
                cat.update({group:members})
        
        # one hot
        sorting_key = lambda x: (x[1][5], x[1][2], x[1][3], x[1][4], x[1][0], x[1][1])
        sorted_one_hot = dict(sorted(one_hot.items(), key=sorting_key, reverse=True))
        sorted_one_hot = {x: {x: sorted_one_hot[x]} for x in sorted_one_hot.keys() if sorted_one_hot[x][5]}

        # cat
        sorted_cat = {}
        for group_key in cat.keys():
            group = cat[group_key]
            sorting_key = lambda x: (x[1][5], x[1][2], x[1][3], x[1][4], x[1][0], x[1][1])
            sorted_cat[group_key] = dict(sorted(group.items(), key=sorting_key, reverse=True))


        return sorted_one_hot, sorted_cat

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
                    precision, recall, f1score, fpr, fnr, n = group_error_rates[member]
                    env.log.debug("[ModelReportNote] has computed these error rates for member, {4}, in group: {0}\nPrecision: {1:.4g}\nRecall: {2:.4g}\nF1Score: {3:.4g}\nFalse Positive Rate: {5:.4g}\nFalse Negative Rate: {6:.4g}\n Count: {7}"\
                                    .format(group, precision, recall, f1score, member, fpr, fnr, n))
                # save them
                all_error_rates[group] = group_error_rates
            else:
                env.log.debug("[ModelReportNote] has failed to compute error ratees for this group: {0}".format(group))
        sorted_one_hot_rates, sorted_cat_rates = self.sort_error_rates(all_error_rates)

        # env.log.debug(f"[ModelReportNote] columns: {col_names}, one hot error rates {sorted_one_hot_rates}")
        # env.log.debug(f"[ModelReportNote columns: {col_names}, cat error rates {sorted_cat_rates}")

        k_sorted_one_hot_rates = {}
        k_sorted_cat_rates = {}
        if len(sorted_one_hot_rates) > 0:
            sorted_one_hot_rates = self.filter_and_select(sorted_one_hot_rates, len(X), env)

            # separate one hot rates from multiple protected categories (we want behavior to be identical
            # for one hot and cat columns)
            prot_vals = check_for_protected(list(sorted_one_hot_rates.keys()))
            k_group_sorted_one_hot_rates = {}
            for entry in prot_vals:
                prot_val = entry['protected_value']
                col_name = entry['original_name']
                if prot_val not in k_group_sorted_one_hot_rates:
                    k_group_sorted_one_hot_rates[prot_val] = [{col_name: sorted_one_hot_rates[col_name]}]
                else:
                    k_group_sorted_one_hot_rates[prot_val].append({col_name: sorted_one_hot_rates[col_name]})
            
            for prot_group_vals in k_group_sorted_one_hot_rates.values():
                for n, member_dict in enumerate(prot_group_vals):
                    if n < self.k:
                        k_sorted_one_hot_rates = {**k_sorted_one_hot_rates, **member_dict}
                    else:
                        break


            # k_sorted_one_hot_rates = {key: val for n, (key, val) in enumerate(sorted_one_hot_rates.items()) if n < self.k and len(val) > 0}

        if len(sorted_cat_rates) > 0: 
            sorted_cat_rates = self.filter_and_select(sorted_cat_rates, len(X), env)
            k_sorted_cat_rates = {key: val for n, (key, val) in enumerate(sorted_cat_rates.items()) if n < self.k and len(val) > 0}
            k_sorted_cat_rates = {group: {} for group in sorted_cat_rates}
            for group in sorted_cat_rates:
                k_sorted_cat_rates[group] = {key: val for n, (key, val) in enumerate(sorted_cat_rates[group].items()) if n < self.k and len(val) > 0}
        k_highest_rates = {**k_sorted_one_hot_rates, **k_sorted_cat_rates}
        sorted_error_rates = {**sorted_one_hot_rates, **sorted_cat_rates}
        return sorted_error_rates, k_highest_rates
    def filter_and_select(self, error_rates, n, env):
        """
        do not return any slice with less than 1% of data
        add level to the group: group_val: metrics: (pr, recall, f1score, fpr, fnr), "highlight" : (+1, 0, -1, ...)
        """
        new_output = {}

        for group in error_rates:

            new_output[group] = {}
            group_vals = list(error_rates[group].keys())
            metric_list = ["precision", "recall", "f1score", "fpr", "fnr"]

            group_vals = [group_val for group_val in group_vals if error_rates[group][group_val][5] > n*self.GROUP_LIMIT]
            if len(group_vals) == 0:
                continue
            for metric_idx, metric in enumerate(metric_list):

                vals = np.array([error_rates[group][group_val][metric_idx] for group_val in group_vals])
                med_val = np.median(vals)

                above = vals >= med_val*(1+self.BOUND)
                below = vals <= med_val*(1-self.BOUND)

                env.log.debug(f"[ModelReportNote.filter_select] {group} bounds {med_val*(1-self.BOUND)}, {med_val*(1+self.BOUND)}")
                env.log.debug(f"[ModelReportNote.filter_select] {vals} {above}, {below}")

                for group_idx, group_val in enumerate(group_vals):
                    if group_val not in new_output[group]:
                        new_output[group][group_val] = {"metrics" : error_rates[group][group_val], 
                                                        "highlight" : [0 for metric in metric_list]} 
                    if metric in ["fpr", "fnr"]:
                        if above[group_idx]:
                            new_output[group][group_val]["highlight"][metric_idx] = -1
                        elif below[group_idx]:
                            new_output[group][group_val]["highlight"][metric_idx] = 1
                    else:
                        if above[group_idx]:
                            new_output[group][group_val]["highlight"][metric_idx] = 1
                        elif below[group_idx]:
                            new_output[group][group_val]["highlight"][metric_idx] = -1
        return new_output
    def make_response(self, env, kernel_id, cell_id):
        # pylint: disable=too-many-locals,too-many-statements
        super().make_response(env, kernel_id, cell_id)

        #env.log.debug("[ModelReportNote] has received a request to make a response")
      
        for model_name in self.aligned_models.keys(): 
            resp = {"type" : "model_report", "model_name" : model_name}

            X = self.aligned_models[model_name]["x"]
            y = self.aligned_models[model_name]["y"]
            model = self.aligned_models[model_name]["model"]

            acc_orig = model.score(X, y)
            orig_preds = model.predict(X)
            orig_preds = pd.Series(orig_preds, index=X.index)


            x_ancestors, x_ancestor_names, prot_col_names, prot_cols = self.get_prot_from_aligned(model_name)
            sorted_error_rates = {}
            k_highest_error_rates = {}
            for x_ancestor, x_ancestor_name, prot_col_name, prot_col in zip(x_ancestors, x_ancestor_names, prot_col_names, prot_cols):
                sorted_error_rate, k_highest_error_rate = self.get_sorted_k_highest_error_rates(
                    env, 
                    prot_col_name, 
                    model_name, 
                    x_ancestor, 
                    X, y, 
                    orig_preds
                ) 
                sorted_error_rates = {**sorted_error_rates, **sorted_error_rate}
                k_highest_error_rates = {**k_highest_error_rates, **k_highest_error_rate}
           

            resp["acc_orig"] = acc_orig
            resp["overall"] = error_rates(*acc_measures(y, orig_preds))
            resp["groups"] = list(set().union(*prot_col_names))
            resp["error_rates"] = sorted_error_rates
            resp["k_highest_error_rates"] = k_highest_error_rates
            resp["current_df"] = self.aligned_models[model_name]["match"]["name"]
            resp["ancestor_df"] = x_ancestor_names

            env.log.debug("[ModelReportNote] response is \n{0}".format(resp))
            self._info_cache[model_name] = self.aligned_models[model_name] 
            if resp["model_name"] not in self.columns:
                self.columns[resp["model_name"]] = (X,y)
            else:
                self.columns[resp["model_name"]] = (X, y)
 
            if model_name in self.data:
                self.data[model_name].append(resp)
            else:
                self.data[model_name] = [resp]

    def update(self, env, kernel_id, cell_id, dfs, ns):
        """
        Check if model is still defined, if not, remove note
        If model is still defined, recalculate ModelReport correction for grp
        """
        # pylint: disable=too-many-locals,too-many-arguments
        ns = self.db.recent_ns()
        non_dfs_ns = dill.loads(ns["namespace"])

        def check_if_defined(resp):

            if resp not in non_dfs_ns:
                return False

            X, y = self.columns.get(resp)
            model = non_dfs_ns.get(resp)

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

        live_resps = [model for model in self.data if check_if_defined(model)]
        updated_data = {}

        for model_name in live_resps:
        
            X = self._info_cache[model_name]["x"]
            y = self._info_cache[model_name]["y"]
            
            # match_name, match_cols, match_indexer = search_for_sensitive_cols(env, X, model_name,dfs)
            model = non_dfs_ns[model_name]

            df_name = self._info_cache[model_name]["x_name"]
            

            new_preds = model.predict(X)
            new_preds = pd.Series(new_preds, index=X.index)
            new_acc = model.score(X, y)

            # check if still sensitive

            
            prot_anc_found, x_ancestors, x_ancestor_names, prot_col_names, prot_cols = self.prot_ancestors_found(env, df_name, dfs, env._kernel_id)
            if not prot_anc_found:
                env.log.error(f"[ModelReportNote] (update) Error. no prot ancestors found in {x_ancestor_name} for current df {df_name}")
                continue
            env.log.debug("[ModelReportNote] (update) is retrieving error rates for these columns: {0}."
                .format(prot_col_names))
            env.log.debug(f"[ModelReportNote] (update) checking vars for {df_name} and {model_name}")
            env.log.debug(x_ancestors)
            env.log.debug(x_ancestor_names)
            env.log.debug(prot_col_names)
            env.log.debug(prot_cols)
            sorted_error_rates = {}
            k_highest_error_rates = {}
            for x_ancestor, x_ancestor_name, prot_col_name, prot_col in zip(x_ancestors, x_ancestor_names, prot_col_names, prot_cols):
                sorted_error_rate, k_highest_error_rate = self.get_sorted_k_highest_error_rates(
                    env, 
                    prot_col_name, 
                    model_name, 
                    x_ancestor, 
                    X, y, 
                    new_preds
                )
                env.log.debug(f"[ModelReportNote] (update) new sorted_error_rate found for {x_ancestor_name} and {prot_col_name}", sorted_error_rate)
                env.log.debug(f"[ModelReportNote] (update) new k_highest_error_rate found for {x_ancestor_name} and {prot_col_name}", k_highest_error_rate)
                sorted_error_rates = {**sorted_error_rates, **sorted_error_rate}
                k_highest_error_rates = {**k_highest_error_rates, **k_highest_error_rate}
                
            resp = {"type" : "model_report", "model_name" : model_name}
            resp["acc_orig"] = new_acc
            resp["overall"] = error_rates(*acc_measures(y, new_preds))
            resp["groups"] = list(set().union(*prot_col_names))
            resp["error_rates"] = sorted_error_rates
            resp["k_highest_error_rates"] = k_highest_error_rates
            resp["current_df"] = df_name
            resp["ancestor_df"] = x_ancestor_names
            updated_data[model_name] = [resp]
            env.log.debug("[ModelReportNote] (update) response is \n{0}".format(updated_data[model_name]))
            
        # remember to clean up non-live elements of self.columns
        live_names = [model_name for model_name in live_resps]
        old_names = [resp for resp in self.data if resp  not in live_names]
       
        for old_name in old_names:
            del self.columns[old_name]
            del self._info_cache[old_name] 
        self.data = updated_data

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

class UncertaintyNote(Notification):
    """
    Something something uncertainty...

    """
    def __init__(self, db):
        super().__init__(db)
        self.sent_count = 1
        self.T = 1 # num of trials allotted
        self._info_cache = {}
        self.columns = {}
        self.length_combinations = 2 

    def _get_new_models(self, cell_id, env, non_dfs_ns): 
        """
        return dictionary of model names in cell that are defined in the namespace
        and that do not already have a note issued about them
        """  
        poss_models = env.get_models()
        models = {model_name : model_info for model_name, model_info in poss_models.items() if model_name in non_dfs_ns.keys()} 
        old_models = list(self.data.keys())
        
        return {model_name : model_info for model_name, model_info in models.items() if model_name not in old_models}

    def check_feasible(self, cell_id, env, dfs, ns):
        # if there exists a model (prob similar to modelrepnote)
        if "namespace" in ns:
            non_dfs_ns = dill.loads(ns["namespae"])
        else:
            non_dfs_ns = ns

        models = self._get_new_models(cell_id, env, non_dfs_ns)
        defined_dfs = dfs

        models_with_dfs = check_call_dfs(defined_dfs, non_dfs_ns, models, env)
        found_models = {}
        
        env.log.info(f"[uncertainty] models_with_dfs:\n{models_with_dfs}")
        env.log.info(f"[uncertainty] models:\n{models}")
        for model_name in models_with_dfs:
            # TODO: check if model_name is in _info_cache with the same accuracy?
            if model_name in self._info_cache:
            # if this model is already in info cache, check if the accuracy is the same
                old_resp = self._info_cache[model_name]["resp"]
                X = models_with_dfs[model_name]["x"]
                y = models_with_dfs[model_name]["y"]
                accuracy = models[model_name].score(X, y)
                if (X.shape == old_resp["original_shape"] and 
                    accuracy == old_resp["original_accuracy"]):
                    continue
            found_models[model_name] = models_with_dfs[model_name]
        
        
        
        if len(found_models) > 0:
            self.found_models = found_models
            return True
        else:
            return False

    def choose_numeric(self, env, data, unique_vals, budget):
        """

        Parameters
        ----------
        env : _type_
            _description_
        unique_vals : _type_
            _description_
        budget : _type_
            _description_

        Returns
        -------
        list-like
            Randomly chosen values chose
        """
        # Random Sampling
        # chosen = sample(unique_vals, budget)
        # or 
        # max_val = np.max(unique_vals)
        # max_range = range(max_val)
        # chosen = sample(max_range, budget) # any numbers in the range from 0 
        # or 
        # quantiles = [choice(list(range(1, len(unique_vals))))/len
        # (unique_vals) for _ in range(budget)]
        # chosen = np.quantile(unique_vals, quantiles)

        if isinstance(data, pd.Series):
            values = data.values
            indices = data.index
        else:
            # raise error
            pass
        # or 
        std = data.std()
        rng = np.random.default_rng()
        deltas = np.asarray(rng.random(budget)) * 0.5 # limit range of values to [0, 0.5)
        def _choose_num(x, std, d, lower_bound, upper_bound):
            plus_minus = 1 if random_number() < 0.5 else -1
            new_x = x + (plus_minus * std * d) 
            if new_x < lower_bound:
                return lower_bound
            elif new_x > upper_bound:
                return upper_bound
            else:
                return new_x

        chosen = [data.copy() for _ in range(budget)] 
        minim = data.min()
        maxim = data.max()
        # modified copies of original data
        for b, d in enumerate(deltas):
            chosen[b] = data.apply(_choose_num, args=(std, d, minim, maxim))
        return chosen

    def choose_categorical(self, env, data, unique_vals, budget, is_one_hot):
        if isinstance(data, pd.Series):
            values = data.values
            indices = data.index
        else:
            # raise error
            pass

        
        chosen = [data.copy() for _ in range(budget)] 
        for row, idx in zip(values, indices):   
            rand_samp = sample(list(set(unique_vals) - {row}), k=budget)
            for b in range(budget):
                chosen[b][idx] = rand_samp[b]

        if is_one_hot:
            for b in range(budget):
                chosen[b] = pd.get_dummies(chosen[b])
        return chosen
    
    def generate_counterfactual(self, env, data, unique_vals, budget, is_one_hot):
        """
        Modifies a row instance for the given column, generates rows according to the given budget.


        Parameters
        ----------
        data : pd.Series, np.ndarray
             the data instance counterfactuals will be generated for
        unique_vals : pd.Series, np.ndarray
            set of unique values in the column_to_modify
        budget : int
            the maximum number of new rows to be generated

        Returns 
        -------
        Array of counterfactual values

        Raises
        ------
        """
        ctf_instances = []


        if is_categorical(data) or is_one_hot:
            ctf_instances = self.choose_categorical(env, data,
                unique_vals, budget, is_one_hot)
            # ctf_instances = sample(unique_vals, budget)
        elif is_numeric_dtype(data):
            ctf_instances = self.choose_numeric(env, data, unique_vals, budget)
        else:
            env.log.error(f"[uncertainty] no data type found for unique_vals: {unique_vals}")
            raise RuntimeError()

        env.log.info(f"[uncertainty] generated ctfs:\n{ctf_instances}")
        return ctf_instances

    def ctf_predict(self, env, model, data, ctfs, y_true, is_one_hot):
        """
        Parameters
        ----------
        env : _type_
            _description_
        model : Classifier Model
            the model used to make new classifications
        data : DataFrame
            original data tested on
        ctfs : dict
            the counter factuals \n            
            {
                col_name: [original_val', original_val'', ...],
                col_name2: [...], \n
                ...
            }
        y_true : Series
            the true y labels
            
        Returns
        -------
        dict
            New predictions \n
            {
                col_name: pd.Series(new_predictions), \n
                ...
            }
            
        """
        new_preds = {column : {} for column in ctfs.keys()}
        new_scores = {column : {} for column in ctfs.keys()} 
        new_dfs = {column : {} for column in ctfs.keys()} 
        # holds the new dataframes with the counterfactuals
        col_list = []
        if len(ctfs.keys()) > 1:
            # treat combinations as one feature -> ("income", "interest")
            new_preds = {tuple(ctfs.keys()) : {}} 
            new_scores = {tuple(ctfs.keys()) : {}}
            new_dfs = {tuple(ctfs.keys()) : {}}
            for b in range(self.T):
                data_prime = data.copy()
                orig_col_order = list(data_prime.columns)
                for column in ctfs.keys():
                    if is_one_hot[column]:
                        for col in column:
                            col_list.append(col)
                        env.log.info(f"data_prime columns before: {data_prime.columns}\n shape: {data_prime.shape}")
                        df_prime = pd.DataFrame(ctfs[column][b])
                        env.log.info(f"df_prime cols: {df_prime.columns}\n shape: {df_prime.shape}")
                        data_prime = data_prime.drop(columns=list(column))

                        if df_prime.shape[1] != len(orig_col_order):
                            env.log.info(f"column: {column}")
                            empty_cols = set(list(column)) - set(df_prime.columns)
                            empties = []
                            env.log.info(f"empty_cols: {empty_cols}")
                            for empty in empty_cols:
                                empties.append(pd.Series([0] * df_prime.shape[0], name=empty, index=df_prime.index))
                            df_prime = pd.concat([df_prime, *empties], axis=1)

                        try:
                            data_prime[list(column)] = df_prime
                        except ValueError as v:
                            env.log.error(f"{v} \ndata_prime columns: {data_prime.shape}, {data_prime.columns}, subset: {df_prime.shape} {list(column)}")
                            raise ValueError(v.args)
                        try:
                            data_prime = data_prime[orig_col_order] 
                        except ValueError as v:
                            env.log.error(f"{v}")
                            raise ValueError(v.args)
                    else:
                        col_list.append(column)
                        try:
                            col_prime = pd.Series(ctfs[column][b])
                        except ValueError as v:
                            env.log.error(f"[uncertainty] error occured with column {column} and budget {b}: {v}")
                            env.log.info(f"[uncertainty] ctfs:\n{ctfs}")
                            continue
                        data_prime[column] = col_prime

                # after modifications to data_prime ...
                new_dfs[tuple(ctfs.keys())][b] = data_prime[col_list]

                # predict
                new_preds[tuple(ctfs.keys())][b] = pd.Series(model.predict(data_prime),
                    index=data_prime.index)
                new_scores[tuple(ctfs.keys())][b] = model.score(data_prime, y_true)
        else:
            for column in ctfs.keys():
                data_prime = data.copy()
                for b in range(self.T):
                    if is_one_hot[column]:
                        # dataframe 
                        orig_col_order = list(data_prime.columns)
                        env.log.info(f"data_prime columns before: {data_prime.columns}\n shape: {data_prime.shape}")
                        df_prime = pd.DataFrame(ctfs[column][b])
                        env.log.info(f"df_prime cols: {df_prime.columns}\n shape: {df_prime.shape}")
                        data_prime = data_prime.drop(columns=list(column))

                        if df_prime.shape[1] != len(orig_col_order):
                            env.log.info(f"column: {column}")
                            empty_cols = set(list(column)) - set(df_prime.columns)
                            empties = []
                            env.log.info(f"empty_cols: {empty_cols}")
                            for empty in empty_cols:
                                empties.append(pd.Series([0] * df_prime.shape[0], name=empty, index=df_prime.index))
                            df_prime = pd.concat([df_prime, *empties], axis=1)

                        try:
                            data_prime[list(column)] = df_prime
                        except ValueError as v:
                            env.log.error(f"{v} \ndata_prime columns: {data_prime.shape}, {data_prime.columns}, subset: {df_prime.shape} {list(column)}")
                            raise ValueError(v.args)
                        try:
                            data_prime = data_prime[orig_col_order] 
                        except ValueError as v:
                            env.log.error(f"{v}")
                            raise ValueError(v.args)
                    else:
                        col_prime = pd.Series(ctfs[column][b])
                        data_prime[column] = col_prime
                    if isinstance(column, tuple):
                        new_dfs[column][b] = data_prime[list(column)]
                    else:
                        new_dfs[column][b] = data_prime[[column]]
                    new_preds[column][b] = pd.Series(model.predict(data_prime), index=data_prime.index)
                    new_scores[column][b] = model.score(data_prime, y_true)
        return new_preds, new_scores, new_dfs

    def ctf_statistics(self, env, ctf_predictions, original_predictions):
       
        '''
        want to calculate all the ctf specific data (for each feature's predictions) then
        calculate some general uncertainty calculations
        '''
        statistics = {}
        biggest_diff = {}
        for ctf_key, value in ctf_predictions.items():
            ctf_trials, ctf_accuracy = value
            # ctf_key = str(ctf_key)
            largest_diff_indices = -1
            if True: 
                # Kev Mode
                for ctf_pred in ctf_trials.values():
                    # TODO: only keep the highest diff in trials
                    # ctf_pred, ctf_accuracy = ctf_value
                    env.log.info(f"[uncertainty] generating stats for {ctf_key}")
                    env.log.info(f"[uncertainty] ctf_trials: {ctf_trials}")

                    # get the indices of rows with different preds
                    diff_indices = original_predictions[(original_predictions != ctf_pred)].index.to_list()

                    total = len(original_predictions)
                    raw_diff = len(diff_indices)
                    if raw_diff <= largest_diff_indices:
                        continue
                                        
                    try:
                        true_to_False = int(ctf_pred[original_predictions==True].value_counts()[False])
                    except KeyError:
                        true_to_False = 0
                    # num of rows where the prediction shifted from True -> False

                    try:
                        false_to_True = int(ctf_pred[original_predictions==False].value_counts()[True])
                    except KeyError:
                        false_to_True = 0
                    # num of rows where the prediction shifted from False -> True

                    env.log.debug(f"[uncertainty] {ctf_key} true_to_False: {true_to_False}, false_to_True: {false_to_True}")
                    if ctf_key not in statistics:
                        statistics[ctf_key] = {
                            'info': ctf_key,
                            'raw_diff': raw_diff,
                            'true_to_False': true_to_False,
                            'false_to_True': false_to_True,
                            'accuracy': ctf_accuracy,
                            'diff_indices': diff_indices,
                            'total': total
                        }
                        # quick fix for single features to be saved in info as a list
                        if isinstance(ctf_key, str):
                            statistics[ctf_key]['info'] = [ctf_key]
                    
                    # old as of july 13
                    # statistics[ctf_key]['raw_diff'] += raw_diff
                    # statistics[ctf_key]['true_to_False'] += true_to_False
                    # statistics[ctf_key]['false_to_True'] += false_to_True
                    # statistics[ctf_key]['total'] += total
                    
                    if "single_ctf" not in biggest_diff:
                        biggest_diff["single_ctf"] = {
                            "column": ctf_key,
                            "raw_diff": statistics[ctf_key]['raw_diff'],
                            "true_to_False": statistics[ctf_key]['true_to_False'],
                            "false_to_True": statistics[ctf_key]['false_to_True'],
                            "accuracy": statistics[ctf_key]['accuracy'],
                            "diff_indices": statistics[ctf_key]['diff_indices'],
                            "total": statistics[ctf_key]['total']
                        }
                    elif biggest_diff["single_ctf"]["raw_diff"] < raw_diff:
                        biggest_diff["single_ctf"] = {
                            "column": ctf_key,
                            "raw_diff": statistics[ctf_key]['raw_diff'],
                            "true_to_False":  statistics[ctf_key]['true_to_False'],
                            "false_to_True": statistics[ctf_key]['false_to_True'],
                            "accuracy": statistics[ctf_key]['accuracy'],
                            "diff_indices": statistics[ctf_key]['diff_indices'],
                            "total": statistics[ctf_key]['total']
                        }
                    
                    # TODO: double_ctf i.e. combinations of two - July 21: probably not doing this
            else: 
                # Galen stats
                pass
        statistics["biggest_diff"] = biggest_diff
        return statistics

    def uncertainty(self, env, model_name, mode, updated_data={}):
        resp = {"type" : "uncertainty", "model_name" : model_name, "trials" : self.T}
        try:
            X = self.found_models[model_name]["x"]
            y = self.found_models[model_name]["y"]
            model = self.found_models[model_name]["model"]
        except KeyError:
            X = self._info_cache[model_name]["x"]
            y = self._info_cache[model_name]["y"]
            model = self._info_cache[model_name]["model"]
        orig_accuracy = model.score(X,y)
        orig_predictions = pd.Series(model.predict(X), index=X.index)
        orig_indices = X.index.tolist()
        orig_shape = X.shape

        if model_name in self._info_cache and mode == "update":
            # if this model is already in info cache, check if the accuracy is the same
            old_resp = self._info_cache[model_name]["resp"]
            if (X.shape == old_resp["original_shape"] and 
                orig_accuracy == old_resp["original_accuracy"]):
                return self.wrap_up(mode, old_resp, model_name, X, y, updated_data)

        # for each feature get the ctfs and put in a dict
        # budget = self.determine_budget(env, kernel_id, cell_id, X)
        counterfactuals = {}
        new_predictions = {}
        prefixes = get_one_hot_prefix(list(X.columns))
        one_hots = [tuple(c for c in X.columns if c.startswith(pre)) for pre in prefixes]
        # subsets of one hot columns (tuple for hashability)
        while True:
            try:
                empty_elem = one_hots.index(()) # look for empty
            except ValueError:
                # no more
                break
            else:
                # remove empty (i.e. this prefix was incorrect)
                one_hots.pop(empty_elem)
                prefixes.pop(empty_elem)
        columns = []
        datas = []
        for c in X.columns:
            is_one_hot = False
            for pre in prefixes:
                if c.startswith(pre):
                    is_one_hot = True
            if not is_one_hot:
                columns.append(c)
                datas.append(X[c])
        one_hot_as_column = []
        if len(one_hots) > 0:
            env.log.debug(f"[uncertainty] one_hots: {list(one_hots)}")
            one_hot_as_column = [X[list(one_hots[idx])].idxmax(axis=1) for idx in range(len(list(one_hots)))]

        datas.extend(one_hot_as_column) 
        columns.extend(one_hots)

        env.log.debug(f"[uncertainty] prefixes: {prefixes}")
        env.log.debug(f"[uncertainty] datas: {datas}")
        env.log.debug(f"[uncertainty] columns: {columns}")

        # 1. Generate Counterfactuals
        for feature, data in zip(columns, datas):
            # generate a list of possible counterfactual values
            one_hot_feature = True if feature in one_hots else False
            feature_ctfs = self.generate_counterfactual(env, 
                data, data.unique(), budget=self.T, is_one_hot=one_hot_feature)
            counterfactuals[feature] = feature_ctfs

        # 2. Predictions
        comb_list = []
        counterfactual_dfs = {}
        for i in range(self.length_combinations):
            comb_list += list(combinations(list(counterfactuals.keys()), i+1))
        env.log.info(f"[uncertainty] combinations of features to predict: {comb_list}")
        for f in comb_list:
            _ctfs = {}
            one_hot_feature = {}
            try:
                f1, f2 = f
                two_features = True
            except ValueError:
                f_single = f[0]
                two_features = False

            if two_features:
                _ctfs = {
                    f1: counterfactuals[f1],
                    f2: counterfactuals[f2]
                }
                one_hot_feature = {}
                one_hot_feature[f1] = True if f1 in one_hots else False
                one_hot_feature[f2] = True if f2 in one_hots else False
            else:
                _ctfs = {
                    f_single: counterfactuals[f_single]
                }
                one_hot_feature = {f_single: True} if f_single in one_hots else {f_single: False}
            

            ctf_preds, ctf_accuracy, ctf_dfs = self.ctf_predict(env, model, X,
                    _ctfs, y, is_one_hot=one_hot_feature
                )
            for feat in ctf_preds.keys():
                new_predictions[feat] = (ctf_preds[feat], ctf_accuracy[feat])
                counterfactual_dfs[feat] = ctf_dfs[feat]
                env.log.info(f"[uncertainty] new preds for {f}/{feat} are:\n{new_predictions[feat]}")

        # 3. Statistics and output formatting
        ctf_statistics = self.ctf_statistics(env, new_predictions, orig_predictions)

        # get the diff (only rows with different predictions)
        diff_preds = {}
        diff_data = {}
        diff_columns = {}
        for f in ctf_statistics.keys():
            if f == "biggest_diff":
                continue
            diff_indices = ctf_statistics[f]['diff_indices']
            # trying to avoid key error from stringed tuple
            try:
                key_f = literal_eval(f)
            except ValueError:
                key_f = f

            diff_columns_, diff_preds_, diff_data_ = self.get_diff(env, 
            diff_indices, key_f, new_predictions[key_f][0], counterfactual_dfs[key_f], X, orig_predictions)
            diff_preds[f] = diff_preds_
            diff_data[f] = diff_data_
            diff_columns[f] = diff_columns_
        # resp["counterfactuals"] = clean_json(counterfactuals)
        # resp["new_predictions"] = clean_json(ctf_preds)
        resp["columns"] = clean_json(diff_columns)
        resp["original_shape"] = orig_shape
        resp["ctf_statistics"] = clean_json(ctf_statistics)
        # resp["original_values"] = diff_original
        resp["modified_values"] = clean_json(diff_data)
        # resp["original_results"] = diff_original_preds 
        resp["modified_results"] = clean_json(diff_preds)
        try:
            resp["df_name"] = self.found_models[model_name]["x_name"]
        except KeyError:
            resp["df_name"] = self._info_cache[model_name]["x_name"]
        resp["original_accuracy"] = orig_accuracy

        return self.wrap_up(mode, resp, model_name, X, y, updated_data)

    def wrap_up(self, mode, resp, model_name, X, y, updated_data=None):
        if mode == "make_response":
            self._info_cache[model_name] = self.found_models[model_name]
            self._info_cache[model_name]["resp"] = resp
            if resp["model_name"] not in self.columns:
                self.columns[resp["model_name"]] = (X,y)
            else:
                self.columns[resp["model_name"]] = (X, y)
                
            resp = json.loads(NpEncoder().encode(resp))
            if model_name in self.data:
                self.data[model_name].append(resp)
            else:
                self.data[model_name] = [resp]
            return self.data
        elif mode == "update":
            resp = json.loads(NpEncoder().encode(resp))
            updated_data[model_name] = [resp]
            return updated_data

    def make_response(self, env, kernel_id, cell_id):
        super().make_response(env, kernel_id, cell_id)
        
        for model_name in self.found_models.keys():
            self.uncertainty(env, model_name, mode="make_response")
    
    def update(self, env, kernel_id, cell_id, dfs, ns):
        ns = self.db.recent_ns()
        non_dfs_ns = dill.loads(ns["namespace"])

        def check_if_defined(resp):

            if resp not in non_dfs_ns:
                return False

            X, y = self.columns.get(resp)
            model = non_dfs_ns.get(resp)

            if X is None or y is None or model is None:
                return False
            if not isinstance(model, ClassifierMixin):
                return False
            try: 
                # there's no universal way to test whether the input and 
                # output shapes match the trained model in sklearn, so this
                # is easiest
                model.score(X,y)
                # TODO: check if this model and same accuracy is in _info_cache 
            except ValueError:
                return False
            return True 
        
        live_resps = [model for model in self.data if check_if_defined(model)]
        updated_data = {}

        for model_name in live_resps:
            updated_d = self.uncertainty(env, model_name, mode="update", 
                updated_data=updated_data)
            if updated_data:
                updated_data = updated_d
        # remember to clean up non-live elements of self.columns
        live_names = [model_name for model_name in live_resps]
        old_names = [resp for resp in self.data if resp not in live_names]
    
        for old_name in old_names:
            del self.columns[old_name]
            del self._info_cache[old_name] 
        self.data = updated_data

    def get_diff(self, env, indices, feature, predictions, df, X, orig_preds):
        # diff_predictions = {}
        # diff_df = {}
        # for b in predictions.keys():
        #     diff_predictions[b] = predictions[b].loc[indices]
        #     diff_df[b] = df[b].loc[indices]
        # return diff_predictions, diff_df
        preds = pd.concat([orig_preds.loc[indices], predictions[0].loc[indices]], axis=1)
        df = df[0].loc[indices] # NOTE: limiting to just one "trial" (AKA b or budget previously) for simplification
        column_set = set(X.columns.tolist())
        modified_indicator = '_mod'
        if isinstance(feature, tuple):
            for mod_f in feature:
                if isinstance(mod_f, tuple):
                    for c in mod_f:
                        column_set.add(c+modified_indicator)
                else:
                    column_set.add(mod_f+modified_indicator)
        else:
            column_set.add(feature+modified_indicator)
        column_set = list(column_set)
        column_set.sort() # place '_mod' features after their originals
        env.log.debug(f"[uncertainty] column_set for {feature} is {column_set}")
        
        df.columns = [c+modified_indicator for c in df.columns]
        diff_df = X.join(df, how='right')
        diff_df = diff_df[column_set]
        
        return column_set, preds, diff_df

def error_rates(tp, fp, tn, fn):
    """Returns precision, recall, f1score, false positive rate, false negative rate, and the number of rows """
    if tp < 0:
        return -1, -1, -1, -1, -1, -1
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
    n = tp+fp+fn+tn
    return float(precision), float(recall), float(f1score), float(fpr), float(fnr), float(n)

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

def search_for_sensitive_cols(env, df, df_name_to_match, df_ns):
    """
    search through dataframes to see if there are sensitive columns that
    can be associated with the inputs

    returns name of matched df, possibly empty list of columns that are potentially
    sensitive, as well as a selector if alignment based on indices or None if alignment
    based on length
    """
    # pylint: disable=too-many-branches
    # first look in df inputs themself
    if isinstance(df, pd.DataFrame):
        protected_cols = check_for_protected(df.columns)
    elif isinstance(df, pd.Series):
        protected_cols = check_for_protected(df.name)

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
            env.log.debug("[check_call_df] feature head:")
            env.log.debug(dfs[features_df_name].head())
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
            env.log.debug("[check_call_df] defined model {1} - {0}".format(defined_models[model_name], model_name))

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

def get_one_hot_prefix(columns):
    substring_counts={}
    
    special_char = compile('[@_!#$%^&*()<>?/\|}{~:]')
    for i in range(0, len(columns)):
        for j in range(i+1,len(columns)):
            string1 = columns[i]
            string2 = columns[j]
            match = SequenceMatcher(None, string1, string2).find_longest_match(0, len(string1), 0, len(string2))
            matching_substring=string1[match.a:match.a+match.size]
            if(matching_substring not in substring_counts):
                if (special_char.search(matching_substring)):
                    substring_counts[matching_substring]=1
            else:
                substring_counts[matching_substring]+=1

    return [prefix for prefix, occurences in substring_counts.items() if occurences > 1 and len(prefix) > 0]
