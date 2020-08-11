"""
test the DbHandler methods
"""

import unittest
import sqlite3
import os
from context import prompter
#import prompter


class TestDBMethods(unittest.TestCase):

    def setUp(self):

        self.TEST_DB_DIR = "./"
        self.TEST_DB_NAME = "cellstest.db"
        self.db = prompter.DbHandler(dirname=self.TEST_DB_DIR, dbname=self.TEST_DB_NAME)
        self.conn = sqlite3.connect(self.TEST_DB_DIR + self.TEST_DB_NAME)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def test_init(self):
        self.cursor.execute(
            """
            SELECT
                name
            FROM
                sqlite_master
            WHERE
                type = 'table' AND
                name NOT LIKE 'sqlite_%';
            """)
        tables = self.cursor.fetchall() 
        
        self.assertEqual(len(tables), 5, "found tables {0}".format(tables))
        table_names = [t[0] for t in tables]

        self.assertTrue("cells" in table_names)
        self.assertTrue("versions" in table_names)

    #tests if changing text creates new version (key constant)
    def test_add_entry_versions(self):
        self.db.add_entry({"kernel" : "TEST-1234", 'contents': '1+1+1=2', 'cell_id': 'some_key_1', "exec_ct" : 1})
        self.db.add_entry({"kernel" : "TEST-1234", 'contents': '1+1=4', 'cell_id': 'some_key_1', "exec_ct" : 2})
        self.cursor.execute(
            """
            SELECT
                contents,version
            FROM
                versions
            WHERE
                id = 'some_key_1';
            """)
        tables = self.cursor.fetchall() 
        self.assertEqual(len(tables), 2)

        self.assertTrue({"contents" : "1+1+1=2","version" : 1} == tables[0], tables)
        self.assertTrue({"contents":"1+1=4", "version" : 2} == tables[1], tables)

    #tests if identical executions increment num_exec
    #and create no new versions
    def test_add_entry_reexec(self):
        self.db.add_entry({"kernel" : "TEST-1234", 'contents': 'hello friends', 'cell_id': 'a_key_1', "exec_ct" : 1})
        self.db.add_entry({"kernel" : "TEST-1234", 'contents': 'hello friends', 'cell_id': 'a_key_1', "exec_ct" : 2})
        self.cursor.execute(
            """
            SELECT
                id, num_exec
            FROM
                cells
            WHERE
                id = 'a_key_1';
            """)
        tables = self.cursor.fetchall() 
        self.assertEqual(len(tables), 1)

        self.assertTrue(tables[0]["num_exec"] == 2, "tables {0}".format(tables))
        self.cursor.execute(
            """
            SELECT
                *
            FROM
                versions
            WHERE
                id = 'a_key_1';
            """)
        tables_versions = self.cursor.fetchall() 
        self.assertEqual(len(tables_versions), 1)

    def test_add_data(self):
        # test adding data
        data = {
            "kernel" : "TESTKERNEL-01234",
            "cell" : "TESTCELL",
            "source": "test.csv",
            "name" : "test_df",
            "columns" : {
               "age" : {"type" : "int", "size" : 10},
               "gender" : {"type" : "bool", "size" : 10},
               "SAT" : {"type" : "int", "size" : 12},
               "v1_stat" : {"type" : "obj", "size" : 32} 
             }
        }

        self.db.add_data(data, 1)
        self.cursor.execute(
            """
            SELECT 
                *
            FROM
                data
            """)

        add_result = self.cursor.fetchall()
        self.assertEqual(len(add_result), 1)
         
        self.cursor.execute(
            """
            SELECT
                *
            FROM
                columns
            WHERE
                name = 'test_df' AND
                version = 1 AND
                source = 'test.csv'
            """)
        col_result = self.cursor.fetchall()
        self.assertEqual(len(col_result), 4)
        test_names = [r["col_name"] for r in col_result]

        for col_name in data["columns"].keys():
            self.assertTrue(col_name in test_names, "{0} not in {1}\nraw = {2}".format(col_name, test_names, col_result))

    def test_find_data(self):
        data = {
            "kernel" : "TESTKERNEL-01234",
            "cell" : "TESTCELL",
            "source": "test.csv",
            "name" : "test_df",
            "columns" : {
               "age" : {"type" : "int", "size" : 10},
               "gender" : {"type" : "bool", "size" : 10},
               "SAT" : {"type" : "int", "size" : 12},
               "v1_stat" : {"type" : "obj", "size" : 32} 
             }
        }
        self.db.add_data(data, 1)

        self_result = self.db.find_data(data)
        
        self.assertEqual(len(self_result), 1)
        self.assertEqual(self_result[0]["kernel"], "TESTKERNEL-01234")
        self.assertEqual(self_result[0]["source"], "test.csv")
        self.assertEqual(self_result[0]["version"], 1) 
        
    def test_update_data(self):
        data = {
            "kernel" : "TESTKERNEL-01234",
            "cell" : "TESTCELL",
            "source": "test.csv",
            "name" : "test_df",
            "columns" : {
               "age" : {"type" : "int", "size" : 10},
               "gender" : {"type" : "bool", "size" : 10},
               "SAT" : {"type" : "int", "size" : 12},
               "v1_stat" : {"type" : "obj", "size" : 32} 
             }
        }

        self.db.add_data(data, 1)

        new_data = {
            "kernel" : "TESTKERNEL-01234",
            "cell" : "TESTCELL-01",
            "source": "test.csv",
            "name" : "test_df",
            "columns" : {
               "age" : {"type" : "int", "size" : 10},
               "gender" : {"type" : "bool", "size" : 10},
               "SAT" : {"type" : "int", "size" : 12},
               "v1_stat" : {"type" : "obj", "size" : 32},
               "v2_stat" : {"type" : "float", "size" : 12}
             }
        }
    
        new_version = self.db.find_data(new_data)[0]["version"]
        self.db.add_data(new_data, new_version + 1)

        self.cursor.execute(
            """
            SELECT
                *
            FROM
                columns
            """)
        col_result = self.cursor.fetchall()
        self.assertEqual(len(col_result), 9)

    def tearDown(self):
        if os.path.exists(self.TEST_DB_DIR+self.TEST_DB_NAME):
            os.remove(self.TEST_DB_DIR+self.TEST_DB_NAME)

if __name__ == "__main__":
    unittest.main()
