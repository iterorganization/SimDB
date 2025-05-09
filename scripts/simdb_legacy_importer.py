#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
simdb_legacy_importer.py

This script is designed to update legacy YAML metadata files into manifest files. It validates and processes data
from YAML files and IMAS database entries, generating manifest files with updated metadata.

Command-line Arguments:
    --files: List of YAML metadata files to process.
    --folder: List of folders to search for YAML files recursively.
    --output-directory: Directory to save the generated manifest files.

Usage:
    Run the script with the appropriate command-line arguments to process YAML files and generate manifest files.

Example:
    python simdb_legacy_importer.py
    python simdb_legacy_importer.py --files file1.yaml file2.yaml --output-directory ./manifests

Notes:
    - The script validates data consistency between YAML files and IMAS database entries.
    - Validation errors and warnings are logged into separate log files.
    - The script supports both experimental and simulation data.

Dependencies:
    - pyyaml: For YAML file handling. pip install pyyaml
    - imas-python: For interacting with IMAS database entries. pip install imas-python
"""


import logging
import sys

try:
    import imaspy as imas
except ImportError:
    import imas
import argparse
import os
from datetime import datetime

import numpy as np
import yaml

enable_console_logging = False
output_directory = "simdb_legacy_importer_logs"
os.makedirs(output_directory, exist_ok=True)
validation_log_path = os.path.join(output_directory, "simdb_legacy_importer_validation.log")
error_log_path = os.path.join(output_directory, "simdb_legacy_importer_error.log")
validation_logger = logging.getLogger("validation_logger")
validation_logger.setLevel(logging.INFO)
validation_handler = logging.FileHandler(validation_log_path, mode="w")
validation_handler.setFormatter(logging.Formatter("%(message)s"))
validation_logger.addHandler(validation_handler)
if enable_console_logging:
    validation_console_handler = logging.StreamHandler(sys.stdout)
    validation_console_handler.setFormatter(logging.Formatter("%(message)s"))
    validation_logger.addHandler(validation_console_handler)
error_logger = logging.getLogger("error_logger")
error_logger.setLevel(logging.ERROR)
error_handler = logging.FileHandler(error_log_path, mode="w")
error_handler.setFormatter(logging.Formatter("%(levelname)s - line %(lineno)d - %(message)s"))
error_logger.addHandler(error_handler)

if enable_console_logging:
    error_console_handler = logging.StreamHandler(sys.stdout)
    error_console_handler.setFormatter(logging.Formatter("%(levelname)s - line %(lineno)d - %(message)s"))
    error_logger.addHandler(error_console_handler)
# -----------------------------------------------------------------------------------------------------


class Literal(str):
    pass


def literal_presenter(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(Literal, literal_presenter)


def load_yaml_file(yaml_file, Loader=yaml.SafeLoader):
    if not os.path.exists(yaml_file):
        error_logger.error(f"YAML file {yaml_file} does not exist")
        return None
    yaml_data = None
    try:
        with open(yaml_file, "r", encoding="utf-8") as file_handle:
            yaml_data = yaml.load(file_handle, Loader=Loader)
    except Exception as e:
        error_logger.error(f"error loading YAML file {yaml_file}: {e}", exc_info=True)
    return yaml_data


def get_central_electron_density(ids_core_profiles):
    slice_index = 0
    ne0_raw = []
    for t in range(len(ids_core_profiles.time)):
        ne0_raw.append(ids_core_profiles.profiles_1d[t].electrons.density[0])
    ne0 = np.array(ne0_raw)
    central_electron_density = 0
    for islice in range(len(ne0)):
        if ne0[islice] > central_electron_density:
            central_electron_density = ne0[islice]
            slice_index = islice
    return central_electron_density, slice_index


def get_sepmid_electron_density(ids_summary):
    slice_index = 0
    ne_sep = ids_summary.local.separatrix.n_e.value
    sepmid_electron_density = 0
    for islice in range(len(ne_sep)):
        if ne_sep[islice] > sepmid_electron_density:
            sepmid_electron_density = ne_sep[islice]
            slice_index = islice
    return sepmid_electron_density, slice_index


def get_power_loss(ids_summary, slice_index):
    p_sol = np.nan
    debug_info = ""
    if hasattr(ids_summary.global_quantities, "power_loss"):

        debug_info += "\n\t> ids_summary.global_quantities.power_loss.value : "
        f"{ids_summary.global_quantities.power_loss.value.value}"
        if len(ids_summary.global_quantities.power_loss.value) > 0:
            p_sol = ids_summary.global_quantities.power_loss.value[slice_index]
    return p_sol, debug_info


def get_confinement_regime(ids_summary):
    confinement_regime = ""
    debug_info = ""
    if len(ids_summary.global_quantities.h_mode.value) > 0:

        foo = ""
        nt = len(ids_summary.global_quantities.h_mode.value)
        for it in range(nt):
            if ids_summary.global_quantities.h_mode.value[it] == 1:
                foo = foo + "H"
            else:
                foo = foo + "L"
        debug_info = f"\n\t> ids_summary.global_quantities.h_mode.value : {foo}"
        confinement_regime = "".join([foo[i] + "-" for i in range(len(foo) - 1) if foo[i + 1] != foo[i]] + [foo[-1]])
        if len(confinement_regime) > 5:
            confinement_regime = confinement_regime[0:5]
        if len(confinement_regime) == 1:
            confinement_regime = confinement_regime + "-mode"
    else:
        debug_info += "\n\t> ids_summary.global_quantities.h_mode is empty"
    return confinement_regime, debug_info


def get_magnetic_field(ids_summary, ids_equilibrium):
    magnetic_field = np.nan
    magnetic_field_equilibrium = 0
    magnetic_field_summary = 0
    debug_info = ""
    if ids_equilibrium:
        debug_info += (
            f"\n\t> ids_equilibrium.vacuum_toroidal_field.b0 : {ids_equilibrium.vacuum_toroidal_field.b0.value}"
        )
        if len(ids_equilibrium.vacuum_toroidal_field.b0) > 0:
            if min(np.sign(ids_equilibrium.vacuum_toroidal_field.b0)) < 0:
                magnetic_field_equilibrium = min(ids_equilibrium.vacuum_toroidal_field.b0)
            else:
                magnetic_field_equilibrium = max(ids_equilibrium.vacuum_toroidal_field.b0)
            magnetic_field = magnetic_field_equilibrium
    if ids_summary:
        debug_info += f"\n\t> ids_summary.global_quantities.b0.value : {ids_summary.global_quantities.b0.value.value}"
        if len(ids_summary.global_quantities.b0.value) > 0:
            if min(np.sign(ids_summary.global_quantities.b0.value)) < 0:
                magnetic_field_summary = min(ids_summary.global_quantities.b0.value)
            else:
                magnetic_field_summary = max(ids_summary.global_quantities.b0.value)
            magnetic_field = magnetic_field_summary
    if magnetic_field_equilibrium != magnetic_field_summary:
        debug_info += "\n\t> magnetic_field is not same in summary and equilibrium ids"

    return magnetic_field, debug_info


def get_plasma_current(ids_summary, ids_equilibrium):
    plasma_current = np.nan
    plasma_current_summary = 0
    plasma_current_equilibrium = 0
    debug_info = ""
    if ids_summary:
        if len(ids_summary.global_quantities.ip.value) > 0:
            debug_info += (
                f"\n\t> ids_summary.global_quantities.ip.value : {ids_summary.global_quantities.ip.value.value}"
            )
            ip = ids_summary.global_quantities.ip.value
            plasma_current_summary = ip[np.argmax(np.abs(ip))]
            plasma_current = plasma_current_summary
            debug_info += f"\n\t> plasma_current_summary : {plasma_current_summary}"
        else:
            debug_info += "\n\t> ids_summary.global_quantities.ip.value is empty"

    if ids_equilibrium:
        ip_raw = []
        for t in range(len(ids_equilibrium.time)):
            ip_raw.append(ids_equilibrium.time_slice[t].global_quantities.ip)
        ip = np.array(ip_raw)
        debug_info += f"\n\t> ids_equilibrium.time_slice[t].global_quantities.ip : {ip}"
        plasma_current_equilibrium = ip[np.argmax(np.abs(ip))]
        plasma_current = plasma_current_equilibrium
        if plasma_current_equilibrium == 0:
            debug_info += "\n\t> ids_equilibrium.time_slice[t].global_quantities.ip is empty"
        else:
            debug_info += f"\n\t> plasma_current_equilibrium : {plasma_current_equilibrium}"
    else:
        debug_info += "\n\t> equilibrium ids is not available"
    if plasma_current_summary != plasma_current_equilibrium:
        debug_info += "\n\t> plasma_current is not same in summary and equilibrium ids"

    return plasma_current, debug_info


def get_local(scenario_key_parameters: dict, slice_index, ids_summary, ids_core_profiles, ids_edge_profiles, alias):
    debug_info = ""
    validation_status = True
    central_electron_density_ids = np.nan
    central_zeff_ids = np.nan
    sepmid_electron_density_ids = np.nan
    if ids_summary.local.separatrix.zeff.value.has_value:
        sepmid_zeff_ids = ids_summary.local.separatrix.zeff.value[slice_index]
    else:
        sepmid_zeff_ids = np.nan

    if ids_core_profiles:
        central_electron_density_ids, _ = get_central_electron_density(ids_core_profiles)
        central_zeff_ids = ids_core_profiles.profiles_1d[slice_index].zeff[0]
    elif ids_edge_profiles:
        sepmid_electron_density_ids, _ = get_sepmid_electron_density(ids_summary)

    sepmid_electron_density_yaml = scenario_key_parameters.get("sepmid_electron_density", np.nan)
    sepmid_zeff_yaml = scenario_key_parameters.get("sepmid_zeff", np.nan)
    central_zeff_yaml = scenario_key_parameters.get("central_zeff", np.nan)
    central_electron_density_yaml = scenario_key_parameters.get("central_electron_density", np.nan)

    if sepmid_electron_density_yaml == "tbd":
        sepmid_electron_density_yaml = np.nan
    if sepmid_zeff_yaml == "tbd":
        sepmid_zeff_yaml = np.nan
    if central_zeff_yaml == "tbd":
        central_zeff_yaml = np.nan
    if central_electron_density_yaml == "tbd":
        central_electron_density_yaml = np.nan

    if not np.isnan(sepmid_electron_density_ids):
        if np.isnan(sepmid_electron_density_yaml):
            validation_logger.error(
                f"{alias} sepmid_electron_density, yaml value empty (yaml,ids):[{sepmid_electron_density_yaml}],"
                f"[{sepmid_electron_density_ids}]"
            )
        are_values_same = abs(sepmid_electron_density_yaml - sepmid_electron_density_ids) < 5e-2
        if are_values_same is False:
            validation_logger.error(
                f"{alias} sepmid_electron_density (yaml,ids):[{sepmid_electron_density_yaml}],"
                f"[{sepmid_electron_density_ids}]"
            )
            debug_info = "\n\t> sepmid_electron_density is not same in legacy yaml  and summary ids"
            validation_logger.warning(f"{debug_info}")
            validation_status = False

    if not np.isnan(sepmid_zeff_ids):
        if np.isnan(sepmid_zeff_yaml):
            validation_logger.error(
                f"{alias} sepmid_zeff, yaml value empty (yaml,ids):[{sepmid_zeff_yaml}]," f"[{sepmid_zeff_ids}]"
            )
        are_values_same = abs(sepmid_zeff_yaml - sepmid_zeff_ids) < 5e-2
        if are_values_same is False:
            validation_logger.error(f"{alias} sepmid_zeff (yaml,ids):[{sepmid_zeff_yaml}]," f"[{sepmid_zeff_ids}]")
            debug_info = "\n\t> sepmid_zeff is not same in legacy yaml and summary ids"
            validation_logger.warning(f"{debug_info}")
            validation_status = False

    if not np.isnan(central_electron_density_ids):
        if np.isnan(central_electron_density_yaml):
            validation_logger.error(
                f"{alias} central_electron_density, yaml value empty (yaml,ids):[{central_electron_density_yaml}],"
                f"[{central_electron_density_ids}]"
            )
        are_values_same = abs(central_electron_density_yaml - central_electron_density_ids) < 5e-2
        if are_values_same is False:
            validation_logger.error(
                f"{alias} central_electron_density (yaml,ids):[{central_electron_density_yaml}],"
                f"[{central_electron_density_ids}]"
            )
            debug_info = "\n\t> central_zeff is not same in legacy yaml and core_profiles"
            validation_logger.warning(f"{debug_info}")
            validation_status = False

    if not np.isnan(central_zeff_ids):
        if np.isnan(central_zeff_yaml):
            validation_logger.error(
                f"{alias} central_zeff, yaml value empty (yaml,ids):[{central_zeff_yaml}]," f"[{central_zeff_ids}]"
            )
        are_values_same = abs(central_zeff_yaml - central_zeff_ids) < 5e-2
        if are_values_same is False:
            validation_logger.error(f"{alias} central_zeff (yaml,ids):[{central_zeff_yaml}]," f"[{central_zeff_ids}]")
            debug_info = "\n\t> central_zeff is not same in legacy yaml and core_profiles"
            validation_logger.warning(f"{debug_info}")
            validation_status = False

    local = {}
    local["separatrix"] = {}
    local["separatrix"]["zeff"] = scenario_key_parameters.get("sepmid_zeff", "tbd")
    local["separatrix"]["n_e"] = scenario_key_parameters.get("sepmid_electron_density", "tbd")

    local["magnetic_axis"] = {}
    local["magnetic_axis"]["zeff"] = scenario_key_parameters.get("central_zeff", "tbd")
    local["magnetic_axis"]["n_e"] = scenario_key_parameters.get("central_electron_density", "tbd")
    return local, validation_status


def get_dataset_description(legacy_yaml_data: dict, ids_summary=None, ids_dataset_description=None):
    validation_status = True
    dataset_description = {}
    shot = legacy_yaml_data["characteristics"]["shot"]
    run = legacy_yaml_data["characteristics"]["run"]
    alias = str(shot) + "/" + str(run)
    # https://github.com/iterorganization/IMAS-Data-Dictionary/discussions/63
    # Removed after discussion on 05/07/2025 Standup meeting
    # dataset_description["responsible_name"] = legacy_yaml_data["responsible_name"]

    # removed https://github.com/iterorganization/IMAS-Data-Dictionary/discussions/63
    # dataset_description["uri"] = f"imas:hdf5?path=/work/imas/shared/imasdb/ITER/3/{shot}/{run}"

    # https://github.com/iterorganization/IMAS-Data-Dictionary/discussions/63
    # Removed after discussion on 05/07/2025 Standup meeting
    # if legacy_yaml_data["characteristics"]["type"].lower() == "experimental":
    #     dataset_description["type"] = {"name": "experimental"}
    # elif legacy_yaml_data["characteristics"]["type"].lower() == "simulation":
    #     dataset_description["type"] = {"name": "simulation"}
    # elif legacy_yaml_data["characteristics"]["type"].lower() == "predictive":
    #     dataset_description["type"] = {"name": "predictive"}
    # else:
    #     dataset_description["type"] = {"name": f"{legacy_yaml_data['characteristics']['type'].lower()}"}
    dataset_description["machine"] = legacy_yaml_data["characteristics"]["machine"].upper()

    dataset_description["pulse"] = legacy_yaml_data["characteristics"]["shot"]

    simulation = {}
    debug_info = ""
    workflow_name_ids = ""
    if ids_dataset_description is not None:
        debug_info += (
            f"\n\t> ids_dataset_description.simulation.workflow : {ids_dataset_description.simulation.workflow}"
        )

        workflow_name_ids = ids_dataset_description.simulation.workflow

    workflow_name_yaml = legacy_yaml_data["characteristics"]["workflow"]
    if workflow_name_ids != "":
        if workflow_name_yaml != workflow_name_ids:
            validation_logger.error(f"{alias} workflow (yaml,ids):[{workflow_name_yaml}]," f"[{workflow_name_ids}]")
            validation_logger.warning(f"{debug_info}")
            validation_status = False

    description = str(legacy_yaml_data["reference_name"]) + "\n" + str(legacy_yaml_data["free_description"])
    simulation["description"] = Literal(description)
    dataset_description["simulation"] = simulation

    code = {}
    code["name"] = legacy_yaml_data["characteristics"]["workflow"]

    dataset_description["code"] = code

    if "summary" in legacy_yaml_data["idslist"]:
        start = end = step = 0.0
        if "start_end_step" in legacy_yaml_data["idslist"]["summary"]:
            start, end, step = legacy_yaml_data["idslist"]["summary"]["start_end_step"][0].split()
        elif "time" in legacy_yaml_data["idslist"]["summary"]:
            start = end = legacy_yaml_data["idslist"]["summary"]["time"][0]
            step = 0.0
        try:
            if step == "varying":
                times = ids_summary.time
                homogeneous_time = ids_summary.ids_properties.homogeneous_time
                if homogeneous_time == 1:
                    if times is not None:
                        if len(times) > 1:
                            step = (times[len(times) - 1] - times[0]) / (len(times) - 1)

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
            dataset_description["simulation"]["time_begin"] = start
            dataset_description["simulation"]["time_end"] = end

        except ValueError as e:
            error_logger.error(f"{alias}:{e}")

        try:
            dataset_description["simulation"]["time_step"] = float(step)
        except ValueError as e:
            error_logger.error(f"{alias}:{e}")

    return dataset_description, validation_status


def get_heating_current_drive(legacy_yaml_data: dict, ids_summary, alias):
    validation_status = True
    heating_current_drive = {}
    debug_info_ec = ""
    debug_info_ic = ""
    debug_info_nbi = ""
    debug_info_lh = ""
    # validation
    p_ec = 0
    p_ic = 0
    p_nbi = 0
    p_lh = 0

    n_ec = len(ids_summary.heating_current_drive.ec)
    n_ic = len(ids_summary.heating_current_drive.ic)
    n_nbi = len(ids_summary.heating_current_drive.nbi)
    n_lh = len(ids_summary.heating_current_drive.lh)
    if n_ec > 0:
        for isource in range(n_ec):
            if len(ids_summary.heating_current_drive.ec[isource].power.value) > 0:
                p_ec = p_ec + max(ids_summary.heating_current_drive.ec[isource].power.value)
    else:
        debug_info_ec += "\n\t> ids_summary.heating_current_drive.ec is empty"
    if n_ic > 0:
        for isource in range(n_ic):
            if len(ids_summary.heating_current_drive.ic[isource].power.value) > 0:
                p_ic = p_ic + max(ids_summary.heating_current_drive.ic[isource].power.value)
    else:
        debug_info_ic += "\n\t> ids_summary.heating_current_drive.ic is empty"
    if n_nbi > 0:
        for isource in range(n_nbi):
            if len(ids_summary.heating_current_drive.nbi[isource].power.value) > 0:
                p_nbi = p_nbi + max(ids_summary.heating_current_drive.nbi[isource].power.value)
    else:
        debug_info_nbi += "\n\t> ids_summary.heating_current_drive.n_nbi is empty"
    if n_lh > 0:
        for isource in range(n_lh):
            if len(ids_summary.heating_current_drive.lh[isource].power.value) > 0:
                p_lh = p_lh + max(ids_summary.heating_current_drive.lh[isource].power.value)
    else:
        debug_info_lh += "\n\t> ids_summary.heating_current_drive.n_lh is empty"

    p_hcd = p_ec + p_ic + p_nbi + p_lh

    p_ec_yaml = float(legacy_yaml_data["hcd"]["p_ec"])
    p_ec_ids = float(p_ec * 1.0e-6)
    are_values_same = abs(p_ec_ids - p_ec_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.error(f"{alias} hcd p_ec (yaml,ids):[{p_ec_yaml}]," f"[{p_ec_ids}]")
        validation_logger.warning(f"{debug_info_ec}")
        validation_status = False
    heating_current_drive["power_ec"] = float(p_ec)

    p_ic_yaml = float(legacy_yaml_data["hcd"]["p_ic"])
    p_ic_ids = float(p_ic * 1.0e-6)
    are_values_same = abs(p_ic_ids - p_ic_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.error(f"{alias} hcd p_ic (yaml,ids):[{p_ic_yaml}]," f"[{p_ic_ids}]")
        validation_logger.warning(f"{debug_info_ic}")
        validation_status = False
    heating_current_drive["power_ic"] = float(p_ic)

    p_nbi_yaml = float(legacy_yaml_data["hcd"]["p_nbi"])
    p_nbi_ids = float(p_nbi * 1.0e-6)
    are_values_same = abs(p_nbi_ids - p_nbi_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.error(f"{alias} hcd p_nbi (yaml,ids):[{p_nbi_yaml}]," f"[{p_nbi_ids}]")
        validation_logger.warning(f"{debug_info_nbi}")
        validation_status = False
    heating_current_drive["power_nbi"] = float(p_nbi)

    p_lh_yaml = float(legacy_yaml_data["hcd"]["p_lh"])
    p_lh_ids = float(p_lh * 1.0e-6)
    are_values_same = abs(p_lh_ids - p_lh_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.error(f"{alias} hcd p_lh (yaml,ids):[{p_lh_yaml}]," f"[{p_lh_ids}]")
        validation_logger.warning(f"{debug_info_lh}")
        validation_status = False
    heating_current_drive["power_lh"] = float(p_lh)
    p_hcd_yaml = float(legacy_yaml_data["hcd"]["p_hcd"])
    p_hcd_ids = float(p_hcd * 1.0e-6)
    are_values_same = abs(p_hcd_ids - p_hcd_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.error(f"{alias} hcd p_hcd (yaml,ids):[{p_hcd_yaml}]," f"[{p_hcd_ids}]")
        validation_logger.warning(f"{debug_info_ec}{debug_info_ic} {debug_info_nbi} {debug_info_lh}")
        validation_status = False
    heating_current_drive["power_additional"] = float(p_hcd)
    return heating_current_drive, validation_status


def get_plasma_composition(plasma_composition):
    # https://github.com/iterorganization/IMAS-Data-Dictionary/discussions/51
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


def get_global_quantities(legacy_yaml_data: dict, slice_index, ids_summary, ids_equilibrium, alias):
    # https://github.com/iterorganization/IMAS-Data-Dictionary/discussions/66
    validation_status = True
    # confinement_regime
    confinement_regime_from_ids, debug_info = get_confinement_regime(ids_summary)
    confinement_regime_from_yaml = legacy_yaml_data["scenario_key_parameters"]["confinement_regime"]
    if confinement_regime_from_ids != "":
        if confinement_regime_from_yaml != confinement_regime_from_ids:
            validation_logger.error(
                f"{alias} confinement_regime (yaml,ids):[{confinement_regime_from_yaml}],"
                f"[{confinement_regime_from_ids}]"
            )
            validation_logger.warning(f"{debug_info}")
            validation_status = False

    # plasma_current
    plasma_current_from_ids, debug_info = get_plasma_current(ids_summary, ids_equilibrium)
    plasma_current_from_yaml = legacy_yaml_data["scenario_key_parameters"]["plasma_current"]
    if plasma_current_from_yaml == "tbd":
        plasma_current_from_yaml = np.nan
    plasma_current_from_ids_MA = plasma_current_from_ids * 1e-6
    plasma_current_from_yaml = plasma_current_from_yaml
    are_values_same = abs(plasma_current_from_ids_MA - plasma_current_from_yaml) < 5e-2

    if are_values_same is False:
        validation_logger.error(
            f"{alias} plasma_current (yaml,ids):[{plasma_current_from_yaml}]," f"[{plasma_current_from_ids}]"
        )
        validation_logger.warning(f"{debug_info}")
        validation_status = False

    # magnetic_field
    magnetic_field_from_ids, debug_info = get_magnetic_field(ids_summary, ids_equilibrium)
    magnetic_field_from_yaml = legacy_yaml_data["scenario_key_parameters"]["magnetic_field"]

    are_values_same = abs(magnetic_field_from_ids - magnetic_field_from_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.error(
            f"{alias} magnetic_field (yaml,ids):[{magnetic_field_from_yaml}]," f"[{magnetic_field_from_ids}]"
        )
        validation_logger.warning(f"{debug_info}")
        validation_status = False

    # power_loss
    p_sol_from_ids, debug_info = get_power_loss(ids_summary, slice_index)
    p_sol_from_ids_W = p_sol_from_ids * 1e-6
    p_sol_from_yaml = legacy_yaml_data["hcd"].get("p_sol", np.nan)
    if p_sol_from_yaml == "tbd" or p_sol_from_yaml is None:
        p_sol_from_yaml = np.nan
    if not np.isnan(p_sol_from_ids):
        are_values_same = abs(p_sol_from_ids_W - p_sol_from_yaml) < 5e-2
        if are_values_same is False:
            validation_logger.error(f"{alias} power_loss (yaml,ids):[{p_sol_from_yaml}]," f"[{p_sol_from_ids}]")
            validation_logger.warning(f"{debug_info}")
            validation_status = False
    global_quantities = {}
    global_quantities["h_mode"] = confinement_regime_from_yaml
    global_quantities["b0"] = float(magnetic_field_from_ids)
    global_quantities["main_species"] = legacy_yaml_data["scenario_key_parameters"]["main_species"]
    global_quantities["ip"] = float(plasma_current_from_ids)
    # TODO how to calulate density_peaking? https://github.com/iterorganization/IMAS-Data-Dictionary/discussions/65
    global_quantities["density_peaking"] = legacy_yaml_data["scenario_key_parameters"].get("density_peaking", "tbd")
    if not np.isnan(p_sol_from_ids):
        global_quantities["power_loss_total"] = float(p_sol_from_ids)
    else:
        global_quantities["power_loss_total"] = "tbd"
    return global_quantities, validation_status


def write_manifest_file(legacy_yaml_file: str, output_directory: str = None):
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    legacy_yaml_data = load_yaml_file(legacy_yaml_file)
    if legacy_yaml_data is None:
        return
    dbentry_status = "obsolete"
    if "status" in legacy_yaml_data:
        dbentry_status = legacy_yaml_data["status"]
    if dbentry_status == "active":

        shot = legacy_yaml_data["characteristics"]["shot"]
        run = legacy_yaml_data["characteristics"]["run"]
        alias = str(shot) + "/" + str(run)
        manifest_file_path = os.path.join(output_directory, f"manifest_{shot:06d}{run:04d}.yaml")
        data_entry_path_parts = legacy_yaml_file.strip("/").split("/")
        folder_path = "/".join(data_entry_path_parts[:6])
        uri = f"imas:hdf5?path=/{folder_path}/{shot}/{run}"

        connection = None
        try:
            connection = imas.DBEntry(uri, "r")
        except Exception as e:  #
            error_logger.error(f"{alias} {uri}: {e}")
        ids_summary = None
        ids_dataset_description = None
        ids_equilibrium = None
        ids_core_profiles = None
        ids_edge_profiles = None
        if connection is not None:
            try:
                ids_summary = connection.get("summary", autoconvert=False, lazy=True, ignore_unknown_dd_version=True)
            except Exception as e:  # noqa: F841
                error_logger.error(f"{alias}: {e}")
                exit(0)
            try:
                ids_core_profiles = connection.get(
                    "core_profiles", autoconvert=False, lazy=True, ignore_unknown_dd_version=True
                )
            except Exception as e:  # noqa: F841
                pass
            try:
                ids_edge_profiles = connection.get(
                    "edge_profiles", autoconvert=False, lazy=True, ignore_unknown_dd_version=True
                )
            except Exception as e:  # noqa: F841
                pass
            try:
                ids_dataset_description = connection.get(
                    "dataset_description", autoconvert=False, lazy=True, ignore_unknown_dd_version=True
                )
            except Exception as _:  # noqa: F841
                pass
            try:
                ids_equilibrium = connection.get(
                    "equilibrium", autoconvert=False, lazy=True, ignore_unknown_dd_version=True
                )
            except Exception as e:  # noqa: F841
                pass
        slice_index = 0
        if ids_core_profiles:
            central_electron_density, slice_index = get_central_electron_density(ids_core_profiles)
        elif ids_edge_profiles:
            sepmid_electron_density, slice_index = get_sepmid_electron_density(ids_summary)
        global_quantities_validation = False
        hcd_validation = False
        dataset_validation = False
        local_validation = False
        manifest_metadata = {}

        manifest_metadata["dataset_description"], dataset_validation = get_dataset_description(
            legacy_yaml_data=legacy_yaml_data, ids_summary=ids_summary, ids_dataset_description=ids_dataset_description
        )
        summary = {}
        summary["heating_current_drive"], hcd_validation = get_heating_current_drive(
            legacy_yaml_data, ids_summary, alias
        )
        summary["global_quantities"], global_quantities_validation = get_global_quantities(
            legacy_yaml_data, slice_index, ids_summary, ids_equilibrium, alias
        )
        summary["local"], local_validation = get_local(
            legacy_yaml_data["scenario_key_parameters"],
            slice_index,
            ids_summary,
            ids_core_profiles,
            ids_edge_profiles,
            alias,
        )
        summary["plasma_composition"] = get_plasma_composition(legacy_yaml_data["plasma_composition"])
        manifest_metadata["summary"] = summary

        try:
            creation_date = ids_summary.ids_properties.creation_date
            dt = datetime.strptime(creation_date, "%Y%m%d   %H%M%S.%f %z")
            creation_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:  # noqa: F841
            stat = os.stat(legacy_yaml_file)
            creation_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        out_data = {
            "version": 2,
            "creation_date": creation_time,
            "alias": alias,
            "outputs": [{"uri": uri}],
            "inputs": [],
            "metadata": [{"values": manifest_metadata}],
        }

        # manifest_file_path = os.path.join(os.path.dirname(legacy_yaml_file), f"manifest_{shot:06d}{run:04d}.yaml")

        manifest_file_path = os.path.join(output_directory, f"manifest_{shot:06d}{run:04d}.yaml")
        with open(manifest_file_path, "w") as file:
            yaml.dump(out_data, file, default_flow_style=False, sort_keys=False)

        if connection:
            connection.close()
        if (
            global_quantities_validation is False
            or hcd_validation is False
            or dataset_validation is False
            or local_validation is False
        ):
            sys.stdout.write("v")
        else:
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
    error_logger.info(f"\nManifest files are written into  {output_directory}")
