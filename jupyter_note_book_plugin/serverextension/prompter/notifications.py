from random import choice

import pandas as pd
import numpy as np
import dill

from scipy.stats import zscore
from sklearn.base import ClassifierMixin
from aif360.sklearn.postprocessing import CalibratedEqualizedOdds, PostProcessingMeta

from .storage import load_dfs
from .string_compare import check_for_protected
from .sortilege import is_categorical

RACE_COL_NAME = "race"
PROXY_COL_NAME = "zip"
ZIP_1 = 60637
ZIP_2 = 60611
OUTLIER_COL = "principal"
 
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

class ZipVarianceNote(OnetimeNote):
    """
    A notification that measures the variance in race between the
    zip codes 60637 and 60611

    Format is {"type" : "variance", "df" : <name of df cols are in>,
               "zip1" : 60637, "zip2" : 60611,
               "demo" : {60637 : <pct applications by black ppl>,
                         60611 : <pct applications by white ppl>}}
    """
    def check_feasible(self, cell_id, env):
        if super().check_feasible(cell_id, env):
            env._nbapp.log.debug("[ZipVar] checking columns")
            race_columns = self.db.get_columns(RACE_COL_NAME)
            zip_columns = self.db.get_columns(PROXY_COL_NAME)
            env._nbapp.log.debug("[ZipVar] columns are {0}, {1}".format(race_columns, zip_columns))
            if race_columns and zip_columns: 
                return True
            return False
        return False

    def make_response(self, env, kernel_id, cell_id):

        super().make_response(env, kernel_id, cell_id)

        resp = {"type" : "variance"}

        race_columns = self.db.get_columns(RACE_COL_NAME)
        zip_columns = self.db.get_columns(PROXY_COL_NAME)
        
        df_name = None
 
        for r_col in race_columns:
            for z_col in zip_columns:
                if r_col["name"] == z_col["name"] and r_col["version"] == z_col["version"]:
                    df_name = r_col["name"]
                    df_version = r_col["version"]
        if not df_name:
            env._nbapp.log.warning("[NOTIFICATIONS] ZipVarianceNote.make_response: cannot recover dataframe name")
            return
        curr_ns = self.db.recent_ns()
        dfs = load_dfs(curr_ns)

        if df_name not in dfs:
            env._nbapp.log.warning("[NOTIFICATIONS] ZipVarianceNote.make_response: cannot recover dataframe object of name %s" % df_name)
            return

        df = dfs[df_name]
        resp["df"] = df_name

        if RACE_COL_NAME not in df.columns or PROXY_COL_NAME not in df.columns:
            env._nbapp.log.warning("[NOTIFICATIONS] ZipVarianceNote.make_response: race or zip not in dataframe columns")
            return

        resp["zip1"] = ZIP_1
        resp["zip2"] = ZIP_2 

        resp["demo"] = self.compute_var(df, PROXY_COL_NAME, RACE_COL_NAME)
        self.data[cell_id] = [resp]

    def compute_var(self, df, proxy_col, race_col):

        panel_df = pd.get_dummies(df[race_col])
        panel_df[proxy_col] = df[proxy_col]
        rate_df = panel_df.groupby([proxy_col]).mean()

        return {ZIP_1 : int(rate_df["black"][ZIP_1]*100), ZIP_2 : int(rate_df["white"][ZIP_2]*100)}
        
    def update(self, env, kernel_id, cell_id):
        """
        check that df is still defined, still has race and zip code columns, and
        if so, recalculate whether rates are still the same
        """

        ns = self.db.recent_ns()
        dfs = load_dfs(ns)
        
        for note in self.data[cell_id]:

            df = note["df"]

            if df in dfs.keys() and\
               PROXY_COL_NAME in dfs[df].columns  and\
               RACE_COL_NAME in dfs[df].columns:
                note["demo"] = self.compute_var(dfs[df], PROXY_COL_NAME, RACE_COL_NAME)
                continue
            for other_df in dfs.keys():
                if PROXY_COL_NAME in dfs[other_df].columns and\
                   RACE_COL_NAME in dfs[other_df].columns:
                    note["df"] = other_df
                    note["demo"] = self.compute_var(dfs[other_df], PROXY_COL_NAME, RACE_COL_NAME) 
                    break
            if df != note["df"]:
                continue
            del self.data[cell_id]
            self.sent = False    
