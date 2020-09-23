<!--- section_1_text -->
# Introduction

Thank you for agreeing to take part in this evaluation. During this evaluation you will be asked to carry out a series of tasks related to the dataset shown in the next section. Please carry out these tasks with the same care and rigor as if these tasks were part of your job duties.
    
Before beginning please ensure that you are using the prompter kernel by looking at the top right of this notebook. It should say \"prompter\", rather than \"Python 3\". If says you are using a python kernel, please click on where it says Python, and select the prompter from the drop down study. If you encounter any errors, or if it says No Kernel! please contact PLACEHOLDER@uchicago.edu.
<!--- section_2_text -->
## Task Description

This task is structured into four parts.

1. **Dataset introduction**
2. **Data cleaning**
3. **Model Training**
4. **Model Selection**

In each of these, there will be some code pre-written. You are not required to use this code, and may replace it if you like. You may refer to any documentation source you like during this task (such as Pandas of scikit-learn API documentation, or StackOverflow).

We ask that you use pandas and scikit-learn to perform the tasks. We have also installed numpy and matplotlib, should those be helpful. You will not be able to install any other non-standard libraries.
<!--- section_3_text -->
## 1. Dataset Introduction
<!--- section_4_text -->
We will be asking you to use loan&#95;data dataset during this experiment. This data was collected in a major metropolitan city in the United States. It contains information about applications received for loans aggregated from several different loan providers.

<!--- section_5_text -->
Let's look at some of the columns in the dataframe. The column ``approved`` indicates whether or not the loan was approved

<!--- section_6_text -->
The column ``principal`` is the amount of money the loan was for, that is how much money the applicant received if the loan was approved.
<!--- section_7_text -->

``interest`` is the annual percent interest on the loan. 

``term`` is how long in months the loan was supposed to run.

 ``income`` is the annual income of the loan applicants.
