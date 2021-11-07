import unittest
import pandas as pd

from ast import parse
from context import prompter

from sklearn.linear_model import LinearRegression

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

        snippet_ast = parse(snippet)

        visitor.visit(snippet_ast)

        self.assertEqual(visitor.info, {"df" : {"source" : "filename1", "format" : "csv"}})
        
        ptr_set = set([snippet_ast.body[3].value])
        self.assertEqual(visitor.assign_map["X"], ptr_set)

    def test_magic_func(self):
        snippet=\
        """df = make_df(filename)\n"""+\
        """X = do_tfm(df, trgt)"""
        df_names = set(["df", "y"])
        pd_alias = prompter.Aliases("pandas")
        visitor = prompter.DataFrameVisitor(df_names, pd_alias)

        snippet_ast = parse(snippet)

        visitor.visit(snippet_ast)

        ptr_set = set([snippet_ast.body[1].value])

        self.assertEqual(visitor.assign_map["X"], ptr_set)
        self.assertEqual(visitor.info, {"df" : {}})

    def test_dropna(self):
        snippet_1 =\
        """import pandas as pd\n"""+\
        """df = pd.read_csv("filename")\n"""

        snippet_2 = """loans = df.dropna()"""

        df_names = set(["df", "loans"])
        pd_alias = prompter.Aliases("pandas")
        visitor = prompter.DataFrameVisitor(df_names, pd_alias)
        visitor.visit(parse(snippet_1))
        visitor.visit(parse(snippet_2))

        self.assertTrue("loans" in visitor.info, visitor.info)

    def test_train_test_split(self):
        snippet =\
        """X_test, X_train, y_test, y_train = train_test_split(X,y,split=0.2)"""

        df_names = set(["X_test", "X_train", "y_test", "y_train", "X", "y"])
        pd_alias = prompter.Aliases("pandas")
        visitor = prompter.DataFrameVisitor(df_names, pd_alias)
        visitor.visit(parse(snippet))

        print(visitor.info)       
