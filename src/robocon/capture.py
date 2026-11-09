"""Headless rendering: run the simulation with a fixed time step and save PNGs.

Used to make the README screenshots and as an end-to-end check that every
mode renders. No window is opened.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import moderngl
from PIL import Image
from pyglm import glm

from robocon.graphics import Renderer
from robocon.hud import Hud, help_text, sidebar_width
from robocon.simulation import Simulation

log = logging.getLogger(__name__)

FPS = 60
HUD_SCALE = 1.0
TOP_DOWN_CAMERA = (glm.vec3(0.0, 15.0, 0.01), 90.0, -89.9)
COVER_CAMERA = (glm.vec3(0.0, 9.0, -9.6), 90.0, -45.0)  # whole arena, framed for 2:1
GOBI_CAMERA = (glm.vec3(-2.2, 4.2, 1.6), -90.0, -40.0)  # behind MR2, over the red Gobi area


@dataclass(frozen=True)
class Shot:
    filename: str
    mode: int
    seconds: float
    top_down: bool = False
    overlay: bool = False
    hud: bool = False
    autopilot: bool = False  # let the mode's bot drive (time trial and match)
    camera: tuple[glm.vec3, float, float] | None = None  # (position, yaw, pitch) override
    size: tuple[int, int] | None = None  # override the capture size for this shot


SHOTS = [
    Shot("arena.png", mode=1, seconds=1.0),
    Shot("mr1-closeup.png", mode=2, seconds=4.0),
    Shot("mr2-closeup.png", mode=3, seconds=4.0),
    Shot("match.png", mode=4, seconds=8.0, autopilot=True),
    Shot("mr2-sand-dune.png", mode=4, seconds=25.0, autopilot=True, camera=GOBI_CAMERA),
    Shot("mr2-mountain.png", mode=4, seconds=39.5, autopilot=True, camera=GOBI_CAMERA),
    Shot("robot-view-forest.png", mode=5, seconds=5.5),
    Shot("robot-view-mr2.png", mode=5, seconds=31.5),
    Shot("walls-and-routes.png", mode=4, seconds=9.0, top_down=True, overlay=True),
    Shot("help-panel.png", mode=4, seconds=4.0, hud=True),
    Shot("time-trial.png", mode=6, seconds=4.5, hud=True, autopilot=True),
    # 2:1 cover for portfolio cards and the README header
    Shot("cover.png", mode=4, seconds=22.0, autopilot=True, camera=COVER_CAMERA, size=(1600, 800)),
]


def capture(
    out_dir: Path, shots: list[Shot] = SHOTS, size: tuple[int, int] = (1280, 720)
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = moderngl.create_standalone_context(require=330)
    try:
        renderer = Renderer(ctx)
        hud = Hud(ctx)
        framebuffers: dict[tuple[int, int], tuple[moderngl.Framebuffer, moderngl.Framebuffer]] = {}

        def framebuffers_for(shot_size: tuple[int, int]):
            # Render with 4x MSAA, then resolve into a plain framebuffer to read back.
            if shot_size not in framebuffers:
                framebuffers[shot_size] = (
                    ctx.framebuffer(
                        color_attachments=[ctx.renderbuffer(shot_size, samples=4)],
                        depth_attachment=ctx.depth_renderbuffer(shot_size, samples=4),
                    ),
                    ctx.framebuffer(color_attachments=[ctx.renderbuffer(shot_size)]),
                )
            return framebuffers[shot_size]

        written = []
        for shot in shots:
            shot_size = shot.size or size
            msaa, resolved = framebuffers_for(shot_size)
            sim = Simulation()
            sim.set_mode(shot.mode)
            sim.show_overlay = shot.overlay
            for _ in range(round(shot.seconds * FPS)):
                if shot.autopilot:
                    sim.drive = sim.mode.autopilot(sim) or glm.vec2(0.0)
                sim.update(1 / FPS)
            if shot.top_down:
                sim.camera.set_pose(*TOP_DOWN_CAMERA)
            if shot.camera:
                sim.camera.set_pose(*shot.camera)

            msaa.use()
            left = sidebar_width(shot.hud, HUD_SCALE)
            viewport = (left, 0, shot_size[0] - left, shot_size[1])
            renderer.render(
                sim.scene, sim.camera, sim.light_position(), viewport, sim.overlay_lines()
            )
            if shot.hud:
                hud.render(help_text(sim, expanded=True), shot_size, scale=HUD_SCALE)
            ctx.copy_framebuffer(resolved, msaa)
            pixels = resolved.read(components=3)
            image = Image.frombytes("RGB", shot_size, pixels).transpose(
                Image.Transpose.FLIP_TOP_BOTTOM
            )
            path = out_dir / shot.filename
            image.save(path, optimize=True)
            log.info("wrote %s", path)
            written.append(path)
        return written
    finally:
        ctx.release()
