from flask_restx import Api

from ...core.auth import HEADER_NAME
from .simulations import api as sim_ns
from ..files import api as file_ns
from ..metadata import api as metadata_ns
from ..watchers import api as watcher_ns


api = Api(
    title='SimDB REST API',
    version='1.1',
    description='SimDB REST API',
    authorizations={
        'basicAuth': {
            'type': 'basic',
        },
        'apiToken': {
            'type': 'apiKey',
            'in': 'header',
            'name': HEADER_NAME,
        }
    },
    security=['basicAuth', 'apiToken'],
    doc='/docs'
)

api.add_namespace(sim_ns)
namespaces = [metadata_ns, watcher_ns, file_ns, sim_ns]
