import json
from fuzzywuzzy import fuzz

PROTECTED_MATCH_THRESHOLD = 90
PROTECTED_PROXY_MATCH_THRESHOLD = 80
PATH_PROTECTED_JSON = './protected_columns.json'

#read in the protected values corpus
with open(PATH_PROTECTED_JSON) as f:
  PROTECTED_VALUES = json.load(f)

def check_for_protected(column_name):
    '''check to see if a column name contains a protected group'''
    return _fuzzy_string_across_dict(column_name.lower(), PROTECTED_VALUES, PROTECTED_MATCH_THRESHOLD)

def _fuzzy_string_across_dict(candidate_string, reference_dict, threshold):
    '''return list of dictionary keys that have a fuzzy match with a candidate string'''
    results = []
    for k,v in reference_dict.items():
        #see source for explanation of partial ratio
        #https://github.com/seatgeek/fuzzywuzzy/blob/9a4bc22c7483198fcb96afacc42f5f700fb803ed/fuzzywuzzy/fuzz.py#L59-L100
        partial_match = fuzz.partial_ratio(k, candidate_string)
        if partial_match >= threshold:
            results.append((k,v))
    return results