"""Additional milling cutter types use the shared G41/G42 geometry solver."""

import pytest

from app.gcode.kernel import execute


@pytest.mark.parametrize("tool_type", ["face_mill", "slot_mill", "chamfer_mill"])
@pytest.mark.parametrize("mode,expected_x", [(41, 7.0), (42, 13.0)])
@pytest.mark.parametrize("dialect", ["fanuc", "sinumerik"])
def test_additional_milling_types_apply_planar_compensation(tool_type, mode, expected_x, dialect):
    source = f"G21 G17 G90\nT1 M6\nG0 X0 Y0 Z0\nG{mode} G1 X10 Y0 F100\nG1 X10 Y10\nG40 G1 X20 Y10\nM30"
    result = execute(
        source,
        language="fanuc_mill",
        source_dialect=dialect,
        milling_tools={"T1": {"type": tool_type, "diameter": 6.0, "length": 50.0}},
    )
    assert result.ok and result.complete, result.diagnostics
    steady = next(motion for motion in result.motions if motion.source_raw == "G1 X10 Y10")
    assert steady.compensation_applied
    assert (steady.end_x, steady.end_y, steady.end_z) == pytest.approx((expected_x, 10, 0))


@pytest.mark.parametrize("tool_type", ["face_mill", "slot_mill", "chamfer_mill"])
def test_additional_milling_types_apply_arc_compensation(tool_type):
    result = execute(
        "G21 G17 G90 G40\nT1 M6\nG0 X0 Y0\nG1 Z-1 F300\nG41 G1 X5 F100\nG3 X0 Y5 I-5 J0\nG40 G1 X0 Y0\nM30",
        language="fanuc_mill",
        milling_tools={"T1": {"type": tool_type, "diameter": 6.0, "length": 50.0}},
    )
    assert result.ok and result.complete, result.diagnostics
    arc = next(motion for motion in result.motions if motion.move == 3)
    assert arc.compensation_applied
    assert arc.arc.radius == pytest.approx(2.0)
