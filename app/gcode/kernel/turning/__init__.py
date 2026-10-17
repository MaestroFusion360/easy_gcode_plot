"""FANUC turning-specific execution and cycle semantics."""

import sys

from ..frontend import turning_dialect as dialect
from ..frontend import turning_type_a as type_a
from ..frontend import turning_type_b as type_b
from . import cycles

__all__ = ["cycles"]

for _name, _module in {"dialect": dialect, "type_a": type_a, "type_b": type_b}.items():
    sys.modules[f"{__name__}.{_name}"] = _module
