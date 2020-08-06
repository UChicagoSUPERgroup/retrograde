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

CREATE TABLE IF NOT EXISTS namespaces(
    user TEXT, 
    msg_id VARCHAR(255) PRIMARY KEY, 
    exec_num INT, 
    time TIMESTAMP, 
    code TEXT, 
    namespace BLOB)
