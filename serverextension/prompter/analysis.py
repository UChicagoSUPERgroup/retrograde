"""
analysis.py creates a running environment for dynamically tracking
data relationships between variables
"""
from ast import parse, Import, Assign, Import, ImportFrom
from code import InteractiveInterpreter

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

#        self._session = InteractiveInterpreter()

    def cell_exec(self, code):
        """
        execute a cell and propagate the analysis
        """
        cell_code = parse(code) 

    def add_imports(self, line):
        """
        take an import ast node and render the names to watch for
        """
         
        new_imports = []

        if type(line) == Import:
            for alias_node in line.names:
                if self._check_submod(alias_node.name):
                    if not alias_node.asname:
                        new_imports.append(alias_node.name)
                    else:
                        new_imports.append(alias_node.asname)
        elif type(line) == ImportFrom:
            if self._check_submod(line.module):
                for alias_node in line.names:
                    if not alias_node.asname:
                        new_imports.append(alias_node.name)
                    else:
                        new_imports.append(alias_node.asname)
        return new_imports

    
    def new_data(self, line):
        """
        note introduction of new entry points (i.e. call to pd.read_*)
        """
    def is_tagged(self, node):
        pass
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
        pass #TODO

    def add_import(self, alias_node):
        """
        take an alias node from an import stmnt ("name","asname") and 
        add to space if imported module a submod of this alias space
        """
        pass #TODO
    def add_importfrom(self, module_name, alias_node):
        """
        take an import from statement, and add mapping if 
        module_name is a submodule of this alias space
        """
        pass # TODO

class CellVisitor(NodeVisitor):

    """
    visit the AST of the code in the cell
    connect data introduction, flow, and sinks
    """

    def __init__(self, environment):
        """
        environment = the analysis environment, necessary to log aliases, etc.
        """
        super.__init__()
        self.env = environment

    def visit_Import(self, node):
        """visit nodes formed by import foo or import foo.bar or import foo as bar"""
        for alias in node.names:
            self.env.pandas_alias.add_import(alias)
            self.env.sklearn_alias.add_import(alias)

    def visit_ImportFrom(self, node):
        """visit nodes which are like import x from y [as z]"""
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
                self.env.tag(trgt)

    def visit_Call(self, node)
    # TODO: function definitions
