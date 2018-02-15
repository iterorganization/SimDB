from flask import Flask, g, Blueprint, request, jsonify, Response

from .. import __version__
from ..database.database import Database, DatabaseError
from ..database.models import Simulation

api = Blueprint('api', __name__)


def error(message: str) -> Response:
    response = jsonify(error=message)
    response.status_code = 500
    return response


def get_db() -> Database:
    if not hasattr(g, 'db'):
        g.db = Database(Database.Type.POSTGRESQL, host="localhost", port=5432)
    return g.db


@api.route("/")
def index():
    return jsonify({"api": "simdb", "version": __version__})


@api.route("/reset")
def reset_db():
    get_db().reset()
    return jsonify({})


@api.route("/simulations", methods=["GET"])
def list_simulations():
    simulations = get_db().list()
    return jsonify([sim.data() for sim in simulations])


@api.route("/simulations", methods=["PUT"])
def ingest_simulation():
    data = request.get_json()
    if "simulation" not in data:
        return error("Simulation data not provided")
    simulation = Simulation.from_data(data["simulation"])
    get_db().insert(simulation)
    return jsonify({})


@api.route("/simulation/<string:sim_id>", methods=["GET"])
def get_simulation(sim_id):
    try:
        simulation = get_db().get(sim_id)
        return jsonify(simulation.data())
    except DatabaseError as err:
        return jsonify({"error": str(err)})


@api.route("/simulation/<string:sim_id>", methods=["DELETE"])
def delete_simulation(sim_id):
    try:
        get_db().delete(sim_id)
    except DatabaseError as err:
        return jsonify({"error": str(err)})


app = Flask(__name__)
app.register_blueprint(api, url_prefix="/api/v" + __version__)
