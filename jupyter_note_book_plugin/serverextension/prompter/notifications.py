import pandas as pd
import numpy as np
import dill
import re

from scipy.stats import zscore
from random import choice

from .storage import load_dfs
from .sortilege import is_categorical

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

class OnetimeNote(EnabledNote):
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

        self.db.store_response(kernel_id, cell_id, resp) 

class PerformanceNote(EnabledNote):

    def feasible(self, cell_id, env):

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
            has_labels = labels_df in dfs.keys()

            if has_features:
                df = dfs[features_df]
                has_feature_cols = all([f in df.columns for f in features_cols])
            else:
                has_feature_cols = False 
            if has_labels:
                df = dfs[labels_df]
                has_label_cols = all([f in df.columns for f in label_cols])
            else:
                has_label_cols = False
            env._nbapp.log.debug(
                "[PERFORMANCENOTE] model {0} has_model {1}, has_features {2}, has_labels {3}".format(model_name, has_model, has_features, has_labels))

            if (has_model and has_features and has_labels and has_feature_cols and has_label_cols):
                models.append((model_name, ns[model_name], dfs[features_df], 
                               dfs[labels_df], features_cols, label_cols))

        self.models = models

        if models: return True
        return False 

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

        model_name, model, features, labels, features_list, labels_list = choice(self.models) # lets mix it up a little

        resp = {"type" : "model_perf"}
        resp["model_name"] = model_name

        if features_list:
            if len(features_list) == 1:
                features_df = features[features_list[0]]
            else:
                features_df = features[features_list]
        else:
            features_df = features

        env._nbapp.log.debug("[PERFORMANCENOTE] features_list {0}".format(features_list))
        env._nbapp.log.debug("[PERFORMENCENOTE] Input columns {0}".format(features_df.columns))

        if labels_list:
            if len(labels_list) == 1:
                labels_df = labels[labels_list[0]]
            else:
                labels_df = labels[labels_list]
        else:
            labels_df = labels
       
        subgroups = []
         
        if "race" in features.columns: 
            subgroups.append("race")
        if "sex" in features.columns:
            subgroups.append("sex")

        if len(subgroups) == 0: # fall back to this option
            env._nbapp.log.debug("[NOTIFICATIONS] PerfNote.make_response, cannot find sensitive columns falling back to categorical vars")
            subgroups = [c for c in column if is_categorical(features[c])]

        env._nbapp.log.debug("[NOTIFICATIONS] Perfnote.make_response analyzing columns {0}".format(subgroups))

        preds = model.predict(features_df)
      
        pos = model.classes_[0]
        neg = model.classes_[1]

        resp["values"] = {"pos" : str(pos), "neg" : str(neg)}
        resp["columns"] = {}
 
        for col_name in subgroups:

            resp["columns"][col_name] = {} 

            for val in features[col_name].unique():

                mask = (features[col_name] == val)

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
