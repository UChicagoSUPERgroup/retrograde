import pandas as pd
import numpy as np

from pandas.api.types import is_numeric_dtype
from scipy.stats import ttest_ind

from .sortilege import is_categorical

def effect_size(preds, true, selector, psi):
    """measure the effect size using the t-test""" 
    diffs = (preds.astype(float) - true.astype(float)).abs()
    metric_in_slice = psi(preds[selector], true[selector])
    metric_out_slice = psi(preds[~selector], true[~selector])
    
    sigma_in = diffs[selector].var()**2
    sigma_out = diffs[~selector].var()**2

    if sigma_in + sigma_out == 0:
        if (metric_in_slice - metric_out_slice) > 0:
            return np.inf
        elif (metric_in_slice - metric_out_slice) < 0:
            return -np.inf
        return 0.0 
    return np.sqrt(2)*(metric_in_slice - metric_out_slice)/np.sqrt(sigma_in + sigma_out)

def fpr(preds, true):
    """fpr calculation"""
    joint = ((preds == True) & (true == False)).sum()
    if joint == 0:
        return 0.0
    return joint/((true == False).sum())

def fnr(preds, true):
    """fnr calculation"""
    joint = ((preds == False) & (true == True)).sum()
    if joint == 0:
        return 0.0
    return joint/((true == True).sum())

def expand_slices(data, prev_slices):
    """expand the slices in prev_slices to include new unseen slices""" 
    col_names = data.columns
    predicates = []
    
    if prev_slices != []:
        old_len = len(prev_slices[0])
        assert all([len(s) == old_len for s in prev_slices])
    
    for col_name in col_names:
        predicates.extend([(col_name, value) for value in data[col_name].unique()])
    if prev_slices == []:
        for pred in predicates:
            yield [pred]
    for prev_slice in prev_slices:
        for pred in predicates:
            prev_cols = [p[0] for p in prev_slice]
            if pred[0] not in prev_cols:
                if (select_data(data, prev_slice + [pred]).sum())/len(data) > 0.01:
                    yield prev_slice + [pred]

def select_data(data, data_slice):
    """produce a boolean row selector based on data_slice"""
    selector = np.array([True for _ in range(len(data))])
    for pred in data_slice:
        selector = selector & (data[pred[0]] == pred[1])
    return selector

def is_significant(preds, true, selector, w):
    """
    test if the difference between the samples selected by
    selector is significant at level less than w
    """ 
    true_in = true[selector]
    true_out = true[~selector]
    preds_in = preds[selector]
    preds_out = preds[~selector]
    
    loss_in = (true_in.astype(float) - preds_in.astype(float)).abs()
    loss_out = (true_out.astype(float) - preds_out.astype(float)).abs()
    
    _,p = ttest_ind(loss_in, loss_out,equal_var=False)
    return p < w

def pre_process_df(raw_df):
    """
    take df, bin numeric columns, reduce columns with high levels of
    uniqueness.
    """
    new_cols = {}

    for col in raw_df.columns:
        if is_categorical(raw_df[col]):
            new_cols[col] = raw_df[col]
        elif is_numeric_dtype(raw_df[col]):
            new_cols[col] = pd.cut(raw_df[col], bins=10)
        else:
            # column is not numeric, but has high entropy
            old_values = raw_df[col].value_counts(sort=True)
            top_vals = old_values.index.tolist()[:9]
            new_cols[col] = raw_df[col]
            new_cols[col][~raw_df[col].isin(top_vals)] = "Other"

    return pd.DataFrame(new_cols, index=raw_df.index)

def find_slices(data, preds, true, T, alpha, psi, k, env):
    
    significant = []
    non_significant = []
    
    poss_slices = gen_preds(data)
    selector_map = {ds["slice"][0] : ds["selector"] for ds in poss_slices}
   
    for i in range(2):
        sig_q = []
        for data_slice in poss_slices:
            
            effect = effect_size(preds, true, data_slice["selector"], psi)
            env.log.debug("[slice_finder] slice {0}, effect {1}".format(data_slice["slice"], effect, data_slice["selector"].sum()))
 
            if effect > T:
                sig_q.append(data_slice)
            else:
                non_significant.append(data_slice)
        sig_q.sort(key = lambda ds: ds["selector"].sum())
        
        while sig_q != []:
            data_slice = sig_q.pop()
            if is_significant(preds, true, data_slice["selector"], alpha):
                significant.append(data_slice)
            else:
                non_significant.append(data_slice)
        poss_slices = search_slices(significant, non_significant, selector_map)
#        env.log.debug("[slice_finder] next possible slices {0}".format(poss_slices))
        if poss_slices == [] or len(significant) > k:
            return significant
    return significant

def search_slices(significant, non_significant, selector_map):
    
    sig_preds = set([s for data_slice in significant for s in data_slice["slice"]])
    non_sig_preds = set([s for data_slice in non_significant for s in data_slice["slice"]])
    
    new_slices = []
    
    for non_sig_slice in non_significant:
        prev_cols = set(p[0] for p in non_sig_slice["slice"])
        for pred in selector_map.keys():
            if pred[0] not in prev_cols:
                
                new_selector = non_sig_slice["selector"] & selector_map[pred]
                
                if new_selector.sum()/len(new_selector) > 0.05:
                    new_slice = {}
                    new_slice["slice"] = non_sig_slice["slice"] + [pred]
                    new_slice["selector"] = new_selector
                    
                    new_slices.append(new_slice)
    return new_slices

def gen_preds(data):
    
    predicates = []
    
    for col_name in data.columns:
        for value in data[col_name].unique():
            selector = (data[col_name] == value)
            if (data[col_name] == value).sum()/len(data) > 0.05:
                predicates.append({"slice" : [(col_name, value)], "selector" : selector})
                
    return predicates
 
def err_slices(raw_df, preds, true, env): 
    """
    Assume preds and true is boolean
    both must be np arrays
    """
    proc_df = pre_process_df(raw_df)

    fpr_slices = find_slices(proc_df, preds, true, 0.4, 0.05, fpr, 5, env)
    fnr_slices = find_slices(proc_df, preds, true, 0.4, 0.05, fnr, 5, env)

    fpr_slices.sort(key = lambda x: effect_size(preds, true, x["selector"], fpr))
    fnr_slices.sort(key = lambda x: effect_size(preds, true, x["selector"], fnr))

    top_k_fpr = fpr_slices[:-2]
    top_fpr_names = [f["slice"] for f in top_k_fpr]
    top_fpr_names = []
    top_k_fnr = [f for f in fnr_slices if f["slice"] not in top_fpr_names][:-2]
   
    results = []
    for data_slice in top_k_fpr:
        slice_select = data_slice["selector"]
        results.append({
            "metric_name" : "fpr", "slice" : data_slice["slice"],
            "metric_in" : fpr(preds[slice_select], true[slice_select]),
            "metric_out" : fpr(preds[~slice_select], true[~slice_select]), "n" : slice_select.sum()})
    for data_slice in top_k_fnr:  
        slice_select = data_slice["selector"]
        results.append({
            "metric_name" : "fnr", "slice" : data_slice["slice"],
            "metric_in" : fnr(preds[slice_select], true[slice_select]),
            "metric_out" : fnr(preds[~slice_select], true[~slice_select]), "n" : slice_select.sum()})

    return results
