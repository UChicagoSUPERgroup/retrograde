"""
analysis.py creates a running environment for dynamically tracking
data relationships between variables
"""
from ast import parse, Import, Assign, Import, ImportFrom
from code import InteractiveInterpreter

class AnalysisEnvironment(object):
    """
    Analysis environment creates a session wit
    """
    def __init__(self, dbhandler):

        self.pandas_alias = Alias("pandas")
        self.sklearn_alias = Alias("sklearn")

        self._var_table = {
            "functions" : {},
            "vars" : {}}
    
#        self._session = InteractiveInterpreter()

    def cell_exec(self, code):
        """
        execute a cell and propagate the analysis
        """
        cell_code = parse(code) 
       
        for block in cell_code.body: 
            if type(block) in [ClassDef, FunctionDef]:
                self.execute_function(block):
            else:
                self.execute_line(block)

    def execute_line(self, line):
        """
        execute a single line from the cell. 
        """
        # imports?
        if type(line) == Import:
            self.add_imports(line)
        if type(line) == Assign:
            # bringing in new data?
            # data being propagated?
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

        self._imports.sort(key = lambda x: x.count("."))
         
        for already_import in self._imports:
            # this is a bug - but not likely to come up
            if modulename.find(already_import) == 0:
                return True
        return False
