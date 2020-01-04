"""
test the DbHandler methods
"""

import unittest
import sqlite3
import os

class TestDBMethods(unittest.TestCase):

    def setUp(self):

        self.TEST_DB_DIR = "./test/"
        self.TEST_DB_NAME = "cellstest.db"

    def test_init(self):

        db = prompter.storage.DbHandler(dirname=TEST_DB_DIR, dbname=TEST_DB_NAME)
        
        conn = sqlite3.connect(TEST_DB_DIR + TEST_DB_NAME)
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
        table_names = [t["name"] for t in tables]

        self.assertTrue("cells" in table_names)
        self.assertTrue("versions" in table_names)

    def tearDown(self):

        os.remove(self.TEST_DB_DIR+self.TEST_DB_NAME)
        os.rmdir(self.TEST_DB_DIR)

if __name__ == "__main__":
    unittest.main()
