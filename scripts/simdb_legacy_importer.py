#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pip install pyyaml
# pip install imas-python
import sys
import logging

try:
    import imaspy as imas
except ImportError:
    import imas
import argparse
import os
import re
from datetime import datetime

import yaml

# TODO Add validation functions
# TODO Check workflow name and type is empty and matching with dataset_description.simulation.workflow
# TODO Finalize names of the attributes in summary and dataset_description
# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)  # Set default level

log_format = logging.Formatter("%(levelname)s - line %(lineno)d - %(message)s")

# --- File handler ---
file_handler = logging.FileHandler(f"{os.path.basename(__file__)}.log")
file_handler.setFormatter(log_format)
logger.addHandler(file_handler)

enable_console_logging = True  # Set this to False to disable console logs

if enable_console_logging:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

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
        logger.error(f"error loading YAML file {yaml_file}: {e}", exc_info=True)
    return yaml_data


def get_local(scenario_key_parameters: dict):
    local = {}
    local["separatrix"] = {}
    local["separatrix"]["zeff_calc"] = scenario_key_parameters.get("sepmid_zeff", "missing_key")
    local["separatrix"]["n_e_calc"] = scenario_key_parameters.get("sepmid_electron_density", "missing_key")

    local["magnetic_axis"] = {}
    local["magnetic_axis"]["zeff"] = scenario_key_parameters.get("central_zeff", "missing_key")
    local["magnetic_axis"]["n_e"] = scenario_key_parameters.get("central_electron_density", "missing_key")
    return local


def get_dataset_description(legacy_yaml_data: dict):
    dataset_description = {}
    shot = legacy_yaml_data["characteristics"]["shot"]
    run = legacy_yaml_data["characteristics"]["run"]
    alias = str(shot) + "/" + str(run)

    dataset_description["uri"] = f"imas:hdf5?path=/work/imas/shared/imasdb/ITER/3/{shot}/{run}"
    # TODO check what is predictive means here. as per 4.0.0 we have expermiental and
    # simulation as a type (Some places it is tbd)
    # TODO we also had workflow type does it different from pulse type. It seems both are same
    # so just adding type in dataset_description
    # and dropping workflow type
    if legacy_yaml_data["characteristics"]["type"] == "experimental":
        dataset_description["type"] = {"name": "experimental", "index": 1, "description": ""}
    elif legacy_yaml_data["characteristics"]["type"] == "simulation":
        dataset_description["type"] = {"name": "simulation", "index": 2, "description": ""}
    elif legacy_yaml_data["characteristics"]["type"] == "predictive":
        dataset_description["type"] = {"name": "predictive", "index": 3, "description": ""}
    else:
        dataset_description["type"] = {"name": "simulation", "index": 2, "description": ""}
    dataset_description["machine"] = legacy_yaml_data["characteristics"]["machine"]

    dataset_description["pulse"] = legacy_yaml_data["characteristics"]["shot"]

    simulation = {}
    simulation["workflow"] = legacy_yaml_data["characteristics"]["workflow"]
    dataset_description["simulation"] = simulation

    code = {}
    code["name"] = legacy_yaml_data["characteristics"]["workflow"]
    code["description"] = Literal(legacy_yaml_data["free_description"])
    dataset_description["code"] = code

    # TODO when we have single time step do we need to add time_step in dataset_description?
    if "summary" in legacy_yaml_data["idslist"]:
        start = end = step = 0.0
        if "start_end_step" in legacy_yaml_data["idslist"]["summary"]:
            start, end, step = legacy_yaml_data["idslist"]["summary"]["start_end_step"][0].split()
        elif "time" in legacy_yaml_data["idslist"]["summary"]:
            start = end = legacy_yaml_data["idslist"]["summary"]["time"][0]
            step = 0.0
        try:
            start = float(start)
            end = float(end)
            dataset_description["pulse_time_begin_epoch"] = {
                "seconds": round(start),
                "nanoseconds": (start - round(start)) * 10**9,
            }
            dataset_description["pulse_time_end_epoch"] = {
                "seconds": round(end),
                "nanoseconds": (end - round(end)) * 10**9,
            }
            dataset_description["simulation"] = {
                "time_begin": start,
                "time_end": end,
            }
        except ValueError as e:
            logger.error(f"{alias}:{e}")

        try:
            dataset_description["simulation"]["time_step"] = float(step)
        except ValueError as e:
            logger.error(f"{alias}:{e}")

    # TODO below attributes are not present in the dataset_description responsible_name, reference_name
    # TODO dataset_description or summary/ids_properties/provider contains the linux name of the user.
    # How to enforce user to store actual name/email ID of the person
    dataset_description["responsible_name"] = legacy_yaml_data["responsible_name"]
    dataset_description["reference_name"] = legacy_yaml_data["reference_name"]

    return dataset_description


def get_heating_current_drive(legacy_yaml_data: dict):
    heating_current_drive = {}
    # for isource in range(n_ic):
    #         if len(summary.heating_current_drive.ic[isource].power.value) > 0:
    #             p_ic = p_ic + max(summary.heating_current_drive.ic[isource].power.value) * 1.0e-6
    heating_current_drive["power_ec_total"] = legacy_yaml_data["hcd"]["p_ec"]
    heating_current_drive["power_ic_total"] = legacy_yaml_data["hcd"]["p_ic"]
    heating_current_drive["power_nbi_total"] = legacy_yaml_data["hcd"]["p_nbi"]
    heating_current_drive["power_lh_total"] = legacy_yaml_data["hcd"]["p_lh"]
    heating_current_drive["power_additional_total"] = legacy_yaml_data["hcd"]["p_hcd"]
    return heating_current_drive


