DB_DIR = "~/.promptml/"
DB_NAME = "cells.db"


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

    output["fp"] = float(sum(subset["predicted"] == outcomes[0] and subset["actual"] == outcomes[1]))/len(subset)\n
    output["fn"] = float(sum(subset["predicted"] == outcomes[1] and subset["actual"] == outcomes[0]))/len(subset)\n
    output["tp"] = float(sum(subset["predicted"] == outcomes[0] and subset["actual"] == outcomes[0]))/len(subset)\n
    output["tn"] = float(sum(subset["predicted"] == outcomes[1] and subset["actual"] == outcomes[1]))/len(subset)\n

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
