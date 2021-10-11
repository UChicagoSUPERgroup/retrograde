"""
we need a global session manager which handles
routing of code analyses and handles failures
"""
import sys, os, re
import json

import mysql.connector
import dill

from random import choice

from .storage import DbHandler, RemoteDbHandler, load_dfs
from .analysis import AnalysisEnvironment
from .config import MODE, remote_config
from .note_config import NOTE_RULES

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

        # mapping of notebook section -> notes to look for
        self.notes = {s : [note_type(self.db) for note_type in allowed_notes] for s, allowed_notes in NOTE_RULES.items()}

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
        metadata = json.loads(request["metadata"])
        cell_mode = metadata.get("section")

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

    #    self.update_notifications(kernel_id, cell_id)
    #    self.new_notifications(kernel_id, cell_id, cell_mode)
        ns = self.db.recent_ns()
        dfs = load_dfs(ns)

        non_dfs = dill.loads(ns["namespace"])

        for r in self.notes[cell_mode]:
            if r.feasible(cell_id, env, dfs, non_dfs):
                r.make_response(env, kernel_id, cell_id) 
            r.update(env, kernel_id, cell_id, dfs, non_dfs)
        response = self.send_notifications(kernel_id, cell_id, request["exec_ct"])
 
        self._nb.log.info("[MANAGER] sending response {0}".format(response))

        return response

    def send_notifications(self, kernel_id, cell_id, exec_ct):

        resp = {}
        resp["info"] = {}
        resp["info"]["cell"] = cell_id
        resp["info"][cell_id] = {}
        resp["kernel_id"] = kernel_id

        for notes in self.notes.values():
            for note in notes:
                for cell in note.data:
                    if cell not in resp["info"]:
                        resp["info"][cell] = {}
                    for note_data in note.data[cell]:
                        if note_data["type"] not in resp["info"][cell]:
                            resp["info"][cell][note_data["type"]] = []
                        resp["info"][cell][note_data["type"]].append(note_data)
                    for response in note.data[cell]:
                        self.db.store_response(kernel_id, cell_id, exec_ct, response)
        resp["type"] = "multiple"

        return resp 

    def update_notifications(self, kernel_id, cell_id):
        """
        are there notes associated with this cell that need to be updated?
        """
        for notes in self.notes.values():
            for note in notes:
                if note.on_cell(cell_id):
                    note.update(self.analyses[kernel_id], kernel_id, cell_id)

    def new_notifications(self, kernel_id, cell_id, cell_mode):
        """
        check if it is feasible to add any new note, and if so select
        and generate data for that note
        """ 
        self._nb.log.debug("[MANAGER] running rules for cell {0}, kernel {1}".format(cell_id, kernel_id)) 
        env = self.analyses[kernel_id]

        if cell_mode not in self.notes:
            self._nb.log.warning("[MANAGER] Cell mode {0} not in configured rules {1}".format(cell_mode, self.notes.keys()))
            return

        feasible_rules = [r for r in self.notes[cell_mode] if r.feasible(cell_id, env)]
        self._nb.log.debug("[MANAGER] There are {0} feasible rules".format(len(feasible_rules)))
        
        if feasible_rules and MODE == "EXP_CTS":
            
            chosen_rule = choice(feasible_rules)
            chosen_rule.make_response(self.analyses[kernel_id], kernel_id, cell_id)
            self._nb.log.debug("[MANAGER] chose rule {0}".format(chosen_rule))

        elif feasible_rules and MODE == "EXP_END":
            for rule in feasible_rules:
                self._nb.log.debug("[MANAGER] running rule {0}".format(rule))
                rule.make_response(self.analyses[kernel_id], kernel_id, cell_id)
