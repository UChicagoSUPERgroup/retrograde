import json
from fuzzywuzzy import fuzz
from sys import stderr

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


def check_for_protected(column_names):
    '''check to see if a list of column names contains any protected groups'''
    protected_corpus = _get_protected()
    results = []
    for column_name in column_names:
        next_results = _fuzzy_string_across_dict(column_name.lower(), protected_corpus, PROTECTED_MATCH_THRESHOLD)
        results.extend(next_results)
    return results

def guess_protected(dataframe):
    for column in dataframe:
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

        # this process may flag the same column multiple times as potentially
        # protected, so we should use a set to 
        results = set()

        # gender
        for column in dataframe:
            words = _get_dictioanry('gender')
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # sex
        for column in dataframe:
            words = _get_dictioanry('sex')
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # race
        for column in dataframe:
            words = _get_dictioanry('race')
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # color
        for column in dataframe:
            words = _get_dictioanry('color')
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # religion
        for column in dataframe:
            words = _get_dictioanry('religion')
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # age
        for column in dataframe:
            if not is_numeric_dtype(dataframe[column]):
                continue
            count = 0
            for index, row in dataframe.iterrows():
                if _is_integer(row[column]) and (row[column] <= 125 and row[column] >= 1):
                    count += 1
            level_match = float(count) / dataframe.shape[0]
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # sexual orientation
        for column in dataframe:
            words = _get_dictioanry('sexual_orientation')
            level_match = _string_column_vs_list(dataframe, column, words,
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # nationality
        for column in dataframe:
            words = _get_dictioanry('nationality')
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 NATIONALITY_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # NOTE these last ones return empty lists and add nothing to the results
        # unless protected_columns.json is modified

        # pregnancy
        for column in dataframe:
            words = _get_dictioanry('pregnancy')
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 NATIONALITY_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # disability
        for column in dataframe:
            words = _get_dictioanry('disability')
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 NATIONALITY_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)

        # genetic information
        for column in dataframe:
            words = _get_dictioanry('genetic_information')
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 NATIONALITY_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(column)
    
        # now we have a set of potentially sensitive columns
        # NOTE we haven't recorded why they were flagged as such
        return list(results)

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
def _string_column_vs_list(dataframe, colname, words, threshold):
    count = 0
    for index, row in dataframe.iterrows():
        didmatch = _match_any_string(str(row[colname]), words, threshold)
        if didmatch['match']:
            count += 1
    return float(count) / dataframe.shape[0]

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
