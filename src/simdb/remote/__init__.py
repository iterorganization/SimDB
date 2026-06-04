"""Remote module.

The remote module contains code for running a REST API which is used to provide a remote
endpoint to which simulations can be sent for staging and signing-off.
"""

from semantic_version import SimpleSpec

# Compatibility scheme for the latest API version, i.e. anything with the same major and
# minor version
COMPATIBILITY_SPEC = SimpleSpec("~=1.2.0")


# API constants
class APIConstants:
    LIMIT_HEADER = "simdb-result-limit"
    PAGE_HEADER = "simdb-page"
    SORT_BY_HEADER = "simdb-sort-by"
    SORT_ASC_HEADER = "simdb-sort-asc"
