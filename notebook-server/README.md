# Note Book Server

It serves the notebook with the extension on different ports for the qualtrics survey.

Because the app needs to scan the machine it is running on for open ports, it needs to be run under a user with permission to scan for open ports (generally root). 

To run the app:

	pipenv run sudo python wsgi.py

	source scripts/clean-up.sh

<https://jupyter-docker-stacks.readthedocs.io/en/latest/>