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


def normalized_tools(raw):
    """Return validated turning tool definitions from persisted library data."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    if not isinstance(raw, dict):
        return {}

    tools = {}
    for raw_key, raw_spec in raw.items():
        if not isinstance(raw_spec, dict):
            continue
        key = str(raw_key).strip().upper()
        digits = key[1:] if key.startswith("T") else key
        if not digits.isdigit() or not 1 <= len(digits) <= 4:
            continue
        key = f"T{int(digits):04d}"

        tool_type, implied_application = _migrate_turning_type(raw_spec.get("type", "turn" + "ing"))
        if tool_type not in TURNING_TOOL_TYPES:
            continue
        spec = {"type": tool_type}

        description = raw_spec.get("description")
        if isinstance(description, str) and description.strip():
            spec["description"] = " ".join(description.split())

        if tool_type in TURNING_INSERT_TYPES:
            try:
                radius = float(raw_spec.get("noseRadius", 0.0))
                orientation = int(raw_spec.get("tipOrientation", DEFAULT_AUTO_TIP_ORIENTATION[tool_type]))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(radius) or radius <= 0.0 or orientation not in range(1, 10):
                continue
            spec["noseRadius"] = radius
            spec["tipOrientation"] = orientation
            spec["applications"] = list(
                _normalized_tool_applications(raw_spec, tool_type, implied_application, orientation)
            )
            if not spec["applications"]:
                continue
            default_insert_length = 16.0 if tool_type == "diamond_35" else 12.0
            try:
                insert_length = float(raw_spec.get("insertLength", default_insert_length))
            except (TypeError, ValueError):
                insert_length = default_insert_length
            if not math.isfinite(insert_length) or insert_length <= 0.0:
                insert_length = default_insert_length
            spec["insertLength"] = insert_length

        if tool_type == "thread":
            try:
                insert_length = float(raw_spec.get("insertLength", 12.0))
                thread_angle = float(raw_spec.get("threadAngle", 60.0))
                tip_width = float(raw_spec.get("threadTipWidth", 0.8))
                corner_radius = float(raw_spec.get("threadCornerRadius", 0.1))
                orientation = int(raw_spec.get("tipOrientation", 3))
            except (TypeError, ValueError):
                continue
            finite = all(math.isfinite(value) for value in (insert_length, thread_angle, tip_width, corner_radius))
            dimensions_valid = insert_length > 0.0 and tip_width > 0.0 and corner_radius >= 0.0
            if not finite or not dimensions_valid or not 1.0 <= thread_angle < 180.0 or orientation not in range(1, 10):
                continue
            spec.update(
                insertLength=insert_length,
                threadAngle=thread_angle,
                threadTipWidth=tip_width,
                threadCornerRadius=corner_radius,
                tipOrientation=orientation,
            )
            spec["applications"] = list(
                _normalized_tool_applications(raw_spec, tool_type, implied_application, orientation)
            )
            if not spec["applications"]:
                continue

        if tool_type == "groove":
            try:
                width = float(raw_spec.get("width", 0.0))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(width) or width <= 0.0:
                continue
            spec["width"] = width
            try:
                groove_radius = float(raw_spec.get("noseRadius", 0.0))
            except (TypeError, ValueError):
                groove_radius = 0.0
            spec["noseRadius"] = groove_radius if math.isfinite(groove_radius) and groove_radius > 0.0 else 0.0
            applications = _normalized_tool_applications(
                raw_spec,
                tool_type,
                implied_application,
                DEFAULT_AUTO_TIP_ORIENTATION[tool_type],
            )
            default_orientation = 2 if applications == ("id",) else 3
            try:
                orientation = int(raw_spec.get("tipOrientation", default_orientation))
            except (TypeError, ValueError):
                orientation = default_orientation
            choices = {
                value
                for application in applications
                for value in AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION[tool_type][application]
            }
            if orientation not in choices:
                orientation = min(choices)
            spec["tipOrientation"] = orientation
            spec["applications"] = list(applications)

        if tool_type == "drill" and any(key in raw_spec for key in ("diameter", "length", "tipAngle")):
            try:
                diameter = float(raw_spec.get("diameter", 0.0))
                length = float(raw_spec.get("length", 0.0))
                tip_angle = float(raw_spec.get("tipAngle", 118.0))
            except (TypeError, ValueError):
                continue
            if (
                not all(math.isfinite(value) for value in (diameter, length, tip_angle))
                or diameter <= 0.0
                or length <= 0.0
                or not 1.0 <= tip_angle < 180.0
            ):
                continue
            spec.update(diameter=diameter, length=length, tipAngle=tip_angle)

        if tool_type == "tap":
            try:
                diameter = float(raw_spec.get("diameter", 0.0))
                length = float(raw_spec.get("length", 0.0))
                tip_angle = float(raw_spec.get("tipAngle", 118.0))
            except (TypeError, ValueError):
                continue
            if (
                not all(math.isfinite(value) for value in (diameter, length, tip_angle))
                or diameter <= 0.0
                or length <= 0.0
                or not 1.0 <= tip_angle < 180.0
            ):
                continue
            spec.update(diameter=diameter, length=length, tipAngle=tip_angle)

        tools[key] = spec
    return tools


def normalized_milling_tools(raw):
    """Return validated milling tool geometry from persisted library data."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    if not isinstance(raw, dict):
        return {}

    tools = {}
    for raw_key, raw_spec in raw.items():
        if not isinstance(raw_spec, dict):
            continue
        key = str(raw_key).strip().upper()
        digits = key[1:] if key.startswith("T") else key
        if not digits.isdigit():
            continue
        tool_number = int(digits)
        if not 1 <= tool_number <= 99:
            continue
        key = f"T{tool_number}"

        tool_type = str(raw_spec.get("type", "mill_flat")).strip().lower()
        if tool_type not in MILLING_TOOL_TYPES:
            continue
        try:
            diameter = float(raw_spec.get("diameter", 0.0))
            length = float(raw_spec.get("length", 0.0))
            radius = max(0.0, float(raw_spec.get("cornerRadius", 0.0)))
        except (TypeError, ValueError):
            continue

        if not all(math.isfinite(value) for value in (diameter, length, radius)):
            continue
        if diameter <= 0.0 or length <= 0.0:
            continue
        if tool_type == "mill_ball":
            radius = diameter / 2.0
        elif tool_type == "mill_bull" and radius > diameter / 2.0:
            continue
        elif tool_type != "mill_bull":
            radius = 0.0

        spec = {
            "type": tool_type,
            "diameter": diameter,
            "cornerRadius": radius,
            "length": length,
        }

        if tool_type in {"face_mill", "slot_mill"}:
            try:
                cutting_height = float(
                    raw_spec.get("cuttingHeight", default_cutting_height(tool_type, diameter, length))
                )
                shank_diameter = float(raw_spec.get("shankDiameter", default_shank_diameter(diameter)))
            except (TypeError, ValueError):
                continue
            if not all(math.isfinite(value) for value in (cutting_height, shank_diameter)):
                continue
            if not 0.0 < cutting_height <= length or not 0.0 < shank_diameter < diameter:
                continue
            spec.update(cuttingHeight=cutting_height, shankDiameter=shank_diameter)

        if tool_type == "chamfer_mill":
            try:
                tip_diameter = float(raw_spec.get("tipDiameter", default_tip_diameter(diameter)))
                chamfer_angle = float(raw_spec.get("chamferAngle", 90.0))
            except (TypeError, ValueError):
                continue
            if not all(math.isfinite(value) for value in (tip_diameter, chamfer_angle)):
                continue
            if not 0.0 <= tip_diameter < diameter or not 1.0 <= chamfer_angle < 180.0:
                continue
            spec.update(tipDiameter=tip_diameter, chamferAngle=chamfer_angle)

        if tool_type == "drill":
            try:
                tip_angle = float(raw_spec.get("tipAngle", default_drill_tip_angle()))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(tip_angle) or not 1.0 <= tip_angle < 180.0:
                continue
            spec["tipAngle"] = tip_angle
        description = raw_spec.get("description")
        if isinstance(description, str) and description.strip():
            spec["description"] = " ".join(description.split())
        tools[key] = spec
    return tools
