"""G76 multi-pass threading-cycle expansion."""

from __future__ import annotations

import math

from ...api.resources import SemanticError, checkpoint, require_progress
from ...frontend.model import Motion, Point2
from ...frontend.program import radius_to_diameter
from .common import add_motion, add_motion_with_meta

_G76_TOOL_ANGLES = frozenset({0, 29, 30, 55, 60, 80})


def _parse_g76_packed_p(packed_p: int) -> tuple[int, int, int]:
    """Decode FANUC two-line G76 P(m)(r)(a): finish passes, chamfer, angle."""
    value = abs(int(packed_p))
    finish_passes = max(0, min(99, value // 10000))
    chamfer_tenths = max(0, min(99, (value // 100) % 100))
    tool_angle = max(0, min(99, value % 100))
    return finish_passes, chamfer_tenths, tool_angle


def _parse_g76_finish_passes(packed_p: int) -> int:
    return _parse_g76_packed_p(packed_p)[0]


def _g76_infeed_shift(remaining_rad: float, tool_angle: int, direction_z: float) -> float:
    """Return the axial single-edge infeed offset for one radial pass depth."""
    if tool_angle not in _G76_TOOL_ANGLES:
        raise SemanticError(
            "UNSUPPORTED_G76_TOOL_ANGLE",
            f"G76 tool angle must be one of {sorted(_G76_TOOL_ANGLES)} degrees; got {tool_angle}",
            "unsupported",
        )
    if tool_angle == 0:
        return 0.0
    return -direction_z * max(0.0, remaining_rad) * math.tan(math.radians(tool_angle / 2.0))


def _g76_pass_z(total_rad, actual_rad, tool_angle, direction_z, stock_z, target_z) -> tuple[float, float]:
    shift = _g76_infeed_shift(total_rad - actual_rad, tool_angle, direction_z)
    return stock_z + shift, target_z + shift


def _g76_constant_area_depths(
    total_rad: float,
    first_rad: float,
    min_increment_rad: float,
    finish_allow_rad: float,
    finish_passes: int,
) -> list[float]:
    """Return monotonically increasing radial depths for a FANUC-style G76.

    FANUC's multi-pass threading cycle uses a decreasing depth of cut / roughly
    constant chip-area progression.  The commonly documented relationship is
    based on ``Q(first) * sqrt(pass_no)`` with the first-block Q acting as the
    minimum radial increment.  The final R allowance is removed at the finish
    depth and P's leading digits request spring/finish passes.
    """
    total = max(0.0, float(total_rad))
    if total <= 1e-12:
        return []
    first = max(1e-9, min(abs(float(first_rad)), total))
    min_inc = max(0.0, abs(float(min_increment_rad)))
    finish_allow = max(0.0, min(abs(float(finish_allow_rad)), total))
    rough_target = max(0.0, total - finish_allow)

    depths: list[float] = []
    if rough_target > 1e-12:
        depth = min(first, rough_target)
        depths.append(depth)
        pass_no = 2
        while depth < rough_target - 1e-9:
            checkpoint("cycle_iterations")
            if pass_no >= 10000:
                raise SemanticError("RESOURCE_LIMIT", "G76 exceeds 10000 passes", "resource_limit")
            nominal = first * math.sqrt(float(pass_no))
            candidate = max(nominal, depth + min_inc) if min_inc > 0 else nominal
            candidate = min(rough_target, candidate)
            require_progress(depth, candidate)
            depths.append(candidate)
            depth = candidate
            pass_no += 1

    # The commanded X is the final thread diameter. FANUC P(m) is the total
    # repetitive count of the final finishing cycle; when m=0 the control still
    # performs one final cycle.  Do not add an extra uncommanded spring pass.
    if not depths or depths[-1] < total - 1e-9:
        depths.append(total)
    requested_final_count = max(1, int(finish_passes))
    existing_final_count = 0
    for value in reversed(depths):
        if abs(value - total) <= 1e-9:
            existing_final_count += 1
        else:
            break
    if existing_final_count < requested_final_count:
        depths.extend([total] * (requested_final_count - existing_final_count))
    return depths


def build_g76_threading(
    stock_x: float,
    stock_z: float,
    target_x: float,
    target_z: float,
    packed_p: int,
    q_min_microns: float,
    r_finish_microns: float,
    p_height_microns: float,
    q_first_microns: float,
    lead: float,
    taper_r: float = 0.0,
) -> list[Motion]:
    """Expand a FANUC two-line G76 into XZ primitives.

    Despite the legacy parameter names, all Q/P/R depth arguments received by
    this function are millimetres in radius.  Conversion from FANUC integer
    least-input increments is performed by the runtime before this call.
    ``target_x`` is the authoritative final thread diameter from the second G76
    block; P controls pass-depth distribution and is expected to agree with it.
    """
    motions: list[Motion] = []
    total_rad = abs(float(p_height_microns))
    first_rad = abs(float(q_first_microns))
    q_min_rad = abs(float(q_min_microns))
    finish_rad = abs(float(r_finish_microns))
    if total_rad <= 1e-12 or first_rad <= 1e-12:
        return motions

    finish_passes, chamfer_tenths, tool_angle = _parse_g76_packed_p(packed_p)
    pass_depths = _g76_constant_area_depths(
        total_rad,
        first_rad,
        q_min_rad,
        finish_rad,
        finish_passes,
    )
    if not pass_depths:
        return motions

    direction_x = 1.0 if target_x >= stock_x else -1.0
    direction_z = 1.0 if target_z >= stock_z else -1.0
    feed = lead if lead > 0 else None

    # P is the radial thread height; therefore X plus P defines the crest/root
    # geometry independently of the clearance X from which G76 was called.
    # Example: X12.916 P542 implies an external crest diameter of 14.000 mm even
    # when the tool starts at X14.6 for clearance.
    crest_end_x = target_x - direction_x * radius_to_diameter(total_rad)
    taper_start_dia = 2.0 * float(taper_r)
    crest_start_x = crest_end_x + taper_start_dia
    chamfer_len = max(0.0, (chamfer_tenths / 10.0) * abs(float(lead)))
    thread_len = abs(target_z - stock_z)
    chamfer_len = min(chamfer_len, thread_len)

    def q(v: float) -> float:
        return round(v, 6)

    def point(x: float, z: float) -> Point2:
        return Point2(q(x), q(z))

    tool = Point2(stock_x, stock_z)
    for index, depth_rad in enumerate(pass_depths):
        actual_rad = min(total_rad, max(0.0, depth_rad))
        pass_start_z, pass_end_z = _g76_pass_z(total_rad, actual_rad, tool_angle, direction_z, stock_z, target_z)
        x_end = crest_end_x + direction_x * radius_to_diameter(actual_rad)
        x_start = crest_start_x + direction_x * radius_to_diameter(actual_rad)
        if depth_rad >= total_rad - 1e-9:
            x_end = target_x
            x_start = target_x + taper_start_dia
        pass_start = point(x_start, pass_start_z)
        pass_end = point(x_end, pass_end_z)
        retract_end = point(stock_x, pass_end_z)

        add_motion(motions, 0, tool, pass_start)
        if chamfer_len > 1e-12 and thread_len > chamfer_len + 1e-12:
            z_chamfer = pass_end_z - direction_z * chamfer_len
            t = (z_chamfer - pass_start_z) / (pass_end_z - pass_start_z)
            x_chamfer = x_start + (x_end - x_start) * t
            chamfer_start = point(x_chamfer, z_chamfer)
            add_motion_with_meta(motions, 1, pass_start, chamfer_start, None, feed)
            add_motion_with_meta(motions, 1, chamfer_start, pass_end, None, feed)
        else:
            add_motion_with_meta(motions, 1, pass_start, pass_end, None, feed)
        add_motion(motions, 0, pass_end, retract_end)

        if index < len(pass_depths) - 1:
            return_start = point(stock_x, stock_z)
            add_motion(motions, 0, retract_end, return_start)
            tool = return_start
        else:
            tool = retract_end

    return motions
