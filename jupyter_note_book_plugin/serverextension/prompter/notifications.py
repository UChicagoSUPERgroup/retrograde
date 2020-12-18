import pandas as pd
import numpy as np
import dill
import re

from scipy.stats import zscore
from random import choice

from .storage import load_dfs
from .sortilege import is_categorical

LAST_SENT = None
WAIT_TIME = 8 # How many turns should notes wait before becoming active again?

class Notifications:

    def __init__(self, db):
        self.db = db

    def feasible(self, cell_id, env):
        """is it feasible to send this notification?"""
        # nb. bake in timing + whether prerequisites exist here
        return False
   
    def times_sent(self):
        """the number of times this notification has been sent"""
        return 0 

    def make_response(self, env, kernel_id, cell_id):
        """form the response to send to the frontend""" 
        raise NotImplementedError

class EnabledNote(Notifications):

    def __init__(self, db):
        super().__init__(db)
        self.start_message_recvd = False

    def feasible(self, cell_id, env):

        env._nbapp.log.debug("[ENABLEDNOTE] checking whether enabled")
        if self.start_message_recvd:
            env._nbapp.log.debug("[ENABLEDNOTE] yes")
            return True 

        cell_code = self.db.get_code(env._kernel_id, cell_id)
        invocation_matcher = re.compile(r"#\W*%(\w+)\W+(\w+)")
        for line in cell_code.splitlines():
            mtch = invocation_matcher.search(line)
            if mtch and mtch.group(1) == "prompter_plugin"\
                    and mtch.group(2) == "model_training":
                self.start_message_recvd = True
                env._nbapp.log.debug("[ENABLEDNOTE] model training started")
        return self.start_message_recvd

class SpacedNote(EnabledNote):

    def __init__(self, db):
        super().__init__(db)
    
    def feasible(self, cell_id, env):
        # TODO: want to have a counter shared among instances of subclasses
        # that gets incremented every time one is sent.
        if not super().feasible(cell_id, env):
            return False
 
        global LAST_SENT
        if not LAST_SENT or LAST_SENT > WAIT_TIME:
            return True 
        LAST_SENT += 1 # this is a hack, based on number of notes
        return False 

    def make_response(self, env, kernel_id, cell_id):
        LAST_SENT = 0
class OnetimeNote(SpacedNote):
    """
    A notification that is sent exactly once
    """

    def __init__(self, db):
        super().__init__(db)
        self.sent = False

    def feasible(self, cell_id, env):
        enabled = super().feasible(cell_id, env)
        env._nbapp.log.debug("[ONETIMENOTE] sent: {0}".format(self.sent))
        env._nbapp.log.debug("[ONETIMENOTE] enabled: {0}".format(enabled))
        return ((not self.sent) and enabled)
    
    def times_sent(self):
        return int(self.sent)

    def make_response(self, env, kernel_id, cell_id):
        super().make_response(env, kernel_id, cell_id)
        self.sent = True

class SensitiveColumnNote(OnetimeNote):

    """
    a class that indicates whether a sensitive column is present in
    an active dataframe
    """

    def feasible(self, cell_id, env):
        if super().feasible(cell_id, env):
            columns = self.db.get_columns("race") # hardcoded for experiment
            if columns: 
                self.df_name = columns[0]["name"]
                return True
            return False
        return False

    def make_response(self, env, kernel_id, cell_id):

        super().make_response(env, kernel_id, cell_id)

        resp = {"type" : "resemble"}
        resp["col"] = "race"
        resp["category"] = "race"
        if hasattr(self, "df_name"):
            resp["df"] = self.df_name
        else:
            resp["df"] = "unnamed"
        self.db.store_response(kernel_id, cell_id, resp)

