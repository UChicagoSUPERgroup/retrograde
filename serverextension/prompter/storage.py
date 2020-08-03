"""
storage.py contains utilities for storing responses from the 
notebook application and tracking development of particular cells over time
"""
import sqlite3
import os
import dill

from datetime import datetime, timedelta
from mysql.connector import connect

from .config import DB_DIR, DB_NAME


class DbHandler(object):

    def __init__(self, dirname = DB_DIR, dbname = DB_NAME):

        db_path_resolved = os.path.expanduser(dirname)

        self.user="default"

        if os.path.isdir(db_path_resolved) and os.path.isfile(db_path_resolved+dbname):

            self._conn = sqlite3.connect(db_path_resolved+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._conn.row_factory = sqlite3.Row
            self._cursor = self._conn.cursor()
        else:
            if not os.path.isdir(db_path_resolved):
               os.mkdir(db_path_resolved)
            self._conn = sqlite3.connect(db_path_resolved+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._conn.row_factory = sqlite3.Row
            self._cursor = self._conn.cursor()
            self._init_db()

    def _init_db(self):
        """
        add the tables to the new database
        """
        self._cursor.execute("""
            CREATE TABLE cells(user TEXT, kernel TEXT, id TEXT PRIMARY KEY, contents TEXT, num_exec INT, last_exec TIMESTAMP);
            """)
        self._cursor.execute("""
            CREATE TABLE versions(user TEXT, kernel TEXT, id TEXT, version INT, time TIMESTAMP, contents TEXT, exec_ct INT, PRIMARY KEY(id, contents));
            """)

        # the table w/ the data entities in it
        # TODO: start here (needed to implement other methods for getting changes etc working
        self._cursor.execute("""
            CREATE TABLE data(user TEXT, kernel TEXT, cell TEXT, version INT, source TEXT, name TEXT, PRIMARY KEY(name, version, source));
            """)
        # columns for each data entry
        self._cursor.execute("""
            CREATE TABLE columns(source TEXT, 
                                 user TEXT,
                                 version INT, 
                                 name TEXT, 
                                 col_name TEXT,
                                 type TEXT,
                                 size INT,
                                 PRIMARY KEY(source, version, name, col_name));
            """)

        self._cursor.execute("""
            CREATE TABLE namespaces(user TEXT, msg_id TEXT PRIMARY KEY, exec_num INT, time TIMESTAMP, code TEXT, namespace BLOB)
            """)
        self._conn.commit()
    def get_code(self, kernel_id, cell_id):
        """return the contents of the cell, none if does not exist"""
        result = self._cursor.execute(
            """SELECT contents FROM cells WHERE id = ? AND kernel = ? AND user = ?""", (cell_id, kernel_id, self.user)).fetchall()
        if len(result) != 0:
            return result[0]["contents"]
        return None

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
        #inserting new value into cells
        try:
          #if the cell already exists, this will raise an integrity error
          self._cursor.execute("""INSERT INTO cells(id, contents, num_exec, last_exec, kernel, user)
                 VALUES (?,?,?,?,?,?);""", (cell['cell_id'], cell['contents'], 1, datetime.now(), cell["kernel"], self.user))
        except sqlite3.IntegrityError as e:
          #value for cell already exists in cells, so update as needed
          self._cursor.execute("""UPDATE cells
                 SET contents = ?, num_exec = num_exec + 1, last_exec = ?, kernel = ?
                 WHERE id = ? AND user = ?;""", (cell['contents'], datetime.now(), cell["kernel"], cell['cell_id'], self.user))

        #this is adding the versions row if it doesnt exist. If it 
        #does exist then do nothing.
        try:
          self._cursor.execute("""INSERT INTO versions(id, version, time, contents, exec_ct, user)
                 VALUES (?,?,?,?,?,?);""", (cell['cell_id'], 1, datetime.now(),cell['contents'], cell["exec_ct"], self.user))
        except sqlite3.IntegrityError as e:
          #As I understand the documentation, nothing happens if a version
          #already exists. 
          pass
        self._conn.commit()
        pass

    def recover_ns(self, msg_id):
        """return the namespace under the msg_id entry"""
        return self._cursor.execute("""
                SELECT namespace FROM namespaces WHERE msg_id = ? AND user = ? 
            """, (msg_id, self.user)).fetchall()[0]

    def recent_ns(self):
        """return the most recently logged namespace"""
        return self._cursor.execute("""
            SELECT * FROM namespaces WHERE user = ? ORDER BY time DESC LIMIT 1
        """, (self.user,)).fetchall()[0]

    def link_cell_to_ns(self, exec_ct, time, delta=timedelta(seconds=5)):
        """given an entry in the versions table, find matching namespace entry"""
        results = self._cursor.execute("""
            SELECT * FROM namespaces WHERE exec_num = ? AND user = ? AND time BETWEEN ? AND ? 
        """, (exec_ct, self.user, time - delta, time + delta)).fetchall()
        
        if len(results) == 0:
            return None
        if len(results) == 1:
            return results[0]        
        else:
            raise sqlite3.IntegrityError("Multiple namespaces in range")  
    def find_data(self, data):
        """look up if data entry exists, return if exists, None if not"""
        # note that will *not* compare columns

        source = data["source"]
        name = data["name"] 
 
        data_versions = self._cursor.execute("""
            SELECT 
                kernel,
                source,
                name,
                version,
                user
            FROM 
                data 
            WHERE source = ? AND name = ? AND user = ? 
            ORDER BY version""", (source, name, self.user)).fetchall()

        if data_versions == []: return None
        return data_versions

    def add_data(self, data, version):
        """add data to data entry table"""
        """data format is 
            {"kernel" : kernel_id, 
             "cell" : cell id, 
             "source" : source filename, 
             "name" : data var name, 
             "columns" : column dict}
            should not be called without checking whether data
            already in database, via find_data
        """

        kernel = data["kernel"]
        cell = data["cell"]
        source = data["source"]
        name = data["name"]

        columns = data["columns"]

        self._cursor.execute("""
            INSERT INTO data(kernel, cell, version, source, name, user)
            VALUES (?, ?, ?, ?, ?, ?)""", (kernel, cell, version, source, name, self.user))

        cols = [(source, 
                 self.user,
                 version, 
                 name, # nb notebook name
                 col, # column's name
                 str(columns[col]["type"]), 
                 columns[col]["size"]) for col in columns.keys()]
        self._cursor.executemany("""
            INSERT INTO columns VALUES (?, ?, ?, ?, ?, ?, ?) 
            """, cols)
        self._conn.commit()
    def find_model(self, name, info, kernel_id):
        """look up if model entry exists, return if exists, None if not"""
        # TODO
    def add_model(self, name, info, kernel_id):
        """add model to model entry table"""
        # TODO

class RemoteDbHandler(DbHandler):
    """when we want the database to be remote"""
    def __init__(self, db_name, user, password, host):
        self._conn = connect(host=host, user=user, 
                             password=password, database=db_name)
        self._cursor = self._conn.cursor(buffer=True, dictionary=True)
        self.user = user

def load_dfs(ns):
    ns_dict = dill.loads(ns["namespace"])
    return {k : dill.loads(v) for k,v in ns_dict["_forking_kernel_dfs"].items()}
