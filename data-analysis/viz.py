import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plot_likert
from utils import *
sns.set_theme(style="whitegrid")


def read_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path)
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    not_needed = ["Status", "Create New Field or Choose From Dropdown...", 
              "RecipientLastName", "RecipientFirstName", "RecipientEmail", "LocationLatitude", 
              "LocationLongitude", "IPAddress", "ExternalReference"]
    data = df.drop(not_needed, axis=1)
    data = data.drop([0,1]).reset_index() # no data in these rows just metadata
    return data


def main():
    df = clean_data(read_data(DATA_PATH))

if __name__=="__main__":
    main()