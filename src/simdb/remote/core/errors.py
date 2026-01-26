from flask import Response, jsonify


def error(message: str) -> Response:
    response = jsonify(error=message)
    response.status_code = 400
    return response
