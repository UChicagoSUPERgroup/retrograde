"""
storage.py contains utilities for storing responses from the 
notebook application and tracking development of particular cells over time
"""
import sqlite3
import os

from .config import DB_DIR, DB_NAME

class DbHandler(object):

    def __init__(self, dirname = DB_DIR, dbname = DB_NAME):

        db_path_resolved = os.path.expanduser(dirname)

        if os.path.isdir(db_path_resolved) and os.path.isfile(db_path_resolved+dbname):

            self._conn = sqlite3.connect(db_path_resolved+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._cursor = self._conn.cursor()
        else:
            if not os.path.isdir(db_path_resolved):
               os.mkdir(db_path_resolved)
            self._conn = sqlite3.connect(db_path_resolved+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._cursor = self._conn.cursor()
            self._init_db()

    def _init_db(self):
        """
        add the tables to the new database
        """
        self._cursor.execute("""
            CREATE TABLE cells(id TEXT PRIMARY KEY, contents TEXT, num_exec INT, last_exec TIMESTAMP)
            """)
        self._cursor.execute("""
            CREATE TABLE versions(id TEXT, version INT, time TIMESTAMP, contents TEXT, PRIMARY KEY(id, text))
        """)
        self._conn.commit()

    def add_entry(self, cell):
        """
         TODO: should take cell, and add it to the database
               a cell is a python object produced by the 
               tornado.escape.json_decode call in the CodeExecHandler.post
               method.

               The cell is an object with an 'id' field (a unique 
               alphanumeric identifier for that code cell), and a 'contents'
               field, which is a string containing the code in the cell.

               At most two things need to happen to add the cell to the database.
               
               if the cell is new (as determined by the id), then we need to insert a 
               new entry into the cells table.

               If the cell is not new, then we need to increment the num_exec field, 
               update the last_exec field, and replace the contents field with
               the most recent cell contents, if they have changed.

               In both cases, we will need to see if the cell is a new version or not.
               If the cell is not a new version (the code has changed), then we 
               will need to create a new entry in the versions table
        """

        pass
