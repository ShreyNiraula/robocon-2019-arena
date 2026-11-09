"""The interactive window: GLFW input in, simulation step, render out."""

from __future__ import annotations

import logging

import glfw
import moderngl
from pyglm import glm

from robocon import config
from robocon.graphics import Renderer
from robocon.hud import Hud, help_text, sidebar_width
from robocon.simulation import Simulation

log = logging.getLogger(__name__)

_MODE_KEYS = {getattr(glfw, f"KEY_{n}"): n for n in range(1, 10)}


class App:
    def __init__(self, size: tuple[int, int] = config.WINDOW_SIZE) -> None:
        if not glfw.init():
            raise RuntimeError("could not initialise GLFW")
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)  # required on macOS
        glfw.window_hint(glfw.SAMPLES, 4)

        self.window = glfw.create_window(*size, f"{config.WINDOW_TITLE} (loading...)", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("could not create an OpenGL 3.3 window")
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)

        self.ctx = moderngl.create_context()
        self.renderer = Renderer(self.ctx)
        self.renderer.load_models()
        self.hud = Hud(self.ctx)
        self.show_help = True
        self.sim = Simulation()
        self._looking = False
        self._last_cursor = (0.0, 0.0)
        self._title = ""

        glfw.set_key_callback(self.window, self._on_key)
        glfw.set_scroll_callback(self.window, self._on_scroll)
        glfw.set_mouse_button_callback(self.window, self._on_mouse_button)
        glfw.set_cursor_pos_callback(self.window, self._on_cursor)

    def run(self) -> None:
        last = glfw.get_time()
        try:
            while not glfw.window_should_close(self.window):
                now = glfw.get_time()
                dt, last = now - last, now
                self._handle_held_keys(dt)
                self.sim.update(dt)
                width, height = glfw.get_framebuffer_size(self.window)
                scale = glfw.get_window_content_scale(self.window)[0]
                # The 3D view sits to the right of the help sidebar, never under it.
                left = min(sidebar_width(self.show_help, scale), width // 2)
                self.renderer.render(
                    self.sim.scene,
                    self.sim.camera,
                    self.sim.light_position(),
                    (left, 0, width - left, height),
                    self.sim.overlay_lines(),
                )
                self.hud.render(
                    help_text(self.sim, expanded=self.show_help), (width, height), scale
                )
                self._update_title()
                glfw.swap_buffers(self.window)
                glfw.poll_events()
        finally:
            glfw.terminate()

    # -- input -------------------------------------------------------------
    def _handle_held_keys(self, dt: float) -> None:
        # The camera looks up the field (+z), so +x is on the left of the screen.
        # Arrows and I/J/K/L both drive; held together they don't double the speed.
        sideways = self._axis(glfw.KEY_J, glfw.KEY_L) + self._axis(glfw.KEY_LEFT, glfw.KEY_RIGHT)
        ahead = self._axis(glfw.KEY_I, glfw.KEY_K) + self._axis(glfw.KEY_UP, glfw.KEY_DOWN)
        self.sim.drive = glm.vec2(glm.clamp(sideways, -1.0, 1.0), glm.clamp(ahead, -1.0, 1.0))
        if not self.sim.mode.free_camera:
            return
        forward = self._axis(glfw.KEY_W, glfw.KEY_S)
        strafe = self._axis(glfw.KEY_D, glfw.KEY_A)
        lift = self._axis(glfw.KEY_E, glfw.KEY_Q)
        if forward or strafe or lift:
            self.sim.camera.fly(forward, strafe, lift, min(dt, config.MAX_FRAME_TIME))

    def _axis(self, positive: int, negative: int) -> float:
        pressed = lambda key: glfw.get_key(self.window, key) == glfw.PRESS  # noqa: E731
        return float(pressed(positive)) - float(pressed(negative))

    def _on_key(self, window, key: int, scancode: int, action: int, mods: int) -> None:
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif key in _MODE_KEYS and _MODE_KEYS[key] in self.sim.modes:
            self.sim.set_mode(_MODE_KEYS[key])
        elif key == glfw.KEY_R:
            self.sim.restart()
        elif key == glfw.KEY_C:
            self.sim.show_overlay = not self.sim.show_overlay
        elif key == glfw.KEY_SPACE:
            self.sim.toggle_pause()
        elif key == glfw.KEY_H:
            self.show_help = not self.show_help

    def _on_scroll(self, window, x_offset: float, y_offset: float) -> None:
        if self.sim.mode.free_camera:
            self.sim.camera.zoom(y_offset)

    def _on_mouse_button(self, window, button: int, action: int, mods: int) -> None:
        if button == glfw.MOUSE_BUTTON_RIGHT:
            self._looking = action == glfw.PRESS
            self._last_cursor = glfw.get_cursor_pos(window)

    def _on_cursor(self, window, x: float, y: float) -> None:
        if self._looking and self.sim.mode.free_camera:
            last_x, last_y = self._last_cursor
            self.sim.camera.look(x - last_x, y - last_y)
        self._last_cursor = (x, y)

    def _update_title(self) -> None:
        mode = self.sim.mode
        keys = "/".join(str(k) for k in sorted(self.sim.modes))
        hints = f"{keys} modes, H help"
        title = f"{config.WINDOW_TITLE}  |  [{mode.key}] {mode.name}  |  {hints}"
        if title != self._title:
            glfw.set_window_title(self.window, title)
            self._title = title
