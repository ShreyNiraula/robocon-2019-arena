"""Yaw/pitch fly camera.

Angles are in degrees. With yaw = 90 the camera looks down +z, which is
"up the field" from the start zones.
"""

from __future__ import annotations

import math

from pyglm import glm

WORLD_UP = glm.vec3(0.0, 1.0, 0.0)
MIN_FOV, MAX_FOV = 1.0, 45.0
PITCH_LIMIT = 89.0


class Camera:
    def __init__(
        self,
        position: glm.vec3 | None = None,
        yaw: float = 90.0,
        pitch: float = -30.0,
        fov: float = MAX_FOV,
    ) -> None:
        self.position = glm.vec3(position) if position is not None else glm.vec3(0.0)
        self.yaw = yaw
        self.pitch = pitch
        self.fov = fov
        self.move_speed = 4.0  # units per second
        self.look_sensitivity = 0.1  # degrees per pixel

    # -- orientation -------------------------------------------------------
    @property
    def front(self) -> glm.vec3:
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        return glm.normalize(
            glm.vec3(
                math.cos(yaw) * math.cos(pitch),
                math.sin(pitch),
                math.sin(yaw) * math.cos(pitch),
            )
        )

    @property
    def right(self) -> glm.vec3:
        return glm.normalize(glm.cross(self.front, WORLD_UP))

    @property
    def up(self) -> glm.vec3:
        return glm.normalize(glm.cross(self.right, self.front))

    def set_pose(self, position: glm.vec3, yaw: float, pitch: float) -> None:
        self.position = glm.vec3(position)
        self.yaw = yaw
        self.pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, pitch))

    # -- matrices ----------------------------------------------------------
    def view_matrix(self) -> glm.mat4:
        return glm.lookAt(self.position, self.position + self.front, self.up)

    def projection_matrix(self, aspect: float) -> glm.mat4:
        # Built every frame so zoom and window resizes take effect.
        return glm.perspective(glm.radians(self.fov), max(aspect, 1e-3), 0.05, 100.0)

    # -- user input --------------------------------------------------------
    def look(self, dx: float, dy: float) -> None:
        self.yaw += dx * self.look_sensitivity
        self.pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, self.pitch - dy * self.look_sensitivity))

    def zoom(self, scroll: float) -> None:
        self.fov = max(MIN_FOV, min(MAX_FOV, self.fov - scroll))

    def fly(self, forward: float, strafe: float, lift: float, dt: float) -> None:
        """Move relative to where the camera faces; forward/strafe stay level with the floor."""
        flat_front = glm.vec3(self.front.x, 0.0, self.front.z)
        if glm.length(flat_front) > 1e-6:
            flat_front = glm.normalize(flat_front)
        step = self.move_speed * dt
        self.position += (flat_front * forward + self.right * strafe + WORLD_UP * lift) * step
