"""
test the heuristics methods
"""

import unittest
import pandas as pd
import os

from context import prompter
from unittest.mock import Mock, MagicMock
from jupyter_client.manager import start_new_kernel
from _queue import Empty

class TestKernelHooks(unittest.TestCase):
    """
    Test whether heuristics for data detections work
    """
    
    def setUp(self):

        nbapp = Mock()
        self.kernel_manager, self.client = start_new_kernel()

        nbapp.kernel_manager = self.kernel_manager
        nbapp.kernel_manager.get_kernel = MagicMock(return_value = self.kernel_manager)

        nbapp.web_app.kernel_locks = {"TEST" : Mock()}
        nbapp.web_app.kernel_locks["TEST"].lock = MagicMock()
        nbapp.web_app.kernel_locks["TEST"].release = MagicMock()

        nbapp.log.debug = print
        nbapp.log.info = print
        nbapp.log.error = print

        self.env = prompter.AnalysisEnvironment(nbapp, "TEST")

        # create test csv
        d = pd.DataFrame({"gender" : ["M", "F", "M", "F", "F"],
                          "age" : [26, 57, 49, 20, 30],
                          "grade" : [.9, .8, .7, .6, .5],
                          "height": [136, 260, 145, 235, 78],
                          "score" : [187, 170, 178, 169, 173]})
        d.to_csv("test.csv")

    def tearDown(self):

        self.client.shutdown()
        if self.kernel_manager.is_alive(): self.kernel_manager.shutdown_kernel(now=True)
        if os.path.exists("test.csv"): os.remove("test.csv")

    def test_code_exec(self):

        test_code = """print("hello world")\n"""
        output = self.env._execute_code(test_code, timeout=5)
        self.assertEqual("hello world\n", output)

    def test_get_model(self):
        model_cell = """import pandas as pd\n"""+\
            """from sklearn.linear_model import LinearRegression\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = LinearRegression()\n"""

        self.client.execute(model_cell) # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST", "TESTCELL")
        
        self.assertTrue("lr" in self.env.models)

    def test_get_model_alias(self):
        model_cell = """import pandas as pd\n"""+\
            """from sklearn.linear_model import LinearRegression as LR\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = LR()"""
        
        self.client.execute(model_cell) # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST", "TESTCELL")
        
        self.assertTrue("lr" in self.env.models)

    def test_get_model_module(self):
        model_cell = """import pandas as pd\n"""+\
            """import sklearn.linear_model\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = sklearn.linear_model.LinearRegression()"""

        self.client.execute(model_cell) # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST", "TESTCELL")
        
        self.assertTrue("lr" in self.env.models)

    def test_get_model_module_alias(self):
        model_cell = """import pandas as pd\n"""+\
            """import sklearn.linear_model as lm\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = lm.LinearRegression()"""

        self.client.execute(model_cell) # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST", "TESTCELL")
        
        self.assertTrue("lr" in self.env.models)

    def test_model_fit(self):
        model_cell = """import pandas as pd\n"""+\
            """import sklearn.linear_model as lm\n"""+\
            """df = pd.read_csv("test.csv")\n"""+\
            """lr = lm.LinearRegression()\n"""+\
            """lr.fit(df.iloc[:,2:5].to_numpy(), df.iloc[:,5].to_numpy())"""

        expected_models = {"lr": 
                {"train" : {
                    "features" : ["age", "grade", "height"],
                    "labels" : ["score"]},
                 "cell" : "TESTCELL",
                }}
 
        self.client.execute(model_cell) # need to execute code this way to avoid issues with message queueing
        self.env.cell_exec(model_cell, "TEST", "TESTCELL")
       
        self.assertEqual(self.env.models, expected_models)

    def _client_execute(self, code):
        """execute code in external client to simulate nb execution"""
        msg_id = self.client.execute(code)
#        reply = self.client.get_shell_msg(msg_id, timeout=1)
        io_msg_content = self.client.get_iopub_msg(timeout=2)["content"]

        if "execution_state" in io_msg_content and io_msg_content["execution_state"] == "idle":
            return "no output"
        while True:
            temp = io_msg_content
            try:
                io_msg_content = self.client.get_iopub_msg(timeout=2)["content"]
                if "execution_state" in io_msg_content and\
                    io_msg_content["execution_state"] == "idle":
                    break
            except Empty:
                break
        return temp

    def test_flow(self):
        data_cell = "import pandas as pd\n"+\
                     "from sklearn.linear_model import LinearRegression\n"+\
                     "df = pd.read_csv(\"./test/test.csv\")\n"+\
                     "df.head()"
        model_cell = "X = df[[\"age\", \"juv_fel_count\", \"priors_count.1\"]].to_numpy()\n"+\
                     "y = df[\"two_year_recid\"].to_numpy()\n"+\
                     "lr = LinearRegression()\n"+\
                     "lr.fit(X, y)"
        output = self._client_execute(data_cell)
#        print(output)
        self.env.cell_exec(data_cell, "TEST", "TESTCELL")

        output = self._client_execute(model_cell)
#        print(output)
        self.env.cell_exec(model_cell, "TEST", "TESTCELL")
        expected_models = {"lr": 
                {"train" : {
                    "features" : ["age", "juv_fel_count", "priors_count.1"],
                    "labels" : ["two_year_recid"]},
                 "cell" : "TESTCELL",
                }}

        expected_data = {"df" : {"source" : "./test/test.csv", "format" : "csv", "cell" : "TESTCELL"}}

        self.assertEqual(expected_data, self.env.entry_points)
        self.assertEqual(expected_models, self.env.models)

if __name__ == "__main__":
    unittest.main()
