"""Qt-free 2D X/Z silhouettes for turning tools."""

from __future__ import annotations

import math

EPS = 1e-9

TURNING_TOOL_LABELS = {
    "face_groove": "Face Groove",
    "od_groove": "OD Groove",
    "id_groove": "ID Groove",
    "drill": "Drill",
    "od_80": "OD80",
    "id_80": "ID80",
    "od_35": "OD35",
    "id_35": "ID35",
}
TURNING_INSERT_TYPES = frozenset(
    {
        "turning",
        "od_80",
        "id_80",
        "od_35",
        "id_35",
        "od_cutting",
        "id_cutting",
    }
)
TURNING_GROOVE_TYPES = frozenset({"face_groove", "od_groove", "id_groove"})

INSERT_GEOMETRY = {
    "od_80": (80.0, 5.0, 3, False),
    "id_80": (80.0, 5.0, 2, True),
    "od_35": (35.0, 3.0, 3, False),
    "id_35": (35.0, 3.0, 2, True),
}

TIP_DIRECTIONS = {
    1: (1.0, 1.0),
    2: (1.0, -1.0),
    3: (-1.0, -1.0),
    4: (-1.0, 1.0),
    5: (0.0, 1.0),
    6: (1.0, 0.0),
    7: (0.0, -1.0),
    8: (-1.0, 0.0),
    9: (0.0, 0.0),
}


def canonical_turning_tool_type(value: object) -> str:
    """Map legacy turning type names to current geometry names."""
    tool_type = str(value or "turning").strip().lower()
    return {"turning": "od_80", "od_cutting": "od_80", "id_cutting": "id_80"}.get(tool_type, tool_type)


def positive_float(spec: dict[str, object], key: str, default: float = 0.0) -> float:
    try:
        value = float(spec.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) and value > 0.0 else default


def tip_orientation(spec: dict[str, object], default: int) -> int:
    try:
        orientation = int(spec.get("tipOrientation", default))
    except (TypeError, ValueError):
        return default
    return orientation if orientation in range(1, 10) else default


def default_groove_orientation(tool_type: str) -> int:
    if tool_type == "od_groove":
        return 3
    if tool_type == "id_groove":
        return 2
    if tool_type == "face_groove":
        return 3
    return 1


def allowed_groove_orientations(tool_type: str) -> tuple[int, ...]:
    if tool_type == "od_groove":
        return (3, 4)
    if tool_type == "id_groove":
        return (1, 2)
    if tool_type == "face_groove":
        return (2, 3)
    return ()


def normalize_groove_orientation(spec: dict[str, object], tool_type: str) -> int:
    allowed = allowed_groove_orientations(tool_type)
    default = default_groove_orientation(tool_type)
    orientation = tip_orientation(spec, default)
    return orientation if orientation in allowed else default


def cutting_insert_points(
    length: float,
    insert_angle: float,
    edge_angle: float,
    orientation: int,
    *,
    internal: bool,
) -> tuple[tuple[float, float], ...]:
    """Build a display insert polygon whose main edge starts at the programmed tip."""
    _tip_x, tip_z = TIP_DIRECTIONS.get(orientation, TIP_DIRECTIONS[1])
    axial_sign = 1.0 if tip_z <= 0.0 else -1.0
    radial_sign = -1.0 if internal else 1.0
    main_angle = math.radians(edge_angle)
    other_angle = math.radians(edge_angle + insert_angle)
    main = (
        radial_sign * length * math.cos(main_angle),
        axial_sign * length * math.sin(main_angle),
    )
    other = (
        radial_sign * length * math.cos(other_angle),
        axial_sign * length * math.sin(other_angle),
    )
    return ((0.0, 0.0), main, (main[0] + other[0], main[1] + other[1]), other)


def stock_insert_points(
    length: float,
    insert_angle: float,
    edge_angle: float,
    *,
    internal: bool,
) -> tuple[tuple[float, float], ...]:
    """Return the sharp P3-OD/P2-ID rhombus used for stock removal."""
    radial_sign = -1.0 if internal else 1.0
    main_angle = math.radians(edge_angle)
    other_angle = math.radians(edge_angle + insert_angle)
    main = (
        radial_sign * length * math.cos(main_angle),
        length * math.sin(main_angle),
    )
    other = (
        radial_sign * length * math.cos(other_angle),
        length * math.sin(other_angle),
    )
    return ((0.0, 0.0), main, (main[0] + other[0], main[1] + other[1]), other)


