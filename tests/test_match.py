import pytest
from pyglm import glm

from robocon import config
from robocon.match import BLUE, Match
from robocon.simulation import Simulation

DT = 1 / 60


def match_sim() -> Simulation:
    sim = Simulation()
    sim.set_mode(4)
    return sim


def play(sim: Simulation, seconds: float, bot: bool = True) -> None:
    for _ in range(round(seconds / DT)):
        sim.drive = sim.mode.autopilot(sim) if bot else glm.vec2(0.0)
        sim.update(DT)


def test_nothing_moves_until_the_first_input() -> None:
    sim = match_sim()
    play(sim, 3, bot=False)
    match: Match = sim.mode
    assert match.phase == "ready" and match.clock == 0
    assert sim.scene.robot_red.position == config.ROBOT_RED_START
    assert "Drive the blue MR1 to start" in match.status(sim)


def test_red_starts_with_your_first_input() -> None:
    sim = match_sim()
    play(sim, 1)
    assert sim.mode.phase == "running"
    assert sim.scene.robot_red.position != config.ROBOT_RED_START


def test_blue_mr1_must_pass_checkpoints_cross_line_1_then_hand_off() -> None:
    sim = match_sim()
    match: Match = sim.mode
    while match.blue_handoff_at is None and match.clock < 60:
        play(sim, 0.1)
    assert match.next_checkpoint == len(match.checkpoints)
    assert match.crossed_line_1
    assert match.blue_handoff_at is not None
    assert "blue MR2 runs on its own" in match.status(sim)


def test_handoff_is_ignored_before_crossing_line_1() -> None:
    sim = match_sim()
    match: Match = sim.mode
    play(sim, 0.1)
    match.driver.position = glm.vec2(match.handoff_point)  # teleport to Gobi urtuu
    sim.drive = glm.vec2(0.0)
    sim.update(DT)
    assert match.blue_handoff_at is None


def test_blue_mr2_runs_by_itself_after_the_handoff() -> None:
    sim = match_sim()
    match: Match = sim.mode
    while match.blue_handoff_at is None:
        play(sim, 0.1)
    start = glm.vec3(sim.scene.spider_blue.position)
    play(sim, 6, bot=False)
    assert sim.scene.spider_blue.position.z < start.z - 2  # walking down its guideline


def test_a_quick_driver_beats_the_line_follower() -> None:
    sim = match_sim()
    match: Match = sim.mode
    play(sim, match.red_finish_time + 5)
    # By now red has finished too, so both times are shown.
    assert dict(match.panel_rows(sim))["Red UUKHAI"] == f"{match.red_finish_time:.1f} s"
    assert match.phase == "finished"
    assert match.winner == "blue"
    assert match.status(sim).startswith("BLUE WINS")
    assert match.blue_finish_time < match.red_finish_time
    labels = dict(match.panel_rows(sim))
    assert labels["Blue UUKHAI"] == f"{match.blue_finish_time:.1f} s"


def test_red_wins_if_blue_stops_driving() -> None:
    sim = match_sim()
    match: Match = sim.mode
    play(sim, 0.2)  # start, then let go
    play(sim, match.red_finish_time + 1, bot=False)
    assert match.winner == "red"
    assert match.blue_finish_time is None
    labels = dict(match.panel_rows(sim))
    assert labels["Red UUKHAI"] == f"{match.red_finish_time:.1f} s"
    assert labels["Blue UUKHAI"] == "not yet"


def test_panel_tracks_both_teams() -> None:
    sim = match_sim()
    play(sim, 1)
    labels = dict(sim.mode.panel_rows(sim))
    assert labels["Blue"].startswith("MR1, checkpoint")
    assert labels["Red"] == "MR1, in the forest"


def test_restart_resets_the_match() -> None:
    sim = match_sim()
    play(sim, 20)
    sim.restart()
    match: Match = sim.mode
    assert match.phase == "ready" and match.blue_handoff_at is None and match.next_checkpoint == 0
    assert sim.scene.robot_blue.position == config.ROBOT_BLUE_START


def test_blue_course_is_on_the_blue_half() -> None:
    match = Match()
    assert all(c.x > 0 for c in match.checkpoints)
    assert match.handoff_point.x == pytest.approx(BLUE * 1.22)


def test_red_mr2_runs_all_the_way_to_uukhai() -> None:
    sim = Simulation()
    sim.set_mode(4)
    sim.drive = glm.vec2(0.0, 1.0)  # the match starts on the first input
    sim.update(1 / 60)
    sim.drive = glm.vec2(0.0)
    match = sim.mode
    for _ in range(round((match.red_finish_time + 1) * 60)):
        sim.update(1 / 60)
    spider = sim.scene.spider_red.position
    assert (spider.x, spider.y, spider.z) == pytest.approx((-0.56, 0.4, -4.25), abs=1e-3)
    assert match.winner == "red"
