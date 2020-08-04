"""
we need a global session manager which handles
routing of code analyses and handles failures
"""
import sys

from random import choice

from .storage import DbHandler
from .analysis import AnalysisEnvironment
from .config import MODE

class AnalysisManager:
    """
    AnalysisManager routes code execution requests to the proper analysis 
    environment. It spawns new environments as appropriate. It is also responsible
    for resurrecting past sessions and error handling
    """

    def __init__(self, nbapp):

        self.db = DbHandler()
        self.analyses = {}
        self._nb = nbapp
    
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
        request["exec_ct"] = env.exec_count + 1
        self.db.add_entry(request) 

        try:
            env.cell_exec(code, kernel_id, cell_id)
        except RuntimeError as e:
            self._nb.log.error("[MANAGER] Analysis environment encountered exception {0}, call back {1}".format(e, sys.exc_info()[0]))

        response = self.make_response(kernel_id, cell_id, mode=MODE)
        self._nb.log.info("[MANAGER] sending response {0}".format(response))
        return response

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
                resp["info"] = self.run_colsim(kernel_id, cell_id)
        resp["info"]["cell"] = cell_id
        return resp

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

