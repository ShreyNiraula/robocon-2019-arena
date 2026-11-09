"""Match: you drive blue MR1, red runs itself, and the first MR2 to the Uukhai zone wins.

As in the rules, MR1 is driven by hand and MR2 is automatic. You drive
the blue MR1 from Khangai urtuu along the white guideline (checkpoints on every
corner and on the bridge), across Line 1 and up to Gobi urtuu, where it hands
the Gerege to the blue MR2. From then on blue MR2 runs on its own over the sand
dune, through the tussock and up the mountain.

Red is a line follower that stops at every corner, with the same top speed
and acceleration as your robot, followed by its own automatic MR2. Both teams
start at your first input. Whichever MR2 reaches the Uukhai zone first wins.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pyglm import glm

from robocon import config
from robocon.collision import Collider, forest_lane_walls
from robocon.modes import Mode, place_mr2, place_on_floor, sway
from robocon.mr2 import Mr2Run
from robocon.path import (
    HANDOFF_X,
    LANE_TOP_Z,
    LINE_1_X,
    LINE_1_Z,
    LineFollower,
    MotionLimits,
    mr1_route,
)
from robocon.scene import Entity, LineSet
from robocon.trial import AMBER, GREEN, GREY, Driver, course_checkpoints, ring

if TYPE_CHECKING:
    from robocon.simulation import Simulation

BLUE, RED = 1, -1
HANDOFF_RADIUS = 0.5  # drive within this distance of Gobi urtuu's hand-off point


class Match(Mode):
    key = 4
    name = "Match"
    description = (
        "Drive the blue MR1 through the forest and across Line 1 to hand the Gerege to "
        "blue MR2, which then runs on its own. Red is a line follower. "
        "First MR2 to the Uukhai zone wins."
    )
    hints = (("Arrows / I J K L", "drive the blue MR1"),)
    panel_heading = "MATCH"

    def __init__(self) -> None:
        self.limits = MotionLimits(config.MR1_MAX_SPEED, config.MR1_ACCEL)
        self.mr1 = mr1_route(RED)  # red's scripted MR1
        self.follower = LineFollower(self.mr1, self.limits)
        self.red_mr2 = Mr2Run(RED)
        self.blue_mr2 = Mr2Run(BLUE)
        self.collider = Collider(forest_lane_walls(), config.MR1_RADIUS)
        self.checkpoints = course_checkpoints(BLUE)
        self.handoff_point = glm.vec2(BLUE * HANDOFF_X, LANE_TOP_Z)
        self.finish_x = BLUE * (LINE_1_X - config.MR1_RADIUS)  # whole robot past Line 1
        self._reset()

    def _reset(self) -> None:
        start = glm.vec2(config.ROBOT_BLUE_START.x, config.ROBOT_BLUE_START.z)
        self.driver = Driver(start, self.limits, self.collider)
        self.phase = "ready"  # ready -> running -> finished
        self.clock = 0.0  # match time, from the first input
        self.next_checkpoint = 0
        self.crossed_line_1 = False
        self.blue_handoff_at: float | None = None
        self.winner: str | None = None

    # -- timings -------------------------------------------------------------
    @property
    def handoff_time(self) -> float:
        """When red MR1 hands over to red MR2."""
        return self.follower.total_time

    @property
    def red_finish_time(self) -> float:
        return self.handoff_time + self.red_mr2.total_time

    @property
    def blue_finish_time(self) -> float | None:
        if self.blue_handoff_at is None:
            return None
        return self.blue_handoff_at + self.blue_mr2.total_time

    # -- mode hooks ----------------------------------------------------------
    def enter(self, sim: Simulation) -> None:
        self._reset()
        place_on_floor(sim.scene.robot_blue, self.driver.position)

    def update(self, sim: Simulation, t: float, dt: float) -> None:
        scene = sim.scene
        drive = glm.vec2(sim.drive)
        if self.phase == "ready":
            if glm.length(drive) == 0:
                scene.spider_red.yaw = scene.spider_blue.yaw = sway(t)
                return
            self.phase = "running"  # both teams start now
        self.clock += dt

        if self.blue_handoff_at is not None:
            drive = glm.vec2(0.0)  # blue MR1's job is done; it rolls to a stop
        self.driver.update(drive, dt)
        place_on_floor(scene.robot_blue, self.driver.position)
        if self.blue_handoff_at is None:
            self._blue_progress()

        place_on_floor(scene.robot_red, self.mr1.point(self.follower.distance_at(self.clock)))
        self._place_mr2(scene.spider_red, self.red_mr2, self.clock - self.handoff_time, t)
        blue_run_t = -1.0 if self.blue_handoff_at is None else self.clock - self.blue_handoff_at
        self._place_mr2(scene.spider_blue, self.blue_mr2, blue_run_t, t)

        if self.winner is None:
            self._decide_winner()

    def _place_mr2(self, entity: Entity, run: Mr2Run, run_t: float, t: float) -> None:
        if run_t < 0:
            entity.yaw = sway(t)  # still waiting in Gobi urtuu for the Gerege
        else:
            place_mr2(entity, run, run_t)

    def _blue_progress(self) -> None:
        position = self.driver.position
        if self.next_checkpoint < len(self.checkpoints):
            if glm.distance(position, self.checkpoints[self.next_checkpoint]) < (
                config.CHECKPOINT_RADIUS
            ):
                self.next_checkpoint += 1
        elif not self.crossed_line_1:
            in_lane = LINE_1_Z[0] < position.y < LINE_1_Z[1]
            self.crossed_line_1 = in_lane and BLUE * (position.x - self.finish_x) <= 0
        elif glm.distance(position, self.handoff_point) < HANDOFF_RADIUS:
            self.blue_handoff_at = self.clock

    def _decide_winner(self) -> None:
        blue = self.blue_finish_time
        red = self.red_finish_time
        blue_done = blue is not None and self.clock >= blue
        red_done = self.clock >= red
        if blue_done or red_done:
            self.winner = "blue" if blue_done and (not red_done or blue <= red) else "red"
            self.phase = "finished"

    # -- presentation --------------------------------------------------------
    def status(self, sim: Simulation) -> str:
        if self.phase == "ready":
            return "Drive the blue MR1 to start. Red starts at the same moment."
        if self.phase == "finished":
            return f"{self.winner.upper()} WINS - UUKHAI! Press R to play again."
        if self.blue_handoff_at is not None:
            return "Hand-off done: blue MR2 runs on its own. Watch the race!"
        if self.next_checkpoint < len(self.checkpoints):
            return f"Drive to checkpoint {self.next_checkpoint + 1} of {len(self.checkpoints)}."
        if not self.crossed_line_1:
            return "Cross Line 1 (the blue line across the top lane)."
        return "Drive into Gobi urtuu (the ring) to hand the Gerege to blue MR2."

    def panel_rows(self, sim: Simulation) -> list[tuple[str, str]]:
        rows = [("Clock", f"{math.floor(self.clock * 10) / 10:.1f} s")]
        rows.append(("Blue", self._blue_label()))
        rows.append(("Red", self._red_label()))
        if self.phase == "finished":
            # Each team's time appears once its MR2 has actually reached the Uukhai zone.
            for team, finish in (("Blue", self.blue_finish_time), ("Red", self.red_finish_time)):
                reached = finish is not None and self.clock >= finish
                rows.append((f"{team} UUKHAI", f"{finish:.1f} s" if reached else "not yet"))
        return rows

    def _blue_label(self) -> str:
        if self.blue_handoff_at is None:
            if self.next_checkpoint < len(self.checkpoints):
                return f"MR1, checkpoint {self.next_checkpoint} / {len(self.checkpoints)}"
            return "MR1, to Gobi urtuu" if self.crossed_line_1 else "MR1, to Line 1"
        return f"MR2, {self.blue_mr2.label(self.clock - self.blue_handoff_at)}"

    def _red_label(self) -> str:
        if self.clock < self.handoff_time:
            return "MR1, in the forest"
        return f"MR2, {self.red_mr2.label(self.clock - self.handoff_time)}"

    def overlay_lines(self, sim: Simulation) -> list[LineSet]:
        if self.blue_handoff_at is not None:
            return []
        lines: list[LineSet] = []
        remaining = self.checkpoints[self.next_checkpoint :]
        if remaining:
            lines.append((AMBER, ring(remaining[0], config.CHECKPOINT_RADIUS)))
            later = [seg for c in remaining[1:] for seg in ring(c, config.CHECKPOINT_RADIUS * 0.5)]
            lines.append((GREY, later))
        x = BLUE * LINE_1_X
        line_color = GREY if remaining else GREEN
        lines.append(
            (line_color, [(glm.vec3(x, 0.06, LINE_1_Z[0]), glm.vec3(x, 0.06, LINE_1_Z[1]))])
        )
        if self.crossed_line_1:
            lines.append((AMBER, ring(self.handoff_point, HANDOFF_RADIUS)))
        return lines

    def autopilot(self, sim: Simulation) -> glm.vec2:
        """Steer at the next checkpoint, then the hand-off point (for tests and screenshots)."""
        if self.blue_handoff_at is not None:
            return glm.vec2(0.0)
        if self.next_checkpoint < len(self.checkpoints):
            target = self.checkpoints[self.next_checkpoint]
        else:
            target = self.handoff_point
        return target - self.driver.position
