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


def likert_counts(data:pd.DataFrame, questions:list, condition_column: str, from_int: bool = False)-> dict:
    counts = {cond:{} for cond in data[condition_column].unique()}
    for cond in counts.keys():
        d = data[data[condition_column] == cond]
        for question in questions:
            if not from_int:
                counts[cond][question] = d[question].value_counts().reindex(LIKERT_CONVERT.keys()).fillna(0).to_list()
            else:
                lc = {v: k for k, v in LIKERT_CONVERT.items()}
                counts[cond][question] = d[question].value_counts().reindex(lc.keys()).fillna(0).to_list()
    return counts

def diverging_likert(results: pd.DataFrame, 
    questions: list, 
    condition_column: str, 
    conditions_to_include: list, category_names: list,
    percentages: bool = True, figsize: tuple = (20, 25), 
    fontsize: int = 12, save_fig_path: str = None,
    method: str = "section"
    ):
    for fig_num, question_group in enumerate(iter_likert_questions(method=method)):
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
            for label in labels: 
                pass
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
            fig.savefig(os.path.join(dir_path, f"{save_fig_path}_{method}{fig_num}.png"), bbox_inches="tight")

# TODO: match most of the diverging params
def aligned_likert(data, 
    conditions_to_include: list,
    save_path: str,
    include_groups: list=[0,1,2], 
    condition_column: str='mode', 
    title: str='', 
    method: str='sections'
    ):
    labels = data[condition_column].unique()
    figsize = (100, 10)
    question_groups = np.asarray(iter_likert_questions(method=method), dtype=object)[include_groups]
    if not isinstance(include_groups, int):
        ncols = sum([len(question_group) for question_group in question_groups])
    else:
        ncols = len(question_groups)
        question_groups = [question_groups]
    fig, axs = plt.subplots(ncols=ncols, figsize=figsize)
    last_m = 0
    for idx, question_group in enumerate(question_groups):
        likert_percents_cumul = pd.DataFrame()
        likerts_ = _compute_percentages(likert_counts(data, LIKERT_QUESTIONS, 'mode', from_int=True))
        # print(likerts_)
        for jdx, cond in enumerate(labels):
            likerts = likert_counts(data[data['mode'] == cond], LIKERT_QUESTIONS, 'mode', from_int=True)
            likert_percents = _compute_percentages(likerts)
            mode = likert_percents['mode'].copy(deep=True)
            likert_percents = pd.concat((mode,likert_percents.drop('mode', axis=1).cumsum(axis=0)), axis=1) # add in the column
            likert_percents_cumul = pd.concat((likert_percents_cumul, likert_percents), axis=0) # combine with rest
        for mdx, question_colname in enumerate(question_group):
            ax = axs[mdx+last_m]
            ax.invert_yaxis()
            ax.set_xlim(0, 100)
            ticks = [0, 25, 50, 75, 100]
            ax.set_xticks(ticks, labels=[f'{t}%' for t in ticks], )
            category_colors = plt.colormaps['coolwarm_r'](np.linspace(0.15, 0.85, 5))
            for kdx, (likert_name, color) in enumerate(zip(LIKERT_CONVERT, category_colors)):
                # .loc[index_of_likert_scale_value, question_column_name]
                widths = likerts_.loc[kdx%5, question_colname].values
                starts = likert_percents_cumul.loc[kdx%5, question_colname].values - widths
                if idx == 1:
                    print(widths)
                    print(starts)
                    print(question_colname, likert_name)
                    print()
                rects = ax.barh(labels, widths, left=starts, height=0.5,
                                label=likert_name, color=color,
                                edgecolor='white', linewidth=1.5)
                r, g, b, _ = color
                text_color = 'white' if r * g * b < 0.5 else 'black'
                # ax.bar_label(rects, 
                #              labels=[f'{x:.1f}%' for x in likerts_.loc[kdx%5, question_colname]], 
                #              label_type='center', 
                #              color=text_color,
                #              fontsize=15)
                ax.tick_params(axis='both', labelsize=24)
                ax.tick_params(axis='y', pad=30)
            ax.set_title(question_colname, loc='center', fontsize=36)
            if mdx != 0 or idx != 0:
                ax.set_yticklabels([])
        last_m += mdx + 1
    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, ncol=5, loc='lower center', bbox_to_anchor=(0.5,0), borderaxespad=.1, frameon=False, prop={'size': 32})
    if title != '':
        fig.suptitle(title, fontsize=40)
    fig.savefig(os.path.join(dir_path, "figs/", f"{save_path}.png"), bbox_inches='tight')
# Likert
# ---------------


def likert_plots(args: argparse.ArgumentParser):
    df = read_data(ALT_DATA_PATH)

    if args.method.lower():
        method = args.method
    elif args.method is None:
        # TODO: what else ??
        pass 

    if args.conditions.lower() == "all":
        conds = get_conds()
    # TODO what else?


    if method == 'sections':
        for section in [0, 1, 2]:
            path = args.path + str(section)
            if args.show_title:
                title = str(args.title)
                title = title.replace('_', ' ')
                title = title + '_' + str(section)
            else:
                title = ''
            if section == 2:
                # EXP_END has no responses for this section, so implicitly exclude
                aligned_likert(df, 
                    conditions_to_include=conds[:2],
                    save_path=path,
                    include_groups=[section],
                    title=title,
                    method=method
                )
            else:
                aligned_likert(df, 
                    conditions_to_include=conds,
                    save_path=path,
                    include_groups=[section],
                    title=title,
                    method=method,
                )