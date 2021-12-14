CREATE TABLE IF NOT EXISTS cells(
    user TEXT, 
    kernel VARCHAR(36), 
    id VARCHAR(255) PRIMARY KEY, 
    contents TEXT, 
    metadata TEXT,
    num_exec INT, 
    last_exec TIMESTAMP
);

CREATE TABLE IF NOT EXISTS versions(
    user TEXT, 
    kernel VARCHAR(36), 
    id VARCHAR(255), 
    version INT, 
    time TIMESTAMP, 
    contents TEXT, 
    exec_ct INT, 
    PRIMARY KEY(id, version));

CREATE TABLE IF NOT EXISTS data(
    user VARCHAR(64) NOT NULL, 
    kernel VARCHAR(36) NOT NULL, 
    cell TEXT, 
    version INT NOT NULL, 
    source VARCHAR(255), 
    name VARCHAR(160) NOT NULL, 
    exec_ct INT,
    PRIMARY KEY(user, kernel, name, version));

-- PEP says variables should be no more than 80 characters, but there's no actual limitation.

CREATE TABLE IF NOT EXISTS columns(
    user VARCHAR(64), 
    kernel VARCHAR(36), 
    name VARCHAR(160), 
    version INT, 
    col_name VARCHAR(160),
    type TEXT,
    size INT,
    is_sensitive BOOLEAN DEFAULT FALSE,
    user_specified BOOLEAN DEFAULT FALSE,
    checked BOOLEAN DEFAULT FALSE,
    fields TEXT,
    FOREIGN KEY (user, kernel, name, version) REFERENCES data(user, kernel, name, version),
    PRIMARY KEY (user, kernel, name, version, col_name));

CREATE TABLE IF NOT EXISTS notifications(
    kernel VARCHAR(36),
    user VARCHAR(255),
    cell VARCHAR(255),
    exec_ct INT, 
    resp LONGTEXT);

CREATE TABLE IF NOT EXISTS UsersContainers(
    prolific_id VARCHAR(255) PRIMARY KEY,
    container_id VARCHAR(255),
    port INT,
    container_started_at DATETIME,
    running BOOL); 
