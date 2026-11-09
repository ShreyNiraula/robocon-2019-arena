import pytest
from pyglm import glm

from robocon import config
from robocon.collision import Collider, Wall, forest_lane_walls
from robocon.path import mr1_route


def test_lane_walls_land_where_the_arena_fence_is() -> None:
    walls = forest_lane_walls()
    outer_fence = walls[0]
    assert (outer_fence.start.x, outer_fence.start.y) == pytest.approx((6.65, -5.0))
    assert (outer_fence.end.x, outer_fence.end.y) == pytest.approx((6.65, 5.0))


def test_both_halves_have_walls_and_the_centre_divider_is_not_duplicated() -> None:
    walls = forest_lane_walls()
    assert len(walls) == 9
    assert any(w.start.x < 0 for w in walls) and any(w.start.x > 0 for w in walls)
    centre = [w for w in walls if w.start.x == 0 and w.end.x == 0]
    assert len(centre) == 1


def test_distance_is_measured_to_the_segment_not_the_infinite_line() -> None:
    wall = Wall(glm.vec2(0, 0), glm.vec2(0, 1))
    assert wall.distance_to(glm.vec2(0.5, 0.5)) == pytest.approx(0.5)
    assert wall.distance_to(glm.vec2(0, 3)) == pytest.approx(2)  # past the end


def test_wall_stored_high_to_low_still_collides() -> None:
    # A wall's ends may be stored in either order.
    collider = Collider([Wall(glm.vec2(2, 0), glm.vec2(-2, 0))], radius=0.3)
    assert collider.hits(glm.vec2(0.5, 0.1))


def test_robot_cannot_drive_through_the_inner_lane_wall() -> None:
    collider = Collider(forest_lane_walls(), config.MR1_RADIUS)
    position = glm.vec2(5.4, -2.0)
    for _ in range(200):
        position = collider.move(position, glm.vec2(-0.05, 0.0))
    inner_wall_x = 4.2
    assert position.x == pytest.approx(inner_wall_x + config.MR1_RADIUS, abs=0.06)


def test_blocked_move_slides_along_the_wall() -> None:
    collider = Collider([Wall(glm.vec2(0, -10), glm.vec2(0, 10))], radius=0.3)
    moved = collider.move(glm.vec2(0.31, 0.0), glm.vec2(-0.1, 0.1))
    assert moved.x == pytest.approx(0.31)
    assert moved.y == pytest.approx(0.1)


@pytest.mark.parametrize("side", [-1, 1])
def test_the_scripted_routes_never_touch_a_wall(side: int) -> None:
    collider = Collider(forest_lane_walls(), config.MR1_RADIUS)
    route = mr1_route(side)
    steps = 500
    for i in range(steps + 1):
        assert not collider.hits(route.point(route.length * i / steps))


def test_blocked_move_comes_to_rest_against_the_wall() -> None:
    collider = Collider([Wall(glm.vec2(1, -5), glm.vec2(1, 5))], radius=0.3)
    moved = collider.move(glm.vec2(0.0, 0.0), glm.vec2(1.0, 0.0))
    assert moved.x == pytest.approx(0.7, abs=1e-3)
    assert collider.clearance(moved) == pytest.approx(0.0, abs=1e-3)
