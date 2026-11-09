"""Everything that changes over time, independent of the window and OpenGL."""

from __future__ import annotations

import math
from collections.abc import Sequence

from pyglm import glm

from robocon import config
from robocon.camera import Camera
from robocon.collision import forest_lane_walls
from robocon.modes import (
    ArenaShowcase,
    Mode,
    RobotShowcase,
    RobotView,
    SpiderShowcase,
)
from robocon.path import mr1_route, mr2_route
from robocon.runlog import RunLog
from robocon.scene import LineSet, Scene
from robocon.trial import TimeTrial


def default_modes() -> list[Mode]:
    return [
        ArenaShowcase(),
        RobotShowcase(),
        SpiderShowcase(),
        RobotView(),
        TimeTrial(),
    ]


class Simulation:
    def __init__(self, modes: Sequence[Mode] | None = None, run_log: RunLog | None = None) -> None:
        self.modes = {mode.key: mode for mode in (modes or default_modes())}
        self.run_log = run_log or RunLog()  # in memory unless the app passes a file
        self.scene = Scene.default()
        self.camera = Camera()
        self.clock = 0.0  # total running time, drives the light
        self.mode_time = 0.0  # time since the current mode was entered
        self.drive = glm.vec2(0.0)  # manual driving input (x, z), set by the window each frame
        self.show_overlay = False  # draw walls and routes
        self.paused = False
        self._overlay: list[LineSet] | None = None
        self.mode = self.modes[min(self.modes)]
        self.set_mode(self.mode.key)

    def set_mode(self, key: int) -> None:
        """Switch to a mode, resetting the scene and camera so it always starts the same way."""
        self.mode = self.modes[key]
        self.mode_time = 0.0
        self.scene = Scene.default()
        self.camera = Camera()
        self.camera.set_pose(*config.OVERVIEW_CAMERA)
        self.mode.enter(self)

    def restart(self) -> None:
        self.set_mode(self.mode.key)

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def update(self, dt: float) -> None:
        if self.paused:
            return
        dt = min(max(dt, 0.0), config.MAX_FRAME_TIME)
        self.clock += dt
        self.mode_time += dt
        self.mode.update(self, self.mode_time, dt)

    def light_position(self) -> glm.vec3:
        """The light circles above the arena."""
        angle = config.LIGHT_ORBIT_RATE * self.clock
        return glm.vec3(
            config.LIGHT_ORBIT_RADIUS * math.cos(angle),
            config.LIGHT_HEIGHT,
            config.LIGHT_ORBIT_RADIUS * math.sin(angle),
        )

    def overlay_lines(self) -> list[LineSet]:
        """Lines drawn on the arena: the mode's own (e.g. checkpoints), plus walls (red)
        and routes (yellow MR1, cyan MR2) when the debug overlay is on."""
        lines = self.mode.overlay_lines(self)
        if self.show_overlay:
            if self._overlay is None:
                self._overlay = _build_overlay()
            lines = self._overlay + lines
        return lines


def _build_overlay() -> list[LineSet]:
    lift = 0.05  # just above the floor

    def floor_segments(points) -> list[tuple[glm.vec3, glm.vec3]]:
        pts = [glm.vec3(float(x), lift, float(z)) for x, z in points]
        return list(zip(pts[:-1], pts[1:], strict=True))

    walls = [seg for w in forest_lane_walls() for seg in floor_segments([w.start, w.end])]
    mr1 = [seg for side in (-1, 1) for seg in floor_segments(mr1_route(side).points)]
    mr2 = [seg for side in (-1, 1) for seg in floor_segments(mr2_route(side).points)]
    return [((1.0, 0.2, 0.2), walls), ((1.0, 0.9, 0.2), mr1), ((0.2, 0.9, 1.0), mr2)]
