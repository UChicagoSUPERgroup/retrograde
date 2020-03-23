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
        
        self.assertEqual(len(tables), 2)
        table_names = [t[0] for t in tables]

        self.assertTrue("cells" in table_names)
        self.assertTrue("versions" in table_names)

    #tests if changing text creates new version (key constant)
    def test_add_entry_versions(self):
        self.db.add_entry({'contents': '1+1+1=2', 'id': 'some_key_1'})
        self.db.add_entry({'contents': '1+1=4', 'id': 'some_key_1'})
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
        self.db.add_entry({'contents': 'hello friends', 'id': 'a_key_1'})
        self.db.add_entry({'contents': 'hello friends', 'id': 'a_key_1'})
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

    def tearDown(self):
        if os.path.exists(self.TEST_DB_DIR+self.TEST_DB_NAME):
            os.remove(self.TEST_DB_DIR+self.TEST_DB_NAME)

if __name__ == "__main__":
    unittest.main()
