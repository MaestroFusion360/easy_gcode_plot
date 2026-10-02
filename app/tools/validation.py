"""Validation and normalization for persisted tool-library records."""

import json
import math

from app.tools.definitions import (
    AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION,
    DEFAULT_AUTO_TIP_ORIENTATION,
    MILLING_TOOL_TYPES,
    TURNING_INSERT_TYPES,
    TURNING_TOOL_TYPES,
    applications_for_orientation,
    normalized_applications,
)
from app.tools.milling_geometry import (
    default_cutting_height,
    default_drill_tip_angle,
    default_shank_diameter,
    default_tip_diameter,
)
from app.tools.milling_lengths import milling_lengths


def _migrate_turning_type(value: object) -> tuple[str, str | None]:  # pylint: disable=too-many-return-statements
    """Decode the historical compositional type format at the persistence boundary."""
    raw_type = str(value or "").strip().lower()
    if raw_type in TURNING_TOOL_TYPES:
        return raw_type, None
    parts = raw_type.split("_")
    if len(parts) == 1 and raw_type == "turn" + "ing":
        return "diamond_80", "od"
    if len(parts) != 2:
        return "", None
    qualifier, shape = parts
    if qualifier == "insert" and shape in {"square", "round", "triangle"}:
        return shape, None
    if qualifier in {"od", "id", "face"}:
        if shape in {"80", "35"}:
            return f"diamond_{shape}", qualifier
        if shape == "cutting":
            return "diamond_80", qualifier
        if shape == "groove":
            return "groove", qualifier
    return "", None


def _normalized_tool_applications(
    raw_spec: dict[str, object], tool_type: str, implied_application: str | None, orientation: int
) -> tuple[str, ...]:
    applications = normalized_applications(raw_spec.get("applications"))
    if implied_application is not None:
        applications = tuple(dict.fromkeys((*applications, implied_application)))
    if not applications:
        applications = applications_for_orientation(tool_type, orientation)
    supported = AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION.get(tool_type, {})
    return tuple(application for application in applications if application in supported)


