import os
from app.app import create_app
from flask import request

config_file = os.path.abspath('config.yml')
app = create_app(config_file)


@app.after_request
def add_cors_headers(response):
    whitelist = ["https://l-uca.com/", "https://uchicago.co1.qualtrics.com/"]
    r = request.referrer

    if r in whitelist:
        response.headers.add("Access-Control-Allow-Origin", r[:-1])
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Headers", "Cache-Control")
        response.headers.add("Access-Control-Allow-Headers", "X-Requested-With")
        response.headers.add("Access-Control-Allow-Headers", "Authorization")
        response.headers.add("Access-Control-Allow-Headers", "backend_token")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")

    return response
if __name__ == '__main__':
    app.run(host="0.0.0.0")
