"""Per-user application settings stored outside the program directory."""

import os
import shutil

from PyQt6.QtCore import QSettings, QStandardPaths

_APP_DIR = "easy-gcode-plot"


def _config_dir() -> str:
    """Return the per-user config directory (``%APPDATA%\\easy-gcode-plot``)."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation)
    path = os.path.join(base, _APP_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def config_path() -> str:
    """Return the absolute path of the ini file used to store settings."""
    return os.path.join(_config_dir(), "config.ini")


def _migrate_legacy_config() -> None:
    """Copy a legacy ``config.ini`` next to the launcher on first run."""
    target = config_path()
    if os.path.exists(target):
        return
    legacy = os.path.join(os.getcwd(), "config.ini")
    if os.path.exists(legacy):
        shutil.copy2(legacy, target)


def get_settings() -> QSettings:
    """Return a QSettings instance bound to the per-user config.ini file."""
    _migrate_legacy_config()
    return QSettings(config_path(), QSettings.Format.IniFormat)
