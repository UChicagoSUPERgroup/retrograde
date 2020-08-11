"""
test the remote db handler
"""

import unittest
import mysql.connector
import os

from context import prompter 
from test_storage import TestDBMethods

class TestRemoteDB(TestDBMethods):

    def setUp(self):

        user_config = {"database" : "test_jupyter",
                       "db_user" : "test_user",
                       "nb_user" : "test_uid",
                       "password" : "test",
                       "host" : "localhost"}

        test_config = {"database" : "test_jupyter",
                       "user" : "prompter_tester",
                       "password" : "test",
                       "host" : "localhost"}

        self.db = prompter.RemoteDbHandler(**user_config)

        self.conn = mysql.connector.connect(**test_config)

        self.cursor = self.conn.cursor(buffered=True, dictionary=True)

        self.cursor.execute("DROP TABLE IF EXISTS cells;")
        self.cursor.execute("DROP TABLE IF EXISTS versions;")
        self.cursor.execute("DROP TABLE IF EXISTS data;")
        self.cursor.execute("DROP TABLE IF EXISTS columns;")
        self.cursor.execute("DROP TABLE IF EXISTS namespaces;")

        query = prompter.table_query.split(";")
        for q in query:
            self.cursor.execute(q)
        self.conn.commit()

    def tearDown(self):

        self.db.close()
        self.cursor.execute("DROP TABLE IF EXISTS cells;")
        self.cursor.execute("DROP TABLE IF EXISTS versions;")
        self.cursor.execute("DROP TABLE IF EXISTS data;")
        self.cursor.execute("DROP TABLE IF EXISTS columns;")
        self.cursor.execute("DROP TABLE IF EXISTS namespaces;")

        self.cursor.close()
        self.conn.close()

    def test_init(self):

        self.cursor.execute("""SHOW TABLES;""")
        tables = self.cursor.fetchall()
        self.assertEqual(len(tables), 5, "found tables {0}".format(tables))

if __name__ == "__main__":
    unittest.main()
