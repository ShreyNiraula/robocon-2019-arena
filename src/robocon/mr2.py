"""MR2's run: from Gobi urtuu across the Gobi area and up the mountain.

Following rules 1.6 and 1.8 of the rulebook, MR2 (the four-legged
robot) takes the Gerege from MR1 at Gobi urtuu, crosses Line 2, goes over the
sand dune, crosses Line 3, goes through the tussock to Mountain urtuu, waits
there until MR1 has scored with the Shagai, then climbs the mountain to the
Uukhai zone and raises the Gerege ("UUKHAI!").

The run is a pure function of time since the hand-off, so the match and the
robot's-eye view can both ask where MR2 is at any moment. Height comes from
the arena's sand dune and mountain, so MR2 steps up onto the timber and
climbs the slope.
"""

from __future__ import annotations

import math
from functools import cache

from pyglm import glm

from robocon import config
from robocon.path import (
    LINE_2_Z,
    LINE_3_OFFSET,
    MOUNTAIN_URTUU_INDEX,
    MR2_GUIDELINE,
    SUMMIT_X,
    TUSSOCK_Z,
    mr2_route,
)
from robocon.terrain import Terrain

LOOKAHEAD = 0.3  # face a point this far ahead, so turns at corners look smooth

_STAGES = {  # stage: (status sentence, short label)
    "start": ("MR2 leaves Gobi urtuu with the Gerege.", "Gobi urtuu"),
    "line_2": ("MR2 crossed Line 2.", "Line 2"),
    "dune": ("MR2 crosses the sand dune.", "Sand dune"),
    "after_dune": ("MR2 is over the sand dune, heading for Line 3.", "After sand dune"),
    "line_3": ("MR2 crossed Line 3.", "Line 3"),
    "tussock": ("MR2 crosses the tussock.", "Tussock"),
    "waiting": ("MR2 waits at Mountain urtuu while MR1 throws the Shagai.", "Mountain urtuu"),
    "climbing": ("MR2 climbs the mountain.", "Climbing"),
    "uukhai": ("UUKHAI! MR2 raises the Gerege in the Uukhai zone.", "UUKHAI"),
}


@cache
def arena_terrain() -> Terrain:
    return Terrain.arena()


class Mr2Run:
    def __init__(self, side: int, terrain: Terrain | None = None) -> None:
        self.side = side
        self.route = mr2_route(side)
        self.terrain = terrain if terrain is not None else arena_terrain()
        self.walk_speed = config.MR2_WALK_SPEED
        self.climb_speed = config.MR2_CLIMB_SPEED
        self.wait = config.MR2_URTUU_WAIT

        self.urtuu_distance = float(self.route.vertex_distances[MOUNTAIN_URTUU_INDEX])
        self.walk_time = self.urtuu_distance / self.walk_speed
        climb_length = self.route.length - self.urtuu_distance
        self.total_time = self.walk_time + self.wait + climb_length / self.climb_speed

        # Milestones along the guideline, as distances travelled.
        gobi_x = side * MR2_GUIDELINE[0][0]
        side_run_z = MR2_GUIDELINE[3][1]  # the sideways run that crosses Line 3
        line_3_x = side_run_z + LINE_3_OFFSET  # |x| where z = |x| - 4.31 meets that run
        self.line_2 = self.route.project((gobi_x, LINE_2_Z))
        self.line_3 = self.route.project((side * line_3_x, side_run_z))
        tussock_x = side * MR2_GUIDELINE[3][0]
        self.tussock = self.route.project((tussock_x, TUSSOCK_Z[1]))
        self.summit = self.route.project((side * SUMMIT_X, MR2_GUIDELINE[-1][1]))
        self.dune_start, self.dune_end = self._raised_span(0.0, self.line_3)

    def distance_at(self, t: float) -> float:
        """Distance along the guideline ``t`` seconds after the hand-off."""
        if t <= 0:
            return 0.0
        if t <= self.walk_time:
            return self.walk_speed * t
        if t <= self.walk_time + self.wait:
            return self.urtuu_distance
        climbed = self.climb_speed * (t - self.walk_time - self.wait)
        return min(self.urtuu_distance + climbed, self.route.length)

    def position(self, t: float) -> glm.vec3:
        point = self.route.point(self.distance_at(t))
        return glm.vec3(point.x, self.terrain.height(point.x, point.y), point.y)

    def heading(self, t: float) -> float:
        """Direction of travel as a camera yaw in degrees (0 = +x, 90 = +z)."""
        return self.route.heading(self.distance_at(t), LOOKAHEAD)

    def model_yaw(self, t: float) -> float:
        """Entity yaw (radians) that turns the spider model to face its direction of travel.

        The model faces -z at yaw 0; yaw rotates it about +y.
        """
        angle = math.radians(self.heading(t))
        dx, dz = math.cos(angle), math.sin(angle)
        return math.atan2(-dx, -dz)

    def finished(self, t: float) -> bool:
        return t >= self.total_time

    def stage(self, t: float) -> str:
        """What MR2 is doing, as a sentence for the status line."""
        return _STAGES[self._stage(t)][0]

    def label(self, t: float) -> str:
        """What MR2 is doing, in a word or two for a sidebar row."""
        return _STAGES[self._stage(t)][1]

    def _stage(self, t: float) -> str:
        s = self.distance_at(t)
        if self.finished(t):
            return "uukhai"
        if self.walk_time < t <= self.walk_time + self.wait:
            return "waiting"
        if s > self.urtuu_distance:
            return "climbing"
        if s >= self.tussock:
            return "tussock"
        if s >= self.line_3:
            return "line_3"
        if s > self.dune_end:
            return "after_dune"
        if s >= self.dune_start:
            return "dune"
        if s >= self.line_2:
            return "line_2"
        return "start"

    def _raised_span(self, start: float, end: float, step: float = 0.02) -> tuple[float, float]:
        """First and last distance in [start, end] where the guideline is above the floor."""
        raised = []
        s = start
        while s <= end:
            p = self.route.point(s)
            if self.terrain.height(p.x, p.y) > 1e-3:
                raised.append(s)
            s += step
        return (raised[0], raised[-1]) if raised else (end, end)
