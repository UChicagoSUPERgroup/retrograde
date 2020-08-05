def check_sex(col, df):
    if "sex" in col.lower() or\
        "gender" in col.lower() or\
        "male" in col.lower() or\
        "female" in col.lower():
        return 1.0

    values = [v.lower() for v in df[col].unique()]
    # semi-arbitrary number, assuming questionaire is formatted as
    #   male, female, trans, nb, intersex, other, prefer not to say
    if len(values > 7): return 0.0

    value_strings = ["male", "female"]
    
    for value in values:
        for string in value_strings:
            if string in value:
                return 1.0
    return 0.0 
