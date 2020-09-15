"""
we need a global session manager which handles
routing of code analyses and handles failures
"""
import sys, os

import mysql.connector

from random import choice

from .storage import DbHandler, RemoteDbHandler
from .analysis import AnalysisEnvironment
from .config import MODE, remote_config
from .notifications import SensitiveColumnNote, ZipVarianceNote, OutliersNote, PerformanceNote

class AnalysisManager:
    """
    AnalysisManager routes code execution requests to the proper analysis 
    environment. It spawns new environments as appropriate. It is also responsible
    for resurrecting past sessions and error handling
    """

    def __init__(self, nbapp):
        
        try:

            remote_config["nb_user"] = os.getenv("JP_PLUGIN_USER")
            if not remote_config["nb_user"]: remote_config["nb_user"] = "DEFAULT_USER"

            self.db = RemoteDbHandler(**remote_config)

        except mysql.connector.Error as e:
            nbapp.log.warning("[MANAGER] Unable to connect to remote db, creating local backup. Error {0}".format(e))
            self.db = DbHandler()
        self.analyses = {}
        self._nb = nbapp
        self.rules = {} # rules used to trigger notifications
    
        if MODE == "EXP_CTS" or MODE == "EXP_END":
            self.rules = {
                "column" : SensitiveColumnNote(self.db),
                "variance" : ZipVarianceNote(self.db),
                "outliers" : OutliersNote(self.db),
                "performance" : PerformanceNote(self.db)
            }

    def handle_request(self, request):
        """
        handle a request (json object with "content", "id", and "kernel" fields)
        """
        self._nb.log.debug("[MANAGER] received {0}".format(request))

        if request["type"] != "execute":
            print(request)
            return
        kernel_id = request["kernel"]
        cell_id = request["cell_id"]
        code = request["contents"]

        self._nb.log.info("[MANAGER] Analyzing cell {0} with kernel {1}".format(cell_id, kernel_id))

        if kernel_id not in self.analyses:

            self._nb.log.info("[MANAGER] Starting new analysis environment for kernel {0}".format(kernel_id))
            self.analyses[kernel_id] = AnalysisEnvironment(self._nb, kernel_id, self.db)
        
        env = self.analyses[kernel_id]
        self.db.add_entry(request) 

        try:
            env.cell_exec(code, kernel_id, cell_id, request["exec_ct"])
        except RuntimeError as e:
            self._nb.log.error("[MANAGER] Analysis environment encountered exception {0}, call back {1}".format(e, sys.exc_info()[0]))

        self.new_data(kernel_id) # add columns and data to db
        response = self.make_response(kernel_id, cell_id, mode=MODE)
        self._nb.log.info("[MANAGER] sending response {0}".format(response))
        return response

    def check_submit(self, kernel_id, cell_id):
        code = self.db.get_code(kernel_id, cell_id)
        return "%prompter_plugin submit%" in code

    def make_response(self, kernel_id, cell_id, mode=None):
        """
        form the body of the response to send back to plugin, in the form of a dictionary
        """
        resp = {}

        if mode == "SORT":
            resp["info"] = self.run_sortilege(kernel_id, cell_id)
        if mode == "SIM":
            ans = self.run_colsim(kernel_id, cell_id)
            if ans:
                resp["info"] = ans
        if mode == "EXP_CTS":
            ans = self.run_rules(kernel_id, cell_id)

            if cell_id in ans:
                resp["info"] = {cell_id : ans[cell_id]}
            else:
                resp["info"] = {}
            resp["type"] = "multiple"

        if mode == "EXP_END":

            ans = self.run_rules(kernel_id, cell_id)

            if self.check_submit(kernel_id, cell_id):

                self._nb.log.info("[MANAGER] model submission")                
                resp["info"] = ans
                resp["type"] = "multiple"

        if "info" not in resp:
            resp["info"] = {}

        resp["info"]["cell"] = cell_id
        return resp

    def run_rules(self, kernel_id, cell_id):

        self._nb.log.debug("[MANAGER] running rules for cell {0}, kernel {1}".format(cell_id, kernel_id)) 
        env = self.analyses[kernel_id]
 
        feasible_rules = [r for r in self.rules.values() if r.feasible(cell_id, env)]
        self._nb.log.debug("[MANAGER] There are {0} feasible rules".format(len(feasible_rules)))
        
        if feasible_rules:

            chosen_rule = choice(feasible_rules)
            chosen_rule.make_response(self.analyses[kernel_id], kernel_id, cell_id)
            self._nb.log.debug("[MANAGER] chose rule {0}".format(chosen_rule))

        responses = self.db.get_responses(kernel_id)

        return responses 

    def run_sortilege(self, kernel_id, cell_id):
        """run the sortilege analsysis and drop in a pattern"""
        env = self.analyses[kernel_id]
        options = env.sortilege(kernel_id, cell_id) # run the analyses on closest df
                                         # options is list of individual responses
        self._nb.log.debug("[MANAGER] there are %s options to choose from" % len(options))

        if len(options) == 0: return None

        return choice(options)

    def run_colsim(self, kernel_id, cell_id):
        """see if any of the columns resemble sensitive categories"""
        env = self.analyses[kernel_id]

        options, weights = env.colsim(cell_id)
        index = weights.index(max(weights))

        if weights[index] > 0.5: # Do we need a better notification decision mechanism?

            resp = {"type" : "resemble"}
            resp["column"] = options[index][0]
            resp["category"] = options[index][1]
            return resp
        return None           
    def new_data(self, kernel_id): 
        """ check if data in the env is new, and if so, register and send event"""
        env = self.analyses[kernel_id]
        new_data_response = {} 
        for name, info in env.entry_points.items():
            data_entry = self.db.find_data(info)
            if not data_entry:
                new_data_response[name] = info
                self.db.add_data(info, 1)
        return new_data_response

    def new_models(self, kernel_id, cell_id):
        """check if model is new, and if so register and send event"""
        env = self.analyses[kernel_id]
        new_model_response = {}

        for name, info in env.models.items():
            model_entry = self.db.find_model(name, info, kernel_id)
            if not model_entry:
                new_model_response[name] = info
                self.db.add_model(name, info, kernel_id)

        return new_model_response

    def changed_data(self, kernel_id, cell_id):
        """is data changed? if so notify of differences"""
        env = self.analyses[kernel_id]
        changed_data = {}
    
        for name, info in env.models.items():
            data_entry = self.db.find_data(name, info, kernel_id)
            if data_entry and data_entry != {name : info}:
                changed_data[name] = {data_entry.values()[0] : info, "new" : info}
                self.db.add_data(name, info, kernel_id)
        return changed_data 
    def changed_models(self, kernel_id, cell_id):
        """is model changed? if so notify of differences"""
        pass # TODO                
    def restore_session(self, kernel_id, cell_id):
        # TODO
        pass

