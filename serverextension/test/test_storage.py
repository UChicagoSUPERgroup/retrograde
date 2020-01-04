"""
test the DbHandler methods
"""

import unittest
import sqlite3
import os
from context import prompter

class TestDBMethods(unittest.TestCase):

    def setUp(self):

        self.TEST_DB_DIR = "./"
        self.TEST_DB_NAME = "cellstest.db"

    def test_init(self):

        db = prompter.DbHandler(dirname=self.TEST_DB_DIR, dbname=self.TEST_DB_NAME)
        
        conn = sqlite3.connect(self.TEST_DB_DIR + self.TEST_DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                name
            FROM
                sqlite_master
            WHERE
                type = 'table' AND
                name NOT LIKE 'sqlite_%';
            """)
        tables = cursor.fetchall() 
        
        self.assertEqual(len(tables), 2)
        table_names = [t[0] for t in tables]

        self.assertTrue("cells" in table_names)
        self.assertTrue("versions" in table_names)

    def tearDown(self):
        if os.path.exists(self.TEST_DB_DIR+self.TEST_DB_NAME):
            os.remove(self.TEST_DB_DIR+self.TEST_DB_NAME)

if __name__ == "__main__":
    unittest.main()
