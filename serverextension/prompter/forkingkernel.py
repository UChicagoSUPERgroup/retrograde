"""
this kernel does not itself fork, but enables one to create a "forked"
kernel based on the state of the kernel at a previous point.

It does this by updating a table associating msg_ids with a version 
of the namespace in the cells database. 
"""

import sqlite3
import os
import dill

import pandas as pd

from ipykernel.kernelbase import Kernel
from ipykernel.ipkernel import IPythonKernel
from inspect import ismodule

from .config import DB_DIR, DB_NAME

class ForkingKernel(IPythonKernel):

    impelementation = "Forkable IPython"
    implementation_version = "0.1"
    banner = "IPython kernel that allows forking"
    
    language_info = IPythonKernel.language_info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connect_db()

    def _connect_db(self, dirname=DB_DIR, dbname=DB_NAME):
        db_path = os.path.expanduser(dirname)                        
        if os.path.isdir(db_path) and os.path.isfile(db_path+dbname):

            self._conn = sqlite3.connect(db_path+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._cursor = self._conn.cursor()
        else:
            if not os.path.isdir(db_path):
               os.mkdir(db_path)
            self._conn = sqlite3.connect(db_path+dbname, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._conn.row_factory = sqlite3.Row
            self._cursor = self._conn.cursor()
            self._add_table()

    def _add_table(self):
        result = self._cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='namespaces'
        """).fetchall()
        if len(result) == 0:
            self._cursor.execute("""
                CREATE TABLE namespaces(msg_id TEXT PRIMARY KEY, namespace BLOB)
                """)
            self._conn.commit()

    def _handle_ns(self):
        """render objects into serializable format as needed""" 
        better_ns = {}

        boiler_plate_keys = [ # defs that are just part of kernel exec env
            "__name__", "__doc__", "__package__", "__loader__",
            "__spec__", "_ih", "_oh", "_dh", "In", "Out", 
            "_", "__", "___", "_i", "_ii", "_iii", "_i1", "_exit_code"]
       
        for k, v in self.shell.user_ns.items():
            if k in boiler_plate_keys:
                continue
            if type(v) == pd.DataFrame:
                better_ns[k] = dill.dumps(v)
            elif not dill.detect.badobjects(v):
                better_ns[k] = v
            else:
                self.log.debug(
                    "[FORKINGKERNEL] could not pickle {0}, problem items {1}".format(k, dill.detect.baditems(v)))
        return better_ns
 
    def _cache_ns(self):
      
        msg_id = self._parent_header["msg_id"]
#        print(dill.detect.baditems(locals())) # In testing, only object not pickleable is kernel object, which is fine
#        bad_items = dill.detect.baditems(self.shell.user_ns)
#        censored_ns = {k : v for k,v in self.shell.user_ns.items() if v not in bad_items}
        relevant_ns = self._handle_ns() 
        ns = sqlite3.Binary(dill.dumps(relevant_ns))
        self._cursor.execute("""
            INSERT INTO namespaces(msg_id, namespace) VALUES (?, ?)""", (msg_id, ns))
        self._conn.commit()
 
    def do_execute(self, code, silent, store_history=True, 
                   user_expressions=None, allow_stdin=False):
        result = super().do_execute(code, silent, store_history=store_history,
                                    user_expressions=user_expressions, allow_stdin=allow_stdin)
        self._cache_ns()
        return result
