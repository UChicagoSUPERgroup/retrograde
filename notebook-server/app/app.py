from flask import Flask, redirect, url_for
import yaml
import os


def create_app(config_path):
    with open(config_path, "r") as f:
        config = yaml.load(f)
    app = Flask(config.get("APP_NAME", __name__))
    app.config.update(config)
    app.url_map.strict_slashes = False # Don't auto redirect to urls ending in a slash
    app.debug = app.config.get('DEBUG', False)

    from .redirect_to_notebook.views import MainView
    MainView.register(app)

    return app
