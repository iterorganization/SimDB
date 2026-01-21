import os

from simdb.remote.core.typing import current_app


def create_alias_dir(simulation):
    base_dir = current_app.simdb_config.get_option("server.upload_folder")

    # Make sure the aliases directory exists
    os.makedirs(os.path.join(base_dir, "aliases"), exist_ok=True)

    alias_path = os.path.join(base_dir, "aliases", simulation.alias)
    if not os.path.exists(alias_path):
        if "/" in simulation.alias:
            pieces = simulation.alias.split("/")
            pieces = pieces[:-1]
            first_bit = os.path.join(base_dir, "aliases", *pieces)
            os.makedirs(first_bit, exist_ok=True)

        os.symlink(os.path.join(base_dir, simulation.uuid.hex), alias_path)
