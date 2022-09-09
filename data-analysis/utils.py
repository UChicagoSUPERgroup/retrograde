import os
import pandas as pd
import numpy as np
dir_path = os.path.dirname(os.path.realpath(__file__))
EXCLUDE_PARTICIPANTS = [
    "630c15ae6bebca06b5f79aae", # scam
    "56a38b45dbe850000cfd50c3", ###### issue
    "630b97b387b7b77ecdd94218", ###### issue
    "5678ea0289319e00116519c3", ###### issue
    "615d051e2366aeb051acb734", ###### issue
    "604445808afbd64cbbcd20a1", ###### issue
    "5d93ee94eaf36200134a1d87", ###### issue
    "62bdd8ea1de5b02c9ccb99fc", # restarting, so only remove the first one
    "5b3011a8c6d7d20001143ab5", # in CTS, did not see notifications... 
]
PID = "PROLIFIC_PID"
CTS = "EXP_CTS"
END = "EXP_END"
NONE = "EXP_NONE"
conds = [NONE, CTS, END]
DATA_PATH = os.path.join(dir_path, "data/Jupyter+in+Retrograde+evaluation+study_September+8,+2022_05.57.csv")
ALT_DATA_PATH = os.path.join(dir_path, "data/alt_df.csv")
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
QUESTION_TEXT = pd.read_csv(DATA_PATH).iloc[0][QUESTION_COLUMNS].values

def get_conds() -> list:
    return conds
def get_notif_conds() -> list:
    return conds[1:3]
def read_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path)
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    not_needed = ["Status", "Create New Field or Choose From Dropdown...", 
              "RecipientLastName", "RecipientFirstName", "RecipientEmail", "LocationLatitude", 
              "LocationLongitude", "IPAddress", "ExternalReference"]
    data = df.drop(not_needed, axis=1)
    data = data.drop([0,1]).reset_index(drop=True) # just metadata in these rows
    # data = data.replace(LIKERT_CONVERT) # replaces "Strongly Agree" with 2, "Somewhat Agree" with 1, etc. 
    data["StartDate"] = pd.to_datetime(data["StartDate"])
    data["EndDate"] = pd.to_datetime(data["StartDate"])
    data["RecordedDate"] = pd.to_datetime(data["StartDate"])
    data["Duration (in seconds)"] = data["Duration (in seconds)"].astype(int)
    data["Finished"] = data["Finished"].astype(bool)
    return data
def get_question_column(question: str):
    if isinstance(question, int):
        return QUESTION_COLUMNS[question]
    else:
        return QUESTION_COLUMNS[np.where(QUESTION_TEXT == question)[0][0]]
def iter_likert_questions(method: str = "pairs") -> list:
    likert_it = iter(LIKERT_QUESTIONS)
    if method == "pairs":
        return [[x, next(likert_it)] for x in likert_it]
    elif method == "sections":
        sections = []
        sections.append([q for q in LIKERT_QUESTIONS if q.startswith("Q12")])
        sections.append([q for q in LIKERT_QUESTIONS if q.startswith("Q13")])
        sections.append([q for q in LIKERT_QUESTIONS if q.startswith("Q14")])
        return sections