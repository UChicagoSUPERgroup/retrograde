"""
analysis.py creates a running environment for dynamically tracking
data relationships between variables
"""
from queue import Empty
from ast import NodeVisitor, Call, Name, Attribute, Expr, Load, Str, Num
from ast import Subscript, List, Index, ExtSlice, keyword, NameConstant
from ast import parse, walk, iter_child_nodes
import astor
from timeit import default_timer as timer
from .config import other_funcs, ambig_funcs, series_funcs

#from code import InteractiveInterpreter

DATAFRAME_TYPE = "DataFrame"
SERIES_TYPE = "Series"
OTHER_TYPE = "Other"
MAYBE_TYPE = "Maybe"

class AnalysisEnvironment:
    """
    Analysis environment tracks relevant variables in execution

    TODO: should add ability to execute in parallel, in order to be able to run
          tests DS isn't thinking of
    """
    def __init__(self, nbapp, kernel_id):
        """
        nbapp = the notebook application object
        """
        self.pandas_alias = Aliases("pandas") # handle imports and functions
        self.sklearn_alias = Aliases("sklearn")

        self.entry_points = {} # new data introduced into notebook
        self.graph = Graph() # connections
        self.active_names = set()
        self._kernel_id = kernel_id

        self._read_funcs = ["read_csv", "read_fwf", "read_json", "read_html",
                            "read_clipboard", "read_excel", "read_hdf",
                            "read_feather", "read_parquet", "read_orc",
                            "read_msgpack", "read_stata", "read_sas",
                            "read_spss", "read_pickle", "read_sql",
                            "read_gbq"]
        self._nbapp = nbapp
        self.client = None
#        self._session = InteractiveInterpreter()
        self.models = {}

    def cell_exec(self, code, notebook, cell_id):
        """
        execute a cell and propagate the analysis
        """
        cell_code = parse(code)

        old_models = set(self.models.keys())
        old_data = set(self.entry_points.keys())

        # add parent data to each node
        for node in walk(cell_code):
            for child in iter_child_nodes(node):
                child.parent = node

        visitor = CellVisitor(self)
        visitor.visit(cell_code)

        new_models = set(self.models.keys())
        new_data = set(self.entry_points.keys())

        for model in (new_models - old_models):
            self.models[model]["cell"] = cell_id
        for data in (new_data - old_data):
            self.entry_points[data]["cell"] = cell_id

    def _add_entry(self, call_node, targets):
        """add an entry point"""
        source = as_string(call_node.args[0])
        if isinstance(call_node.func, Name):
            if call_node.func.id not in self._read_funcs:
                func_name = self.pandas_alias.get_alias_for(call_node.func.id)
                fmt = func_name.split("_")[-1]
            else:
                fmt = call_node.func.id.split("_")[-1]
        else:
            fmt = call_node.func.attr.split("_")[-1]
        for target in targets:
            while not isinstance(target, Name):
                target = target.value # assumes target is attribute type
            self.entry_points[target.id] = {"source" : source, "format" : fmt}

    def _wait_for_clear(self, client):
        """let's try polling the iopub channel until nothing queued up to execute"""
        while True:
            self._nbapp.log.debug("[ANALYSIS] waiting for channel to clear")
            try:
                io_msg_content = client.get_iopub_msg(timeout=1)['content']
                self._nbapp.log.debug("[ANALYSIS] io_msg {0}".format(io_msg_content))
            except Empty:
                return True

    def _execute_code(self, code, client=None, kernel_id=None, timeout=1):

        if not kernel_id: kernel_id = self._kernel_id

        start_time = timer()

        if not client: client = self.client # client initially defined as None

        if (not client) or (kernel_id != self._kernel_id):
            self._nbapp.log.debug("[ANALYSIS] creating new client for {0}".format(code))
            kernel = self._nbapp.kernel_manager.get_kernel(kernel_id)
            client = kernel.client()

            client.start_channels()
            client.wait_for_ready()

            self.client = client # want to associate kernel id with client
            self._kernel_id = kernel_id
#        self._nbapp.log.debug("[ANALYSIS] acquiring lock for {0}".format(kernel_id))
#        self._nbapp.log.debug("[ANALYSIS] {0}".format(dir(kernel)))
        self._nbapp.web_app.kernel_locks[kernel_id].acquire()

        msg_id = client.execute(code)
        self._nbapp.log.debug("[ANALYSIS] code execution on {0}".format(kernel_id))
        reply = client.get_shell_msg(msg_id)
        # using loop from https://github.com/abalter/polyglottus/blob/master/simple_kernel.py
        
