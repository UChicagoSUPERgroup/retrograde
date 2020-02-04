"""
test the DbHandler methods
"""

import unittest
import sqlite3
import os

from ast import parse
from context import prompter

class TestAnalysisMethods(unittest.TestCase):

    def test_import_module(self):

        simple_import = "import pandas"
        alias_import = "import pandas as pd"
        
        multiple_import = "import pandas, numpy, sklearn"
        multiple_alias = "import pandas as pd, sklearn as sk"

        submod_import = "import sklearn.metrics"
        # TODO: Never actually seen an import of that form, lower priority for the moment
        # TODO: star imports (i.e. "from <module> import *")

        imports_list = [simple_import, alias_import, 
                        multiple_import, multiple_alias, submod_import]

        
        imports_asts = [parse(c).body[0] for c in imports_list]
       
        expected_outputs = [
            {"pandas" : 
                {"module_aliases" : set(["pandas"]), 
                 "func_mapping" : {},
                 "functions" : set()},
            "sklearn" : 
                {"module_aliases" : set(),
                 "func_mapping" : {},
                 "functions" : set()},
            },
            {"pandas" : 
                {"module_aliases" : set(["pd"]), 
                 "func_mapping" : {},
                 "functions" : set()},
            "sklearn" : 
                {"module_aliases" : set(),
                 "func_mapping" : {},
                 "functions" : set()},
            },
            {"pandas" : 
                {"module_aliases" : set(["pandas"]), 
                 "func_mapping" : {},
                 "functions" : set()},
            "sklearn" : 
                {"module_aliases" : set(["sklearn"]),
                 "func_mapping" : {},
                 "functions" : set()},
            },
            {"pandas" : 
                {"module_aliases" : set(["pd"]), 
                 "func_mapping" : {},
                 "functions" : set()},
            "sklearn" : 
                {"module_aliases" : set(["sk"]),
                 "func_mapping" : {},
                 "functions" : set()},
            },
            {"pandas" : 
                {"module_aliases" : set(), 
                 "func_mapping" : {},
                 "functions" : set()},
            "sklearn" : 
                {"module_aliases" : set(["sklearn"]),
                 "func_mapping" : {},
                 "functions" : set()},
            },]
        for source,import_ast,expected in zip(imports_list, imports_asts, expected_outputs):

            env = prompter.AnalysisEnvironment(None)
            env.add_imports(import_ast)
            self._compare_alias_env(env, expected_outputs)
            
    def _compare_alias_env(self, env, expected):

        self.assertEqual(expected["pandas"]["module_aliases"],
                         env.pandas_alias.module_aliases)
        self.assertEqual(expected["pandas"]["func_mapping"],
                         env.pandas_alias.func_mapping)
        self.assertEqual(expected["pandas"]["functions"],
                         env.pandas_alias.functions)
                          
        self.assertEqual(expected["sklearn"]["module_aliases"],
                         env.sklearn_alias.module_aliases)
        self.assertEqual(expected["sklearn"]["func_mapping"],
                         env.sklearn_alias.func_mapping)
        self.assertEqual(expected["sklearn"]["functions"],
                         env.sklearn_alias.functions)

    def test_import_from(self):

        from_import = "from pandas import Dataframe"
        from_alias = "from pandas import Dataframe as Df"
        from_submod = "from sklearn.neighbors import BallTree"
        from_as_submod = "from sklearn.neighbors import BallTree as bt"

        expected_outputs = [
            {"pandas" : 
                {"module_aliases" : set(), 
                 "func_mapping" : {"Dataframe" : "Dataframe"},
                 "functions" : set(["Dataframe"])},
            "sklearn" : 
                {"module_aliases" : set(),
                 "func_mapping" : {},
                 "functions" : set()},
            },
            {"pandas" : 
                {"module_aliases" : set(), 
                 "func_mapping" : {"Dataframe": "Df"},
                 "functions" : set("Df")},
            "sklearn" : 
                {"module_aliases" : set(),
                 "func_mapping" : {},
                 "functions" : set()},
            },
            {"pandas" : 
                {"module_aliases" : set(), 
                 "func_mapping" : {},
                 "functions" : set()},
            "sklearn" : 
                {"module_aliases" : set(),
                 "func_mapping" : {"BallTree" : "BallTree"},
                 "functions" : set(["BallTree"])},
            },
            {"pandas" : 
                {"module_aliases" : set(), 
                 "func_mapping" : {},
                 "functions" : set()},
            "sklearn" : 
                {"module_aliases" : set(),
                 "func_mapping" : {"BallTree", "bt"},
                 "functions" : set("bt")},
            },]
        for source,import_ast,expected in zip(imports_list, imports_asts, expected_outputs):

            env = prompter.AnalysisEnvironment(None)
            env.add_imports(import_ast)
            self._compare_alias_env(env, expected_outputs)

    def test_newdata(self):

        formats = ["csv", "fwf", "json", "html", "clipboard", "excel", 
                    "hdf", "feather", "parquet", "orc", "msgpack", "stata",
                    "sas", "spss", "pickle", "sql", "gbq"]

        function_names = ["read_"+fmt for fmt in formats]
        import_stmnt = "import pandas as pd\n" 
        calls = [import_stmnt+"df = pd."+fn+"(filename.csv)" for fn in function_names]
        
    
        for call in calls:

            env = prompter.AnalysisEnvironment(None)
            output = env.new_data(call_ast)
            self.assertEqual(output, "filename.csv", "error interpreting "+call)
    def test_newdata_importfrom(self):
        """
        test from pandas import read_*
        """

        formats = ["csv", "fwf", "json", "html", "clipboard", "excel", 
                    "hdf", "feather", "parquet", "orc", "msgpack", "stata",
                    "sas", "spss", "pickle", "sql", "gbq"]

        function_names = ["read_"+fmt for fmt in formats]
         
        calls = ["from pandas import "+fn+"\n" for fn in function_names]

    def test_newdata_import_alias(self):
        """
        test from pandas import read_* as func_name
        """
        pass
    def test_newdata_import_comprehension(self)
        """
        test x = read_csv()[d]...[y]
        """
        pass 
    def test_newdata_import_chaining(self):
        """
        test x = read_csv(file).select()
        """
        pass

if __name__ == "__main__":
    unittest.main()
