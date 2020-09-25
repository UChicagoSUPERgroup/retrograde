import unittest
from ast import parse
from context import prompter

class TestDataFrameVisitor(unittest.TestCase):

    def test_newdata_slicing_chaining(self):
        """
        test x = read_csv()[d]...[y], or x = read_csv().select()
        """

        slicing_cell = """from pandas import read_fwf\ndf = read_fwf(filename)[0:6,5:10]"""
        chaining_cell = """import pandas as pd\n"""+\
            """df = pd.read_csv(filename).between_time("2016-05-01","2020-01-01")"""

        df_names = set(["df"])
        pd_alias = prompter.Aliases("pandas")
        visitor = prompter.DataFrameVisitor(df_names, pd_alias)

        visitor.visit(parse(slicing_cell))
        self.assertEqual(visitor.info, {"df" : {"source" : "filename", "format" : "fwf"}})

        visitor = prompter.DataFrameVisitor(df_names, pd_alias)
        visitor.visit(parse(chaining_cell))

        self.assertEqual(visitor.info, {"df" : {"source" : "filename", "format" : "csv"}})

    def test_transfer(self):

        snippet=\
        """import pandas as pd\n"""+\
        """pd.read_csv("filename")\n"""+\
        """df = pd.read_csv("filename1")\n"""+\
        """X = df[["a", "b"]].to_numpy()\n"""+\
        """y = do_stuff(df)"""

        df_names = set(["df", "y"])
        pd_alias = prompter.Aliases("pandas")
        visitor = prompter.DataFrameVisitor(df_names, pd_alias)
        visitor.visit(parse(snippet))

        self.assertEqual(visitor.info, {"df" : {"source" : "filename1", "format" : "csv"}})
        
        ptr_set = set(["df"])
        self.assertEqual(visitor.assign_map["X"], ptr_set)

    def test_magic_func(self):
        snippet=\
        """df = make_df(filename)\n"""+\
        """X = do_tfm(df, trgt)"""
        df_names = set(["df", "y"])
        pd_alias = prompter.Aliases("pandas")
        visitor = prompter.DataFrameVisitor(df_names, pd_alias)
        visitor.visit(parse(snippet))

        self.assertEqual(visitor.assign_map["X"], set(["df", "trgt", "do_tfm"]))
        self.assertEqual(visitor.info, {})

