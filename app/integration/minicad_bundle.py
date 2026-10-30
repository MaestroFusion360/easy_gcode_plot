"""Validated MiniCAD exchange bundle; no changes to the CNC kernel."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from app.tools.definitions import DEFAULT_MILLING_TOOL


@dataclass(frozen=True)
class MiniCadBundle:
    nc: Path
    stl: Path | None
    bounds: tuple[float, float, float, float, float, float]
    tool_number: int
    tool_diameter: float
    tool_type: str
    wcs: str
    origin: tuple[float, float, float]
    manifest: Path | None = None


def _bundle_file_path(manifest: Path, data: dict, key: str, suffix: str) -> Path:
    name = data.get(key)
    if not isinstance(name, str) or Path(name).name != name or not name:
        raise ValueError(f"Invalid bundle file name: {key}")
    result = (manifest.parent / name).resolve(strict=True)
    if result.parent != manifest.parent or result.suffix.lower() != suffix or not result.is_file():
        raise ValueError(f"Invalid bundle file: {key}")
    return result


def read_bundle(path: str | Path) -> MiniCadBundle:
    """Read only local, explicitly named files from a versioned bundle."""
    manifest = Path(path).expanduser().resolve(strict=True)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported MiniCAD simulation bundle version")
    if data.get("units") != "mm":
        raise ValueError("MiniCAD simulation bundle must use millimetres")

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
        _bundle_file_path(manifest, data, "nc", ".nc"),
        _bundle_file_path(manifest, data, "stl", ".stl") if "stl" in data else None,
        bounds,
        number,
        diameter,
        str(tool.get("type", "mill_flat")),
        wcs,
        origin,
        manifest,
    )


def apply_bundle(window, bundle, *, import_reference=False):
    """Apply exchange stock and tool to the active program, including disk reloads."""
    stock = bundle.bounds
    ox, oy, oz = bundle.origin
    window.millingStockManual = True
    for attr, value in zip(
        ("XMinus", "XPlus", "YMinus", "YPlus", "ZMinus", "ZPlus"),
        (stock[0] - ox, stock[1] - ox, stock[2] - oy, stock[3] - oy, stock[4] - oz, stock[5] - oz),
    ):
        setattr(window, "millingStock" + attr, value)
    window.millingTools[f"T{bundle.tool_number}"] = {
        **DEFAULT_MILLING_TOOL,
        "diameter": bundle.tool_diameter,
        "type": bundle.tool_type,
    }
    window._simulation_bundle_path = getattr(bundle, "manifest", None)  # pylint: disable=protected-access
    if import_reference and bundle.stl is not None:
        window.importStl(str(bundle.stl))
