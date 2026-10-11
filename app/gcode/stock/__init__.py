"""Stock simulation engines for milling and turning (physical units: mm)."""

from .milling_stock import MillingStockSpec, MillingStockTimeline, auto_milling_stock, write_milling_stock_stl
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
