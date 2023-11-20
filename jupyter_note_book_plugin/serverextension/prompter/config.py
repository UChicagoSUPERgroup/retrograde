import os
import importlib.resources as pkg_resources

DB_DIR = "~/.promptml/"
DB_NAME = "cells.db"


if not os.getenv("MODE"):
    MODE = "NO_EXP"
else:
    MODE = os.getenv("MODE")
if not os.getenv("DOCKER_HOST_IP"):
    remote_config = {"db_user" : "prompter_user", "host" : "localhost", "password" : "user_pw", "database" : "notebooks"}
else:
    remote_config = {"db_user" : "prompter_user", "host" : os.getenv("DOCKER_HOST_IP"), "password" : "user_pw", "database" : "notebooks"}

table_query = pkg_resources.read_text(__package__, "make_tables.sql")

