"""Shared axial geometry for milling tool previews."""

from __future__ import annotations

import math

from app.tools.definitions import MILLING_TOOL_TYPES
from app.tools.milling_lengths import milling_lengths

SUPPORTED_MILLING_GEOMETRIES = MILLING_TOOL_TYPES


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


def _stepped_geometry(spec, lengths, tool_type, diameter):
    """Use flute length for new heads and retain legacy cutting-height geometry."""
    length = lengths["length"]
    try:
        cutting_height = float(
            lengths.get("fluteLength", spec.get("cuttingHeight", default_cutting_height(tool_type, diameter, length)))
        )
        shank_diameter = float(spec.get("shankDiameter", default_shank_diameter(diameter)))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (cutting_height, shank_diameter)):
        return None
    if "fluteLength" not in lengths:
        cutting_height = min(max(cutting_height, 0.1), length)
    return {
        "cuttingHeight": cutting_height,
        "shankDiameter": shank_diameter if 0 < shank_diameter < diameter else min(max(shank_diameter, 0.1), diameter),
    }


def _chamfer_geometry(spec, diameter):
    try:
        tip_diameter = float(spec.get("tipDiameter", default_tip_diameter(diameter)))
        chamfer_angle = float(spec.get("chamferAngle", 90.0))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (tip_diameter, chamfer_angle)):
        return None
    return {
        "tipDiameter": min(max(tip_diameter, 0.0), diameter),
        "chamferAngle": min(max(chamfer_angle, 1.0), 179.0),
    }


def _drill_geometry(spec):
    try:
        tip_angle = float(spec.get("tipAngle", default_drill_tip_angle()))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(tip_angle):
        return None
    return {"tipAngle": min(max(tip_angle, 1.0), 179.0)}


def _taper_ball_geometry(spec):
    try:
        taper_angle = float(spec.get("taperAngle", 6.0))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(taper_angle):
        return None
    return {"taperAngle": min(max(taper_angle, 0.1), 89.0)}


def _type_specific_geometry(spec, lengths, tool_type, diameter):
    """Return the fields only one tool family has, or ``None`` when they are invalid."""
    if tool_type == "thread_mill":
        return _thread_mill_geometry(spec, diameter, lengths["length"])
    if tool_type in {"face_mill", "slot_mill"}:
        return _stepped_geometry(spec, lengths, tool_type, diameter)
    if tool_type == "chamfer_mill":
        return _chamfer_geometry(spec, diameter)
    if tool_type == "drill":
        return _drill_geometry(spec)
    if tool_type == "taper_ball_mill":
        return _taper_ball_geometry(spec)
    return {}


def _resolved_corner_radius(tool_type, corner_radius, radius):
    if tool_type == "mill_ball":
        return radius
    if tool_type == "mill_bull":
        return min(max(corner_radius, 0.0), radius)
    return 0.0


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
        corner_radius = float(spec.get("cornerRadius", 0.0))
    except (TypeError, ValueError):
        return None
    lengths = milling_lengths(spec)
    if lengths is None or not all(math.isfinite(value) for value in (diameter, corner_radius)):
        return None
    if diameter <= 0.0:
        return None

    result: dict[str, float | str] = {
        "type": tool_type,
        "diameter": diameter,
        **lengths,
        "cornerRadius": _resolved_corner_radius(tool_type, corner_radius, diameter * 0.5),
    }
    extras = _type_specific_geometry(spec, lengths, tool_type, diameter)
    if extras is None:
        return None
    result.update(extras)
    if "shankDiameter" in spec and tool_type not in {"face_mill", "slot_mill"}:
        try:
            shank = float(spec["shankDiameter"])
        except (ValueError, TypeError):
            return None
        if not math.isfinite(shank) or shank <= 0:
            return None
        result["shankDiameter"] = shank
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
    elif tool_type == "taper_ball_mill":
        key.append(float(geometry["taperAngle"]))
    if tool_type == "thread_mill":
        key.extend((geometry["threadRootDiameter"], geometry["threadAngle"], geometry["threadTipWidth"]))
    if "shankDiameter" in geometry and tool_type not in {"face_mill", "slot_mill"}:
        key.append(("shankDiameter", geometry["shankDiameter"]))
    if "fluteLength" in geometry:
        key.append((float(geometry["fluteLength"]), float(geometry["bodyLength"])))
    return tuple(key)


