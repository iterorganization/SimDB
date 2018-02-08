from flask import Flask
import flask.json as json
app = Flask(__name__)


@app.route('/')
def hello_world():
    return json.jsonify({"message": "Hello, World!"})
