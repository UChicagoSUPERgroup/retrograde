"""
storage.py contains utilities for storing responses from the 
notebook application and tracking development of particular cells over time
"""
from datetime import datetime, timedelta

import json
import sqlite3
import os
import dill

from mysql.connector import connect
from mysql.connector.errors import IntegrityError

from .config import DB_DIR, DB_NAME, table_query

SQL_CMDS = {
  "GET_CODE" : """SELECT contents FROM cells WHERE id = ? AND kernel = ? AND user = ?""",
  "INSERT_CELLS" : """INSERT INTO cells(id, contents, num_exec, last_exec, kernel, user, metadata) VALUES (?,?,?,?,?,?,?);""",
  "UPDATE_CELLS" : """UPDATE cells SET contents = ?, num_exec = num_exec + 1, last_exec = ?, kernel = ?, metadata = ? WHERE id = ? AND user = ?;""",
  "INSERT_VERSIONS" : """INSERT INTO versions(user, kernel, id, version, time, contents, exec_ct) VALUES (?,?,?,?,?,?,?);""",
  "DATA_VERSIONS" : """SELECT kernel, source, name, version, user FROM data WHERE source = ? AND name = ? AND user = ? AND kernel = ? ORDER BY version""",
  "DATA_VERSIONS_NO_SOURCE" : """SELECT kernel, source, name, version, user FROM data WHERE name = ? AND user = ? AND kernel = ? ORDER BY version""",
  "ADD_DATA" : """INSERT INTO data(kernel, cell, version, source, name, user) VALUES (?, ?, ?, ?, ?, ?)""",
  "ADD_COLS" : """INSERT INTO columns(user, kernel, name, version, col_name, type, size) VALUES (?, ?, ?, ?, ?, ?, ?)""",
  "GET_VERSIONS" : """SELECT contents, version FROM versions WHERE kernel = ? AND id = ? AND user = ? ORDER BY version DESC LIMIT 1""",
  "GET_COLS" : """SELECT * FROM columns WHERE user = ? AND col_name = ?""",
  "GET_ALL_COLS" : """SELECT * FROM columns WHERE user = ? AND kernel = ? AND name = ? AND version = ?""",
  "GET_UNMARKED" : """SELECT col_name, name, version, type, size FROM columns WHERE kernel = ? AND user = ? AND name = ? AND version = ? AND checked = FALSE""",
  "UPDATE_COL_TYPES" : """UPDATE columns SET fields = ?, is_sensitive = ?, user_specified = ?, checked = ? WHERE user = ? AND kernel = ? AND name = ? AND version = ? AND col_name = ?""",
  "GET_MAX_VERSION" : """SELECT name,MAX(version) FROM data WHERE user = ? AND kernel = ? GROUP BY name""",
  "STORE_RESP" : """INSERT INTO notifications(kernel, user, cell, resp, exec_ct) VALUES (?, ?, ?, ?, ?)""",
  "GET_RESPS" : """SELECT cell, resp FROM notifications WHERE kernel = ? AND user = ?""",
}

LOCAL_SQL_CMDS = { # cmds that will always get executed locally
  "MAKE_NS_TABLE" : """CREATE TABLE namespaces(msg_id TEXT PRIMARY KEY, exec_num INT, code TEXT, time TIMESTAMP, namespace BLOB)""",
  "RECOVER_NS" : """SELECT namespace FROM namespaces WHERE msg_id = ?""",
  "RECENT_NS" : """SELECT * FROM namespaces ORDER BY time DESC LIMIT 1""",
  "LINK_CELL" : """SELECT * FROM namespaces WHERE exec_num = ?""",
}

