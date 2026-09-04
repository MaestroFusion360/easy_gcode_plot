"""Turning contour construction, direct programming, and arc geometry."""

from __future__ import annotations

import math

from .model import ArcGeom, Block, PendingAngleSegment, Point2, ProfileSegment
from .program import (
    eval_words,
    move_for_xz_plot,
    radius_to_diameter,
    x_delta_to_diameter,
    x_value_to_diameter,
)


def _apply_a_programming(
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


def _apply_corner_direct_programming(
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
            if trim >= len1 - 1e-6 or trim >= len2 - 1e-6:
                segments[i] = _clear_corner(s1)
                i += 1
                continue
            p1 = Point2(vertex.x - d_in_x * trim, vertex.z - d_in_z * trim)
            p2 = Point2(vertex.x + d_out_x * trim, vertex.z + d_out_z * trim)
            seg1_new = _make_line_segment(s1.block, s1.start, p1)
            chamfer_seg = _make_line_segment(s1.block, p1, p2)
            seg2_new = _make_line_segment(
                s2.block,
                p2,
                s2.end,
                corner_chamfer=s2.corner_chamfer,
                corner_radius_cmd=s2.corner_radius_cmd,
            )
            segments[i : i + 2] = [seg1_new, chamfer_seg, seg2_new]
            i += 2
            continue

        trim = fillet * math.tan(turn * 0.5)
        if trim <= 1e-9 or trim >= len1 - 1e-6 or trim >= len2 - 1e-6:
            segments[i] = _clear_corner(s1)
            i += 1
            continue

        p1 = Point2(vertex.x - d_in_x * trim, vertex.z - d_in_z * trim)
        p2 = Point2(vertex.x + d_out_x * trim, vertex.z + d_out_z * trim)

        # Program geometry is interpreted in XZ, but practical turning contour orientation
        # is equivalent to a swapped plotting basis (Z as horizontal, X as vertical).
        # Flip the signed turn to keep inserted R-fillets on the same side as machine contour.
        cross = d_in_z * d_out_x - d_in_x * d_out_z
        arc_move = 3 if cross > 0.0 else 2

        seg1_new = _make_line_segment(s1.block, s1.start, p1)
        fillet_seg = ProfileSegment(
            block=s1.block,
            move=arc_move,
            start=p1,
            end=p2,
            has_radius=True,
            radius=fillet,
            has_center=False,
            center=Point2(0.0, 0.0),
        )
        seg2_new = _make_line_segment(
            s2.block,
            p2,
            s2.end,
            corner_chamfer=s2.corner_chamfer,
            corner_radius_cmd=s2.corner_radius_cmd,
        )
        segments[i : i + 2] = [seg1_new, fillet_seg, seg2_new]
        i += 2

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
            tx, tz, has_x, has_z = _apply_a_programming(
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
        corner_chamfer = abs(w.get("C", 0.0))
        corner_radius = abs(w.get("R", 0.0))

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
        i_off = radius_to_diameter(i_raw) if x_is_diameter else i_raw
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

    return _apply_corner_direct_programming(profile)


def normalize_sweep(gcode: int, start_a: float, end_a: float) -> float:
    gcode = move_for_xz_plot(gcode)
    sweep = end_a - start_a
    if gcode == 2 and sweep > 0:
        sweep -= 2.0 * math.pi
    if gcode == 3 and sweep < 0:
        sweep += 2.0 * math.pi
    return sweep


def score_center_candidate(seg: ProfileSegment, center: Point2, x_scale: float) -> float:
    sx = seg.start.x * x_scale
    sz = seg.start.z
    ex = seg.end.x * x_scale
    ez = seg.end.z
    cx = center.x * x_scale
    cz = center.z

    r0 = math.hypot(sx - cx, sz - cz)
    r1 = math.hypot(ex - cx, ez - cz)
    if r0 <= 1e-9 or r1 <= 1e-9:
        return float("inf")

    score = abs(r0 - r1)
    a0 = math.atan2(sz - cz, sx - cx)
    a1 = math.atan2(ez - cz, ex - cx)
    sw = normalize_sweep(seg.move, a0, a1)
    plot_move = move_for_xz_plot(seg.move)
    dir_ok = sw <= 0 if plot_move == 2 else sw >= 0
    if not dir_ok:
        score += 10.0
    return score


def arc_center_from_r(start: Point2, end: Point2, radius: float, move: int, x_scale: float = 1.0) -> Point2 | None:
    # Use ConvertPlot.CircMove(type==2) center selection logic.
    signed_r = radius
    rr = abs(signed_r)
    if rr <= 1e-12:
        return None

    sx = start.x * x_scale
    sy = start.z
    ex = end.x * x_scale
    ey = end.z
    dx = sx - ex
    dy = sy - ey
    d = math.hypot(dx, dy)
    if d <= 1e-12 or rr < (d * 0.5):
        return None

    half_d = d * 0.5
    h = math.sqrt(max(0.0, (rr * rr) - (half_d * half_d)))
    mapped_move = move_for_xz_plot(move)

    if signed_r > 0.0:
        if mapped_move == 2:
            cx = sx + (ex - sx) * 0.5 + h * (ey - sy) / d
            cy = sy + (ey - sy) * 0.5 - h * (ex - sx) / d
        else:
            cx = sx + (ex - sx) * 0.5 - h * (ey - sy) / d
            cy = sy + (ey - sy) * 0.5 + h * (ex - sx) / d
    else:
        if mapped_move == 2:
            cx = sx + (ex - sx) * 0.5 - h * (ey - sy) / d
            cy = sy + (ey - sy) * 0.5 + h * (ex - sx) / d
        else:
            cx = sx + (ex - sx) * 0.5 + h * (ey - sy) / d
            cy = sy + (ey - sy) * 0.5 - h * (ex - sx) / d

    return Point2(cx / x_scale, cy)


def try_get_arc_geometry(seg: ProfileSegment) -> ArcGeom | None:
    if seg.has_center:
        i_delta = seg.center.x - seg.start.x
        center_as_written = seg.center
        center_with_radius_i = Point2(seg.start.x + (i_delta * 2.0), seg.center.z)
        candidates = [
            (center_as_written, 1.0),
            (center_as_written, 0.5),
            (center_with_radius_i, 0.5),
        ]
        best: tuple[Point2, float, float] | None = None
        best_score = float("inf")
        for center, scale in candidates:
            score = score_center_candidate(seg, center, scale)
            if not math.isfinite(score):
                continue
            if score < best_score:
                best = (center, scale, score)
                best_score = score
        if best is not None:
            center, scale, _score = best
            return ArcGeom(center, scale)

    if seg.has_radius:
        # Lathe default: diameter programming (X is diameter) -> solve in radius-space first.
        scaled = arc_center_from_r(seg.start, seg.end, seg.radius, seg.move, x_scale=0.5)
        if scaled is not None:
            return ArcGeom(scaled, 0.5)

        direct = arc_center_from_r(seg.start, seg.end, seg.radius, seg.move, x_scale=1.0)
        if direct is not None:
            return ArcGeom(direct, 1.0)

    return None


def try_compute_signed_arc_radius_from_center(move: int, start: Point2, end: Point2, center: Point2) -> float | None:
    sx = start.x * 0.5
    ex = end.x * 0.5
    cx = center.x * 0.5
    rr = math.hypot(sx - cx, start.z - center.z)
    if rr <= 1e-9:
        return None
    a0 = math.atan2(start.z - center.z, sx - cx)
    a1 = math.atan2(end.z - center.z, ex - cx)
    sw = normalize_sweep(move, a0, a1)
    return rr if abs(sw) <= math.pi + 1e-6 else -rr


def arc_progress01(seg: ProfileSegment, geom: ArcGeom, p: Point2) -> float:
    sx = seg.start.x * geom.x_scale
    sy = seg.start.z
    ex = seg.end.x * geom.x_scale
    ey = seg.end.z
    px = p.x * geom.x_scale
    py = p.z
    cx = geom.center.x * geom.x_scale
    cy = geom.center.z

    rad = math.hypot(sx - cx, sy - cy)
    if rad <= 1e-9:
        return 0.0
    mapped_move = move_for_xz_plot(seg.move)

    st_ang = math.atan2(cy - sy, cx - sx) - math.atan2(0.0, -rad)
    if st_ang < 0.0:
        st_ang += 2.0 * math.pi

    if mapped_move == 2:
        full = math.atan2(cy - sy, cx - sx) - math.atan2(cy - ey, cx - ex)
        part = math.atan2(cy - sy, cx - sx) - math.atan2(cy - py, cx - px)
    else:
        full = math.atan2(cy - ey, cx - ex) - math.atan2(cy - sy, cx - sx)
        part = math.atan2(cy - py, cx - px) - math.atan2(cy - sy, cx - sx)

    if full <= 0.0:
        full += 2.0 * math.pi
    if part <= 0.0:
        part += 2.0 * math.pi
    if mapped_move == 2:
        full = -abs(full)
        part = -abs(part)
    if abs(full) <= 1e-12:
        return 0.0
    return part / full


def is_point_on_arc(seg: ProfileSegment, geom: ArcGeom, p: Point2) -> bool:
    t = arc_progress01(seg, geom, p)
    return -1e-4 <= t <= 1.0001


def segment_points(seg: ProfileSegment, s: Point2, e: Point2) -> list[Point2]:
    pts = [s]
    if seg.move in (2, 3):
        g = try_get_arc_geometry(seg)
        if g is not None:
            sx = s.x * g.x_scale
            sy = s.z
            ex = e.x * g.x_scale
            ey = e.z
            cx = g.center.x * g.x_scale
            cy = g.center.z
            r = math.hypot(sx - cx, sy - cy)
            if r <= 1e-9:
                pts.append(e)
                return pts
            mapped_move = move_for_xz_plot(seg.move)
            st_ang = math.atan2(cy - sy, cx - sx) - math.atan2(0.0, -r)
            if st_ang < 0.0:
                st_ang += 2.0 * math.pi
            if mapped_move == 2:
                sw = math.atan2(cy - sy, cx - sx) - math.atan2(cy - ey, cx - ex)
            else:
                sw = math.atan2(cy - ey, cx - ex) - math.atan2(cy - sy, cx - sx)
            if sw <= 0.0:
                sw += 2.0 * math.pi
            if mapped_move == 2:
                sw = -abs(sw)
            count = max(48, int(math.ceil(abs(sw) / (math.pi / 64.0))))
            for i in range(1, count):
                t = i / count
                a = st_ang + sw * t
                x_scaled = cx + r * math.cos(a)
                z = cy + r * math.sin(a)
                pts.append(Point2(x_scaled / g.x_scale, z))
    pts.append(e)
    return pts


def intersect_at_x(a: Point2, b: Point2, x: float) -> Point2:
    dx = b.x - a.x
    if abs(dx) <= 1e-9:
        return Point2(x, a.z)
    t = max(0.0, min(1.0, (x - a.x) / dx))
    return Point2(x, a.z + (b.z - a.z) * t)


def clip_polyline_max_x(polyline: list[Point2], max_x: float) -> list[Point2]:
    if not polyline:
        return []
    out: list[Point2] = []
    prev = polyline[0]
    prev_in = prev.x <= max_x + 1e-5
    if prev_in:
        out.append(prev)
    for curr in polyline[1:]:
        curr_in = curr.x <= max_x + 1e-5
        if prev_in and curr_in:
            out.append(curr)
        elif prev_in and not curr_in:
            hit = intersect_at_x(prev, curr, max_x)
            if not out or abs(out[-1].x - hit.x) > 1e-5 or abs(out[-1].z - hit.z) > 1e-5:
                out.append(hit)
        elif not prev_in and curr_in:
            hit = intersect_at_x(prev, curr, max_x)
            if not out or abs(out[-1].x - hit.x) > 1e-5 or abs(out[-1].z - hit.z) > 1e-5:
                out.append(hit)
            out.append(curr)
        prev = curr
        prev_in = curr_in
    return out


def clip_polyline_min_x(polyline: list[Point2], min_x: float) -> list[Point2]:
    if not polyline:
        return []
    out: list[Point2] = []
    prev = polyline[0]
    prev_in = prev.x >= min_x - 1e-5
    if prev_in:
        out.append(prev)
    for curr in polyline[1:]:
        curr_in = curr.x >= min_x - 1e-5
        if prev_in and curr_in:
            out.append(curr)
        elif prev_in and not curr_in:
            hit = intersect_at_x(prev, curr, min_x)
            if not out or abs(out[-1].x - hit.x) > 1e-5 or abs(out[-1].z - hit.z) > 1e-5:
                out.append(hit)
        elif not prev_in and curr_in:
            hit = intersect_at_x(prev, curr, min_x)
            if not out or abs(out[-1].x - hit.x) > 1e-5 or abs(out[-1].z - hit.z) > 1e-5:
                out.append(hit)
            out.append(curr)
        prev = curr
        prev_in = curr_in
    return out


def try_find_entry_on_profile(profile: list[ProfileSegment], pass_x: float) -> tuple[int, Point2] | None:
    best: tuple[int, Point2] | None = None
    best_z = float("inf")

    for i, seg in enumerate(profile):
        if seg.move in (2, 3):
            g = try_get_arc_geometry(seg)
            if g is None:
                continue
            sx = seg.start.x * g.x_scale
            cx = g.center.x * g.x_scale
            pass_x_scaled = pass_x * g.x_scale
            r = math.hypot(sx - cx, seg.start.z - g.center.z)
            dx = pass_x_scaled - cx
            disc = r * r - dx * dx
            if disc < -1e-6:
                continue
            disc = max(0.0, disc)
            root = math.sqrt(disc)
            cands = [Point2(pass_x_scaled / g.x_scale, g.center.z + root)]
            if root > 1e-6:
                cands.append(Point2(pass_x_scaled / g.x_scale, g.center.z - root))

            best_arc: Point2 | None = None
            best_prog = float("-inf")
            for p in cands:
                if not is_point_on_arc(seg, g, p):
                    continue
                prog = arc_progress01(seg, g, p)
                if prog > best_prog:
                    best_prog = prog
                    best_arc = p
            if best_arc is not None and best_arc.z < best_z:
                best_z = best_arc.z
                best = (i, best_arc)
            continue

        x1, z1 = seg.start.x, seg.start.z
        x2, z2 = seg.end.x, seg.end.z
        if pass_x < min(x1, x2) - 1e-5 or pass_x > max(x1, x2) + 1e-5:
            continue
        if abs(x2 - x1) <= 1e-8:
            z = min(z1, z2)
        else:
            t = (pass_x - x1) / (x2 - x1)
            if t < -1e-5 or t > 1.00001:
                continue
            t = max(0.0, min(1.0, t))
            z = z1 + (z2 - z1) * t
        if z < best_z:
            best_z = z
            best = (i, Point2(pass_x, z))

    return best
