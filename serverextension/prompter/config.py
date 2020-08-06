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

CREATE TABLE IF NOT EXISTS namespaces(
    user TEXT, 
    msg_id VARCHAR(255) PRIMARY KEY, 
    exec_num INT, 
    time TIMESTAMP, 
    code TEXT, 
    namespace BLOB)
"""

"""df_funcs are dataframe methods that return non-dataframe values"""
# TODO: this is a noisy list. Some elements sometimes return a df, and some methods not in this
# can return a df depending on whether level is specified. (e.g. df.mean). 
other_funcs = [
    "equals",
    "size",
    "shape",
    "values",
    "style",
    "plot",
    "ndim",
    "lookup",
    "first_valid_index",
    "last_valid_index",
    "keys",
    "itertuples",
    "iteritems",
    "iterrows",
    "items",
    "index",
    "hist",
    "first_valid_index"
    "equals",
    "empty",
    "columns",
    "boxplot",
    "bool",
    "attrs",
    "axes",
    "to_clipboard",
    "to_csv",
    "to_dict",
    "to_excel",
    "to_feather",
    "to_gbq",
    "to_hdf",
    "to_html",
    "to_json",
    "to_latex",
    "to_markdown",
    "to_numpy",
    "to_parquet",
    "to_period",
    "to_pickle",
    "to_records",
    "to_sql",
    "to_stata",
    "to_string",
    "to_timestamp",
    "to_xarray",
    "to_coo", # technically called through df.sparse.to_coo, but ok b/c sparse not in this list
]

ambig_funcs = [
    "loc", # can return scalar or df depending on number of indexes
    "iloc", # can return scalar df or series depending on indices
    "iat", # can be used like iloc and loc, but meant for single items
    "at", # can also be used to set
    "agg", # sometimes scalar
    "aggregate", # sometimes scalar
    "asof", # sometimes scalar
    "squeeze", # sometimes scalar
    "eval", # depends on type of expression
    "all",
    "any",
    "apply",
    "count",
    "dot",
    "get",
    "var",
    "unstack",
    "sum",
    "std",
    "skew",
    "sem",
    "quantile",
    "product",
    "prod",
    "pipe", # maybe should consider argument inspection to avoid reexecution of expensive calls
    "min",
    "median",
    "mean",
    "max",
    "mad",
    "kurtosis",
    "kurt",
]

series_funcs = [
    "corrwith",
    "dtypes",
    "duplicated",
    "idxmax",
    "idxmin",
    "pop",
    "nunique",
    "memory_usage",
]

make_df_snippet = """\n
prompt_ml_pred = REPLACE_MODEL.predict(REPLACE_X)\n
prompt_ml_df = DF_ALIAS(REPLACE_X)\n
prompt_ml_df["predicted"] = prompt_ml_pred\n
prompt_ml_df["actual"] = REPLACE_Y\n
"""

clf_fp_fn_snippet =\
"""
def prompt_ml_get_rates(df, col, val):\n
    output = {"fp" : None, "fn": None, "tp":None, "tn" : None}\n
    subset = df[df[col] == val]\n
    outcomes = df["predicted"].unique() # assume that binary clf\n

    output["fp"] = float(sum((subset["predicted"] == outcomes[0]) & (subset["actual"] == outcomes[1])))/len(subset)\n
    output["fn"] = float(sum((subset["predicted"] == outcomes[1]) & (subset["actual"] == outcomes[0])))/len(subset)\n
    output["tp"] = float(sum((subset["predicted"] == outcomes[0]) & (subset["actual"] == outcomes[0])))/len(subset)\n
    output["tn"] = float(sum((subset["predicted"] == outcomes[1]) & (subset["actual"] == outcomes[1])))/len(subset)\n

    return output
"""

clf_scan_snippet = """\n
prompt_ml_cols = [c for c in prompt_ml_df.columns if c not in ["actual", "predicted"]]\n
prompt_ml_cat_columns = []\n
for c in prompt_ml_cols:\n
    if len(prompt_ml_df[c].unique()) < 6:\n
        prompt_ml_cat_columns.append(c)

prompt_ml_output = {}
for col in prompt_ml_cat_columns:
    prompt_ml_output[col] = {}
    for val in prompt_ml_df[col].unique():
        prompt_ml_output[col][val] = prompt_ml_get_rates(prompt_ml_df, col, val)

prompt_ml_output 
"""

clf_test_snippet =\
"""
from sklearn.base import ClassifierMixin\n
isinstance(REPLACE_NAME, ClassifierMixin)\n
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

MODE = "SORT" # the sorts of responses the plugin should provide. options are "SORT" for sortilege, "SIM" for column similarity, and None

