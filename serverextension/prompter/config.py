DB_DIR = "~/.promptml/"
DB_NAME = "cells.db"


"""df_funcs are dataframe methods that return non-dataframe values"""
df_funcs = [
        "agg", # sometimes scalar
        "aggregate", # sometimes scalar
        "asof", # sometimes scalar
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
]
