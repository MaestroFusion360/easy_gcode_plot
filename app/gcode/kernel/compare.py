from __future__ import annotations

# Ported comparison logic intentionally validates a complete motion signature.
# pylint: disable=too-many-boolean-expressions


def parse_explicit_motion_primitives(
    lines,
    *,
    x_is_diameter: bool = True,
    cycle_only_marked: bool = False,
    strip_comments_fn,
    word_re,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
):
    motions = []
    modal_x = 0.0
    modal_z = 0.0
    modal_feed = 0.0
    modal_move = 0
    unit_scale = 1.0
    in_cycle = False

    for raw in lines:
        up_raw = raw.upper()
        start_mark = "(START G" in up_raw
        end_mark = "(END G" in up_raw
        if cycle_only_marked and start_mark:
            in_cycle = True
        include_motion = (not cycle_only_marked) or in_cycle or start_mark or end_mark

        line = strip_comments_fn(raw)
        if not line:
            if cycle_only_marked and end_mark:
                in_cycle = False
            continue
        words: dict[str, float] = {}
        for m in word_re.finditer(line):
            try:
                words[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                continue
        if not words:
            continue

        gcode = int(words["G"]) if "G" in words else None
        if gcode == 20:
            unit_scale = 25.4
        elif gcode == 21:
            unit_scale = 1.0

        if "F" in words:
            modal_feed = words["F"] * unit_scale

        has_pos = any(k in words for k in ("X", "Z", "U", "W"))
        if gcode in (0, 1, 2, 3):
            modal_move = gcode
        elif gcode in (32, 33):
            modal_move = 1
        non_motion_g = gcode is not None and gcode not in (0, 1, 2, 3, 32, 33)

        if has_pos and not non_motion_g and modal_move in (0, 1, 2, 3):
            tx = modal_x
            tz = modal_z
            if "X" in words:
                tx = x_value_to_diameter_fn(words["X"] * unit_scale, x_is_diameter)
            elif "U" in words:
                tx = modal_x + x_delta_to_diameter_fn(words["U"] * unit_scale, x_is_diameter)
            if "Z" in words:
                tz = words["Z"] * unit_scale
            elif "W" in words:
                tz = modal_z + (words["W"] * unit_scale)

            if abs(tx - modal_x) > 1e-9 or abs(tz - modal_z) > 1e-9:
                radius = (words["R"] * unit_scale) if (modal_move in (2, 3) and "R" in words) else None
                feed = modal_feed if modal_move in (1, 2, 3) and modal_feed > 0 else None
                if include_motion:
                    motions.append(
                        motion_ctor(
                            modal_move,
                            point_ctor(modal_x, modal_z),
                            point_ctor(tx, tz),
                            radius,
                            feed,
                        )
                    )
            modal_x, modal_z = tx, tz
        if cycle_only_marked and end_mark:
            in_cycle = False
    return motions


def motion_repr(m) -> str:
    return (
        f"{m.move} "
        f"S({m.start.x:.6f},{m.start.z:.6f}) "
        f"E({m.end.x:.6f},{m.end.z:.6f}) "
        f"F({0.0 if m.feed is None else m.feed:.6f}) "
        f"R({0.0 if m.radius is None else m.radius:.6f}) "
        f"I({0.0 if getattr(m, 'i', None) is None else m.i:.6f}) "
        f"K({0.0 if getattr(m, 'k', None) is None else m.k:.6f})"
    )


def compare_motion_sequences(left, right, tol: float, context: int) -> bool:
    def eq(a, b) -> bool:
        av = 0.0 if a is None else a
        bv = 0.0 if b is None else b
        return abs(av - bv) <= tol

    min_len = min(len(left), len(right))
    mismatch_idx: int | None = None
    for i in range(min_len):
        left_motion = left[i]
        right_motion = right[i]
        if (
            left_motion.move != right_motion.move
            or not eq(left_motion.start.x, right_motion.start.x)
            or not eq(left_motion.start.z, right_motion.start.z)
            or not eq(left_motion.end.x, right_motion.end.x)
            or not eq(left_motion.end.z, right_motion.end.z)
            or not eq(left_motion.feed, right_motion.feed)
            or not eq(left_motion.radius, right_motion.radius)
            or not eq(getattr(left_motion, "i", None), getattr(right_motion, "i", None))
            or not eq(getattr(left_motion, "k", None), getattr(right_motion, "k", None))
        ):
            mismatch_idx = i
            break

    if mismatch_idx is None and len(left) == len(right):
        print(f"COMPARE OK: {len(left)} primitives are identical.")
        return True

    if mismatch_idx is None:
        mismatch_idx = min_len

    print(f"COMPARE FAIL at index {mismatch_idx}: left={len(left)} right={len(right)}")
    lo = max(0, mismatch_idx - max(0, context))
    hi = min(max(len(left), len(right)), mismatch_idx + max(0, context) + 1)
    print("---- context ----")
    for i in range(lo, hi):
        ltxt = motion_repr(left[i]) if i < len(left) else "<EOF>"
        rtxt = motion_repr(right[i]) if i < len(right) else "<EOF>"
        mark = ">>" if i == mismatch_idx else "  "
        print(f"{mark} [{i}] L: {ltxt}")
        print(f"{mark} [{i}] R: {rtxt}")
    print("---- end ----")
    return False
