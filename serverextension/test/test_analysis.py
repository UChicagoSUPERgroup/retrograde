"""
test the DbHandler methods
"""

import unittest

from ast import parse
from context import prompter

class TestAnalysisMethods(unittest.TestCase):
    """
    test import detection, new data addition, tracking, and model train/test
    call functionality
    """

    def test_import_module(self):
        """
        test whether various ways of importing pandas and sklearn functions
        are properly detected
        """

        simple_import = "import pandas"
        alias_import = "import pandas as pd"
        
        multiple_import = "import pandas, numpy, sklearn"
        multiple_alias = "import pandas as pd, sklearn as sk"

        submod_import = "import sklearn.metrics"
        # TODO: Never actually seen an import of that form, lower priority for the moment
        # TODO: star imports (i.e. "from <module> import *")

        imports_list = [simple_import, alias_import, 
                        multiple_import, multiple_alias, submod_import]

        
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
                {"module_aliases" : set(["sklearn.metrics"]),
                 "func_mapping" : {},
                 "functions" : set()},
            },]
        for import_stmnt, expected in zip(imports_list, expected_outputs):

            env = prompter.AnalysisEnvironment()
            env.cell_exec(import_stmnt)
            self._compare_alias_env(env, expected)

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
        """test whether imports of the form "from <module> import foo" are correctly tagged"""

        from_import = "from pandas import Dataframe"
        from_alias = "from pandas import Dataframe as Df"
        from_submod = "from sklearn.neighbors import BallTree"
        from_as_submod = "from sklearn.neighbors import BallTree as bt"

        import_stmnts = [from_import, from_alias, from_submod, from_as_submod]
        expected_outputs = [
            {"pandas" : {
                "module_aliases" : set(),
                 "func_mapping" : {"Dataframe" : "Dataframe"},
                 "functions" : set(["Dataframe"])},
            "sklearn" : {
                "module_aliases" : set(),
                "func_mapping" : {},
                "functions" : set()},
            },
            {"pandas" : {
                "module_aliases" : set(),
                 "func_mapping" : {"Dataframe": "Df"},
                 "functions" : set(["Df"])},
             "sklearn" : {
                "module_aliases" : set(),
                "func_mapping" : {},
                "functions" : set()},
            },
            {"pandas" : {
                "module_aliases" : set(),
                "func_mapping" : {},
                "functions" : set()},
             "sklearn" : {
                "module_aliases" : set(),
                "func_mapping" : {"BallTree" : "BallTree"},
                "functions" : set(["BallTree"])},
            },
            {"pandas" : {
                "module_aliases" : set(),
                "func_mapping" : {},
                "functions" : set()},
             "sklearn" : {
                "module_aliases" : set(),
                "func_mapping" : {"BallTree": "bt"},
                "functions" : set(["bt"])},
            },]
        for import_stmnt, expected in zip(import_stmnts, expected_outputs):

            env = prompter.AnalysisEnvironment()
            env.cell_exec(import_stmnt)
            self._compare_alias_env(env, expected)

    def test_newdata(self):
        """
        test whether importation of new data is properly noted
        """
        formats = ["csv", "fwf", "json", "html", "clipboard", "excel",
                   "hdf", "feather", "parquet", "orc", "msgpack", "stata",
                   "sas", "spss", "pickle", "sql", "gbq"]

        function_names = ["read_"+fmt for fmt in formats]
        import_stmnt = "import pandas as pd\n"
        calls = [import_stmnt+"df = pd."+fn+"(filename.csv)" for fn in function_names]

        expected_imports = {
            "pandas" :
                {"module_aliases" : set(["pd"]),
                 "func_mapping" : {},
                 "functions" : set()},
            "sklearn" :
                {"module_aliases" : set(),
                 "func_mapping" : {},
                 "functions" : set()},
            }

        expected = [{"df": {"source": "filename.csv", "format" : fmt}} for fmt in formats]

        for call, data in zip(calls, expected):

            env = prompter.AnalysisEnvironment()
            env.cell_exec(call)

            self._compare_alias_env(env, expected_imports)
            self._compare_new_data_env(env, data)

    def _compare_new_data_env(self, env, data_entries):
        """
        are the expected source nodes noted in the environment?
        """
        for var_name in data_entries.keys():
            self.assertTrue(var_name in env.entry_points,
                            "{0} not in {1}".format(var_name, str(env.entry_points)))
            self.assertEqual(data_entries[var_name], env.entry_points[var_name])

    def test_newdata_importfrom(self):
        """
        test from pandas import read_*
        """

        formats = ["csv", "fwf", "json", "html", "clipboard", "excel",
                   "hdf", "feather", "parquet", "orc", "msgpack", "stata",
                   "sas", "spss", "pickle", "sql", "gbq"]

        function_names = ["read_"+fmt for fmt in formats]

        calls = ["from pandas import "+fn+"\ndf = "+fn+"(filename.csv)" for fn in function_names]

        expected = [{"df": {"source": "filename.csv", "format" : fmt}} for fmt in formats]

        for call, data in zip(calls, expected):

            env = prompter.AnalysisEnvironment()
            env.cell_exec(call)

            self._compare_new_data_env(env, data)

    def test_newdata_import_alias(self):
        """
        test from pandas import read_* as func_name
        """
        formats = ["csv", "fwf", "json", "html", "clipboard", "excel",
                   "hdf", "feather", "parquet", "orc", "msgpack", "stata",
                   "sas", "spss", "pickle", "sql", "gbq"]

        function_names = ["read_"+fmt for fmt in formats]

        calls = ["from pandas import "+fn+" as gimme_data\ndf = gimme_data(filename.csv)"
                 for fn in function_names]

        expected = [{"df": {"source": "filename.csv", "format" : fmt}} for fmt in formats]

        for call, data in zip(calls, expected):

            env = prompter.AnalysisEnvironment()
            env.cell_exec(call)

            self._compare_new_data_env(env, data)

    def test_newdata_slicing_chaining(self):
        """
        test x = read_csv()[d]...[y], or x = read_csv().select()
        """

        slicing_cell = """from pandas import read_fwf\ndf = read_fwf(filename)[0:6,5:10]"""
        chaining_cell = """import pandas as pd\n"""+\
            """df = pd.read_csv(filename).between_time("2016-05-01","2020-01-01")"""

        expected_slicing = {"df" : {"source": "filename", "format" : "fwf"}}
        expected_chaining = {"df" : {"source": "filename", "format" : "csv"}}

        env = prompter.AnalysisEnvironment()
        env.cell_exec(slicing_cell)
        self._compare_new_data_env(env, expected_slicing)

        env = prompter.AnalysisEnvironment()
        env.cell_exec(chaining_cell)
        self._compare_new_data_env(env, expected_chaining)

    def test_multiple_new_datasources(self):
        """
        make sure that we get both data sources in when multiple
        read_* calls are made
        """
        multiple_cell = "import pandas as pd\n"+\
            """df = pd.read_csv(filename).between_time("2016-05-01","2020-01-01")\n""" +\
            """df2 = pd.read_csv(filename).between_time("2016-05-02","2020-02-01")\n"""

        expected_multiple = {"df" : {"source": "filename", "format" : "csv"},
                             "df2" : {"source" : "filename", "format" : "csv"}}

        env = prompter.AnalysisEnvironment()
        env.cell_exec(multiple_cell)
        self._compare_new_data_env(env, expected_multiple)

    def test_reassign_newdata(self):
        """
        df = read_csv(file1) df = read_csv(file2), should only have 1
        df = read_csv(file) df = x + 1
        also del df
        """

        reassign_cell = "from pandas import read_csv\n" +\
            """df = read_csv(filename).between_time("2016-05-01","2020-01-01")\n"""+\
            """df = read_csv(filename).between_time("2016-05-02","2020-02-01")\n"""

        expected_reassign = {"df" : {"source": "filename", "format" : "csv"}}

        env = prompter.AnalysisEnvironment()
        env.cell_exec(reassign_cell)
        self._compare_new_data_env(env, expected_reassign)

        newvar_cell = """
            from pandas import read_csv 
            df = read_csv(filename).between_time("2016-05-01","2020-01-01")
            df = 12 + 6
            """

        expected_newvar = {"df" : {"source": "filename", "format" : "csv"}}

        env = prompter.AnalysisEnvironment()
        env.cell_exec(newvar_cell)
        self._compare_new_data_env(env, expected_newvar)

        delete_cell = """
            from pandas import read_csv 
            df = read_csv(filename).between_time("2016-05-01","2020-01-01")
            del df
            """

        expected_delete = {"df" : {"source": "filename", "format" : "csv"}}

        env = prompter.AnalysisEnvironment()
        env.cell_exec(delete_cell)
        self._compare_new_data_env(env, expected_delete)

if __name__ == "__main__":
    unittest.main()
