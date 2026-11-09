"""Wall collision for the forest lane.

The five walls around a forest lane are written in a local frame of the blue
half of the field (``x0 = 6.65 - x``, ``y0 = z + 5``), converted to world
coordinates and mirrored, so both halves collide. A robot is a circle with
the chassis radius; it collides when it comes closer than that to a wall
segment, and a blocked move slides along the wall instead of stopping dead.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pyglm import glm

# The walls as (x0, y0) pairs in a local frame of the blue half.
_LOCAL_WALLS = [
    ((0.0, 0.0), (0.0, 10.0)),  # outer fence
    ((2.45, 0.0), (2.45, 8.0)),  # inner wall of the forest lane
    ((0.0, 10.0), (6.65, 10.0)),  # far fence
    ((2.45, 8.0), (6.65, 8.0)),  # inner wall of the top lane
    ((6.65, 8.0), (6.65, 10.0)),  # centre divider at the top
]


def _to_world(x0: float, y0: float) -> glm.vec2:
    return glm.vec2(6.65 - x0, y0 - 5.0)


@dataclass(frozen=True)
class Wall:
    start: glm.vec2  # (x, z)
    end: glm.vec2

    def distance_to(self, point: glm.vec2) -> float:
        along = self.end - self.start
        length_sq = glm.dot(along, along)
        if length_sq == 0:
            return glm.distance(point, self.start)
        f = glm.clamp(glm.dot(point - self.start, along) / length_sq, 0.0, 1.0)
        return glm.distance(point, self.start + along * f)

    def mirrored(self) -> Wall:
        flip = glm.vec2(-1.0, 1.0)
        return Wall(self.start * flip, self.end * flip)


def forest_lane_walls() -> list[Wall]:
    """The forest-lane walls of both halves (the shared centre divider only once)."""
    blue = [Wall(_to_world(*a), _to_world(*b)) for a, b in _LOCAL_WALLS]
    red = [w.mirrored() for w in blue if not (w.start.x == 0 and w.end.x == 0)]
    return blue + red


class Collider:
    def __init__(self, walls: Iterable[Wall], radius: float) -> None:
        self.walls = list(walls)
        self.radius = radius

    def hits(self, position: glm.vec2) -> bool:
        return any(wall.distance_to(position) < self.radius for wall in self.walls)

    def clearance(self, position: glm.vec2) -> float:
        """Distance from the robot's edge to the nearest wall (infinite with no walls)."""
        nearest = min((wall.distance_to(position) for wall in self.walls), default=float("inf"))
        return nearest - self.radius

    def move(self, position: glm.vec2, step: glm.vec2) -> glm.vec2:
        """Apply ``step`` if it is clear; otherwise slide along whichever axis is free,
        or as a last resort move up to the wall without touching it."""
        for candidate in (step, glm.vec2(step.x, 0.0), glm.vec2(0.0, step.y)):
            moved = position + candidate
            if candidate != glm.vec2(0.0) and not self.hits(moved):
                return moved
        clear, blocked = 0.0, 1.0  # bisect the largest fraction of the step that fits
        for _ in range(12):
            middle = (clear + blocked) / 2
            if self.hits(position + step * middle):
                blocked = middle
            else:
                clear = middle
        return position + step * clear