def _tool_records(raw):
    """Decode either supported persisted representation into tool records."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    return raw if isinstance(raw, dict) else {}


def _tool_number(raw_key, *, minimum, maximum, maximum_digits=None):
    key = str(raw_key).strip().upper()
    digits = key[1:] if key.startswith("T") else key
    if not digits.isdigit() or (maximum_digits is not None and len(digits) > maximum_digits):
        return None
    number = int(digits)
    return number if minimum <= number <= maximum else None


def _valid_thread_geometry(insert_length, thread_angle, tip_width, corner_radius, orientation):
    return (
        all(math.isfinite(value) for value in (insert_length, thread_angle, tip_width, corner_radius))
        and insert_length > 0.0
        and tip_width > 0.0
        and corner_radius >= 0.0
        and 1.0 <= thread_angle < 180.0
        and orientation in range(1, 10)
    )


def _normalize_thread_spec(raw_spec, spec, implied_application):
    try:
        insert_length = float(raw_spec.get("insertLength", 12.0))
        thread_angle = float(raw_spec.get("threadAngle", 60.0))
        tip_width = float(raw_spec.get("threadTipWidth", 0.8))
        corner_radius = float(raw_spec.get("threadCornerRadius", 0.1))
        orientation = int(raw_spec.get("tipOrientation", 3))
    except (TypeError, ValueError):
        return False
    if not _valid_thread_geometry(insert_length, thread_angle, tip_width, corner_radius, orientation):
        return False
    applications = _normalized_tool_applications(raw_spec, "thread", implied_application, orientation)
    if not applications:
        return False
    spec.update(
        insertLength=insert_length,
        threadAngle=thread_angle,
        threadTipWidth=tip_width,
        threadCornerRadius=corner_radius,
        tipOrientation=orientation,
        applications=list(applications),
    )
    return True


def _normalize_insert_spec(raw_spec, spec, tool_type, implied_application):
    try:
        radius = float(raw_spec.get("noseRadius", 0.0))
        orientation = int(raw_spec.get("tipOrientation", DEFAULT_AUTO_TIP_ORIENTATION[tool_type]))
    except (TypeError, ValueError):
        return False
    if not math.isfinite(radius) or radius <= 0.0 or orientation not in range(1, 10):
        return False
    applications = _normalized_tool_applications(raw_spec, tool_type, implied_application, orientation)
    if not applications:
        return False
    default_length = 16.0 if tool_type == "diamond_35" else 12.0
    try:
        insert_length = float(raw_spec.get("insertLength", default_length))
    except (TypeError, ValueError):
        insert_length = default_length
    if not math.isfinite(insert_length) or insert_length <= 0.0:
        insert_length = default_length
    spec.update(
        noseRadius=radius,
        tipOrientation=orientation,
        applications=list(applications),
        insertLength=insert_length,
    )
    return True


def _normalize_groove_spec(raw_spec, spec, implied_application):
    try:
        width = float(raw_spec.get("width", 0.0))
    except (TypeError, ValueError):
        return False
    if not math.isfinite(width) or width <= 0.0:
        return False
    try:
        groove_radius = float(raw_spec.get("noseRadius", 0.0))
    except (TypeError, ValueError):
        groove_radius = 0.0
    applications = _normalized_tool_applications(
        raw_spec, "groove", implied_application, DEFAULT_AUTO_TIP_ORIENTATION["groove"]
    )
    default_orientation = 2 if applications == ("id",) else 3
    try:
        orientation = int(raw_spec.get("tipOrientation", default_orientation))
    except (TypeError, ValueError):
        orientation = default_orientation
    choices = {
        value
        for application in applications
        for value in AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION["groove"][application]
    }
    if orientation not in choices:
        orientation = min(choices)
    spec.update(
        width=width,
        noseRadius=groove_radius if math.isfinite(groove_radius) and groove_radius > 0.0 else 0.0,
        tipOrientation=orientation,
        applications=list(applications),
    )
    return True


def _normalize_turning_drill_geometry(raw_spec, spec):
    try:
        diameter = float(raw_spec.get("diameter", 0.0))
        length = float(raw_spec.get("length", 0.0))
        tip_angle = float(raw_spec.get("tipAngle", 118.0))
    except (TypeError, ValueError):
        return False
    if (
        not all(math.isfinite(value) for value in (diameter, length, tip_angle))
        or diameter <= 0.0
        or length <= 0.0
        or not 1.0 <= tip_angle < 180.0
    ):
        return False
    spec.update(diameter=diameter, length=length, tipAngle=tip_angle)
    return True


def _normalize_milling_drill_tip(raw_spec, spec):
    try:
        tip_angle = float(raw_spec.get("tipAngle", default_drill_tip_angle()))
    except (TypeError, ValueError):
        return False
    if not math.isfinite(tip_angle) or not 1.0 <= tip_angle < 180.0:
        return False
    spec["tipAngle"] = tip_angle
    return True


def _normalize_face_slot_extras(raw_spec, spec, tool_type, diameter, length):
    if tool_type not in {"face_mill", "slot_mill"}:
        return True
    try:
        cutting_height = float(
            spec.get("fluteLength", raw_spec.get("cuttingHeight", default_cutting_height(tool_type, diameter, length)))
        )
        shank_diameter = float(raw_spec.get("shankDiameter", default_shank_diameter(diameter)))
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(value) for value in (cutting_height, shank_diameter)):
        return False
    if not 0.0 < cutting_height <= length or not 0.0 < shank_diameter < diameter:
        return False
    spec["shankDiameter"] = shank_diameter
    if "fluteLength" not in spec:
        spec["cuttingHeight"] = cutting_height
    return True


def _normalize_chamfer_extras(raw_spec, spec, tool_type, diameter):
    if tool_type != "chamfer_mill":
        return True
    try:
        tip_diameter = float(raw_spec.get("tipDiameter", default_tip_diameter(diameter)))
        chamfer_angle = float(raw_spec.get("chamferAngle", 90.0))
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(value) for value in (tip_diameter, chamfer_angle)):
        return False
    if not 0.0 <= tip_diameter < diameter or not 1.0 <= chamfer_angle < 180.0:
        return False
    spec.update(tipDiameter=tip_diameter, chamferAngle=chamfer_angle)
    return True


def _normalize_milling_extras(raw_spec, spec, tool_type, diameter, length):
    if not _normalize_face_slot_extras(raw_spec, spec, tool_type, diameter, length):
        return False
    if not _normalize_chamfer_extras(raw_spec, spec, tool_type, diameter):
        return False
    if tool_type == "drill":
        return _normalize_milling_drill_tip(raw_spec, spec)
    if tool_type == "taper_ball_mill":
        try:
            taper_angle = float(raw_spec.get("taperAngle", 6.0))
        except (TypeError, ValueError):
            return False
        if not math.isfinite(taper_angle) or not 0.0 < taper_angle < 90.0:
            return False
        spec["taperAngle"] = taper_angle
    return True


def _milling_base_spec(raw_spec):
    tool_type = str(raw_spec.get("type", "mill_flat")).strip().lower()
    if tool_type not in MILLING_TOOL_TYPES:
        return None
    try:
        diameter = float(raw_spec.get("diameter", 0.0))
        radius = max(0.0, float(raw_spec.get("cornerRadius", 0.0)))
    except (TypeError, ValueError):
        return None
    lengths = milling_lengths(raw_spec)
    if lengths is None or not all(math.isfinite(value) for value in (diameter, radius)):
        return None
    if diameter <= 0.0:
        return None
    if tool_type == "mill_ball":
        radius = diameter / 2.0
    elif tool_type == "mill_bull" and radius > diameter / 2.0:
        return None
    elif tool_type != "mill_bull":
        radius = 0.0
    return {"type": tool_type, "diameter": diameter, "cornerRadius": radius, **lengths}


def _turning_base_spec(raw_key, raw_spec):
    if not isinstance(raw_spec, dict):
        return None
    number = _tool_number(raw_key, minimum=0, maximum=9999, maximum_digits=4)
    if number is None:
        return None
    tool_type, implied_application = _migrate_turning_type(raw_spec.get("type", "turn" + "ing"))
    if tool_type not in TURNING_TOOL_TYPES:
        return None
    spec = {"type": tool_type}
    description = raw_spec.get("description")
    if isinstance(description, str) and description.strip():
        spec["description"] = " ".join(description.split())
    return f"T{number:04d}", spec, tool_type, implied_application


def _normalize_turning_variant(raw_spec, spec, tool_type, implied_application):
    if tool_type in TURNING_INSERT_TYPES:
        return _normalize_insert_spec(raw_spec, spec, tool_type, implied_application)
    if tool_type == "thread":
        return _normalize_thread_spec(raw_spec, spec, implied_application)
    if tool_type == "groove":
        return _normalize_groove_spec(raw_spec, spec, implied_application)
    if tool_type == "tap" or (
        tool_type == "drill" and any(key in raw_spec for key in ("diameter", "length", "tipAngle"))
    ):
        return _normalize_turning_drill_geometry(raw_spec, spec)
    return True


def normalized_tools(raw):
    """Return validated turning tool definitions from persisted library data."""
    raw = _tool_records(raw)

    tools = {}
    for raw_key, raw_spec in raw.items():
        base = _turning_base_spec(raw_key, raw_spec)
        if base is None:
            continue
        key, spec, tool_type, implied_application = base

        if not _normalize_turning_variant(raw_spec, spec, tool_type, implied_application):
            continue

        tools[key] = spec
    return tools


def normalized_milling_tools(raw):
    """Return validated milling tool geometry from persisted library data."""
    raw = _tool_records(raw)

    tools = {}
    for raw_key, raw_spec in raw.items():
        if not isinstance(raw_spec, dict):
            continue
        tool_number = _tool_number(raw_key, minimum=1, maximum=99)
        if tool_number is None:
            continue
        key = f"T{tool_number}"

        spec = _milling_base_spec(raw_spec)
        if spec is None:
            continue
        tool_type = spec["type"]
        diameter = spec["diameter"]
        length = spec["length"]

        if not _normalize_milling_extras(raw_spec, spec, tool_type, diameter, length):
            continue
        description = raw_spec.get("description")
        if isinstance(description, str) and description.strip():
            spec["description"] = " ".join(description.split())
        tools[key] = spec
    return tools
