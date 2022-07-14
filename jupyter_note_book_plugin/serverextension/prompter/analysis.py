"""
analysis.py creates a running environment for dynamically tracking
data relationships between variables
"""
from queue import Empty
from ast import parse, Name, Attribute, Str
from sklearn.base import ClassifierMixin
from pandas import DataFrame

import dill

from timeit import default_timer as timer

from .storage import load_dfs
from .visitors import DataFrameVisitor, ModelScoreVisitor, ModelFitVisitor

class AnalysisEnvironment:
    """
    Analysis environment tracks relevant variables in execution

    """
    def __init__(self, nbapp, kernel_id, db):
        """
        nbapp: the notebook application object, needed for access to logging and (maybe) kernel stuff? TODO: check to see whether we just need this for logging
        
        kernel_id: the kernel this analysis environment is for
        db: the DbHandler object for reading to/from past code executions and significant entities
        """
        self.db = db
        self.pandas_alias = Aliases("pandas") # handle imports and functions
        self.entry_points = {} # new data introduced into notebook
        self._kernel_id = kernel_id
        
        self._nbapp = nbapp
        self.models = {}
        self.models_f = {}

        self.ptr_set = {}
        self.log = self._nbapp.log

        self.ancestors = {} # map of (df_name, version) -> {(input_df_name, version), ...,}

    def cell_exec(self, code, notebook, cell_id, exec_ct):
        """
        rewrite of code execution 
        """ 
        cell_code = parse(code)

        try:
            ns = self.db.recent_ns() 
        except:
            self._nbapp.log.warning("[ANALYSIS.CELL_EXEC] Could not acquire namespace") 
            return

        ns_dfs = load_dfs(ns)
        full_ns = dill.loads(ns["namespace"])
        
        full_ns.update(ns_dfs)

        model_names = [k for k,v in full_ns.items() if isinstance(v, ClassifierMixin)]
    
        # new data check
        new_data = self._get_new_data(ns_dfs, cell_id)

        # parse relationships
        df_visitor = DataFrameVisitor(ns_dfs.keys(), new_data, self.pandas_alias)
        df_visitor.visit(cell_code) 
        self.ptr_set.update(df_visitor.assign_map)  

        model_score_visitor = ModelScoreVisitor(self.pandas_alias, model_names, full_ns, self.ptr_set) 
        model_score_visitor.visit(cell_code)

        model_fit_visitor = ModelFitVisitor(self.pandas_alias, model_names, full_ns, self.ptr_set)
        model_fit_visitor.visit(cell_code)
       
        # handle updates, update columns, model score + fit calls etc
        
        # check if new data in any way
        # of form {<df name> : {"source" : filename, "format" : format}}

        for df_name in df_visitor.info:

            self.entry_points[df_name] = {"ancestors" : df_visitor.info[df_name]}
            self.entry_points[df_name]["cell"] = cell_id
            self.entry_points[df_name]["name"] = df_name
            self.entry_points[df_name]["kernel"] = self._kernel_id

            if df_name in full_ns:
                df_obj = full_ns[df_name]
                if isinstance(df_obj, DataFrame):
                    self.entry_points[df_name]["columns"] = {}
                    for c in df_obj.columns:
                        self.entry_points[df_name]["columns"][c] = {}
                        self.entry_points[df_name]["columns"][c]["size"] = len(df_obj[c])
                        self.entry_points[df_name]["columns"][c]["type"] = str(df_obj[c].dtypes)
        # add data to db
        for entry_point in self.entry_points.values():

            self.log.debug("[AnalysisEnv] checking {0}".format(entry_point))
            pt_version = self.db.check_add_data(entry_point, exec_ct)   
            child = (entry_point["name"], pt_version)

            if child not in self.ancestors:
                self.ancestors[child] = set()

            # get the most recent version of each. ancestor
            # this could be made more efficient by looking up all ancestors
            # once and then using a lookup, but unless this ends up being a 
            # big time-sink, additional complexity probably not worth it. 
            for ancestor in entry_point["ancestors"]:
                anc_versions = self.db.find_data({"name" : ancestor, "kernel" : self._kernel_id})
                if anc_versions is None:
                    anc_max_version = 1
                else:
                    anc_max_version = max([anc["version"] for anc in anc_versions])
                self.ancestors[child].add((ancestor, anc_max_version))

        # new model score calls? 
        new_models = model_score_visitor.models
        self.log.debug(f"[AnalysisEnv] new models discovered from score are {new_models}") 
        for model_name in new_models.keys():
            if model_name in self.models:
                if ("x" in self.models[model_name] and\
                    "x" in new_models[model_name]) or\
                   ("y" in self.models[model_name] and\
                    "y" in new_models[model_name]):
                    self.models[model_name] = new_models[model_name]
                    self.models[model_name]["cell"] = cell_id
            else: 
                self.models[model_name] = new_models[model_name]
                self.models[model_name]["cell"] = cell_id
        # new model fit calls?
        fit_models = model_fit_visitor.models
        self.log.debug(f"[AnalysisEnv] new models discovered from fit are {fit_models}")
        for model_name in fit_models:
            if model_name in self.models_f:
                if ("X" in self.models_f[model_name] and "X" in fit_models[model_name]) or \
                ("y" in self.models_f[model_name] and "y" in self.models_f[model_name]):
                    self.models_f[model_name] = new_models[model_name]
                    self.models_f[model_name]["cell"] = cell_id
            else:
                self.models_f[model_name] = fit_models[model_name]
                self.models_f[model_name]["cell"] = cell_id

    def _get_new_data(self, df_ns, cell_id):
        """find the new dataframe elements""" 
        new_dfs = {}
        for df in df_ns:

            lookup_entry = {
                "cell" : cell_id,
                "name" : df,
                "kernel" : self._kernel_id,
                "columns" : {},
            }

            for col in df_ns[df].columns:
                lookup_entry["columns"][col] = {}
                lookup_entry["columns"][col]["size"] = len(df_ns[df][col])
                lookup_entry["columns"][col]["type"] = str(df_ns[df][col].dtypes)

            version = self.db.is_new_data(lookup_entry) # returns true/false whether entry is new or not

            if version is None: 
                new_dfs[df] = df_ns[df]
        return new_dfs
                
    def get_models(self):
        """are models in cell defined in this analysis?"""
        return self.models

    def get_fitted_models(self):
        """models discovered only by the user doing xxx.fit"""
        return self.models_f

