import os

from flask import current_app


def create_alias_dir(simulation):
    base_dir = current_app.simdb_config.get_option("server.upload_folder")

    # Make sure the aliases directory exists
    os.makedirs(os.path.join(base_dir, "aliases"), exist_ok=True)

    alias_path = os.path.join(base_dir, "aliases", simulation.alias)
    if not os.path.exists(alias_path):
        if "/" not in simulation.alias:
            os.symlink(os.path.join(base_dir, simulation.uuid.hex), alias_path)
        else:
            pieces = simulation.alias.split("/")
            last_bit = pieces[len(pieces) - 1]
            pieces.remove(last_bit)
            first_bit = base_dir + "/aliases/" + "/".join(pieces)
            os.makedirs(first_bit, exist_ok=True)
            os.symlink(
                os.path.join(base_dir, simulation.uuid.hex),
                os.path.join(base_dir, "aliases", simulation.alias),
            )
