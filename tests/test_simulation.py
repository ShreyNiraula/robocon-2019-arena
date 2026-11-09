import math

import pytest
from pyglm import glm

from robocon import config
from robocon.simulation import Simulation


def run(sim: Simulation, seconds: float, fps: int = 60) -> None:
    for _ in range(round(seconds * fps)):
        sim.update(1 / fps)


def test_starts_on_the_first_mode_with_something_visible() -> None:
    sim = Simulation()
    assert sim.mode.key == 1
    assert any(e.visible for e in sim.scene.entities())


@pytest.mark.parametrize("key", [1, 2, 3, 5])
def test_every_mode_replays_from_the_same_state(key: int) -> None:
    sim = Simulation()
    sim.set_mode(key)
    run(sim, 0.5)
    first = [(glm.vec3(e.position), e.yaw, e.visible) for e in sim.scene.entities()]
    run(sim, 3)
    sim.set_mode(key)
    run(sim, 0.5)
    again = [(glm.vec3(e.position), e.yaw, e.visible) for e in sim.scene.entities()]
    assert first == again


def test_switching_modes_resets_the_camera() -> None:
    sim = Simulation()
    sim.camera.fly(1, 1, 1, dt=2)
    sim.camera.zoom(30)
    sim.set_mode(2)
    position, yaw, pitch = config.OVERVIEW_CAMERA
    assert sim.camera.position == position
    assert sim.camera.fov == 45


def test_animation_speed_does_not_depend_on_frame_rate() -> None:
    slow, fast = Simulation(), Simulation()
    run(slow, 2.0, fps=30)
    run(fast, 2.0, fps=144)
    assert slow.scene.arena.yaw == pytest.approx(fast.scene.arena.yaw, abs=1e-4)


@pytest.mark.parametrize("key", [1, 2, 3])
def test_showcases_turn_slowly_in_place(key: int) -> None:
    sim = Simulation()
    sim.set_mode(key)
    shown = next(e for e in sim.scene.entities() if e.visible)
    start = glm.vec3(shown.position)
    run(sim, 10)
    assert shown.position == start  # no more floating out of view
    assert shown.yaw == pytest.approx(config.SHOWCASE_SPIN_RATE * 10, abs=1e-3)


def test_pause_freezes_everything_until_resumed() -> None:
    sim = Simulation()
    run(sim, 1)
    sim.toggle_pause()
    yaw, mode_time = sim.scene.arena.yaw, sim.mode_time
    run(sim, 5)
    assert (sim.scene.arena.yaw, sim.mode_time) == (yaw, mode_time)
    sim.toggle_pause()
    run(sim, 1)
    assert sim.mode_time > mode_time


def test_long_frames_are_clamped() -> None:
    sim = Simulation()
    sim.update(5.0)
    assert sim.mode_time == pytest.approx(config.MAX_FRAME_TIME)


def test_light_orbits_at_constant_radius() -> None:
    sim = Simulation()
    for _ in range(10):
        sim.update(0.1)
        light = sim.light_position()
        assert glm.length(glm.vec2(light.x, light.z)) == pytest.approx(config.LIGHT_ORBIT_RADIUS)
        assert light.y == config.LIGHT_HEIGHT


def test_robot_view_rides_mr1_then_mr2() -> None:
    sim = Simulation()
    sim.set_mode(5)
    view = sim.mode
    assert not sim.scene.robot_red.visible  # the camera is MR1
    assert sim.camera.position.y == pytest.approx(config.MR1_EYE_HEIGHT)

    run(sim, view.handoff_time / 2)
    halfway = view.mr1.point(config.RIDE_SPEED * sim.mode_time)
    assert (sim.camera.position.x, sim.camera.position.z) == pytest.approx(
        (halfway.x, halfway.y), abs=1e-3
    )

    run(sim, view.handoff_time / 2 + 3)
    assert sim.scene.robot_red.visible  # parked at the hand-off
    assert not sim.scene.spider_red.visible  # the camera is MR2 now
    assert sim.camera.position.y == pytest.approx(config.MR2_EYE_HEIGHT)


def test_robot_view_ends_on_the_mountain_facing_the_uukhai_zone() -> None:
    sim = Simulation()
    sim.set_mode(5)
    run(sim, sim.mode.handoff_time + sim.mode.mr2.total_time + 2)
    assert math.cos(math.radians(sim.camera.yaw)) == pytest.approx(1, abs=1e-3)  # +x, uphill
    assert sim.camera.position.y == pytest.approx(0.4 + config.MR2_EYE_HEIGHT, abs=1e-3)


def test_robot_view_ignores_free_camera_input_and_replays() -> None:
    sim = Simulation()
    sim.set_mode(5)
    assert not sim.mode.free_camera
    run(sim, 60)
    sim.set_mode(5)
    run(sim, 1)
    assert sim.camera.position.z < -3  # back near the start zone


def test_overlay_is_off_by_default_and_has_walls_when_on() -> None:
    sim = Simulation()
    assert sim.overlay_lines() == []
    sim.show_overlay = True
    walls = sim.overlay_lines()[0][1]
    assert len(walls) == 9
