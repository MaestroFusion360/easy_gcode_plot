"""Shared axial geometry for milling tool previews."""

from __future__ import annotations

import math

SUPPORTED_MILLING_GEOMETRIES = frozenset(
    {"mill_flat", "mill_bull", "mill_ball", "face_mill", "slot_mill", "chamfer_mill", "drill", "tap"}
)


def default_cutting_height(tool_type: str, diameter: float, length: float) -> float:
    """Return a backward-compatible visible head height for stepped cutters."""
    factor = 0.28 if tool_type == "face_mill" else 0.38
    return max(0.1, min(length * 0.6, max(2.0, diameter * factor)))


def default_shank_diameter(diameter: float) -> float:
    """Return a visibly smaller shank diameter for stepped cutters."""
    return max(0.1, diameter * 0.6)


def default_tip_diameter(diameter: float) -> float:
    """Return a small but non-zero flat tip for chamfer mills."""
    return max(0.1, min(diameter * 0.2, diameter * 0.8))


def default_drill_tip_angle() -> float:
    """Return the same drill point-angle default used by the turning library."""
    return 118.0


def milling_geometry(  # pylint: disable=too-many-return-statements
    spec: dict[str, object] | None,
) -> dict[str, float | str] | None:
    """Normalize the geometry fields needed by both 2D and 3D previews."""
    if not isinstance(spec, dict):
        return None
    tool_type = str(spec.get("type", "")).strip().lower()
    if tool_type not in SUPPORTED_MILLING_GEOMETRIES:
        return None
    try:
        diameter = float(spec.get("diameter", 0.0))
        length = float(spec.get("length", 0.0))
        corner_radius = float(spec.get("cornerRadius", 0.0))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (diameter, length, corner_radius)):
        return None
    if diameter <= 0.0 or length <= 0.0:
        return None

    radius = diameter * 0.5
    if tool_type == "mill_ball":
        corner_radius = radius
    elif tool_type == "mill_bull":
        corner_radius = min(max(corner_radius, 0.0), radius)
    else:
        corner_radius = 0.0

    result: dict[str, float | str] = {
        "type": tool_type,
        "diameter": diameter,
        "length": length,
        "cornerRadius": corner_radius,
    }

    if tool_type in {"face_mill", "slot_mill"}:
        try:
            cutting_height = float(spec.get("cuttingHeight", default_cutting_height(tool_type, diameter, length)))
            shank_diameter = float(spec.get("shankDiameter", default_shank_diameter(diameter)))
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in (cutting_height, shank_diameter)):
            return None
        cutting_height = min(max(cutting_height, 0.1), length)
        shank_diameter = min(max(shank_diameter, 0.1), diameter)
        result.update(cuttingHeight=cutting_height, shankDiameter=shank_diameter)

    if tool_type == "chamfer_mill":
        try:
            tip_diameter = float(spec.get("tipDiameter", default_tip_diameter(diameter)))
            chamfer_angle = float(spec.get("chamferAngle", 90.0))
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in (tip_diameter, chamfer_angle)):
            return None
        tip_diameter = min(max(tip_diameter, 0.0), diameter)
        chamfer_angle = min(max(chamfer_angle, 1.0), 179.0)
        result.update(tipDiameter=tip_diameter, chamferAngle=chamfer_angle)

    if tool_type == "drill":
        try:
            tip_angle = float(spec.get("tipAngle", default_drill_tip_angle()))
        except (TypeError, ValueError):
            return None
        if not math.isfinite(tip_angle):
            return None
        result["tipAngle"] = min(max(tip_angle, 1.0), 179.0)

    return result


def milling_geometry_key(spec: dict[str, object] | None) -> tuple | None:
    """Return an immutable signature for cached preview geometry."""
    geometry = milling_geometry(spec)
    if geometry is None:
        return None
    tool_type = str(geometry["type"])
    key = [
        tool_type,
        float(geometry["diameter"]),
        float(geometry["length"]),
        float(geometry["cornerRadius"]),
    ]
    if tool_type in {"face_mill", "slot_mill"}:
        key.extend((float(geometry["cuttingHeight"]), float(geometry["shankDiameter"])))
    elif tool_type == "chamfer_mill":
        key.extend((float(geometry["tipDiameter"]), float(geometry["chamferAngle"])))
    elif tool_type == "drill":
        key.append(float(geometry["tipAngle"]))
    return tuple(key)


def milling_tool_profile(  # pylint: disable=too-many-return-statements
    spec: dict[str, object] | None,
) -> tuple[tuple[float, float], ...]:
    """Return a radial ``(z, radius)`` profile with the programmed tip at ``z=0``."""
    geometry = milling_geometry(spec)
    if geometry is None:
        return ()

    tool_type = str(geometry["type"])
    diameter = float(geometry["diameter"])
    length = float(geometry["length"])
    corner_radius = float(geometry["cornerRadius"])
    radius = diameter * 0.5

    if tool_type == "drill":
        half_angle = math.radians(float(geometry["tipAngle"]) * 0.5)
        cone_height = min(length, radius / max(math.tan(half_angle), 1.0e-9))
        return ((0.0, 0.0), (cone_height, radius), (length, radius))

    if tool_type == "tap":
        cone_height = min(length, radius / math.sqrt(3.0))
        return ((0.0, 0.0), (cone_height, radius), (length, radius))

    if tool_type == "chamfer_mill":
        tip_radius = float(geometry["tipDiameter"]) * 0.5
        half_angle = math.radians(float(geometry["chamferAngle"]) * 0.5)
        cone_height = (radius - tip_radius) / max(math.tan(half_angle), 1.0e-9)
        cone_height = min(max(cone_height, 0.0), length)
        return ((0.0, tip_radius), (cone_height, radius), (length, radius))

    if tool_type == "face_mill":
        cutting_height = float(geometry["cuttingHeight"])
        shank_radius = float(geometry["shankDiameter"]) * 0.5
        edge = min(max(diameter * 0.04, 0.25), radius * 0.25, cutting_height)
        face_radius = max(0.0, radius - edge)
        return (
            (0.0, face_radius),
            (edge, radius),
            (cutting_height, radius),
            (cutting_height, shank_radius),
            (length, shank_radius),
        )

    if tool_type == "slot_mill":
        cutting_height = float(geometry["cuttingHeight"])
        shank_radius = float(geometry["shankDiameter"]) * 0.5
        return (
            (0.0, radius),
            (cutting_height, radius),
            (cutting_height, shank_radius),
            (length, shank_radius),
        )

    if tool_type == "mill_ball":
        profile = [
            (
                radius * step / 12.0,
                math.sqrt(max(0.0, radius**2 - (radius * step / 12.0 - radius) ** 2)),
            )
            for step in range(13)
        ]
        if length > radius:
            profile.append((length, radius))
        return tuple(profile)

    if tool_type == "mill_bull" and corner_radius > 0.0:
        base_radius = radius - corner_radius
        profile = [
            (
                corner_radius * step / 12.0,
                base_radius
                + math.sqrt(max(0.0, corner_radius**2 - (corner_radius - corner_radius * step / 12.0) ** 2)),
            )
            for step in range(13)
        ]
        if length > corner_radius:
            profile.append((length, radius))
        return tuple(profile)

    return ((0.0, radius), (length, radius))
