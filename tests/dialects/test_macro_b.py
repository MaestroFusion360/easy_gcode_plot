from __future__ import annotations

import pytest

from app.gcode.kernel import execute


def test_macro_b_expression_control_flow_and_indirect_addressing(fixture_text):
    result = execute(fixture_text("milling/macro_b.nc"), language="fanuc_mill")
    assert result.ok, result.diagnostics

    by_label = {motion.source_nlabel: motion for motion in result.motions if motion.source_nlabel is not None}
    expected = {
        1010: (30.0, 42.0, 5.552),
        1020: (27.0, 9.5609, 21.0),
        1030: (29.4323756132, 0.6691306064, 0.7431448255),
        1040: (0.9004040443, 24.7751405688, 5.9160797831),
        1050: (13.125162, 1.0, 1.0),
        1060: (1.0, -2.573, 30.824704),
        1070: (33.0609593116, -5.7733333333, -9.9066666667),
        1080: (1.8973665961, 69.399858, 2.8334252598),
        1090: (42.0, 2.0, 7.0),
        1100: (1.0, 0.0, 0.0),
        1110: (0.0, 0.0, 1.0),
        1120: (1.0, 0.0, 1.0),
        1130: (11.0, 10.0, 11.0),
        1140: (3.0, 3.0, 3.0),
    }

    assert set(expected) <= set(by_label)
    for label, xyz in expected.items():
        motion = by_label[label]
        assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx(xyz, abs=1e-8)


@pytest.mark.parametrize(
    ("fixture_name", "arc_move", "arc_count", "min_z"),
    [
        ("macro_boss_milling.nc", 2, 201, -50.0),
        ("macro_face_milling.nc", 2, 6, 0.3),
        ("macro_hole_milling.nc", 3, 51, -50.0),
    ],
)
def test_macro_b_loop_programs_expand_to_deterministic_motion(fixture_text, fixture_name, arc_move, arc_count, min_z):
    result = execute(fixture_text(f"milling/{fixture_name}"), language="fanuc_mill")
    assert result.ok, result.diagnostics

    arcs = [motion for motion in result.motions if motion.move == arc_move]
    assert len(arcs) == arc_count
    assert min(motion.end_z for motion in arcs) == pytest.approx(min_z)


def test_undefined_macro_is_structured_fail_closed_error():
    result = execute("G1 X#999 Y0 Z0\nM30", language="fanuc_mill")
    assert result.ok is False
    assert result.motions == ()
    assert result.diagnostics[0].code == "UNDEFINED_MACRO"
    assert result.diagnostics[0].line == 1
