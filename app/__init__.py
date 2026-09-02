"""Easy G-code Plot application package."""

import tomllib
from importlib import metadata
from pathlib import Path


def get_version() -> str:
    """Return the application version, taken from ``pyproject.toml``.

    When the project is installed as a distribution the version comes from
    package metadata; otherwise it is read directly from the source file.
    """
    try:
        return metadata.version("easy-gcode-plot")
    except metadata.PackageNotFoundError:
        pass

    project_root = Path(__file__).resolve().parent.parent
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
        return data["project"]["version"]

    return "unknown"
