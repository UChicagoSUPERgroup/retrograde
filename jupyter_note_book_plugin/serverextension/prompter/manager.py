"""
we need a global session manager which handles
routing of code analyses and handles failures
"""
import sys, os, re

import mysql.connector

from random import choice

from .storage import DbHandler, RemoteDbHandler
from .analysis import AnalysisEnvironment
from .config import MODE, remote_config, NOTE_RULES
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
            nbapp.log.debug("[MANAGER] user is {0}".format(remote_config["nb_user"]))
            self.db = RemoteDbHandler(**remote_config)
            nbapp.log.debug("[MANAGER] db local cursor: {0}".format(self.db._local_cursor))

        except mysql.connector.Error as e:
            nbapp.log.warning("[MANAGER] Unable to connect to remote db, creating local backup. Error {0}".format(e))
            self.db = DbHandler()
        self.analyses = {}
        self._nb = nbapp
        self.rules = {s : [note(self.db) for note in notes] for s, notes in NOTE_RULES.items()} # rules used to trigger notifications
    
    def handle_request(self, request):
        """
        handle a request (json object with "content", "id", and "kernel" fields)
        """
        self._nb.log.debug("[MANAGER] received {0}".format(request))

        if request["type"] != "execute":
            self._nb.log.info("[MANAGER] received non-execution request {0}".format(request))
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

        self.update_notifications(kernel_id, cell_id)
        self.new_notifications(kernel_id, cell_id, cell_mode)
        response = self.send_notifications(kernel_id, cell_id)
 
#        response = self.make_response(kernel_id, cell_id, mode=MODE)
        self._nb.log.info("[MANAGER] sending response {0}".format(response))

        return response
    def send_notifications(kernel_id, cell_id):

        resp = {}
        resp["info"] = {}
        resp["info"]["cell"] = cell_id

        for notes in self.rules.items():
            for note in notes:
                if note.on_cell(cell_id):
                    resp["info"][cell_id] = note.get_response(cell_id)
        return resp 
    def update_notifications(self, kernel_id, cell_id):

        # TODO, should go through any active notifications associated with
        # this cell and then then check if the information is still good

        pass
    def new_notifications(kernel_id, cell_id, cell_mode):
        # Start here tomorrow, you were moving things out of make_response
        # and run_rules to parcel things out. 
        # what should the mechanism for enforcing cell_mode restrictions be?        
        self._nb.log.debug("[MANAGER] running rules for cell {0}, kernel {1}".format(cell_id, kernel_id)) 
        env = self.analyses[kernel_id]

        if cell_mode not in self.rules:
            self._nb.log.warning("[MANAGER] Cell mode {0} not in configured rules {1}".format(cell_mode, self.rules.keys()))
            return

        feasible_rules = [r for r in self.rules[cell_mode] if r.feasible(cell_id, env)]
        self._nb.log.debug("[MANAGER] There are {0} feasible rules".format(len(feasible_rules)))
        
        if feasible_rules:

            chosen_rule = choice(feasible_rules)
            chosen_rule.make_response(self.analyses[kernel_id], kernel_id, cell_id)
            self._nb.log.debug("[MANAGER] chose rule {0}".format(chosen_rule))

    def make_response(self, kernel_id, cell_id, mode=None):
        """
        form the body of the response to send back to plugin, in the form of a dictionary
        """
        resp = {}

        if mode == "EXP_CTS":
            ans = self.run_rules(kernel_id, cell_id)

            if cell_id in ans:
                resp["info"] = {cell_id : ans[cell_id]}
            else:
                resp["info"] = {}
            resp["type"] = "multiple"

        if mode == "EXP_END":

            ans = self.run_rules(kernel_id, cell_id)


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

    def new_data(self, kernel_id): 
        """ check if data in the env is new, and if so, register and send event"""
        env = self.analyses[kernel_id]
        new_data_response = {} 
        for name, info in env.entry_points.items():
            data_entry = self.db.find_data(info)
            if not data_entry:
                new_data_response[name] = info
                env._nbapp.log.debug("[MANAGER] Adding new data {0}".format(info))
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

