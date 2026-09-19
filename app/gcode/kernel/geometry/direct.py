"""Turning contour construction and direct (A/C/R) programming."""

from __future__ import annotations

import math

from ..frontend.model import Block, PendingAngleSegment, Point2, ProfileSegment
from ..frontend.program import eval_words, radius_to_diameter, x_delta_to_diameter, x_value_to_diameter


def apply_a_programming(
    start_x: float,
    start_z: float,
    target_x: float,
    target_z: float,
    has_x: bool,
    has_z: bool,
    angle_deg: float,
    supplementary_angle: bool = False,
) -> tuple[float, float, bool, bool]:
    if has_x == has_z:
        return target_x, target_z, has_x, has_z
    if supplementary_angle:
        angle_deg = 180.0 - angle_deg
    a = math.radians(angle_deg)
    tan_a = math.tan(a)
    if abs(tan_a) <= 1e-9:
        return target_x, target_z, has_x, has_z
    if has_x and not has_z:
        target_z = start_z + (target_x - start_x) / tan_a
        return target_x, target_z, True, True
    if has_z and not has_x:
        target_x = start_x + (target_z - start_z) * tan_a
        return target_x, target_z, True, True
    return target_x, target_z, has_x, has_z


def _angle_direction(angle_deg: float) -> Point2:
    a = math.radians(angle_deg)
    return Point2(math.sin(a), math.cos(a))


def _line_intersection_from_angles(p1: Point2, a1_deg: float, p2: Point2, a2_deg: float) -> Point2 | None:
    # Angles are interpreted in lathe XZ conventions where tan(A)=dX/dZ.
    d1 = _angle_direction(a1_deg)
    d2 = _angle_direction(a2_deg)
    det = d1.x * d2.z - d1.z * d2.x
    if abs(det) <= 1e-9:
        return None
    dx = p2.x - p1.x
    dz = p2.z - p1.z
    t1 = (dx * d2.z - dz * d2.x) / det
    return Point2(p1.x + d1.x * t1, p1.z + d1.z * t1)


def _normalize(dx: float, dz: float) -> tuple[float, float, float]:
    ln = math.hypot(dx, dz)
    if ln <= 1e-9:
        return 0.0, 0.0, 0.0
    return dx / ln, dz / ln, ln


def _make_line_segment(
    block: int,
    start: Point2,
    end: Point2,
    corner_chamfer: float = 0.0,
    corner_radius_cmd: float = 0.0,
) -> ProfileSegment:
    return ProfileSegment(
        block=block,
        move=1,
        start=start,
        end=end,
        has_radius=False,
        radius=0.0,
        has_center=False,
        center=Point2(0.0, 0.0),
        corner_chamfer=corner_chamfer,
        corner_radius_cmd=corner_radius_cmd,
    )


def _clear_corner(seg: ProfileSegment) -> ProfileSegment:
    if abs(seg.corner_chamfer) <= 1e-12 and abs(seg.corner_radius_cmd) <= 1e-12:
        return seg
    return ProfileSegment(
        block=seg.block,
        move=seg.move,
        start=seg.start,
        end=seg.end,
        has_radius=seg.has_radius,
        radius=seg.radius,
        has_center=seg.has_center,
        center=seg.center,
        corner_chamfer=0.0,
        corner_radius_cmd=0.0,
    )


