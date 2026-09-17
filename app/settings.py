"""Per-user application settings stored outside the program directory."""

import logging
import math
import os
import shutil
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QSettings, QStandardPaths

from app.tools.definitions import DEFAULT_MILLING_TOOL, default_turning_library
from app.tools.library import ToolLibrary
from app.tools.validation import normalized_milling_tools, normalized_tools

_APP_DIR = "easy-gcode-plot"
_LOG_HANDLER_MARKER = "_easy_gcode_plot_handler"
_LOG_PREVIOUS_LEVEL_MARKER = "_easy_gcode_plot_previous_level"
_LOG_PREVIOUS_PROPAGATE_MARKER = "_easy_gcode_plot_previous_propagate"
LOGGER = logging.getLogger(__name__)


class ToolLibraryLoadError(RuntimeError):
    """The persistent tool library could not be read safely."""


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
ARC_TOLERANCE_MIN = 1e-6
ARC_TOLERANCE_MAX = 10.0
ARC_TOLERANCE_DEFAULT = 0.001
FONT_SIZE_MIN = 6
FONT_SIZE_MAX = 48
AUTO_UPDATE_SEGMENTS_MIN = 1000
AUTO_UPDATE_SEGMENTS_MAX = 2_147_483_647
LINE_WIDTH_MIN = 0.25
LINE_WIDTH_MAX = 6.0


def bounded_number(value, default, minimum, maximum, *, name="setting"):
    """Return a finite persisted number constrained to its domain."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        LOGGER.warning("invalid_setting name=%s value=%r default=%s", name, value, default)
        return default
    if not math.isfinite(number):
        LOGGER.warning("invalid_setting name=%s value=%r default=%s", name, value, default)
        return default
    bounded = min(max(number, minimum), maximum)
    if bounded != number:
        LOGGER.warning("clamped_setting name=%s value=%r bounded=%s", name, value, bounded)
    return bounded


_TOOL_LIBRARY_CACHE = {"library": None, "path": None}
_TOOL_LIBRARY_LOCK = threading.Lock()


def tool_library_path() -> str:
    """Return the SQLite tool-library path next to the per-user config file."""
    return str(Path(config_path()).with_name("tools.db"))


def _seed_tool_library(library) -> None:
    """Initialize a new SQLite library directly with the current tool model."""
    library.seed_defaults_once(default_turning_library(), {"T1": DEFAULT_MILLING_TOOL})


def get_tool_library():
    """Return the process-wide SQLite tool library for the current config path."""
    path = tool_library_path()
    if _TOOL_LIBRARY_CACHE["library"] is None or _TOOL_LIBRARY_CACHE["path"] != path:
        with _TOOL_LIBRARY_LOCK:
            if _TOOL_LIBRARY_CACHE["library"] is None or _TOOL_LIBRARY_CACHE["path"] != path:
                if _TOOL_LIBRARY_CACHE["library"] is not None:
                    _TOOL_LIBRARY_CACHE["library"].close()
                library = ToolLibrary(path)
                _seed_tool_library(library)
                _TOOL_LIBRARY_CACHE["library"] = library
                _TOOL_LIBRARY_CACHE["path"] = path
    return _TOOL_LIBRARY_CACHE["library"]


def load_turning_tools() -> dict[str, dict]:
    """Load a normalized view without modifying stored or unknown records."""
    try:
        library = get_tool_library()
        stored = library.tools_by_kind("turning")
        return normalized_tools(stored)
    except Exception:
        LOGGER.warning("tool_library_load_failed kind=turning", exc_info=True)
        return {}


def load_milling_tools() -> dict[str, dict]:
    """Load normalized milling tools from the SQLite library."""
    try:
        return normalized_milling_tools(get_tool_library().tools_by_kind("milling"))
    except Exception:
        LOGGER.warning("tool_library_load_failed kind=milling", exc_info=True)
        return {}


def load_tool_libraries() -> tuple[dict[str, dict], dict[str, dict]]:
    """Load both tool kinds or fail without presenting partial data as empty."""
    path = "tools.db"
    try:
        path = tool_library_path()
        library = get_tool_library()
        turning = normalized_tools(library.tools_by_kind("turning"))
        milling = normalized_milling_tools(library.tools_by_kind("milling"))
        return turning, milling
    except Exception as exc:
        LOGGER.warning("tool_library_load_failed path=%s", path, exc_info=True)
        raise ToolLibraryLoadError(
            f"Could not read the tool library:\n{path}\n\n"
            "Tool Library has been disabled to protect the existing database."
        ) from exc


def save_turning_tools(tools: dict[str, dict]) -> bool:
    """Persist the complete normalized turning-tool set atomically."""
    try:
        get_tool_library().sync_kind("turning", normalized_tools(tools))
        return True
    except Exception:
        LOGGER.warning("tool_library_save_failed kind=turning", exc_info=True)
        return False


def save_library_edits(kind, original, edited):
    """Persist only explicit library edits; automatic setup never calls this."""
    normalize = normalized_tools if kind == "turning" else normalized_milling_tools
    try:
        get_tool_library().apply_edits(kind, original, normalize(edited))
        return True
    except Exception:
        LOGGER.warning("tool_library_edit_failed kind=%s", kind, exc_info=True)
        return False


def save_library_changes(originals, edited):
    """Persist all changed tool kinds in one SQLite transaction."""
    changes = {}
    for kind in ("milling", "turning"):
        normalize = normalized_tools if kind == "turning" else normalized_milling_tools
        if edited[kind] != originals[kind]:
            changes[kind] = (originals[kind], normalize(edited[kind]))
    if not changes:
        return True
    try:
        get_tool_library().apply_edits_by_kind(changes)
        return True
    except Exception:
        LOGGER.warning("tool_library_transaction_failed", exc_info=True)
        return False


def save_milling_tools(tools: dict[str, dict]) -> bool:
    """Persist the complete normalized milling-tool set atomically."""
    try:
        get_tool_library().sync_kind("milling", normalized_milling_tools(tools))
        return True
    except Exception:
        LOGGER.warning("tool_library_save_failed kind=milling", exc_info=True)
        return False


def normalized_recent_files(paths, limit=RECENT_FILES_LIMIT):
    """Return a stable, case-insensitive MRU list without empty values."""
    out = []
    seen = set()
    for value in paths or []:
        path = str(value).strip()
        # Recent documents may contain Windows paths even when settings are
        # inspected or migrated on Linux. os.path.normcase() is a no-op there,
        # so normalize separators and case explicitly for stable behavior.
        key = path.replace("\\", "/").casefold()
        if not path or key in seen:
            continue
        out.append(path)
        seen.add(key)
        if len(out) >= limit:
            break
    return out
