#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pip install pyyaml
# pip install imas-python

try:
    import imaspy as imas
except ImportError:
    import imas
import argparse
import os
import re
from datetime import datetime

import yaml

try:
    from yaml import CLoader as Loader

except ImportError:
    from yaml import Loader


# TODO Add validation functions
# TODO Finalize names of the attributes in summary and dataset_description


replaces_re1 = re.compile(r"\d+/\d+")
replaces_re2 = re.compile(r"\((\d+),(\d+)\)(\s*-.*)?")


class Literal(str):
    pass


def literal_presenter(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(Literal, literal_presenter)


def load_yaml_file(yaml_file, Loader=yaml.SafeLoader):
    yaml_data = None
    try:
        with open(yaml_file, "r", encoding="utf-8") as file_handle:
            yaml_data = yaml.load(file_handle, Loader=Loader)
    except Exception as e:
        print(f"Error loading YAML file {yaml_file}: {e}")
    return yaml_data


def write_manifest_file(legacy_yaml_file: str, output_directory: str = None):

    legacy_yaml_data = load_yaml_file(legacy_yaml_file)
    dbentry_status = "obsolete"
    if "status" in legacy_yaml_data:
        dbentry_status = legacy_yaml_data["status"]
    if dbentry_status == "active":

        shot = legacy_yaml_data["characteristics"]["shot"]
        run = legacy_yaml_data["characteristics"]["run"]
        uri_mdsplus = f"imas:mdsplus?path=/work/imas/shared/imasdb/ITER/3/{shot}/{run}"
        uri = uri_hdf5 = f"imas:hdf5?path=/work/imas/shared/imasdb/ITER/3/{shot}/{run}"

        connection = None
        try:
            connection = imas.DBEntry(uri_hdf5, "r")
        except Exception as e:
            try:
                connection = imas.DBEntry(uri_mdsplus, "r")
                uri = uri_mdsplus
            except Exception as e:
                pass
        if connection is not None:
            ids_summary = None
            try:
                ids_summary = connection.get("summary", autoconvert=False, lazy=True)
            except Exception as e:
                pass
            ids_dataset_description = None
            try:
                ids_dataset_description = connection.get("dataset_description", autoconvert=False, lazy=True)
            except Exception as e:
                pass

        manifest_metadata = {}

        dataset_description = {}
        dataset_description["uri"] = uri
        if legacy_yaml_data["characteristics"]["type"] == "experimental":
            dataset_description["type"] = {"name": "experimental", "index": 1, "description": ""}
        elif legacy_yaml_data["characteristics"]["type"] == "experimental":
            dataset_description["type"] = {"name": "simulation", "index": 2, "description": ""}
        elif legacy_yaml_data["characteristics"]["type"] == "predictive":
            dataset_description["type"] = {"name": "predictive", "index": 3, "description": ""}
        dataset_description["machine"] = legacy_yaml_data["characteristics"]["machine"]
        dataset_description["pulse"] = legacy_yaml_data["characteristics"]["shot"]

        simulation = {}
        simulation["workflow"] = legacy_yaml_data["characteristics"]["workflow"]
        dataset_description["simulation"] = simulation

        code = {}
        code["name"] = legacy_yaml_data["characteristics"]["workflow"]
        code["description"] = Literal(legacy_yaml_data["free_description"])
        dataset_description["code"] = code

        # TODO below attributes are not present in the dataset_description responsible_name, reference_name
        dataset_description["responsible_name"] = legacy_yaml_data["responsible_name"]
        dataset_description["reference_name"] = legacy_yaml_data["reference_name"]

        manifest_metadata["dataset_description"] = dataset_description

        summary = {}
        heating_current_drive = {}
        heating_current_drive["power_ec_calc"] = legacy_yaml_data["hcd"]["p_ec"]
        heating_current_drive["power_ic_calc"] = legacy_yaml_data["hcd"]["p_ic"]
        heating_current_drive["power_nbi_calc"] = legacy_yaml_data["hcd"]["p_nbi"]
        heating_current_drive["power_lh_calc"] = legacy_yaml_data["hcd"]["p_lh"]
        heating_current_drive["power_additional_calc"] = legacy_yaml_data["hcd"]["p_hcd"]
        summary["heating_current_drive"] = heating_current_drive

        global_quantities = {}
        global_quantities["h_mode_calc"] = legacy_yaml_data["scenario_key_parameters"]["confinement_regime"]
        global_quantities["b0_calc"] = legacy_yaml_data["scenario_key_parameters"]["magnetic_field"]
        global_quantities["main_species"] = legacy_yaml_data["scenario_key_parameters"]["main_species"]
        global_quantities["ip_calc"] = legacy_yaml_data["scenario_key_parameters"]["plasma_current"]
        global_quantities["density_peaking"] = legacy_yaml_data["scenario_key_parameters"].get("density_peaking", "tbd")
        summary["global_quantities"] = global_quantities

        local = {}
        local["separatrix"] = {}
        local["separatrix"]["zeff_calc"] = legacy_yaml_data["scenario_key_parameters"].get("sepmid_zeff", "tbd")
        local["separatrix"]["n_e_calc"] = legacy_yaml_data["scenario_key_parameters"].get(
            "sepmid_electron_density", "tbd"
        )

        local["magnetic_axis"] = {}
        local["magnetic_axis"]["zeff"] = legacy_yaml_data["scenario_key_parameters"].get("central_zeff", "tbd")
        local["magnetic_axis"]["n_e"] = legacy_yaml_data["scenario_key_parameters"].get(
            "central_electron_density", "tbd"
        )
        summary["local"] = local

        plasma_composition = legacy_yaml_data["plasma_composition"]
        species_list = []
        if isinstance(plasma_composition["species"], str):
            species_list = plasma_composition["species"].split()
        a_values = z_values = n_over_ntot_values = n_over_ne_values = n_over_n_maj_values = []
        if "a" in plasma_composition:
            if isinstance(plasma_composition["a"], str):
                a_values = [float(value) for value in plasma_composition["a"].split()]
            else:
                a_values = [plasma_composition["a"]]
        if "z" in plasma_composition:
            if isinstance(plasma_composition["z"], str):
                z_values = [float(value) for value in plasma_composition["z"].split()]
            else:
                z_values = [plasma_composition["z"]]
        if "n_over_ntot" in plasma_composition:
            if isinstance(plasma_composition["n_over_ntot"], str):
                n_over_ntot_values = [float(value) for value in plasma_composition["n_over_ntot"].split()]
            else:
                n_over_ntot_values = [plasma_composition["n_over_ntot"]]
        if "n_over_ne" in plasma_composition:
            if isinstance(plasma_composition["n_over_ne"], str):
                n_over_ne_values = [float(value) for value in plasma_composition["n_over_ne"].split()]
            else:
                n_over_ne_values = [plasma_composition["n_over_ne"]]
        if "n_over_n_maj" in plasma_composition:
            if isinstance(plasma_composition["n_over_n_maj"], str):
                n_over_n_maj_values = [float(value) for value in plasma_composition["n_over_n_maj"].split()]
            else:
                n_over_n_maj_values = [plasma_composition["n_over_n_maj"]]

        species_dict = {}
        for species in species_list:
            species_index = species_list.index(species)
            if a_values is not None and species_index < len(a_values):
                a_value = a_values[species_index]
            else:
                a_value = "tbd"

            if z_values is not None and species_index < len(z_values):
                z_value = z_values[species_index]
            else:
                z_value = "tbd"

            if n_over_ntot_values is not None and species_index < len(n_over_ntot_values):
                n_over_ntot_value = n_over_ntot_values[species_index]
            else:
                n_over_ntot_value = "tbd"

            if n_over_ne_values is not None and species_index < len(n_over_ne_values):
                n_over_ne_value = n_over_ne_values[species_index]
            else:
                n_over_ne_value = "tbd"

            if n_over_n_maj_values is not None and species_index < len(n_over_n_maj_values):
                n_over_n_maj_value = n_over_n_maj_values[species_index]
            else:
                n_over_n_maj_value = "tbd"

            species_dict[species] = {
                "a": a_value,
                "z": z_value,
                "n_over_ntot": n_over_ntot_value,
                "n_over_ne": n_over_ne_value,
                "n_over_n_maj": n_over_n_maj_value,
            }
        summary["plasma_composition"] = species_dict
        manifest_metadata["summary"] = summary
        creation_time = datetime.fromtimestamp(os.path.getctime(legacy_yaml_file)).strftime("%Y-%m-%d %H:%M:%S")

        out_data = {
            "version": 2,
            "creation_date": creation_time,
            "alias": str(shot) + "/" + str(run),
            "outputs": [{"uri": uri}],
            "inputs": [],
            "metadata": [{"values": manifest_metadata}],
        }

        # manifest_file_path = os.path.join(os.path.dirname(legacy_yaml_file), f"manifest_{shot:06d}{run:04d}.yaml")

        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        manifest_file_path = os.path.join(output_directory, f"manifest_{shot:06d}{run:04d}.yaml")

        with open(manifest_file_path, "w") as file:
            yaml.dump(out_data, file, default_flow_style=False, sort_keys=False)

        if connection:
            connection.close()
        print(".", end="")


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="---- Script to update legacy yaml files to manifest files ----")
    parser.add_argument(
        "--files",
        nargs="*",
        help="yaml metadata file",
        required=False,
    )
    parser.add_argument(
        "--folder",
        nargs="*",
        help="list of folders where to search for scenarios (recursive)",
        required=False,
    )
    parser.add_argument(
        "--output-directory",
        help="Directory to save manifest files",
        default=None,
    )
    args = parser.parse_args()

    if args.files is not None:
        files = args.files
        directory_list = files
    else:
        files = []
        if args.folder is not None:
            folder = args.folder
            directory_list = folder
        else:
            directory_list = [os.environ["IMAS_HOME"] + "/shared/imasdb/ITER/3"]
            directory_list.append(os.environ["IMAS_HOME"] + "/shared/imasdb/ITER/4")

            lowlevelVersion = os.environ["AL_VERSION"]
            lowlevelVersion = int(lowlevelVersion.split(".")[0])
            if lowlevelVersion < 4:
                directory_list = [os.environ["IMAS_HOME"] + "/shared/iterdb/3/0"]
            for folder_path in directory_list:
                for root, _, filenames in os.walk(folder_path):
                    for filename in filenames:
                        if filename.endswith(".yaml"):
                            files.append(os.path.join(root, filename))
    output_directory = args.output_directory
    if args.output_directory is None:
        output_directory = os.path.join(os.getcwd(), "manifest")
    for yaml_file in files:
        write_manifest_file(yaml_file, output_directory=output_directory)
    print(f"\nManifest files are written into  {output_directory}")
