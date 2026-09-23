"""FANUC-style 3-axis milling resolver producing logical trace motions."""

import sys

from .cycles import drilling as _drilling
from .executor import execute_milling
from .state import MillState

__all__ = ["MillState", "execute_milling"]

# Historical path retained while ``milling.cycles`` is the canonical home.
sys.modules.setdefault(f"{__name__}.drilling", _drilling)