#        self._nbapp.log.debug("[ANALYSIS] reply id {0} for {1}".format(reply, kernel_id))
        io_msg_content = client.get_iopub_msg(timeout=timeout)['content']

        if 'execution_state' in io_msg_content and io_msg_content['execution_state'] == 'idle':
            return "no output"

        while True:
            temp = io_msg_content
            try:
                io_msg_content = client.get_iopub_msg(timeout=timeout)['content']
                if 'execution_state' in io_msg_content and\
                        io_msg_content['execution_state'] == 'idle':
                    break
            except Empty:
                break

        self._nbapp.web_app.kernel_locks[kernel_id].release()
        if 'data' in temp: # Indicates completed operation
            out = temp['data']['text/plain']
        elif 'name' in temp and temp['name'] == "stdout": # indicates output
            out = temp['text']
        elif 'traceback' in temp: # Indicates error
            out = '\n'.join(temp['traceback']) # Put error into nice format
        else:
            out = ''
        end_time = timer()
        self._nbapp.log.debug("[ANALYSIS] Code execution taking %s seconds" % (end_time - start_time))
        return out

    def make_newdata(self, call_node, assign_node):
        """got to assign at top of new data, fill in entry point"""
        self._add_entry(call_node, assign_node.targets)
#        self.entry_points["info"] = self._data_checks(assign_node.targets)
#        self._nbapp.log.debug("[ANALYSIS] info = {0}".format(self.entry_points["info"])) 

    def new_data_checks(self, targets):
        for target in targets:
            tgt_type = self.graph.get_type(target)
            self._nbapp.log.debug("[ANALYSIS] target type "+tgt_type)

            while not isinstance(target, Name):
                target = target.value
            self.entry_points[target.id]["imbalance"] = {}

            if tgt_type == DATAFRAME_TYPE:
                cols = self.get_col_names(target)
                self.entry_points[target.id]["imbalance"] = self.data_imbalance(target, cols)
                        
            elif tgt_type == SERIES_TYPE:
                pass # TODO: IDK if we should do this for series
               
    def data_imbalance(self, obj, colnames):
        output = {}
        for col in colnames:
            top_counts_expr = Call(Attribute(
                                value=Call(
                                    func=Attribute(
                                        value=Subscript(value=obj, slice=Index(value=Str(s=col))),
                                        attr="value_counts"),
                                    args=[], keywords=[keyword(arg="normalize", value=NameConstant(value=True))]),
                                attr="head"),args=[Num(n=10)],keywords=[])
            low_counts_expr = Call(Attribute(
                                value=Call(
                                    func=Attribute(
                                        value=Subscript(value=obj, slice=Index(value=Str(s=col))),
                                        attr="value_counts"),
                                    args=[], keywords=[keyword(arg="normalize", value=NameConstant(value=True))]),
                                attr="tail"),args=[Num(n=10)],keywords=[])
 
            list_expr = List(elts=[top_counts_expr, low_counts_expr])
            concat_call_expr = Call(
                                func=Attribute(value=Name(id="pd"), attr="concat"),
                                args=[list_expr], keywords=[])
            value_counts_expr = Call(
                                 func=Attribute(
                                   value=concat_call_expr,
                                   attr="to_dict"),
                                 args=[], keywords=[])
            resp = self._execute_code(astor.to_source(value_counts_expr))
            output[col] = eval(resp)

        return output 
#    def data_null(self, obj, colnames):
        
#    def data_corr(self, obj, colnames):     
    def is_newdata_call(self, call_node):
        """is this call node a pd read function"""
        func = call_node.func

        if isinstance(func, Name):
            for read_func in self._read_funcs:
                if read_func in self.pandas_alias.func_mapping:
                    if self.pandas_alias.func_mapping[read_func] == func.id:
                        self.graph.root_node(call_node)
                        return True
        elif isinstance(func, Attribute):
            # in this case, no issue with aliasing
            if func.attr in self._read_funcs:
                self.graph.root_node(call_node)
                return True
        return False

    def is_model_call(self, call_node):
        """is this call to an entity which is a model?"""

        """try executing to test if has "fit" method"""
        """there are a lot of sklearn methods so this seems easier"""

        expr = Expr(
            value=Call(
                func=Name(id="hasattr", ctx=Load()),
                args=[call_node, Str("fit")], keywords=[]))

        resp = self._execute_code(astor.to_source(expr))
        return resp == "True"

    def make_new_model(self, call_node, assign_node):
        """add model to environment"""
        var_names = assign_node.targets
        for var_name in assign_node.targets:
            self.models[var_name.id] = {}

