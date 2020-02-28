"""
we need a global session manager which handles
routing of code analyses and handles failures
"""

from prompter.storage import DbHandler
from prompter.analysis import AnalysisEnvironment

class AnalysisManager:
    """
    AnalysisManager routes code execution requests to the proper analysis 
    environment. It spawns new environments as appropriate. It is also responsible
    for resurrecting past sessions and error handling
    """

    def __init__(self, nbapp):

        #self.db = DbHandler()
        self.analyses = {}
        self._nb = nbapp

    def handle_request(self, request):
        """
        handle a request (json object with "content", "id", and "kernel" fields)
        """
        kernel_id = request["kernel"]
        cell_id = request["cell_id"]
        code = request["contents"]

        self._nb.log.info("Analyzing cell {0} with kernel {1}".format(cell_id, kernel_id))

        if kernel_id not in self.analyses:

            self._nb.log.info("Starting new analysis environment for kernel {0}".format(kernel_id))
            self.analyses[kernel_id] = AnalysisEnvironment(self._nb, kernel_id)
        
        env = self.analyses[kernel_id]

        try:
            env.cell_exec(code, kernel_id)
        except Exception as e:
            self._nb.log.error("Analysis environment encountered exception {0}".format(str(e)))

        response = self.make_response(kernel_id, cell_id)

        return response

    def make_response(self, kernel_id, cell_id):
        """
        form the body of the response to send back to plugin, in the form of a dictionary
        """

        # TODO: for now, just send back model and data info every time
        env = self.analyses[kernel_id]
        response = {"data" : env.entry_points, "models" : env.models}

        return response
        
    def restore_session(self, kernel_id, cell_id):
        # TODO
        pass