def rounded_polygon(
    points: tuple[tuple[float, float], ...],
    radius: float,
    *,
    segments: int = 8,
) -> tuple[tuple[float, float], ...]:
    """Replace convex polygon corners with tangent circular arcs."""
    if radius <= EPS or len(points) < 3:
        return points
    area = sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )
    direction = 1.0 if area > 0.0 else -1.0
    rounded: list[tuple[float, float]] = []
    for index, point in enumerate(points):
        previous = points[index - 1]
        following = points[(index + 1) % len(points)]
        before = (previous[0] - point[0], previous[1] - point[1])
        after = (following[0] - point[0], following[1] - point[1])
        before_length = math.hypot(*before)
        after_length = math.hypot(*after)
        if before_length <= EPS or after_length <= EPS:
            rounded.append(point)
            continue
        before_unit = (before[0] / before_length, before[1] / before_length)
        after_unit = (after[0] / after_length, after[1] / after_length)
        corner_angle = math.acos(max(-1.0, min(1.0, before_unit[0] * after_unit[0] + before_unit[1] * after_unit[1])))
        tangent = radius / max(math.tan(corner_angle * 0.5), EPS)
        tangent = min(tangent, before_length * 0.45, after_length * 0.45)
        effective_radius = tangent * math.tan(corner_angle * 0.5)
        bisector = (before_unit[0] + after_unit[0], before_unit[1] + after_unit[1])
        bisector_length = math.hypot(*bisector)
        if bisector_length <= EPS:
            rounded.append(point)
            continue
        center_distance = effective_radius / max(math.sin(corner_angle * 0.5), EPS)
        center = (
            point[0] + bisector[0] / bisector_length * center_distance,
            point[1] + bisector[1] / bisector_length * center_distance,
        )
        tangent_before = (
            point[0] + before_unit[0] * tangent,
            point[1] + before_unit[1] * tangent,
        )
        tangent_after = (
            point[0] + after_unit[0] * tangent,
            point[1] + after_unit[1] * tangent,
        )
        start = math.atan2(tangent_before[1] - center[1], tangent_before[0] - center[0])
        end = math.atan2(tangent_after[1] - center[1], tangent_after[0] - center[0])
        if direction > 0.0:
            while end <= start:
                end += 2.0 * math.pi
        else:
            while end >= start:
                end -= 2.0 * math.pi
        angles = [start + (end - start) * step / segments for step in range(segments + 1)]
        low = min(start, end)
        high = max(start, end)
        for quarter_turn in range(-8, 9):
            angle = quarter_turn * math.pi * 0.5
            if low + EPS < angle < high - EPS:
                angles.append(angle)
        angles = sorted(set(angles), reverse=end < start)
        rounded.extend(
            (
                center[0] + effective_radius * math.cos(angle),
                center[1] + effective_radius * math.sin(angle),
            )
            for angle in angles
        )
    return tuple(rounded)


def tip_fillet_center(
    points: tuple[tuple[float, float], ...],
    radius: float,
) -> tuple[float, float]:
    """Return the rounded physical nose center for the sharp corner at index 0."""
    point = points[0]
    previous = points[-1]
    following = points[1]
    before = (previous[0] - point[0], previous[1] - point[1])
    after = (following[0] - point[0], following[1] - point[1])
    before_length = math.hypot(*before)
    after_length = math.hypot(*after)
    before_unit = (before[0] / before_length, before[1] / before_length)
    after_unit = (after[0] / after_length, after[1] / after_length)
    corner_angle = math.acos(max(-1.0, min(1.0, before_unit[0] * after_unit[0] + before_unit[1] * after_unit[1])))
    tangent = radius / max(math.tan(corner_angle * 0.5), EPS)
    tangent = min(tangent, before_length * 0.45, after_length * 0.45)
    effective_radius = tangent * math.tan(corner_angle * 0.5)
    bisector = (before_unit[0] + after_unit[0], before_unit[1] + after_unit[1])
    bisector_length = math.hypot(*bisector)
    center_distance = effective_radius / max(math.sin(corner_angle * 0.5), EPS)
    return (
        point[0] + bisector[0] / bisector_length * center_distance,
        point[1] + bisector[1] / bisector_length * center_distance,
    )


