-- separate the user/database parts since these aren't relevant when used
-- by sqlite

DROP DATABASE IF EXISTS test_jupyter;
CREATE DATABASE test_jupyter;

CREATE USER IF NOT EXISTS 'test_user'@'localhost' IDENTIFIED BY 'test';
GRANT INSERT, SELECT, UPDATE ON test_jupyter.* TO 'test_user'@'localhost';

CREATE USER IF NOT EXISTS 'prompter_tester'@'localhost' IDENTIFIED BY 'test';
GRANT ALL PRIVILEGES ON test_jupyter.* TO 'prompter_tester'@'localhost';