def milling_tool_profile(
    spec: dict[str, object] | None,
) -> tuple[tuple[float, float], ...]:
    """Return a radial ``(z, radius)`` profile with the programmed tip at ``z=0``."""
    geometry = milling_geometry(spec)
    if geometry is None:
        return ()

    if "fluteLength" not in geometry:
        return _cutting_tool_profile(geometry)
    total = float(geometry["length"])
    geometry["length"] = geometry["fluteLength"]
    profile = _cutting_tool_profile(geometry)
    if float(geometry["bodyLength"]) > 0:
        shank = float(geometry.get("shankDiameter", profile[-1][1] * 2)) / 2
        profile += ((float(geometry["fluteLength"]), shank), (total, shank))
    return profile


def _ball_tool_profile(length, radius):
    profile = [
        (
            min(length, radius) * step / 12.0,
            math.sqrt(max(0.0, radius**2 - (min(length, radius) * step / 12.0 - radius) ** 2)),
        )
        for step in range(13)
    ]
    if length > radius:
        profile.append((length, radius))
    return tuple(profile)


def _taper_ball_tool_profile(geometry, length, radius):
    angle = math.radians(float(geometry["taperAngle"]))
    tangent_angle = math.pi * 0.5 - angle
    sphere_end_z = radius * (1.0 - math.cos(tangent_angle))
    sphere_steps = 16
    sphere_end = min(length, sphere_end_z)
    profile = []
    for step in range(sphere_steps + 1):
        z_value = sphere_end * step / sphere_steps
        radial = math.sqrt(max(0.0, radius * radius - (z_value - radius) ** 2))
        profile.append((z_value, radial))
    if length > sphere_end_z:
        cone_radius = radius * math.sin(tangent_angle)
        cone_height = length - sphere_end_z
        profile.extend(
            (sphere_end_z + cone_height * step / 12.0, cone_radius + cone_height * step / 12.0 * math.tan(angle))
            for step in range(1, 13)
        )
    return tuple(profile)


def _bull_tool_profile(length, radius, corner_radius):
    base_radius = radius - corner_radius
    profile = [
        (
            min(length, corner_radius) * step / 12.0,
            base_radius
            + math.sqrt(max(0.0, corner_radius**2 - (corner_radius - min(length, corner_radius) * step / 12.0) ** 2)),
        )
        for step in range(13)
    ]
    if length > corner_radius:
        profile.append((length, radius))
    return tuple(profile)


def _cutting_tool_profile(geometry):
    """Construct the cutter; explicit body length is appended by the caller."""

    tool_type = str(geometry["type"])
    diameter = float(geometry["diameter"])
    length = float(geometry["length"])
    corner_radius = float(geometry["cornerRadius"])
    radius = diameter * 0.5

    if tool_type == "thread_mill":
        root = float(geometry["threadRootDiameter"]) / 2
        flank = (radius - root) * math.tan(math.radians(float(geometry["threadAngle"]) / 2))
        crest = float(geometry["threadTipWidth"])
        return ((0, root), (flank, radius), (flank + crest, radius), (2 * flank + crest, root), (length, root))
    if tool_type in {"drill", "tap", "chamfer_mill"}:
        return _axial_tool_profile(geometry, tool_type, length, radius)
    if tool_type in {"face_mill", "slot_mill"}:
        return _stepped_tool_profile(geometry, tool_type, length, diameter, radius)
    return _rounded_or_flat_profile(geometry, tool_type, length, radius, corner_radius)


def _rounded_or_flat_profile(geometry, tool_type, length, radius, corner_radius):
    if tool_type == "mill_ball":
        return _ball_tool_profile(length, radius)
    if tool_type == "taper_ball_mill":
        return _taper_ball_tool_profile(geometry, length, radius)
    if tool_type == "mill_bull" and corner_radius > 0.0:
        return _bull_tool_profile(length, radius, corner_radius)
    return ((0.0, radius), (length, radius))


def _axial_tool_profile(geometry, tool_type, length, radius):
    """Build axial profiles, including a flat-ended cylindrical tap."""
    if tool_type == "drill":
        half_angle = math.radians(float(geometry["tipAngle"]) * 0.5)
        cone_height = min(length, radius / max(math.tan(half_angle), 1.0e-9))
        return ((0.0, 0.0), (cone_height, radius), (length, radius))

    if tool_type == "tap":
        return ((0.0, radius), (length, radius))

    tip_radius = float(geometry["tipDiameter"]) * 0.5
    half_angle = math.radians(float(geometry["chamferAngle"]) * 0.5)
    cone_height = (radius - tip_radius) / max(math.tan(half_angle), 1.0e-9)
    cone_height = min(max(cone_height, 0.0), length)
    return ((0.0, tip_radius), (cone_height, radius), (length, radius))