def apply_corner_direct_programming(
    profile: list[ProfileSegment],
) -> list[ProfileSegment]:
    if len(profile) < 2:
        return profile

    segments = list(profile)
    i = 0
    while i < len(segments) - 1:
        s1 = segments[i]
        s2 = segments[i + 1]
        if s1.move != 1 or s2.move != 1:
            segments[i] = _clear_corner(s1)
            i += 1
            continue

        chamfer = abs(s1.corner_chamfer)
        fillet = abs(s1.corner_radius_cmd)
        if chamfer <= 1e-9 and fillet <= 1e-9:
            i += 1
            continue

        vertex = s1.end
        # If the polyline is not connected tightly, ignore corner command and preserve geometry.
        if abs(vertex.x - s2.start.x) > 1e-5 or abs(vertex.z - s2.start.z) > 1e-5:
            segments[i] = _clear_corner(s1)
            i += 1
            continue

        d_in_x, d_in_z, len1 = _normalize(vertex.x - s1.start.x, vertex.z - s1.start.z)
        d_out_x, d_out_z, len2 = _normalize(s2.end.x - vertex.x, s2.end.z - vertex.z)
        if len1 <= 1e-9 or len2 <= 1e-9:
            segments[i] = _clear_corner(s1)
            i += 1
            continue

        turn_dot = max(-1.0, min(1.0, d_in_x * d_out_x + d_in_z * d_out_z))
        turn = math.acos(turn_dot)
        if turn <= math.radians(1.0) or abs(math.pi - turn) <= math.radians(1.0):
            segments[i] = _clear_corner(s1)
            i += 1
            continue

        if chamfer > 1e-9:
            trim = chamfer
            if trim > len1 + 1e-6 or trim > len2 + 1e-6:
                segments[i] = _clear_corner(s1)
                i += 1
                continue
            p1 = Point2(vertex.x - d_in_x * trim, vertex.z - d_in_z * trim)
            p2 = Point2(vertex.x + d_out_x * trim, vertex.z + d_out_z * trim)
            remaining_in = max(0.0, len1 - trim)
            remaining_out = max(0.0, len2 - trim)
            replacement: list[ProfileSegment] = []
            if remaining_in > 1e-6:
                replacement.append(_make_line_segment(s1.block, s1.start, p1))
            chamfer_seg = _make_line_segment(
                s1.block,
                p1,
                p2,
                corner_chamfer=s2.corner_chamfer if remaining_out <= 1e-6 else 0.0,
                corner_radius_cmd=s2.corner_radius_cmd if remaining_out <= 1e-6 else 0.0,
            )
            replacement.append(chamfer_seg)
            if remaining_out > 1e-6:
                replacement.append(
                    _make_line_segment(
                        s2.block,
                        p2,
                        s2.end,
                        corner_chamfer=s2.corner_chamfer,
                        corner_radius_cmd=s2.corner_radius_cmd,
                    )
                )
            segments[i : i + 2] = replacement
            i += len(replacement) - 1
            continue

        trim = fillet * math.tan(turn * 0.5)
        if trim <= 1e-9 or trim > len1 + 1e-6 or trim > len2 + 1e-6:
            segments[i] = _clear_corner(s1)
            i += 1
            continue

        p1 = Point2(vertex.x - d_in_x * trim, vertex.z - d_in_z * trim)
        p2 = Point2(vertex.x + d_out_x * trim, vertex.z + d_out_z * trim)
        remaining_in = max(0.0, len1 - trim)
        remaining_out = max(0.0, len2 - trim)

        # Program geometry is interpreted in XZ, but practical turning contour orientation
        # is equivalent to a swapped plotting basis (Z as horizontal, X as vertical).
        # Flip the signed turn to keep inserted R-fillets on the same side as machine contour.
        cross = d_in_z * d_out_x - d_in_x * d_out_z
        arc_move = 3 if cross > 0.0 else 2

        replacement = []
        if remaining_in > 1e-6:
            replacement.append(_make_line_segment(s1.block, s1.start, p1))
        fillet_seg = ProfileSegment(
            block=s1.block,
            move=arc_move,
            start=p1,
            end=p2,
            has_radius=True,
            radius=fillet,
            has_center=False,
            center=Point2(0.0, 0.0),
            corner_chamfer=s2.corner_chamfer if remaining_out <= 1e-6 else 0.0,
            corner_radius_cmd=s2.corner_radius_cmd if remaining_out <= 1e-6 else 0.0,
        )
        replacement.append(fillet_seg)
        if remaining_out > 1e-6:
            replacement.append(
                _make_line_segment(
                    s2.block,
                    p2,
                    s2.end,
                    corner_chamfer=s2.corner_chamfer,
                    corner_radius_cmd=s2.corner_radius_cmd,
                )
            )
        segments[i : i + 2] = replacement
        i += len(replacement) - 1

    return [_clear_corner(s) for s in segments]