class TestModelVisitor(unittest.TestCase):

    def test_simple(self):
        snippet=\
        """lr = LinearRegression()\n"""+\
        """lr.fit(X, y)\n"""+\
        """lr.score(X,y)"""

        test_df = pd.DataFrame(
                    {
                        "a": [0,1,2,3],
                        "b": [4,5,6,7],
                        "c": [8,9,10,11]
                    })

        namespace = {
            "X" : test_df[["a","b"]],
            "y" : test_df["c"],
            "lr": LinearRegression().fit(test_df[["a", "b"]], test_df["c"])} 

        expected = {"lr" : {"x" : ["a", "b"], "y" : ["c"], "x_df": "X", "y_df" : "y"}}

        pd_alias = prompter.Aliases("pandas")

        df_visit = prompter.DataFrameVisitor(set(["X", "y"]), pd_alias)
        df_visit.visit(parse(snippet))
        
        visitor = prompter.ModelScoreVisitor(pd_alias, ["lr"], namespace, df_visit.assign_map)

        visitor.visit(parse(snippet))
        self.assertEqual(visitor.models, expected, "Actual {0}, expected {1}".format(visitor.models, expected))

    def test_intercell(self):

        snippet_0=\
        """lr = LinearRegression()\n"""
        snippet_1="""lr.fit(X, y)"""

        test_df = pd.DataFrame(
                    {
                        "a": [0,1,2,3],
                        "b": [4,5,6,7],
                        "c": [8,9,10,11]
                    })

        namespace = {
            "X" : test_df[["a","b"]],
            "y" : test_df["c"],
            "lr": LinearRegression().fit(test_df[["a", "b"]], test_df["c"])} 

        expected_0 = {"lr" : {}}
        expected_1 = {"lr" : {"x" : ["a", "b"], "y" : ["c"], "y_df" : "y", "x_df" : "X"}}

        pd_alias = prompter.Aliases("pandas")

        df_visit = prompter.DataFrameVisitor(set(["X", "y"]), pd_alias)
        df_visit.visit(parse(snippet_0))
        assign_map = df_visit.assign_map
 
        visitor = prompter.ModelScoreVisitor(pd_alias, ["lr"], namespace, assign_map)
        visitor.visit(parse(snippet_0))
            
        self.assertEqual(visitor.models, expected_0)
        
        df_visit = prompter.DataFrameVisitor(set(["X", "y"]),pd_alias) 
        df_visit.visit(parse(snippet_1))
        assign_map.update(df_visit.assign_map)

        visitor = prompter.ModelScoreVisitor(pd_alias, ["lr"], namespace, assign_map)
        visitor.visit(parse(snippet_1))
        self.assertEqual(visitor.models, expected_1)

    def test_call_chain(self):

        snippet=\
        """X_train = X.dropna().to_numpy()\n"""+\
        """lr = LinearRegression().fit(X_train, y)"""

        test_df = pd.DataFrame(
                    {
                        "a": [0,1,2,3],
                        "b": [4,5,6,7],
                        "c": [8,9,10,11]
                    })

        X_train = test_df[["a", "b"]].dropna().to_numpy()

        namespace = {
            "X" : test_df[["a", "b"]],
            "X_train" : X_train,
            "y" : test_df["c"],
            "lr": LinearRegression().fit(X_train, test_df["c"])} 
       
        expected = {"lr" : {"x" : ["a", "b"], "y" : ["c"], "y_df" : "y", "x_df" : "X"}}
        
        pd_alias = prompter.Aliases("pandas")

        df_visit = prompter.DataFrameVisitor(set(["X", "y"]), pd_alias)
        df_visit.visit(parse(snippet))

        visitor = prompter.ModelScoreVisitor(pd_alias, ["lr"], namespace, df_visit.assign_map)
        visitor.visit(parse(snippet))

        self.assertEqual(visitor.models, expected)

    def test_index_rows(self):

        snippet_rows=\
        """X = test_df[["a", "b"]]\n"""+\
        """y = test_df["c"]\n"""+\
        """lr = LinearRegression().fit(X[:3], y[:3])\n"""

        test_df = pd.DataFrame(
                    {
                        "a": [0,1,2,3],
                        "b": [4,5,6,7],
                        "c": [8,9,10,11]
                    })

        namespace = {
            "X" : test_df[["a", "b"]],
            "y" : test_df["c"],
            "lr": LinearRegression().fit(test_df[["a", "b"]][:3], test_df["c"][:3])} 
       
        expected = {"lr" : {"x" : ["a", "b"], "y" : ["c"]}}

        df_visit = prompter.DataFrameVisitor(set(["X", "y"]), prompter.Aliases("pandas"))
        df_visit.visit(parse(snippet_rows))
        visitor = prompter.ModelScoreVisitor(["lr"], namespace, df_visit.assign_map)

        visitor.visit(parse(snippet_rows))
        
        self.assertEqual(visitor.models, expected)

    def test_index_rows_cols(self):
 
        snippet_rows_cols=\
        """lr = LinearRegression().fit(test_df[["a", "b"]][:3], test_df["c"][:3])"""

        test_df = pd.DataFrame(
                    {
                        "a": [0,1,2,3],
                        "b": [4,5,6,7],
                        "c": [8,9,10,11]
                    })

        namespace = {
            "test_df" : test_df,
            "lr": LinearRegression().fit(test_df[["a", "b"]][:3], test_df["c"][:3])} 
       
        expected = {"lr" : {"x" : ["a", "b"], "y" : ["c"]}}

        df_visit = prompter.DataFrameVisitor(set(["test_df"]), prompter.Aliases("pandas"))
        df_visit.visit(parse(snippet_rows_cols))

        visitor = prompter.ModelScoreVisitor(["lr"], namespace, df_visit.assign_map)

        visitor.visit(parse(snippet_rows_cols))
        
        self.assertEqual(visitor.models, expected)

    def test_index_cols(self):
        snippet_cols=\
        """lr = LinearRegression().fit(test_df[["a", "b"]], test_df["c"])\n"""

        test_df = pd.DataFrame(
                    {
                        "a": [0,1,2,3],
                        "b": [4,5,6,7],
                        "c": [8,9,10,11]
                    })

        namespace = {
            "test_df" : test_df,
            "lr": LinearRegression().fit(test_df[["a", "b"]], test_df["c"])} 
       
        expected = {"lr" : {"x" : ["a", "b"], "y" : ["c"]}}
        pd_alias = prompter.Aliases("pandas")

        df_visit = prompter.DataFrameVisitor(set(["test_df"]), pd_alias)
        df_visit.visit(parse(snippet_cols))

        visitor = prompter.ModelScoreVisitor(pd_alias, ["lr"], namespace, df_visit.assign_map)

        visitor.visit(parse(snippet_cols))
        
        self.assertEqual(visitor.models, expected)
        
    def test_iloc(self): # test loc and iloc

        test_df = pd.DataFrame(
                    {
                        "a": [0,1,2,3],
                        "b": [4,5,6,7],
                        "c": [8,9,10,11]
                    })

        expected = {"lr" : {"x" : ["a", "b"], "y" : ["c"]}}

        snippet_loc =\
        """lr = LinearRegression().fit(test_df.loc[:,"a":"b"], test_df.iloc[:,2])"""
        
        namespace = {
            "test_df" : test_df,
            "lr": LinearRegression().fit(test_df.loc[:,"a":"b"], test_df.iloc[:,2])} 

        df_visit = prompter.DataFrameVisitor(set(["test_df"]), prompter.Aliases("pandas"))
        df_visit.visit(parse(snippet_loc))

        visitor = prompter.ModelScoreVisitor(["lr"], namespace, df_visit.assign_map)
        visitor.visit(parse(snippet_loc))
        
        self.assertEqual(visitor.models, expected)

        snippet_iloc =\
        """lr = LinearRegression().fit(test_df.iloc[::1, [0, 1]], test_df.iloc[:, [2]])"""

        namespace = {
            "test_df" : test_df,
            "lr": LinearRegression().fit(test_df.iloc[::1, [0,1]], test_df.iloc[:,[2]])} 
        
        
        df_visit = prompter.DataFrameVisitor(set(["test_df"]), prompter.Aliases("pandas"))
        df_visit.visit(parse(snippet_loc))

        visitor = prompter.ModelScoreVisitor(["lr"], namespace, df_visit.assign_map)
        visitor.visit(parse(snippet_iloc))
        
        self.assertEqual(visitor.models, expected)

    def test_drop(self):
        # n.b. should have as argument i.e. fit(X.dropna("test")
        # also dropna

        test_df = pd.DataFrame(
                    {
                        "a": [0,1,2,3],
                        "b": [4,5,6,7],
                        "c": [8,9,10,11],
                        "d": [None, None, None, None]
                    })
        snippet_drop =\
        """lr = LinearRegression()\n"""+\
        """lr.fit(test_df.drop(["c", "d"], axis=1), test_df.drop(columns=["a", "b", "d"]))"""

        snippet_dropna =\
        """lr = LinearRegression()\n"""+\
        """lr.fit(test_df.dropna(axis=1)[["a", "b"]], test_df.dropna(subset=["c"])["c"])"""

        
        namespace = {
            "test_df" : test_df,
            "lr": LinearRegression().fit(test_df.drop(["c", "d"], axis=1), test_df.drop(columns=["a", "b", "d"]))} 
        expected = {"lr" : {"x" : ["a", "b"], "y" : ["c"]}}


        df_visit = prompter.DataFrameVisitor(set(["test_df"]), prompter.Aliases("pandas"))
        df_visit.visit(parse(snippet_drop))

        visitor = prompter.ModelScoreVisitor(["lr"], namespace, df_visit.assign_map)
        visitor.visit(parse(snippet_drop))

        self.assertEqual(visitor.models, expected)
        
        namespace = {
            "test_df" : test_df,
            "lr": LinearRegression().fit(test_df.dropna(axis=1)[["a", "b"]], test_df.dropna(subset=["a", "b", "c"])["c"])} 
        df_visit = prompter.DataFrameVisitor(set(["test_df"]), prompter.Aliases("pandas"))
        df_visit.visit(parse(snippet_dropna))

        visitor = prompter.ModelScoreVisitor(["lr"], namespace, df_visit.assign_map)
        visitor.visit(parse(snippet_dropna))
        self.assertEqual(visitor.models, expected)

    def test_bool_index(self):
        """testing boolean indexing/selection"""

        snippet_var =\
        """lr = LinearRegression()\n"""+\
        """var = [True for _ in range(len(test_df))]\n"""+\
        """lr.fit(test_df[["a", "b"], var], test_df[test_df.columns.isin(["c"]), var])"""

        expected = {"lr" : {"x_cols" : ["a", "b"], "y_cols" : ["c"]}}

        visitor = prompter.ModelScoreVisitor(pd_alias, model_names, namespace, assign_map)
        visitor.visit(parse(snippet_loc))
        
        self.assertEqual(visitor.models, expected)
         
    def test_to_numpy(self):
        snippet =\
        """lr = LinearRegression()\n"""+\
        """lr.fit(test_df[["a", "b"]].to_numpy(), test_df["c"].to_numpy())"""

        expected = {"lr" : {"x_cols" : ["a", "b"], "y_cols" : ["c"]}}
        visitor = prompter.ModelScoreVisitor()
        visitor.visit(parse(snippet_loc))
        
        self.assertEqual(visitor.models, expected)

    def test_col_ref(self):
        # passing y as x.colname
        snippet =\
        """lr = LinearRegression()\n"""+\
        """lr.fit(test_df[["a", "b"]], test_df.c)"""

        expected = {"lr" : {"x_cols" : ["a", "b"], "y_cols" : ["c"]}}
        visitor = prompter.ModelScoreVisitor()
        visitor.visit(parse(snippet_loc))
        
        self.assertEqual(visitor.models, expected)
