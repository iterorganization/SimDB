import sys
from typing import List, Dict, Tuple, TYPE_CHECKING, TypeVar
from collections import OrderedDict
import click

if TYPE_CHECKING or 'sphinx' in sys.modules:
    # Only importing these for type checking and documentation generation in order to speed up runtime startup.
    from simdb.database.models import Simulation
else:
    Config = TypeVar('Config')


def flatten_dict(values: Dict) -> List[Tuple[str, str]]:
    items = []
    for (k, v) in values.items():
        if type(v) == list:
            for n, i in enumerate(v):
                items.append(("{}[{}]".format(k, n), i))
        elif type(v) == dict:
            for i in flatten_dict(v):
                items.append(("{}.{}".format(k, i[0]), i[1]))
        else:
            items.append((k, v))
    return items


def print_simulations(simulations: List["Simulation"], verbose: bool = False, metadata_names: List[str] = None) -> None:
    if len(simulations) == 0:
        click.echo("No simulations found")
        return

    lines = []
    column_widths = OrderedDict(UUID=4, alias=5)
    if verbose:
        column_widths["datetime"] = 8
        column_widths["status"] = 6

    for sim in simulations:
        line = [str(sim.uuid), sim.alias if sim.alias else '']
        column_widths["UUID"] = max(column_widths["UUID"], len(str(sim.uuid)))
        column_widths["alias"] = max(column_widths["alias"], len(sim.alias) if sim.alias else 0)

        if verbose:
            line.append(sim.datetime)
            line.append(sim.status)
            column_widths["datetime"] = max(column_widths["datetime"], len(sim.datetime))
            column_widths["status"] = max(column_widths["status"], len(sim.status))

        if metadata_names:
            for name in metadata_names:
                meta = sim.find_meta(name)
                column_widths.setdefault(name, len(name))
                if meta:
                    line.append(str(meta[0].value))
                    column_widths[name] = max(column_widths[name], len(str(meta[0].value)))
                else:
                    line.append('')

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


def _print_trace_sim(trace_data: dict, indentation: int):
    spaces = ' ' * indentation

    if 'error' in trace_data:
        error = trace_data['error']
        click.echo(f"{spaces}{error}")
        return

    uuid = trace_data['uuid']
    alias = trace_data['alias']
    status = trace_data['status'] if 'status' in trace_data else 'unknown'

    click.echo(f"{spaces}Simulation: {uuid}")
    click.echo(f"{spaces}     Alias: {alias}")
    click.echo(f"{spaces}    Status: {status}")
    status_on_name = status + '_on'
    if status_on_name in trace_data:
        status_on = trace_data[status_on_name]
        label = status_on_name.replace('_', ' ').capitalize()
        click.echo(f"{spaces}{label}: {status_on}")

    if 'replaces' in trace_data:
        if 'replaces_reason' in trace_data:
            replaces_reason = trace_data['replaces_reason']
            click.echo(f'{spaces}Replaces: (reason: {replaces_reason})')
        else:
            click.echo(f'{spaces}Replaces:')
        _print_trace_sim(trace_data['replaces'], indentation + 2)


def print_trace(trace_data, verbose: bool = False) -> None:
    if not trace_data:
        click.echo("No simulations trace found")
        return

    _print_trace_sim(trace_data, 0)
