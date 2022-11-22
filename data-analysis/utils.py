import os
import pandas as pd
import numpy as np
dir_path = os.path.dirname(os.path.realpath(__file__))
EXCLUDE_PARTICIPANTS = [
    "62fe9bebf5d09924e321a32c", # Did not submit model
    "630b97b387b7b77ecdd94218", # Issues with server set-up    
    "5678ea0289319e00116519c3", # Issues with server set-up
    "604445808afbd64cbbcd20a1", # Issues with server set-up
    "56a38b45dbe850000cfd50c3", # Issues with server set-up
    "5d93ee94eaf36200134a1d87", # Issues with server set-up
    "615d051e2366aeb051acb734", # Issues with server set-up
    "5b3011a8c6d7d20001143ab5", # Claimed to not see notifs
    "630c15ae6bebca06b5f79aae", # Claimed to not see notifs
    "62b43755f6be0c82be3cb760", # Claimed to not see notifs
    "631b72b707641a079ee9cd1d", # Didn't finish
    "61719508d946490934305f3a" # Didn't see notifs
]
PID = "PROLIFIC_PID"
CTS = "EXP_CTS"
END = "EXP_END"
NONE = "EXP_NONE"
conds = [NONE, CTS, END]
DATA_PATH = os.path.join(dir_path, "data/Jupyter+in+Retrograde+evaluation+study_September+12,+2022_16.15.csv")
ALIGNED_DATA_PATH = os.path.join(dir_path, "data/aligned_likert_df.csv")
LIKERT_QUESTIONS = [
    'Q12.2', 'Q12.3', 'Q12.4', 'Q12.5', 'Q12.6', 'Q13.1',
    'Q13.3', 'Q13.5', 'Q13.7', 'Q13.10', 'Q13.12', 'Q13.14',
    'Q14.2', 'Q14.4', 'Q14.6', 'Q14.8', 'Q14.10', 'Q14.12',
]
LIKERT_QUESTIONS_PLOT = {
    'Q12.2': "Examining the data\n(p = 0.817)",
    'Q12.3': "Model architectures\n(p = 0.512)", 
    'Q12.4': "Transforming features\n(p = 0.784)", 
    'Q12.5': "Selecting predictors\n(p = 0.132)", 
    'Q12.6': "Understanding the model\n(p = 0.156)", 
    'Q13.1': "Successful characteristics\n(p = 0.330)",
    'Q13.3': "Comfortable deploying\n(p = 0.018)", 
    'Q13.5': "Best that can be achieved\n(p = 0.024)", 
    'Q13.7': "Confident I understand\n(p = 0.117)", 
    'Q13.10': "Data is reliable\n(p = 0.223)", 
    'Q13.12': "Model is fair\n(p = 0.604)", 
    'Q13.14': "Feel model is biased\n(p = 0.128)",
    'Q14.2': "Check ASAP\n(p = 0.018)", 
    'Q14.4': "Notifications annoying\n(p = 0.041)", 
    'Q14.6': "Caused changes\n(p = 0.355)", 
    'Q14.8': "Understood information\n(p < .001)", 
    'Q14.10': "Understood actions\n(p = 0.067)", 
    'Q14.12': "More ethical model\n(p = 0.925)",
}
LIKERT_CONVERT = {
    "Strongly agree": 2,
    "Somewhat agree": 1,
    "Neither agree nor disagree": 0,
    "Somewhat disagree": -1,
    "Strongly disagree": -2,
}
QUESTION_COLUMNS = [
    'Q1.2', 'Q2.1', 'Q2.2', 'Q2.3',
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
for idx, qt in enumerate(QUESTION_TEXT):
    if "..." in qt:
        QUESTION_TEXT[idx] = "I spent a large portion of my time in this study " + qt[3:]

def get_conds() -> list:
    return conds
def get_conds_plot(conds_to_plot: list) -> list:
    plot_names = {
        "EXP_NONE": "None",
        "EXP_CTS": "Continuous",
        "EXP_END": "Post-Facto",
    }
    order = [('None', 0), ('Continuous',1), ('Post-Facto', 2)]
    if len(conds_to_plot) == 3:
        return list(plot_names.values())[::-1]
    else:
        names = [plot_names[cond] for cond in conds_to_plot]
        names.sort(key=lambda x: x[1])
        return [name[0] for name in names]
    
def get_notif_conds() -> list:
    return conds[1:3]
def read_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path)
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    not_needed = [
        "Status", "Create New Field or Choose From Dropdown...", 
        "RecipientLastName", "RecipientFirstName", "RecipientEmail", "LocationLatitude", 
        "LocationLongitude", "IPAddress", "ExternalReference"
    ]
    data = df.drop(not_needed, axis=1)
    excluding_participants_indices = data[data["PROLIFIC_PID"].isin(EXCLUDE_PARTICIPANTS)].index
    data = data.drop(excluding_participants_indices)
    data = data.drop([0,1]).reset_index(drop=True) # just metadata in these rows
    # data = data.replace(LIKERT_CONVERT) # replaces "Strongly Agree" with 2, "Somewhat Agree" with 1, etc. 
    data["StartDate"] = pd.to_datetime(data["StartDate"])
    data["EndDate"] = pd.to_datetime(data["StartDate"])
    data["RecordedDate"] = pd.to_datetime(data["StartDate"])
    data["Duration (in seconds)"] = data["Duration (in seconds)"].astype(int)
    data["Finished"] = data["Finished"].astype(bool)
    data["Progress"] = data["Progress"].astype(int)
    data = data[data["Progress"] == 100]
    return data
def get_question_idx(question: str) -> int:
    return np.where(QUESTION_TEXT == question)[0][0]
def get_question_column(question: int or str) -> str:
    if isinstance(question, (int, np.int64, np.int32)):
        return QUESTION_COLUMNS[question]
    else:
        return QUESTION_COLUMNS[get_question_idx(question)]
def convert_idx(question: str) -> list:
    return [LIKERT_QUESTIONS[LIKERT_QUESTIONS.index(get_question_column(question))]]
def question_number_to_question_text(question: str) -> str:
    return QUESTION_TEXT[QUESTION_COLUMNS.index(question)]
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
    elif method == "paper":
        sections = []
        sections.append(["Q12.2", "Q12.3", "Q12.4", "Q12.5", "Q12.6"])
        sections.append(["Q13.3", "Q13.5", "Q13.7", "Q13.14"])
        sections.append(["Q13.1", "Q13.10", "Q13.12"])
        sections.append(["Q14.6", "Q14.12", "Q14.4", "Q14.2", "Q14.8", "Q14.10"])
        return sections
def make_aligned_likert_df() -> pd.DataFrame:
    data = clean_data(read_data(DATA_PATH))
    alt = data[[PID, 'mode'] + LIKERT_QUESTIONS]
    alt = alt.replace(LIKERT_CONVERT).fillna(0)
    alt.to_csv(ALIGNED_DATA_PATH)
    return alt