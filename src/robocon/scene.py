"""What is in the arena and where. Pure data: no OpenGL here, so it can be unit tested."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pyglm import glm

from robocon import config

# A debug overlay: an RGB colour and the (start, end) points of its line segments.
LineSet = tuple[tuple[float, float, float], Sequence[tuple[glm.vec3, glm.vec3]]]


@dataclass
class Entity:
    model: str  # key into config.MODELS
    position: glm.vec3
    scale: float = 1.0
    yaw: float = 0.0  # radians about +y
    visible: bool = True

    def model_matrix(self) -> glm.mat4:
        matrix = glm.translate(glm.mat4(1.0), self.position)
        matrix = glm.scale(matrix, glm.vec3(self.scale))
        return glm.rotate(matrix, self.yaw, glm.vec3(0.0, 1.0, 0.0))


@dataclass
class Scene:
    arena: Entity
    robot_red: Entity
    robot_blue: Entity
    spider_red: Entity
    spider_blue: Entity

    @classmethod
    def default(cls) -> Scene:
        """Every object at its start position; modes start from this so they replay cleanly."""
        return cls(
            arena=Entity("arena", glm.vec3(0.0)),
            robot_red=Entity("robot_red", glm.vec3(config.ROBOT_RED_START)),
            robot_blue=Entity("robot_blue", glm.vec3(config.ROBOT_BLUE_START)),
            spider_red=Entity("spider_red", glm.vec3(config.SPIDER_RED_START)),
            spider_blue=Entity("spider_blue", glm.vec3(config.SPIDER_BLUE_START)),
        )

    def entities(self) -> list[Entity]:
        return [self.arena, self.robot_red, self.robot_blue, self.spider_red, self.spider_blue]

    def show_only(self, *visible: Entity) -> None:
        for entity in self.entities():
            entity.visible = any(entity is v for v in visible)
