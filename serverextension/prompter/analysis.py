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
             
    def link(self, value, target):
        """link two nodes together"""
        self.live_set.add(target)
        if value not in self.edges:
            self.edges[value] = [target]
        else:
            self.edges[value].append(target)

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
            self.env.make_newdata(self.unfinished_call, node)
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

        if self.env.is_newdata_call(node):
            self.nodes.add(node)
            self.unfinished_call = node

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if node.value in self.nodes: # referencing a tagged element
            self.nodes.add(node)
            self.env.graph.link(node.value, node)

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
#    def visit_Expr(self, node):
        
    # TODO: function definitions, attributes

class Graph:
    """
    keep track of connections between ast nodes
    """
    def __init__(self):

        self.edges = {}
        self.active_nodes = set()
        self.entry_points = set()
        self._name_register = {}

    def _register_name(self, maybe_name):
        if type(maybe_name) == Name:
            if maybe_name.id not in self._name_register:
                self._name_register[maybe_name.id] = maybe_name

    def link(self, source, dest):
        """
        create link between source and dest nodes
        """

        self.active_nodes.add(source)
        self.active_nodes.add(dest)

        self._register_name(dest)

        if source not in self.edges:
            self.edges[source] = [dest]
        else:
            self.edges[source].append(dest)

    def root_node(self, node):
        """add root node"""
        self.edges[node] = []
        self.active_nodes.add(node)
        self.entry_points.add(node)

    def find_by_name(self, name_node):        
        """find the nodes associated with name"""
        if name_node.id in self._name_register:
            return self._name_register[name_node.id]
        else:
            return None
    def remove_name(self, name_node):
        if name_node.id in self._name_register:
            del self._name_register[name_node.id]

def get_call(assign_node):
    """search down until we find the root call node"""
    last_call = None
    q = [assign_node]

    while len(q) > 0:
        node = q.pop()
        if type(node) == Call:
            last_call = node
        if not hasattr(node, "_fields"):
            continue
        for field in node._fields:
            if type(getattr(node, field)) == list:
                for elt in getattr(node, field):
                    if type(elt) != str:
                        q.insert(0, elt)
            elif type(getattr(node, field)) != str:
                q.insert(0, getattr(node, field))
            # TODO make more precise by chekcing if subtype of AST node 
    return last_call

def as_string(name_or_attrib):
    if type(name_or_attrib) == Attribute:
        full = name_or_attrib.attr
        curr = name_or_attrib

        while type(curr) == Attribute:
            curr = curr.value
            if type(curr) == Attribute:
                full = curr.attr+"."+full
            elif type(curr) == Name:
                full = curr.id+"."+full
        return full
    if type(name_or_attrib) == Name:
        return name_or_attrib.id
