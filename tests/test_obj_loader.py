from pathlib import Path

import numpy as np
import pytest

from robocon.obj_loader import load_obj, parse_obj

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "models"

QUAD_OBJ = """\
mtllib quad.mtl
v 0 0 0
v 1 0 0
v 1 0 1
v 0 0 1
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vn 0 1 0
usemtl Painted
f 1/1/1 2/2/1 3/3/1 4/4/1
usemtl Missing
f -4 -2 -1
"""

QUAD_MTL = """\
newmtl Painted
Kd 1.0 0.5 0.25
Ns 10
map_Kd red texture.png
"""


@pytest.fixture
def quad(tmp_path: Path) -> Path:
    (tmp_path / "quad.obj").write_text(QUAD_OBJ)
    (tmp_path / "quad.mtl").write_text(QUAD_MTL)
    (tmp_path / "red texture.png").write_bytes(b"")
    return tmp_path / "quad.obj"


def test_quad_is_fan_triangulated_per_material(quad: Path) -> None:
    mesh = parse_obj(quad)
    painted, missing = mesh.submeshes
    assert painted.vertices.shape == (6, 8)
    assert missing.vertices.shape == (3, 8)
    assert painted.vertices.dtype == np.float32


def test_material_properties_and_texture_with_spaces(quad: Path) -> None:
    painted = parse_obj(quad).submeshes[0].material
    assert painted.diffuse == (1.0, 0.5, 0.25)
    assert painted.shininess == 10
    assert painted.texture is not None and painted.texture.name == "red texture.png"


def test_unknown_material_falls_back_to_default(quad: Path) -> None:
    missing = parse_obj(quad).submeshes[1].material
    assert missing.name == "Missing"
    assert missing.texture is None


def test_missing_normals_are_computed_from_the_face(quad: Path) -> None:
    # "f -4 -2 -1" has no normals: the flat normal of that triangle points down -y.
    normals = parse_obj(quad).submeshes[1].vertices[:, 3:6]
    np.testing.assert_allclose(normals, [[0, -1, 0]] * 3, atol=1e-6)


def test_negative_indices_resolve_relative_to_the_end(quad: Path) -> None:
    positions = parse_obj(quad).submeshes[1].vertices[:, 0:3]
    np.testing.assert_allclose(positions, [[0, 0, 0], [1, 0, 1], [0, 0, 1]])


def test_cache_round_trip(quad: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    first = load_obj(quad, cache_dir=cache)
    assert len(list(cache.iterdir())) == 1
    second = load_obj(quad, cache_dir=cache)
    np.testing.assert_array_equal(first.submeshes[0].vertices, second.submeshes[0].vertices)


@pytest.mark.parametrize(
    "relative",
    ["arena/arena.obj", "robot/TeamARobot.obj", "spider/TeamBSpider.obj"],
)
def test_project_models_load_with_textures(relative: str, tmp_path: Path) -> None:
    mesh = load_obj(ASSETS / relative, cache_dir=tmp_path)
    assert mesh.vertex_count > 0
    assert all(s.material.texture is not None for s in mesh.submeshes)
