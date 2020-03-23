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
