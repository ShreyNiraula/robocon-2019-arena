"""Time trial: drive MR1 along the forest guideline against a line-following ghost.

The course follows the rules for MR1: start in Khangai urtuu, follow the
white guideline through the forest (rule 1.4.2), cross the river over the
bridge (rule 1.4.4) and cross Line 1 completely (rule 1.4.1). Checkpoints sit
on the guideline's corners and the bridge and must be passed in order.

The reference ("ideal") time is a line follower with the same top speed and
acceleration as your robot that brakes to a stop at every corner. It drives
as the ghost (the blue robot). Carry speed through the corners to beat it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pyglm import glm

from robocon import config
from robocon.collision import Collider, forest_lane_walls
from robocon.modes import Mode, place_on_floor, sway
from robocon.path import (
    BRIDGE,
    FOREST_GUIDELINE,
    LANE_TOP_Z,
    LINE_1_X,
    LINE_1_Z,
    LineFollower,
    MotionLimits,
    mr1_route,
)
from robocon.scene import LineSet

if TYPE_CHECKING:
    from robocon.simulation import Simulation

SIDE = -1  # the red half
GREEN, AMBER, GREY = (0.3, 1.0, 0.4), (1.0, 0.8, 0.2), (0.5, 0.5, 0.5)
CONTACT_RELEASE = 0.05  # how far the robot must back off before another wall hit counts


def course_checkpoints(side: int = SIDE) -> list[glm.vec2]:
    """Every corner of the guideline, plus the middle of the bridge, in driving order."""
    corners = FOREST_GUIDELINE[1:-1]
    before_bridge = corners.index((BRIDGE[0], LANE_TOP_Z))
    points = corners[:before_bridge] + [BRIDGE] + corners[before_bridge:]
    return [glm.vec2(side * x, z) for x, z in points]


class Driver:
    """A robot driven by hand: velocity eases towards the input within an acceleration limit."""

    def __init__(self, position: glm.vec2, limits: MotionLimits, collider: Collider) -> None:
        self.position = glm.vec2(position)
        self.velocity = glm.vec2(0.0)
        self.limits = limits
        self.collider = collider
        self.wall_hits = 0
        self._in_contact = False

    def update(self, drive: glm.vec2, dt: float) -> None:
        if dt <= 0:
            return
        target = glm.vec2(0.0)
        if glm.length(drive) > 0:
            target = glm.normalize(drive) * self.limits.max_speed
        change = target - self.velocity
        max_change = self.limits.accel * dt
        if glm.length(change) > max_change:
            change = glm.normalize(change) * max_change
        self.velocity += change

        wanted = self.position + self.velocity * dt
        moved = self.collider.move(self.position, self.velocity * dt)
        if glm.distance(moved, wanted) > 1e-6:  # a wall stopped part of the move
            self.velocity = (moved - self.position) / dt  # keep only the sliding part
            if not self._in_contact:
                self.wall_hits += 1
                self._in_contact = True
        elif self._in_contact and self.collider.clearance(moved) > CONTACT_RELEASE:
            self._in_contact = False  # pulled clear: the next touch counts as a new hit
        self.position = moved


class TimeTrial(Mode):
    key = 6
    name = "Time trial"
    description = (
        "Drive red MR1 through the checkpoints on the white line and across Line 1. "
        "Blue ghost: a line follower that stops at each corner."
    )
    hints = (("Arrows / I J K L", "drive red MR1"),)
    panel_heading = "TIME TRIAL"

    def __init__(self) -> None:
        self.limits = MotionLimits(config.MR1_MAX_SPEED, config.MR1_ACCEL)
        self.route = mr1_route(SIDE)
        self.ghost = LineFollower(self.route, self.limits)
        self.checkpoints = course_checkpoints(SIDE)
        self.collider = Collider(forest_lane_walls(), config.MR1_RADIUS)
        # The run ends when the whole robot is past Line 1.
        self.finish_x = SIDE * LINE_1_X - SIDE * config.MR1_RADIUS
        finish_distance = self.route.project((self.finish_x, LANE_TOP_Z))
        self.reference_time = self.ghost.time_at(finish_distance)
        self.reference_splits = [
            self.ghost.time_at(self.route.project(c)) for c in self.checkpoints
        ]
        self._reset()

    def _reset(self) -> None:
        start = self.route.point(0.0)
        self.driver = Driver(start, self.limits, self.collider)
        self.phase = "ready"  # ready -> running -> finished
        self.elapsed = 0.0
        self.next_checkpoint = 0
        self.last_split: float | None = None
        self.result = None

    # -- mode hooks ----------------------------------------------------------
    def enter(self, sim: Simulation) -> None:
        self._reset()
        sim.camera.set_pose(*config.TRIAL_CAMERA)
        sim.scene.spider_blue.visible = False
        place_on_floor(sim.scene.robot_red, self.driver.position)
        place_on_floor(sim.scene.robot_blue, self.driver.position)

    def update(self, sim: Simulation, t: float, dt: float) -> None:
        drive = glm.vec2(sim.drive)
        if self.phase == "ready" and glm.length(drive) > 0:
            self.phase = "running"
        if self.phase == "finished":
            drive = glm.vec2(0.0)  # coast to a stop after the line
        if self.phase == "running":
            self.elapsed += dt
        self.driver.update(drive, dt)
        position = self.driver.position

        if self.phase == "running":
            self._check_progress(sim, position)

        place_on_floor(sim.scene.robot_red, position)
        ghost_distance = self.ghost.distance_at(self.elapsed)
        place_on_floor(sim.scene.robot_blue, self.route.point(ghost_distance))
        sim.scene.spider_red.yaw = sway(t)

    def _check_progress(self, sim: Simulation, position: glm.vec2) -> None:
        if self.next_checkpoint < len(self.checkpoints):
            target = self.checkpoints[self.next_checkpoint]
            if glm.distance(position, target) < config.CHECKPOINT_RADIUS:
                self.last_split = self.elapsed - self.reference_splits[self.next_checkpoint]
                self.next_checkpoint += 1
        elif self._past_line_1(position):
            self.phase = "finished"
            self.result = sim.run_log.add(self.elapsed, self.reference_time, self.driver.wall_hits)

    def _past_line_1(self, position: glm.vec2) -> bool:
        in_lane = LINE_1_Z[0] < position.y < LINE_1_Z[1]
        return in_lane and SIDE * (position.x - self.finish_x) <= 0

    # -- presentation --------------------------------------------------------
    def status(self, sim: Simulation) -> str:
        if self.phase == "ready":
            return "Drive to start the clock."
        if self.phase == "finished" and self.result is not None:
            return (
                f"Finished in {self.result.time:.2f} s "
                f"({self.result.delta:+.2f} s vs line follower). R to go again."
            )
        if self.next_checkpoint < len(self.checkpoints):
            return f"Go to checkpoint {self.next_checkpoint + 1} of {len(self.checkpoints)}."
        return "All checkpoints passed: cross Line 1!"

    def panel_rows(self, sim: Simulation) -> list[tuple[str, str]]:
        # Rounded to 0.1 s so the sidebar is redrawn ten times a second, not every frame.
        rows = [
            ("Time", f"{math.floor(self.elapsed * 10) / 10:.1f} s"),
            ("Line follower", f"{self.reference_time:.2f} s"),
            ("Checkpoints", f"{self.next_checkpoint} / {len(self.checkpoints)}"),
            ("Wall hits", str(self.driver.wall_hits)),
        ]
        if self.last_split is not None:
            rows.append(("Last split", f"{self.last_split:+.2f} s vs ghost"))
        best = sim.run_log.best
        if best is not None:
            rows.append(("Best", f"{best.time:.2f} s ({best.delta:+.2f})"))
        for i, run in enumerate(sim.run_log.recent(3)):
            rows.append(("Recent" if i == 0 else "", f"{run.time:.2f} s ({run.delta:+.2f})"))
        return rows

    def autopilot(self, sim: Simulation) -> glm.vec2:
        """Steer at the next checkpoint, then past Line 1 (for tests and screenshots)."""
        if self.next_checkpoint < len(self.checkpoints):
            target = self.checkpoints[self.next_checkpoint]
        else:
            target = glm.vec2(SIDE * (LINE_1_X - 1.0), LANE_TOP_Z)
        return target - self.driver.position

    def overlay_lines(self, sim: Simulation) -> list[LineSet]:
        lines: list[LineSet] = []
        remaining = self.checkpoints[self.next_checkpoint :]
        if remaining:
            lines.append((AMBER, ring(remaining[0], config.CHECKPOINT_RADIUS)))
            later = [seg for c in remaining[1:] for seg in ring(c, config.CHECKPOINT_RADIUS * 0.5)]
            lines.append((GREY, later))
        finish_color = GREEN if not remaining else GREY
        x = SIDE * LINE_1_X
        lines.append(
            (finish_color, [(glm.vec3(x, 0.06, LINE_1_Z[0]), glm.vec3(x, 0.06, LINE_1_Z[1]))])
        )
        return lines


def ring(centre: glm.vec2, radius: float, segments: int = 32) -> list[tuple[glm.vec3, glm.vec3]]:
    points = [
        glm.vec3(
            centre.x + radius * math.cos(2 * math.pi * i / segments),
            0.06,
            centre.y + radius * math.sin(2 * math.pi * i / segments),
        )
        for i in range(segments + 1)
    ]
    return list(zip(points[:-1], points[1:], strict=True))
