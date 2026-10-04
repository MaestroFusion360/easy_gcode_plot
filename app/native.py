"""Single, cached native-extension boundary for source and packaged execution.

Loading is lazy to avoid cycles through the public kernel compatibility package.
Missing extensions are supported in source checkouts, never in frozen releases.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from threading import RLock
from types import ModuleType

MODULES = {
    "parser": "app.gcode.kernel.frontend._native_parser",
    "discovery": "app.tools._native_discovery",
    "executor": "app.gcode.kernel.milling._native_executor",
}


class NativeRuntimeError(RuntimeError):
    """A packaged release is incomplete or its native DLLs cannot load."""


@dataclass(frozen=True)
class NativeExtension:
    module: ModuleType | None
    reason: str | None


_extensions: dict[str, NativeExtension] = {}
_lock = RLock()


def extension(name: str) -> NativeExtension:
    with _lock:
        if name not in _extensions:
            try:
                module = importlib.import_module(MODULES[name])
            except (ImportError, OSError) as error:
                _extensions[name] = NativeExtension(None, f"{type(error).__name__}: {error}")
            else:
                _extensions[name] = NativeExtension(module, None)
        return _extensions[name]


def native_symbol(name: str, symbol: str):
    module = extension(name).module
    return getattr(module, symbol) if module is not None else None


def native_status() -> dict[str, dict[str, object]]:
    return {
        name: {"available": extension(name).module is not None, "reason": extension(name).reason} for name in MODULES
    }


def require_packaged_native() -> None:
    if not getattr(sys, "frozen", False):
        return
    missing = [
        f"{module} ({extension(name).reason})" for name, module in MODULES.items() if extension(name).module is None
    ]
    if missing:
        raise NativeRuntimeError("Packaged release is missing native extensions: " + "; ".join(missing))


def __getattr__(name: str):
    if name.startswith("HAS_NATIVE_"):
        key = name.removeprefix("HAS_NATIVE_").lower()
        if key in MODULES:
            return extension(key).module is not None
    raise AttributeError(name)
