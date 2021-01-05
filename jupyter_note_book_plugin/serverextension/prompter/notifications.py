import pandas as pd
import numpy as np
import dill
import re

from scipy.stats import zscore
from random import choice

from .storage import load_dfs
from .sortilege import is_categorical

RACE_COL_NAME = "race"
PROXY_COL_NAME = "zip"
ZIP_1 = 60637
ZIP_2 = 60611
OUTLIER_COL = "principal"
 
class Notification:
    """Abstract base class for all notifications"""
    def __init__(self, db):
        self.db = db
        self.data = {}

        # data format is cell id -> {note info}

    def feasible(self, cell_id, env):
        """is it feasible to send this notification?"""
        return False
   
    def times_sent(self):
        """the number of times this notification has been sent"""
        return 0 

    def make_response(self, env, kernel_id, cell_id):
        """form and store the response to send to the frontend""" 
        raise NotImplementedError
    
    def on_cell(self, cell_id):
        """has this note been associated with the cell with this id?"""
        return cell_id in self.data

    def get_response(self, cell_id): 
        """what response was associated with this cell, return None if no response"""
        return self.data.get(cell_id)
    def update(self, env, kernel_id, cell_id):
        """check whether the note on this cell needs to be updated"""
        raise NotImplementedError

class OnetimeNote(Notification):
    """
    Abstract base class for notification that is sent exactly once
    """

    def __init__(self, db):
        super().__init__(db)
        self.sent = False

    def feasible(self, cell_id, env):
        return (not self.sent)
    
    def times_sent(self):
        return int(self.sent)

    def make_response(self, env, kernel_id, cell_id):
        self.sent = True

class SensitiveColumnNote(OnetimeNote):

    """
    a class that indicates whether a sensitive column is present in
    an active dataframe.

    data format is {"type" : "resemble", 
                    "col" : "race", "category" : "race"
                    "df" : <df name or "unnamed">}
    """

    def feasible(self, cell_id, env):
        if super().feasible(cell_id, env):
            columns = self.db.get_columns(RACE_COL_NAME)
            if columns: 
                self.df_name = columns[0]["name"]
                return True
            return False
        return False

    def make_response(self, env, kernel_id, cell_id):

        super().make_response(env, kernel_id, cell_id)

        resp = {"type" : "resemble"}
        resp["col"] = RACE_COL_NAME
        resp["category"] = RACE_COL_NAME

        if hasattr(self, "df_name"):
            resp["df"] = self.df_name
        else:
            resp["df"] = "unnamed"
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
                    return
            for other_df in dfs.keys():
                if col_name in dfs[other_df].columns:
                    note["df"] = other_df
                    return
            del self.data[cell_id]
            self.sent = False # unset this so it can be sent again

class ZipVarianceNote(OnetimeNote):
    """
    A notification that measures the variance in race between the
    zip codes 60637 and 60611

    Format is {"type" : "variance", 
               "zip1" : 60637, "zip2" : 60611,
               "demo" : {60637 : <pct applications by black ppl>,
                         60611 : <pct applications by white ppl>}}
    """
    def feasible(self, cell_id, env):
        if super().feasible(cell_id, env):
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

        if RACE_COL_NAME not in df.columns or PROXY_COL_NAME not in df.columns:
            env._nbapp.log.warning("[NOTIFICATIONS] ZipVarianceNote.make_response: race or zip not in dataframe columns")
            return
        panel_df = pd.get_dummies(df[RACE_COL_NAME])
        panel_df[PROXY_COL_NAME] = df[PROXY_COL_NAME]

        rate_df = panel_df.groupby([PROXY_COL_NAME]).mean() 

        resp["zip1"] = ZIP_1
        resp["zip2"] = ZIP_2 

        resp["demo"] = {ZIP_1 : int(rate_df["black"][ZIP_1]*100), ZIP_2 : int(rate_df["white"][ZIP_2]*100)}
        self.data[cell_id] = [resp]

class OutliersNote(OnetimeNote):
    """
    A note that is computes whether there are outliers in the column
    named principal

    format is {"type" : "outliers", "col_name" : "principal",
               "value" : <max outlier value>, "std_dev" : <std_dev of value>,
               "df_name" : <name of dataframe column belongs to>}
    """
    def feasible(self, cell_id, env):
        if super().feasible(cell_id, env):

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
        scores = np.absolute(zscore(df[OUTLIER_COL]))
        index = np.argmax(scores)

        resp["col_name"] = OUTLIER_COL
        resp["value"] = float(df[OUTLIER_COL].iloc[index])
        resp["std_dev"] = float(scores[index])
        resp["df_name"] = df_name
        self.data[cell_id] = [resp]

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
    def feasible(self, cell_id, env):

        cell_code = self.db.get_code(env._kernel_id, cell_id)
        if not cell_code: return False

        poss_models = env.get_models(cell_code)
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

        if len(subgroups) == 0: # fall back to this option if no sensitive cols

            env._nbapp.log.debug("[NOTIFICATIONS] PerfNote.make_response, cannot find sensitive columns falling back to categorical vars")

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
