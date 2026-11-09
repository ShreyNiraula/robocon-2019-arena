"""End-to-end render check. Skipped where no OpenGL 3.3 context can be created (e.g. plain CI)."""

from pathlib import Path

import moderngl
import pytest
from PIL import Image

from robocon.capture import Shot, capture


@pytest.fixture(scope="module", autouse=True)
def require_opengl() -> None:
    try:
        moderngl.create_standalone_context(require=330).release()
    except Exception as error:  # noqa: BLE001 - any backend failure means "no GPU here"
        pytest.skip(f"no OpenGL 3.3 context available: {error}")


def test_every_mode_renders_something(tmp_path: Path) -> None:
    shots = [Shot(f"mode{key}.png", mode=key, seconds=1.0) for key in (1, 2, 3, 4, 5)]
    for path in capture(tmp_path, shots, size=(160, 90)):
        with Image.open(path) as image:
            _, lightest = image.convert("L").getextrema()
        assert lightest > 40, f"{path.name} is blank"
