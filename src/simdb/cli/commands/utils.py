import sys
from typing import List, Dict, Tuple, TYPE_CHECKING, TypeVar, TextIO


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


def print_simulations(simulations: List["Simulation"], verbose: bool=False, metadata_names: list=None,
                      out_stream: TextIO=sys.stdout) -> None:
    if len(simulations) == 0:
        print("No simulations found", file=out_stream)
        return

    lines = []
    header = ["UUID", "alias"]
    if verbose:
        header.append("datetime")
        header.append("status")

    for sim in simulations:
        line = [str(sim.uuid), sim.alias]
        if verbose:
            line.append(sim.datetime)
            line.append(sim.status)
        if metadata_names:
            for name in metadata_names:
                if sim.find_meta(name):
                    if name not in header:
                        header.append(name)
                    line.append(sim.find_meta(name)[0].data()["value"])
        if not lines:
            lines.append(header)
        lines.append(line)

    column_widths = [0] * len(header)
    for line in lines:
        for col in range(len(line)):
            width = len(str(line[col]))
            if width > column_widths[col]:
                column_widths[col] = width
              
    line_written = False
    for line in lines:
        for col in range(len(line)):
            print("%s" % str(line[col]).ljust(column_widths[col] + 1), end="", file=out_stream)
        print(file=out_stream)
        if not line_written:
            print("-" * (sum(column_widths) + len(column_widths) - 1), file=out_stream)
            line_written = True
