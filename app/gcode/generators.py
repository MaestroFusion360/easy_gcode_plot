"""Small user-facing G-code generators used by calculator dialogs."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

Point = tuple[float, float]
MAX_POCKET_PATH_POINTS = 20_000


def _number(value: float, decimals: int = 3) -> str:
    if abs(value) < 0.5 * 10**-decimals:
        value = 0.0
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".") or "0"


def hole_circle_points(*, diameter, start_angle, center_x, center_y, count, ccw=True) -> list[Point]:
    radius = diameter / 2.0
    direction = 1.0 if ccw else -1.0
    return [
        (
            center_x + radius * math.cos(math.radians(start_angle) + direction * math.tau * index / count),
            center_y + radius * math.sin(math.radians(start_angle) + direction * math.tau * index / count),
        )
        for index in range(count)
    ]


def hole_circle(*, diameter, start_angle, center_x, center_y, count, ccw=True) -> str:
    return "\n".join(
        f"X{_number(x_value)} Y{_number(y_value)}"
        for x_value, y_value in hole_circle_points(
            diameter=diameter,
            start_angle=start_angle,
            center_x=center_x,
            center_y=center_y,
            count=count,
            ccw=ccw,
        )
    )


def hole_grid_points(*, start_x, start_y, step_x, step_y, count_x, count_y) -> list[Point]:
    points = []
    for row in range(count_y):
        columns = range(count_x) if row % 2 == 0 else range(count_x - 1, -1, -1)
        for column in columns:
            points.append((start_x + column * step_x, start_y + row * step_y))
    return points


def hole_grid(*, start_x, start_y, step_x, step_y, count_x, count_y) -> str:
    return "\n".join(
        f"X{_number(x_value)} Y{_number(y_value)}"
        for x_value, y_value in hole_grid_points(
            start_x=start_x,
            start_y=start_y,
            step_x=step_x,
            step_y=step_y,
            count_x=count_x,
            count_y=count_y,
        )
    )


@dataclass(frozen=True, slots=True)
class PocketParameters:
    tool_diameter: float = 10.0
    pocket_diameter: float = 100.0
    pocket_width: float = 100.0
    pocket_height: float = 100.0
    corner_radius: float = 0.0
    stepover: float = 5.0
    center_x: float = 0.0
    center_y: float = 0.0
    z_reference: float = 10.0
    z_start: float = 0.0
    z_end: float = -2.0
    z_step: float = 1.0
    stock_xy: float = 0.0
    stock_z: float = 0.0
    feed: float = 1000.0
    circular: bool = True
    ccw: bool = True
    spiral: bool = False
    correction: bool = False
    helix: bool = False


@dataclass(frozen=True, slots=True)
class PocketPreviewGeometry:
    boundary: tuple[Point, ...]
    paths: tuple[tuple[Point, ...], ...]


def _depths(start: float, end: float, step: float) -> list[float]:
    target = end
    values = []
    current = start - step
    while current >= target:
        values.append(current)
        current -= step
    if not values or not math.isclose(values[-1], target, abs_tol=1e-9):
        values.append(target)
    return values


def _xy(x: float, y: float) -> str:
    return f"X{_number(x)} Y{_number(y)}"


def _circle_spiral_points(params: PocketParameters, radius: float) -> list[Point]:
    count = max(120, math.ceil(radius / params.stepover) * 20)
    direction = 1.0 if params.ccw else -1.0
    return [
        (
            params.center_x + radius * index / count * math.cos(direction * math.tau * index / 20.0),
            params.center_y + radius * index / count * math.sin(direction * math.tau * index / 20.0),
        )
        for index in range(1, count + 1)
    ]


def _circle_loop_points(params: PocketParameters, radius: float, samples: int = 64) -> list[Point]:
    direction = 1.0 if params.ccw else -1.0
    return [
        (
            params.center_x + radius * math.cos(direction * math.tau * index / samples),
            params.center_y + radius * math.sin(direction * math.tau * index / samples),
        )
        for index in range(samples + 1)
    ]


def _circle_passes(lines: list[str], params: PocketParameters, radius: float) -> None:
    arc = "G3" if params.ccw else "G2"
    if params.spiral:
        points = _circle_spiral_points(params, radius)
        for index, point in enumerate(points):
            lines.append(("G1 " if index == 0 else "") + _xy(*point))
        start_x = params.center_x + radius
        lines.extend(
            (
                f"G1 {_xy(start_x, params.center_y)}",
                f"{arc} {_xy(2 * params.center_x - start_x, params.center_y)} R{_number(radius)}",
                f"{arc} {_xy(start_x, params.center_y)} R{_number(radius)}",
            )
        )
        return

    for current in [
        min(radius, index * params.stepover) for index in range(1, math.ceil(radius / params.stepover) + 1)
    ]:
        x = params.center_x + current
        y = params.center_y
        lines.extend(
            (
                f"G1 {_xy(x, y)}",
                f"{arc} {_xy(2 * params.center_x - x, 2 * params.center_y - y)} R{_number(current)}",
                f"{arc} {_xy(x, y)} R{_number(current)}",
            )
        )


def _rounded_rectangle_point(
    center_x: float,
    center_y: float,
    half_w: float,
    half_h: float,
    corner: float,
    phase: float,
    *,
    ccw: bool,
) -> Point:
    phase = phase % 1.0 if ccw else (-phase) % 1.0
    corner = min(max(0.0, corner), half_w, half_h)
    position = phase * 8.0
    segment = min(7, int(position))
    t = position - segment

    if segment == 0:
        point = center_x + half_w, center_y - half_h + corner + t * (2 * half_h - 2 * corner)
    elif segment == 1:
        angle = t * math.pi / 2.0
        point = (
            center_x + half_w - corner + corner * math.cos(angle),
            center_y + half_h - corner + corner * math.sin(angle),
        )
    elif segment == 2:
        point = center_x + half_w - corner - t * (2 * half_w - 2 * corner), center_y + half_h
    elif segment == 3:
        angle = math.pi / 2.0 + t * math.pi / 2.0
        point = (
            center_x - half_w + corner + corner * math.cos(angle),
            center_y + half_h - corner + corner * math.sin(angle),
        )
    elif segment == 4:
        point = center_x - half_w, center_y + half_h - corner - t * (2 * half_h - 2 * corner)
    elif segment == 5:
        angle = math.pi + t * math.pi / 2.0
        point = (
            center_x - half_w + corner + corner * math.cos(angle),
            center_y - half_h + corner + corner * math.sin(angle),
        )
    elif segment == 6:
        point = center_x - half_w + corner + t * (2 * half_w - 2 * corner), center_y - half_h
    else:
        angle = 3.0 * math.pi / 2.0 + t * math.pi / 2.0
        point = (
            center_x + half_w - corner + corner * math.cos(angle),
            center_y - half_h + corner + corner * math.sin(angle),
        )
    return point


def _rounded_rectangle_points(
    center_x: float,
    center_y: float,
    half_w: float,
    half_h: float,
    corner: float,
    *,
    ccw: bool,
    samples: int = 64,
) -> list[Point]:
    return [
        _rounded_rectangle_point(center_x, center_y, half_w, half_h, corner, index / samples, ccw=ccw)
        for index in range(samples + 1)
    ]


def _rectangle_offsets(half_w: float, half_h: float, stepover: float) -> list[float]:
    maximum = min(half_w, half_h)
    return list(reversed([index * stepover for index in range(math.ceil(maximum / stepover))]))


def _rectangle_spiral_points(
    params: PocketParameters, half_w: float, half_h: float, radius: float, samples_per_turn: int = 32
) -> list[Point]:
    inner_half = min(params.stepover * 0.5, half_w, half_h)
    maximum_offset = max(0.0, min(half_w, half_h) - inner_half)
    turns = max(1, math.ceil(maximum_offset / params.stepover))
    sample_count = turns * samples_per_turn
    points = []
    for index in range(sample_count + 1):
        progress = index / sample_count
        offset = maximum_offset * (1.0 - progress)
        current_w = half_w - offset
        current_h = half_h - offset
        current_corner = max(0.0, radius - offset)
        point = _rounded_rectangle_point(
            params.center_x,
            params.center_y,
            current_w,
            current_h,
            current_corner,
            progress * turns,
            ccw=params.ccw,
        )
        if not points or not (math.isclose(point[0], points[-1][0]) and math.isclose(point[1], points[-1][1])):
            points.append(point)
    return points


def _rectangle_loop_commands(
    lines: list[str], params: PocketParameters, half_w: float, half_h: float, corner: float
) -> None:
    right = params.center_x + half_w
    left = params.center_x - half_w
    top = params.center_y + half_h
    bottom = params.center_y - half_h
    if corner <= 0:
        points = (
            ((right, bottom), (right, top), (left, top), (left, bottom), (right, bottom))
            if params.ccw
            else ((right, bottom), (left, bottom), (left, top), (right, top), (right, bottom))
        )
        lines.extend(f"G1 {_xy(*point)}" for point in points)
        return

    arc = "G3" if params.ccw else "G2"
    if params.ccw:
        commands = (
            ("G1", (right, bottom + corner)),
            ("G1", (right, top - corner)),
            (arc, (right - corner, top)),
            ("G1", (left + corner, top)),
            (arc, (left, top - corner)),
            ("G1", (left, bottom + corner)),
            (arc, (left + corner, bottom)),
            ("G1", (right - corner, bottom)),
            (arc, (right, bottom + corner)),
        )
    else:
        commands = (
            ("G1", (right, bottom + corner)),
            (arc, (right - corner, bottom)),
            ("G1", (left + corner, bottom)),
            (arc, (left, bottom + corner)),
            ("G1", (left, top - corner)),
            (arc, (left + corner, top)),
            ("G1", (right - corner, top)),
            (arc, (right, top - corner)),
            ("G1", (right, bottom + corner)),
        )
    for mode, point in commands:
        suffix = f" R{_number(corner)}" if mode == arc else ""
        lines.append(f"{mode} {_xy(*point)}{suffix}")


def _rectangle(lines: list[str], params: PocketParameters, width: float, height: float, radius: float) -> None:
    half_w, half_h = width / 2.0, height / 2.0
    radius = min(max(0.0, radius), half_w, half_h)
    if params.spiral:
        for index, point in enumerate(_rectangle_spiral_points(params, half_w, half_h, radius)):
            lines.append(("G1 " if index == 0 else "") + _xy(*point))
        _rectangle_loop_commands(lines, params, half_w, half_h, radius)
        return

    for offset in _rectangle_offsets(half_w, half_h, params.stepover):
        current_w = half_w - offset
        current_h = half_h - offset
        if current_w <= 0 or current_h <= 0:
            continue
        _rectangle_loop_commands(lines, params, current_w, current_h, max(0.0, radius - offset))


def _effective_pocket_geometry(params: PocketParameters) -> tuple[float, float, float]:
    tool_radius = params.tool_diameter / 2.0
    if params.circular:
        radius = params.pocket_diameter / 2.0 - tool_radius - params.stock_xy
        if radius <= 0:
            raise ValueError("Pocket is too small for the selected tool.")
        return radius, radius, radius

    width = params.pocket_width - 2 * (tool_radius + params.stock_xy)
    height = params.pocket_height - 2 * (tool_radius + params.stock_xy)
    if width <= 0 or height <= 0:
        raise ValueError("Pocket is too small for the selected tool.")
    return width, height, max(0.0, params.corner_radius - tool_radius - params.stock_xy)


def _validate_pocket(params: PocketParameters) -> tuple[float, float, float, float, int]:
    values = (
        params.tool_diameter,
        params.pocket_diameter,
        params.pocket_width,
        params.pocket_height,
        params.corner_radius,
        params.stepover,
        params.center_x,
        params.center_y,
        params.z_reference,
        params.z_start,
        params.z_end,
        params.z_step,
        params.stock_xy,
        params.stock_z,
        params.feed,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Pocket parameters must be finite.")
    if min(params.tool_diameter, params.stepover, params.z_step, params.feed) <= 0:
        raise ValueError("Tool diameter, stepover, Z step and feed must be positive.")
    if params.stock_xy < 0 or params.stock_z < 0:
        raise ValueError("Stock allowances must not be negative.")
    target_z = params.z_end + params.stock_z
    if params.z_reference < params.z_start or target_z >= params.z_start:
        raise ValueError("Z reference must be at or above Z start, and Z end must be below Z start.")
    width, height, radius = _effective_pocket_geometry(params)
    depth_count = math.ceil((params.z_start - target_z) / params.z_step)
    radial_count = math.ceil((width if params.circular else min(width, height) / 2.0) / params.stepover)
    points_per_depth = (max(120, radial_count * 40) + 65) if params.spiral else radial_count * 65
    if (points_per_depth + (65 if params.correction else 0)) * depth_count > MAX_POCKET_PATH_POINTS:
        raise ValueError("Pocket path exceeds the 20,000-point limit; increase stepover or Z step.")
    return width, height, radius, target_z, depth_count


def _finish_geometry(params: PocketParameters) -> tuple[float, float, float]:
    return _effective_pocket_geometry(replace(params, stock_xy=0.0))


def pocket_preview_geometry(params: PocketParameters) -> PocketPreviewGeometry:
    """Return lightweight XY geometry for the calculator's live preview."""
    width, height, radius, _target_z, _depth_count = _validate_pocket(params)

    if params.circular:
        pocket_radius = params.pocket_diameter / 2.0
        boundary = tuple(_circle_loop_points(params, pocket_radius, 96))
        if params.spiral:
            paths = (tuple(_circle_spiral_points(params, width)), tuple(_circle_loop_points(params, width)))
        else:
            radii = [min(width, index * params.stepover) for index in range(1, math.ceil(width / params.stepover) + 1)]
            paths = tuple(tuple(_circle_loop_points(params, current)) for current in radii)
        if params.correction:
            finish_width, _, _ = _finish_geometry(params)
            paths += (tuple(_circle_loop_points(params, finish_width)),)
        return PocketPreviewGeometry(boundary, paths)

    boundary = tuple(
        _rounded_rectangle_points(
            params.center_x,
            params.center_y,
            params.pocket_width / 2.0,
            params.pocket_height / 2.0,
            min(max(0.0, params.corner_radius), params.pocket_width / 2.0, params.pocket_height / 2.0),
            ccw=params.ccw,
            samples=96,
        )
    )
    half_w, half_h = width / 2.0, height / 2.0
    if params.spiral:
        paths = (
            tuple(_rectangle_spiral_points(params, half_w, half_h, radius)),
            tuple(
                _rounded_rectangle_points(
                    params.center_x, params.center_y, half_w, half_h, radius, ccw=params.ccw, samples=64
                )
            ),
        )
    else:
        paths = tuple(
            tuple(
                _rounded_rectangle_points(
                    params.center_x,
                    params.center_y,
                    half_w - offset,
                    half_h - offset,
                    max(0.0, radius - offset),
                    ccw=params.ccw,
                )
            )
            for offset in _rectangle_offsets(half_w, half_h, params.stepover)
            if half_w - offset > 0 and half_h - offset > 0
        )
    if params.correction:
        finish_width, finish_height, finish_radius = _finish_geometry(params)
        paths += (
            tuple(
                _rounded_rectangle_points(
                    params.center_x,
                    params.center_y,
                    finish_width / 2.0,
                    finish_height / 2.0,
                    finish_radius,
                    ccw=params.ccw,
                )
            ),
        )
    return PocketPreviewGeometry(boundary, paths)


