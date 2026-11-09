"""Routes the robots follow, and how fast a line-following robot covers them.

Coordinates are (x, z) on the floor. Red (team A) uses ``side=-1`` and
blue (team B) the mirror image with ``side=+1``.

Rule 1.4.2 of the rulebook: "MR1 has to travel through the forest
according to the route indicated by white guidelines." The guideline below
was measured from the floor texture (mapped onto the floor as
``x = 13.40 u - 6.70``, ``z = 5.05 - 10.10 v``). It zig-zags at right angles
around the three forest poles, crosses the river over the bridge (rule
1.4.4), and runs along the top lane past Line 1 to Gobi urtuu, where MR1
hands the Gerege to MR2.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from pyglm import glm

# The blue-side (+x) guideline; the red side is its mirror image.
FOREST_GUIDELINE = [
    (6.15, -4.55),  # Khangai urtuu (MR1 start)
    (6.15, -3.75),
    (4.73, -3.75),  # zig-zag around the first forest pole
    (4.73, -2.25),
    (6.14, -2.25),  # ... the second
    (6.14, -0.77),
    (4.73, -0.77),  # ... the third
    (4.73, 0.75),
    (5.43, 0.75),
    (5.43, 3.99),  # straight over the bridge and up the lane
    (1.22, 3.99),  # along the top lane, across Line 1, to Gobi urtuu
]
START_X, START_Z = FOREST_GUIDELINE[0]
LANE_TOP_Z = FOREST_GUIDELINE[-1][1]
HANDOFF_X = FOREST_GUIDELINE[-1][0]  # MR2's guideline runs down this x
BRIDGE = (5.43, 2.0)  # middle of the bridge over the river
LINE_1_X = 2.18  # Line 1 crosses the top lane (z 3..5) here
LINE_1_Z = (3.0, 5.0)

# MR2's guideline (blue side, +x), also measured from the floor texture: from the cross in
# Gobi urtuu down across Line 2, diagonally over the sand-dune timber and across Line 3,
# down through the tussock into Mountain urtuu, then up the mountain to the Uukhai zone.
MR2_GUIDELINE = [
    (1.22, 2.45),  # Gobi urtuu (MR2 start)
    (1.22, -0.78),  # across Line 2 (z = -0.48)
    (2.23, -1.79),  # over the sand dune
    (3.42, -1.79),  # across Line 3 (the 45-degree red line)
    (3.42, -4.25),  # through the tussock into Mountain urtuu
    (0.56, -4.25),  # up the mountain to the middle of the Uukhai zone
]
MOUNTAIN_URTUU_INDEX = 4  # MR2 waits at this corner of its guideline
LINE_2_Z = -0.48
LINE_3_OFFSET = 4.31  # Line 3 is the 45-degree line z = |x| - 4.31
TUSSOCK_Z = (-3.42, -2.55)
SUMMIT_X = 1.11  # the mountain top (and Uukhai zone) spans |x| <= 1.11


class Route:
    def __init__(self, points: Sequence[tuple[float, float]]) -> None:
        self.points = np.asarray(points, dtype=np.float64)
        if len(self.points) < 2:
            raise ValueError("a route needs at least two points")
        segment_lengths = np.linalg.norm(np.diff(self.points, axis=0), axis=1)
        self.vertex_distances = np.concatenate([[0.0], np.cumsum(segment_lengths)])

    @property
    def length(self) -> float:
        return float(self.vertex_distances[-1])

    def point(self, s: float) -> glm.vec2:
        """Position after travelling ``s`` along the route (clamped to the ends)."""
        s = min(max(s, 0.0), self.length)
        i = self._segment(s)
        start, end = self.points[i], self.points[i + 1]
        span = self.vertex_distances[i + 1] - self.vertex_distances[i]
        f = (s - self.vertex_distances[i]) / span if span > 0 else 0.0
        x, z = start + (end - start) * f
        return glm.vec2(x, z)

    def heading(self, s: float, lookahead: float = 0.0) -> float:
        """Camera yaw in degrees (0 = +x, 90 = +z) facing along the route.

        With a lookahead the yaw aims at a point further on, which softens the corners.
        """
        if lookahead > 0:
            here = self.point(min(s, self.length - 1e-6))
            ahead = self.point(min(s + lookahead, self.length))
            direction = ahead - here
        else:
            i = self._segment(min(max(s, 0.0), self.length))
            dx, dz = self.points[i + 1] - self.points[i]
            direction = glm.vec2(dx, dz)
        return math.degrees(math.atan2(direction.y, direction.x))

    def project(self, point: glm.vec2 | tuple[float, float]) -> float:
        """Distance along the route of the route point closest to ``point``."""
        p = np.array([point[0], point[1]], dtype=np.float64)
        best_distance, best_s = math.inf, 0.0
        for i in range(len(self.points) - 1):
            a, b = self.points[i], self.points[i + 1]
            ab = b - a
            length_sq = float(np.dot(ab, ab))
            f = 0.0 if length_sq == 0 else min(max(float(np.dot(p - a, ab)) / length_sq, 0.0), 1.0)
            gap = float(np.linalg.norm(p - (a + ab * f)))
            if gap < best_distance:
                best_distance = gap
                best_s = float(self.vertex_distances[i]) + f * math.sqrt(length_sq)
        return best_s

    def turn_angles(self) -> list[float]:
        """Turn in degrees at each inner vertex (0 = straight on)."""
        d = np.diff(self.points, axis=0)
        angles = []
        for a, b in zip(d[:-1], d[1:], strict=True):
            cos = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            angles.append(math.degrees(math.acos(max(-1.0, min(1.0, float(cos))))))
        return angles

    def _segment(self, s: float) -> int:
        i = int(np.searchsorted(self.vertex_distances, s, side="right")) - 1
        return min(max(i, 0), len(self.points) - 2)


def mr1_route(side: int) -> Route:
    """MR1's route along the forest guideline, from Khangai urtuu to Gobi urtuu."""
    return Route([(side * x, z) for x, z in FOREST_GUIDELINE])