class OutliersNote(OnetimeNote):
    """
    A note that is computes whether there are outliers in the column
    named principal

    format is {"type" : "outliers", "col_name" : "principal",
               "value" : <max outlier value>, "std_dev" : <std_dev of value>,
               "df_name" : <name of dataframe column belongs to>}
    """
    def check_feasible(self, cell_id, env):
        if super().check_feasible(cell_id, env):

            columns = self.db.get_columns(OUTLIER_COL) 
            if columns: 
                return True
            return False

    def make_response(self, env, kernel_id, cell_id):
    
        super().make_response(env, kernel_id, cell_id)

        resp = {"type" : "outliers"}
        cols = self.db.get_columns(OUTLIER_COL)
      
        if not cols:
            env._nbapp.log.warning("[NOTIFICATIONS] OutlierNote.make_response: cannot find column named principal") 
            return

        df_name = cols[0]["name"]
        curr_ns = self.db.recent_ns()
        dfs = load_dfs(curr_ns)

        if df_name not in dfs:
            env._nbapp.log.warning("[NOTIFICATIONS] OutlierNote.make_response cannot recover dataframe object named %s" % df_name)
            return

        df = dfs[df_name]

        resp["col_name"] = OUTLIER_COL
        resp["df_name"] = df_name

        resp["value"], resp["std_dev"] = self.compute_outliers(df, OUTLIER_COL)

        self.data[cell_id] = [resp]

    def compute_outliers(self, df, col_name):
        
        scores = np.absolute(zscore(df[col_name]))
        index = np.argmax(scores)

        return float(df[col_name].iloc[index]), float(scores[index])

    def update(self, env, kernel_id, cell_id):
        """
        Check that df is still defined, still has outlier column in it,
        if not, try to find another df with outlier column in it
        
        Then recalculate the zscores 
        """

        ns = self.db.recent_ns()
        dfs = load_dfs(ns)
        
        for note in self.data[cell_id]:

            df_name = note["df_name"]
            col_name = note["col_name"]
            
            if df_name not in dfs.keys():

                other_dfs = [df_name for df_name in dfs.keys() if col_name in dfs[df_name].columns]

                if len(other_dfs) == 0:
                    del self.data[cell_id]
                    self.sent = False
                    continue
            
                df_name = other_dfs[0]
                df = dfs[df_name]
                note["df_name"] = df_name
 
            else:
                df = dfs[df_name]
            note["value"], note["std_dev"] = self.compute_outliers(df, col_name)
           
