"""
analysis.py creates a running environment for dynamically tracking
data relationships between variables
"""
from queue import Empty
from ast import Import, NodeVisitor, Call, Name, Attribute, Expr, Load, Str
from ast import parse, walk, iter_child_nodes

from .config import df_funcs, index_funcs

import astor
#from code import InteractiveInterpreter

class AnalysisEnvironment(object):
    """
    Analysis environment tracks relevant variables in execution

    TODO: should add ability to execute in parallel, in order to be able to run
          tests DS isn't thinking of
    """
    def __init__(self, nbapp):
        """
        nbapp = the notebook application object
        """
        self.pandas_alias = Aliases("pandas") # handle imports and functions
        self.sklearn_alias = Aliases("sklearn")

        self.entry_points = {} # new data introduced into notebook
        self.graph = Graph() # connections
        self.active_names = set()

        self._read_funcs = ["read_csv", "read_fwf", "read_json", "read_html",
                            "read_clipboard", "read_excel", "read_hdf",
                            "read_feather", "read_parquet", "read_orc", 
                            "read_msgpack", "read_stata", "read_sas",
                            "read_spss", "read_pickle", "read_sql", 
                            "read_gbq"]
        self._nbapp = nbapp
#        self._session = InteractiveInterpreter()
        self.models = {}

    def cell_exec(self, code, notebook):
        """
        execute a cell and propagate the analysis
        """
        cell_code = parse(code) 
        
        # add parent data to each node
        for node in walk(cell_code):
            for child in iter_child_nodes(node):
                child.parent = node

        visitor = CellVisitor(self)
        visitor.visit(cell_code)

        # TODO: need hooks to check if kernel access needed 

    def _add_entry(self, call_node, targets):
        """add an entry point"""
        source = as_string(call_node.args[0])
        if type(call_node.func) == Name:
            if call_node.func.id not in self._read_funcs:
                func_name = self.pandas_alias.get_alias_for(call_node.func.id)
                fmt = func_name.split("_")[-1]
            else:
                fmt = call_node.func.id.split("_")[-1]
        else:
            fmt = call_node.func.attr.split("_")[-1]
        for target in targets:
            while type(target) != Name:
                target = target.value # assumes target is attribute type
            self.entry_points[target.id] = {"source" : source, "format" : fmt}

    def _execute_code(self, code, kernel_id, timeout=1):

        kernel = self._nbapp.get_kernel(kernel_id)
        client = kernel.client()
        msg_id = client.execute(code)

        reply = client.get_shell_msg(msg_id)
        # using loop from https://github.com/abalter/polyglottus/blob/master/simple_kernel.py

        io_msg_content = client.get_iopub_msg(timeout=timeout)['content']

        if 'execution_state' in io_msg_content and io_msg_content['execution_state'] == 'idle':
            return "no output"

        while True:
            temp = io_msg_content
            try:
                io_msg_content = client.get_iopub_msg(timeout=timeout)['content']
                if 'execution_state' in io_msg_content and io_msg_content['execution_state'] == 'idle':
                    break
            except Empty:
                break
        if 'data' in temp: # Indicates completed operation
            out = temp['data']['text/plain']
        elif 'name' in temp and temp['name'] == "stdout": # indicates output
            out = temp['text']
        elif 'traceback' in temp: # Indicates error
            out = '\n'.join(temp['traceback']) # Put error into nice format
        else:
            out = ''
        return out

    def make_newdata(self, call_node, assign_node):
        """got to assign at top of new data, fill in entry point"""
        self._add_entry(call_node, assign_node.targets)

    def is_newdata_call(self, call_node):
        """is this call node a pd read function"""
        func = call_node.func

        if type(func) == Name:
            for read_func in self._read_funcs:
                if read_func in self.pandas_alias.func_mapping:
                    if self.pandas_alias.func_mapping[read_func] == func.id:
                        self.graph.root_node(call_node)
                        return True
        elif type(func) == Attribute:
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
            value = Call(
                func = Name(id="hasattr", ctx=Load()),
                args = [call_node, Str("fit")], keywords = []))
        
        resp = self._execute_code(astor.to_source(expr), "TEST")
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
        self._nbapp.log("Retrieved model %s" % model_name)

        if model_name not in self.models:
            self._nbapp.log("%s not a registered model" % model_name)
            return

        # id labels 
        label_call_or_name = self.resolve_data(args[1])
        self._nbapp.log("model %s has %s as labels" % (model_name, label_call_or_name))

        # id features 
        feature_call_or_name = self.resolve_data(args[0]) 
        self._nbapp.log("model %s has %s as features" % (model_name, feature_call_or_name))

        # get label column names
        label_cols = self.get_col_names(label_call_or_name)
        self._nbapp.log("%s seems to use %s as labels" % (model_name, label_cols))

        # get feature column names
        feature_cols = self.get_col_names(feature_call_or_name)
        self._nbapp.log("%s seems to use %s as features" % (model_name, feature_cols))

        self.models[model_name]["train"] = {}
        self.models[model_name]["train"]["features"] = feature_cols
        self.models[model_name]["train"]["labels"] = feature_cols

        # run perf. test on features
    def get_col_names(self, call_or_name_node):
        """try to get columns from the node"""
        if not self.is_node_df(call_or_name_node):
            return None

        colnames_expression = Call(
                func = Name(id="list", ctx=Load()),
                args = [Attribute(value = call_or_name_node, attr="columns")], keywords=[])
        colnames_return = self._execute_code(astor.to_source(colnames_expression), "TEST")

        try:
            return eval(colnames_return)
        except:
            return None
    def is_node_df(self, call_or_name_node): 

        if "DataFrame" in self.pandas_alias.func_mapping:
            df_alias = parse(self.pandas_alias.func_mapping["DataFrame"])
        else:
            # TODO: we need to rewrite the alias module to handle this better.
            #       this is absolutely a dumb hack, and I expect it to break 
            #       quickly.

            mod_aliases = list(self.pandas_alias.module_aliases)
            mod_aliases.sort(key = lambda x: len(x), reverse=True)
            df_alias = parse(mod_aliases[0]+".DataFrame")

        is_df_expr = Expr(
                value = Call(
                    func = Name(id="isinstance", ctx=Load()),
                    args = [call_or_name_node, df_alias], keywords = []))
        is_df = self._execute_code(astor.to_source(is_df_expr), "TEST")
        return is_df == "True"

    def resolve_data(self, node):
        """given a node, find nearest df variable"""
        if self.graph.is_dataframe(node):
            return node
        queue = self.graph.get_parents(node)
        
        while queue:
            parent = queue.pop()
            if self.graph.is_dataframe(parent):
                return parent
            queue.extend(self.graph.get_parents(parent))
        return None

    def is_df_func(self, attr_node):
        """is this attribute accessing a function that could return a nondataframe typed value?"""
        if not self.graph.is_dataframe(attr_node.value):
            return False
        # Check against a list of df methods
        if attr_node.attr in df_funcs + index_funcs:
            return False
        return True
