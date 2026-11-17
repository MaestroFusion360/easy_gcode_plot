"""Validated MiniCAD exchange bundle; no changes to the CNC kernel."""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from app.gcode.stock import TurningStockSpec
from app.tools.definitions import DEFAULT_MILLING_TOOL
from app.tools.milling_geometry import strict_bundle_geometry
from app.tools.validation import normalized_tools


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
    version: int = 1
    tools: dict | None = None
    dialect: str = "fanuc_mill"
    turning_stock: tuple[float, float, float, float] | None = None


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
    data = json.loads(manifest.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
    json.dumps(data, allow_nan=False)
    if (
        isinstance(data, dict)
        and isinstance(data.get("version"), int)
        and not isinstance(data.get("version"), bool)
        and data["version"] == 2
    ):
        return _read_v2(manifest, data)
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
    if bundle.dialect == "fanuc_turn":
        outer, inner, length, front = bundle.turning_stock
        window.turnStockDiameter, window.turnStockInnerDiameter = outer, inner
        window.turnStockLength, window.turnStockFrontZ = length, front
        window.stockEnabled = window.stockConfigured = True
        window.tools = deepcopy(bundle.tools)
        window.program_tool_inference = {}
        window._simulation_bundle_version = 2  # pylint: disable=protected-access
        window._simulation_bundle_path = bundle.manifest  # pylint: disable=protected-access
        return
    stock = bundle.bounds
    ox, oy, oz = bundle.origin
    window.millingStockManual = True
    for attr, value in zip(
        ("XMinus", "XPlus", "YMinus", "YPlus", "ZMinus", "ZPlus"),
        (stock[0] - ox, stock[1] - ox, stock[2] - oy, stock[3] - oy, stock[4] - oz, stock[5] - oz),
    ):
        setattr(window, "millingStock" + attr, value)
    if getattr(bundle, "version", 1) == 2:
        window.millingTools = deepcopy(bundle.tools)
        window.program_tool_inference = {}
        # Bundle coordinates are program-local; no persisted machine offsets may move them.
        window._simulation_bundle_version = 2  # pylint: disable=protected-access
    else:
        window._simulation_bundle_version = 1  # pylint: disable=protected-access
        window.millingTools[f"T{bundle.tool_number}"] = {
            **DEFAULT_MILLING_TOOL,
            "diameter": bundle.tool_diameter,
            "type": bundle.tool_type,
        }
    window._simulation_bundle_path = getattr(bundle, "manifest", None)  # pylint: disable=protected-access
    if import_reference and bundle.stl is not None:
        window.importStl(str(bundle.stl))


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate bundle field: {key}")
        result[key] = value
    return result


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("Bundle coordinates must be finite numbers")
    return float(value)


def _turning_tool_geometry(key, record):
    for field in ("diameter", "length", "insertLength", "width", "noseRadius", "threadCornerRadius"):
        if field in record and _finite_number(record[field]) < (
            0 if field in ("noseRadius", "threadCornerRadius") else 1e-9
        ):
            raise ValueError(f"Invalid turning tool geometry: {field}")
    normalized = normalized_tools({key: record})
    if len(normalized) != 1:
        raise ValueError("Invalid turning tool geometry")
    return next(iter(normalized.values()))


def _v2_tools(records, *, turning=False):
    if not isinstance(records, list) or not records:
        raise ValueError("Missing bundle tool table")
    tools = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid bundle tool record")
        for key, minimum in (("number", 1), ("h", 0), ("d", 0)):
            value = record.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 9999:
                raise ValueError(f"Invalid bundle register: {key}")
        key = f"T{record['number']:04d}" if turning else f"T{record['number']}"
        if key in tools or not isinstance(record.get("name"), str) or not record["name"].strip():
            raise ValueError("Invalid or duplicate bundle tool identity")
        geometry = _turning_tool_geometry(key, record) if turning else strict_bundle_geometry(record)
        tools[key] = {**geometry, "description": record["name"], "h": record["h"], "d": record["d"]}
    return tools


def _verify_v2_files(manifest, data):
    files = {"nc": _bundle_file_path(manifest, data, "nc", ".nc")}
    if "stl" in data:
        files["stl"] = _bundle_file_path(manifest, data, "stl", ".stl")
    hashes = data.get("sha256")
    if not isinstance(hashes, dict) or set(hashes) != {p.name for p in files.values()}:
        raise ValueError("Missing bundle file integrity records")
    for path in files.values():
        if hashes[path.name] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError(f"Bundle integrity check failed: {path.name}")
    return files


def _verify_v2_nc(nc, tools, wcs, *, turning=False):
    source = nc.read_text(encoding="ascii")
    source = re.sub(r"\([^)]*\)|;[^\n]*", "", source)
    words = re.findall(r"([A-Za-z])([+-]?\d+(?:\.\d*)?)", source)
    numbers = {
        f"T{int(value):04d}" if turning else f"T{int(value)}" for letter, value in words if letter.upper() == "T"
    }
    codes = {float(value) for letter, value in words if letter.upper() == "G"}
    if numbers != tools.keys():
        raise ValueError("Bundle tool table does not match NC tool changes")
    if 21 not in codes or 20 in codes or codes & set(range(54, 60)) != {int(wcs[1:])}:
        raise ValueError("Bundle NC must use G21 and the declared WCS")


def _turning_stock(data, bounds, nc):
    if "stl" in data or not isinstance(data.get("turningStock"), dict):
        raise ValueError("Turning bundle requires a cylinder, not stock STL")
    stock_spec = data["turningStock"]
    cylinder = tuple(
        _finite_number(stock_spec.get(key)) for key in ("outerDiameter", "innerDiameter", "length", "frontZ")
    )
    outer, inner, length, front = cylinder
    TurningStockSpec(outer_diameter=outer, inner_diameter=inner, length=length, front_z=front).validate()
    expected = (-outer / 2, outer / 2, -outer / 2, outer / 2, front - length, front)
    if bounds != expected:
        raise ValueError("Turning cylinder and stock envelope differ")
    source = nc.read_text(encoding="ascii")
    source = re.sub(r"\([^)]*\)|;[^\n]*", "", source)
    codes = {float(value) for value in re.findall(r"[Gg]([+-]?\d+(?:\.\d*)?)", source)}
    if 18 not in codes or 17 in codes:
        raise ValueError("Turning bundle requires G18 NC")
    return cylinder


def _read_v2(manifest, data):
    if data.get("units") != "mm" or data.get("dialect") not in ("fanuc_mill", "fanuc_turn"):
        raise ValueError("Bundle v2 requires millimetres and Fanuc Mill or Turn")
    turning = data["dialect"] == "fanuc_turn"
    tools = _v2_tools(data.get("tools"), turning=turning)
    stock, coords = data.get("stock"), data.get("coordinates")
    if not isinstance(stock, dict) or not isinstance(coords, dict):
        raise ValueError("Missing bundle stock or coordinates")
    if (
        not {"xmin", "xmax", "ymin", "ymax", "zmin", "zmax"} <= stock.keys()
        or not {"wcs", "x", "y", "z"} <= coords.keys()
    ):
        raise ValueError("Incomplete bundle stock or coordinates")
    bounds = tuple(_finite_number(stock[key]) for key in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"))
    if any(bounds[i] >= bounds[i + 1] for i in (0, 2, 4)):
        raise ValueError("Invalid stock bounds")
    origin = tuple(_finite_number(coords[key]) for key in ("x", "y", "z"))
    if any(origin):
        raise ValueError("Simulation bundle v2 requires a zero work origin")
    wcs = coords.get("wcs")
    if wcs not in {f"G{i}" for i in range(54, 60)}:
        raise ValueError("Invalid bundle WCS")
    files = _verify_v2_files(manifest, data)
    _verify_v2_nc(files["nc"], tools, wcs, turning=turning)
    cylinder = _turning_stock(data, bounds, files["nc"]) if turning else None
    first_key = next(iter(tools))
    number = int(first_key[1:])
    tool = tools[first_key]
    return MiniCadBundle(
        files["nc"],
        files.get("stl"),
        bounds,
        number,
        tool.get("diameter", 0.0),
        tool["type"],
        wcs,
        origin,
        manifest,
        2,
        tools,
        data["dialect"],
        cylinder,
    )
