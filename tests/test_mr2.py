import math

import numpy as np
import pytest
from pyglm import glm

from robocon import config
from robocon.mr2 import Mr2Run
from robocon.path import LINE_2_Z, MR2_GUIDELINE, TUSSOCK_Z, mr2_route
from robocon.terrain import Terrain


@pytest.fixture(scope="module")
def run() -> Mr2Run:
    return Mr2Run(side=-1)


def test_route_starts_in_gobi_urtuu_and_ends_in_the_uukhai_zone() -> None:
    route = mr2_route(-1)
    assert tuple(route.points[0]) == pytest.approx((-1.22, 2.45))
    assert tuple(route.points[-1]) == pytest.approx((-0.56, -4.25))
    assert len(route.points) == len(MR2_GUIDELINE)


def test_milestones_come_in_rulebook_order(run: Mr2Run) -> None:
    order = [run.line_2, run.dune_start, run.dune_end, run.line_3, run.tussock]
    order += [run.urtuu_distance, run.summit, run.route.length]
    assert order == sorted(order)


def test_line_2_is_crossed_at_its_measured_z(run: Mr2Run) -> None:
    assert run.route.point(run.line_2).y == pytest.approx(LINE_2_Z, abs=1e-6)


def test_line_3_crossing_lies_on_the_45_degree_line(run: Mr2Run) -> None:
    p = run.route.point(run.line_3)
    assert p.y == pytest.approx(abs(p.x) - 4.31, abs=1e-6)


def test_tussock_is_crossed_on_the_way_down_to_mountain_urtuu(run: Mr2Run) -> None:
    p = run.route.point(run.tussock)
    assert p.y == pytest.approx(TUSSOCK_Z[1])


def test_mr2_steps_up_onto_the_sand_dune(run: Mr2Run) -> None:
    middle = (run.dune_start + run.dune_end) / 2
    t = middle / run.walk_speed
    assert run.position(t).y == pytest.approx(0.1, abs=0.01)
    assert run.position(0).y == 0


def test_mr2_waits_at_mountain_urtuu_then_climbs(run: Mr2Run) -> None:
    waiting = run.walk_time + run.wait / 2
    assert run.distance_at(waiting) == pytest.approx(run.urtuu_distance)
    assert "waits at Mountain urtuu" in run.stage(waiting)
    climbing = run.walk_time + run.wait + 1
    assert run.distance_at(climbing) == pytest.approx(run.urtuu_distance + config.MR2_CLIMB_SPEED)
    assert "climbs" in run.stage(climbing)


def test_mr2_ends_on_top_of_the_mountain(run: Mr2Run) -> None:
    end = run.position(run.total_time + 5)
    assert end.y == pytest.approx(0.4, abs=1e-3)
    assert run.finished(run.total_time)
    assert run.stage(run.total_time).startswith("UUKHAI")


def test_height_never_jumps(run: Mr2Run) -> None:
    heights = [run.position(t).y for t in np.arange(0, run.total_time, 0.05)]
    assert max(abs(b - a) for a, b in zip(heights[:-1], heights[1:], strict=True)) < 0.11


def test_spider_faces_its_direction_of_travel(run: Mr2Run) -> None:
    # The model faces -z at yaw 0; turned by model_yaw it must face the way it walks.
    for t in (1.0, 7.0, 10.0, 20.0):
        yaw = run.model_yaw(t)
        facing = glm.vec2(-math.sin(yaw), -math.cos(yaw))
        heading = math.radians(run.heading(t))
        assert glm.dot(facing, glm.vec2(math.cos(heading), math.sin(heading))) > 0.99


def test_terrain_heights_match_the_mountain_and_dune() -> None:
    terrain = Terrain.arena()
    assert terrain.height(0.0, -4.2) == pytest.approx(0.4, abs=1e-3)  # mountain top
    assert terrain.height(-1.9, -4.25) == pytest.approx(0.2, abs=0.01)  # halfway up the ramp
    assert terrain.height(-3.0, -4.25) == 0  # Mountain urtuu, on the floor
    assert terrain.height(-5.0, 0.0) == 0  # forest lane


def test_flat_terrain_without_raised_parts() -> None:
    assert Terrain(np.zeros((0, 3, 3))).height(1.0, 2.0) == 0.0
