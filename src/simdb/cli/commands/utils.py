from typing import List, Dict, Tuple, TYPE_CHECKING, TypeVar, Optional, Any
from collections import OrderedDict
import uuid
import click
import numpy

if TYPE_CHECKING:
    # Only importing these for type checking and documentation generation in order to speed up runtime startup.
    from ...database.models import Simulation
else:
    Config = TypeVar("Config")


def _flatten_dict(values: Dict) -> List[Tuple[str, str]]:
    items = []
    for k, v in values.items():
        if isinstance(v, list):
            for n, i in enumerate(v):
                items.append(("{}[{}]".format(k, n), i))
        elif isinstance(v, dict):
            for i in _flatten_dict(v):
                items.append(("{}.{}".format(k, i[0]), i[1]))
        else:
            items.append((k, v))
    return items


def _format_meta_value(meta_value: Any, max_len: int) -> str:
    """
    Format the meta value as a string, limiting array values to max_len.
    """
    if isinstance(meta_value, list) or isinstance(meta_value, numpy.ndarray):
        values = []
        for i, v in enumerate(meta_value):
            values.append(f"{v:.2f}")
            if i >= max_len - 1:
                values.append("...")
                break
        output = ", ".join(values)
        return f"[{output}]"
    return str(meta_value)


def print_simulations(
    simulations: List["Simulation"],
    verbose: bool = False,
    metadata_names: Optional[List[str]] = None,
    show_uuid: bool = False,
) -> None:
    """
    Print a table of simulations to the console.

    By default, only the simulation alias is printed on each row. If verbose is True
    then the simulation datetime and status are also printed and metadata_names allows additional
    columns to be specified.

    :param simulations: The simulations to print.
    :param verbose: Whether to print a more verbose table.
    :param metadata_names: Additional metadata fields to print as extra columns.
    :param show_uuid: Whether to include UUID column.
    :return: None
    """
    if len(simulations) == 0:
        click.echo("No simulations found")
        return

    lines = []
    if show_uuid:
        column_widths: Dict[str, int] = OrderedDict(alias=5, UUID=4)
    else:
        column_widths: Dict[str, int] = OrderedDict(alias=5)
    if verbose:
        column_widths["datetime"] = 8
        column_widths["status"] = 6

    for sim in simulations:
        if show_uuid:
            line = [sim.alias if sim.alias else "", str(sim.uuid)]
            column_widths["alias"] = max(
                column_widths["alias"], len(sim.alias) if sim.alias else 0
            )
            column_widths["UUID"] = max(column_widths["UUID"], len(str(sim.uuid)))
        else:
            line = [sim.alias if sim.alias else ""]
            column_widths["alias"] = max(
                column_widths["alias"], len(sim.alias) if sim.alias else 0
            )

        if verbose:
            line.append(sim.datetime)
            line.append(sim.status)
            column_widths["datetime"] = max(
                column_widths["datetime"], len(str(sim.datetime))
            )
            column_widths["status"] = max(column_widths["status"], len(str(sim.status)))

        if metadata_names:
            for name in metadata_names:
                meta = sim.find_meta(name)
                column_widths.setdefault(name, len(name))
                if meta:
                    value = _format_meta_value(meta[0].value, 5)
                    line.append(value)
                    column_widths[name] = max(column_widths[name], len(value))
                else:
                    line.append("")

        if not lines:
            lines.append(list(column_widths.keys()))

        lines.append(line)

    line_written = False
    for line in lines:
        for col, width in enumerate(column_widths.values()):
            click.echo("%s" % str(line[col]).ljust(width + 1), nl=False)
        click.echo()
        if not line_written:
            click.echo("-" * (sum(column_widths.values()) + len(column_widths) - 1))
            line_written = True
    if (lines.__len__() - 1) == 100:
        click.echo(
            "\n...first 100 entries shown, use command $simdb remote [NAME] list -l 0 to list all simulations.\n"
        )


def _print_trace_sim(trace_data: dict, indentation: int):
    spaces = " " * indentation

    if "error" in trace_data:
        error = trace_data["error"]
        click.echo(f"{spaces}{error}")
        return

    uuid = trace_data["uuid"]
    alias = trace_data["alias"]
    status = trace_data["status"] if "status" in trace_data else "unknown"

    click.echo(f"{spaces}Simulation: {uuid}")
    click.echo(f"{spaces}     Alias: {alias}")
    click.echo(f"{spaces}    Status: {status}")
    status_on_name = status + "_on"
    if status_on_name in trace_data:
        status_on = trace_data[status_on_name]
        label = status_on_name.replace("_", " ").capitalize()
        click.echo(f"{spaces}{label}: {status_on}")

    if "replaces" in trace_data:
        if "replaces_reason" in trace_data:
            replaces_reason = trace_data["replaces_reason"]
            click.echo(f"{spaces}Replaces: (reason: {replaces_reason})")
        else:
            click.echo(f"{spaces}Replaces:")
        _print_trace_sim(trace_data["replaces"], indentation + 2)


def print_trace(trace_data: dict) -> None:
    """
    Print the simulation trace data to the console.

    :param trace_data: A dictionary containing the simulation trace data.
    :return: None
    """
    if not trace_data:
        click.echo("No simulations trace found")
        return

    _print_trace_sim(trace_data, 0)
