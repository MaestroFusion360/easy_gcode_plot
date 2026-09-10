"""Easy G-code Plot application package."""

import tomllib
from importlib import metadata
from pathlib import Path


def get_version() -> str:
    """Return the application version from the project or installed package.

    The source tree uses ``pyproject.toml`` as the canonical version. Packaged
    builds, where that file is unavailable, use installed distribution metadata.
    """
    project_root = Path(__file__).resolve().parent.parent
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
        return data["project"]["version"]

    try:
        return metadata.version("easy-gcode-plot")
    except metadata.PackageNotFoundError:
        return "unknown"
