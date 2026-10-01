"""Helpers shared by the CLI tests.

Kept out of ``conftest.py`` because pytest imports every ``conftest`` under
the same module name, so importing from it directly picks up whichever one
was loaded first.
"""

from typing import Optional
from unittest import mock


def make_simulation(
    alias: str,
    uuid: str = "0123456789abcdef0123456789abcdef",
    datetime: str = "2000-01-01 00:00:00",
    status: str = "not validated",
    meta: Optional[dict] = None,
) -> mock.Mock:
    """Build a stand-in for a :class:`~simdb.database.models.Simulation`.

    Only the attributes the CLI display code touches are set; ``find_meta``
    answers from ``meta`` the same way the real model does (a list of objects
    with a ``value``, empty when the name is unknown).
    """
    simulation = mock.Mock()
    simulation.alias = alias
    simulation.uuid = uuid
    simulation.datetime = datetime
    simulation.status = status
    meta = meta or {}
    simulation.find_meta.side_effect = lambda name: (
        [mock.Mock(value=meta[name])] if name in meta else []
    )
    return simulation
