"""Validated MiniCAD exchange bundle; no changes to the CNC kernel."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MiniCadBundle:
    nc: Path
    stl: Path
    bounds: tuple[float, float, float, float, float, float]
    tool_number: int
    tool_diameter: float
    tool_type: str
    wcs: str
    origin: tuple[float, float, float]


def read_bundle(path: str | Path) -> MiniCadBundle:
    """Read only local, explicitly named files from a versioned bundle."""
    manifest = Path(path).expanduser().resolve(strict=True)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported MiniCAD simulation bundle version")
    if data.get("units") != "mm":
        raise ValueError("MiniCAD simulation bundle must use millimetres")

    def file_path(key: str, suffix: str) -> Path:
        name = data.get(key)
        if not isinstance(name, str) or Path(name).name != name or not name:
            raise ValueError(f"Invalid bundle file name: {key}")
        result = (manifest.parent / name).resolve(strict=True)
        if result.parent != manifest.parent or result.suffix.lower() != suffix or not result.is_file():
            raise ValueError(f"Invalid bundle file: {key}")
        return result

    stock = data.get("stock")
    tool = data.get("tool")
    coords = data.get("coordinates")
    if not all(isinstance(v, dict) for v in (stock, tool, coords)):
        raise ValueError("Missing stock, tool or coordinates")
    names = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    bounds = tuple(float(stock[name]) for name in names)
    if not all(math.isfinite(x) for x in bounds) or any(bounds[i] >= bounds[i + 1] for i in (0, 2, 4)):
        raise ValueError("Invalid stock bounds")
    number = int(tool["number"])
    diameter = float(tool["diameter"])
    if number < 0 or not math.isfinite(diameter) or diameter <= 0:
        raise ValueError("Invalid tool")
    origin = tuple(float(coords[axis]) for axis in ("x", "y", "z"))
    if not all(math.isfinite(x) for x in origin):
        raise ValueError("Invalid coordinate offset")
    wcs = str(coords.get("wcs", "G54"))
    if wcs not in {f"G{i}" for i in range(54, 60)}:
        raise ValueError("Invalid WCS")
    return MiniCadBundle(
        file_path("nc", ".nc"),
        file_path("stl", ".stl"),
        bounds,
        number,
        diameter,
        str(tool.get("type", "mill_flat")),
        wcs,
        origin,
    )
