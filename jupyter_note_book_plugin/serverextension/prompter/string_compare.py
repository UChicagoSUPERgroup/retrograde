import json
from fuzzywuzzy import fuzz

PROTECTED_MATCH_THRESHOLD = 90
PROTECTED_PROXY_MATCH_THRESHOLD = 80
PATH_PROTECTED_JSON = './protected_columns.json'
PATH_PROTECTED_JSON_FULL = 'evaluation_task/build/protected_columns.json'

COLUMN_PATTERN_THRESHOLD = 0.8


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
        
        Nationality: TODO can we import a list of nationalities?
        Disability: TODO can we import a list of disabilities?
        Genetic information: TODO can we import a list of genetic diseases?

        Pregnancy: none
        """

        # this process may flag the same column multiple times as potentially
        # protected, so we should use a set to 
        results = set()

        # gender/sex
        for column in dataframe:
            words = ['male', 'female', 'm', 'f', 'man', 'woman', 'boy', 'girl', 
                     'non-binary', 'nb']
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(level_match)
        
        # race/color
        for column in dataframe:
            words = ['black', 'white', 'red', 'yellow', 'brown', 'african', 
                     'asian', 'caucasian', 'indigenous', 'native', 'hispanic', 
                     'pacific islander']
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(level_match)

        # religion
        for column in dataframe:
            words = ['christianity', 'christian', 'islam', 'muslim', 'judaism', 
                     'jewish', 'buddhism', 'buddhist', 'hinduism', 'hindu', 
                     'atheist', 'agnostic', 'non-believer', 'folk', 'none']
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(level_match)

        # age
        # TODO

        # sexual orientation
        for column in dataframe:
            words = ['gay', 'straight', 'pansexual', 'pan', 'bisexual', 'bi', 
                     'heterosexual', 'homosexual', 'ace', 'asexual', 
                     'allosexual', 'alloromantic', 'aromantic', 'aro', 
                     'questioning', 'lesbian']
            level_match = _string_column_vs_list(dataframe, column, words, 
                                                 PROTECTED_MATCH_THRESHOLD)
            if level_match >= COLUMN_PATTERN_THRESHOLD:
                results.add(level_match)
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
    for row in dataframe.iterrows():
        didmatch = _match_any_string(str(row[colname]), words, threshold)
        if didmatch['match']:
            count += 1
    return float(count) / dataframe.shape[0]
