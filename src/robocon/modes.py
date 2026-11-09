"""Demo modes, one per number key.

Each mode gets a freshly reset scene and camera in ``enter`` and then
animates from ``t`` = seconds since it was entered, so pressing a key again
always replays the mode from the start.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, ClassVar

from pyglm import glm

from robocon import config
from robocon.mr2 import Mr2Run
from robocon.path import approach_angle, mr1_route
from robocon.scene import Entity, LineSet

if TYPE_CHECKING:
    from robocon.simulation import Simulation


class Mode:
    key: ClassVar[int]
    name: ClassVar[str]
    description: ClassVar[str]  # one line for the on-screen help
    hints: ClassVar[tuple[tuple[str, str], ...]] = ()  # extra (key, action) rows for this mode
    panel_heading: ClassVar[str] = "INFO"
    free_camera: ClassVar[bool] = True  # False when the mode drives the camera itself

    def enter(self, sim: Simulation) -> None:
        """Set up the scene; it has already been reset to its default layout."""

    def update(self, sim: Simulation, t: float, dt: float) -> None:
        """Advance the animation. ``t`` is the time since the mode was entered."""

    def status(self, sim: Simulation) -> str | None:
        """Short live status for the on-screen help, if the mode has phases."""
        return None

    def panel_rows(self, sim: Simulation) -> list[tuple[str, str]]:
        """Extra (label, value) rows for the sidebar, e.g. times in the time trial."""
        return []

    def overlay_lines(self, sim: Simulation) -> list[LineSet]:
        """Lines on the arena that are part of the mode (always drawn), e.g. checkpoints."""
        return []

    def autopilot(self, sim: Simulation) -> glm.vec2 | None:
        """Driving input a simple bot would give, for tests and screenshots (None: no driving)."""
        return None


class ArenaShowcase(Mode):
    key = 1
    name = "Arena"
    description = "The ABU Robocon 2019 arena, modelled from the rulebook drawings."

    def enter(self, sim: Simulation) -> None:
        sim.scene.show_only(sim.scene.arena)
        sim.camera.set_pose(*config.ARENA_SHOWCASE_CAMERA)

    def update(self, sim: Simulation, t: float, dt: float) -> None:
        sim.scene.arena.yaw = config.SHOWCASE_SPIN_RATE * t


class RobotShowcase(Mode):
    key = 2
    name = "MR1 close-up"
    description = "MR1, the omni-wheel messenger robot, at 10x scale."

    def enter(self, sim: Simulation) -> None:
        robot = sim.scene.robot_blue
        sim.scene.show_only(robot)
        robot.position = glm.vec3(0.0, 0.0, 0.0)
        robot.scale = config.SHOWCASE_ROBOT_SCALE

    def update(self, sim: Simulation, t: float, dt: float) -> None:
        sim.scene.robot_blue.yaw = config.SHOWCASE_SPIN_RATE * t


class SpiderShowcase(Mode):
    key = 3
    name = "MR2 close-up"
    description = "MR2, the legged messenger robot, at 10x scale."

    def enter(self, sim: Simulation) -> None:
        spider = sim.scene.spider_red
        sim.scene.show_only(spider)
        spider.position = glm.vec3(0.0, 0.0, 0.0)
        spider.scale = config.SHOWCASE_ROBOT_SCALE

    def update(self, sim: Simulation, t: float, dt: float) -> None:
        sim.scene.spider_red.yaw = config.SHOWCASE_SPIN_RATE * t


def sway(t: float) -> float:
    """Idle animation for a waiting MR2: turn back and forth, in radians."""
    angle = config.SPIDER_SWAY_ANGLE * math.sin(2 * math.pi * t / config.SPIDER_SWAY_PERIOD)
    return math.radians(angle)


def place_on_floor(entity: Entity, point: glm.vec2) -> None:
    entity.position.x, entity.position.z = point.x, point.y


def place_mr2(entity: Entity, run: Mr2Run, t: float) -> None:
    """Put MR2 where its run is at time ``t`` after the hand-off, facing where it walks."""
    entity.position = run.position(t)
    entity.yaw = run.model_yaw(t)
    if run.finished(t):
        entity.yaw += 0.5 * sway(t)  # a little victory wiggle in the Uukhai zone


class RobotView(Mode):
    """Ride along as red MR1 through the forest, then as MR2 after the hand-off."""

    key = 5
    name = "Robot's-eye view"
    description = "Ride along as MR1 through the forest, then as MR2 up the mountain."
    free_camera = False

    def __init__(self) -> None:
        self.mr1 = mr1_route(side=-1)
        self.mr2 = Mr2Run(side=-1)

    @property
    def handoff_time(self) -> float:
        return self.mr1.length / config.RIDE_SPEED

    def status(self, sim: Simulation) -> str:
        if sim.mode_time < self.handoff_time:
            return "Riding MR1"
        return f"Riding MR2. {self.mr2.stage(sim.mode_time - self.handoff_time)}"

    def enter(self, sim: Simulation) -> None:
        sim.scene.robot_red.visible = False  # the camera is MR1
        start = self.mr1.point(0.0)
        yaw = self.mr1.heading(0.0, config.RIDE_LOOKAHEAD)
        sim.camera.set_pose(glm.vec3(start.x, config.MR1_EYE_HEIGHT, start.y), yaw, 0.0)

    def update(self, sim: Simulation, t: float, dt: float) -> None:
        scene, camera = sim.scene, sim.camera
        scene.spider_blue.yaw = sway(t)
        if t < self.handoff_time:
            s = config.RIDE_SPEED * t
            point = self.mr1.point(s)
            camera.position = glm.vec3(point.x, config.MR1_EYE_HEIGHT, point.y)
            target = self.mr1.heading(s, config.RIDE_LOOKAHEAD) if s < self.mr1.length else None
            scene.spider_red.yaw = sway(t)
        else:
            # MR1 parks at the hand-off point and the camera becomes MR2, which
            # steps up onto the sand dune and climbs the mountain.
            run_t = t - self.handoff_time
            scene.robot_red.visible = True
            place_on_floor(scene.robot_red, self.mr1.point(self.mr1.length))
            scene.spider_red.visible = False
            camera.position = self.mr2.position(run_t) + glm.vec3(0.0, config.MR2_EYE_HEIGHT, 0.0)
            target = None if self.mr2.finished(run_t) else self.mr2.heading(run_t)
        if target is not None:
            camera.yaw = approach_angle(camera.yaw, target, config.RIDE_TURN_RATE, dt)
