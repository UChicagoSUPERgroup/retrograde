from flask_classy import FlaskView, route
from flask import Flask, redirect
from app.make_notebook import start_notebook 
from .models import PatronCount, PATRON_TYPES
from datetime import date
import math

class MainView(FlaskView):
    route_base = '/'

    @route('/', methods=['GET'])
    def handle_request(self):
        '''Handles all requests for registering people with the check-in
        app. This function is routed to /main/'''       
        port = start_notebook()
        redirect_url = 'http://localhost:'+str(port)
        return redirect(redirect_url)
