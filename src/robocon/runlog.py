"""Time-trial results, kept in a CSV file so they survive restarts.

The default file is ``~/.local/share/robocon/time_trials.csv`` (override the
folder with ``ROBOCON_DATA``). Each row is one finished run:

    finished_at, time_s, reference_s, delta_s, wall_hits
"""

from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

FIELDS = ["finished_at", "time_s", "reference_s", "delta_s", "wall_hits"]


@dataclass(frozen=True)
class Run:
    finished_at: str  # ISO 8601, local time
    time: float  # seconds from first input to crossing Line 1
    reference: float  # the line follower's time for the same course
    wall_hits: int

    @property
    def delta(self) -> float:
        """Seconds slower (+) or faster (-) than the line follower."""
        return self.time - self.reference


def default_log_path() -> Path:
    data = os.environ.get("ROBOCON_DATA")
    folder = Path(data) if data else Path.home() / ".local" / "share" / "robocon"
    return folder / "time_trials.csv"


class RunLog:
    """Finished runs, oldest first. With ``path=None`` runs are kept in memory only."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.runs: list[Run] = self._read() if path else []

    def add(self, time: float, reference: float, wall_hits: int) -> Run:
        run = Run(datetime.now().isoformat(timespec="seconds"), time, reference, wall_hits)
        self.runs.append(run)
        if self.path:
            self._append(run)
        return run

    @property
    def best(self) -> Run | None:
        return min(self.runs, key=lambda r: r.time, default=None)

    def recent(self, count: int) -> list[Run]:
        """The latest ``count`` runs, newest first."""
        return self.runs[-count:][::-1]

    def _read(self) -> list[Run]:
        assert self.path is not None
        if not self.path.is_file():
            return []
        runs = []
        with self.path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    runs.append(
                        Run(
                            row["finished_at"],
                            float(row["time_s"]),
                            float(row["reference_s"]),
                            int(row["wall_hits"]),
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    log.warning("skipping unreadable row in %s: %s", self.path, row)
        return runs

    def _append(self, run: Run) -> None:
        assert self.path is not None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            new_file = not self.path.is_file()
            with self.path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                if new_file:
                    writer.writerow(FIELDS)
                writer.writerow(
                    [
                        run.finished_at,
                        f"{run.time:.3f}",
                        f"{run.reference:.3f}",
                        f"{run.delta:+.3f}",
                        run.wall_hits,
                    ]
                )
        except OSError:
            log.warning("could not save the run to %s", self.path)
