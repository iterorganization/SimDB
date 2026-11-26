"""Tests for the aligned push/pull progress display."""

import io
import re

import pytest
from rich.console import Console

from simdb.cli.transfer_progress import (
    NAME_MAX_WIDTH,
    ProgressStyle,
    TransferProgress,
    progress_style_from_config,
)


class _Config:
    def __init__(self, value=None):
        self._value = value

    def get_option(self, name, default=None):
        assert name == "cli.progress"
        return default if self._value is None else self._value


def _console() -> Console:
    return Console(file=io.StringIO(), width=160, force_terminal=True)


def _rendered_lines(progress: TransferProgress) -> list:
    console = _console()
    console.print(progress.progress.get_renderable())
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", console.file.getvalue())
    return [line for line in text.splitlines() if line.strip()]


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, ProgressStyle.COMPACT),
        ("compact", ProgressStyle.COMPACT),
        ("list", ProgressStyle.LIST),
        (" LIST ", ProgressStyle.LIST),
    ],
)
def test_progress_style_from_config(value, expected):
    assert progress_style_from_config(_Config(value)) is expected


def test_progress_style_invalid_falls_back_to_compact(capsys):
    assert progress_style_from_config(_Config("fancy")) is ProgressStyle.COMPACT
    assert "fancy" in capsys.readouterr().err


def test_name_width_is_longest_name_capped():
    p = TransferProgress(["a.h5", "longer_name.h5"], ProgressStyle.COMPACT, "Up")
    assert p.name_width == len("longer_name.h5")
    p = TransferProgress(["x" * 100], ProgressStyle.COMPACT, "Up")
    assert p.name_width == NAME_MAX_WIDTH


def test_compact_has_single_file_row_above_overall():
    names = ["master.h5", "core_profiles.h5", "equilibrium.h5"]
    p = TransferProgress(names, ProgressStyle.COMPACT, "Upload", console=_console())
    for i in range(len(names)):
        p.start_file(i, 20)
        p.update_file(20)
        p.finish_file()
    tasks = p.progress.tasks
    assert len(tasks) == 2
    assert tasks[-1].description == "Upload"
    assert tasks[-1].completed == 3
    assert tasks[0].description == "equilibrium.h5"
    lines = _rendered_lines(p)
    assert len(lines) == 2
    assert lines[-1].startswith("Upload")
    assert "3/3 files" in lines[-1]


def test_list_keeps_one_row_per_started_file_in_order():
    names = ["master.h5", "core_profiles.h5", "equilibrium.h5"]
    p = TransferProgress(names, ProgressStyle.LIST, "Download", console=_console())
    for i in range(2):
        p.start_file(i, None)
        p.advance_file(10)
        p.finish_file()
    tasks = p.progress.tasks
    assert [t.description for t in tasks] == [*names, "Download"]
    assert [t.visible for t in tasks] == [True, True, False, True]
    assert tasks[-1].completed == 2
    # Unknown size: the row settles on what was read.
    assert tasks[0].total == 10
    # A row not started yet has no running timer.
    assert not tasks[2].started

    lines = _rendered_lines(p)
    assert [line.split()[0] for line in lines] == [*names[:2], "Download"]
    assert "2/3 files" in lines[-1]


def test_overall_counts_files_and_moves_through_current_file():
    names = ["a.h5", "b.h5"]
    p = TransferProgress(names, ProgressStyle.COMPACT, "Upload", console=_console())
    p.start_file(0, 100)
    p.update_file(50)
    overall = p.progress.tasks[-1]
    assert overall.total == 2
    assert overall.completed == 0.5
    # The counter only shows whole files done.
    assert "0/2 files" in _rendered_lines(p)[-1]


def test_overall_only_shows_no_file_rows():
    names = ["a.h5", "b.h5"]
    p = TransferProgress(
        names, ProgressStyle.LIST, "Checksums", show_files=False, console=_console()
    )
    for i in range(2):
        p.start_file(i, 10)
        p.advance_file(10)
        p.finish_file()
    lines = _rendered_lines(p)
    assert len(lines) == 1
    assert lines[0].startswith("Checksums")
    assert "2/2 files" in lines[0]


def test_columns_are_aligned_across_rows():
    names = ["a.h5", "dataset_description.h5", "core.h5"]
    p = TransferProgress(names, ProgressStyle.LIST, "Upload", console=_console())
    for i, size in enumerate([5, 2_000_000, 300]):
        p.start_file(i, size)
        p.update_file(size // 2)
    lines = _rendered_lines(p)
    assert len(lines) == 4
    # The bar starts at the same column on every row, whatever the name length.
    bar_starts = {re.search(r"[━╸╺]", line).start() for line in lines}
    assert len(bar_starts) == 1
    assert len({len(line.rstrip()) for line in lines}) == 1


def test_overall_counts_bytes_when_total_known():
    names = ["a.h5", "b.h5"]
    p = TransferProgress(
        names, ProgressStyle.COMPACT, "Upload", total_bytes=300, console=_console()
    )
    p.start_file(0, 100)
    p.update_file(100)
    p.finish_file()
    p.start_file(1, 200)
    p.update_file(50)
    overall = p.progress.tasks[-1]
    assert overall.total == 300
    assert overall.completed == 150
    assert "files" not in _rendered_lines(p)[-1]
    p.update_file(200)
    p.finish_file()
    assert p.progress.tasks[-1].completed == 300