class Aliases:
    """
    store, parse and handle aliases for modules, submodules and function imports
    """
    def __init__(self, module_name):

        self.name = module_name
        self.module_aliases = set() # live names in session
        self.func_mapping = {}
        self.functions = set()

    def import_module_as(self, alias_name):
        """handle node of type "import <modulename> as <alias_name>"""
        self.module_aliases.add(alias_name)

    def import_func(self, func_name, alias_name=None):
        """
        handle node representing "from <module> import func" or 
        "from <module> import func as aliasfunc"
        """
        if not alias_name:
            self.func_mapping[func_name] = func_name
            self.functions.add(func_name)
        else:
            self.func_mapping[func_name] = alias_name
            self.functions.add(alias_name)

    def import_glob(self, module):
        """
        handle statements like "from <module> import *" and "import <module>.*"
        """
        # TODO
        pass

    def _check_submod(self, modulename):
        """
        check if calling a submodule we care about
        should return true for case where pandas is in import table and
        module is just pandas

        in normal case return true for things like pandas.Dataframe
        """
        return self.name in modulename

    def add_import(self, alias_node):
        """
        take an alias node from an import stmnt ("name","asname") and
        add to space if imported module a submod of this alias space
        """
        if self._check_submod(alias_node.name):
            if alias_node.asname:
                self.module_aliases.add(alias_node.asname)
            else:
                self.module_aliases.add(alias_node.name)

    def add_importfrom(self, module_name, alias_node):
        """
        take an import from statement, and add mapping if
        module_name is a submodule of this alias space
        """
        if self._check_submod(module_name):
            if alias_node.asname:
                self.func_mapping[alias_node.name] = alias_node.asname
                self.functions.add(alias_node.asname)
            else:
                self.func_mapping[alias_node.name] = alias_node.name
                self.functions.add(alias_node.name)

    def get_alias_for(self, func_name):
        """return function func_name is alias for"""
        for mod_func, alias in self.func_mapping.items():
            if alias == func_name:
                return mod_func
        return None