class Aliases(object):

    def __init__(self, module_name):

        self.name = module_name
        self.module_aliases = set() # live names in session
        self.func_mapping = {}
        self.functions = set()

    def import_module_as(self, alias_name):
        self.module_aliases.add(alias_name)

    def import_func(self, func_name, alias_name = None):
        if not alias_name:
            self.func_mapping[func_name] = func_name
            self.functions.add(func_name)
        else:
            self.func_mapping[func_name] = alias_name
            self.functions.add(alias_name)

    def import_glob(self, module):
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
        if self.unfinished_call:
            if self.env.is_newdata_call(self.unfinished_call): 
                self.env.make_newdata(self.unfinished_call, node)
            elif self.env.is_model_call(self.unfinished_call):
                self.env.make_new_model(self.unfinished_call, node)
            self.unfinished_call = None

        if node.value in self.nodes:
            for trgt in node.targets:
                self.env.graph.link(node.value, trgt)
                self.nodes.add(trgt)
        if node.value not in self.nodes:
            for trgt in node.targets:
                self.nodes.discard(trgt)
                self.env.graph.remove_name(trgt) 

    #def visit_Delete(self, node):
    def visit_Call(self, node):
        """propogate tagging if function or arguments tagged"""
        self.generic_visit(node)
        if node.func in self.nodes:
            self.env.graph.link(node.func, node)
            self.nodes.add(node)
        for arg in node.args:
            if arg in self.nodes: 
                self.env.graph.link(arg, node)
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
        self.generic_visit(node)
        if node.value in self.nodes: # referencing a tagged element
            self.nodes.add(node)
            self.env.graph.link(node.value, node, preserve_df = self.env.is_df_func(node))

    def visit_Name(self, node):
        """is name referencing a var we care about?"""
        if self.env.graph.find_by_name(node):
            self.env.graph.link(self.env.graph.find_by_name(node), node)
            self.nodes.add(node)

    def visit_Subscript(self, node):
        self.generic_visit(node)
        if node.value in self.nodes:
            self.nodes.add(node)
            self.env.graph.link(node.value, node)
        
            if isinstance(node.value, Attribute) and node.value.attr in index_funcs:
                if self.env.is_node_df(node): 
                    self.env.graph._df_nodes.add(node)
                    self.env.graph._df_nodes.add(node.value)
        # TODO: pickup here tomorrow -- if subscript encloses a pd indexing function, 
        # test if the subscript is a dataframe instance

