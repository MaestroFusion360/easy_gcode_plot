"""Small user-facing G-code generators used by calculator dialogs."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .formatting import _number, _signed_number
from .types import PocketParameters, PocketPreviewGeometry, Point

MAX_POCKET_PATH_POINTS = 20_000

# Maximum nominal chord error relative to cutter diameter, in the input units.
# It applies to polylines used for pocket spirals, not to native G2/G3 arcs.
SPIRAL_CHORD_ERROR_TOOL_FRACTION = 0.0025
MIN_SPIRAL_SAMPLES_PER_TURN = 32


def _path_limit_error() -> ValueError:
    return ValueError("Pocket path exceeds the 20,000-point limit; increase stepover or Z step.")


def _step_count(distance: float, step: float) -> int:
    """Count positive steps with a small, dimensionless float-boundary tolerance."""
    if distance <= 0:
        return 0
    quotient = distance / step
    if not math.isfinite(quotient) or quotient > MAX_POCKET_PATH_POINTS + 1:
        raise _path_limit_error()
    nearest = round(quotient)
    if nearest > 0 and math.isclose(quotient, nearest, rel_tol=0.0, abs_tol=1e-8):
        count = nearest
    else:
        count = math.ceil(quotient)
    if count > MAX_POCKET_PATH_POINTS:
        raise _path_limit_error()
    return max(1, count)


def _depths(start: float, end: float, step: float) -> list[float]:
    if end >= start:
        return [end]
    count = _step_count(start - end, step)
    # Index arithmetic avoids accumulated subtraction error; the final level
    # is always exactly the requested target, including in near-integer cases.
    return [start - index * step for index in range(1, count)] + [end]


def _xy(x: float, y: float) -> str:
    return f"X{_number(x)} Y{_number(y)}"


def _hxy(x: float, y: float) -> str:
    """Klartext coordinate pair; iTNC requires an explicit sign on each axis."""
    return f"X{_signed_number(x)} Y{_signed_number(y)}"


def _samples_per_turn(radius: float, tool_diameter: float) -> int:
    """Angular sampling from the largest local arc's nominal chord error."""
    if radius <= 0:
        return MIN_SPIRAL_SAMPLES_PER_TURN
    tolerance = max(tool_diameter * SPIRAL_CHORD_ERROR_TOOL_FRACTION, 1e-15)
    if tolerance >= radius:
        return MIN_SPIRAL_SAMPLES_PER_TURN
    angle = 2.0 * math.acos(1.0 - tolerance / radius)
    if angle <= 0:
        raise _path_limit_error()
    samples = max(MIN_SPIRAL_SAMPLES_PER_TURN, math.ceil(math.tau / angle))
    # Align samples with the eight straight/arc portions of the rectangle.
    samples = math.ceil(samples / 8) * 8
    if samples > MAX_POCKET_PATH_POINTS:
        raise _path_limit_error()
    return samples


def _circle_spiral_sample_count(params: PocketParameters, radius: float) -> tuple[int, int]:
    turns = max(1, _step_count(radius, params.stepover))
    samples_per_turn = _samples_per_turn(radius, params.tool_diameter)
    count = turns * samples_per_turn
    if count > MAX_POCKET_PATH_POINTS:
        raise _path_limit_error()
    return count, samples_per_turn


