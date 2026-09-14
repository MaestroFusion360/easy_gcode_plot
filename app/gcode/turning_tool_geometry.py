"""Qt-free 2D X/Z silhouettes for turning tools."""

from __future__ import annotations

import math

from app.tools.definitions import tool_application

EPS = 1e-9

INSERT_GEOMETRY = {
    "diamond_80": (80.0, 5.0),
    "diamond_35": (35.0, 3.0),
    "square": (90.0, 0.0),
    "triangle": (60.0, 0.0),
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

ORIENTATION_SCREEN_ANGLES = {
    1: -45.0,
    2: -135.0,
    3: 135.0,
    4: 45.0,
    5: 0.0,
    6: -90.0,
    7: 180.0,
    8: 90.0,
}


def lathe_view_point(x_value: float, z_value: float) -> tuple[float, float]:
    """Project an X/Z tool point like the fixed Stock Removal lathe camera."""
    return z_value, -x_value


def canonical_turning_tool_type(value: object) -> str:
    """Return a normalized canonical type key for runtime dispatch."""
    return str(value or "").strip().lower()


def positive_float(spec: dict[str, object], key: str, default: float = 0.0) -> float:
    try:
        value = float(spec.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) and value > 0.0 else default


def nonnegative_float(spec: dict[str, object], key: str, default: float = 0.0) -> float:
    try:
        value = float(spec.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) and value >= 0.0 else default


def tip_orientation(spec: dict[str, object], default: int) -> int:
    try:
        orientation = int(spec.get("tipOrientation", default))
    except (TypeError, ValueError):
        return default
    return orientation if orientation in range(1, 10) else default


def default_groove_orientation(application: str) -> int:
    return 2 if application == "id" else 3


def allowed_groove_orientations(application: str) -> tuple[int, ...]:
    if application == "od":
        return (3, 4)
    if application == "id":
        return (1, 2)
    if application == "face":
        return (2, 3)
    return ()


def normalize_groove_orientation(spec: dict[str, object], application: str | None = None) -> int:
    application = tool_application(spec, application)
    allowed = allowed_groove_orientations(application)
    default = default_groove_orientation(application)
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
    points = stock_insert_points(length, insert_angle, edge_angle, internal=internal)
    if orientation == 9:
        center_x = (min(x for x, _z in points) + max(x for x, _z in points)) * 0.5
        center_z = (min(z for _x, z in points) + max(z for _x, z in points)) * 0.5
        return tuple((x - center_x, z - center_z) for x, z in points)
    expected = 2 if internal else 3
    angle = ORIENTATION_SCREEN_ANGLES.get(orientation, ORIENTATION_SCREEN_ANGLES[expected])
    base_angle = ORIENTATION_SCREEN_ANGLES[expected]
    return _rotate_polygon(points, angle - base_angle)


def _rotate_polygon(
    points: tuple[tuple[float, float], ...],
    angle_degrees: float,
) -> tuple[tuple[float, float], ...]:
    angle = math.radians(angle_degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return tuple((x_value * cosine - z_value * sine, x_value * sine + z_value * cosine) for x_value, z_value in points)


def _align_trace_direction(
    points: tuple[tuple[float, float], ...],
    screen_angle_degrees: float,
) -> tuple[tuple[float, float], ...]:
    """Rotate a symmetric insert so its programmed point faces an exact screen direction."""
    center_x = (min(x for x, _z in points) + max(x for x, _z in points)) * 0.5
    center_z = (min(z for _x, z in points) + max(z for _x, z in points)) * 0.5
    if math.hypot(center_x, center_z) <= EPS:
        return points

    trace_angle = math.radians(screen_angle_degrees)
    target_center_x = -math.sin(trace_angle)
    target_center_z = -math.cos(trace_angle)
    current_angle = math.atan2(center_z, center_x)
    target_angle = math.atan2(target_center_z, target_center_x)
    return _rotate_polygon(points, math.degrees(target_angle - current_angle))


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


def stock_triangle_points(
    length: float,
    edge_angle: float,
    *,
    internal: bool,
) -> tuple[tuple[float, float], ...]:
    """Return an equilateral triangular insert with its programmed tip at the origin."""
    radial_sign = -1.0 if internal else 1.0
    main_angle = math.radians(edge_angle)
    other_angle = math.radians(edge_angle + 60.0)
    main = (
        radial_sign * length * math.cos(main_angle),
        length * math.sin(main_angle),
    )
    other = (
        radial_sign * length * math.cos(other_angle),
        length * math.sin(other_angle),
    )
    return ((0.0, 0.0), main, other)


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
    application: str | None = None,
) -> tuple[tuple[float, float], ...] | None:
    """Return the local X/Z cutting silhouette relative to the programmed point."""
    tool_type = canonical_turning_tool_type(spec.get("type"))
    application = tool_application(spec, application)
    scale = max(3.0, min(12.0, stock_diameter * 0.08))
    polygon = None
    if tool_type == "thread":
        length = positive_float(spec, "insertLength", 12.0)
        tip_width = min(positive_float(spec, "threadTipWidth", 0.8), length * 0.8)
        thread_angle = min(179.0, max(1.0, positive_float(spec, "threadAngle", 60.0)))
        corner_radius = nonnegative_float(spec, "threadCornerRadius", 0.1)
        half_angle = math.radians(thread_angle * 0.5)
        body_depth = length * 0.75
        body_half_width = min(length * 0.5, tip_width * 0.5 + body_depth * math.tan(half_angle))
        local = (
            (0.0, -tip_width * 0.5),
            (body_depth, -body_half_width),
            (body_depth, body_half_width),
            (0.0, tip_width * 0.5),
        )
        local = rounded_polygon(local, corner_radius)
        canonical = _rotate_polygon(local, 45.0)
        orientation = tip_orientation(spec, 3)
        if orientation == 9:
            center_x = (min(x for x, _z in canonical) + max(x for x, _z in canonical)) * 0.5
            center_z = (min(z for _x, z in canonical) + max(z for _x, z in canonical)) * 0.5
            polygon = tuple((x - center_x, z - center_z) for x, z in canonical)
        else:
            rotation = ORIENTATION_SCREEN_ANGLES.get(orientation, ORIENTATION_SCREEN_ANGLES[3])
            polygon = _rotate_polygon(canonical, rotation - ORIENTATION_SCREEN_ANGLES[3])
    elif tool_type == "round":
        radius = positive_float(spec, "insertLength", 12.0) * 0.5
        direction_x, direction_z = TIP_DIRECTIONS[tip_orientation(spec, 3)]
        direction_length = math.hypot(direction_x, direction_z)
        if direction_length > EPS:
            center_x = -direction_x / direction_length * radius
            center_z = -direction_z / direction_length * radius
        else:
            center_x = 0.0
            center_z = 0.0
        polygon = tuple(
            (
                center_x + radius * math.cos(2.0 * math.pi * step / 32),
                center_z + radius * math.sin(2.0 * math.pi * step / 32),
            )
            for step in range(32)
        )
    elif tool_type in INSERT_GEOMETRY:
        insert_angle, edge_angle = INSERT_GEOMETRY[tool_type]
        internal = application == "id"
        expected_orientation = 2 if internal else 3
        orientation = tip_orientation(spec, expected_orientation)
        nose = positive_float(spec, "noseRadius")
        default_length = 16.0 if tool_type == "diamond_35" else 12.0
        length = positive_float(spec, "insertLength", default_length)
        if nose > EPS:
            minimum_length = nose / max(math.tan(math.radians(insert_angle * 0.5)), EPS) / 0.45
            length = max(length, minimum_length)
        if tool_type == "triangle":
            sharp = stock_triangle_points(length, edge_angle, internal=internal)
        else:
            sharp = stock_insert_points(length, insert_angle, edge_angle, internal=internal)
        if nose > EPS:
            rounded = rounded_polygon(sharp, nose)
            nose_center = tip_fillet_center(sharp, nose)
            target_center = (-nose if internal else nose, nose)
            shift_x = target_center[0] - nose_center[0]
            shift_z = target_center[1] - nose_center[1]
            canonical = tuple((x_value + shift_x, z_value + shift_z) for x_value, z_value in rounded)
        else:
            canonical = sharp
        if orientation == expected_orientation:
            polygon = canonical
        elif orientation == 9:
            center_x = (min(x for x, _z in canonical) + max(x for x, _z in canonical)) * 0.5
            center_z = (min(z for _x, z in canonical) + max(z for _x, z in canonical)) * 0.5
            polygon = tuple((x - center_x, z - center_z) for x, z in canonical)
        elif tool_type == "diamond_35" and application == "id" and orientation == 1:
            # P1 is the screen-horizontal mirror of the accepted P2 geometry.
            polygon = tuple((x, -z) for x, z in reversed(canonical))
        elif tool_type == "diamond_35" and application == "od" and orientation == 4:
            # P4 is the screen-horizontal mirror of the accepted P3 geometry.
            polygon = tuple((x, -z) for x, z in reversed(canonical))
        elif tool_type == "diamond_35" and application == "od" and orientation == 7:
            polygon = _align_trace_direction(canonical, 180.0)
        elif tool_type == "diamond_35" and application == "id" and orientation in {6, 7, 8}:
            screen_angle = {6: 90.0, 7: 180.0, 8: 270.0}[orientation]
            polygon = _align_trace_direction(canonical, screen_angle)
        else:
            rotation = ORIENTATION_SCREEN_ANGLES[orientation] - ORIENTATION_SCREEN_ANGLES[expected_orientation]
            polygon = _rotate_polygon(canonical, rotation)
    elif tool_type == "groove" and application in {"od", "id"}:
        width = positive_float(spec, "width")
        if width > EPS:
            length = positive_float(spec, "insertLength", max(scale, width * 2.0))
            direction = -1.0 if application == "id" else 1.0
            orientation = normalize_groove_orientation(spec, application)
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
    elif tool_type == "groove" and application == "face":
        width = positive_float(spec, "width", max(1.0, stock_diameter * 0.03))
        length = max(scale * 1.5, width * 2.0)
        orientation = normalize_groove_orientation(spec, application)
        x0, x1 = (0.0, width) if orientation == 2 else (-width, 0.0)
        sharp = (
            (x0, 0.0),
            (x1, 0.0),
            (x1, length),
            (x0, length),
        )
        polygon = rounded_polygon(sharp, positive_float(spec, "noseRadius"))
    return polygon


def display_tool_geometry(spec: dict[str, object], stock_diameter: float, application: str | None = None):
    """Return ``(polygon, preview_depth, cache_key)`` for the OpenGL tool preview."""
    tool_type = canonical_turning_tool_type(spec.get("type"))
    application = tool_application(spec, application)
    scale = max(3.0, min(12.0, stock_diameter * 0.08))
    if tool_type in {"drill", "tap"}:
        diameter = positive_float(spec, "diameter", max(2.0, stock_diameter * 0.1))
        length = positive_float(spec, "length", max(12.0, diameter * 4.0))
        angle = min(179.0, max(1.0, positive_float(spec, "tipAngle", 60.0 if tool_type == "tap" else 118.0)))
        cone = (diameter * 0.5) / math.tan(math.radians(angle * 0.5))
        points = (
            (0.0, 0.0),
            (-diameter * 0.5, cone),
            (-diameter * 0.5, length),
            (diameter * 0.5, length),
            (diameter * 0.5, cone),
        )
        return points, max(1.0, diameter * 0.35), (tool_type, diameter, length, angle)
    points = turning_tool_polygon(spec, stock_diameter, application=application)
    if points is None:
        return ((0.0, 0.0), (scale, 0.0), (scale, scale), (0.0, scale)), 1.0, (tool_type, "empty")
    width = positive_float(spec, "width")
    nose = positive_float(spec, "noseRadius")
    orientation = tip_orientation(spec, 1)
    length = positive_float(spec, "insertLength", scale)
    if tool_type == "thread":
        angle = positive_float(spec, "threadAngle", 60.0)
        tip_width = positive_float(spec, "threadTipWidth", 0.8)
        corner_radius = nonnegative_float(spec, "threadCornerRadius", 0.1)
        cache_key = (tool_type, application, length, angle, tip_width, corner_radius, orientation)
    else:
        cache_key = (tool_type, application, width, nose, orientation, length)
    return points, max(1.0, max(width, length, nose) * 0.35), cache_key
