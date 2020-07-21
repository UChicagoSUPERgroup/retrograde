import pandas as pd

from itertools import product

def wands(df):

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in df.columns if pd.api.types.is_categorical_dtype(df[c]) or\
                                         pd.api.types.is_bool_dtype(df[c])]

    pairs = product(num_cols, cat_cols)
  
    sum_vars = []
    mean_vars = []
 
    for (num_col, cat_col) in pairs:
        if num_col == cat_col: continue # cat columns and num columns are not always distinct
        # calculate raw variance, by op (sum and mean)
        sum_var = df.groupby([cat_col]).sum()[num_col].var()
        mean_var = df.groupby([cat_col]).sum()[num_col].var()
        
        sum_vars.append({"type" : "wands", 
                         "op" : "sum", 
                         "cat_col" : cat_col,
                         "num_col" : num_col,
                         "var" : sum_var})
        mean_vars.append({"type" : "wands", 
                          "op" : "mean", 
                          "cat_col" : cat_col,
                          "num_col" : num_col,
                          "var" : mean_var})

    total_mean_var = sum(mean_var["var"] for mean_var in mean_vars)
    total_sum_var = sum(sum_var["var"] for sum_var in sum_vars)

    for mean_var in mean_vars:
        mean_var["var"] = mean_var["var"]/total_mean_var
    for sum_var in sum_vars:
        sum_var["var"] = sum_var["var"]/total_sum_var

    total_sum = len(sum_vars)
    total_mean = len(mean_vars)

    mean_vars.sort(key = lambda x : x["var"])
    sum_vars.sort(key = lambda x : x["var"])

    for i in range(total_sum):
        sum_vars[i]["var"] = str(sum_vars[i]["var"])
        sum_vars[i]["rank"] = i+1
        sum_vars[i]["total"] = total_sum
    
    for j in range(total_mean):
        mean_vars[j]["var"] = str(mean_vars[j]["var"])
        mean_vars[j]["rank"] = j+1
        mean_vars[j]["total"] = total_mean

    return mean_vars + sum_vars
    
