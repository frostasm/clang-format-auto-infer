import sys
import time

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn, TimeRemainingColumn

# Seconds between two status lines when no progress bar is shown
STATUS_INTERVAL = 30.0


def _format_best(best):
    """Formats a fitness for the status: '-' while no evaluation has succeeded."""
    if best is None or best == float('inf'):
        return "-"
    return f"{best:g}"


def _format_duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


class RunProgress:
    """
    Shows the status of an optimization run: the completed steps (generations or evaluations),
    the number and rate of fitness evaluations, the best fitness, the elapsed and remaining time.

    On a terminal, without --verbose, it is a rich progress bar at the bottom of the output; the
    lines that the main process prints to stderr meanwhile appear above it. Otherwise (output
    redirected to a file, or --verbose with its many lines from the workers) it prints a status
    line every STATUS_INTERVAL seconds and at the end.
    """

    def __init__(self, description: str, total: int, verbose: bool):
        self.description = description
        self.total = total
        self.console = Console(stderr=True)
        self.use_bar = self.console.is_terminal and not verbose
        self._progress = None
        self._task = None
        self._start = None
        self._last_status = None
        self._state = (0, 0, None)

    def start(self):
        self._start = time.monotonic()
        self._last_status = self._start
        if self.use_bar:
            self._progress = Progress(
                TextColumn("[bold]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TextColumn("evals {task.fields[evaluations]} ({task.fields[rate]}/s)"),
                TextColumn("best [bold green]{task.fields[best]}"),
                TimeElapsedColumn(),
                TextColumn("eta"),
                TimeRemainingColumn(),
                console=self.console,
                redirect_stderr=True,
            )
            self._progress.start()
            self._task = self._progress.add_task(self.description, total=self.total, evaluations=0, rate="0.0", best="-")
        return self

    def update(self, completed: int, evaluations: int, best):
        """Updates the status; cheap enough to be called a few times per second."""
        self._state = (completed, evaluations, best)
        now = time.monotonic()
        elapsed = now - self._start
        rate = evaluations / elapsed if elapsed > 0 else 0.0
        if self._progress is not None:
            self._progress.update(self._task, completed=completed, evaluations=evaluations, rate=f"{rate:.1f}", best=_format_best(best))
        elif now - self._last_status >= STATUS_INTERVAL:
            self._last_status = now
            self._print_status(elapsed, rate)

    def stop(self):
        """Removes the progress bar (keeping its last state on the screen) or prints the final status."""
        if self._start is None:
            return
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
        else:
            elapsed = time.monotonic() - self._start
            _, evaluations, _ = self._state
            self._print_status(elapsed, evaluations / elapsed if elapsed > 0 else 0.0)

    def _print_status(self, elapsed, rate):
        completed, evaluations, best = self._state
        percent = 100.0 * completed / self.total if self.total else 100.0
        remaining = f", remaining ~{_format_duration(elapsed / completed * (self.total - completed))}" if completed else ""
        print(f"[status] {self.description} {completed}/{self.total} ({percent:.0f}%) | evals {evaluations} ({rate:.1f}/s) | "
              f"best {_format_best(best)} | elapsed {_format_duration(elapsed)}{remaining}", file=sys.stderr, flush=True)
