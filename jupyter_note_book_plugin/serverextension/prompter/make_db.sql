-- separate the user/database parts since these aren't relevant when used
-- by sqlite

-- must be run as root/user w/ privileges to make databases

DROP DATABASE IF EXISTS notebooks;
CREATE DATABASE notebooks;

CREATE USER IF NOT EXISTS 'prompter_user'@'%' IDENTIFIED BY 'user_pw';
GRANT INSERT, SELECT, UPDATE ON notebooks.* TO 'prompter_user'@'%';
