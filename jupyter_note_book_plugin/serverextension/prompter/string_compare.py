import json
from fuzzywuzzy import fuzz
from sys import stderr
from math import floor, log2

import pandas as pd
from pandas.api.types import is_numeric_dtype

PROTECTED_MATCH_THRESHOLD = 90
PROTECTED_PROXY_MATCH_THRESHOLD = 80
NATIONALITY_THRESHOLD = 30
COLUMN_PATTERN_THRESHOLD = 0.8
PATH_PROTECTED_JSON = './protected_columns.json'
PATH_PROTECTED_JSON_FULL = 'evaluation_task/build/protected_columns.json'
PATH_NATIONALITIES = './nationalities.txt'
PATH_NATIONALITIES_FULL = 'evaluation_task/build/nationalities.txt'


# try to pre-load the nationalitie file
nationality_file = None
try:
    nationality_file = open(PATH_NATIONALITIES)
except FileNotFoundError:
    nationality_file = open(PATH_NATIONALITIES_FULL)
NATIONALITY_WORDS = nationality_file.readlines()


def check_for_protected(column_names):
    '''check to see if a list of column names contains any protected groups'''
    protected_corpus = _get_protected()
    results = []
    for column_name in column_names:
        next_results = _fuzzy_string_across_dict(column_name.lower(), protected_corpus, PROTECTED_MATCH_THRESHOLD)
        results.extend(next_results)
    return results

def guess_protected(dataframe):
        """
        using: https://www.kite.com/python/answers/how-to-count-the-elements-of-a-pandas-dataframe-where-a-condition-is-true-in-python
        
        Gender/sex: check if column matches threshold for: 
            male, female, m, f, man, woman, boy, girl, non-binary, nb
        Race/color: check if column matches threshold for:
            black, white, red, yellow, brown, african, asian, caucasian, 
            indigenous, native, hispanic
        Religion: check if column matches threshold for:
            christianity, christian, islam, muslim, judaism, jewish, buddhism, 
            buddhist, hinduism, hindu, atheist, agnostic, non-believer
        Age: check if column matches threshold for:
            integer between 1 and 122
        Sexual orientation: check if column matches threhold for:
            gay, straight, pansexual, pan, bisexual, bi, heterosexual, 
            homosexual, ace, asexual, allosexual, alloromantic, aromantic,
            aro, questioning, lesbian
        Nationality: Import from World Bank databank, then repeat the above

        Disability: TODO too nuanced to be worth it
        Genetic information: TODO too nuanced to be worth it

        Pregnancy: none
        """

        results = []
        protected_corpus = _get_protected()

        # by only testing a logarithmic sample of the rows in each column,
        # we can reduce this process from polynomial ~O(n^2) time 
        # to linearithmic ~O(n log n) time

        # avoids duplication by picking the first possible protected 
        # value that passes the threshold. We could consider choosing 
        # category with highest match score
        for column in dataframe.columns:
            for k,v in protected_corpus.items():
                if "use_func" not in v.keys():
                    words = v["dictionary"]
                    level_match = _string_column_vs_list(dataframe, column, words, 
                                                         PROTECTED_MATCH_THRESHOLD,
                                                         log_sample=True)
                    if level_match >= COLUMN_PATTERN_THRESHOLD:
                        results.append({"protected_value" : k, 
                                        "protected_value_background" : v,
                                        "original_name": column})
                        break # we make a guess once and don't consider it again
                else:
                    level_match = SPECIAL_FUNC[v["use_func"]](dataframe, column, v, PROTECTED_MATCH_THRESHOLD, log_sample=True)
                    if level_match >= COLUMN_PATTERN_THRESHOLD:
                        results.append({"protected_value" : k,
                                        "protected_value_background" : v,
                                        "original_name" : column})
                        break
        return results


        columns = set(dataframe.columns)
        results = []
        protected_corpus = _get_protected()

        for k,v in protected_corpus.items():
            iter_cols = columns.copy()
            for column in iter_cols:
                if "use_func" not in v.keys():
                    words = v["dictionary"]
                    level_match = _string_column_vs_list(dataframe, column, words, 
                                                         PROTECTED_MATCH_THRESHOLD)
                    if level_match >= COLUMN_PATTERN_THRESHOLD:
                        results.append({"protected_value" : k, 
                                        "protected_value_background" : v,
                                        "original_name": column})
                        columns.remove(column)
                        continue # we make a guess once and don't consider it again. We could consider choosing category with highest match score
                else:
                    level_match = SPECIAL_FUNC[v["use_func"]](dataframe, column, v, PROTECTED_MATCH_THRESHOLD)
                    if level_match >= COLUMN_PATTERN_THRESHOLD:
                        results.append({"protected_value" : k,
                                        "protected_value_background" : v,
                                        "original_name" : column})
                        columns.remove(column)
                        continue
        return results
