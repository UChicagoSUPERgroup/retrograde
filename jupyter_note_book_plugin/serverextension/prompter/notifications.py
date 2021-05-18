from random import choice

import pandas as pd
import numpy as np
import dill

from scipy.stats import zscore, f_oneway, chi2_contingency
from sklearn.base import ClassifierMixin
from aif360.sklearn.postprocessing import CalibratedEqualizedOdds, PostProcessingMeta
from pandas.api.types import is_numeric_dtype

from .storage import load_dfs
from .string_compare import check_for_protected
from .sortilege import is_categorical

PVAL_CUTOFF = 0.25 # cutoff for thinking that column is a proxy for a sensitive column
STD_DEV_CUTOFF = 0.1 # cutoff for standard deviation change that triggers difference in OutliersNotes


class Notification:
    """Abstract base class for all notifications"""
    def __init__(self, db):
        self._feasible = False
        self.db = db
        self.data = {}

        # data format is cell id -> {note info}

    def feasible(self, cell_id, env):
        """is it feasible to send this notification?"""
        ret_value = self.check_feasible(cell_id, env)
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
    def update(self, env, kernel_id, cell_id):
        """check whether the note on this cell needs to be updated"""
        raise NotImplementedError
    def check_feasible(self, cell_id, env):
        """check feasibility of implementing class"""
        raise NotImplementedError("check_feasible must be overridden") 
class OnetimeNote(Notification):
    """
    Abstract base class for notification that is sent exactly once
    """

    def __init__(self, db):
        super().__init__(db)
        self.sent = False

    def check_feasible(self, cell_id, env):
        return (not self.sent)
    
    def times_sent(self):
        return int(self.sent)

    def make_response(self, env, kernel_id, cell_id):
        super().make_response(env, kernel_id, cell_id)
        self.sent = True

class ProtectedColumnNote(OnetimeNote):

    """
    a class that indicates whether a protected column is present in
    an active dataframe.

    data format is {"type" : "resemble", 
                    "col" : "race", "category" : "race"
                    "df" : <df name or "unnamed">}
    """
    def __init__(self, db):

        super().__init__(db)
        self.df_protected_cols = {}

    def check_feasible(self, cell_id, env):
        if super().check_feasible(cell_id, env):

            ns = self.db.recent_ns()
            dfs = load_dfs(ns)
       
            df_cols = {}

            for df_name, df in dfs.items():
                 df_cols[df_name] = [col for col in df.columns] 

            for df_name, cols in dfs.items():

                protected_columns = check_for_protected(cols)
                self.df_protected_cols[df_name] = protected_columns

            if self.df_protected_cols:
                return True
            return False
        return False

    def make_response(self, env, kernel_id, cell_id):

        super().make_response(env, kernel_id, cell_id)
        resp = {"type" : "resemble"}
        #using protected columns found in csv build string to display in notification
        df_name = choice(list(self.df_protected_cols.keys()))

        protected_columns_string = ', '.join([p["original_name"] for p in self.df_protected_cols[df_name]])
        protected_values_string = ', '.join([p["protected_value"] for p in self.df_protected_cols[df_name]]) 

        resp["df"] = df_name
        resp["col"] = protected_columns_string
        resp["category"] = protected_values_string

        self.data[cell_id] = [resp]

    def update(self, env, kernel_id, cell_id):
        """
        check if column with RACE_COL_NAME is still in df.columns
        if so, nothing happens, if RACE_COL_NAME still defined, but no longer
        in df of df_name, update df name
        if no longer in namespace, remove note altogether
        """

        ns = self.db.recent_ns()
        dfs = load_dfs(ns)

        for note in self.data[cell_id]:

            col_name = note["col"]
            df_name = note["df"]

            if df_name in dfs.keys():
                if col_name in dfs[df_name].columns:
                    continue
            for other_df in dfs.keys():
                if col_name in dfs[other_df].columns:
                    note["df"] = other_df
                    break
            if note["df"] != df_name:
                continue
            del self.data[cell_id]
            self.sent = False # unset this so it can be sent again

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
    
    def check_feasible(self, cell_id, env):
        if super().check_feasible(cell_id, env):
            # check if any of the dataframes also have numeric or categorical columns
            ns = self.db.recent_ns()
            dfs = load_dfs(ns)

            diff_cols = []
            
            for df_name in self.df_protected_cols:

                sense_col_names = [c["original_name"] for c in self.df_protected_cols[df_name]]
                non_sensitive_cols = [c for c in dfs[df_name].columns if c not in sense_col_names]
                if len(non_sensitive_cols) != 0: 
                    diff_cols.append(df_name)

            self.df_protected_cols = {df_name : cols for df_name, cols in self.df_protected_cols.items() if df_name in diff_cols}
            return len(self.df_protected_cols) > 0

        return False

    def make_response(self, env, kernel_id, cell_id):

        OnetimeNote.make_response(self, env, kernel_id, cell_id)
        
        resp = {"type" : "proxy"}
        
        ns = self.db.recent_ns()
        dfs = load_dfs(ns)

        combos = {"categorical" : [], "numeric" : []}
 
        for df_name, sense_cols in self.df_protected_cols.items():

            sense_col_names = [c["original_name"] for c in sense_cols]

            if df_name not in dfs:
                env._nbapp.log.debug("[ProxyNote] ProxyNote.make_response df {0} cannot be found in namespace".format(df_name))
                continue

            df = dfs[df_name]
            avail_cols = [c for c in dfs[df_name].columns if c not in sense_col_names]

            for col in avail_cols:
                if is_categorical(df[col]):
                    for sense_col in sense_cols:
                        combos["categorical"].append((df_name, sense_col["original_name"], col))
                elif is_numeric_dtype(df[col]):
                    for sense_col in sense_cols:
                        combos["numeric"].append((df_name, sense_col["original_name"], col))
                else:
                    env._nbapp.log.debug("[ProxyNote] ProxyNote.make_response encountered column {0} of uncertain type {1} in {2}".format(col, df[col].dtypes, df_name))

        results = []
        # for numeric, apply one way ANOVA to see if sensitive category -> difference in numeric variable
        for num_combos in combos["numeric"]:
            env._nbapp.log.debug("[ProxyNote] make_response : analyzing column {0} as numeric".format(num_combos[2]))
            results.append({"df_name" : num_combos[0], 
                            "sensitive_col_name" : num_combos[1],
                            "proxy_col_name" : num_combos[2],
                            "p" : self._apply_ANOVA(dfs[num_combos[0]], num_combos[1], num_combos[2])}) 
        # if proxy candidate is categorical, use chi square test
        for num_combos in combos["categorical"]:
            env._nbapp.log.debug("[ProxyNote] make_response : analyzing column {0} as categorical".format(num_combos[2]))
            results.append({"df_name" : num_combos[0], 
                            "sensitive_col_name" : num_combos[1],
                            "proxy_col_name" : num_combos[2],
                            "p" : self._apply_chisq(dfs[num_combos[0]], num_combos[1], num_combos[2])})

        results.sort(key = lambda x: x["p"]) 
        env._nbapp.log.debug("[ProxyNote] ProxyNote.make_response, there are {0} possible combinations, min value {1}, max {2}".format(len(results), results[0], results[-1]))

        if results[0]["p"] > PVAL_CUTOFF:
            env._nbapp.log.debug("[ProxyNote] ProxyNote.make_response: none of the associations are strong enough to consider as proxies")
            self.sent = False
        else:
            resp.update(results[0])
            self.data[cell_id] = [resp]
          
    def _apply_ANOVA(self, df, sense_col, num_col):

        sense_col_values = df[sense_col].dropna().unique()
        value_cols = [df[num_col][df[sense_col] == v].dropna() for v in sense_col_values]
 
        result = f_oneway(*value_cols)

        return result[1] # this returns the p-value
 
    def _apply_chisq(self, df, sense_col, cat_col):

        # contingency table
        table = pd.crosstab(df[sense_col], df[cat_col])
        result = chi2_contingency(table.to_numpy())

        return result[1] # returns the p-value 

    def update(self, env, kernel_id, cell_id):
        """
        Check if dataframe still defined, if proxy col and sensitive col
        still in dataframe. If so, recompute, if not remove note
        """
        
        ns = self.db.recent_ns()
        dfs = load_dfs(ns)

        live_resps = []

        for note in self.data[cell_id]:

            df_name = note["df_name"]
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
            live_resps.append(new_note)

        if len(live_resps) != len(self.data[cell_id]):
            self.data[cell_id] = live_resps
            self.sent = False