class DbHandler:
    """
    DbHandler class handles connections between sqlite3 or MySQL database
    Provides single place for updating database entries
    """
    def __init__(self, dirname = DB_DIR, dbname = DB_NAME):

        db_path_resolved = os.path.expanduser(dirname)

        self.user="default"
        self.cmds = SQL_CMDS
        self.cmds.update(LOCAL_SQL_CMDS)
 
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
        self._cursor.execute(self.cmds["MAKE_NS_TABLE"])
        self._conn.commit()

    def get_code(self, kernel_id, cell_id):
        """return the contents of the cell, none if does not exist"""

        self.renew_connection()
        self._cursor.execute(self.cmds["GET_CODE"], (cell_id, kernel_id, self.user))
        result = self._cursor.fetchall()

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

        self.renew_connection()
        try:
          #if the cell already exists, this will raise an integrity error
          self._cursor.execute(self.cmds["INSERT_CELLS"], (cell['cell_id'], cell['contents'], 1, datetime.now(), cell["kernel"], self.user, cell['metadata']))
        except (sqlite3.IntegrityError, IntegrityError) as _:
          #value for cell already exists in cells, so update as needed
          self._cursor.execute(self.cmds["UPDATE_CELLS"], (cell['contents'], datetime.now(), cell["kernel"], cell['metadata'], cell['cell_id'], self.user))

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
        except (sqlite3.IntegrityError, IntegrityError) as _:
          #As I understand the documentation, nothing happens if a version
          #already exists. 
          pass
        self._conn.commit()

    def recover_ns(self, msg_id, curs=None):
        """return the namespace under the msg_id entry"""
        if not curs: 
            curs = self._cursor
        curs.execute(self.cmds["RECOVER_NS"], (msg_id,))
        return curs.fetchall()[0]

    def recent_ns(self, curs=None):
        """return the most recently logged namespace""" 
        if not curs: 
            curs = self._cursor
        curs.execute(self.cmds["RECENT_NS"])
        return curs.fetchall()[0]

    def link_cell_to_ns(self, exec_ct, contents, cell_time, curs = None):
        """given an entry in the versions table, find matching namespace entry"""
        # pylint: disable=unused-argument
        # disable bc I don't want to mess up other calls
        if not curs: 
            curs = self._cursor

        delta = timedelta(seconds=3) 

        #self.renew_connection()
        curs.execute(self.cmds["LINK_CELL"], (exec_ct,))
        results = curs.fetchall()
       
        results = [r for r in results if r["time"] > (cell_time - delta)]  
        results = [r for r in results if r["time"] < (cell_time + delta)]
        
        if len(results) == 0:
            return None
        if len(results) == 1:
            return results[0]        
        raise sqlite3.IntegrityError("Multiple namespaces in range")  

    def check_add_data(self, entry_point):
        """
        check if entry_point data is updated, compare columns as well,
        then update
        
        entry_point is dict with attributes source, name, kernel, columns : {col_name : {"size", "type"}}
        """ 
        data_versions = self.find_data(entry_point)

        if data_versions:
            # if column name, type and size do not match any version
            for version in data_versions:
                entry_matched = True
                columns = self.get_columns(entry_point["kernel"], entry_point["name"], version["version"])
                names = [col["col_name"] for col in columns]
                
                if len(names) == len(entry_point["columns"]) and set(names).issubset(set(entry_point["columns"])):
                    for col in columns:
                        if entry_point["columns"][col["col_name"]]["type"] != col["type"]:
                            entry_matched = False
                        if entry_point["columns"][col["col_name"]]["size"] != col["size"]:
                            entry_matched = False
                else:
                    entry_matched = False
                if entry_matched:
                    return version["version"]

            max_version = max([v["version"] for v in data_versions])

            if "source" not in entry_point:

                max_data_version = [v for v in data_versions if v["version"] == max_version][0]
                entry_point["source"] = max_data_version["source"] 

            self.add_data(entry_point, max_version+1) 
            return max_version + 1
        else:
            # data is new, add data and columns to database
            self.add_data(entry_point, 1)
            return 1

    def find_data(self, data):
        """look up if data entry exists, return if exists, None if not"""
        # note that will *not* compare columns
        if "source" in data.keys():
            source = data["source"]
            name = data["name"] 
            kernel = data["kernel"] 

            self.renew_connection() 
            self._cursor.execute(self.cmds["DATA_VERSIONS"], 
                                 (source, name, self.user, kernel))
            data_versions = self._cursor.fetchall()

            if data_versions == []: 
                return None
            return data_versions

        name = data["name"]
        kernel = data["kernel"] 

        self.renew_connection()
        self._cursor.execute(self.cmds["DATA_VERSIONS_NO_SOURCE"], (name, self.user, kernel))
        data_versions = self._cursor.fetchall()

        if data_versions == []:
            return None
        return data_versions

    def add_data(self, data, version):
        """add data to data entry table
        data format is 
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

        self.renew_connection()

        self._cursor.execute(self.cmds["ADD_DATA"], (kernel, cell, version, source, name, self.user))

        cols = [(self.user,
                 kernel,
                 name, # nb notebook name
                 version, 
                 col, # column's name
                 str(columns[col]["type"]), 
                 columns[col]["size"]) for col in columns.keys()]
        self._cursor.executemany(self.cmds["ADD_COLS"], cols)
        self._conn.commit()
    
    def get_columns(self, kernel, df_name, version):
        """get columns from df_name"""
        self.renew_connection()

        self._cursor.execute(self.cmds["GET_ALL_COLS"], (self.user, kernel, df_name, version))

        return self._cursor.fetchall()

    def get_unmarked_columns(self, kernel):
        """
        return columns that have not been scanned for whether they are sensitive
        or not.
        
        format is {df_name : [col_names]}
    
        """
        self.renew_connection()
        self._cursor.execute(self.cmds["GET_MAX_VERSION"], (self.user, kernel))

        max_versions = self._cursor.fetchall()
        unmarked_cols = {}

        for max_version in max_versions:

            name = max_version["name"]
            version = max_version["MAX(version)"]
            self._cursor.execute(self.cmds["GET_UNMARKED"], (kernel, self.user, name, version))
            results = self._cursor.fetchall()
            
            unmarked_cols[name] = [res["col_name"] for res in results]

        return unmarked_cols

    def update_marked_columns(self, kernel, input_data):
        """
        update columns
        
        input_data is a dictionary mapping df_name -> {col_name : { "sensitive" : "user_designated" : "fields" : }}
        """
        self.renew_connection()
        query_tuples = [] 

        self._cursor.execute(self.cmds["GET_MAX_VERSION"], (self.user, kernel))
        version_dict = {}

        # turn it into a dictionary
        for resp in self._cursor.fetchall():

            key = (self.user, kernel, resp["name"])
            value = resp["MAX(version)"]

            if key in version_dict:
                raise Exception("Duplicate keys {0}, {1}, {2}".format(key, value, version_dict[key]))
            version_dict[key] = value
        for df_name, columns in input_data.items():
               
            # want to get the max value for each column
            version = version_dict[(self.user, kernel, df_name)]
            for col_name,info in columns.items():
                query_params = (info["fields"], info["is_sensitive"], info["user_specified"], True, 
                                self.user, kernel, df_name, version, col_name)
                query_tuples.append(query_params)
        self._cursor.executemany(self.cmds["UPDATE_COL_TYPES"], query_tuples)
        self._conn.commit()
 
    def store_response(self, kernel_id, cell_id, exec_ct, response):
        """store response in database"""
        self.renew_connection()

        self._cursor.execute(self.cmds["STORE_RESP"], (kernel_id, self.user, cell_id, json.dumps(response), exec_ct))
        self._conn.commit()

    def get_responses(self, kernel_id):
        """
        get responses from the database
        returns dictionary with keys of cell ids and values of a list of responses
        """
        self.renew_connection()        
        self._cursor.execute(self.cmds["GET_RESPS"], (kernel_id, self.user))
        results = self._cursor.fetchall()

        responses = {}

        for elt in results:
            try: 
                responses[elt["cell"]].append(json.loads(elt["resp"]))
            except KeyError:
                responses[elt["cell"]] = [json.loads(elt["resp"])]

        return responses
    def close(self):
        """close the connection to the database"""
        self._cursor.close()
        self._conn.close()

    def renew_connection(self):
        """renew the connection to the database"""
        # pylint: disable=no-self-use
        return True # only relevant when db is remote

class RemoteDbHandler(DbHandler):
    """when we want the database to be remote"""
    # pylint: disable=too-many-arguments,super-init-not-called
    def __init__(self, database, db_user, password, host, nb_user):
        self._conn = connect(host=host, user=db_user, 
                             password=password, database=database)
        self._cursor = self._conn.cursor(buffered=True, dictionary=True)
        self.user = nb_user
        self.cmds = {k : v.replace("?","%s") for k, v in SQL_CMDS.items()}
        self.cmds.update(LOCAL_SQL_CMDS)
        self._init_local_db()

    def _init_local_db(self, dbname=DB_NAME, dirname=DB_DIR):
        db_path_resolved = os.path.expanduser(dirname)

#        print("creating local database at {0}".format(db_path_resolved+dbname))

        if os.path.isdir(db_path_resolved) and os.path.isfile(db_path_resolved+dbname): 
            self._local_conn = sqlite3.connect(db_path_resolved+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._local_conn.row_factory = sqlite3.Row
            self._local_cursor = self._local_conn.cursor()
        else:
            if not os.path.isdir(db_path_resolved):
               os.mkdir(db_path_resolved)
            self._local_conn = sqlite3.connect(db_path_resolved+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._local_conn.row_factory = sqlite3.Row
            self._local_cursor = self._local_conn.cursor()
            self._local_cursor.execute(self.cmds["MAKE_NS_TABLE"])

    def recover_ns(self, msg_id, curs=None):
        return super().recover_ns(msg_id, curs=self._local_cursor)
    def recent_ns(self, curs=None):
        return super().recent_ns(curs=self._local_cursor)
    def link_cell_to_ns(self, exec_ct, contents, cell_time,curs=None):
        return super().link_cell_to_ns(exec_ct, contents, cell_time, curs=self._local_cursor)

    def renew_connection(self):

        if not self._conn.is_connected():
            self._conn.reconnect(attempts=2, delay=1)

        if self._conn.is_connected():
            self._cursor = self._conn.cursor(buffered=True, dictionary=True)
            return True
        return False

def load_dfs(ns):
    """take namespace and load dataframe objects from reserved variable name"""
    ns_dict = dill.loads(ns["namespace"])
    return {k : dill.loads(v) for k,v in ns_dict["_forking_kernel_dfs"].items()}
