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
        
        self.assertEqual(len(tables), 4)
        table_names = [t[0] for t in tables]

        self.assertTrue("cells" in table_names)
        self.assertTrue("versions" in table_names)

    #tests if changing text creates new version (key constant)
    def test_add_entry_versions(self):
        self.db.add_entry({'contents': '1+1+1=2', 'cell_id': 'some_key_1'})
        self.db.add_entry({'contents': '1+1=4', 'cell_id': 'some_key_1'})
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
        table_names = [t[0] for t in tables]
        self.assertTrue([("1+1+1=2",1)] == tables[0])
        self.assertTrue([("1+1=4",1)] == tables[1])

    #tests if identical executions increment num_exec
    #and create no new versions
    def test_add_entry_versions(self):
        self.db.add_entry({'contents': 'hello friends', 'cell_id': 'a_key_1'})
        self.db.add_entry({'contents': 'hello friends', 'cell_id': 'a_key_1'})
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
        table_names = [t[1] for t in tables]
        self.assertTrue(tables[0][1] == 2)
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
         
        col_result = self.cursor.execute(
            """
            SELECT
                *
            FROM
                columns
            WHERE
                name = 'test_df' AND
                version = 1 AND
                source = 'test.csv'
            """).fetchall()
        self.assertEqual(len(col_result), 4)
        test_names = [r[3] for r in col_result]

        for col_name in data["columns"].keys():
            self.assertTrue(col_name in test_names, "{0} not in {1}".format(col_name, test_names))

#    def test_find_data(self):
#    def test_update_data(self):

    def tearDown(self):
        if os.path.exists(self.TEST_DB_DIR+self.TEST_DB_NAME):
            os.remove(self.TEST_DB_DIR+self.TEST_DB_NAME)

if __name__ == "__main__":
    unittest.main()
