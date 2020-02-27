"""
test the heuristics methods
"""

import unittest
import pandas as pd
import os

from context import prompter
from unittest.mock import Mock, MagicMock
from jupyter_client.manager import start_new_kernel

class TestKernelHooks(unittest.TestCase):
    """
    Test whether heuristics for data detections work
    """
    
    def setUp(self):

        nbapp = Mock()
        kl_mock = Mock()
        self.kernel_manager, self.client = start_new_kernel()

        kl_mock.client = MagicMock(return_value = self.client)
        nbapp.get_kernel = MagicMock(return_value = kl_mock) 
        nbapp.log = print
        self.env = prompter.AnalysisEnvironment(nbapp)

        # create test csv
        d = pd.DataFrame({"gender" : ["M", "F", "M", "F", "F"],
                          "age" : [26, 57, 49, 20, 30],
                          "grade" : [.9, .8, .7, .6, .5],
                          "height": [136, 260, 145, 235, 78],
                          "score" : [187, 170, 178, 169, 173]})
        d.to_csv("test.csv")

    def tearDown(self):
        self.kernel_manager.shutdown_kernel()
        if os.path.exists("test.csv"): os.remove("test.csv")

    def test_code_exec(self):

        test_code = """print("hello world")\n"""
        output = self.env._execute_code(test_code, "TEST", timeout=5)
        self.assertEqual("hello world\n", output)

    def test_get_model(self):
        model_cell = """import pandas as pd\n"""+\
            """from sklearn.linear_model import LinearRegression\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = LinearRegression()\n"""

        self.env._execute_code(model_cell, "TEST") # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST")
        
        self.assertTrue("lr" in self.env.models)

    def test_get_model_alias(self):
        model_cell = """import pandas as pd\n"""+\
            """from sklearn.linear_model import LinearRegression as LR\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = LR()"""
        
        self.env._execute_code(model_cell, "TEST") # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST")
        
        self.assertTrue("lr" in self.env.models)

    def test_get_model_module(self):
        model_cell = """import pandas as pd\n"""+\
            """import sklearn.linear_model\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = sklearn.linear_model.LinearRegression()"""

        self.env._execute_code(model_cell, "TEST") # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST")
        
        self.assertTrue("lr" in self.env.models)

    def test_get_model_module_alias(self):
        model_cell = """import pandas as pd\n"""+\
            """import sklearn.linear_model as lm\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = lm.LinearRegression()"""

        self.env._execute_code(model_cell, "TEST") # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST")
        
        self.assertTrue("lr" in self.env.models)

    def test_model_fit(self):
        model_cell = """import pandas as pd\n"""+\
            """import sklearn.linear_model as lm\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = lm.LinearRegression()\n"""+\
            """lr.fit(df.iloc[:,2:5].to_numpy(), df.iloc[:,5].to_numpy())"""

        expected_models = [{"lr": 
                {"type" : "LinearRegression",
                 "train_cols" : ["age", "grade", "height"],
                 "test_cols" : ["score"],
                 "avail_cols" : ["age", "gender", "grade", "height", "score"], 
                }}]
 
        resp = self.env._execute_code(model_cell, "TEST") # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST")
        
        self.assertEqual(self.env.models, expected_models)

if __name__ == "__main__":
    unittest.main()
