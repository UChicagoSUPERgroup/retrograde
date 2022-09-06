import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import typing
from warnings import warn
# import plot_likert
from utils import *
sns.set_theme(style="whitegrid")


def read_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

def clean_data(df: pd.DataFrame, likert_to_numeric=False) -> pd.DataFrame:
    not_needed = ["Status", "Create New Field or Choose From Dropdown...", 
              "RecipientLastName", "RecipientFirstName", "RecipientEmail", "LocationLatitude", 
              "LocationLongitude", "IPAddress", "ExternalReference"]
    data = df.drop(not_needed, axis=1)
    data = data.drop([0,1]).reset_index() # no data in these rows just metadata
    if likert_to_numeric:
        data = data.replace(LIKERT_CONVERT)
    return data
def _compute_percentages(likerts: dict) -> pd.DataFrame:
    likert_df = pd.DataFrame() # to return (has condition info)
    responses_by_cond = pd.DataFrame() # for checking counts
    warned = False
    for cond in likerts:
        responses_per_q = pd.DataFrame(likerts[cond]).sum()
        responses_by_cond = pd.concat((responses_by_cond, responses_per_q))
        responses = responses_per_q[0]
        responses_same = responses_by_cond == responses
        if not responses_same[0].all():
            if not warned:
                warn(
                    "Not all questions hae the same number of responses in your data. These percentages should not be compared to each other."
                )
                warned = True
        
        responses_df = pd.DataFrame(likerts[cond])
        responses_df = responses_df / responses_df.sum() * 100 
        responses_df["mode"] = cond
        likert_df = pd.concat((likert_df, responses_df), axis=0)
    return likert_df

# TODO: add conditions to include
def likert_counts(data:pd.DataFrame, questions:list, condition_column: str)-> dict:
    counts = {cond:{} for cond in data[condition_column].unique()}
    for cond in counts.keys():
        d = data[data[condition_column] == cond]
        for question in questions:
            counts[cond][question] = d[question].value_counts().reindex(LIKERT_CONVERT.keys()).fillna(0).to_list()
    return counts



def _counts_plot():
    pass

# TODO: change parameters to be dataframe, questions, condition_col, 
# conditions, and cat names
def makeLikertPlotsAcrossConds(results: pd.DataFrame, questions: list, condition_column: str, 
                               conditions_to_include: list, category_names: list,
                               percentages: bool = True, figsize: tuple = (30, 10), 
                               fontsize: int = 12, save_fig_path: str = None) -> plt.Figure:
    """
    Parameters
    ----------
    results : dict
        A mapping from question labels to a list of answers per category.
        It is assumed all lists contain the same number of entries and that
        it matches the length of *category_names*.
    category_names : list of str
        The category labels.
    """
    fig, axs = plt.subplots(ncols=len(conditions_to_include), figsize=figsize)
    # Bounnding Box
#     fig.subplots_adjust(top=0.85, bottom=0.15, left=0.2, hspace=0.8)

#     fig.patch.set_linewidth(10)
#     fig.patch.set_edgecolor('cornflowerblue')
    for j, cond in enumerate(conditions_to_include):
        if len(conditions_to_include) > 1:
            ax = axs[j]
        else:
            ax = axs
        likerts = likert_counts(results, questions, condition_column)
        if percentages:
            likert_percents = _compute_percentages(likerts)
            likert_percents = likert_percents[likert_percents['mode'] == cond].drop('mode', axis=1)
        likerts = likerts[cond]
        # TODO: fix this for multiple conditions
        labels = list(likerts.keys())
        data = np.array(list(likerts.values()))
        data_cum = data.cumsum(axis=1)
        middle_index = data.shape[1]//2
        offsets = data[:, range(middle_index)].sum(axis=1) + data[:, middle_index]/2

        # Color Mapping
        category_colors = plt.get_cmap('coolwarm_r')(
            np.linspace(0.15, 0.85, data.shape[1]))

        # fig, ax = plt.subplots(figsize=(10,10))

        # Plot Bars
        # TODO: change colname
        for i, (colname, color) in enumerate(zip(category_names, category_colors)):
            widths = data[:, i]
            starts = data_cum[:, i] - widths - offsets
            rects = ax.barh(labels, widths, left=starts, height=0.5,
                            label=colname, color=color)
            if j < 1:
                rects.set_label(colname)
            c = LIKERT_CONVERT[colname]
            ax.bar_label(rects, labels=[f'{x:.1f}%' for x in likert_percents.iloc[c+2, :]],
                         label_type='center', color='white', weight='bold', fontsize=fontsize)

        # Add Zero Reference Line
        ax.axvline(0, linestyle='--', color='black', alpha=.25)

        # X Axis
        ax.set_xlim(-10, 10)
        # ax.set_xticks(np.arange(-90, 91, 10))
        ax.xaxis.set_major_formatter(lambda x, pos: str(abs(int(x))))

        # Y Axis
        ax.invert_yaxis()

        # Remove spines
        # ax.spines['right'].set_visible(False)
        # ax.spines['top'].set_visible(False)
        # ax.spines['left'].set_visible(False)

        # Annotate subplots
        ax.annotate(f'{cond}', (0.5, 0.5),
                           transform=ax.transAxes,
                           ha='center', va='center', fontsize=fontsize*2.5,
                           color='darkgrey')
    
    
    # Title
    fig.suptitle('Plots of Likert Questions', fontsize=fontsize*2)
    
    # Legend
    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, bbox_to_anchor=(1, .75),
               loc='upper center', ncol=1, fontsize=fontsize*1.5)

    # X and Y Labels
    fig.supxlabel('Number of participants', fontsize=fontsize*2, y=.0115)
    fig.supylabel('Question', fontsize=fontsize*2, x=.095)

    # Set Background Color
    fig.set_facecolor('#FFFFFF')
    
    # Save figure
    if save_fig_path:
        fig.savefig(save_fig_path)

    return fig

def main():
    df = clean_data(read_data(DATA_PATH), likert_to_numeric=True)
    plot_likert_data(df, LIKERT_QUESTIONS[:3], LIKERT_CONVERT)
if __name__=="__main__":
    main()