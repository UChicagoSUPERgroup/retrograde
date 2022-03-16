"""
we need a global session manager which handles
routing of code analyses and handles failures
"""
import sys, os, re
import json

import mysql.connector
import dill

from random import choice, randrange

from .storage import DbHandler, RemoteDbHandler, load_dfs
from .analysis import AnalysisEnvironment
from .config import MODE, remote_config
from .note_config import NOTE_RULES, SHOW


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
        self.show = SHOW
 
    def handle_request(self, request):
        """
        handle a request (json object with "content", "id", and "kernel" fields)
        """
        self._nb.log.debug("[MANAGER] received {0}".format(request))

        req_type = ""
        kernel_id = ""

        if "type" in request:
            req_type = request["type"]
        if "kernel" in request:
            kernel_id = request["kernel"]

        if req_type != "execute":
            if req_type == "sensitivityModification":
                self._nb.log.info("[MANAGER] handling updated sensitivity modification request {0}".format(request))
                col_info = {"is_sensitive" : request["sensitivity"] != "none",
                            "user_specified" : True,
                            "fields" : request["sensitivity"]}
                update_data = {request["df"] : {request["col"] : col_info}}
                
                self.db.update_marked_columns(kernel_id, update_data) # Q?: what is the name of the key holding the input data dict? (not in luca's design google doc)
                return "Updated"
            elif req_type == "columnInformation":
                self._nb.log.info("[MANAGAER] handling request for column information {0}".format(request))
                result = self.handle_col_info(kernel_id, request)
                self._nb.log.debug("[MANAGER] returning result {0}".format(result))
                return result
            self._nb.log.info("[MANAGER] received non-execution request {0}".format(request))
            return

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

        ns = self.db.recent_ns()
        dfs = load_dfs(ns)

        non_dfs = dill.loads(ns["namespace"])

        for r in self.notes["all"]:
            if r.feasible(cell_id, env, dfs, non_dfs):
                r.make_response(env, kernel_id, cell_id)
            r.update(env, kernel_id, cell_id, dfs, non_dfs)
        for r in self.notes[cell_mode]:
            if r.feasible(cell_id, env, dfs, non_dfs):
                r.make_response(env, kernel_id, cell_id) 
            r.update(env, kernel_id, cell_id, dfs, non_dfs)
        if cell_mode in self.show:
            response = self.send_notifications(kernel_id, cell_id, request["exec_ct"])
            return response
#        self._nb.log.info("[MANAGER] sending response {0}".format(response))

        return
    def handle_col_info(self, kernel_id, request):
        """Routes a request of type 'columnInformation' to DbHandler.provide_col_info()"""
        result = self.db.provide_col_info(kernel_id, request)
        if "error" in result:
            self._nb.log.warning("[MANAGER] Unable to provide columnInformation.\nRequest: {0}\nError: {1}".format(request, result))

        formatted_result = {"col_name" : result["col_name"],
                            "sensitivity" : result["sensitivity"]}
        
        formatted_result["valueCounts"] = {}
        
        for value, count in result["valueCounts"].to_dict().items():          
            formatted_result["valueCounts"][str(value)] = str(count)

        return formatted_result

    def send_notifications(self, kernel_id, cell_id, exec_ct):

        resp = {}
        resp["kernel_id"] = kernel_id

        """
        main note response format
        {"kernel_id" : kernel_id, 
         <note_type> : [notes]}
        """
        note_list = [note for note_list in self.notes.values() for note in note_list]

        for note in note_list:
            for note_data in note.data.values():
                self._nb.log.debug("[send_notifications] note data {0}".format(note_data))
                for note_entry in note_data:
                    
                    if note_entry["type"] not in resp:
                        resp[note_entry["type"]] = []
                    resp[note_entry["type"]].append(note_entry)
                    self.db.store_response(kernel_id, cell_id, exec_ct, note_entry)

        return resp 

