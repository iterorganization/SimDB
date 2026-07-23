"""Database-backed simulation filtering and quantity selection endpoint."""

from typing import Annotated

from flask_restx import Namespace, Resource

from simdb.query import QueryType
from simdb.remote.core.auth import User, requires_auth
from simdb.remote.core.pydantic_utils import Body, pydantic_validate
from simdb.remote.core.typing import current_app
from simdb.remote.models import (
    PaginatedResponse,
    SimulationDataQuantityResult,
    SimulationDataQueryItem,
    SimulationDataQueryRequest,
)

api = Namespace("simulation-data-query", path="/")


def _filter_value(value) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return "" if value is None else str(value)


@api.route("/simulations/data/query")
class SimulationDataQuery(Resource):
    @requires_auth()
    @pydantic_validate(api)
    def post(
        self,
        user: User,
        body: Annotated[SimulationDataQueryRequest, Body()],
    ) -> PaginatedResponse[SimulationDataQueryItem]:
        """Filter simulations and retrieve quantities from stored metadata."""
        constraints = [
            (
                item.field,
                _filter_value(item.value),
                QueryType[item.operator.upper()],
            )
            for item in body.filters
        ]
        metadata_paths = list(dict.fromkeys(item.path for item in body.quantities))

        count, rows = current_app.db.query_meta_data(
            constraints,
            metadata_paths,
            limit=body.limit,
            page=body.page,
            sort_by=body.sort_by,
            sort_asc=body.sort_asc,
        )

        results = []
        for row in rows:
            metadata = {
                item["element"]: item["value"] for item in row.get("metadata", [])
            }
            quantities = {}
            missing = []
            for requested in body.quantities:
                if requested.path not in metadata:
                    missing.append(requested.name)
                    continue
                quantities[requested.name] = SimulationDataQuantityResult(
                    source=requested.source,
                    path=requested.path,
                    value=metadata[requested.path],
                )

            results.append(
                SimulationDataQueryItem(
                    uuid=row["uuid"],
                    alias=row["alias"],
                    datetime=row["datetime"],
                    quantities=quantities,
                    missing=missing,
                )
            )

        return PaginatedResponse[SimulationDataQueryItem](
            count=count,
            page=body.page,
            limit=body.limit,
            results=results,
        )