class OutliersNote(OnetimeNote):
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

    def check_feasible(self, cell_id, env):
        if super().check_feasible(cell_id, env):
            ns = self.db.recent_ns()
            dfs = load_dfs(ns)

            numeric_cols = []
            for df_name, df in dfs.items():
                for col in df.columns:
                    if not is_categorical(df[col]) and is_numeric_dtype(df[col]):
                        numeric_cols.append({"df_name" : df_name,  "col_name" : col})
            if len(numeric_cols) > 0: 
                self.numeric_cols = numeric_cols
                return True
            return False
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

        env._nbapp.log.debug("[OutlierNote] outlier columns {0}".format(outlier_cols))

        resp.update(outlier_cols[0])
 
        self.data[cell_id] = [resp]

    def _compute_outliers(self, df, col_name):
        # pylint: disable=no-self-use 
        col = df[col_name].dropna()  
        scores = np.absolute(zscore(col))
        index = np.argmax(scores)

        return float(col.iloc[index]), float(scores[index])

    def update(self, env, kernel_id, cell_id):
        """
        Check that df is still defined, still has outlier column in it,
        and zscore is still similar
       
        If not, then remove and reset 
        """

        ns = self.db.recent_ns()
        dfs = load_dfs(ns)
       
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


    def check_feasible(self, cell_id, env):
        
        ns = self.db.recent_ns()
        non_dfs_ns = dill.loads(ns["namespace"])

        models = self._get_new_models(cell_id, env, non_dfs_ns)
        defined_dfs = load_dfs(ns)
        
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

        env._nbapp.log.debug("[EqOddsNote] Using input \n{0}".format(X.head()))

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
        env._nbapp.log.debug("[EqOddsNote] possible corrections are {0}".format(corrections)) 
        inv = max(corrections, key = lambda corr: corr["acc"])

        resp["acc_corr"] = inv["acc"]
        resp["eq"] = inv["constraint"]
        resp["num_changed"] = int(inv["preds"])
        resp["groups"] = inv["grp"]
        resp["acc_orig"] = acc_orig

        env._nbapp.log.debug("[EqOddsNote] response is {0}".format(resp))

        if resp["model_name"] not in self.columns:
            self.columns[resp["model_name"]] = {cell_id : (X,y)}
        else:
            self.columns[resp["model_name"]][cell_id] = (X, y)
 
        if cell_id in self.data:
            self.data[cell_id].append(resp)
        else:
            self.data[cell_id] = [resp]
    def update(self, env, kernel_id, cell_id):
        """
        Check if model is still defined, if not, remove note
        If model is still defined, recalculate EqOdds correction for grp
        """
        # pylint: disable=too-many-locals
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