def build_profile_segments(
    blocks: tuple[Block, ...],
    start_idx: int,
    end_idx: int,
    start_x: float,
    start_z: float,
    variables: dict[str, float],
    x_is_diameter: bool,
    unit_scale: float = 1.0,
    supplementary_angles: bool = False,
) -> list[ProfileSegment]:
    profile: list[ProfileSegment] = []
    x = start_x
    z = start_z
    move = 0
    pending_angle: PendingAngleSegment | None = None

    for i in range(start_idx, end_idx + 1):
        w = eval_words(blocks[i].parsed_words, variables)
        if w.errors:
            raise ValueError(f"Invalid profile expression at line {i + 1}: {w.errors[0][1]}")
        if "G" in w:
            g = int(w["G"])
            if g in (0, 1, 2, 3):
                move = g

        tx = x
        tz = z
        has_x = False
        has_z = False

        if "X" in w:
            tx = x_value_to_diameter(w["X"] * unit_scale, x_is_diameter)
            has_x = True
        elif "U" in w:
            tx = x + x_delta_to_diameter(w["U"] * unit_scale, x_is_diameter)
            has_x = True

        if "Z" in w:
            tz = w["Z"] * unit_scale
            has_z = True
        elif "W" in w:
            tz = z + (w["W"] * unit_scale)
            has_z = True

        if "A" in w:
            tx, tz, has_x, has_z = apply_a_programming(
                x,
                z,
                tx,
                tz,
                has_x,
                has_z,
                w["A"],
                supplementary_angle=supplementary_angles,
            )

        has_a = "A" in w
        corner_chamfer = abs(w.get("C", 0.0) * unit_scale)
        corner_radius = abs(w.get("R", 0.0) * unit_scale)

        if move == 1 and has_a and not (has_x or has_z):
            a_val = 180.0 - w["A"] if supplementary_angles else w["A"]
            pending_angle = PendingAngleSegment(
                block=blocks[i].index,
                start=Point2(x, z),
                angle_deg=a_val,
                corner_chamfer=corner_chamfer,
                corner_radius_cmd=corner_radius,
            )
            continue

        if not (has_x or has_z):
            continue

        if move == 0:
            x, z = tx, tz
            pending_angle = None
            continue

        if pending_angle is not None and move == 1 and has_a and has_x and has_z:
            a2_val = 180.0 - w["A"] if supplementary_angles else w["A"]
            joint = _line_intersection_from_angles(pending_angle.start, pending_angle.angle_deg, Point2(tx, tz), a2_val)
            if joint is not None and (
                abs(joint.x - pending_angle.start.x) > 1e-5 or abs(joint.z - pending_angle.start.z) > 1e-5
            ):
                profile.append(
                    _make_line_segment(
                        pending_angle.block,
                        pending_angle.start,
                        joint,
                        corner_chamfer=pending_angle.corner_chamfer,
                        corner_radius_cmd=pending_angle.corner_radius_cmd,
                    )
                )
                x, z = joint.x, joint.z
            pending_angle = None

        if abs(tx - x) <= 1e-5 and abs(tz - z) <= 1e-5:
            x, z = tx, tz
            continue

        has_center = "I" in w or "K" in w
        # Fanuc lathe I center offset is radius-based even in X-diameter programming.
        i_raw = w.get("I", 0.0) * unit_scale
        i_off = radius_to_diameter(i_raw)
        k_off = w.get("K", 0.0) * unit_scale
        center = Point2(x + i_off, z + k_off)

        has_radius = move in (2, 3) and "R" in w
        profile.append(
            ProfileSegment(
                block=blocks[i].index,
                move=move,
                start=Point2(x, z),
                end=Point2(tx, tz),
                has_radius=has_radius,
                radius=(w.get("R", 0.0) * unit_scale) if has_radius else 0.0,
                has_center=has_center,
                center=center,
                corner_chamfer=corner_chamfer if move == 1 else 0.0,
                corner_radius_cmd=corner_radius if move == 1 else 0.0,
            )
        )
        x, z = tx, tz

    return apply_corner_direct_programming(profile)
