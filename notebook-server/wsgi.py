import os
from app.app import create_app


config_file = os.path.abspath('config.yml')
app = create_app(config_file)

if __name__ == '__main__':
    app.run(host="0.0.0.0")