"""
Handle received text from front end application
"""

import json
import tornado

from notebook.notebookapp import NotebookApp
from notebook.base.handlers import APIHandler
from notebook.utils import url_path_join
from notebook.services.kernels.handlers import default_handlers

from tornado.routing import Rule, PathMatches

from prompter.storage import DbHandler, RemoteDbHandler
from prompter.analysis import AnalysisEnvironment, run_code, ModelVisitor
from prompter.manager import AnalysisManager
from prompter.forkingkernel import ForkingKernel
from prompter.config import table_query # necessary for testing

#from prompter.handler import TSChannelHandler

# all the examples I've seen require _jupyter_server_extension_paths
# and load_jupyter_server_extension
#
# IDK what either of them do

class CodeExecHandler(APIHandler):
    """handles transactions from notebook js app and server backend"""
    
    def post(self):
#        print(tornado.escape.json_decode(self.request.body))
        resp_body = MANAGER.handle_request(tornado.escape.json_decode(self.request.body))
        self.set_status(200)
        self.set_default_headers()
        self.finish(resp_body)

def _jupyter_server_extension_paths():
    return [{"module" : "prompter"}]

def load_jupyter_server_extension(app):
#    print("LOADING SERVER EXTENSIONS") 
    global MANAGER
    MANAGER = AnalysisManager(app)
    handlers = [("/code_tracker/exec", CodeExecHandler)]
    base_url = app.web_app.settings["base_url"]
    handlers = [(url_path_join(base_url, x[0]), x[1]) for x in handlers]
    app.web_app.add_handlers(".*", handlers)
    # override kernel handler
    
#    print(app.web_app.wildcard_router.rules)
#    replace_handler(default_handlers[-1][0], TSChannelHandler, app.web_app)

def replace_handler(repl_pattern, new_handler, app):
    """replace the hander with repl_patter with new handler"""
    new_rule = Rule(repl_pattern, new_handler)
    repl_matches = PathMatches(repl_pattern)

    app_rules = app.wildcard_router.rules

    for rule in app_rules:
        if comp_matchers(rule.matcher, repl_matches):
            rule.target = new_handler
            return
    raise Exception("Could not replace the handler")

def comp_matchers(m1, m2):
    if type(m1) != type(m2):
        return False
    if isinstance(m1, PathMatches):
        return m1.regex == m2.regex
    return m1 == m2
