"""Progress display shared by the push (checksum, upload) and pull transfers.

All rows of one transfer phase live in a single :class:`rich.progress.Progress`
whose columns have fixed widths, so file names, bars, sizes and speeds stay
vertically aligned from one file to the next. The per-file row(s) are rendered
above an overall row. The overall row shows bytes and speed when the total
size is known up front (upload), and counts files (``2/5 files``) otherwise
(checksums, download); in that case its bar also moves through the file in
progress so it advances smoothly.
The right-most column is the elapsed time of each row.

Two styles are available, selected with the ``cli.progress`` config option:

* ``compact`` (default): a single file row, overwritten for each file.
* ``list``: one row per file, kept on screen once the file is done.
"""

import sys
from enum import Enum
from typing import TYPE_CHECKING, Optional, Sequence

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    ProgressColumn,
    Task,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)
from rich.table import Column
from rich.text import Text

if TYPE_CHECKING:
    from simdb.config import Config

PROGRESS_OPTION = "cli.progress"

NAME_MAX_WIDTH = 40
BAR_WIDTH = 40
SIZE_WIDTH = 21
SPEED_WIDTH = 12
TIME_WIDTH = 8


class ProgressStyle(str, Enum):
    COMPACT = "compact"
    """One file row overwritten for each file, with the overall row below."""
    LIST = "list"
    """One row per file, kept once done, with the overall row below."""


def progress_style_from_config(config: "Config") -> ProgressStyle:
    """Return the progress style set by the ``cli.progress`` option.

    An unknown value prints a warning on stderr and falls back to ``compact``.
    """
    value = config.get_option(PROGRESS_OPTION, default=ProgressStyle.COMPACT.value)
    try:
        return ProgressStyle(str(value).strip().lower())
    except ValueError:
        choices = ", ".join(s.value for s in ProgressStyle)
        print(
            f"Warning: invalid value '{value}' for option {PROGRESS_OPTION} "
            f"(expected one of: {choices}), using "
            f"'{ProgressStyle.COMPACT.value}'.",
            file=sys.stderr,
        )
        return ProgressStyle.COMPACT


def _counts_files(task: Task) -> bool:
    return bool(task.fields.get("count_files"))


class _SizeColumn(ProgressColumn):
    """Bytes as ``done/total unit``, or ``done/total files`` on a file-count row."""

    def __init__(self) -> None:
        self._download = DownloadColumn()
        super().__init__(
            table_column=Column(width=SIZE_WIDTH, justify="right", no_wrap=True)
        )

    def render(self, task: Task) -> Text:
        if _counts_files(task):
            done = task.fields.get("files_done", 0)
            return Text(
                f"{done}/{int(task.total or 0)} files", style="progress.download"
            )
        return self._download.render(task)


class _SpeedColumn(TransferSpeedColumn):
    """Transfer speed, blank on a file-count row."""

    def render(self, task: Task) -> Text:
        if _counts_files(task):
            return Text("")
        return super().render(task)


class TransferProgress:
    """Aligned progress display for one transfer phase (see module docstring).

    :param names: display names of all files of the phase, in transfer order;
        they fix the name column width and, in ``list`` style, the row order.
    :param style: compact or list rendering.
    :param overall_label: label of the overall row (e.g. ``"Upload"``).
    :param show_files: ``False`` to show only the overall row (used for the
        checksum step, so its files are not listed twice with the upload).
    :param total_bytes: total size of all files, when known up front: the
        overall row then shows bytes and speed (upload). Without it, the overall
        row counts files (checksums, and download, where sizes are only known
        once each file starts).
    """

    def __init__(
        self,
        names: Sequence[str],
        style: ProgressStyle,
        overall_label: str,
        show_files: bool = True,
        total_bytes: Optional[int] = None,
        console: Optional[Console] = None,
    ) -> None:
        self._names = list(names)
        self._style = ProgressStyle(style)
        self._show_files = show_files
        self.name_width = min(
            max([len(n) for n in self._names] + [len(overall_label)]),
            NAME_MAX_WIDTH,
        )
        self.progress = Progress(
            TextColumn(
                "[bold blue]{task.description}",
                table_column=Column(
                    width=self.name_width, no_wrap=True, overflow="ellipsis"
                ),
            ),
            BarColumn(bar_width=BAR_WIDTH),
            _SizeColumn(),
            _SpeedColumn(
                table_column=Column(width=SPEED_WIDTH, justify="right", no_wrap=True)
            ),
            TimeElapsedColumn(
                table_column=Column(width=TIME_WIDTH, justify="right", no_wrap=True)
            ),
            console=console,
        )
        # File rows are added before the overall row so it is always rendered
        # last; they are not started (timer stopped) until their file starts.
        rows = self._names if self._style is ProgressStyle.LIST else [""]
        self._file_tasks = (
            [
                self.progress.add_task(name, total=None, visible=False, start=False)
                for name in rows
            ]
            if show_files
            else []
        )
        self._count_bytes = total_bytes is not None
        self._overall = self.progress.add_task(
            overall_label,
            total=total_bytes if self._count_bytes else len(self._names),
            count_files=not self._count_bytes,
            files_done=0,
        )
        self._current: Optional[TaskID] = None
        self._current_done = 0
        self._current_total: Optional[int] = None
        self._files_done = 0
        self._bytes_done = 0

    def _task(self, task_id: TaskID) -> Task:
        return next(t for t in self.progress.tasks if t.id == task_id)

    def __enter__(self) -> "TransferProgress":
        self.progress.start()
        return self

    def __exit__(self, *exc) -> None:
        self.progress.stop()

    def _update_overall(self) -> None:
        if self._count_bytes:
            self.progress.update(
                self._overall, completed=self._bytes_done + self._current_done
            )
            return
        fraction = 0.0
        if self._current_total:
            fraction = min(self._current_done / self._current_total, 1.0)
        self.progress.update(
            self._overall,
            completed=self._files_done + fraction,
            files_done=self._files_done,
        )

    def start_file(self, index: int, total: Optional[int]) -> None:
        """Start the row of file ``index`` (in ``names``), of ``total`` bytes."""
        self._current_done = 0
        self._current_total = total
        if not self._show_files:
            self._current = None
            return
        if self._style is ProgressStyle.LIST:
            task = self._file_tasks[index]
            self.progress.update(task, total=total, visible=True)
            self.progress.start_task(task)
        else:
            task = self._file_tasks[0]
            # reset() also restarts the row's elapsed timer.
            self.progress.reset(
                task, total=total, description=self._names[index], visible=True
            )
        self._current = task

    def update_file(self, completed: int) -> None:
        """Set the current file progress to ``completed`` bytes."""
        self._current_done = completed
        if self._current is not None:
            self.progress.update(self._current, completed=completed)
        self._update_overall()

    def advance_file(self, n: int) -> None:
        """Advance the current file progress by ``n`` bytes."""
        self.update_file(self._current_done + n)

    def finish_file(self) -> None:
        """Mark the current file as done and count it in the overall row."""
        if self._current is not None:
            task = self._task(self._current)
            if task.total is None:
                # Size unknown up front (no content-length): settle on what was read.
                self.progress.update(self._current, total=self._current_done)
            self.progress.update(
                self._current, completed=self._task(self._current).total
            )
        self._files_done += 1
        self._bytes_done += max(self._current_total or 0, self._current_done)
        self._current = None
        self._current_done = 0
        self._current_total = None
        self._update_overall()
