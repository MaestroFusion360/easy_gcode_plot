"""Stock simulation engines for milling and turning (physical units: mm)."""

from .milling_stock import MillingStockTimeline, auto_milling_stock
from .milling_stock_export import write_milling_stock_stl
from .milling_stock_types import MillingStockSpec
from .turning_stock import TurningStockSpec, TurningStockTimeline, profile_interval_mesh_spans

__all__ = [
    "MillingStockSpec",
    "MillingStockTimeline",
    "auto_milling_stock",
    "write_milling_stock_stl",
    "TurningStockSpec",
    "TurningStockTimeline",
    "profile_interval_mesh_spans",
]
