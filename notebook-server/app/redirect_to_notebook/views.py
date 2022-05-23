from flask_classy import FlaskView, route
from flask import Flask, redirect, current_app, render_template, request, abort
import random
import string
import requests
from app.make_notebook import start_notebook, stop_notebook
from .models import UsersContainers
from datetime import date
from requests.exceptions import ConnectionError
import math
import time

INVALID_PROLIFIC_ID_ERROR = 'Error, Invalid Prolific ID Specified'
CONTAINER_STOPPED_MESSAGE = 'Container Stopped'
CONTAINER_ALREADY_STOPPED_MESSAGE = 'Container was already stopped'
NOTEBOOK_NAME = "notebook_dist.ipynb"


class MainView(FlaskView):
    route_base = '/'
    tokens = []

    # Expects two GET parameters, specifically <URL>?prolific_id=<PROLIFIC ID>&mode=<EXP MODE>
    @route('/', methods=['GET'])
    def handle_request(self):
        '''
        Handles getting and creating containers and corresponding db entry

        This method/route is responsible for creating prolic-id container pairs
        when a new prolific-id is given. If a prolific id already exists in the 
        database, the corresponding container is returned if it is running. If
        a prolific ID's container is not running, then it is assumed that the user
        has completed the survey.
        '''
        if not ("id" in request.args and "mode" in request.args and "auth_token" in request.args):
            return render_template('bad_req.html')
        if not self.auth_token(request.args["auth_token"]):
            return render_template('bad_auth.html')
        prolific_id = request.args["id"]
        mode = request.args["mode"]
        hostname = current_app.config['HOSTNAME']
        is_testing = current_app.config['TESTING']
        if is_testing.lower() == 'true':
            is_testing = True
        elif is_testing.lower() == 'false':
            is_testing = False
        else:
            raise ValueError("Testing Configuration Variable must be string 'True' or 'False'")
        docker_image = current_app.config['IMAGE']

        if prolific_id is None:
            return INVALID_PROLIFIC_ID_ERROR, 404       
        prolific_id_exists = UsersContainers.check_if_prolific_id_exists(prolific_id)
        build_redirect_url = lambda hostname, port, prolific_id : f'{hostname}:{port}/lab/tree/{NOTEBOOK_NAME}?token={prolific_id}'
        if not prolific_id_exists:
            #this is a new user, create a container
            port, container = start_notebook(docker_image = docker_image, prolific_id=prolific_id, mode=mode, test_configuration=is_testing)
            redirect_url = build_redirect_url(hostname, port, prolific_id)
            UsersContainers.handle_new_entry(prolific_id, container, port, True)
            print(f'redirecting to "{redirect_url}"...')
            #Sleep for 10 seconds to make sure jupyter lab is booted
            #TODO: find a non-hacky way to do this
            return render_template('redirect.html', 
                                   redirect_url=redirect_url,
                                   time_till_redirect=10)
        else:
            running = UsersContainers.check_if_container_running(prolific_id)
            if running:
                #if the container is running, redirect to the container
                port = UsersContainers.get_port(prolific_id)
                redirect_url = build_redirect_url(hostname, port, prolific_id)
                return redirect(redirect_url)
            else:
                #this user with has completed survey. Return message saying they are done
                return 'Sorry, this prolific ID has already been used to complete the survey.', 404

    @route('/kill/<prolific_id>', methods=['GET'])
    def handle_kill_request(self, prolific_id):
        '''
        Handles Stopping a Container By Prolific ID

        TODO: This should probably be a DELETE request instead of a GET request.
        But for the sake of ease of development I made it a get request so 
        I can test with browser.
        '''
        prolific_id_exists = UsersContainers.check_if_prolific_id_exists(prolific_id)
        if prolific_id_exists:
            container_id = UsersContainers.get_container_id(prolific_id)
            running = UsersContainers.check_if_container_running(prolific_id)
            if running:
                #stop cotainer and mark container as not running
                stop_notebook(container_id)
                UsersContainers.update_container_not_running(prolific_id)
                return CONTAINER_STOPPED_MESSAGE, 200
            else:
                return CONTAINER_ALREADY_STOPPED_MESSAGE, 200

        return INVALID_PROLIFIC_ID_ERROR, 404

    @route('/auth/', methods=['POST'])
    def handle_auth_request(self):
        val = request.form.get("backend_token")
        if val == None:
            abort(400, "Malformed format.")
        if  val != "Ggfkhltoh0U9vJt4":
            abort(403, "False auth.")
        new_token = self.gen_token()
        return new_token

    def gen_token(self):
        x = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(16))
        while x in self.tokens:
            x = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(16))
        self.tokens.append(x)
        return x

    def auth_token(self, token):
        if not token in self.tokens:
            return False
        self.tokens.remove(token)
        return True