from robocon.hud import HelpText, help_text, rasterize, sidebar_width
from robocon.simulation import Simulation


def keys(text: HelpText) -> list[str]:
    return [key for key, _ in text.section("CONTROLS").rows]


def test_every_mode_is_listed_by_name_and_the_current_one_is_marked() -> None:
    sim = Simulation()
    sim.set_mode(3)
    modes = help_text(sim, expanded=True).section("MODES")
    assert modes.rows == tuple((str(k), m.name) for k, m in sorted(sim.modes.items()))
    assert modes.rows[modes.current] == ("3", "MR2 close-up")


def test_collapsed_panel_is_a_small_badge() -> None:
    text = help_text(Simulation(), expanded=False)
    assert text.compact
    assert text.sections[0].rows == (("H", "show help"),)


def test_sidebar_takes_room_only_when_expanded() -> None:
    assert sidebar_width(expanded=True, scale=2.0) == 2 * sidebar_width(expanded=True, scale=1.0)
    assert sidebar_width(expanded=False, scale=2.0) == 0


def test_camera_keys_hidden_when_the_camera_is_scripted() -> None:
    sim = Simulation()
    sim.set_mode(5)
    text = help_text(sim, expanded=True)
    assert "W A S D, Q E" not in keys(text)
    assert "The camera follows the robot." in text.lines


def test_status_follows_the_handoff() -> None:
    sim = Simulation()
    sim.set_mode(5)
    assert help_text(sim, expanded=True).status == "Riding MR1"
    while sim.mode_time < sim.mode.handoff_time + 0.1:
        sim.update(0.1)
    assert help_text(sim, expanded=True).status.startswith("Riding MR2")


def test_pause_is_shown() -> None:
    sim = Simulation()
    sim.toggle_pause()
    text = help_text(sim, expanded=True)
    assert text.status == "Paused"
    assert ("Space", "resume") in text.section("CONTROLS").rows


def test_overlay_row_says_what_c_will_do() -> None:
    sim = Simulation()
    assert ("C", "show walls & routes") in help_text(sim, expanded=True).section("CONTROLS").rows
    sim.show_overlay = True
    assert ("C", "hide walls & routes") in help_text(sim, expanded=True).section("CONTROLS").rows


def test_every_mode_has_a_description() -> None:
    sim = Simulation()
    for mode in sim.modes.values():
        assert mode.description


def test_sidebar_fills_the_window_height_and_scales() -> None:
    text = help_text(Simulation(), expanded=True)
    small, large = rasterize(text, 1.0, height=900), rasterize(text, 2.0, height=1800)
    assert small.size == (sidebar_width(True, 1.0), 900)
    assert large.size == (sidebar_width(True, 2.0), 1800)


def test_long_descriptions_wrap_inside_the_sidebar() -> None:
    from PIL import ImageFont

    from robocon.hud import BODY_SIZE, PADDING, _sidebar_layout

    width = sidebar_width(True, 1.0)
    _, lines, _ = _sidebar_layout(HelpText("title", lines=("word " * 80,)), width, 1.0)
    font = ImageFont.load_default(size=BODY_SIZE)
    assert len(lines) > 1
    assert all(font.getlength(line) <= width - 2 * PADDING for line in lines)
