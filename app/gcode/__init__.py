"""G-code domain package: kernel execution, trace tools and exporters.

The historical flat exporter module paths are registered as lazy in-process
aliases so ``app.gcode.exporter`` and ``app.gcode.dxf_exporter`` keep resolving
without compatibility files at the package root.
"""

from __future__ import annotations

import importlib
import sys
import types

_LAZY_ALIASES = {
    "exporter": "app.gcode.export",
    "dxf_exporter": "app.gcode.export.dxf",
}


class _LazyAlias(types.ModuleType):
    """Import the canonical module on first attribute access."""

    def __init__(self, name: str, target: str) -> None:
        super().__init__(name)
        self.__dict__["_target"] = target

    def _load(self):
        return importlib.import_module(self.__dict__["_target"])

    def __getattr__(self, attribute: str):
        value = getattr(self._load(), attribute)
        setattr(self, attribute, value)
        return value

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(dir(self._load())))


for _alias, _target in _LAZY_ALIASES.items():
    _full = f"{__name__}.{_alias}"
    if _full not in sys.modules:
        _proxy = _LazyAlias(_full, _target)
        sys.modules[_full] = _proxy
        setattr(sys.modules[__name__], _alias, _proxy)