def turning_tool_polygon(
    spec: dict[str, object],
    stock_diameter: float,
    *,
    stock_scope: bool = False,
) -> tuple[tuple[float, float], ...] | None:
    """Return the local X/Z cutting silhouette relative to the programmed point."""
    tool_type = canonical_turning_tool_type(spec.get("type"))
    scale = max(3.0, min(12.0, stock_diameter * 0.08))
    polygon = None
    if tool_type in INSERT_GEOMETRY:
        insert_angle, edge_angle, expected_orientation, internal = INSERT_GEOMETRY[tool_type]
        orientation = tip_orientation(spec, expected_orientation)
        nose = positive_float(spec, "noseRadius")
        if nose > EPS:
            default_length = max(3.0, min(12.0, stock_diameter * 0.08))
            minimum_length = nose / max(math.tan(math.radians(insert_angle * 0.5)), EPS) / 0.45
            length = max(positive_float(spec, "insertLength", default_length), minimum_length)
            if orientation == expected_orientation:
                sharp = stock_insert_points(length, insert_angle, edge_angle, internal=internal)
                rounded = rounded_polygon(sharp, nose)
                nose_center = tip_fillet_center(sharp, nose)
                target_center = (-nose if internal else nose, nose)
                shift_x = target_center[0] - nose_center[0]
                shift_z = target_center[1] - nose_center[1]
                polygon = tuple((x_value + shift_x, z_value + shift_z) for x_value, z_value in rounded)
            elif not stock_scope:
                polygon = rounded_polygon(
                    cutting_insert_points(
                        length,
                        insert_angle,
                        edge_angle,
                        orientation,
                        internal=internal,
                    ),
                    nose,
                    segments=5,
                )
    elif tool_type in {"od_groove", "id_groove"}:
        width = positive_float(spec, "width")
        if width > EPS:
            length = positive_float(spec, "insertLength", max(scale, width * 2.0))
            direction = -1.0 if tool_type == "id_groove" else 1.0
            orientation = normalize_groove_orientation(spec, tool_type)
            if orientation in (2, 3):
                z0, z1 = 0.0, width
            else:
                z0, z1 = -width, 0.0
            sharp = (
                (0.0, z0),
                (direction * length, z0),
                (direction * length, z1),
                (0.0, z1),
            )
            polygon = rounded_polygon(sharp, positive_float(spec, "noseRadius"))
    elif tool_type == "face_groove":
        width = positive_float(spec, "width", max(1.0, stock_diameter * 0.03))
        length = max(scale * 1.5, width * 2.0)
        orientation = normalize_groove_orientation(spec, tool_type)
        x0, x1 = (0.0, width) if orientation == 2 else (-width, 0.0)
        sharp = (
            (x0, 0.0),
            (x1, 0.0),
            (x1, length),
            (x0, length),
        )
        polygon = rounded_polygon(sharp, positive_float(spec, "noseRadius"))
    return polygon


def display_tool_geometry(spec: dict[str, object], stock_diameter: float):
    """Return ``(polygon, preview_depth, cache_key)`` for the OpenGL tool preview."""
    tool_type = canonical_turning_tool_type(spec.get("type"))
    scale = max(3.0, min(12.0, stock_diameter * 0.08))
    if tool_type == "drill":
        diameter = positive_float(spec, "diameter", max(2.0, stock_diameter * 0.1))
        length = positive_float(spec, "length", max(12.0, diameter * 4.0))
        angle = min(179.0, max(1.0, positive_float(spec, "tipAngle", 118.0)))
        cone = (diameter * 0.5) / math.tan(math.radians(angle * 0.5))
        points = (
            (0.0, 0.0),
            (-diameter * 0.5, cone),
            (-diameter * 0.5, length),
            (diameter * 0.5, length),
            (diameter * 0.5, cone),
        )
        return points, max(1.0, diameter * 0.35), (tool_type, diameter, length, angle)
    points = turning_tool_polygon(spec, stock_diameter)
    if points is None:
        return ((0.0, 0.0), (scale, 0.0), (scale, scale), (0.0, scale)), 1.0, (tool_type, "empty")
    width = positive_float(spec, "width")
    nose = positive_float(spec, "noseRadius")
    orientation = tip_orientation(spec, 1)
    length = positive_float(spec, "insertLength", scale)
    return points, max(1.0, max(width, length, nose) * 0.35), (tool_type, width, nose, orientation, length)
