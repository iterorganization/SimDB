from flask import jsonify, Response


def error(message: str) -> Response:
    response = jsonify(error=message)
    response.status_code = 500
    return response
