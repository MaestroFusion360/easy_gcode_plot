"""Deterministic analytic references, independent of kernel geometry helpers."""

import math

import pytest

from app.gcode.kernel import execute

PLANES = [(17, "X", "Y", "Z", "I", "J"), (18, "Z", "X", "Y", "K", "I"), (19, "Y", "Z", "X", "J", "K")]


def xyz(u, v, w, a, b, c):
    values = {u: a, v: b, w: c}
    return tuple(values[axis] for axis in "XYZ")


@pytest.mark.parametrize("plane,u,v,w,i,j", PLANES)
def test_1000_fanuc_arcs_per_plane(plane, u, v, w, i, j):
    # 3000 cases: both directions, IJK/R, variable sweep/radius and helical rise.
    for case in range(1000):
        radius = 2 + (case % 97) / 3
        angle = (30 + case % 120) * math.pi / 180
        sign = 1 if case % 2 else -1
        end_u, end_v = radius * math.cos(angle), sign * radius * math.sin(angle)
        rise = (case % 7 - 3) / 2
        center = f"{i}{-radius:.12f} {j}0" if case % 4 < 2 else f"R{radius:.12f}"
        source = (
            f"G21 G90 G{plane}\nG0 {u}{radius:.12f} {v}0 {w}0\n"
            f"G{3 if sign > 0 else 2} {u}{end_u:.12f} {v}{end_v:.12f} {w}{rise} {center} F100\nM30"
        )
        result = execute(source, "fanuc_mill")
        assert result.ok and result.complete, (case, result.diagnostics)
        motion = result.motions[-1]
        assert motion.arc.center == pytest.approx((0, 0, 0), abs=1e-8)
        assert motion.arc.radius == pytest.approx(radius, abs=1e-8)
        assert motion.arc.sweep == pytest.approx(angle, abs=1e-8)
        assert motion.arc.clockwise == ((sign < 0) != (plane == 18))
        assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx(xyz(u, v, w, end_u, end_v, rise))


@pytest.mark.parametrize("plane,u,v,w,i,j", PLANES)
def test_heidenhain_2500_circle_cases(plane, u, v, w, i, j):
    count = 834 if plane == 17 else 833
    for case in range(count):
        radius = 3 + (case % 83) / 4
        angle = (20 + case % 140) * math.pi / 180
        sign = 1 if case % 2 else -1
        a, b = radius * math.cos(angle), sign * radius * math.sin(angle)
        command = f"CC {u}0 {v}0\nC" if case % 4 < 2 else "CR"
        rword = "" if case % 4 < 2 else f" R{radius:.12f}"
        result = execute(
            f"TOOL CALL 1 {w}\nL {u}{radius:.12f} {v}0 F100\n"
            f"{command} {u}{a:.12f} {v}{b:.12f}{rword} DR{'+' if sign > 0 else '-'}\nM30",
            "fanuc_mill",
            source_dialect="heidenhain",
        )
        assert result.ok and result.complete, (case, result.diagnostics)
        arc = result.motions[-1].arc
        assert arc.plane == plane
        assert arc.center == pytest.approx((0, 0, 0), abs=1e-8)
        assert arc.radius == pytest.approx(radius, abs=1e-8)
        assert arc.sweep == pytest.approx(angle, abs=1e-8)
        assert arc.clockwise == ((sign < 0) != (plane == 18))


def test_1500_heidenhain_corners_against_trim_condition():
    invalid_count = 0
    for case in range(1500):
        angle = math.radians(30 + case % 100)
        radius = 1 + case % 13
        trim = radius * math.tan(angle / 2)
        # Deliberately constructed eleven infeasible RND cases, independently certified.
        invalid = case < 22 and case % 2 == 0
        length = trim * (0.8 if invalid else 2.5) + (0 if invalid else 1)
        rounding = case % 2 == 0
        distance = radius if rounding else trim
        corner = f"RND R{radius}" if rounding else f"CHF {distance:.12f}"
        end = (length + length * math.cos(angle), length * math.sin(angle))
        result = execute(
            f"L X0 Y0 F100\nL X{length:.12f} Y0\n{corner}\nL X{end[0]:.12f} Y{end[1]:.12f}\nM30",
            "fanuc_mill",
            source_dialect="heidenhain",
        )
        diagnostics = [d for d in result.diagnostics if d.code == "INVALID_HEIDENHAIN_CORNER"]
        assert bool(diagnostics) == invalid, (case, trim, length, result.diagnostics)
        if invalid:
            assert trim > length
            invalid_count += 1
            continue
        assert result.ok, result.diagnostics
        motion = next(
            m for m in result.motions if m.source_kind == ("heidenhain_rnd" if rounding else "heidenhain_chf")
        )
        assert (motion.start_x, motion.start_y) == pytest.approx((length - trim, 0), abs=1e-8)
        assert (motion.end_x, motion.end_y) == pytest.approx(
            (length + trim * math.cos(angle), trim * math.sin(angle)), abs=1e-8
        )
        if rounding:
            assert motion.arc.radius == pytest.approx(radius)
            assert motion.arc.center == pytest.approx((length - trim, radius, 0), abs=1e-8)
            assert motion.arc.sweep == pytest.approx(angle)
    assert invalid_count == 11