def _stepped_tool_profile(geometry, tool_type, length, diameter, radius):
    """Build a cutting head followed by the narrower body radius."""
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

    cutting_height = float(geometry["cuttingHeight"])
    shank_radius = float(geometry["shankDiameter"]) * 0.5
    return (
        (0.0, radius),
        (cutting_height, radius),
        (cutting_height, shank_radius),
        (length, shank_radius),
    )


def _thread_mill_geometry(spec, diameter, length):
    """Single annular tooth; no turning-tool geometry or cylindrical fallback."""
    if spec.get("threadProfile") != "single_form":
        return None
    try:
        root, angle, crest = (float(spec[key]) for key in ("threadRootDiameter", "threadAngle", "threadTipWidth"))
    except (KeyError, ValueError, TypeError):
        return None
    if not all(math.isfinite(v) for v in (root, angle, crest)):
        return None
    if not 0 < root < diameter or not 1 <= angle < 180 or crest <= 0:
        return None
    if (diameter - root) * math.tan(math.radians(angle / 2)) + crest > float(spec.get("fluteLength", length)):
        return None
    return {"threadProfile": "single_form", "threadRootDiameter": root, "threadAngle": angle, "threadTipWidth": crest}


def strict_bundle_geometry(spec):
    """Validate explicit v2 dimensions without filling, clipping or coercing fields."""
    required = {"type", "diameter", "length", "fluteLength", "bodyLength", "shankDiameter", "cornerRadius"}
    extras = {
        "chamfer_mill": {"tipDiameter", "chamferAngle"},
        "drill": {"tipAngle"},
        "taper_ball_mill": {"taperAngle"},
        "thread_mill": {"threadProfile", "threadRootDiameter", "threadAngle", "threadTipWidth"},
    }
    if not isinstance(spec, dict) or spec.get("type") not in SUPPORTED_MILLING_GEOMETRIES:
        raise ValueError("Unknown bundle tool type")
    required |= extras.get(spec["type"], set())
    if not required <= spec.keys():
        raise ValueError("Incomplete bundle tool geometry")
    if spec.keys() - required - {"number", "name", "h", "d"}:
        raise ValueError("Unexpected bundle tool fields")
    _explicit_bundle_dimensions(spec, required)
    geometry = milling_geometry(spec)
    if geometry is None or any(geometry.get(key) != spec[key] for key in required):
        raise ValueError("Unsupported or inconsistent bundle tool geometry")
    if spec["type"] in {"face_mill", "slot_mill"} and spec["shankDiameter"] >= spec["diameter"]:
        raise ValueError("Head diameter must exceed shank diameter")
    _validate_bundle_profile(spec)
    return geometry


def _explicit_bundle_dimensions(spec, required):
    numeric = required - {"type", "threadProfile"}
    for key in numeric:
        value = spec[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"Invalid bundle dimension: {key}")
    if any(spec[k] <= 0 for k in ("diameter", "length", "fluteLength", "shankDiameter")) or spec["bodyLength"] < 0:
        raise ValueError("Invalid bundle tool lengths")
    if abs(spec["length"] - spec["fluteLength"] - spec["bodyLength"]) > 1e-9:
        raise ValueError("Inconsistent bundle tool lengths")


def _validate_bundle_profile(spec):
    if spec["type"] == "taper_ball_mill" and spec["taperAngle"] < 1:
        raise ValueError("Invalid bundle taper angle")
    minimum_flute = {"mill_ball": spec["diameter"] / 2, "mill_bull": spec["cornerRadius"]}
    if spec["type"] == "drill":
        minimum_flute["drill"] = spec["diameter"] / (2 * math.tan(math.radians(spec["tipAngle"] / 2)))
    if spec["type"] in minimum_flute and spec["fluteLength"] < minimum_flute[spec["type"]]:
        raise ValueError("Cutting profile exceeds flute length")
    if spec["type"] == "chamfer_mill":
        height = (spec["diameter"] - spec["tipDiameter"]) / (2 * math.tan(math.radians(spec["chamferAngle"] / 2)))
        if spec["tipDiameter"] >= spec["diameter"] or height > spec["fluteLength"]:
            raise ValueError("Chamfer profile exceeds flute length")
