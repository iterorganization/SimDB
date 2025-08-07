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
output_directory = "manifest"
os.makedirs(output_directory, exist_ok=True)
validation_log_path = os.path.join(output_directory, "_manifest_validation.log")
validation_logger = logging.getLogger("validation_logger")
validation_logger.setLevel(logging.INFO)
validation_handler = logging.FileHandler(validation_log_path, mode="w")
validation_handler.setFormatter(logging.Formatter("%(message)s"))
validation_logger.addHandler(validation_handler)
if enable_console_logging:
    validation_console_handler = logging.StreamHandler(sys.stdout)
    validation_console_handler.setFormatter(logging.Formatter("%(message)s"))
    validation_logger.addHandler(validation_console_handler)
# -----------------------------------------------------------------------------------------------------


class Literal(str):
    pass


def literal_presenter(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(Literal, literal_presenter)

ion_names_map = {
    "H": "hydrogen",
    "D": "deuterium",
    "T": "tritium",
    "He": "helium",
    "He3": "helium_3",
    "He4": "helium_4",
    "Be": "beryllium",
    "B": "boron",
    "Li": "lithium",
    "C": "carbon",
    "N": "nitrogen",
    "Ne": "neon",
    "Ar": "argon",
    "Xe": "xenon",
    "O": "oxygen",
    "Fe": "iron",
    "Kr": "krypton",
    "W": "tungsten",
    "Mo": "molybdenum",
    "DT": "deuterium_tritium",
}


def load_yaml_file(yaml_file, Loader=yaml.SafeLoader):
    if not os.path.exists(yaml_file):
        validation_logger.error(f"YAML file {yaml_file} does not exist")
        return None
    yaml_data = None
    try:
        with open(yaml_file, "r", encoding="utf-8") as file_handle:
            yaml_data = yaml.load(file_handle, Loader=Loader)
    except Exception as e:
        validation_logger.error(f"error loading YAML file {yaml_file}: {e}", exc_info=True)
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
        debug_info += "\n\t> ids_summary.global_quantities.h_mode is empty "
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


def get_local(scenario_key_parameters: dict, slice_index, ids_summary, ids_core_profiles, ids_edge_profiles):
    debug_info = ""
    local = {}
    separatrix = {}
    magnetic_axis = {}
    # get values from IDS
    central_electron_density_ids = np.nan
    central_zeff_ids = np.nan
    sepmid_zeff_ids = np.nan
    sepmid_electron_density_ids = np.nan

    if ids_core_profiles:
        central_electron_density_ids, _ = get_central_electron_density(ids_core_profiles)
        central_zeff_ids = ids_core_profiles.profiles_1d[slice_index].zeff[0]

    # sepmid_electron_density
    if ids_edge_profiles:
        sepmid_electron_density_ids, _ = get_sepmid_electron_density(ids_summary)
    sepmid_electron_density_yaml = scenario_key_parameters.get("sepmid_electron_density", np.nan)
    if sepmid_electron_density_yaml == "tbd" or sepmid_electron_density_yaml == "":
        sepmid_electron_density_yaml = np.nan
    if not np.isnan(sepmid_electron_density_ids):
        if np.isnan(sepmid_electron_density_yaml):
            validation_logger.info(
                f"\t> sepmid_electron_density, yaml value empty (yaml,ids):[{sepmid_electron_density_yaml}],"
                f"[{sepmid_electron_density_ids}]"
            )
        are_values_same = abs(sepmid_electron_density_yaml - sepmid_electron_density_ids) < 5e-2
        if are_values_same is False:
            validation_logger.info(
                f"\t> sepmid_electron_density (yaml,ids):[{sepmid_electron_density_yaml}],"
                f"[{sepmid_electron_density_ids}]"
            )
            debug_info = "\n\t> sepmid_electron_density is not same in legacy yaml  and summary ids"
            validation_logger.info(f"\t> {debug_info}")

    if not ids_summary.local.separatrix.n_e.value.has_value:
        if sepmid_electron_density_yaml is not None and not np.isnan(sepmid_electron_density_yaml):
            separatrix["n_e"] = {"value": sepmid_electron_density_yaml}
        else:
            validation_logger.info(
                "\t> ids_summary.local.separatrix.n_e.value is empty and "
                "sepmid_electron_density from yaml is empty, nothing to set"
            )
    else:
        validation_logger.info("\t> ids_summary.local.separatrix.n_e.value is already set in the IDS, not setting")
        validation_logger.info(
            f"\t> (yaml,ids):[{sepmid_electron_density_yaml}]," f"[{ids_summary.local.separatrix.n_e.value}]"
        )

    # sepmid_zeff
    if ids_summary.local.separatrix.zeff.value.has_value:
        sepmid_zeff_ids = ids_summary.local.separatrix.zeff.value[slice_index]
    sepmid_zeff_yaml = scenario_key_parameters.get("sepmid_zeff", np.nan)
    if sepmid_zeff_yaml == "tbd" or sepmid_zeff_yaml == "":
        sepmid_zeff_yaml = np.nan
    if not np.isnan(sepmid_zeff_ids):
        if np.isnan(sepmid_zeff_yaml):
            validation_logger.info(
                f"\t> sepmid_zeff, yaml value empty (yaml,ids):[{sepmid_zeff_yaml}]," f"[{sepmid_zeff_ids}]"
            )
        are_values_same = abs(sepmid_zeff_yaml - sepmid_zeff_ids) < 5e-2
        if are_values_same is False:
            validation_logger.info(f"\t> sepmid_zeff (yaml,ids):[{sepmid_zeff_yaml}]," f"[{sepmid_zeff_ids}]")
            debug_info = "\n\t> sepmid_zeff is not same in legacy yaml and summary ids"
            validation_logger.info(f"\t> {debug_info}")

    if not ids_summary.local.separatrix.zeff.value.has_value:
        if sepmid_zeff_yaml is not None and not np.isnan(sepmid_zeff_yaml):
            separatrix["zeff"] = {"value": sepmid_zeff_yaml}
        else:
            validation_logger.info(
                "\t> ids_summary.local.separatrix.zeff.value is empty and "
                "sepmid_zeff from yaml is empty, nothing to set"
            )
    else:
        validation_logger.info("\t> ids_summary.local.separatrix.zeff.value is already set in the IDS, not setting")
        validation_logger.info(f"\t> (yaml,ids):[{sepmid_zeff_yaml}]," f"[{ids_summary.local.separatrix.zeff.value}]")

    # central_electron_density
    central_electron_density_yaml = scenario_key_parameters.get("central_electron_density", np.nan)
    if central_electron_density_yaml == "tbd" or central_electron_density_yaml == "":
        central_electron_density_yaml = np.nan

    if not np.isnan(central_electron_density_ids):
        if np.isnan(central_electron_density_yaml):
            validation_logger.info(
                f"\t> central_electron_density, yaml value empty (yaml,ids):[{central_electron_density_yaml}],"
                f"[{central_electron_density_ids}]"
            )
        are_values_same = abs(central_electron_density_yaml - central_electron_density_ids) < 5e-2
        if are_values_same is False:
            validation_logger.info(
                f"\t> central_electron_density (yaml,ids):[{central_electron_density_yaml}],"
                f"[{central_electron_density_ids}]"
            )
            debug_info = "\n\t> central_zeff is not same in legacy yaml and core_profiles"
            validation_logger.info(f"\t> {debug_info}")

    if not ids_summary.local.magnetic_axis.n_e.value.has_value:
        if central_electron_density_yaml is not None and not np.isnan(central_electron_density_yaml):
            magnetic_axis["n_e"] = {"value": central_electron_density_yaml}
        else:
            validation_logger.info(
                "\t> ids_summary.local.magnetic_axis.n_e.value is empty "
                "and central_electron_density from yaml is empty, nothing to set"
            )
    else:
        validation_logger.info("\t> ids_summary.local.magnetic_axis.n_e.value is already set in the IDS, not setting")
        validation_logger.info(
            f"\t> (yaml,ids):[{central_electron_density_yaml}]," f"[{ids_summary.local.magnetic_axis.n_e.value}]"
        )

    # central_zeff
    central_zeff_yaml = scenario_key_parameters.get("central_zeff", np.nan)
    if central_zeff_yaml == "tbd" or central_zeff_yaml == "":
        central_zeff_yaml = np.nan
    if not np.isnan(central_zeff_ids):
        if np.isnan(central_zeff_yaml):
            validation_logger.info(
                f"\t> central_zeff, yaml value empty (yaml,ids):[{central_zeff_yaml}]," f"[{central_zeff_ids}]"
            )
        are_values_same = abs(central_zeff_yaml - central_zeff_ids) < 5e-2
        if are_values_same is False:
            validation_logger.info(f"central_zeff (yaml,ids):[{central_zeff_yaml}]," f"[{central_zeff_ids}]")
            debug_info = "\n\t> central_zeff is not same in legacy yaml and core_profiles"
            validation_logger.info(f"\t> {debug_info}")

    if not ids_summary.local.magnetic_axis.zeff.value.has_value:
        if central_zeff_yaml is not None and not np.isnan(central_zeff_yaml):
            magnetic_axis["zeff"] = {"value": central_zeff_yaml}
        else:
            validation_logger.info(
                "\t> ids_summary.local.magnetic_axis.zeff.value is empty and "
                "central_zeff from yaml is empty, nothing to set"
            )
    else:
        validation_logger.info("\t> ids_summary.local.magnetic_axis.zeff.value is already set in the IDS, not setting")
        validation_logger.info(
            f"\t> (yaml,ids):[{central_zeff_yaml}]," f"[{ids_summary.local.magnetic_axis.zeff.value}]"
        )

    if separatrix and separatrix != {}:
        local["separatrix"] = separatrix
    if magnetic_axis and magnetic_axis != {}:
        local["magnetic_axis"] = magnetic_axis
    return local


def flatten_description(data, indent=0):
    lines = []
    prefix = " " * indent

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(flatten_description(value, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        for item in data:
            lines.append(flatten_description(item, indent))
    elif isinstance(data, str):
        lines.append(prefix + data.replace("\\n", "\n" + prefix))
    else:
        lines.append(prefix + str(data))

    return "\n".join(lines)


def get_dataset_description(legacy_yaml_data: dict, ids_summary=None, ids_dataset_description=None):
    dataset_description = {}
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

    # dataset_description.machine
    machine_from_yaml = legacy_yaml_data["characteristics"]["machine"]
    machine_from_ids = None
    if ids_dataset_description is not None and hasattr(ids_dataset_description, "machine"):
        machine_from_ids = ids_dataset_description.machine if ids_dataset_description.machine.has_value else None
    if machine_from_ids:
        if machine_from_ids != machine_from_yaml:
            validation_logger.info("\tdiscrepancies found in machine name")
            validation_logger.info(
                f"\t>  yaml['characteristics']['machine'], "
                f"dataset_description.machine (yaml,ids):[{machine_from_yaml}],"
                f"[{machine_from_ids}]"
            )
        dataset_description["machine"] = machine_from_ids.value
    else:
        validation_logger.info("\tids_dataset_description.machine is not set in the IDS, setting it from yaml file")
        validation_logger.info(f"\t>  (yaml,ids):[{machine_from_yaml}]," f"[{machine_from_ids}]")
        dataset_description["machine"] = machine_from_yaml.upper()

    # dataset_description.pulse
    # pulse_from_yaml = legacy_yaml_data["characteristics"]["shot"]
    # pulse_from_ids = None
    # if ids_dataset_description is not None and hasattr(ids_dataset_description, "pulse"):
    #     pulse_from_ids = ids_dataset_description.pulse if ids_dataset_description.pulse.has_value else None
    # if pulse_from_ids:
    #     if pulse_from_ids != pulse_from_yaml:
    #         validation_logger.info("\tdiscrepancies found in pulse")
    #         validation_logger.info(
    #             f"\t>  yaml['characteristics']['shot'], dataset_description.pulse (yaml,ids):[{pulse_from_yaml}],"
    #             f"[{pulse_from_ids}]"
    #         )
    #     dataset_description["pulse"] = pulse_from_ids.value
    # else:
    #     validation_logger.info("\tids_dataset_description.pulse is not set in the IDS, setting it from yaml file")
    #     validation_logger.info(f"\t>  (yaml,ids):[{pulse_from_yaml}]," f"[{pulse_from_ids}]")
    #     dataset_description["pulse"] = pulse_from_yaml

    # dataset_description.code
    code_from_yaml = legacy_yaml_data["characteristics"]["workflow"]
    code_from_ids = None
    if ids_summary is not None:
        code_from_ids = ids_summary.code.name

    code = {}
    if code_from_ids:
        if code_from_ids != code_from_yaml:
            validation_logger.info("\tdiscrepancies found in code name")
            validation_logger.info(
                f"\t>  yaml['characteristics']['workflow'], summary.code.name  "
                f"(yaml,ids):[{code_from_yaml}],[{code_from_ids}]"
            )
        # code["name"] = code_from_ids.upper()
    # else:
    #     validation_logger.info("\tsummary.code.name is not set in the IDS, setting it from yaml file")
    #     validation_logger.info(f"\t>  (yaml,ids):[{code_from_yaml}], [{code_from_ids}]")

    code["name"] = code_from_yaml.upper()
    dataset_description["code"] = code

    # dataset_description.simulation.description
    _description_yaml = flatten_description(legacy_yaml_data["free_description"])
    _description_yaml = _description_yaml.replace("\\n", "\n")
    description_yaml = (
        "reference_name:" + str(legacy_yaml_data["reference_name"]) + "\ndescription:" + _description_yaml
    )
    scenario_key_parameters = "scenario_key_parameters:\n"
    for key, value in legacy_yaml_data["scenario_key_parameters"].items():
        if value == "tbd" or value == "":
            continue
        scenario_key_parameters += f"    {key}: {value}\n"
    description_yaml += scenario_key_parameters

    hcd_data = "hcd:\n"
    for key, value in legacy_yaml_data["hcd"].items():
        if value == "tbd" or value == "":
            continue
        hcd_data += f"    {key}: {value}\n"
    description_yaml += hcd_data

    characteristics = "characteristics:\n"
    for key, value in legacy_yaml_data["characteristics"].items():
        if key == "shot" or key == "run":
            continue
        if value == "tbd" or value == "":
            continue
        characteristics += f"    {key}: {value}\n"
    description_yaml += characteristics

    plasma_composition = get_plasma_composition(legacy_yaml_data["plasma_composition"])
    output_parts = []
    plasma_composition_parts = {}
    for key, props in plasma_composition.items():
        plasma_composition_parts[key] = props["n_over_ne"]
    sorted_items = dict(sorted(plasma_composition_parts.items(), key=lambda x: x[1], reverse=True))
    for key, val in sorted_items.items():
        if val is None or val == "tbd" or val == "":
            continue
        val = float(val)
        if val < 0.01:
            formatted = f"{key}({val:.2e})"
        else:
            formatted = f"{key}({val:.3f})"
            output_parts.append(formatted)
    output = ",".join(output_parts)

    description_yaml += f"plasma_composition:{output}"

    density_peaking_yaml = legacy_yaml_data["scenario_key_parameters"].get("density_peaking", "")
    if density_peaking_yaml != "tbd" and density_peaking_yaml != "":
        description_yaml += f"\ndensity_peaking:{density_peaking_yaml}"
    description_yaml = Literal(description_yaml)
    simulation = {}
    simulation["description"] = description_yaml
    dataset_description["simulation"] = simulation

    if "summary" in legacy_yaml_data["idslist"]:
        start = end = step = 0.0
        if "start_end_step" in legacy_yaml_data["idslist"]["summary"]:
            start, end, step = legacy_yaml_data["idslist"]["summary"]["start_end_step"][0].split()
        elif "time" in legacy_yaml_data["idslist"]["summary"]:
            start = end = legacy_yaml_data["idslist"]["summary"]["time"][0]
            step = 0.0
        if step == "varying":
            times = ids_summary.time
            homogeneous_time = ids_summary.ids_properties.homogeneous_time
            if homogeneous_time == 1:
                if times is not None:
                    if len(times) > 1:
                        step = (times[len(times) - 1] - times[0]) / (len(times) - 1)

        start = float(start)
        end = float(end)

        # pulse_time_begin_epoch_seconds_ids = 0
        # pulse_time_begin_epoch_nanoseconds_ids = 0
        # pulse_time_end_epoch_seconds_ids = 0
        # pulse_time_end_epoch_nanoseconds_ids = 0
        simulation_time_begin_ids = 0.0
        simulation_time_end_ids = 0.0
        simulation_time_step_ids = 0

        # pulse_time_begin_epoch_seconds_yaml = round(start)
        # pulse_time_begin_epoch_nanoseconds_yaml = (start - round(start)) * 10**9
        # pulse_time_end_epoch_seconds_yaml = round(end)
        # pulse_time_end_epoch_nanoseconds_yaml = (end - round(end)) * 10**9
        simulation_time_begin_yaml = start
        simulation_time_end_yaml = end
        simulation_time_step_yaml = float(step)

        # dataset_description["pulse_time_begin_epoch"] = {}
        # dataset_description["pulse_time_end_epoch"] = {}
        if ids_dataset_description is not None:
            # pulse_time_begin_epoch_seconds_ids = (
            #     ids_dataset_description.pulse_time_begin_epoch.seconds
            #     if ids_dataset_description.pulse_time_begin_epoch.seconds.has_value
            #     else 0
            # )
            # pulse_time_begin_epoch_nanoseconds_ids = (
            #     ids_dataset_description.pulse_time_begin_epoch.nanoseconds
            #     if ids_dataset_description.pulse_time_begin_epoch.nanoseconds.has_value
            #     else 0
            # )
            # pulse_time_end_epoch_seconds_ids = (
            #     ids_dataset_description.pulse_time_end_epoch.seconds
            #     if ids_dataset_description.pulse_time_end_epoch.seconds.has_value
            #     else 0
            # )
            # pulse_time_end_epoch_nanoseconds_ids = (
            #     ids_dataset_description.pulse_time_end_epoch.nanoseconds
            #     if ids_dataset_description.pulse_time_end_epoch.nanoseconds.has_value
            #     else 0
            # )
            simulation_time_begin_ids = (
                ids_dataset_description.simulation.time_begin
                if ids_dataset_description.simulation.time_begin.has_value
                else 0.0
            )
            simulation_time_end_ids = (
                ids_dataset_description.simulation.time_end
                if ids_dataset_description.simulation.time_end.has_value
                else 0.0
            )
            simulation_time_step_ids = (
                ids_dataset_description.simulation.time_step
                if ids_dataset_description.simulation.time_step.has_value
                else 0
            )

        # if pulse_time_begin_epoch_seconds_ids:
        #     if pulse_time_begin_epoch_seconds_ids != pulse_time_begin_epoch_seconds_yaml:
        #         validation_logger.info("\tdiscrepancies found in dataset_description.pulse_time_begin_epoch.seconds")
        #         validation_logger.info(
        #             f"\t>  (yaml,ids):[{pulse_time_begin_epoch_seconds_yaml}],[{pulse_time_begin_epoch_seconds_ids}]"
        #         )
        #     dataset_description["pulse_time_begin_epoch"]["seconds"] = pulse_time_begin_epoch_seconds_ids.value
        # else:
        #     validation_logger.info(
        #         "\tdataset_description.pulse_time_begin_epoch.seconds is "
        # "not set in the IDS, setting it from yaml file"
        #     )
        #     validation_logger.info(
        #         f"\t>  (yaml,ids):[{pulse_time_begin_epoch_seconds_yaml}],[{pulse_time_begin_epoch_seconds_ids}]"
        #     )
        #     dataset_description["pulse_time_begin_epoch"]["seconds"] = round(start)
        # if pulse_time_begin_epoch_nanoseconds_ids:
        #     if pulse_time_begin_epoch_nanoseconds_ids != pulse_time_begin_epoch_nanoseconds_yaml:
        #         validation_logger.info(
        #             "\tdiscrepancies found in dataset_description.pulse_time_begin_epoch.nanoseconds"
        #         )
        #         validation_logger.info(
        #             f"\t>  (yaml,ids):"
        #             f"[{pulse_time_begin_epoch_nanoseconds_yaml}],[{pulse_time_begin_epoch_nanoseconds_ids}]"
        #         )
        #     dataset_description["pulse_time_begin_epoch"]["nanoseconds"] = int(
        #         pulse_time_begin_epoch_nanoseconds_ids.value
        #     )
        # else:
        #     validation_logger.info(
        #         "\tdataset_description.pulse_time_begin_epoch.nanoseconds is not set in the IDS, "
        #         "setting it from yaml file"
        #     )
        #     validation_logger.info(
        #         f"\t>  (yaml,ids):[{pulse_time_begin_epoch_nanoseconds_yaml}],"
        #         f"[{pulse_time_begin_epoch_nanoseconds_ids}]"
        #     )
        #     dataset_description["pulse_time_begin_epoch"]["nanoseconds"] = int((start - round(start)) * 10**9)

        # if pulse_time_end_epoch_seconds_ids:
        #     if pulse_time_end_epoch_seconds_ids != pulse_time_end_epoch_seconds_yaml:
        #         validation_logger.info("\tdiscrepancies found in dataset_description.pulse_time_end_epoch.seconds")
        #         validation_logger.info(
        #             f"\t>  (yaml,ids):[{pulse_time_end_epoch_seconds_yaml}],[{pulse_time_end_epoch_seconds_ids}]"
        #         )
        #     dataset_description["pulse_time_end_epoch"]["seconds"] = pulse_time_end_epoch_seconds_ids.value
        # else:
        #     validation_logger.info(
        #         "\tdataset_description.pulse_time_end_epoch.seconds is not set in the IDS, setting it from yaml file"
        #     )
        #     validation_logger.info(
        #         f"\t>  (yaml,ids):[{pulse_time_end_epoch_seconds_yaml}],[{pulse_time_end_epoch_seconds_ids}]"
        #     )
        #     dataset_description["pulse_time_end_epoch"]["seconds"] = round(end)
        # if pulse_time_end_epoch_nanoseconds_ids:
        #     if pulse_time_end_epoch_nanoseconds_ids != pulse_time_end_epoch_nanoseconds_yaml:
        #         validation_logger.info(
        # "\tdiscrepancies found in dataset_description.pulse_time_end_epoch.nanoseconds")
        #         validation_logger.info(
        #             f"\t>  (yaml,ids):[{pulse_time_end_epoch_nanoseconds_yaml}],"
        #             f"[{pulse_time_end_epoch_nanoseconds_ids}]"
        #         )
        #     dataset_description["pulse_time_end_epoch"]["nanoseconds"] = \
        # int(pulse_time_end_epoch_nanoseconds_ids.value)
        # else:
        #     validation_logger.info(
        #         "\tdataset_description.pulse_time_end_epoch.nanoseconds is not set in the IDS"
        #         ", setting it from yaml file"
        #     )
        #     validation_logger.info(
        #         f"\t>  (yaml,ids):[{pulse_time_end_epoch_nanoseconds_yaml}],[{pulse_time_end_epoch_nanoseconds_ids}]"
        #     )
        #     dataset_description["pulse_time_end_epoch"]["nanoseconds"] = int((end - round(end)) * 10**9)

        if simulation_time_begin_ids:
            if simulation_time_begin_ids != simulation_time_begin_yaml:
                validation_logger.info("\tdiscrepancies found in dataset_description.simulation.time_start")
                validation_logger.info(f"\t>  (yaml,ids):[{simulation_time_begin_yaml}],[{simulation_time_begin_ids}]")
            dataset_description["simulation"]["time_begin"] = simulation_time_begin_ids.value
        else:
            validation_logger.info(
                "\tdataset_description.simulation.time_begin is not set in the IDS, setting it from yaml file"
            )
            validation_logger.info(f"\t>  (yaml,ids):[{simulation_time_begin_yaml}],[{simulation_time_begin_ids}]")
            dataset_description["simulation"]["time_begin"] = start
        if simulation_time_end_ids:
            if simulation_time_end_ids != simulation_time_end_yaml:
                validation_logger.info("\tdiscrepancies found in dataset_description.simulation.time_end")
                validation_logger.info(f"\t>  (yaml,ids):[{simulation_time_end_yaml}],[{simulation_time_end_ids}]")
            dataset_description["simulation"]["time_end"] = simulation_time_end_ids.value
        else:
            validation_logger.info(
                "\tdataset_description.simulation.time_end is not set in the IDS, setting it from yaml file"
            )
            validation_logger.info(f"\t>  (yaml,ids):[{simulation_time_end_yaml}],[{simulation_time_end_ids}]")
            dataset_description["simulation"]["time_end"] = end

        if simulation_time_step_ids:
            if simulation_time_step_ids != simulation_time_step_yaml:
                validation_logger.info("\tdiscrepancies found in dataset_description.simulation.time_step")
                validation_logger.info(f"\t>  (yaml,ids):[{simulation_time_step_yaml}],[{simulation_time_step_ids}]")
            dataset_description["simulation"]["time_step"] = simulation_time_step_ids.value
        else:
            validation_logger.info(
                "\tdataset_description.simulation.time_step is not set in the IDS, setting it from yaml file"
            )
            validation_logger.info(f"\t>  (yaml,ids):[{simulation_time_step_yaml}],[{simulation_time_step_ids}]")
            dataset_description["simulation"]["time_step"] = float(step)

    return dataset_description


def get_heating_current_drive(legacy_yaml_data: dict, ids_summary):
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
        validation_logger.info(f"\t> discrepancies found in hcd p_ec (yaml,ids):[{p_ec_yaml}]," f"[{p_ec_ids}]")
        validation_logger.info(f"{debug_info_ec}")

    if not ids_summary.heating_current_drive.power_ec.value.has_value:
        if float(p_ec_yaml) != 0.0:
            heating_current_drive["power_ec"] = {"value": float(p_ec_yaml) / 1.0e-6}
        else:
            validation_logger.info(
                "\t> ids_summary.heating_current_drive.power_ec.value is empty and "
                "p_ec from yaml is empty, nothing to set"
            )
            validation_logger.info(
                f"\t>  (yaml,ids):[{p_ec_yaml}],[{ids_summary.heating_current_drive.power_ec.value}]"
            )
    else:
        validation_logger.info(
            "\t> ids_summary.heating_current_drive.power_ec.value is already set in the IDS, not setting"
        )
        validation_logger.info(
            f"\t>  (yaml,ids):[{p_ec_yaml}],[{ids_summary.heating_current_drive.power_ec.value.value}]"
        )

    p_ic_yaml = float(legacy_yaml_data["hcd"]["p_ic"])
    p_ic_ids = float(p_ic * 1.0e-6)
    are_values_same = abs(p_ic_ids - p_ic_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.info(f"\t> discrepancies found in hcd p_ic (yaml,ids):[{p_ic_yaml}]," f"[{p_ic_ids}]")
        validation_logger.info(f"{debug_info_ic}")

    if not ids_summary.heating_current_drive.power_ic.value.has_value:
        if float(p_ic_yaml) != 0.0:
            heating_current_drive["power_ic"] = {"value": float(p_ic_yaml) / 1.0e-6}
        else:
            validation_logger.info(
                "\t> ids_summary.heating_current_drive.power_ic.value is empty and "
                "p_ic from yaml is empty, nothing to set"
            )
            validation_logger.info(
                f"\t>  (yaml,ids):[{p_ic_yaml}],[{ids_summary.heating_current_drive.power_ic.value}]"
            )
    else:
        validation_logger.info(
            "\t> ids_summary.heating_current_drive.power_ic.value is already set in the IDS, not setting"
        )
        validation_logger.info(
            f"\t>  (yaml,ids):[{p_ic_yaml}],[{ids_summary.heating_current_drive.power_ic.value.value}]"
        )

    p_nbi_yaml = float(legacy_yaml_data["hcd"]["p_nbi"])
    p_nbi_ids = float(p_nbi * 1.0e-6)
    are_values_same = abs(p_nbi_ids - p_nbi_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.info(f"\t>  discrepancies found in hcd p_nbi (yaml,ids):[{p_nbi_yaml}]," f"[{p_nbi_ids}]")
        validation_logger.info(f"{debug_info_nbi}")

    if not ids_summary.heating_current_drive.power_nbi.value.has_value:
        if float(p_nbi_yaml) != 0.0:
            heating_current_drive["power_nbi"] = {"value": float(p_nbi_yaml) / 1.0e-6}

        else:
            validation_logger.info(
                "\t> ids_summary.heating_current_drive.power_nbi.value and p_nbi from yaml is empty, nothing to set"
            )
            validation_logger.info(
                f"\t>  (yaml,ids):[{p_nbi_yaml}],[{ids_summary.heating_current_drive.power_nbi.value}]"
            )
    else:
        validation_logger.info(
            "\t> ids_summary.heating_current_drive.power_nbi.value is already set in the IDS, not setting"
        )
        validation_logger.info(f"\t>  (yaml,ids):[{p_nbi_yaml}],[{ids_summary.heating_current_drive.power_nbi.value}]")

    p_lh_yaml = float(legacy_yaml_data["hcd"]["p_lh"])
    p_lh_ids = float(p_lh * 1.0e-6)
    are_values_same = abs(p_lh_ids - p_lh_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.info(f"\t> discrepancies found in hcd p_lh (yaml,ids):[{p_lh_yaml}]," f"[{p_lh_ids}]")
        validation_logger.info(f"{debug_info_lh}")

    if not ids_summary.heating_current_drive.power_lh.value.has_value:
        if float(p_lh_yaml) != 0.0:
            heating_current_drive["power_lh"] = {"value": float(p_lh_yaml) / 1.0e-6}
        else:
            validation_logger.info(
                "\t> ids_summary.heating_current_drive.power_lh.value is empty and "
                "p_lh from yaml is empty, nothing to set"
            )
            validation_logger.info(
                f"\t>  (yaml,ids):[{p_lh_yaml}],[{ids_summary.heating_current_drive.power_lh.value}]"
            )
    else:
        validation_logger.info(
            "\t> ids_summary.heating_current_drive.power_lh.value is already set in the IDS, not setting"
        )
        validation_logger.info(f"\t>  (yaml,ids):[{p_lh_yaml}],[{ids_summary.heating_current_drive.power_lh.value}]")

    p_hcd_yaml = float(legacy_yaml_data["hcd"]["p_hcd"])
    p_hcd_ids = float(p_hcd * 1.0e-6)
    are_values_same = abs(p_hcd_ids - p_hcd_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.info(f"\t> discrepancies found in hcd p_hcd (yaml,ids):[{p_hcd_yaml}]," f"[{p_hcd_ids}]")
        validation_logger.info(f"{debug_info_ec}{debug_info_ic} {debug_info_nbi} {debug_info_lh}")

    if not ids_summary.heating_current_drive.power_additional.value.has_value:
        if float(p_hcd_yaml) != 0.0:
            heating_current_drive["power_additional"] = {"value": float(p_hcd_yaml) / 1.0e-6}
        else:
            validation_logger.info(
                "\t> ids_summary.heating_current_drive.power_additional.value is empty and "
                "p_hcd from yaml is empty, nothing to set"
            )
            validation_logger.info(
                f"\t>  (yaml,ids):[{p_hcd_yaml}],[{ids_summary.heating_current_drive.power_additional.value}]"
            )
    else:
        validation_logger.info(
            "\t> ids_summary.heating_current_drive.power_additional.value is already set in the IDS, not setting"
        )
        validation_logger.info(
            f"\t>  (yaml,ids):[{p_hcd_yaml}],[{ids_summary.heating_current_drive.power_additional.value}]"
        )
    return heating_current_drive


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
            a_value = ""

        if z_values is not None and species_index < len(z_values):
            z_value = z_values[species_index]
        else:
            z_value = ""

        if n_over_ntot_values is not None and species_index < len(n_over_ntot_values):
            n_over_ntot_value = n_over_ntot_values[species_index]
        else:
            n_over_ntot_value = ""

        if n_over_ne_values is not None and species_index < len(n_over_ne_values):
            n_over_ne_value = n_over_ne_values[species_index]
        else:
            n_over_ne_value = ""

        if n_over_n_maj_values is not None and species_index < len(n_over_n_maj_values):
            n_over_n_maj_value = n_over_n_maj_values[species_index]
        else:
            n_over_n_maj_value = ""

        species_dict[species] = {
            "a": a_value,
            "z": z_value,
            "n_over_ntot": n_over_ntot_value,
            "n_over_ne": n_over_ne_value,
            "n_over_n_maj": n_over_n_maj_value,
        }
    return species_dict


def get_global_quantities(legacy_yaml_data: dict, slice_index, ids_summary, ids_equilibrium):
    # https://github.com/iterorganization/IMAS-Data-Dictionary/discussions/66
    global_quantities = {}
    # confinement_regime
    confinement_regime_from_ids, debug_info = get_confinement_regime(ids_summary)
    confinement_regime_from_yaml = legacy_yaml_data["scenario_key_parameters"]["confinement_regime"]
    if confinement_regime_from_ids != "":
        if confinement_regime_from_yaml != confinement_regime_from_ids:
            validation_logger.info(
                f"\t> confinement_regime (yaml,ids):[{confinement_regime_from_yaml}],"
                f"[{confinement_regime_from_ids}]"
            )
            validation_logger.info(f"\t> {debug_info}")

    if not ids_summary.global_quantities.h_mode.value.has_value:
        if not confinement_regime_from_yaml == "tbd" and confinement_regime_from_yaml != "":
            if "l" in confinement_regime_from_yaml.lower() and "h" in confinement_regime_from_yaml.lower():
                pass
            elif "l" in confinement_regime_from_yaml.lower():
                global_quantities["h_mode"] = {"value": 0}
            elif "h" in confinement_regime_from_yaml.lower():
                global_quantities["h_mode"] = {"value": 1}
        else:
            validation_logger.info(
                "\t> ids_summary.global_quantities.h_mode.value is empty "
                "and confinement regime from yaml is empty, nothing to set"
            )
    else:
        validation_logger.info("\t> ids_summary.global_quantities.h_mode.value is already set in the IDS, not setting")
        validation_logger.info(
            f"\t>  (yaml,ids):[{confinement_regime_from_yaml}],[{ids_summary.global_quantities.h_mode.value}]"
        )

    # plasma_current
    plasma_current_from_ids, debug_info = get_plasma_current(ids_summary, ids_equilibrium)
    plasma_current_from_yaml = legacy_yaml_data["scenario_key_parameters"]["plasma_current"]
    if plasma_current_from_yaml == "tbd":
        plasma_current_from_yaml = np.nan
    plasma_current_from_ids_MA = plasma_current_from_ids * 1e-6
    plasma_current_from_yaml = plasma_current_from_yaml
    are_values_same = abs(plasma_current_from_ids_MA - plasma_current_from_yaml) < 5e-2

    if are_values_same is False:
        validation_logger.info(
            f"\t>  discrepancies found in plasma_current (yaml,ids):[{plasma_current_from_yaml}],"
            f"[{plasma_current_from_ids}]"
        )
        validation_logger.info(f"\t> {debug_info}")

    if not ids_summary.global_quantities.ip.value.has_value:
        if not np.isnan(plasma_current_from_ids) and plasma_current_from_ids != 0.0:
            global_quantities["ip"] = {"value": float(plasma_current_from_ids)}
            validation_logger.info("\t> ids_summary.global_quantities.ip.value setting from ids")
        else:
            validation_logger.info(
                "\t> ids_summary.global_quantities.ip.value is empty "
                "and plasma current from ids is empty, nothing to set"
            )
    else:
        validation_logger.info("\t> ids_summary.global_quantities.ip.value is already set in the IDS, not setting")
        validation_logger.info(
            f"\t>  (yaml,ids):[{plasma_current_from_yaml}],[{ids_summary.global_quantities.ip.value}]"
        )

    # magnetic_field
    magnetic_field_from_ids, debug_info = get_magnetic_field(ids_summary, ids_equilibrium)
    magnetic_field_from_yaml = legacy_yaml_data["scenario_key_parameters"]["magnetic_field"]

    are_values_same = abs(magnetic_field_from_ids - magnetic_field_from_yaml) < 5e-2
    if are_values_same is False:
        validation_logger.info(
            f"\t>  discrepancies found in magnetic_field (yaml,ids):[{magnetic_field_from_yaml}],"
            f"[{magnetic_field_from_ids}]"
        )
        validation_logger.info(f"\t> {debug_info}")

    if not ids_summary.global_quantities.b0.value.has_value:
        if magnetic_field_from_ids != 0.0:
            global_quantities["b0"] = {"value": float(magnetic_field_from_ids)}
        else:
            validation_logger.info(
                "\t> ids_summary.global_quantities.b0.value is empty "
                "and magnetic field from ids is empty, nothing to set"
            )
    else:
        validation_logger.info("\t> ids_summary.global_quantities.b0.value is already set in the IDS, not setting")
        validation_logger.info(
            f"\t>  (yaml,ids):[{magnetic_field_from_yaml}],[{ids_summary.global_quantities.b0.value}]"
        )
    # power_loss
    p_sol_from_ids, debug_info = get_power_loss(ids_summary, slice_index)
    p_sol_from_ids_W = p_sol_from_ids * 1e-6
    p_sol_from_yaml = legacy_yaml_data["hcd"].get("p_sol", np.nan)
    if p_sol_from_yaml == "tbd" or p_sol_from_yaml is None:
        p_sol_from_yaml = np.nan
    if not np.isnan(p_sol_from_ids):
        are_values_same = abs(p_sol_from_ids_W - p_sol_from_yaml) < 5e-2
        if are_values_same is False:
            validation_logger.info(
                f"\t> discrepancies found in power_loss (yaml,ids):[{p_sol_from_yaml}]," f"[{p_sol_from_ids}]"
            )
            validation_logger.info(f"\t> {debug_info}")

    if not ids_summary.global_quantities.power_loss.value.has_value:
        if p_sol_from_ids != 0.0 and not np.isnan(p_sol_from_ids):
            global_quantities["power_loss"] = {"value": float(p_sol_from_ids)}
        else:
            validation_logger.info(
                "\t> ids_summary.global_quantities.power_loss.value is empty "
                "and power loss from ids is empty, nothing to set"
            )
    else:
        validation_logger.info(
            "\t> ids_summary.global_quantities.power_loss.value is already set in the IDS, not setting"
        )
        validation_logger.info(
            f"\t>  (yaml,ids):[{p_sol_from_yaml}],[{ids_summary.global_quantities.power_loss.value}]"
        )

    main_species_yaml = legacy_yaml_data["scenario_key_parameters"]["main_species"]
    if main_species_yaml != "tbd" and main_species_yaml != "":
        global_quantities["main_species"] = main_species_yaml
    else:
        validation_logger.info("\t> main species from yaml is empty, nothing to set")
    # TODO how to calulate density_peaking? https://github.com/iterorganization/IMAS-Data-Dictionary/discussions/65
    # density_peaking_yaml = legacy_yaml_data["scenario_key_parameters"].get("density_peaking", "")
    # if density_peaking_yaml != "tbd" and density_peaking_yaml != "":
    #     global_quantities["density_peaking"] = density_peaking_yaml
    # else:
    #     validation_logger.info("\t> density peaking from yaml is empty, nothing to set")

    return global_quantities


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
            validation_logger.error(f"{alias} {uri}: {e}")
            return
        ids_summary = None
        ids_dataset_description = None
        ids_equilibrium = None
        ids_core_profiles = None
        ids_edge_profiles = None
        try:
            ids_summary = connection.get("summary", autoconvert=False, lazy=True, ignore_unknown_dd_version=True)
        except Exception as e:  # noqa: F841
            validation_logger.error(f"{alias}: {e}")
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

        validation_logger.info(f"{alias}")
        manifest_metadata = {}

        dataset_description = get_dataset_description(
            legacy_yaml_data=legacy_yaml_data, ids_summary=ids_summary, ids_dataset_description=ids_dataset_description
        )
        summary = {**dataset_description}
        heating_current_drive = get_heating_current_drive(legacy_yaml_data, ids_summary)
        if heating_current_drive and heating_current_drive != {}:
            summary["heating_current_drive"] = heating_current_drive
        global_quantities = get_global_quantities(legacy_yaml_data, slice_index, ids_summary, ids_equilibrium)
        if global_quantities and global_quantities != {}:
            summary["global_quantities"] = global_quantities

        local = get_local(
            legacy_yaml_data["scenario_key_parameters"],
            slice_index,
            ids_summary,
            ids_core_profiles,
            ids_edge_profiles,
        )
        if local and local != {}:
            summary["local"] = local

        if not ids_summary.ids_properties.creation_date.has_value:
            stat = os.stat(legacy_yaml_file)
            creation_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            summary["ids_properties"] = {"creation_date": creation_time}

        _plasma_composition = get_plasma_composition(legacy_yaml_data["plasma_composition"])
        composition = {}
        for species, properties in _plasma_composition.items():
            species_name = ion_names_map[species]  # if species in ion_names_map.keys() else species
            composition[species_name] = {}
            if "n_over_ne" in properties:
                composition[species_name]["value"] = properties["n_over_ne"]

        summary["composition"] = composition
        manifest_metadata["summary"] = summary
        out_data = {
            "manifest_version": 2,
            "responsible_name": legacy_yaml_data["responsible_name"],
            "alias": alias,
            "outputs": [{"uri": uri}],
            "inputs": [],
            "metadata": [manifest_metadata],
        }

        # manifest_file_path = os.path.join(os.path.dirname(legacy_yaml_file), f"manifest_{shot:06d}{run:04d}.yaml")

        manifest_file_path = os.path.join(output_directory, f"manifest_{shot:06d}{run:04d}.yaml")
        with open(manifest_file_path, "w") as file:
            yaml.dump(out_data, file, default_flow_style=False, sort_keys=False)

        if connection:
            connection.close()

        sys.stdout.write(".")
        validation_logger.info(
            "-----------------------------------------" "-------------------------------------------"
        )
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
    validation_logger.info(f"\nManifest files are written into  {output_directory}")