class PerformanceNote(Notification):
    """
    A note that computes the false positive rate and false negative rate of
    the model on training data

    Format: {"type" : "model_perf", "model_name" : <name of model>,
             "acc" : <training accuracy>, 
             "values" : {"pos" : <value treated as positive, as string>,
                         "neg" : <value treated as neg, as string>},
             "columns" : {
                <name of column to break down on> : {
                    <value of column> : {"fpr" : <training fpr on subset of data when column == value>,
                                         "fnr" : <training fnr on subset of data when column == value>}}}
    """
    def check_feasible(self, cell_id, env):

        poss_models = env.get_models()
        ns = self.db.recent_ns()
        dfs = load_dfs(ns)

        ns = dill.loads(ns["namespace"])

        models = []
        env._nbapp.log.debug("[PERFORMANCENOTE] there are {0} possible models".format(len(poss_models)))


        # cell_models is used to ensure that we're not generating a new note
        # for a model that's already had a note generated for it

        if cell_id in self.data: 
            cell_models = [model.get("model_name") for model in self.data.get(cell_id)]
        else:
            cell_models = []

        for model_name in poss_models:

            if not poss_models[model_name]: 
                env._nbapp.log.debug("[PERFORMANCENOTE] model {0} not defined".format(model_name))
                continue

            env._nbapp.log.debug("[PERFORMANCENOTE] model is: {0}".format(poss_models[model_name]))

            if "x" in poss_models[model_name]:
                features_cols = poss_models[model_name]["x"]
            else:
                features_cols = None

            if "y" in poss_models[model_name]:
                labels_cols = poss_models[model_name]["y"]
            else:
                labels_cols = None

            if "y_df" in poss_models[model_name]:
                labels_df = poss_models[model_name]["y_df"]
            else:
                labels_df = None
                
            if "x_df" in poss_models[model_name]:
                features_df = poss_models[model_name]["x_df"]
            else:   
                features_df = None

            has_model = model_name in ns.keys()
            has_features = features_df in dfs.keys() # implicit expectation that arguments are dataframes
            has_labels = (labels_df in dfs.keys()) or (labels_df in ns.keys()) 

            if has_features:
                feature_df = dfs[features_df]
                subset_features = self.get_df(feature_df, features_cols) 
            else:
                feature_df = None
            if has_labels and (labels_df in dfs.keys()):
                label_df = dfs[labels_df]
                subset_labels = self.get_df(label_df, labels_cols)
            elif has_labels and isinstance(ns[labels_df], pd.Series):
                label_df = None
                subset_labels = ns[labels_df]
            else:
                label_df = None
            # note that feasible method checks if it is feasible to generate a *new* model
            # rather than update an old one. 

            # therefore, only look to see if models defined do not already have notes
            # associated with them

            if (has_model and has_features and has_labels and (subset_features is not None) and (subset_labels is not None)):
                if model_name not in cell_models: 
                    models.append((model_name, ns[model_name], subset_features, subset_labels, feature_df, label_df)) 

        self.models = models
        if models: return True
        return False 

    def try_align(self, feature_df, candidate_df, col_name):
        """
        try and see if column of col_name in candidate_df, or feature df
        if in feature_df return column
        if in candidate_df return column if it is same length as feature df
        """

        if col_name in feature_df.columns: return feature_df[col_name]
        elif candidate_df is not None and col_name in candidate_df.columns:
            if len(candidate_df[col_name]) == len(feature_df): 
                return candidate_df[col_name]
            return None
        else:
            return None

    def get_df(self, df, cols):
        if not cols:
            return None
        if all([f in df.columns for f in cols]):
            if len(cols) == 1:
                return df[cols[0]]
            else:
                return df[cols]
        return None
         
    def times_sent(self):
        if not hasattr(self, "sent"):
            self.sent = 0
        return self.sent
    
    def make_response(self, env, kernel_id, cell_id):

        model_name, model, features_df, labels_df, full_feature, full_label = choice(self.models) # lets mix it up a little

        resp = {"type" : "model_perf"}
        resp["model_name"] = model_name
        
        env._nbapp.log.debug("[PERFORMENCENOTE] Input columns {0}".format(features_df.columns))

        subgroups = []
                 
        r_col = self.try_align(features_df, full_feature, "race")
        if r_col is not None: subgroups.append(r_col)

        s_col = self.try_align(features_df, full_feature, "sex")
        if s_col is not None: subgroups.append(s_col)

        if len(subgroups) == 0: # fall back to this option if no protected cols

            env._nbapp.log.debug("[NOTIFICATIONS] PerfNote.make_response, cannot find protected columns falling back to categorical vars")

            input_cols = [c for c in features_df.columns if is_categorical(features_df[c])]
            poss_cor_cols = [c for c in full_feature.columns if c not in input_cols and is_categorical(full_feature[c])]

            cor_cols = [self.try_align(features_df, full_feature, c) for c in poss_cor_cols]
            subgroups.extend([features_df[c] for c in input_cols])
            subgroups.extend([c for c in cor_cols if c is not None])

        env._nbapp.log.debug("[NOTIFICATIONS] Perfnote.make_response analyzing columns {0}".format([subgrp.name for subgrp in subgroups]))

        try:
            preds = model.predict(features_df)
            score = model.score(features_df, labels_df)

        except ValueError:
            env._nbapp.log.warning("[NOTIFICATIONS] PerfNote.make_response features does not match model")
            env._nbapp.log.debug("[NOTIFICATIONS] PerfNote.make_response features {0}, model {1}".format(features_df.columns, model))
            return

        pos = model.classes_[0]
        neg = model.classes_[1]

        resp["acc"] = score
        resp["values"] = {"pos" : str(pos), "neg" : str(neg)}
        resp["columns"] = {}
 
        for col in subgroups:

            col_name = col.name
            resp["columns"][col_name] = {} 

            for val in col.unique():

                mask = (col == val)

                fp = sum((preds[mask] == pos) & (labels_df[mask] == neg))
                fp = fp/(sum(labels_df[mask] == neg))

                fn = sum((preds[mask] == neg) & (labels_df[mask] == pos))
                fn = fn/(sum(labels_df[mask] == pos))

                resp["columns"][col_name][str(val)] = {"fpr" : fp, "fnr" : fn}

        env._nbapp.log.debug("[PERFORMANCENOTE] notification is {0}".format(resp))

        if cell_id in self.data:
            self.data[cell_id].append(resp)
        else:
            self.data[cell_id] = [resp]  

    def update(self, env, kernel_id, cell_id):
        """
        check if the model referenced in the current note needs to be updated

        since PerformanceNote is not a OneTimeNote subclass, we don't need
        to look for another available model here. We only need to check if the
        model named in the note needs updating.  
        """
          
        # TODO: this function and module we expect to change significantly
        # to use AIF 360 to recommend corrections 
        raise NotImplementedError

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
        # pylint: disable=too-many-locals    
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

    new_col = (col == max_val).astype(int)

    return new_col
