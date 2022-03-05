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

It stores the contents of the cells in a database as well as contains a mechanism for determining which cells need characterization.

# Up and Running. Making the Test Environment

To create a test environment, first install [miniconda3](https://docs.conda.io/projects/conda/en/latest/user-guide/install/macos.html) and mysql. 

Once miniconda and mysql have been installed, run the following command to create a conda environment for the jupyter kernal which contains numpy, sci-py, and scikit-learn (the reason these are installed outside of pip [is discussed here](https://github.com/scikit-learn/scikit-learn/issues/18852)).

	conda create -n plugin_conda python=3.9 numpy scipy scikit-learn
	
Once your conda environment is created, run the `test_build.sh` script to build install the jupyter lab plugin and serverextension, and configure the server extension to connect to your local mysql database. 

	source ./test_build.sh

This will open a Jupyter lab instance. You may be prompted to enter your password for your MySQL server to create the database and tables.
**If you are running this for the first time, or making modifications to the frontend code** you should set ```BUILD_FRONTEND=1``` before executing the test_build script.
This causes the frontend components to build, which can take up to two minutes. 
If you are running this after making changes to the backend, you can reset the bash variable to save some time.

Once the Jupyter lab window opens, you may need to reload the page if it does not open with an open notebook.
Running this locally, you must select the ```prompter``` kernel from the dropdown menu in order for the plugin to work. 

# Docker Build

This plugin is packaged in a docker container. 
To build the docker image, in the jupyter_plugin directory run 

```bash
docker build .
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

## Deployment Instructions

You will need to find a webserver with docker and mysql installed. You may also need to run individually the ```make_db.sql``` and ```make_tables.sql``` scripts in the jupyter_lab_plugin/serverextension/prompter folder.

The mysql database will need to have a user named "prompter_user", open on localhost, with password "user_pw". You will also need to have a user with permissions to create databases and tables in mysql. 

Once these are installed, it is necessary to transfer the docker image built through to the web server.  If you are building the image somewhere else, ie. on your local machine, then you will need to make the image available by pulling it to the web server. You will need to tag the image with a meaningful tag, and then push it to dockerhub. 

```bash
docker push gsamharrison/plugin-test:tagname
```

and 

```bash
docker pull gsamharrison/plugin-test:tagname
```

Then in notebook-server/, copy over config.yml.tmpl to config.yml, fill out the SQL fields with the information about the connection (do not worry about the Secret Key field), and change the IMAGE field to gsamharrison/plugin-test:tagname. 

Then to run the webserver, run pipenv run python3 wsgi.py. This starts the webserver on port 5000.

To test the server, go to (hostname)>:5000/(USER_ID)/(MODE). (MODE) is either EXP_CTS or EXP_END and USER_ID can be anything you want. It's helpful to make it relatively unique as it will enable us to debug any issues that may arise. 
	
**Note**: the webapp runs the containers in host mode, where the containers and host share the same network interface. This allows the containers to access mysql on localhost, without requiring the mysql database be exposed on other IP addresses. 

# Helpful examples

[Jupyter lab code formatter](https://github.com/ryantam626/jupyterlab_code_formatter)
[Verdant](https://github.com/mkery/Verdant/blob/master/src/lilgit/jupyter-hooks/notebook-listen.ts)