def _circle_spiral_points(params: PocketParameters, radius: float) -> list[Point]:
    count, samples_per_turn = _circle_spiral_sample_count(params, radius)
    direction = 1.0 if params.ccw else -1.0
    return [
        (
            params.center_x + radius * index / count * math.cos(direction * math.tau * index / samples_per_turn),
            params.center_y + radius * index / count * math.sin(direction * math.tau * index / samples_per_turn),
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
    count = _step_count(maximum, stepover)
    return [index * stepover for index in range(count - 1, -1, -1)]


def _rectangle_spiral_layout(
    params: PocketParameters, half_w: float, half_h: float, radius: float
) -> tuple[float, int, int]:
    inner_half = min(params.stepover * 0.5, half_w, half_h)
    maximum_offset = max(0.0, min(half_w, half_h) - inner_half)
    turns = max(1, _step_count(maximum_offset, params.stepover))
    samples_per_turn = _samples_per_turn(radius, params.tool_diameter)
    if (turns + 1) * samples_per_turn + 1 > MAX_POCKET_PATH_POINTS:
        raise _path_limit_error()
    return maximum_offset, turns, turns * samples_per_turn


def _rectangle_spiral_points(
    params: PocketParameters,
    half_w: float,
    half_h: float,
    radius: float,
    samples_per_turn: int = 32,
) -> list[Point]:
    inner_half = min(params.stepover * 0.5, half_w, half_h)
    maximum_offset = max(0.0, min(half_w, half_h) - inner_half)
    turns = max(1, _step_count(maximum_offset, params.stepover))
    sample_count = turns * samples_per_turn
    points: list[Point] = []
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
    lines: list[str],
    params: PocketParameters,
    half_w: float,
    half_h: float,
    corner: float,
    *,
    heidenhain: bool = False,
) -> None:
    # Defensive protection for internal callers, in addition to input validation.
    corner = min(max(0.0, corner), half_w, half_h)
    coord = _hxy if heidenhain else _xy
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
        lines.extend(f"{'L' if heidenhain else 'G1'} {coord(*point)}" for point in points)
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
        if heidenhain:
            direction = "DR+" if params.ccw else "DR-"
            lines.append(f"CR {coord(*point)}{suffix} {direction}" if mode == arc else f"L {coord(*point)}")
        else:
            lines.append(f"{mode} {coord(*point)}{suffix}")


def _effective_pocket_geometry(params: PocketParameters) -> tuple[float, float, float]:
    tool_radius = params.tool_diameter / 2.0
    if params.circular:
        radius = params.pocket_diameter / 2.0 - tool_radius - params.stock_xy
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError("Pocket is too small for the selected tool.")
        return radius, radius, radius

    inset = tool_radius + params.stock_xy
    width = params.pocket_width - 2.0 * inset
    height = params.pocket_height - 2.0 * inset
    if not (math.isfinite(width) and math.isfinite(height)) or width <= 0 or height <= 0:
        raise ValueError("Pocket is too small for the selected tool.")
    corner = max(0.0, params.corner_radius - inset)
    return width, height, min(corner, width / 2.0, height / 2.0)


def _finish_geometry(params: PocketParameters) -> tuple[float, float, float]:
    return _effective_pocket_geometry(replace(params, stock_xy=0.0))


@dataclass(frozen=True, slots=True)
class _CircleContour:
    radius: float
    spiral: bool = False


@dataclass(frozen=True, slots=True)
class _RectangleContour:
    half_width: float
    half_height: float
    corner_radius: float
    spiral: bool = False


@dataclass(frozen=True, slots=True)
class _CenterlineContour:
    """Clear the otherwise-uncovered center of a concentric rectangle pocket."""

    axis: str
    extent: float


_PocketContour = _CircleContour | _RectangleContour | _CenterlineContour


@dataclass(frozen=True, slots=True)
class _PocketPlan:
    width: float
    height: float
    depths: tuple[float, ...]
    contours: tuple[_PocketContour, ...]


def _pocket_contours(
    params: PocketParameters, width: float, height: float, radius: float
) -> tuple[_PocketContour, ...]:
    """An identical ordered XY path plan for preview and NC, independent of Z."""
    contours: list[_PocketContour]
    if params.circular:
        if params.spiral:
            contours = [_CircleContour(width, spiral=True)]
        else:
            count = _step_count(width, params.stepover)
            contours = [_CircleContour(min(width, index * params.stepover)) for index in range(1, count)]
            contours.append(_CircleContour(width))
    else:
        half_w, half_h = width / 2.0, height / 2.0
        if params.spiral:
            contours = [_RectangleContour(half_w, half_h, radius, spiral=True)]
        else:
            offsets = _rectangle_offsets(half_w, half_h, params.stepover)
            contours = []
            # The innermost rectangular loop can leave a long central strip:
            # unlike circles, a rectangle does not shrink to the center when
            # its shorter half-dimension is exhausted.
            inner_w, inner_h = half_w - offsets[0], half_h - offsets[0]
            if min(inner_w, inner_h) > params.tool_diameter / 2.0:
                contours.append(
                    _CenterlineContour("x", inner_w) if inner_w >= inner_h else _CenterlineContour("y", inner_h)
                )
            contours.extend(
                _RectangleContour(
                    half_w - offset,
                    half_h - offset,
                    max(0.0, radius - offset),
                )
                for offset in offsets
                if half_w - offset > 0 and half_h - offset > 0
            )
    if params.correction:
        # An intentional finishing/spring pass, even when stock_xy == 0.
        finish_width, finish_height, finish_radius = _finish_geometry(params)
        contours.append(
            _CircleContour(finish_width)
            if params.circular
            else _RectangleContour(finish_width / 2.0, finish_height / 2.0, finish_radius)
        )
    return tuple(contours)


def _validate_pocket_parameters(params: PocketParameters) -> None:
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
    if params.stepover > params.tool_diameter:
        raise ValueError("Stepover must not exceed the tool diameter; unmachined stock could remain.")
    if not params.circular:
        if params.corner_radius < 0:
            raise ValueError("Rectangle corner radius must not be negative.")


def _contour_path_sizes(params: PocketParameters, contour: _PocketContour) -> tuple[int, int]:
    preview_points = 65  # A closed 64-segment outline in the live preview.
    if isinstance(contour, _CenterlineContour):
        return 4, 3
    if isinstance(contour, _CircleContour):
        nc_points = 3  # Lead-in plus two native semicircular arcs.
        if contour.spiral:
            samples, _ = _circle_spiral_sample_count(params, contour.radius)
            preview_points += samples
            nc_points += samples
    else:
        nc_points = 9 if contour.corner_radius > 0 else 5
        if contour.spiral:
            _offset, turns, samples = _rectangle_spiral_layout(
                params, contour.half_width, contour.half_height, contour.corner_radius
            )
            initial_loop_points = samples // turns + 1
            preview_points += samples + initial_loop_points
            nc_points += samples + initial_loop_points
    return preview_points, nc_points


def _validate_pocket(params: PocketParameters) -> _PocketPlan:
    _validate_pocket_parameters(params)
    target_z = params.z_end + params.stock_z
    if not math.isfinite(target_z) or params.z_reference < params.z_start or target_z >= params.z_start:
        raise ValueError("Z reference must be at or above Z start, and Z end must be below Z start.")

    width, height, radius = _effective_pocket_geometry(params)
    depths = tuple(_depths(params.z_start, target_z, params.z_step))
    radial_span = width if params.circular else min(width, height) / 2.0
    _step_count(radial_span, params.stepover)  # Refuse pathological counts before allocation.
    contours = _pocket_contours(params, width, height, radius)

    preview_per_depth = 0
    nc_per_depth = 0
    for contour in contours:
        preview_points, nc_points = _contour_path_sizes(params, contour)
        preview_per_depth += preview_points
        nc_per_depth += nc_points
        if max(preview_per_depth, nc_per_depth) * len(depths) > MAX_POCKET_PATH_POINTS:
            raise _path_limit_error()

    if (
        max(preview_per_depth * len(depths) + 97, (nc_per_depth + (5 if params.helix else 1)) * len(depths))
        > MAX_POCKET_PATH_POINTS
    ):
        raise _path_limit_error()
    return _PocketPlan(width, height, depths, contours)


def _centerline_points(params: PocketParameters, contour: _CenterlineContour) -> tuple[Point, ...]:
    cx, cy = params.center_x, params.center_y
    if contour.axis == "x":
        return ((cx, cy), (cx + contour.extent, cy), (cx - contour.extent, cy), (cx, cy))
    return ((cx, cy), (cx, cy + contour.extent), (cx, cy - contour.extent), (cx, cy))


def _contour_preview(params: PocketParameters, contour: _PocketContour) -> tuple[tuple[Point, ...], ...]:
    if isinstance(contour, _CenterlineContour):
        return (_centerline_points(params, contour),)
    if isinstance(contour, _CircleContour):
        loop = tuple(_circle_loop_points(params, contour.radius))
        if contour.spiral:
            return (tuple(_circle_spiral_points(params, contour.radius)), loop)
        return (loop,)
    loop = tuple(
        _rounded_rectangle_points(
            params.center_x,
            params.center_y,
            contour.half_width,
            contour.half_height,
            contour.corner_radius,
            ccw=params.ccw,
        )
    )
    if contour.spiral:
        return (
            tuple(_rectangle_spiral_points(params, contour.half_width, contour.half_height, contour.corner_radius)),
            loop,
        )
    return (loop,)


def _emit_pocket_contour(
    lines: list[str], params: PocketParameters, contour: _PocketContour, *, heidenhain: bool = False
) -> None:
    linear = "L" if heidenhain else "G1"
    coord = _hxy if heidenhain else _xy
    if isinstance(contour, _CenterlineContour):
        for point in _centerline_points(params, contour)[1:]:
            lines.append(f"{linear} {coord(*point)}")
        return
    if isinstance(contour, _CircleContour):
        if contour.spiral:
            for index, point in enumerate(_circle_spiral_points(params, contour.radius)):
                prefix = "L " if heidenhain else "G1 " if index == 0 else ""
                lines.append(prefix + coord(*point))
        else:
            lines.append(f"{linear} {coord(params.center_x + contour.radius, params.center_y)}")
        # Retain two R-defined semicircles for compatibility with the NC fragment contract.
        arc = "CR" if heidenhain else "G3" if params.ccw else "G2"
        direction = (" DR+" if params.ccw else " DR-") if heidenhain else ""
        start_x = params.center_x + contour.radius
        if contour.spiral:
            lines.append(f"{linear} {coord(start_x, params.center_y)}")
        lines.extend(
            (
                f"{arc} {coord(params.center_x - contour.radius, params.center_y)} "
                f"R{_number(contour.radius)}{direction}",
                f"{arc} {coord(start_x, params.center_y)} R{_number(contour.radius)}{direction}",
            )
        )
        return

    if contour.spiral:
        for index, point in enumerate(
            _rectangle_spiral_points(params, contour.half_width, contour.half_height, contour.corner_radius)
        ):
            prefix = "L " if heidenhain else "G1 " if index == 0 else ""
            lines.append(prefix + coord(*point))
    _rectangle_loop_commands(
        lines, params, contour.half_width, contour.half_height, contour.corner_radius, heidenhain=heidenhain
    )


def pocket_preview_geometry(params: PocketParameters) -> PocketPreviewGeometry:
    """Return lightweight XY geometry for the calculator's live preview."""
    plan = _validate_pocket(params)
    if params.circular:
        boundary = tuple(_circle_loop_points(params, params.pocket_diameter / 2.0, 96))
    else:
        boundary = tuple(
            _rounded_rectangle_points(
                params.center_x,
                params.center_y,
                params.pocket_width / 2.0,
                params.pocket_height / 2.0,
                params.corner_radius,
                ccw=params.ccw,
                samples=96,
            )
        )
    paths = tuple(path for contour in plan.contours for path in _contour_preview(params, contour))
    return PocketPreviewGeometry(boundary, paths)


def pocket_program(params: PocketParameters, *, source_dialect: str = "fanuc") -> str:
    """Generate the milling NC fragment exposed by Pocket Calculator."""
    plan = _validate_pocket(params)
    if source_dialect == "heidenhain":
        return _heidenhain_pocket_program(params, plan)
    lines = [f"G0 Z{_number(params.z_reference)} M8", f"G0 {_xy(params.center_x, params.center_y)}"]
    previous_depth = params.z_start
    for depth_index, depth in enumerate(plan.depths):
        if params.helix:
            helix_radius = min(
                params.tool_diameter * 0.2,
                plan.width if params.circular else min(plan.width, plan.height) / 2.0,
            )
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
        for contour in plan.contours:
            _emit_pocket_contour(lines, params, contour)
        previous_depth = depth
        if depth_index < len(plan.depths) - 1:
            lines.append(f"G0 Z{_number(params.z_reference)}")
            lines.append(f"G0 {_xy(params.center_x, params.center_y)}")
    lines.append(f"G0 Z{_number(params.z_reference)}")
    return "\n".join(lines)


def _heidenhain_pocket_program(params: PocketParameters, plan: _PocketPlan) -> str:
    """Write the calculator's own path directly as Klartext, without a postprocessor."""

    def z(value: float) -> str:
        return f"Z{_signed_number(value)}"

    lines = [f"L {z(params.z_reference)} R0 FMAX M8", f"L {_hxy(params.center_x, params.center_y)} FMAX"]
    previous_depth = params.z_start
    direction = "DR+" if params.ccw else "DR-"
    for depth_index, depth in enumerate(plan.depths):
        if params.helix:
            radius = min(
                params.tool_diameter * 0.2, plan.width if params.circular else min(plan.width, plan.height) / 2.0
            )
            angle = 360 if params.ccw else -360
            lines.extend(
                (
                    f"L {z(previous_depth)} FMAX",
                    f"L {_hxy(params.center_x + radius, params.center_y)} F{_number(params.feed)}",
                    f"CC {_hxy(params.center_x, params.center_y)}",
                    f"CP IPA{_signed_number(angle)} {z(depth)} {direction} F{_number(params.feed)}",
                    f"L {_hxy(params.center_x, params.center_y)} F{_number(params.feed)}",
                )
            )
        else:
            lines.append(f"L {z(depth)} F{_number(params.feed)}")
        for contour in plan.contours:
            _emit_pocket_contour(lines, params, contour, heidenhain=True)
        previous_depth = depth
        if depth_index < len(plan.depths) - 1:
            lines.extend((f"L {z(params.z_reference)} FMAX", f"L {_hxy(params.center_x, params.center_y)} FMAX"))
    lines.append(f"L {z(params.z_reference)} R0 FMAX")
    return "\n".join(lines)