def get_plasma_composition(plasma_composition):

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
    return species_dict


def get_global_quantities(legacy_yaml_data: dict):
    # TODO should we keep h_mode_derived or confinement_regime. h_mode is time based array
    # and mode is calculaed from the time based array
    # Beow isthe code
    # if len(summary.global_quantities.h_mode.value) > 0:
    #     foo = ""
    #     nt = len(summary.global_quantities.h_mode.value)
    #     for it in range(nt):
    #         if summary.global_quantities.h_mode.value[it] == 1:
    #             foo = foo + "H"
    #         else:
    #             foo = foo + "L"
    #     confinement_regime = "".join(
    #         [foo[i] + "-" for i in range(len(foo) - 1) if foo[i + 1] != foo[i]] + [foo[-1]]
    #     )
    #     if len(confinement_regime) > 5:
    #         confinement_regime = confinement_regime[0:5]
    #     if len(confinement_regime) == 1:
    #         confinement_regime = confinement_regime + "-mode"
    # TODO Should we also keep as scenario_key_parameters as part of summary
    global_quantities = {}
    global_quantities["h_mode_derived"] = legacy_yaml_data["scenario_key_parameters"]["confinement_regime"]
    global_quantities["b0_calc"] = legacy_yaml_data["scenario_key_parameters"]["magnetic_field"]
    global_quantities["main_species"] = legacy_yaml_data["scenario_key_parameters"]["main_species"]
    global_quantities["ip_calc"] = legacy_yaml_data["scenario_key_parameters"]["plasma_current"]
    global_quantities["density_peaking"] = legacy_yaml_data["scenario_key_parameters"].get(
        "density_peaking", "missing_key"
    )
    global_quantities["power_loss_total"] = legacy_yaml_data["hcd"].get("p_sol", "missing_key")
    return global_quantities


def write_manifest_file(legacy_yaml_file: str, output_directory: str = None):

    legacy_yaml_data = load_yaml_file(legacy_yaml_file)
    dbentry_status = "obsolete"
    if "status" in legacy_yaml_data:
        dbentry_status = legacy_yaml_data["status"]
    if dbentry_status == "active":

        shot = legacy_yaml_data["characteristics"]["shot"]
        run = legacy_yaml_data["characteristics"]["run"]
        alias = str(shot) + "/" + str(run)
        data_entry_path_parts = legacy_yaml_file.strip("/").split("/")
        folder_path = "/" + "/".join(data_entry_path_parts[:6])
        uri_mdsplus = f"imas:mdsplus?path=/{folder_path}/{shot}/{run}"
        uri = uri_hdf5 = f"imas:hdf5?path=/{folder_path}/{shot}/{run}"

        connection = None
        try:
            connection = imas.DBEntry(uri_hdf5, "r")
        except Exception as e:  #
            logger.error(f"{alias} {uri_hdf5}: {e}")
            exit(0)
            try:
                connection = imas.DBEntry(uri_mdsplus, "r")
                uri = uri_mdsplus
            except Exception as e:
                logger.error(f"{alias} {uri_mdsplus}: {e}")
        if connection is not None:
            ids_summary = None
            try:
                ids_summary = connection.get("summary", autoconvert=False, lazy=True)
            except Exception as e:
                logger.error(f"{alias}: {e}")
            ids_dataset_description = None
            try:
                ids_dataset_description = connection.get("dataset_description", autoconvert=False, lazy=True)
            except Exception as e:
                logger.error(f"{alias}: {e}")

        manifest_metadata = {}

        manifest_metadata["dataset_description"] = get_dataset_description(legacy_yaml_data=legacy_yaml_data)
        summary = {}
        summary["heating_current_drive"] = get_heating_current_drive(legacy_yaml_data)
        summary["global_quantities"] = get_global_quantities(legacy_yaml_data)
        summary["local"] = get_local(legacy_yaml_data["scenario_key_parameters"])
        summary["plasma_composition"] = get_plasma_composition(legacy_yaml_data["plasma_composition"])
        manifest_metadata["summary"] = summary

        # TODO get from summary ids
        creation_time = datetime.fromtimestamp(os.path.getctime(legacy_yaml_file)).strftime("%Y-%m-%d %H:%M:%S")

        out_data = {
            "version": 2,
            "creation_date": creation_time,
            "alias": alias,
            "outputs": [{"uri": uri}],
            "inputs": [],
            "metadata": [{"values": manifest_metadata}],
        }

        # manifest_file_path = os.path.join(os.path.dirname(legacy_yaml_file), f"manifest_{shot:06d}{run:04d}.yaml")

        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        manifest_file_path = os.path.join(output_directory, f"manifest_{shot:06d}{run:04d}.yaml")

        with open(manifest_file_path, "w") as file:
            yaml.dump(out_data, file, default_flow_style=False, sort_keys=True)

        if connection:
            connection.close()
        sys.stdout.write(".")
        sys.stdout.flush()


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
    logger.info(f"\nManifest files are written into  {output_directory}")