#    def link(self, value, target):
#        """link two nodes together"""
#        self.live_set.add(target)
#        if value not in self.edges:
#            self.edges[value] = [target]
#        else:
#            self.edges[value].append(target)
    def add_train(self, func_node, args):
        """
        have made a fit(X, y) call on model
        fill in info about training data

        func_node is Attribute where attr == "fit"
        args are args input to fit
        """

        model_name = func_node.value.id
        self._nbapp.log.debug("[ANALYSIS] Retrieved model %s" % model_name)

        if model_name not in self.models:
            self._nbapp.log.debug("[ANALYSIS] %s not a registered model" % model_name)
            return

        # id labels
        label_call_or_name = self.resolve_data(args[1])
        self._nbapp.log.debug("[ANALYSIS] model %s has %s as labels" % (model_name, label_call_or_name))

        # id features
        feature_call_or_name = self.resolve_data(args[0])
        self._nbapp.log.debug("[ANALYSIS] model %s has %s as features" % (model_name, feature_call_or_name))

        # get label column names
        label_cols = None

        if self.graph.get_type(label_call_or_name) == DATAFRAME_TYPE:
            label_cols = self.get_col_names(label_call_or_name)
        elif self.graph.get_type(label_call_or_name) == SERIES_TYPE:
            label_cols = self.get_series_name(label_call_or_name)
        self._nbapp.log.debug("[ANALYSIS] %s seems to use %s as labels" % (model_name, label_cols))

        # get feature column names
        feature_cols = None
        if self.graph.get_type(feature_call_or_name) == DATAFRAME_TYPE:
            feature_cols = self.get_col_names(feature_call_or_name)
        elif self.graph.get_type(feature_call_or_name) == SERIES_TYPE:
            feature_cols = self.get_series_name(feature_call_or_name)
        self._nbapp.log.debug("[ANALYSIS] %s seems to use %s as features" % (model_name, feature_cols))

        self.models[model_name]["train"] = {}
        self.models[model_name]["train"]["features"] = feature_cols
        self.models[model_name]["train"]["labels"] = label_cols

        # run perf. test on features
    def get_series_name(self, call_or_name_node):

        series_name_expr = Attribute(value=call_or_name_node, attr="name")
        series_name_return = self._execute_code(astor.to_source(series_name_expr))
        
        try:
            return [eval(series_name_return)]
        except:
            return None

    def get_col_names(self, call_or_name_node):
        """try to get columns from the node"""
        #if not self.is_node_df(call_or_name_node):
        #    return None

        colnames_expression = Call(
            func=Name(id="list", ctx=Load()),
            args=[Attribute(value=call_or_name_node, attr="columns")], keywords=[])
        colnames_return = self._execute_code(astor.to_source(colnames_expression))
        try:
            return eval(colnames_return)
        except:
            return None

    def is_node_df(self, call_or_name_node):
        """does call or name refer to dataframe type in kernel?"""
        if "DataFrame" in self.pandas_alias.func_mapping:
            df_alias = parse(self.pandas_alias.func_mapping["DataFrame"])
        else:
            # TODO: we need to rewrite the alias module to handle this better.
            #       this is absolutely a dumb hack, and I expect it to break
            #       quickly.

            mod_aliases = list(self.pandas_alias.module_aliases)
            mod_aliases.sort(key=lambda x: len(x), reverse=True)
            df_alias = parse(mod_aliases[0]+".DataFrame")

        is_df_expr = Expr(
            value=Call(
                func=Name(id="isinstance", ctx=Load()),
                args=[call_or_name_node, df_alias], keywords=[]))
        is_df = self._execute_code(astor.to_source(is_df_expr))
        return is_df == "True"

    def is_node_series(self, node):
        """does node resolve to a pd.Series type?"""
        if "Series" in self.pandas_alias.func_mapping:
            series_alias = parse(self.pandas_alias.func_mapping["Series"])
        else:
            # TODO: we need to rewrite the alias module to handle this better.
            #       this is absolutely a dumb hack, and I expect it to break
            #       quickly.

            mod_aliases = list(self.pandas_alias.module_aliases)
            mod_aliases.sort(key=lambda x: len(x), reverse=True)
            series_alias = parse(mod_aliases[0]+".Series")

        # TODO: might be better to do just a simple string comparison, avoids
        #       import issue

        # experiment suggests it works, but other issues (subclasses etc) remain

        is_series_expr = Expr(
            value=Call(
                func=Name(id="isinstance", ctx=Load()),
                args=[node, series_alias], keywords=[]))
        is_series = self._execute_code(astor.to_source(is_series_expr))
        return is_series == "True"

    def resolve_data(self, node, permitted_types={DATAFRAME_TYPE, SERIES_TYPE}):
        """
        given a node, find nearest upstream variable with type in permitted_type

        """
        if self.graph.get_type(node) in permitted_types:
            return node
        queue = self.graph.get_parents(node)

        while queue:
            parent = queue.pop()
            if self.graph.get_type(parent) in permitted_types:
                return parent
            queue.extend(self.graph.get_parents(parent))
        return None

    def resolve_type_flow(self, source, dest):
        """given knowledge of source node, can we tell what type dest is?"""
        # if a call to one of the ambiguous functions, try to resolve 
        if self.graph.get_type(source) == MAYBE_TYPE:
            if self.is_node_df(dest): 
                self.graph.set_type(source,  DATAFRAME_TYPE)
                return DATAFRAME_TYPE
            if self.is_node_series(dest): 
                self.graph.set_type(source, SERIES_TYPE)
                return SERIES_TYPE
            return MAYBE_TYPE
        if isinstance(dest, Attribute):
            if dest.attr in other_funcs:
                return OTHER_TYPE
            if dest.attr in ambig_funcs:
                if self.is_node_df(dest): return DATAFRAME_TYPE
                if self.is_node_series(dest): return SERIES_TYPE
                return MAYBE_TYPE
            if dest.attr in series_funcs:
                return SERIES_TYPE
        if isinstance(dest, Subscript):
           if self.graph.get_type(source) == DATAFRAME_TYPE:
               if isinstance(dest.slice, Index):
                   if isinstance(dest.slice.value, Str):
                       return SERIES_TYPE
        
        return self.graph.get_type(source)

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

