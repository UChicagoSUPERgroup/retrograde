"""
we need a global session manager which handles
routing of code analyses and handles failures
"""
import os

import mysql.connector

from ..storage import DbHandler, RemoteDbHandler, load_dfs
from ..config import remote_config


class DatabaseManager:
    def __init__(self, nbapp):
        try:
            remote_config["nb_user"] = os.getenv("JP_PLUGIN_USER")
            if not remote_config["nb_user"]: remote_config["nb_user"] = "DEFAULT_USER"
            nbapp.log.debug("[MANAGER] user is {0}".format(remote_config["nb_user"]))
            self.db = RemoteDbHandler(**remote_config)
            nbapp.log.debug("[MANAGER] db local cursor: {0}".format(self.db._local_cursor))
        except mysql.connector.Error as e:
            nbapp.log.warning("[MANAGER] Unable to connect to remote db, creating local backup. Error {0}".format(e))
            self.db = DbHandler()
        self._nb = nbapp
        self.db.addTrack("START", "Started up database tracking")

    def getDb(self):
        return self.db