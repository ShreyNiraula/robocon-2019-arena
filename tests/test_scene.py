import math

import pytest
from pyglm import glm

from robocon import config
from robocon.scene import Entity, Scene


def test_default_scene_uses_start_positions() -> None:
    scene = Scene.default()
    assert scene.robot_red.position == config.ROBOT_RED_START
    assert scene.spider_blue.position == config.SPIDER_BLUE_START


def test_default_scene_does_not_share_vectors_with_config() -> None:
    scene = Scene.default()
    scene.robot_red.position.x += 1
    assert Scene.default().robot_red.position == config.ROBOT_RED_START


def test_show_only_hides_everything_else() -> None:
    scene = Scene.default()
    scene.show_only(scene.arena, scene.robot_blue)
    assert [e.visible for e in scene.entities()] == [True, False, True, False, False]


def test_model_matrix_scales_then_translates() -> None:
    entity = Entity("robot_red", glm.vec3(1, 2, 3), scale=10, yaw=math.pi / 2)
    corner = entity.model_matrix() * glm.vec4(1, 0, 0, 1)
    # rotate +x by 90 degrees about y -> -z, scale by 10, then move by (1, 2, 3)
    assert (corner.x, corner.y, corner.z) == pytest.approx((1, 2, -7), abs=1e-5)
