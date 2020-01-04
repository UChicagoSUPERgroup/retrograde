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

        try:
            conn = sqlite3.connect(db_path_resolved+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._cursor = conn.cursor()

        except sqlite3.OperationalError:
            if not os.path.isdir(DB_DIR):
               os.mkdir(db_path_resolved)
            conn = sqlite3.connect(db_path_resolved+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._cursor = conn.cursor()
            self._init_db()

    def _init_db(self):
        """
        add the tables to the new database
        """
        self._cursor.execute("""
            CREATE TABLE cells(id TEXT PRIMARY KEY, contents TEXT, num_exec INT, last_exec TIMESTAMP)
            """)
        self._cursor.execute("""
            CREATE TABLE versions(id TEXT, version INT, time TIMESTAMP, contents TEXT, PRIMARY KEY(id, version))
        """)

        self._cursor.commit()
