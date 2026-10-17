"""Analytical regressions for multi-turn compensation and cycle parameter scope."""

import math

import pytest

from app.gcode.kernel import execute


@pytest.mark.parametrize("axis,plane,u,v", [("Z", 17, "X", "Y"), ("Y", 18, "Z", "X"), ("X", 19, "Y", "Z")])
@pytest.mark.parametrize("degrees", [450, 1080])
@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("compensation", ["RL", "RR"])
@pytest.mark.parametrize("depth", [0, -4])
def test_compensated_cp_preserves_turns_direction_and_axial_travel(
    axis, plane, u, v, degrees, direction, compensation, depth
):
    source = (
        f"TOOL CALL 1 {axis}\nL {u}10 {v}0 {compensation} F100\nCC {u}0 {v}0\n"
        f"CP IPA{direction * degrees:+} {axis}{depth:+} DR{'+' if direction > 0 else '-'}\nM30"
    )
    result = execute(
        source, "fanuc_mill", source_dialect="heidenhain", milling_tools={"T1": {"type": "mill_flat", "diameter": 6}}
    )
    assert result.ok and result.complete, result.diagnostics
    motion = next(m for m in result.motions if m.arc is not None)
    radius = 10 - direction * (3 if compensation == "RL" else -3)
    assert motion.compensation_applied and motion.arc.plane == plane
    assert motion.arc.radius == pytest.approx(radius, abs=1e-8)
    assert motion.arc.sweep == pytest.approx(math.radians(degrees), abs=1e-8)
    assert motion.arc.clockwise == ((direction < 0) != (plane == 18))
    assert motion.arc.full_circle == (degrees == 1080)
    assert motion.arc.center == pytest.approx((0, 0, 0), abs=1e-8)
    start = dict(zip("XYZ", (motion.start_x, motion.start_y, motion.start_z), strict=True))
    end = dict(zip("XYZ", (motion.end_x, motion.end_y, motion.end_z), strict=True))
    assert (start[u], start[v], start[axis]) == pytest.approx((radius, 0, 0), abs=1e-8)
    angle = math.radians(direction * degrees)
    assert (end[u], end[v], end[axis]) == pytest.approx(
        (radius * math.cos(angle), radius * math.sin(angle), depth), abs=1e-8
    )
    assert sum(s.emitted_count for s in result.execution_steps) == len(result.motions)


@pytest.mark.parametrize("code", [200, 203, 205])
def test_cycle_consumes_only_its_parameters_without_erasing_global_q_variables(code):
    source = (
        "FN 0: Q212=0.5\nFN 0: Q205=1\nFN 0: Q258=0.25\n"
        f"TOOL CALL 1 Z\nCYCL DEF {code}\nQ200=2\nQ201=-6\nQ202=2\nQ203=0\nQ204=10\nQ206=100\n"
        "L X1 FMAX M99\nL XQ212 YQ205 ZQ258 FMAX\nM30"
    )
    result = execute(source, "fanuc_mill", source_dialect="heidenhain")
    assert result.ok and result.complete, result.diagnostics
    feeds = [m for m in result.motions if m.cycle_generated and m.move == 1 and m.end_z < m.start_z]
    expected = [-2, -4, -6] if code == 200 else [-2, -3.5, -4.5, -5.5, -6]
    assert [m.end_z for m in feeds] == pytest.approx(expected, abs=1e-8)
    if code == 200:
        assert [m.start_z for m in feeds] == pytest.approx([2, 0, -2], abs=1e-8)
    operation = next(e.drilling for e in result.events if e.drilling is not None)
    assert (operation.peck_reduction, operation.peck_minimum) == ((0, 0) if code == 200 else (0.5, 1))
    final = result.motions[-1]
    assert (final.end_x, final.end_y, final.end_z) == pytest.approx((0.5, 1, 0.25), abs=1e-8)
