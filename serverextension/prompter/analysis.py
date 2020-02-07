"""
analysis.py creates a running environment for dynamically tracking
data relationships between variables
"""
from ast import Import, Assign, Import, ImportFrom, NodeVisitor, Call, Name, Attribute
from ast import parse, walk, iter_child_nodes
#from code import InteractiveInterpreter

class AnalysisEnvironment(object):
    """
    Analysis environment tracks relevant variables in execution

    TODO: should add ability to execute in parallel, in order to be able to run
          tests DS isn't thinking of
    """
    def __init__(self):

        self.pandas_alias = Aliases("pandas")
        self.sklearn_alias = Aliases("sklearn")

        self.entry_points = {}
        self.edges = {}
        self.live_set = set()
        self.names = {}

        self._read_funcs = ["read_csv", "read_fwf", "read_json", "read_html",
                            "read_clipboard", "read_excel", "read_hdf",
                            "read_feather", "read_parquet", "read_orc", 
                            "read_msgpack", "read_stata", "read_sas",
                            "read_spss", "read_pickle", "read_sql", 
                            "read_gbq"]

        # Callgraph related 
#        self._session = InteractiveInterpreter()

    def cell_exec(self, code):
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

    def is_tagged(self, node):
        """
        is a node tagged, and if not is it new data?

        if it is new data, tag it and create node in graph
        """
        if node in self.live_set:
            return True
        elif type(node) == Call:
            if self.is_newdata(node):
                source = node.args[0]
                format_type = node.func.id.split("_")[1]
                var_names = get_var_assign(node) # get nearest node assign
                for var_name in var_names:
                    self.entry_points[var_name.id] = {"format" : format_type, "source" : str(source)}
                    self.names[var_name.id] = get_store(var_name)
                self.edges[node] = []
                self.live_set.add(node)
                return True 
        return False

    def is_newdata(self, call_node):
        """is the call node a call to pd.read_*?"""

        func = call_node.func

        if type(func) == Name:
            for read_func in self._read_funcs:
                if read_func in self.pandas_alias.func_mapping:
                    if self.pandas_alias.func_mapping[read_func] == func.id:
                        return True
        elif type(func) == Attribute:
            # in this case, no issue with aliasing
            return func.attr in self._read_funcs 
        return False 
    def link(self, value, target):
        """link two nodes together"""
        self.live_set.add(target)
        if value not in self.edges:
            self.edges[value] = [target]
        else:
            self.edges[value].append(target)

    def is_active_name(self, name):
        """is the name actively being tracked?"""
        return name.id in self.names

    def get_def(self, name):
        """get the last store operation to this name"""
        return self.names[name.id]

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
   
        if self.env.is_tagged(node.value):
            for trgt in node.targets:
                self.env.link(node.value, trgt)
        # case where value untagged, but a target was tagged, name should stop being tagged
    #def visit_Delete(self, node):
    def visit_Call(self, node):
        """propogate tagging if function or arguments tagged"""
        self.generic_visit(node)
        if self.env.is_tagged(node.func):
            self.env.link(node.func, node)
        for arg in node.args:
            if self.env.is_tagged(arg): self.env.link(arg, node)

    def visit_Name(self, node):
        """is name referencing a var we care about?"""
        if self.env.is_active_name(node):
            self.env.link(self.env.get_def(node), node)

    # TODO: function definitions, attributes

def get_var_assign(node):
    """walk upward until we can get nearest name assignment"""

    parent = node
    while type(parent) != Assign:
        if not hasattr(parent, "parent"):
            return []
        parent = parent.parent
    return parent.targets

def get_store(name_node):
    """get most proximate storage op"""
    parent = name_node
    while type(parent) != Assign:
        if not hasattr(parent, "parent"):
            return None
        parent = parent.parent
    return parent
