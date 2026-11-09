"""OpenGL rendering with moderngl: GPU models, textures and the per-frame draw."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image
from pyglm import glm

from robocon import config
from robocon.camera import Camera
from robocon.obj_loader import Material, MeshData, load_obj
from robocon.scene import LineSet, Scene

log = logging.getLogger(__name__)


def _shader_source(name: str) -> str:
    return resources.files("robocon").joinpath("shaders", name).read_text(encoding="utf-8")


@dataclass
class _Part:
    vao: moderngl.VertexArray
    material: Material
    texture: moderngl.Texture | None


class GpuModel:
    """One model on the GPU: a vertex array per material."""

    def __init__(
        self,
        ctx: moderngl.Context,
        program: moderngl.Program,
        mesh: MeshData,
        textures: TextureCache,
    ) -> None:
        self.parts: list[_Part] = []
        for submesh in mesh.submeshes:
            vbo = ctx.buffer(submesh.vertices.tobytes())
            vao = ctx.vertex_array(
                program, [(vbo, "3f 3f 2f", "in_position", "in_normal", "in_uv")]
            )
            texture = textures.get(submesh.material.texture) if submesh.material.texture else None
            self.parts.append(_Part(vao, submesh.material, texture))

    def render(self, program: moderngl.Program) -> None:
        for part in self.parts:
            # Untextured parts use their own material colour instead of whatever
            # texture happened to be bound last.
            _set(program, "u_has_texture", part.texture is not None)
            _set(program, "u_diffuse_color", part.material.diffuse)
            _set(program, "u_shininess", part.material.shininess)
            if part.texture is not None:
                part.texture.use(location=0)
            part.vao.render(moderngl.TRIANGLES)


class TextureCache:
    """Loads each image file once, even when several materials share it."""

    def __init__(self, ctx: moderngl.Context) -> None:
        self._ctx = ctx
        self._textures: dict[Path, moderngl.Texture] = {}

    def get(self, path: Path) -> moderngl.Texture:
        if path not in self._textures:
            self._textures[path] = self._load(path)
        return self._textures[path]

    def _load(self, path: Path) -> moderngl.Texture:
        with Image.open(path) as image:
            # OBJ texture coordinates start at the bottom-left; images at the top-left.
            image = image.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            texture = self._ctx.texture(image.size, 4, image.tobytes())
        texture.build_mipmaps()
        texture.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        texture.anisotropy = 8.0
        texture.repeat_x = texture.repeat_y = True
        return texture


class Renderer:
    def __init__(self, ctx: moderngl.Context, assets_dir: Path = config.ASSETS_DIR) -> None:
        self.ctx = ctx
        self.assets_dir = assets_dir
        self.program = ctx.program(
            vertex_shader=_shader_source("phong.vert"),
            fragment_shader=_shader_source("phong.frag"),
        )
        self.line_program = ctx.program(
            vertex_shader=_shader_source("line.vert"),
            fragment_shader=_shader_source("line.frag"),
        )
        self._textures = TextureCache(ctx)
        self._models: dict[str, GpuModel] = {}

    def load_models(self, keys: Iterable[str] = config.MODELS) -> None:
        for key in keys:
            self.model(key)

    def model(self, key: str) -> GpuModel:
        if key not in self._models:
            path = self.assets_dir / config.MODELS[key]
            log.info("loading %s", path.relative_to(self.assets_dir))
            self._models[key] = GpuModel(self.ctx, self.program, load_obj(path), self._textures)
        return self._models[key]

    def render(
        self,
        scene: Scene,
        camera: Camera,
        light_position: glm.vec3,
        viewport: tuple[int, int, int, int],
        lines: Sequence[LineSet] = (),
    ) -> None:
        """Draw the scene into ``viewport`` = (x, y, width, height) of the current framebuffer."""
        x, y, width, height = viewport
        self.ctx.viewport = (0, 0, x + width, y + height)
        self.ctx.clear(*config.BACKGROUND, depth=1.0)
        self.ctx.viewport = viewport
        self.ctx.enable(moderngl.DEPTH_TEST)

        view = camera.view_matrix()
        projection = camera.projection_matrix(width / max(height, 1))

        program = self.program
        _set(program, "u_view", view)
        _set(program, "u_projection", projection)
        _set(program, "u_view_position", camera.position)
        _set(program, "u_light_position", light_position)
        _set(program, "u_light_color", config.LIGHT_COLOR)
        _set(program, "u_ambient", config.AMBIENT)
        _set(program, "u_specular_strength", config.SPECULAR_STRENGTH)
        _set(program, "u_texture", 0)

        for entity in scene.entities():
            if not entity.visible:
                continue
            model = entity.model_matrix()
            _set(program, "u_model", model)
            _set(program, "u_normal_matrix", glm.transpose(glm.inverse(glm.mat3(model))))
            self.model(entity.model).render(program)

        # Overlay lines are arena geometry (walls, routes), so they move with the arena
        # and are not drawn when it is hidden.
        if lines and scene.arena.visible:
            self._render_lines(lines, scene.arena.model_matrix(), view, projection)

    def _render_lines(
        self, lines: Sequence[LineSet], model: glm.mat4, view: glm.mat4, proj: glm.mat4
    ) -> None:
        # Drawn over everything so walls hidden inside fences stay visible.
        self.ctx.disable(moderngl.DEPTH_TEST)
        _set(self.line_program, "u_model", model)
        _set(self.line_program, "u_view", view)
        _set(self.line_program, "u_projection", proj)
        for color, segments in lines:
            if not segments:
                continue
            points = np.array([[*p] for seg in segments for p in seg], dtype=np.float32)
            vbo = self.ctx.buffer(points.tobytes())
            vao = self.ctx.vertex_array(self.line_program, [(vbo, "3f", "in_position")])
            _set(self.line_program, "u_color", color)
            vao.render(moderngl.LINES)
            vao.release()
            vbo.release()


def _set(program: moderngl.Program, name: str, value: object) -> None:
    """Set a uniform, skipping ones the GLSL compiler optimised away."""
    if name not in program:
        return
    uniform = program[name]
    if isinstance(value, glm.mat4 | glm.mat3 | glm.vec3):
        uniform.write(value.to_bytes())
    else:
        uniform.value = value