class ZipVarianceNote(OnetimeNote):

    def feasible(self, cell_id, env):
        if super().feasible(cell_id, env):
            env._nbapp.log.debug("[ZipVar] checking columns")
            race_columns = self.db.get_columns("race") # hardcoded for experiment
            zip_columns = self.db.get_columns("zip")
            env._nbapp.log.debug("[ZipVar] columns are {0}, {1}".format(race_columns, zip_columns))
            if race_columns and zip_columns: 
                return True
            return False
        return False

    def make_response(self, env, kernel_id, cell_id):

        super().make_response(env, kernel_id, cell_id)

        # TODO: what does the response need to be?

        resp = {"type" : "variance"}

        race_columns = self.db.get_columns("race")
        zip_columns = self.db.get_columns("zip")
        
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

        if "race" not in df.columns or "zip" not in df.columns:
            env._nbapp.log.warning("[NOTIFICATIONS] ZipVarianceNote.make_response: race or zip not in dataframe columns")
            return
        panel_df = pd.get_dummies(df["race"])
        panel_df["zip"] = df["zip"]

        rate_df = panel_df.groupby(["zip"]).mean() 

        resp["zip1"] = 60637 # use this to highlight redlining
        resp["zip2"] = 60611 

        resp["demo"] = {60637 : int(rate_df["black"][60637]*100), 60611 : int(rate_df["white"][60611]*100)}

        self.db.store_response(kernel_id, cell_id, resp)

class OutliersNote(OnetimeNote):

    def feasible(self, cell_id, env):
        if super().feasible(cell_id, env):

            columns = self.db.get_columns("principal") # hardcoded for experiment
            if columns: 
                return True
            return False

    def make_response(self, env, kernel_id, cell_id):
    
        super().make_response(env, kernel_id, cell_id)

        resp = {"type" : "outliers"}
        cols = self.db.get_columns("principal")
      
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
        scores = np.absolute(zscore(df["principal"]))
        index = np.argmax(scores)

        resp["col_name"] = "principal"
        resp["value"] = float(df["principal"].iloc[index])
        resp["std_dev"] = float(scores[index])
        resp["df_name"] = df_name

        self.db.store_response(kernel_id, cell_id, resp) 

class PerformanceNote(SpacedNote):

    def feasible(self, cell_id, env):

        if not super().feasible(cell_id, env):
            return False

        cell_code = self.db.get_code(env._kernel_id, cell_id)
        if not cell_code: return False

        poss_models = env.get_models(cell_code)
        ns = self.db.recent_ns()
        dfs = load_dfs(ns)

        ns = dill.loads(ns["namespace"])

        models = []
        env._nbapp.log.debug("[PERFORMANCENOTE] there are {0} possible models".format(len(poss_models)))
 
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
#            env._nbapp.log.debug(
#                "[PERFORMANCENOTE] model {0} has_model {1}, has_features {2}, has_labels {3}".format(model_name, has_model, has_features, has_labels))

            if (has_model and has_features and has_labels and (subset_features is not None) and (subset_labels is not None)):
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

    def new_model_name(self, kernel_id, cell_id, model_name):
        """are we updating an old model perf or creating a new one?"""
        responses = self.db.get_responses(kernel_id)

        if cell_id not in responses: return None

        for resp in responses[cell_id]: 
            if resp["type"] == "model_perf" and resp["model_name"] == model_name:
                return resp
        return None

    def make_response(self, env, kernel_id, cell_id):

        super().make_response(env, kernel_id, cell_id)

        model_name, model, features_df, labels_df, full_feature, full_label = choice(self.models) # lets mix it up a little

        resp = {"type" : "model_perf"}
        resp["model_name"] = model_name

        env._nbapp.log.debug("[PERFORMENCENOTE] Input columns {0}".format(features_df.columns))

        subgroups = []
                 
        r_col = self.try_align(features_df, full_feature, "race")
        if r_col is not None: subgroups.append(r_col)

        s_col = self.try_align(features_df, full_feature, "sex")
        if s_col is not None: subgroups.append(s_col)

        if len(subgroups) == 0: # fall back to this option

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

        old_resp = self.new_model_name(kernel_id, cell_id, model_name) 

        if not old_resp: 
            self.db.store_response(kernel_id, cell_id, resp) 
        else:
            self.db.update_response(kernel_id, cell_id, old_resp, resp) 
