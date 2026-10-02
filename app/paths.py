"""Shared per-user paths without GUI dependencies."""

import os
import sys
from pathlib import Path


def config_dir() -> str:
    """Keep the existing Qt GenericConfigLocation layout without importing Qt."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        configured = os.environ.get("XDG_CONFIG_HOME", "")
        base = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / ".config"
    directory = base / "easy-gcode-plot"
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory)