def as_string(name_or_attrib):
    """print as string name or attribute"""
    if isinstance(name_or_attrib, Attribute):
        full = name_or_attrib.attr
        curr = name_or_attrib

        while isinstance(curr, Attribute):
            curr = curr.value
            if isinstance(curr, Attribute):
                full = curr.attr+"."+full
            elif isinstance(curr, Name):
                full = curr.id+"."+full
        return full
    if isinstance(name_or_attrib, Name):
        return name_or_attrib.id
    if isinstance(name_or_attrib, Str):
        return name_or_attrib.s
    return ""

def poll_client(client): # poll all channels to get client state
    output = {"io": None, "shell" : None, "stdin" : None}
    try:
        output["io"] = client.get_iopub_msg(timeout=0.25)
    except Empty:
        pass
    try:
        output["shell"] = client.get_shell_msg(timeout=0.25)
    except Empty:
        pass
    try:
        output["stdin"] = client.get_stdin_msg(timeout=0.25)
    except Empty:
        pass
    return output
        

# TODO: look and see if all failed executions are caused by execution when busy
def run_code(client, mgr, code, log, shell_timeout=1, poll_timeout=1):

    """
    run the code
    taken from https://github.com/jupyter/nbconvert/blob/f072d782ddbbf6fe77d6c5867e3ac6459d4384cd/nbconvert/preprocessors/execute.py#L524
    """
    io_msg = None
    try:
        io_msg = client.iopub_channel.get_msg(timeout=0.25)
        log.debug("[RUN_CODE] iopub msg before execute {0}".format(io_msg))
    except Empty:
        log.debug("[RUN_CODE] no iopub msg before execute")
        pass 
    request_msg_id = client.execute(code)

    log.debug("[RUN_CODE] execution request {0}".format(request_msg_id))
    log.debug("[RUN_CODE] code to run {0}".format(code))
 
    more_output = True
    polling_exec_reply = True

    shell_deadline = timer() + shell_timeout
    poll_deadline = timer() + poll_timeout

    content = ""

    while more_output or polling_exec_reply:
        if polling_exec_reply:
            if timer() >= shell_deadline:
                log.error("[RUN_CODE] timeout waiting for execute reply {0} seconds".format(shell_timeout))
                mgr.interrupt_kernel()
                polling_exec_reply = False
                continue

            timeout = min(timer() + 1, shell_deadline)
            
            try:
                shell_msg = client.shell_channel.get_msg(timeout=timeout)
                log.debug("[RUN_CODE] received shell msg {0}".format(shell_msg))
                if shell_msg["parent_header"].get("msg_id") == request_msg_id:
                    polling_exec_reply = False 
            except Empty:
                if not client.is_alive():
                    log.error("[RUN_CODE] kernel died while completing request")
                    raise DeadKernelError("kernel died")  
        if more_output: 
            try:
                timeout = poll_timeout
                if polling_exec_reply:
                    # set deadline to be under timeout
                    timeout = min(timer() + 1, poll_deadline)
                msg = client.iopub_channel.get_msg(timeout=timeout)
            except Empty:
                if polling_exec_reply:
                    continue
                else:
                    log.warning("[RUN_CODE] timeout waiting for iopub")
                    more_output = False
                    continue
            log.debug("[RUN_CODE] received iopub msg {0}".format(msg))
            if msg["parent_header"].get("msg_id") != request_msg_id:
                continue
            content+=process_msg(msg)
            if msg["msg_type"] == "status" and msg["content"]["execution_state"] == "idle":
                more_output = False
    return content

def process_msg(msg):

    msg_type = msg["header"]["msg_type"]
    content = msg["content"]

    if msg_type == "execute_result":
        return content["data"]["text/plain"]
    if "traceback" in content:
        raise KernelException(content["traceback"])
    return ""

class KernelException(RuntimeError):
    def __init__(self, traceback):
        RuntimeError.__init__(self, "Kernel encountered exception with traceback {0}".format(traceback))

class DeadKernelError(RuntimeError):
    pass