def mr2_route(side: int) -> Route:
    """MR2's guideline from Gobi urtuu to the Uukhai zone."""
    return Route([(side * x, z) for x, z in MR2_GUIDELINE])


@dataclass(frozen=True)
class MotionLimits:
    max_speed: float  # units per second
    accel: float  # units per second squared (also used for braking)


class LineFollower:
    """Time profile of a robot that follows a route, braking to a stop at every corner.

    Each straight run is driven as fast as the limits allow: accelerate, cruise,
    brake (or accelerate then brake if the run is too short to reach top speed).
    This is the reference ("ideal") run for the time trial.
    """

    def __init__(self, route: Route, limits: MotionLimits, corner_angle: float = 20.0) -> None:
        self.route = route
        self.limits = limits
        breaks = [0.0]
        for i, angle in enumerate(route.turn_angles(), start=1):
            if angle > corner_angle:
                breaks.append(float(route.vertex_distances[i]))
        breaks.append(route.length)
        self._runs = []  # (start distance, length, start time, duration)
        t = 0.0
        for start, end in zip(breaks[:-1], breaks[1:], strict=True):
            duration = self._run_duration(end - start)
            self._runs.append((start, end - start, t, duration))
            t += duration
        self.total_time = t

    @property
    def stop_count(self) -> int:
        return len(self._runs)

    def distance_at(self, t: float) -> float:
        """Distance along the route ``t`` seconds after starting."""
        if t <= 0:
            return 0.0
        for start, length, t0, duration in self._runs:
            if t < t0 + duration:
                return start + self._run_distance(length, t - t0, duration)
        return self.route.length

    def time_at(self, s: float) -> float:
        """Seconds after starting at which the robot reaches distance ``s``."""
        if s <= 0:
            return 0.0
        for start, length, t0, duration in self._runs:
            if s <= start + length:
                return t0 + self._run_time(length, s - start, duration)
        return self.total_time

    # A run of length L: v = top speed, a = acceleration.
    def _run_duration(self, length: float) -> float:
        v, a = self.limits.max_speed, self.limits.accel
        if length >= v * v / a:  # reaches top speed
            return length / v + v / a
        return 2 * math.sqrt(length / a)

    def _run_distance(self, length: float, t: float, duration: float) -> float:
        v, a = self.limits.max_speed, self.limits.accel
        accel_time = min(v / a, duration / 2)
        if t <= accel_time:
            return 0.5 * a * t * t
        if t >= duration - accel_time:
            remaining = duration - t
            return length - 0.5 * a * remaining * remaining
        return 0.5 * a * accel_time * accel_time + v * (t - accel_time)

    def _run_time(self, length: float, d: float, duration: float) -> float:
        v, a = self.limits.max_speed, self.limits.accel
        accel_time = min(v / a, duration / 2)
        accel_distance = 0.5 * a * accel_time * accel_time
        if d <= accel_distance:
            return math.sqrt(2 * d / a)
        if d >= length - accel_distance:
            return duration - math.sqrt(max(0.0, 2 * (length - d) / a))
        return accel_time + (d - accel_distance) / v


def approach_angle(current: float, target: float, rate: float, dt: float) -> float:
    """Turn ``current`` towards ``target`` (degrees) by the shortest way, frame-rate independent."""
    difference = (target - current + 180.0) % 360.0 - 180.0
    return current + difference * (1.0 - math.exp(-rate * dt))
