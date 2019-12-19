# Project Outline

This is a Jupyter Lab plugin which will prompt users to characterize process-relevant aspects of cells within Jupyter notebooks. 
These characterizations will be minimal, things like "what are you trying to do or find out in this cell?". 
By collecting these sorts of cell characterizations, we will be able to use these to automatically build narratives about how the notebook user approached their project. 

## Project Architecture

This project has two components. 
A front end handling notebook interactions and a back end which stores tracked notebook interactions and identifies when the user should be prompted to explain what they are trying to do or did. 

### Front end

The front end is implemented as a Jupyter lab plug in in typescript.
In this repository, it is in the prompt-ml directory. 
Currently, it just makes an HTTP request to the server extension (the back end) whenever a cell is executed.

To fully implement this plug in it will need to not just make the request, but also listen for prompts from the back end.
I think the best way to do this is to have the back end check which cells should be prompted whenever the front end makes a request, and encode that in the response.

We will need to implement both the response listening mechanism, as well as the actual interface by which the user will be prompted.

### Back end

The back end stores information about cell contents and executions sent by the front end.
It is a jupyter lab server extension, meaning that it is a python package with additional characteristics.
Right now it just responds to the GET requests. 

It will need to store the contents of the cells in a database as well as contain a mechanism for determining which cells need characterization.

# Helpful examples

[Jupyter lab code formatter](https://github.com/ryantam626/jupyterlab_code_formatter)
[Verdant](https://github.com/mkery/Verdant/blob/master/src/lilgit/jupyter-hooks/notebook-listen.ts)
