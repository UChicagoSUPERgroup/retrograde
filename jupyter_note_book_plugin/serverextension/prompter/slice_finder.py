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

def find_slices(data, preds, true, T, alpha, psi):
    """
    iteratively find slices where predictions have an error function (psi)
    that is significantly higher than the rest of the data

    data is the data-frame with the attributes to search on
    preds is the boolean predictions
    true is the true labels
    
    T is the minimum effect size for inclusion
    alpha is the significance level to test at
    psi is the loss/error function
    """ 
    E = list(expand_slices(data, []))
    s = []
    c = []
    n = []
        
    while True:
        for data_slice in E:
            selector = select_data(data, data_slice)
            effect = effect_size(preds, true, selector, psi)
            if effect >= T:
                #print("Effect of slice {0} is {1}".format(data_slice, effect))
                c.append(data_slice)
            else:
                n.append(data_slice)
        c.sort(key = lambda ds: len(data[select_data(data, ds)]))
        
        while c != []:
            data_slice = c.pop()
            if is_significant(preds, true, select_data(data, data_slice), alpha):
                s.append(data_slice)
                #w += alpha
            else:
                n.append(data_slice)
                #w -= alpha/(1. - alpha)
            #print("w is {0}".format(w))
        
        E = list(expand_slices(data, n))
        n = []
        if E == []:
            break
    return s

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
     
def err_slices(raw_df, preds, true): 
    """
    Assume preds and true is boolean
    both must be np arrays
    """
    proc_df = pre_process_df(raw_df)

    fpr_slices = find_slices(proc_df, preds, true, 0.4, 0.05, fpr)
    fnr_slices = find_slices(proc_df, preds, true, 0.4, 0.05, fnr)

    def calc_effect(data_slice, psi):
        selector = select_data(proc_df, data_slice)
        return effect_size(preds, true, selector, psi)

    fpr_slices.sort(key = lambda x: calc_effect(x, fpr))
    fnr_slices.sort(key = lambda x: calc_effect(x, fnr))

    top_k_fpr = fpr_slices[:-2]
    top_k_fnr = fnr_slices[:-2]
    
    results = []

    for data_slice in top_k_fpr:
        slice_select = select_data(proc_df, data_slice)
        results.append({
            "metric_name" : "fpr", "slice" : data_slice,
            "metric_in" : fpr(preds[slice_select], true[slice_select]),
            "metric_out" : fpr(preds[~slice_select], true[~slice_select]), "n" : slice_select.sum()})
    for data_slice in top_k_fnr:  
        slice_select = select_data(proc_df, data_slice)
        results.append({
            "metric_name" : "fnr", "slice" : data_slice,
            "metric_in" : fnr(preds[slice_select], true[slice_select]),
            "metric_out" : fnr(preds[~slice_select], true[~slice_select]), "n" : slice_select.sum()})

    return results
