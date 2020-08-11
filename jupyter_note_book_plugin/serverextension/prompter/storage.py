"""
storage.py contains utilities for storing responses from the 
notebook application and tracking development of particular cells over time
"""
import sqlite3
import os
import dill

from datetime import datetime, timedelta
from mysql.connector import connect
from mysql.connector.errors import IntegrityError
from _mysql_connector import MySQLInterfaceError

from .config import DB_DIR, DB_NAME, table_query

SQL_CMDS = {
  "GET_CODE" : """SELECT contents FROM cells WHERE id = ? AND kernel = ? AND user = ?""",
  "INSERT_CELLS" : """INSERT INTO cells(id, contents, num_exec, last_exec, kernel, user) VALUES (?,?,?,?,?,?);""",
  "UPDATE_CELLS" : """UPDATE cells SET contents = ?, num_exec = num_exec + 1, last_exec = ?, kernel = ? WHERE id = ? AND user = ?;""",
  "INSERT_VERSIONS" : """INSERT INTO versions(user, kernel, id, version, time, contents, exec_ct) VALUES (?,?,?,?,?,?,?);""",
  "RECOVER_NS" : """SELECT namespace FROM namespaces WHERE msg_id = ? AND user = ?""",
  "RECENT_NS" : """SELECT * FROM namespaces WHERE user = ? ORDER BY time DESC LIMIT 1""",
  "LINK_CELL" : """SELECT * FROM namespaces WHERE exec_num = ? AND user = ? AND  code_hash = ?""",
  "DATA_VERSIONS" : """SELECT kernel, source, name, version, user FROM data WHERE source = ? AND name = ? AND user = ? ORDER BY version""",
  "ADD_DATA" : """INSERT INTO data(kernel, cell, version, source, name, user) VALUES (?, ?, ?, ?, ?, ?)""",
  "ADD_COLS" : """INSERT INTO columns VALUES (?, ?, ?, ?, ?, ?, ?)""",
  "GET_VERSIONS" : """SELECT contents, version FROM versions WHERE kernel = ? AND id = ? AND user = ? ORDER BY version DESC LIMIT 1"""
}

class DbHandler(object):

    def __init__(self, dirname = DB_DIR, dbname = DB_NAME):

        db_path_resolved = os.path.expanduser(dirname)

        self.user="default"
        self.cmds = SQL_CMDS
 
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
        
        self._cursor.executescript(table_query)
        self._conn.commit()

    def get_code(self, kernel_id, cell_id):
        """return the contents of the cell, none if does not exist"""
        result = self._cursor.execute(self.cmds["GET_CODE"], (cell_id, kernel_id, self.user)).fetchall()
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
          self._cursor.execute(self.cmds["INSERT_CELLS"], (cell['cell_id'], cell['contents'], 1, datetime.now(), cell["kernel"], self.user))
        except (sqlite3.IntegrityError, IntegrityError) as e:
          #value for cell already exists in cells, so update as needed
          self._cursor.execute(self.cmds["UPDATE_CELLS"], (cell['contents'], datetime.now(), cell["kernel"], cell['cell_id'], self.user))

        #this is adding the versions row if it doesnt exist. If it 
        #does exist then do nothing.
        try:

          self._cursor.execute(self.cmds["GET_VERSIONS"], (cell["kernel"], cell["cell_id"], self.user))
          results = self._cursor.fetchone()

          if results and results["contents"] != cell["contents"]:
            self._cursor.execute(self.cmds["INSERT_VERSIONS"], (self.user, cell["kernel"], cell['cell_id'], 
                                                                results["version"]+1, datetime.now(), cell['contents'], 
                                                                cell["exec_ct"]))
          if not results:
            self._cursor.execute(self.cmds["INSERT_VERSIONS"], (self.user, cell["kernel"], cell['cell_id'], 
                                                                1, datetime.now(), cell['contents'], 
                                                                cell["exec_ct"]))
        except (sqlite3.IntegrityError, IntegrityError) as e:
          #As I understand the documentation, nothing happens if a version
          #already exists. 
          pass
        self._conn.commit()
        pass

    def recover_ns(self, msg_id):
        """return the namespace under the msg_id entry"""
        return self._cursor.execute(self.cmds["RECOVER_NS"], (msg_id, self.user)).fetchall()[0]

    def recent_ns(self):
        """return the most recently logged namespace""" 
        self._cursor.execute(self.cmds["RECENT_NS"], (self.user,))
        return self._cursor.fetchall()[0]

    def link_cell_to_ns(self, exec_ct, contents):
        """given an entry in the versions table, find matching namespace entry"""
        self._cursor.execute(self.cmds["LINK_CELL"],
                (exec_ct, self.user, hash(contents)))
        results = self._cursor.fetchall() 
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
 
        self._cursor.execute(self.cmds["DATA_VERSIONS"], 
                             (source, name, self.user))
        data_versions = self._cursor.fetchall()

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

        self._cursor.execute(self.cmds["ADD_DATA"], (kernel, cell, version, source, name, self.user))

        cols = [(source, 
                 self.user,
                 version, 
                 name, # nb notebook name
                 col, # column's name
                 str(columns[col]["type"]), 
                 columns[col]["size"]) for col in columns.keys()]
        self._cursor.executemany(self.cmds["ADD_COLS"], cols)
        self._conn.commit()
        
    def close(self):
        self._cursor.close()
        self._conn.close()

    def find_model(self, name, info, kernel_id):
        """look up if model entry exists, return if exists, None if not"""
        # TODO
    def add_model(self, name, info, kernel_id):
        """add model to model entry table"""
        # TODO

class RemoteDbHandler(DbHandler):
    """when we want the database to be remote"""
    def __init__(self, database, db_user, password, host, nb_user):
        self._conn = connect(host=host, user=db_user, 
                             password=password, database=database)
        self._cursor = self._conn.cursor(buffered=True, dictionary=True)
        self.user = nb_user
        self.cmds = {k : v.replace("?","%s") for k, v in SQL_CMDS.items()}

def load_dfs(ns):
    ns_dict = dill.loads(ns["namespace"])
    return {k : dill.loads(v) for k,v in ns_dict["_forking_kernel_dfs"].items()}
