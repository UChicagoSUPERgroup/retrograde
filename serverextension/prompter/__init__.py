"""
Handle received text from front end application
"""

import json
import tornado

from notebook.notebookapp import NotebookApp
from notebook.base.handlers import APIHandler
from notebook.utils import url_path_join

from prompter.storage import DbHandler

# all the examples I've seen require _jupyter_server_extension_paths
# and load_jupyter_server_extension
#
# IDK what either of them do

class CodeExecHandler(APIHandler):
    """handles transactions from notebook js app and server backend"""

    def get(self):
        self.finish("hello")

    def post(self):
        print(tornado.escape.json_decode(self.request.body))
        self.finish("done")

def _jupyter_server_extension_paths():
    return [{"module" : "prompter"}]

def load_jupyter_server_extension(app):

    handlers = [("/code_tracker/exec", CodeExecHandler)]
    base_url = app.web_app.settings["base_url"]
    handlers = [(url_path_join(base_url, x[0]), x[1]) for x in handlers]

    app.web_app.add_handlers(".*", handlers)
