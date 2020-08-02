# Note Book ServerThis is a flask app that spins up docker containers when visited. 

It serves the notebook with the extension on different ports for the qualtrics survey.

Because the app needs to scan the machine it is running on for open ports, it needs to be run under a user with permission to scan for open ports (generally root). 

To run the app:

	pipenv shell
	#if requirments do not install automatically
	pip install -r requirements.txt
	sudo python wsgi.pyThis section of the project is not fully flushed out but works surprsingly well. Before running you should install docker and get the test docker image that this project is using from here: 

<https://jupyter-docker-stacks.readthedocs.io/en/latest/>