class CellVisitor(NodeVisitor):
    # pylint: disable=invalid-name
    """
    visit the AST of the code in the cell
    connect data introduction, flow, and sinks
    """

    def __init__(self, environment):
        """
        environment = the analysis environment, necessary to log aliases, etc.
        """
        super().__init__()
        self.env = environment
        self.nodes = set()
        self.unfinished_call = None

    def visit_Import(self, node):
        """visit nodes formed by import foo or import foo.bar or import foo as bar"""
        for alias in node.names:
            self.env.pandas_alias.add_import(alias)
            self.env.sklearn_alias.add_import(alias)

    def visit_ImportFrom(self, node):
        """visit nodes which are like import x from y [as z]"""
        module_name = node.module
        for alias in node.names:
            self.env.pandas_alias.add_importfrom(module_name, alias)
            self.env.sklearn_alias.add_importfrom(module_name, alias)

    def visit_Assign(self, node):
        """
        in visiting assign, check if the RHS either is tagged (TODO) or
        intros new data
        """
        self.generic_visit(node) # visit children BEFORE completing this
        # a call node is newdata, and this is nearest assign
        new_data = False

        if self.unfinished_call:
            if self.env.is_newdata_call(self.unfinished_call):
                self.env.make_newdata(self.unfinished_call, node)
                new_data = True
            elif self.env.is_model_call(self.unfinished_call):
                self.env.make_new_model(self.unfinished_call, node)
            self.unfinished_call = None

        if node.value in self.nodes:
            for trgt in node.targets:
                self.env.graph.link(node.value, trgt, 
                                    dest_type=self.env.resolve_type_flow(node.value, trgt))
                self.nodes.add(trgt)
        if node.value not in self.nodes:
            for trgt in node.targets:
                self.nodes.discard(trgt)
                self.env.graph.remove_name(trgt)

        if new_data:
            self.env.new_data_checks(node.targets)

    #def visit_Delete(self, node):
    def visit_Call(self, node):
        """propogate tagging if function or arguments tagged"""
        self.generic_visit(node)
        if node.func in self.nodes:
            self.env.graph.link(node.func, node)
            self.nodes.add(node)
        for arg in node.args:
            if arg in self.nodes:
                self.env.graph.link(arg, node,
                                    dest_type=self.env.resolve_type_flow(arg, node))
                self.nodes.add(node)

        # TODO: this could be potentially an issue if someone
        #       does something goofy like
        #
        #       lr = LinearRegression().fit(read_csv(), read_csv())

        if self.env.is_newdata_call(node):
            self.nodes.add(node)
            self.unfinished_call = node
        if self.env.is_model_call(node):
            self.nodes.add(node)
            self.unfinished_call = node
        if isinstance(node.func, Attribute) and node.func.attr == "fit":
            self.env.add_train(node.func, node.args)

    def visit_Attribute(self, node):
        """if attribute references tagged object, extend"""
        self.generic_visit(node)
        if node.value in self.nodes: # referencing a tagged element
            self.nodes.add(node)
            self.env.graph.link(node.value, node, dest_type=self.env.resolve_type_flow(node.value, node))

    def visit_Name(self, node):
        """is name referencing a var we care about?"""
        name_node = self.env.graph.find_by_name(node)
        if name_node:
            self.env.graph.link(name_node, node, dest_type=self.env.resolve_type_flow(name_node, node))
            self.nodes.add(node)

    def visit_Subscript(self, node):
        """
        visit a subscript node, extend analysis if subscripted object is 
        part of graph.
        """
        self.generic_visit(node)
        if node.value in self.nodes:
            self.nodes.add(node)
            self.env.graph.link(node.value, node,
                                dest_type=self.env.resolve_type_flow(node.value, node))

