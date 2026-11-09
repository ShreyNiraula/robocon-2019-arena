"""On-screen help: a sidebar with the current mode, every mode, and the keys that work.

The sidebar sits to the left of the 3D view (the view is narrowed to make
room), so it never covers the scene. Collapsed with H, it shrinks to a small
badge in the corner and the 3D view gets the full window.

The text is drawn into an image with Pillow and shown as a textured quad.
The image is only rebuilt when the text or the window size changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import TYPE_CHECKING

import moderngl
import numpy as np
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from robocon.simulation import Simulation

Row = tuple[str, str]  # (key or label, text)

SIDEBAR_WIDTH = 300  # pixels at 1x scale
TITLE_SIZE, HEADING_SIZE, BODY_SIZE = 19, 11, 14  # points at 1x scale
PADDING, LINE_GAP, SECTION_GAP, KEY_GAP, MARGIN = 14, 3, 10, 12, 12  # pixels at 1x scale
SIDEBAR_COLOR = (18, 18, 24, 255)
BADGE_COLOR = (18, 18, 24, 220)
TITLE_COLOR = (255, 255, 255, 255)
HEADING_COLOR = (130, 130, 145, 255)
TEXT_COLOR = (205, 205, 210, 255)
DIM_COLOR = (140, 140, 150, 255)
STATUS_COLOR = (130, 220, 255, 255)
KEY_COLOR = (255, 205, 90, 255)
CURRENT_COLOR = (130, 220, 255, 255)


@dataclass(frozen=True)
class Section:
    heading: str
    rows: tuple[Row, ...]
    current: int | None = None  # index of the highlighted row


@dataclass(frozen=True)
class HelpText:
    title: str
    lines: tuple[str, ...] = ()
    status: str | None = None
    sections: tuple[Section, ...] = ()
    compact: bool = False  # collapsed badge instead of the sidebar

    def section(self, heading: str) -> Section:
        return next(s for s in self.sections if s.heading == heading)


def help_text(sim: Simulation, expanded: bool) -> HelpText:
    mode = sim.mode
    title = f"[{mode.key}] {mode.name}"
    if not expanded:
        return HelpText(title, sections=(Section("", (("H", "show help"),)),), compact=True)

    keys = sorted(sim.modes)
    modes = Section(
        "MODES",
        tuple((str(k), sim.modes[k].name) for k in keys),
        current=keys.index(mode.key),
    )
    controls: list[Row] = [
        (f"{keys[0]} - {keys[-1]}", "switch mode"),
        ("R", "restart this mode"),
        ("Space", "resume" if sim.paused else "pause"),
    ]
    controls += mode.hints
    if mode.free_camera:
        controls += [
            ("W A S D, Q E", "move camera"),
            ("Right-drag", "look around"),
            ("Scroll", "zoom"),
        ]
    controls += [
        ("C", "hide walls & routes" if sim.show_overlay else "show walls & routes"),
        ("H", "hide this panel"),
        ("Esc", "quit"),
    ]
    sections = [modes]
    info = mode.panel_rows(sim)
    if info:
        sections.append(Section(mode.panel_heading, tuple(info)))
    sections.append(Section("CONTROLS", tuple(controls)))

    lines = [mode.description]
    if not mode.free_camera:
        lines.append("The camera follows the robot.")
    status = "Paused" if sim.paused else mode.status(sim)
    return HelpText(title, tuple(lines), status, tuple(sections))


def sidebar_width(expanded: bool, scale: float) -> int:
    """Width in pixels that the 3D view must leave free on the left."""
    return round(SIDEBAR_WIDTH * scale) if expanded else 0


def rasterize(text: HelpText, scale: float = 1.0, height: int | None = None) -> Image.Image:
    """Draw the sidebar (``height`` pixels tall) or, for compact text, a small badge.

    If the sidebar's text does not fit the height, the text is drawn smaller until it does
    (down to 70%), so the last controls are never cut off in a short window.
    """
    if text.compact:
        return _draw_badge(text, scale)
    width = round(SIDEBAR_WIDTH * scale)
    text_scale = scale
    if height:
        needed = _sidebar_layout(text, width, text_scale)[0]
        if needed > height:
            text_scale = max(scale * 0.7, scale * height / needed * 0.98)
    return _draw_sidebar(text, width, text_scale, height or 0)


def _fonts(scale: float) -> dict[str, ImageFont.FreeTypeFont]:
    return {
        "title": ImageFont.load_default(size=round(TITLE_SIZE * scale)),
        "heading": ImageFont.load_default(size=round(HEADING_SIZE * scale)),
        "body": ImageFont.load_default(size=round(BODY_SIZE * scale)),
    }


def _spacing(scale: float) -> tuple[int, int, int, int]:
    return tuple(round(v * scale) for v in (PADDING, LINE_GAP, SECTION_GAP, KEY_GAP))


def _draw_badge(text: HelpText, scale: float) -> Image.Image:
    fonts = _fonts(scale)
    pad, gap, _, _ = _spacing(scale)
    body = fonts["body"]
    rows = text.sections[0].rows if text.sections else ()
    hint = "   ".join(f"{k}  {t}" for k, t in rows)
    width = pad * 2 + round(max(fonts["title"].getlength(text.title), body.getlength(hint)))
    badge_height = pad * 2 + _line_height(fonts["title"]) + gap + _line_height(body)
    image = Image.new("RGBA", (width, badge_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, width - 1, badge_height - 1), radius=round(8 * scale), fill=BADGE_COLOR
    )
    draw.text((pad, pad), text.title, font=fonts["title"], fill=TITLE_COLOR)
    draw.text((pad, pad + _line_height(fonts["title"]) + gap), hint, font=body, fill=KEY_COLOR)
    return image


def _sidebar_layout(text: HelpText, width: int, scale: float) -> tuple[int, list[str], list[str]]:
    """Height the sidebar's content needs, and its wrapped description and status lines."""
    fonts = _fonts(scale)
    pad, gap, section_gap, _ = _spacing(scale)
    body = fonts["body"]
    body_height = _line_height(body)
    text_width = width - 2 * pad
    lines = [wrapped for line in text.lines for wrapped in _wrap(line, body, text_width)]
    status = _wrap(text.status, body, text_width) if text.status else []
    needed = pad * 2 + _line_height(fonts["title"]) + gap
    needed += (body_height + gap) * (len(lines) + len(status))
    for section in text.sections:
        needed += section_gap + _line_height(fonts["heading"]) + gap
        needed += (body_height + gap) * len(section.rows)
    return needed, lines, status


