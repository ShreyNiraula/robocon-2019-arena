"""Floor height under a point, from the arena's raised parts.

Only two things in the arena stand above the floor where robots walk: the
sand-dune timber (0.1 high) and the mountain (a 0.4-high top between
x = +/-1.11 with ramps down to x = +/-2.70). Their triangles are taken from
the arena model by material, so the height follows the real geometry.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np

from robocon import config
from robocon.obj_loader import MeshData, load_obj

# Materials of the arena model that robots walk on top of.
RAISED_MATERIALS = ("Material.001", "Material.001_NONE", "Material.002")  # mountain, sand dune


class Terrain:
    def __init__(self, triangles: np.ndarray) -> None:
        """``triangles`` is (n, 3, 3): n triangles of three (x, y, z) corners."""
        self.triangles = np.asarray(triangles, dtype=np.float64).reshape(-1, 3, 3)

    @classmethod
    def from_mesh(cls, mesh: MeshData, materials: Iterable[str] = RAISED_MATERIALS) -> Terrain:
        wanted = set(materials)
        parts = [s.vertices[:, :3] for s in mesh.submeshes if s.material.name in wanted]
        if not parts:
            return cls(np.zeros((0, 3, 3)))
        return cls(np.concatenate(parts).reshape(-1, 3, 3))

    @classmethod
    def arena(cls, assets_dir: Path = config.ASSETS_DIR) -> Terrain:
        return cls.from_mesh(load_obj(assets_dir / config.MODELS["arena"]))

    def height(self, x: float, z: float) -> float:
        """Highest raised surface above (x, z), or 0 for the bare floor."""
        if len(self.triangles) == 0:
            return 0.0
        a, b, c = self.triangles[:, 0], self.triangles[:, 1], self.triangles[:, 2]
        # Barycentric coordinates in the xz plane.
        v0 = c[:, [0, 2]] - a[:, [0, 2]]
        v1 = b[:, [0, 2]] - a[:, [0, 2]]
        v2 = np.array([x, z]) - a[:, [0, 2]]
        dot00 = (v0 * v0).sum(1)
        dot01 = (v0 * v1).sum(1)
        dot02 = (v0 * v2).sum(1)
        dot11 = (v1 * v1).sum(1)
        dot12 = (v1 * v2).sum(1)
        denominator = dot00 * dot11 - dot01 * dot01
        flat = np.abs(denominator) < 1e-12  # triangles seen edge-on from above
        denominator = np.where(flat, 1.0, denominator)
        u = (dot11 * dot02 - dot01 * dot12) / denominator
        v = (dot00 * dot12 - dot01 * dot02) / denominator
        inside = ~flat & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
        if not inside.any():
            return 0.0
        y = a[:, 1] + u * (c[:, 1] - a[:, 1]) + v * (b[:, 1] - a[:, 1])
        return max(0.0, float(y[inside].max()))
