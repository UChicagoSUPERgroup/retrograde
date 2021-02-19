import pandas as pd
import numpy as np

from itertools import product, combinations
from scipy.stats import zscore

def is_categorical(col):
    if pd.api.types.is_categorical_dtype(col) or pd.api.types.is_bool_dtype(col):
        return True
    dist = float(len(col.unique()))/len(col)
    
    # looking at COMPAS, the cutoff seems to be about 0.005
    return dist < 0.01    

def wands(df):

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not is_categorical(df[c])]
    cat_cols = [c for c in df.columns if is_categorical(df[c])]

    pairs = product(num_cols, cat_cols)
  
    sum_vars = []
    mean_vars = []
 
    for (num_col, cat_col) in pairs:
        if num_col == cat_col: continue # cat columns and num columns are not always distinct
        # calculate raw variance, by op (sum and mean)
        sum_var = df.groupby([cat_col]).sum()[num_col].var()
        mean_var = df.groupby([cat_col]).mean()[num_col].var()

        if not pd.isnull(sum_var):
            sum_vars.append({"type" : "wands", 
                             "op" : "sum", 
                             "cat_col" : cat_col,
                             "num_col" : num_col,
                             "var" : sum_var})
        if not pd.isnull(mean_var):
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

def cups(df):

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    corr_df = df[num_cols].corr() # default is Pearson
    
    output = []
 
    pairs = combinations(num_cols, 2)

    for (col_a, col_b) in pairs:

        strength = corr_df[col_a][col_b]
        if strength == 1.0: continue
    
        output.append({"type" : "cups", "col_a" : col_a, "col_b" : col_b, "strength" : strength})

    output = add_rank(output, "strength")
    return output

def add_rank(output, sort_key):

    total = len(output)
    output.sort(key = lambda x : x[sort_key])

    for i in range(total):

        output[i]["strength"] = str(output[i]["strength"])
        output[i]["rank"] = i+1
        output[i]["total"] = total

    return output

def pentacles(df):
   
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    
    output = []
    
    for col in num_cols:

        scores = np.absolute(zscore(df[col]))
        index = np.argmax(scores)
        strength = scores[index]

        output.append({"type" : "pentacles", 
                       "col" : col, "strength" : strength,
                       "element" : str(df[col][index])})

    output = add_rank(output, "strength")

    return output    

def swords(df):

    output = []

    for col in df.columns:

        strength = df[col].isnull().sum()/len(df[col])
        output.append({"type" : "swords", "col" : col, "strength" : strength})

    output = add_rank(output, "strength")

    return output