def _draw_sidebar(text: HelpText, width: int, scale: float, height: int) -> Image.Image:
    fonts = _fonts(scale)
    pad, gap, section_gap, key_gap = _spacing(scale)
    body = fonts["body"]
    body_height = _line_height(body)
    needed, lines, status = _sidebar_layout(text, width, scale)

    image = Image.new("RGBA", (width, max(height, needed)), SIDEBAR_COLOR)
    draw = ImageDraw.Draw(image)
    y = pad
    draw.text((pad, y), text.title, font=fonts["title"], fill=TITLE_COLOR)
    y += _line_height(fonts["title"]) + gap
    for line in lines:
        draw.text((pad, y), line, font=body, fill=TEXT_COLOR)
        y += body_height + gap
    for line in status:
        draw.text((pad, y), line, font=body, fill=STATUS_COLOR)
        y += body_height + gap
    for section in text.sections:
        y += section_gap
        draw.text((pad, y), section.heading, font=fonts["heading"], fill=HEADING_COLOR)
        y += _line_height(fonts["heading"]) + gap
        key_width = max(body.getlength(k) for k, _ in section.rows)
        for i, (key, value) in enumerate(section.rows):
            current = section.current == i
            if current:
                draw.rectangle(
                    (pad // 2, y - gap // 2, width - pad // 2, y + body_height + gap // 2),
                    fill=(40, 60, 80, 255),
                )
            key_color = CURRENT_COLOR if current else KEY_COLOR
            value_color = TITLE_COLOR if current else TEXT_COLOR
            draw.text((pad, y), key, font=body, fill=key_color)
            draw.text((pad + key_width + key_gap, y), value, font=body, fill=value_color)
            y += body_height + gap
    return image


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and font.getlength(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    ascent, descent = font.getmetrics()
    return ascent + descent


class Hud:
    """Draws the sidebar (or the collapsed badge) on the left of the current framebuffer."""

    def __init__(self, ctx: moderngl.Context) -> None:
        self.ctx = ctx
        shaders = resources.files("robocon").joinpath("shaders")
        self.program = ctx.program(
            vertex_shader=shaders.joinpath("hud.vert").read_text(encoding="utf-8"),
            fragment_shader=shaders.joinpath("hud.frag").read_text(encoding="utf-8"),
        )
        corners = np.array([0, 0, 1, 0, 0, 1, 1, 1], dtype="f4")
        self.vao = ctx.vertex_array(
            self.program, [(ctx.buffer(corners.tobytes()), "2f", "in_corner")]
        )
        self._texture: moderngl.Texture | None = None
        self._drawn: tuple[HelpText, float, int] | None = None

    def render(self, text: HelpText, size: tuple[int, int], scale: float = 1.0) -> None:
        width, height = size
        if self._drawn != (text, scale, height):
            self._upload(rasterize(text, scale, height=None if text.compact else height))
            self._drawn = (text, scale, height)
        assert self._texture is not None

        panel_w, panel_h = self._texture.size
        margin = MARGIN * scale if text.compact else 0
        self.ctx.viewport = (0, 0, width, height)
        # Rectangle in clip space: left, bottom, width, height (anchored top-left).
        self.program["u_rect"].value = (
            -1 + 2 * margin / width,
            1 - 2 * (margin + panel_h) / height,
            2 * panel_w / width,
            2 * panel_h / height,
        )
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self._texture.use(location=0)
        self.vao.render(moderngl.TRIANGLE_STRIP)
        self.ctx.disable(moderngl.BLEND)

    def _upload(self, image: Image.Image) -> None:
        if self._texture is not None:
            self._texture.release()
        flipped = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)  # GL rows start at the bottom
        self._texture = self.ctx.texture(image.size, 4, flipped.tobytes())
        self._texture.filter = (moderngl.NEAREST, moderngl.NEAREST)  # 1:1 pixels, keep text crisp
