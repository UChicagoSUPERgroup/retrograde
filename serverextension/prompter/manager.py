"""
we need a global session manager which handles
routing of code analyses and handles failures
"""
import sys

from prompter.storage import DbHandler
from prompter.analysis import AnalysisEnvironment

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

        self.db.add_entry(request)  

        self._nb.log.info("[MANAGER] Analyzing cell {0} with kernel {1}".format(cell_id, kernel_id))

        if kernel_id not in self.analyses:

            self._nb.log.info("[MANAGER] Starting new analysis environment for kernel {0}".format(kernel_id))
            self.analyses[kernel_id] = AnalysisEnvironment(self._nb, kernel_id)
        
        env = self.analyses[kernel_id]

        try:
            env.cell_exec(code, kernel_id, cell_id)
        except RuntimeError as e:
            self._nb.log.error("[MANAGER] Analysis environment encountered exception {0}, call back {1}".format(e, sys.exc_info()[0]))

        response = self.make_response(kernel_id, cell_id)

        return response

    def make_response(self, kernel_id, cell_id):
        """
        form the body of the response to send back to plugin, in the form of a dictionary
        """

        resp = {"new" : {}, "changes" : {}}

        resp["new"] = self.new_data(kernel_id)
#        resp["new"].extend(self.new_models(kernel_id, cell_id))

#        resp["changes"] = self.changed_data(kernel_id, cell_id)
#        resp["changes"].extend(self.changed_models(kernel_id, cell_id)) 

        # TODO: probably makes more sense to do new/changed in one pass to 
        #       minimize number of db lookups (don't want to prematurely minimize,
        #       though)

        return resp

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

