import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from warnings import warn
# import plot_likert
from utils import *
sns.set_theme(style="whitegrid")
global WARNED
WARNED = False
# ---------------
# Likert
def update_warned():
    global WARNED
    WARNED = True
def _compute_percentages(likerts: dict) -> pd.DataFrame:
    likert_df = pd.DataFrame() # to return (has condition info)
    responses_by_cond = pd.DataFrame() # for checking counts
    for cond in likerts:
        responses_per_q = pd.DataFrame(likerts[cond]).sum()
        responses_by_cond = pd.concat((responses_by_cond, responses_per_q))
        responses = responses_per_q[0]
        responses_same = responses_by_cond == responses
        if not responses_same[0].all():
            if not WARNED:
                warn(
                    "Not all questions hae the same number of responses in your data. These percentages should not be compared to each other."
                )
                update_warned()
        
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

# TODO: change parameters to be dataframe, questions, condition_col, 
# conditions, and cat names
def makeLikertPlotsAcrossConds(results: pd.DataFrame, questions: list, 
        condition_column: str, 
        conditions_to_include: list, category_names: list,
        percentages: bool = True, figsize: tuple = (20, 25), 
        fontsize: int = 12, save_fig_path: str = None
    ):
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
    for fig_num, question_group in enumerate(iter_likert_questions()):
        figsize = (50, 10)
        fig, axs = plt.subplots(ncols=len(conditions_to_include), figsize=figsize)
        for j, cond in enumerate(conditions_to_include):
            if len(conditions_to_include) > 1:
                ax = axs[j]
            else:
                ax = axs
            likerts = likert_counts(results, question_group, condition_column)
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
            ax.set_title(cond, fontsize=fontsize*2, pad=10)
            # ax.annotate(f'{cond}', xy=(-10,0.5),
            #             transform=ax.transAxes,
            #             fontsize=fontsize*2.5,
            #             color='darkgrey')
        
        
        # Title
        fig.suptitle('Plots of Likert Questions', x=.51, y=1.05, fontsize=fontsize*2, fontweight="heavy")
        
        # Legend
        lines, labels = fig.axes[-1].get_legend_handles_labels()
        fig.legend(lines, labels,
                loc='center right', ncol=1, fontsize=fontsize*1.5)

        # X and Y Labels
        fig.supxlabel('Number of participants', fontsize=fontsize*2, y=.001)
        fig.supylabel('Question', fontsize=fontsize*2, x=.095)

        # Set Background Color
        fig.set_facecolor('#FFFFFF')
        
        # Save figure
        if save_fig_path:
            fig.savefig(os.path.join(dir_path, f"{save_fig_path}_{fig_num}.png"), bbox_inches="tight")
# Likert
# ---------------


def likert_plots(args: argparse.ArgumentParser):
    # TODO: use argparse
    df = clean_data(read_data(DATA_PATH))

    if args.questions.lower() == "all":
        questions = LIKERT_QUESTIONS
    elif args.questions.lower() == None:
        # what else ??
        pass 

    if args.conditions.lower() == "all":
        conds = get_conds()

    if args.fig_name:
        fig_name = args.fig_name
    else:
        fig_name = None

    makeLikertPlotsAcrossConds(df, questions=questions,
        condition_column="mode", conditions_to_include=conds,
        category_names=LIKERT_CONVERT.keys(),
        percentages=True, fontsize=12, 
        save_fig_path=fig_name
    )