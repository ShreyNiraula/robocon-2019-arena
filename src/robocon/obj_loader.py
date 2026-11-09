"""Wavefront OBJ/MTL loading.

Each model is split into one submesh per material. Vertices are flattened
(no index buffer) into float32 rows of ``position(3) normal(3) uv(2)``,
which is the layout the renderer uploads as-is. Parsed models are cached
on disk because the robot models take a few seconds to parse in Python.
"""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

FLOATS_PER_VERTEX = 8
_CACHE_VERSION = 1


@dataclass
class Material:
    name: str
    diffuse: tuple[float, float, float] = (0.7, 0.7, 0.7)
    specular: tuple[float, float, float] = (0.5, 0.5, 0.5)
    shininess: float = 32.0
    texture: Path | None = None


@dataclass
class SubMesh:
    material: Material
    vertices: np.ndarray  # (n, 8) float32


@dataclass
class MeshData:
    submeshes: list[SubMesh] = field(default_factory=list)

    @property
    def vertex_count(self) -> int:
        return sum(len(s.vertices) for s in self.submeshes)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        positions = np.concatenate([s.vertices[:, :3] for s in self.submeshes])
        return positions.min(axis=0), positions.max(axis=0)


def parse_mtl(path: Path) -> dict[str, Material]:
    materials: dict[str, Material] = {}
    current: Material | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        keyword, _, rest = line.partition(" ")
        rest = rest.strip()
        if keyword == "newmtl":
            current = materials[rest] = Material(rest)
        elif current is None:
            continue
        elif keyword == "Kd":
            current.diffuse = _vec3(rest)
        elif keyword == "Ks":
            current.specular = _vec3(rest)
        elif keyword == "Ns":
            current.shininess = max(float(rest), 1.0)
        elif keyword == "map_Kd":
            # Texture names may contain spaces ("maroon fence texture.jpg").
            texture = path.parent / rest
            if texture.is_file():
                current.texture = texture
            else:
                log.warning("%s: texture %r not found", path.name, rest)
    return materials


def parse_obj(path: Path) -> MeshData:
    """Parse an OBJ file and its material library into per-material submeshes."""
    positions: list[list[float]] = []
    uvs: list[list[float]] = []
    normals: list[list[float]] = []
    materials: dict[str, Material] = {}
    corners: dict[str, list[tuple[int, int, int]]] = {}
    current = ""

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = raw.split()
        if not parts:
            continue
        keyword = parts[0]
        if keyword == "v":
            positions.append([float(p) for p in parts[1:4]])
        elif keyword == "vt":
            uvs.append([float(p) for p in parts[1:3]])
        elif keyword == "vn":
            normals.append([float(p) for p in parts[1:4]])
        elif keyword == "f":
            face = [_corner(token, len(positions), len(uvs), len(normals)) for token in parts[1:]]
            bucket = corners.setdefault(current, [])
            for i in range(1, len(face) - 1):  # fan-triangulate polygons
                bucket.extend((face[0], face[i], face[i + 1]))
        elif keyword == "usemtl":
            current = raw.split(maxsplit=1)[1].strip() if len(parts) > 1 else ""
        elif keyword == "mtllib":
            library = path.parent / raw.split(maxsplit=1)[1].strip()
            if library.is_file():
                materials.update(parse_mtl(library))
            else:
                log.warning("%s: material library %s not found", path.name, library.name)

    pos = np.asarray(positions, dtype=np.float32).reshape(-1, 3)
    uv = np.asarray(uvs, dtype=np.float32).reshape(-1, 2)
    nrm = np.asarray(normals, dtype=np.float32).reshape(-1, 3)

    mesh = MeshData()
    for name, bucket in corners.items():
        if not bucket:
            continue
        material = materials.get(name) or Material(name or "default")
        mesh.submeshes.append(SubMesh(material, _build_vertices(bucket, pos, uv, nrm)))
    return mesh


def load_obj(path: Path, cache_dir: Path | None = None) -> MeshData:
    """Load an OBJ file, reusing a cached parse when the source files are unchanged."""
    path = Path(path).resolve()
    cache_dir = cache_dir or default_cache_dir()
    cache_file = cache_dir / f"{path.stem}-{_source_fingerprint(path)}.pickle"
    if cache_file.is_file():
        try:
            with cache_file.open("rb") as fh:
                return pickle.load(fh)
        except (OSError, pickle.UnpicklingError, EOFError, AttributeError):
            log.warning("ignoring unreadable model cache %s", cache_file)

    mesh = parse_obj(path)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with cache_file.open("wb") as fh:
            pickle.dump(mesh, fh, protocol=pickle.HIGHEST_PROTOCOL)
    except OSError:
        log.warning("could not write model cache %s", cache_file)
    return mesh


def default_cache_dir() -> Path:
    return Path(os.environ.get("ROBOCON_CACHE", Path.home() / ".cache" / "robocon"))


def _source_fingerprint(path: Path) -> str:
    digest = hashlib.sha1(f"v{_CACHE_VERSION}:{path}".encode())
    for source in [path, *sorted(path.parent.glob("*.mtl"))]:
        stat = source.stat()
        digest.update(f"{source.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    return digest.hexdigest()[:16]


def _corner(token: str, n_pos: int, n_uv: int, n_nrm: int) -> tuple[int, int, int]:
    """Convert an OBJ face token (``v``, ``v/vt``, ``v//vn``, ``v/vt/vn``) to 0-based indices.

    Missing components are returned as -1. Negative (relative) indices are supported.
    """
    fields = token.split("/")
    counts = (n_pos, n_uv, n_nrm)
    result = [-1, -1, -1]
    for i, value in enumerate(fields[:3]):
        if value:
            index = int(value)
            result[i] = index - 1 if index > 0 else counts[i] + index
    return result[0], result[1], result[2]


def _build_vertices(
    bucket: list[tuple[int, int, int]], pos: np.ndarray, uv: np.ndarray, nrm: np.ndarray
) -> np.ndarray:
    idx = np.asarray(bucket, dtype=np.int64)
    out = np.zeros((len(idx), FLOATS_PER_VERTEX), dtype=np.float32)
    out[:, 0:3] = pos[idx[:, 0]]

    has_uv = idx[:, 1] >= 0
    if has_uv.any():
        out[has_uv, 6:8] = uv[idx[has_uv, 1]]

    has_normal = idx[:, 2] >= 0
    if has_normal.any():
        out[has_normal, 3:6] = nrm[idx[has_normal, 2]]
    if not has_normal.all():
        # Fill missing normals with the flat face normal instead of crashing or leaving zeros.
        tri = out[:, 0:3].reshape(-1, 3, 3)
        face_normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        length = np.linalg.norm(face_normal, axis=1, keepdims=True)
        face_normal = np.divide(
            face_normal, length, out=np.zeros_like(face_normal), where=length > 0
        )
        flat = np.repeat(face_normal, 3, axis=0)
        out[~has_normal, 3:6] = flat[~has_normal]
    return out


def _vec3(text: str) -> tuple[float, float, float]:
    values = [float(v) for v in text.split()[:3]]
    while len(values) < 3:
        values.append(values[-1] if values else 0.0)
    return values[0], values[1], values[2]