#            if isinstance(node.value, Attribute) and node.value.attr in index_funcs:
#                if self.env.is_node_df(node):
#                    self.env.graph._df_nodes.add(node)
#                    self.env.graph._df_nodes.add(node.value)

#    def visit_Expr(self, node):

    # TODO: function definitions, attributes

class Graph:
    """
    keep track of connections between ast nodes
    """
    def __init__(self):

        self.edges = {}
        self.reverse_edges = {} # not super efficient representation, but w/e
        self.entry_points = set() # aka root nodes
        self._name_register = {}

        self._type_register = {} # maps nodes to dataframe, series, or unknown type

    def _register_name(self, maybe_name):
        if isinstance(maybe_name, Name):
            if maybe_name.id not in self._name_register:
                self._name_register[maybe_name.id] = maybe_name

    def link(self, source, dest, dest_type=None):
        """
        create link between source and dest nodes

        dest_type (optional) the type of the destination node, default None
        """

        self._register_name(dest)
        self._type_register[dest] = dest_type

        if source not in self.edges:
            self.edges[source] = [dest]
        else:
            self.edges[source].append(dest)

        if dest not in self.reverse_edges:
            self.reverse_edges[dest] = [source]
        else:
            self.reverse_edges[dest].append(source)

    def root_node(self, node, is_df=True):
        """add root node"""
        self.edges[node] = []

        self.entry_points.add(node)

        if is_df: self._type_register[node] = DATAFRAME_TYPE
        else: self._type_register[node] = None

    def find_by_name(self, name_node):
        """find the nodes associated with name"""
        if name_node.id in self._name_register:
            return self._name_register[name_node.id]
        return None

    def remove_name(self, name_node):
        """remove name from name tracking (if call to del name or redefinition happens)"""
        if name_node.id in self._name_register:
            del self._name_register[name_node.id]

    def get_parents(self, node):
        """return the parents of node, raises keyerror if node has no parents"""
        return self.reverse_edges[node]
    def get_type(self, node):
        """return type (dataframe, series, or none) of node"""
        if node not in self._type_register:
            return None
        return self._type_register[node]
    def set_type(self, node, type_name):
        """set a nodes type, if node was not in graph, node is added to graph"""
        self._type_register[node] = type_name
def get_call(assign_node):
    """search down until we find the root call node"""
    last_call = None
    queue = [assign_node]

    while len(queue) > 0:
        node = queue.pop()
        if isinstance(node, Call):
            last_call = node
        if not hasattr(node, "_fields"):
            continue
        for field in node._fields:
            if isinstance(getattr(node, field), list):
                for elt in getattr(node, field):
                    if not isinstance(elt, str):
                        queue.insert(0, elt)
            elif not isinstance(getattr(node, field), str):
                queue.insert(0, getattr(node, field))
            # TODO make more precise by chekcing if subtype of AST node
    return last_call


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