#    def visit_Expr(self, node):
        
    # TODO: function definitions, attributes

class Graph:
    """
    keep track of connections between ast nodes
    """
    def __init__(self):

        self.edges = {}
        self.reverse_edges = {} # not super efficient representation, but w/e
        self.nodes = set()
        self.active_nodes = set()
        self.entry_points = set()
        self._name_register = {}
    
        self._df_nodes = set() # nodes which resolve to a dataframe type


    def _register_name(self, maybe_name):
        if type(maybe_name) == Name:
            if maybe_name.id not in self._name_register:
                self._name_register[maybe_name.id] = maybe_name

    def link(self, source, dest, preserve_df = True):
        """
        create link between source and dest nodes
        """

        self.active_nodes.add(source)
        self.active_nodes.add(dest)
        self.nodes.add(source)

        self._register_name(dest)

        if source not in self.edges:
            self.edges[source] = [dest]
        else:
            if preserve_df and source in self._df_nodes:
                self._df_nodes.add(dest)
            self.edges[source].append(dest)

        if dest not in self.reverse_edges:
            self.reverse_edges[dest] = [source]
        else:
            self.reverse_edges[dest].append(source)

        self.nodes.add(source)
        self.nodes.add(dest)

    def root_node(self, node, is_df = True):
        """add root node"""
        self.edges[node] = []
        self.nodes.add(node)

        self.active_nodes.add(node)
        self.entry_points.add(node)
        
        if is_df: self._df_nodes.add(node)

    def find_by_name(self, name_node):        
        """find the nodes associated with name"""
        if name_node.id in self._name_register:
            return self._name_register[name_node.id]
        else:
            return None

    def remove_name(self, name_node):
        if name_node.id in self._name_register:
            del self._name_register[name_node.id]

    def is_dataframe(self, node):
        """will node resolve to a dataframe type object?"""
        if node not in self.nodes:
            raise Exception("node is not tracked, so cannot say if is dataframe or not")
        return node in self._df_nodes

    def get_parents(self, node):
        """return the parents of node, raises keyerror if node has no parents"""
        return self.reverse_edges[node]

def get_call(assign_node):
    """search down until we find the root call node"""
    last_call = None
    queue = [assign_node]

    while len(queue) > 0:
        node = queue.pop()
        if type(node) == Call:
            last_call = node
        if not hasattr(node, "_fields"):
            continue
        for field in node._fields:
            if isinstance(getattr(node, field), list):
                for elt in getattr(node, field):
                    if type(elt) != str:
                        queue.insert(0, elt)
            elif not isinstance(getattr(node, field),str):
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
    return ""
