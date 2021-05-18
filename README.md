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


# Up and Running. Making the Test Environment

To create a test environment, first install [miniconda3](https://docs.conda.io/projects/conda/en/latest/user-guide/install/macos.html) and mysql. 

Once miniconda and mysql have been installed, run the following command to create a conda environment for the jupyter kernal which contains numpy, sci-py, and scikit-learn (the reason these are installed outside of pip [is discussed here](https://github.com/scikit-learn/scikit-learn/issues/18852)).

	conda create -n plugin_conda python=3.9 numpy scipy scikit-learn
	
Once your conda environment is created, run the `test_build.sh` script to build install the jupyter lab plugin and serverextension, and configure the server extension to connect to your local mysql database. 

	source ./test_build.sh


# Build Instruction

This extension is best developed using a python virtual environment.
This is because fully testing the front and back end requires installing the backend as a library accessible to jupyter.

To set up the virtual environment:

```bash
git clone https://bitbucket.org/galen_harrison/prompt-ml.git
cd prompt-ml
python3 -m venv .
source bin/activate
pip3 install jupyterlab
```
This only needs to happen once. 
After this step, you can just use source bin/activate and deactivate to start the environment.
To run jupyterlab, from the prompt-ml directory: 

```bash
source bin/activate
jupyter lab .
```
In order to install the front end plugin, from the top level directory:

```bash
cd ./prompt-ml
jlpm install
jupyter labextension install --no-build
```

To install the back end plugin from the top level directory, while in the virtual environment:

```bash
cd ./serverextension
python3 setup.py sdist bdist_wheel
pip3 install -U -I dist/prompter-0.1-py3-none-any.whl
jupyter serverextension enable --py prompter --sys-prefix --debug
jupyter serverextension list
```

To test the installation, go back to the top level directory in this repo, and run `jupyter lab .`.
This should open a browser window with the jupyter lab environment. 
Open a new python notebook, enter some python code and execute the cell.
If you look in the log, you should see whatever code you wrote down echoed in the console.

For example, the cell I executed was 

```python
print("hello world")
```

so the output I saw was

```python
{'contents': 'print("hello world")', 'id': '2ce8fc3c-1f65-4294-b23f-c267e5db91d0'}
```


## Build Instruction

Testing image build locally

When debugging deployment issues, it is sometimes useful to run the image locally.
The networking capabilities differ on linux and Mac, but I was able to run it by
using

```bash
docker run --env JP_PLUGIN_USER="test_user" --env MODE="EXP_CTS" --env DOCKER_HOST_IP="127.0.0.1" --env TOKEN="test_user" --env PLUGIN_PORT=8889 -p 8889:8889 -it {IMAGE_NAME} bash ./run_image.sh 
```

You may need to select an unused port though
# Helpful examples

[Jupyter lab code formatter](https://github.com/ryantam626/jupyterlab_code_formatter)
[Verdant](https://github.com/mkery/Verdant/blob/master/src/lilgit/jupyter-hooks/notebook-listen.ts)