def test_400_compensated_rounded_rectangles():
    for case in range(400):
        sign = 1 if case % 2 else -1
        mode = 41 if case % 4 < 2 else 42
        rounding = 4 + case % 9
        tool_radius = 0.5 + (case % 5) / 4
        width, height = 50 + case % 17, 40 + case % 19
        y = sign * height
        turn = 3 if sign > 0 else 2
        source = (
            f"G17 G90\nT1 M6\nG0 X-10 Y0\nG{mode} G1 X{rounding} Y0 F100\n"
            f"G1 X{width - rounding}\nG{turn} X{width} Y{sign * rounding} I0 J{sign * rounding}\n"
            f"G1 Y{sign * (height - rounding)}\nG{turn} X{width - rounding} Y{y} I{-rounding} J0\n"
            f"G1 X{rounding}\nG{turn} X0 Y{sign * (height - rounding)} I0 J{-sign * rounding}\n"
            f"G1 Y{sign * rounding}\nG{turn} X{rounding} Y0 I{rounding} J0\n"
            "G1 X20\nG40 G1 X30\nM30"
        )
        result = execute(source, "fanuc_mill", milling_tools={"T1": {"type": "mill_flat", "diameter": 2 * tool_radius}})
        assert result.ok, result.diagnostics
        arcs = [m for m in result.motions if m.arc]
        assert len(arcs) == 4
        inward = sign * (1 if mode == 41 else -1)
        for m in arcs:
            assert m.compensation_status == "APPLIED"
            assert m.arc.radius == pytest.approx(rounding - inward * tool_radius)
            assert m.arc.sweep == pytest.approx(math.pi / 2)
        assert sum(s.emitted_count for s in result.execution_steps) == len(result.motions)


def test_g71_cylindrical_allowance_and_g70_finished_surface():
    source = (
        "G21 G18 G90\nG0 X40 Z5\nG71 U2 R0.5\nG71 P10 Q20 U1 W0.2 F0.2\nN10 G0 X20\nG1 Z0\nN20 Z-20\nG70 P10 Q20\nM30"
    )
    result = execute(source, "fanuc_turn")
    assert result.ok and result.complete, result.diagnostics
    # X is diameter: U1 leaves 0.5 mm radial stock on the D20 cylinder.
    rough = [m for m in result.motions if m.source_raw.startswith("G71 P") and m.move == 1 and m.end_z < m.start_z]
    finish = [m for m in result.motions if m.source_raw.startswith("G70") and m.move == 1]
    assert rough and finish
    assert all(m.start_x >= 21 and m.end_x >= 21 for m in rough)
    assert any(m.end_x == 21 and m.end_z == -20 for m in rough)
    assert all(m.start_x == 20 and m.end_x == 20 for m in finish)
    assert finish[-1].end_z == -20


@pytest.mark.parametrize("mode,sign", [(41, 1), (42, -1)])
@pytest.mark.parametrize("width", [2, 10, 12])
def test_slot_tool_diameter_limit(mode, sign, width):
    source = f"T1 M6\nG17 G90 G0 X-10 Y0\nG{mode} G1 X0 Y0 F100\nX20\nY{sign * width}\nX0\nG40 X-10\nM30"
    result = execute(source, "fanuc_mill", milling_tools={"T1": {"type": "mill_flat", "diameter": 10}})
    steady = [m for m in result.motions if m.source_raw == f"Y{sign * width}"]
    assert len(steady) == 1
    if width <= 10:
        assert steady[0].compensation_status == "UNVERIFIED"
        assert not steady[0].compensation_applied
        assert any(d.code == "UNVERIFIED_CUTTER_COMPENSATION" for d in result.diagnostics)
    else:
        assert steady[0].compensation_status == "APPLIED"
        assert steady[0].end_y - steady[0].start_y == pytest.approx(sign * (width - 10))
    assert sum(s.emitted_count for s in result.execution_steps) == len(result.motions)
