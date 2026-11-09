import math

import pytest
from pyglm import glm

from robocon.path import (
    BRIDGE,
    FOREST_GUIDELINE,
    HANDOFF_X,
    LANE_TOP_Z,
    LINE_1_X,
    LINE_1_Z,
    START_X,
    START_Z,
    LineFollower,
    MotionLimits,
    Route,
    approach_angle,
    mr1_route,
    mr2_route,
)


def xz(v: glm.vec2) -> tuple[float, float]:
    return (v.x, v.y)


def test_route_point_interpolates_by_distance() -> None:
    route = Route([(0, 0), (3, 0), (3, 4)])
    assert route.length == pytest.approx(7)
    assert xz(route.point(1.5)) == pytest.approx((1.5, 0))
    assert xz(route.point(5)) == pytest.approx((3, 2))


def test_route_point_clamps_to_the_ends() -> None:
    route = Route([(0, 0), (1, 0)])
    assert xz(route.point(-5)) == pytest.approx((0, 0))
    assert xz(route.point(99)) == pytest.approx((1, 0))


def test_route_needs_two_points() -> None:
    with pytest.raises(ValueError):
        Route([(0, 0)])


def test_heading_follows_the_segment() -> None:
    route = Route([(0, 0), (0, 1), (-1, 1)])
    assert route.heading(0.5) == pytest.approx(90)  # +z
    assert route.heading(1.5) == pytest.approx(180)  # -x


@pytest.mark.parametrize("side", [-1, 1])
def test_mr1_route_starts_in_the_start_zone_and_ends_at_the_handoff(side: int) -> None:
    route = mr1_route(side)
    assert xz(route.point(0)) == pytest.approx((side * START_X, START_Z))
    assert xz(route.point(route.length)) == pytest.approx((side * HANDOFF_X, LANE_TOP_Z))


def test_mr1_route_is_the_white_guideline() -> None:
    route = mr1_route(side=1)
    assert route.points.ravel().tolist() == pytest.approx([c for p in FOREST_GUIDELINE for c in p])


def test_guideline_turns_only_at_right_angles() -> None:
    # The forest zig-zag is taped with square corners.
    assert mr1_route(-1).turn_angles() == pytest.approx([90.0] * 9, abs=1.0)


def test_mr1_crosses_the_river_over_the_bridge() -> None:
    route = mr1_route(side=-1)
    bridge = glm.vec2(-BRIDGE[0], BRIDGE[1])
    closest = min(glm.distance(route.point(route.length * i / 400), bridge) for i in range(401))
    assert closest < 0.05


def test_mr1_crosses_line_1_before_the_handoff() -> None:
    route = mr1_route(side=-1)
    end = route.point(route.length)
    assert end.x > -LINE_1_X and LINE_1_Z[0] < end.y < LINE_1_Z[1]


def test_red_and_blue_routes_are_mirror_images() -> None:
    red, blue = mr1_route(-1), mr1_route(1)
    assert red.length == pytest.approx(blue.length)
    for s in (0.0, 3.3, 7.7, red.length):
        r, b = red.point(s), blue.point(s)
        assert (r.x, r.y) == pytest.approx((-b.x, b.y))


def test_mr2_route_walks_towards_the_start_zones() -> None:
    route = mr2_route(-1)
    assert route.heading(0) == pytest.approx(-90)


@pytest.mark.parametrize(
    ("current", "target", "expected_sign"),
    [(170, -170, 1), (-170, 170, -1), (0, 90, 1)],
)
def test_approach_angle_turns_the_short_way(current, target, expected_sign) -> None:
    step = approach_angle(current, target, rate=5, dt=0.01) - current
    assert math.copysign(1, step) == expected_sign


def test_approach_angle_is_frame_rate_independent() -> None:
    coarse = approach_angle(0, 90, rate=3, dt=0.5)
    fine = 0.0
    for _ in range(50):
        fine = approach_angle(fine, 90, rate=3, dt=0.01)
    assert fine == pytest.approx(coarse)


LIMITS = MotionLimits(max_speed=2.0, accel=2.0)


def test_line_follower_on_a_long_straight_is_trapezoidal() -> None:
    follower = LineFollower(Route([(0, 0), (10, 0)]), LIMITS)
    # 1 s to reach 2 m/s (1 m), 4 s cruising (8 m), 1 s braking (1 m)
    assert follower.total_time == pytest.approx(6.0)
    assert follower.distance_at(1.0) == pytest.approx(1.0)
    assert follower.distance_at(2.5) == pytest.approx(4.0)
    assert follower.distance_at(99) == pytest.approx(10.0)


def test_line_follower_on_a_short_run_never_reaches_top_speed() -> None:
    follower = LineFollower(Route([(0, 0), (1, 0)]), LIMITS)
    assert follower.total_time == pytest.approx(2 * math.sqrt(1 / 2.0))


def test_line_follower_stops_at_every_corner() -> None:
    follower = LineFollower(mr1_route(-1), LIMITS)
    assert follower.stop_count == 10
    corner_time = follower.time_at(float(follower.route.vertex_distances[1]))
    before = follower.distance_at(corner_time - 0.01)
    after = follower.distance_at(corner_time + 0.01)
    assert after - before < 0.001  # nearly stationary at the corner


def test_line_follower_time_and_distance_are_inverses() -> None:
    follower = LineFollower(mr1_route(-1), LIMITS)
    for s in (0.3, 2.0, 7.7, 12.1, follower.route.length - 0.2):
        assert follower.distance_at(follower.time_at(s)) == pytest.approx(s, abs=1e-6)


def test_line_follower_distance_never_goes_backwards() -> None:
    follower = LineFollower(mr1_route(-1), LIMITS)
    samples = [follower.distance_at(i * 0.05) for i in range(int(follower.total_time / 0.05) + 2)]
    assert all(b >= a - 1e-9 for a, b in zip(samples[:-1], samples[1:], strict=True))
