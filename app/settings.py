"""Per-user application settings stored outside the program directory."""

import json
import logging
import math
import os
import shutil
import sys
from pathlib import Path

from PyQt6.QtCore import QSettings, QStandardPaths

_APP_DIR = "easy-gcode-plot"
_LOG_HANDLER_MARKER = "_easy_gcode_plot_handler"
_LOG_PREVIOUS_LEVEL_MARKER = "_easy_gcode_plot_previous_level"
_LOG_PREVIOUS_PROPAGATE_MARKER = "_easy_gcode_plot_previous_propagate"
LOGGER = logging.getLogger(__name__)


def _config_dir() -> str:
    """Return the per-user config directory (``%APPDATA%\\easy-gcode-plot``)."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation)
    path = os.path.join(base, _APP_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def config_path() -> str:
    """Return the absolute path of the ini file used to store settings."""
    return os.path.join(_config_dir(), "config.ini")


def log_path() -> str:
    """Return the per-user application log path."""
    return os.path.join(_config_dir(), "main.log")


def configure_logging(enabled: bool) -> None:
    """Enable or disable the project-owned file handler without muting third-party logging."""
    project_logger = logging.getLogger("app")
    handlers = [handler for handler in project_logger.handlers if getattr(handler, _LOG_HANDLER_MARKER, False)]
    if enabled:
        if not handlers:
            handler = logging.FileHandler(log_path(), encoding="utf-8")
            setattr(handler, _LOG_HANDLER_MARKER, True)
            setattr(handler, _LOG_PREVIOUS_LEVEL_MARKER, project_logger.level)
            setattr(handler, _LOG_PREVIOUS_PROPAGATE_MARKER, project_logger.propagate)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            handler.setLevel(logging.DEBUG)
            project_logger.addHandler(handler)
        project_logger.setLevel(logging.DEBUG)
        project_logger.propagate = False
        return
    previous_level = getattr(handlers[0], _LOG_PREVIOUS_LEVEL_MARKER, None) if handlers else None
    previous_propagate = getattr(handlers[0], _LOG_PREVIOUS_PROPAGATE_MARKER, None) if handlers else None
    for handler in handlers:
        project_logger.removeHandler(handler)
        handler.close()
    if previous_level is not None:
        project_logger.setLevel(previous_level)
    if previous_propagate is not None:
        project_logger.propagate = previous_propagate


def _application_dir() -> str:
    """Return the stable application directory without depending on process CWD."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return str(Path(__file__).resolve().parent.parent)


def _migrate_legacy_config() -> None:
    """Copy a legacy ``config.ini`` next to the application on first run."""
    target = config_path()
    if os.path.exists(target):
        return
    legacy = os.path.join(_application_dir(), "config.ini")
    if os.path.exists(legacy):
        try:
            shutil.copy2(legacy, target)
        except OSError:
            LOGGER.warning("legacy_config_migration_failed source=%s target=%s", legacy, target, exc_info=True)


def get_settings() -> QSettings:
    """Return a QSettings instance bound to the per-user config.ini file."""
    _migrate_legacy_config()
    return QSettings(config_path(), QSettings.Format.IniFormat)


RECENT_FILES_LIMIT = 5


def normalized_tools(raw):
    """Return validated turning tool definitions from a QSettings JSON value."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    if not isinstance(raw, dict):
        return {}

    tools = {}
    for raw_key, raw_spec in raw.items():
        if not isinstance(raw_spec, dict):
            continue
        key = str(raw_key).strip().upper()
        digits = key[1:] if key.startswith("T") else key
        if not digits.isdigit() or not 1 <= len(digits) <= 4:
            continue
        key = f"T{int(digits):04d}"

        tool_type = str(raw_spec.get("type", "turning")).strip().lower()
        if tool_type not in {"turning", "drill"}:
            continue
        spec = {"type": tool_type}

        description = raw_spec.get("description")
        if isinstance(description, str) and description.strip():
            spec["description"] = " ".join(description.split())

        if tool_type == "turning":
            try:
                radius = float(raw_spec.get("noseRadius", 0.0))
                orientation = int(raw_spec.get("tipOrientation", 0))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(radius) or radius <= 0.0 or orientation not in range(1, 10):
                continue
            spec["noseRadius"] = radius
            spec["tipOrientation"] = orientation

        tools[key] = spec
    return tools


def normalized_milling_tools(raw):
    """Return validated milling tool geometry from a QSettings JSON value."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    if not isinstance(raw, dict):
        return {}

    tools = {}
    valid_types = {"mill_flat", "mill_bull", "mill_ball", "drill"}
    for raw_key, raw_spec in raw.items():
        if not isinstance(raw_spec, dict):
            continue
        key = str(raw_key).strip().upper()
        digits = key[1:] if key.startswith("T") else key
        if not digits.isdigit():
            continue
        tool_number = int(digits)
        if not 1 <= tool_number <= 99:
            continue
        key = f"T{tool_number}"

        tool_type = str(raw_spec.get("type", "mill_flat")).strip().lower()
        if tool_type not in valid_types:
            continue
        try:
            diameter = float(raw_spec.get("diameter", 0.0))
            length = float(raw_spec.get("length", 0.0))
            radius = max(0.0, float(raw_spec.get("cornerRadius", 0.0)))
        except (TypeError, ValueError):
            continue

        if not all(math.isfinite(value) for value in (diameter, length, radius)):
            continue
        if diameter <= 0.0 or length <= 0.0:
            continue
        if tool_type == "mill_ball":
            radius = diameter / 2.0
        elif tool_type == "mill_bull" and radius > diameter / 2.0:
            continue
        elif tool_type != "mill_bull":
            radius = 0.0

        spec = {
            "type": tool_type,
            "diameter": diameter,
            "cornerRadius": radius,
            "length": length,
        }
        description = raw_spec.get("description")
        if isinstance(description, str) and description.strip():
            spec["description"] = " ".join(description.split())
        tools[key] = spec
    return tools


def normalized_recent_files(paths, limit=RECENT_FILES_LIMIT):
    """Return a stable, case-insensitive MRU list without empty values."""
    out = []
    seen = set()
    for value in paths or []:
        path = str(value).strip()
        key = os.path.normcase(path)
        if not path or key in seen:
            continue
        out.append(path)
        seen.add(key)
        if len(out) >= limit:
            break
    return out