def get_nations(dataframe, column, v, PROTECTED_MATCH_THRESHOLD, log_sample=False):
    """
    return match level of column against nations specifically. 
    
    This is required because we need to load in nationalities from a separate file
    """
    words = NATIONALITY_WORDS
    level_match = _string_column_vs_list(dataframe, column, words, 
                                         NATIONALITY_THRESHOLD, log_sample)
    return level_match

def get_age(dataframe, column, v, PROTECTED_MATCH_THRESHOLD, log_sample=False):
    if not is_numeric_dtype(dataframe[column]):
        return 0

    use_df = dataframe
    n = dataframe.shape[0]
    if log_sample:
        n = floor(log2(n))
        use_df = use_df.sample(n=n)

    count = 0
    count = use_df[column].astype(float).apply(float.is_integer).sum()
    level_match = float(count) / n
    return level_match
 
def _get_protected():
    '''read in the protected values corpus'''
    protected_values = {}
    try:
        with open(PATH_PROTECTED_JSON) as f:
            protected_values = json.load(f)
    except FileNotFoundError:
        with open(PATH_PROTECTED_JSON_FULL) as f:
            protected_values = json.load(f)
    return protected_values

def _fuzzy_string_across_dict(candidate_string, reference_dict, threshold):
    '''return list of dictionary keys that have a fuzzy match with a candidate string'''
    results = []
    for k,v in reference_dict.items():
        #see source for explanation of partial ratio
        #https://github.com/seatgeek/fuzzywuzzy/blob/9a4bc22c7483198fcb96afacc42f5f700fb803ed/fuzzywuzzy/fuzz.py#L59-L100
        partial_match = fuzz.partial_ratio(k, candidate_string)
        if partial_match >= threshold:
            results.append({"protected_value" : k, 
                            "protected_value_background" : v,
                            "original_name" : candidate_string})
    return results

# see if a string fuzzy matches any of the words in the words
# list and return a dict with the result and matched word
def _match_any_string(string, words, threshold):
    for word in words:
        partial_match = fuzz.partial_ratio(string.lower(), word)
        if partial_match >= threshold:
            # might be useful to save the actual word it matched to
            return {'match': True, 'value': word}
    return {'match': False, 'value': ''}

# count the number of values in this column match any string in
# the 'words' list
def _string_column_vs_list(dataframe, colname, words, threshold, log_sample=False):
    use_df = dataframe
    n = dataframe.shape[0]
    if log_sample:
        n = floor(log2(n))
        use_df = use_df.sample(n=n)
    count = 0
    for _, row in use_df.iterrows():
        didmatch = _match_any_string(str(row[colname]), words, threshold)
        if didmatch['match']:
            count += 1
    return float(count) / n

# checks if a number is an integer
def _is_integer(n):
    try:
        float(n)
    except ValueError:
        return False
    else:
        return float(n).is_integer()

# get the "dictioanry" from the main
def _get_dictioanry(protected_class):
    protected_values = _get_protected()

    try:
        if protected_class == 'nationality':
            nationality_file = None
            try:
                nationality_file = open(PATH_NATIONALITIES)
            except FileNotFoundError:
                nationality_file = open(PATH_NATIONALITIES_FULL)
            words = nationality_file.readlines()
            return words
        return protected_values[protected_class]['dictionary']
    except KeyError:
        print("[ERROR] \"{}\" not a registered protected class in protected_columns.json".format(protected_class), file=stderr)
        return []
SPECIAL_FUNC = {"get_age" : get_age, "get_nations" : get_nations}
