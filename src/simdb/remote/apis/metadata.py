from flask_restx import Namespace, Resource

from simdb.remote.core.cache import cache, cache_key
from simdb.remote.core.pydantic_utils import pydantic_validate
from simdb.remote.core.typing import current_app
from simdb.remote.models import MetadataKeyInfoList, MetadataValueList

api = Namespace("metadata", path="/")


@api.route("/metadata")
class MetaData(Resource):
    @cache.cached(key_prefix=cache_key)  # type: ignore
    @pydantic_validate(api)
    def get(self) -> MetadataKeyInfoList:
        return MetadataKeyInfoList.model_validate(current_app.db.list_metadata_keys())


@api.route("/metadata/<string:name>")
class MetaDataValues(Resource):
    @cache.cached(key_prefix=cache_key)  # type: ignore
    @pydantic_validate(api)
    def get(self, name: str) -> MetadataValueList:
        return MetadataValueList.model_validate(
            current_app.db.list_metadata_values(name)
        )
