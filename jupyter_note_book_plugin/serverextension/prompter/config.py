DB_DIR = "~/.promptml/"
DB_NAME = "cells.db"

# Table query creates the database tables, it should be exactly the contents of
# make_tables.sql 

table_query = """

CREATE TABLE IF NOT EXISTS cells(
    user TEXT, 
    kernel TEXT, 
    id VARCHAR(255) PRIMARY KEY, 
    contents TEXT, 
    num_exec INT, 
    last_exec TIMESTAMP
);

CREATE TABLE IF NOT EXISTS versions(
    user TEXT, 
    kernel TEXT, 
    id VARCHAR(255), 
    version INT, 
    time TIMESTAMP, 
    contents TEXT, 
    exec_ct INT, 
    PRIMARY KEY(id, version));

CREATE TABLE IF NOT EXISTS data(
    user TEXT, 
    kernel TEXT, 
    cell TEXT, 
    version INT, 
    source VARCHAR(255), 
    name VARCHAR(255), 
    PRIMARY KEY(name, version, source));

CREATE TABLE IF NOT EXISTS columns(
    source VARCHAR(255), 
    user TEXT,
    version INT, 
    name VARCHAR(255), 
    col_name VARCHAR(255),
    type TEXT,
    size INT,
    PRIMARY KEY(source, version, name, col_name));

CREATE TABLE IF NOT EXISTS notifications(
    kernel VARCHAR(255),
    user VARCHAR(255),
    cell VARCHAR(255),
    resp LONGTEXT);
"""

NAMESPACE_CODE =\
"""
def _make_namespace(msg_id, db_path):

    import sqlite3
    import dill

    conn = sqlite3.connection(db_path, detect_types = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()
    
    result = cursor.execute("SELECT namespace FROM namespaces WHERE msg_id = ?", msg_id).fetchall()[0]
    
    for k in result["_forking_kernel_dfs"].keys():
        globals()[k] = dill.loads(result["_forking_kernel_dfs"][k])
    for k in result.keys():
        if k != "_forking_kernel_dfs": globals()[k] = result[k] 

_make_namespace({0}, {1})
""" 

import os

if not os.getenv("MODE"):
    MODE = "EXP_CTS" # the sorts of responses the plugin should provide. options are "SORT" for sortilege, "SIM" for column similarity, and None
else:
    MODE = os.getenv("MODE")
if not os.getenv("DOCKER_HOST_IP"):
    remote_config = {"db_user" : "prompter_user", "host" : "localhost", "password" : "user_pw", "database" : "notebooks"}
else:
    remote_config = {"db_user" : "prompter_user", "host" : os.getenv("DOCKER_HOST_IP"), "password" : "user_pw", "database" : "notebooks"}
