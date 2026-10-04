"""Physical turning fillets must remain circular and tangent in radius X/Z."""

import math
from pathlib import Path

import pytest

from app.gcode.kernel import execute
from app.gcode.trace_tools import sample_motion


@pytest.mark.parametrize("move", [2, 3])
@pytest.mark.parametrize("radius", [10, -10])
def test_explicit_turning_radius_arcs_preserve_minor_and_major_sweep(move, radius):
    result = execute(f"G18 G0 X20 Z0\nG{move} X0 Z10 R{radius} F100\nM30", language="fanuc_turn")
    assert result.ok, result.diagnostics
    arc = result.motions[-1]
    assert arc.arc.radius == 10
    assert arc.arc.sweep == pytest.approx(math.pi / 2 if radius > 0 else 3 * math.pi / 2)
    cx, _, cz = arc.arc.center
    for point in sample_motion(arc, 1, lathe_radius_view=True):
        assert math.hypot(point.x - cx, point.z - cz) == pytest.approx(10)


@pytest.mark.parametrize("radial_end", [10, 30])
@pytest.mark.parametrize("axial_end", [-10, 10])
def test_right_angle_rounding_is_quarter_circle_in_physical_coordinates(radial_end, axial_end):
    result = execute(f"G0 X20 Z0\nG1 Z{axial_end} R2 F100\nX{radial_end}\nM30", language="fanuc_turn")
    assert result.ok, result.diagnostics
    arc = next(m for m in result.motions if m.arc is not None)
    assert arc.arc.radius == 2
    assert arc.arc.sweep == pytest.approx(math.pi / 2)
    assert abs(arc.end_x - arc.start_x) == pytest.approx(4)
    assert abs(arc.end_z - arc.start_z) == pytest.approx(2)


def test_basic_turning_fixture_rounding_is_tangent_and_samples_stay_on_circle():
    source = (Path(__file__).parents[1] / "fixtures/turning/basic_turning_cycles.NC").read_text()
    result = execute(source, language="fanuc_turn")
    assert result.ok, result.diagnostics
    count = 0
    for index, arc in enumerate(result.motions):
        if arc.arc is None or arc.cycle_generated:
            continue
        count += 1
        before, after = result.motions[index - 1], result.motions[index + 1]
        cx, _, cz = arc.arc.center
        for x, z, line in [(arc.start_x, arc.start_z, before), (arc.end_x, arc.end_z, after)]:
            rx, rz = x / 2 - cx, z - cz
            dx, dz = (line.end_x - line.start_x) / 2, line.end_z - line.start_z
            assert math.hypot(rx, rz) == pytest.approx(arc.radius)
            # Four groove fillets consume their entire axial incoming line;
            # the preceding motion is the separate radial approach.
            consumed_entry = line is before and arc.source_block in {97, 103, 221, 227}
            if not consumed_entry:
                assert rx * dx + rz * dz == pytest.approx(0, abs=1e-7)
        for point in sample_motion(arc, index, lathe_radius_view=True):
            assert math.hypot(point.x - cx, point.z - cz) == pytest.approx(arc.radius, abs=1e-7)
    assert count == 10
