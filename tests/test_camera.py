import pytest
from pyglm import glm

from robocon.camera import MAX_FOV, MIN_FOV, PITCH_LIMIT, Camera


def approx_vec(v: glm.vec3, expected: tuple[float, float, float], tol: float = 1e-6) -> None:
    assert (v.x, v.y, v.z) == pytest.approx(expected, abs=tol)


def test_yaw_90_looks_up_the_field() -> None:
    approx_vec(Camera(yaw=90, pitch=0).front, (0, 0, 1))


def test_yaw_0_looks_along_x() -> None:
    approx_vec(Camera(yaw=0, pitch=0).front, (1, 0, 0))


def test_pitch_is_clamped() -> None:
    camera = Camera()
    camera.look(0, -1e6)
    assert camera.pitch == PITCH_LIMIT
    camera.look(0, 1e6)
    assert camera.pitch == -PITCH_LIMIT


def test_zoom_is_clamped_both_ways() -> None:
    camera = Camera()
    camera.zoom(1000)
    assert camera.fov == MIN_FOV
    camera.zoom(-1000)
    assert camera.fov == MAX_FOV


def test_zoom_changes_the_projection() -> None:
    camera = Camera()
    wide = camera.projection_matrix(16 / 9)
    camera.zoom(20)
    assert camera.projection_matrix(16 / 9) != wide


def test_fly_forward_stays_level_when_looking_down() -> None:
    camera = Camera(position=glm.vec3(0, 5, 0), yaw=90, pitch=-60)
    camera.fly(forward=1, strafe=0, lift=0, dt=1.0)
    assert camera.position.y == pytest.approx(5)
    assert camera.position.z == pytest.approx(camera.move_speed)


def test_fly_is_frame_rate_independent() -> None:
    one_step, many_steps = Camera(), Camera()
    one_step.fly(1, 1, 0, dt=1.0)
    for _ in range(120):
        many_steps.fly(1, 1, 0, dt=1 / 120)
    # float32 accumulates ~1e-6 of rounding error over 120 steps
    approx_vec(many_steps.position, (one_step.position.x, 0, one_step.position.z), tol=1e-4)
