from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple, TypeVar

import click
import plotext
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    # Only importing these for type checking and documentation generation in order to
    # speed up runtime startup.
    from simdb.database.models import Simulation
else:
    Config = TypeVar("Config")

_RICH_CONSOLE = Console()


def _get_shape(data: Any) -> Tuple[int, ...]:
    """Recursively compute shape of a nested list"""
    if not isinstance(data, list):
        return ()
    if not data:
        return (0,)
    return (len(data), *_get_shape(data[0]))


def _fmt_val(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def _fmt_row(row: list) -> str:
    """Format a 1-D list with numpy-style head/tail truncation."""
    if len(row) <= 8:
        return " ".join(_fmt_val(v) for v in row)
    head = " ".join(_fmt_val(v) for v in row[:3])
    tail = " ".join(_fmt_val(v) for v in row[-3:])
    return f"{head} ... {tail}"


def _is_numeric(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_numeric_1d(data: Any) -> bool:
    return isinstance(data, list) and bool(data) and all(_is_numeric(v) for v in data)


def _quantity_axis_label(q: dict, fallback: str = "") -> str:
    name = q.get("name") or fallback
    units = q.get("units") or "-"
    label = str(name).rsplit("/", 1)[-1] or str(name)
    return f"{label} [{units}]"


def _build_array_body(data: list, shape: Tuple[int, ...]) -> str:
    """Build string for 1-D or 2-D arrays."""
    if len(shape) == 1:
        return f"[{_fmt_row(data)}]"

    if len(shape) == 2:
        if len(data) <= 8:
            rows = data
            lines = [f" [{_fmt_row(row)}]" for row in rows]
        else:
            lines = [f" [{_fmt_row(row)}]" for row in data[:3]]
            lines.append(" ...")
            lines += [f" [{_fmt_row(row)}]" for row in data[-3:]]
        formatted_lines = "\n".join(lines)
        return f"[\n{formatted_lines}\n]"

    return f"<{len(shape)}-D array, shape {shape}>"


def _iter_numeric(data: Any) -> Iterable[float]:
    """Yield all numeric leaf values from a nested list, skipping None."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_numeric(item)
    elif _is_numeric(data):
        yield float(data)


def _compute_stats(data: Any) -> Optional[Dict[str, float]]:
    """Return basic statistics for numeric data, or None if not applicable."""
    values = list(_iter_numeric(data))
    if len(values) < 2:
        return None
    n = len(values)
    vmin = min(values)
    vmax = max(values)
    mean = sum(values) / n
    std = (sum((x - mean) ** 2 for x in values) / n) ** 0.5
    sorted_v = sorted(values)
    mid = n // 2
    median = sorted_v[mid] if n % 2 else (sorted_v[mid - 1] + sorted_v[mid]) / 2
    return {
        "n": n,
        "min": vmin,
        "max": vmax,
        "mean": mean,
        "std": std,
        "median": median,
    }


def _stats_table(stats: Dict[str, float]) -> Table:
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    for key in ("n", "min", "max", "mean", "std", "median"):
        table.add_column(key, justify="right")
    table.add_row(
        str(int(stats["n"])),
        _fmt_val(stats["min"]),
        _fmt_val(stats["max"]),
        _fmt_val(stats["mean"]),
        _fmt_val(stats["std"]),
        _fmt_val(stats["median"]),
    )
    return table


def _plot_panel(
    *,
    plot: Text,
    title: str,
    units: str,
    shape: Tuple[int, ...],
) -> None:
    _RICH_CONSOLE.print(
        Panel(
            plot,
            title=f"[bold]{title}[/bold]  [dim]\\[{units}][/dim]",
            subtitle=f"shape {shape}",
        )
    )


def show_quantity_textual_plot(
    q: dict,
    label: str = "",
    x_quantity: Optional[dict] = None,
) -> None:
    """Print line plot for a 1-D numeric QuantityData dict."""
    name = q["name"]
    units = q["units"] or "-"
    data = q["data"]
    if not is_numeric_1d(data):
        print_quantity(q, label=label)
        return

    y_values = [float(value) for value in data]
    shape = _get_shape(data)
    x_values = None
    xlabel = "index [-]"
    if (
        x_quantity
        and is_numeric_1d(x_quantity.get("data"))
        and len(x_quantity["data"]) == len(y_values)
    ):
        x_values = [float(value) for value in x_quantity["data"]]
        xlabel = _quantity_axis_label(x_quantity, fallback="x")

    title = label or name
    if x_values is None:
        x_values = [float(index) for index in range(len(y_values))]

    console_width = _RICH_CONSOLE.size.width
    plot_width = max(48, min(70, console_width - 12))
    _, terminal_height = plotext.terminal_size()
    plot_height = max(12, min(24, terminal_height - 8))

    plotext.clear_figure()
    plotext.canvas_color("default")
    plotext.axes_color("default")
    plotext.ticks_color("default")
    plotext.plot_size(plot_width, plot_height)
    plotext.xlabel(xlabel)
    plotext.ylabel(_quantity_axis_label(q, fallback=label or "field"))
    plotext.plot(x_values, y_values, marker="braille", color="cyan")
    plot = Text.from_ansi(plotext.build())
    _plot_panel(
        plot=plot,
        title=title,
        units=units,
        shape=shape,
    )
    print_quantity(q, label=label)


def print_quantity(q: dict, label: str = "", show_stats: bool = True) -> None:
    """Print a QuantityData dict with array display and stats."""
    name = q["name"]
    units = q["units"] or "-"
    data = q["data"]
    title = f"[bold]{label or name}[/bold]  [dim]\\[{units}][/dim]"

    if not isinstance(data, list):
        _RICH_CONSOLE.print(Panel(f"{_fmt_val(data)}", title=title, subtitle="scalar"))
        return

    shape = _get_shape(data)
    stats = _compute_stats(data)
    array_body = _build_array_body(data, shape)
    subtitle = f"shape ({shape[0]},)" if len(shape) == 1 else f"shape {shape}"
    if show_stats and stats:
        _RICH_CONSOLE.print(
            Panel(
                Group(array_body, _stats_table(stats)),
                title=title,
                subtitle=subtitle,
            )
        )
    else:
        _RICH_CONSOLE.print(Panel(array_body, title=title, subtitle=subtitle))


def _flatten_dict(values: Dict) -> List[Tuple[str, str]]:
    items = []
    for k, v in values.items():
        if isinstance(v, list):
            for n, i in enumerate(v):
                items.append((f"{k}[{n}]", i))
        elif isinstance(v, dict):
            for i in _flatten_dict(v):
                items.append((f"{k}.{i[0]}", i[1]))
        else:
            items.append((k, v))
    return items


def _format_meta_value(meta_value: Any, max_len: int) -> str:
    """
    Format the meta value as a string, limiting list values to max_len.
    """
    if isinstance(meta_value, dict) and "min" in meta_value and "max" in meta_value:
        return f"[{meta_value['min']}, {meta_value['max']}]"
    if isinstance(meta_value, list):
        values = []
        for i, v in enumerate(meta_value):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                values.append(str(v))
            else:
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
    then the simulation datetime and status are also printed and metadata_names allows
    additional columns to be specified.

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
            line = [sim.alias or "", str(sim.uuid)]
            column_widths["alias"] = max(
                column_widths["alias"], len(sim.alias) if sim.alias else 0
            )
            column_widths["UUID"] = max(column_widths["UUID"], len(str(sim.uuid)))
        else:
            line = [sim.alias or ""]
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
            click.echo(f"{str(line[col]).ljust(width + 1)}", nl=False)
        click.echo()
        if not line_written:
            click.echo("-" * (sum(column_widths.values()) + len(column_widths) - 1))
            line_written = True
    if (lines.__len__() - 1) == 100:
        click.echo(
            "\n...first 100 entries shown, use command $simdb remote [NAME] list -l 0 "
            "to list all simulations.\n"
        )


def _print_trace_sim(trace_data: dict, indentation: int):
    spaces = " " * indentation

    if "error" in trace_data:
        error = trace_data["error"]
        click.echo(f"{spaces}{error}")
        return

    uuid = trace_data["uuid"]
    alias = trace_data["alias"]
    status = trace_data.get("status", "unknown")

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
