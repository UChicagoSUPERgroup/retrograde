from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
import yaml
import os


db = SQLAlchemy()
bootstrap = Bootstrap()

def create_app(config_path):
    with open(config_path, "r") as f:
        config = yaml.load(f)
    app = Flask(config.get("APP_NAME", __name__))
    app.config.update(config)
    app.url_map.strict_slashes = False # Don't auto redirect to urls ending in a slash
    app.debug = app.config.get('DEBUG', False)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://{user}:{password}@{host}:{port}/{name}'.format(
        user     = config["SQL"]["username"], 
        password = config["SQL"]["password"], 
        host     = config["SQL"]["host"],
        port     = config["SQL"]["port"],   
        name     = config["SQL"]["db"],             
    )
    db.init_app(app)
    bootstrap.init_app(app)

    from .redirect_to_notebook.views import MainView
    MainView.register(app)

    return app