def pocket_program(params: PocketParameters) -> str:
    """Generate the standalone milling fragment exposed by Pocket Calculator."""
    width, height, radius, target_z, _depth_count = _validate_pocket(params)
    lines = [f"G0 Z{_number(params.z_reference)} M8", f"G0 {_xy(params.center_x, params.center_y)}"]
    depths = _depths(params.z_start, target_z, params.z_step)
    previous_depth = params.z_start
    for depth_index, depth in enumerate(depths):
        if params.helix:
            helix_radius = min(params.tool_diameter * 0.2, width if params.circular else min(width, height) / 2.0)
            arc = "G3" if params.ccw else "G2"
            lines.extend(
                (
                    f"G0 Z{_number(previous_depth)}",
                    f"G1 {_xy(params.center_x + helix_radius, params.center_y)} F{_number(params.feed)}",
                    f"{arc} {_xy(params.center_x - helix_radius, params.center_y)} "
                    f"Z{_number((previous_depth + depth) / 2.0)} R{_number(helix_radius)}",
                    f"{arc} {_xy(params.center_x + helix_radius, params.center_y)} "
                    f"Z{_number(depth)} R{_number(helix_radius)}",
                    f"G1 {_xy(params.center_x, params.center_y)}",
                )
            )
        else:
            lines.append(f"G1 Z{_number(depth)} F{_number(params.feed)}")
        if params.circular:
            _circle_passes(lines, params, width)
        else:
            _rectangle(lines, params, width, height, radius)
        if params.correction:
            finish_width, finish_height, finish_radius = _finish_geometry(params)
            if params.circular:
                _circle_passes(lines, replace(params, spiral=False, stepover=finish_width), finish_width)
            else:
                _rectangle_loop_commands(lines, params, finish_width / 2.0, finish_height / 2.0, finish_radius)
        previous_depth = depth
        if depth_index < len(depths) - 1:
            lines.append(f"G0 Z{_number(params.z_reference)}")
            lines.append(f"G0 {_xy(params.center_x, params.center_y)}")
    lines.append(f"G0 Z{_number(params.z_reference)}")
    return "\n".join(lines)
