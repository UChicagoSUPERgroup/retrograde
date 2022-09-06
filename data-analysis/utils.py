import pandas as pd
PID = "PROLIFIC_PID"
CTS = "EXP_CTS"
END = "EXP_END"
NONE = "EXP_NONE"
DATA_PATH = "data/Jupyter in Retrograde evaluation study_September 3, 2022_13.38.csv"
LIKERT_QUESTIONS = ['Q12.2', 'Q12.3', 'Q12.4', 'Q12.5', 'Q12.6', 'Q13.1',
    'Q13.3', 'Q13.5', 'Q13.7', 'Q13.10', 'Q13.12', 'Q13.14',
    'Q14.2', 'Q14.4', 'Q14.6', 'Q14.8', 'Q14.10', 'Q14.12',
]
LIKERT_CONVERT = {
    "Strongly disagree": -2,
    "Somewhat disagree": -1,
    "Neither agree nor disagree": 0,
    "Somewhat agree": 1,
    "Strongly agree": 2,
}
QUESTION_COLUMNS = ['Q1.2', 'Q2.1', 'Q2.2', 'Q2.3',
       'Q2.4', 'Q2.5', 'Q2.6', 'Q2.7', 'Q2.8', 'Q2.9', 'Q5.1', 'Q6.2', 'Q6.3',
       'Q6.4', 'Q6.5', 'Q6.6', 'Q7.2', 'Q7.3', 'Q7.4', 'Q8.2', 'Q8.3', 'Q9.2',
       'Q9.3', 'Q9.4', 'Q10.2', 'Q11.2', 'Q11.3', 'Q11.4', 'Q11.5', 'Q11.6',
       'Q12.2', 'Q12.3', 'Q12.4', 'Q12.5', 'Q12.6', 'Q12.7', 'Q13.1', 'Q13.3',
       'Q13.4', 'Q13.5', 'Q13.6', 'Q13.7', 'Q13.8', 'Q13.10', 'Q13.11',
       'Q13.12', 'Q13.13', 'Q13.14', 'Q13.15', 'Q13.16', 'Q14.2', 'Q14.3',
       'Q14.4', 'Q14.5', 'Q14.6', 'Q14.7', 'Q14.8', 'Q14.9', 'Q14.10',
       'Q14.11', 'Q14.12', 'Q14.13', 'Q14.14', 'Q16.2', 'Q16.3', 'Q16.4',
       'Q16.4_5_TEXT', 'Q16.5', 'Q16.5_7_TEXT'
]
QUESTION_TEXT = pd.read_csv(DATA_PATH)
QUESTION_TEXT = QUESTION_TEXT.iloc[0][QUESTION_COLUMNS].values