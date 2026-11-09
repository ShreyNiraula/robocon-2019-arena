from pathlib import Path

import pytest
from pyglm import glm

from robocon import config
from robocon.collision import Collider, Wall
from robocon.path import LINE_1_X, MotionLimits
from robocon.runlog import RunLog
from robocon.simulation import Simulation
from robocon.trial import Driver, TimeTrial, course_checkpoints

DT = 1 / 60


def trial_sim(tmp_path: Path | None = None) -> Simulation:
    log = RunLog(tmp_path / "runs.csv" if tmp_path else None)
    sim = Simulation(run_log=log)
    sim.set_mode(6)
    return sim


def autopilot(sim: Simulation, max_seconds: float = 60) -> None:
    """Steer straight at the next checkpoint, then past Line 1, until the run finishes."""
    trial: TimeTrial = sim.mode
    beyond_line = glm.vec2(-LINE_1_X + 1.0, 3.99)
    for _ in range(round(max_seconds / DT)):
        if trial.phase == "finished":
            return
        if trial.next_checkpoint < len(trial.checkpoints):
            target = trial.checkpoints[trial.next_checkpoint]
        else:
            target = beyond_line
        sim.drive = target - trial.driver.position
        sim.update(DT)
    raise AssertionError("autopilot did not finish")


def test_course_has_every_corner_plus_the_bridge_in_order() -> None:
    checkpoints = course_checkpoints()
    assert len(checkpoints) == 10
    assert (checkpoints[8].x, checkpoints[8].y) == pytest.approx((-5.43, 2.0))  # the bridge
    assert all(c.x < 0 for c in checkpoints)  # red half


def test_clock_waits_for_the_first_input() -> None:
    sim = trial_sim()
    for _ in range(120):
        sim.update(DT)
    assert sim.mode.phase == "ready"
    assert sim.mode.elapsed == 0
    sim.drive = glm.vec2(0, 1)
    sim.update(DT)
    assert sim.mode.phase == "running"


def test_reference_time_is_the_line_follower_reaching_line_1() -> None:
    trial = trial_sim().mode
    assert 0 < trial.reference_time < trial.ghost.total_time
    assert trial.reference_splits == sorted(trial.reference_splits)


def test_crossing_line_1_without_the_checkpoints_does_not_finish() -> None:
    sim = trial_sim()
    trial: TimeTrial = sim.mode
    trial.phase = "running"
    trial.driver.position = glm.vec2(-LINE_1_X + 1.0, 3.99)  # teleport past the line
    sim.update(DT)
    assert trial.phase == "running"


def test_a_full_run_finishes_and_is_logged(tmp_path: Path) -> None:
    sim = trial_sim(tmp_path)
    autopilot(sim)
    trial: TimeTrial = sim.mode
    assert trial.next_checkpoint == len(trial.checkpoints)
    assert trial.result is not None
    assert trial.result.time == pytest.approx(trial.elapsed)
    assert trial.result.reference == pytest.approx(trial.reference_time)
    assert trial.last_split is not None

    reloaded = RunLog(tmp_path / "runs.csv")
    assert len(reloaded.runs) == 1
    assert reloaded.runs[0].time == pytest.approx(trial.result.time, abs=1e-3)


def test_clock_stops_at_the_finish() -> None:
    sim = trial_sim()
    autopilot(sim)
    finished_at = sim.mode.elapsed
    for _ in range(120):
        sim.update(DT)
    assert sim.mode.elapsed == finished_at


def test_restart_resets_the_run_but_keeps_the_log() -> None:
    sim = trial_sim()
    autopilot(sim)
    sim.restart()
    assert sim.mode.phase == "ready"
    assert sim.mode.next_checkpoint == 0
    assert len(sim.run_log.runs) == 1


def test_panel_shows_times_best_and_recent_runs() -> None:
    sim = trial_sim()
    autopilot(sim)
    labels = [label for label, _ in sim.mode.panel_rows(sim)]
    for expected in ("Time", "Line follower", "Checkpoints", "Wall hits", "Best", "Recent"):
        assert expected in labels


def test_next_checkpoint_and_finish_line_are_drawn() -> None:
    sim = trial_sim()
    colors = [color for color, _ in sim.overlay_lines()]
    assert len(colors) == 3  # next checkpoint, later checkpoints, Line 1


def test_driver_accelerates_within_its_limit() -> None:
    limits = MotionLimits(max_speed=2.0, accel=2.0)
    driver = Driver(glm.vec2(0), limits, Collider([], radius=0.3))
    driver.update(glm.vec2(1, 0), 0.25)
    assert glm.length(driver.velocity) == pytest.approx(0.5)
    for _ in range(100):
        driver.update(glm.vec2(1, 0), 0.05)
    assert glm.length(driver.velocity) == pytest.approx(2.0)


def test_driver_counts_each_wall_contact_once() -> None:
    wall = Wall(glm.vec2(1, -5), glm.vec2(1, 5))
    driver = Driver(glm.vec2(0), MotionLimits(2.0, 20.0), Collider([wall], radius=0.3))
    for _ in range(60):
        driver.update(glm.vec2(1, 0), DT)  # pressed against the wall for a second
    assert driver.wall_hits == 1
    assert driver.position.x == pytest.approx(0.7, abs=0.05)
    for _ in range(30):
        driver.update(glm.vec2(-1, 0), DT)
    for _ in range(60):
        driver.update(glm.vec2(1, 0), DT)
    assert driver.wall_hits == 2


def test_run_log_keeps_best_and_newest_first(tmp_path: Path) -> None:
    log = RunLog(tmp_path / "runs.csv")
    for time in (20.0, 17.5, 19.0):
        log.add(time, reference=18.0, wall_hits=0)
    assert log.best.time == 17.5
    assert [r.time for r in log.recent(2)] == [19.0, 17.5]
    assert log.best.delta == pytest.approx(-0.5)


def test_run_log_skips_bad_rows(tmp_path: Path) -> None:
    path = tmp_path / "runs.csv"
    path.write_text(
        "finished_at,time_s,reference_s,delta_s,wall_hits\n"
        "2026-11-08T10:00:00,18.5,18.0,+0.5,1\n"
        "garbage,row\n"
    )
    assert [r.time for r in RunLog(path).runs] == [18.5]


def test_in_memory_log_writes_nothing(tmp_path: Path) -> None:
    log = RunLog()
    log.add(10.0, 12.0, 0)
    assert log.path is None and len(log.runs) == 1


def test_time_trial_uses_the_mr1_radius_for_the_finish() -> None:
    trial = trial_sim().mode
    assert trial.finish_x == pytest.approx(-LINE_1_X + config.MR1_RADIUS)
