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
        ("macro_thread_milling.nc", 3, 1200, -75.0),
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


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_g65_type_i_type_ii_arguments_restore_locals_and_do_not_apply_machine_side_effects(language):
    source = """\
#1=100
#100=0
G65 P9000 A1. B2. I3. I4. D5. F9. M12. S10. T11. X6. Y7. Z8.
#101=#1
G1 X#100 F100
G1 X#101
M30
O9000
#100=#1+#2+#4+#7+#9+#13+#19+#20+#24+#25+#26
#1=999
M99
"""

    result = execute(source, language=language)

    assert result.ok, result.diagnostics
    assert [motion.end_x for motion in result.motions[-2:]] == pytest.approx([74.0, 100.0])
    assert [signal.code for signal in result.signals] == ["M30"]
    assert not any(event.kind == "tool_change" for event in result.events)
    call_block = result.program.blocks[2]
    assert call_block.motion_node is None
    assert result.program.ast.nodes[2].kind == "control"
    assert result.program.ast.nodes[2].m_codes == ()
    call_step = next(step for step in result.execution_steps if step.source_block == 2)
    assert call_step.signals == ()


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_g65_l_repeat_resets_arguments_and_nested_m98_shares_the_current_macro_local_level(language):
    source = """\
#1=100
#100=0
G65 P9000 L3 A10.
#101=#1
G1 X#100 F100
G1 X#101
M30
O9000
M98 P9100
G65 P9200 A30.
#100=#100+#1
M99
O9100
#1=#1+5
M99
O9200
#1=999
M99
"""

    result = execute(source, language=language)

    assert result.ok, result.diagnostics
    assert [motion.end_x for motion in result.motions[-2:]] == pytest.approx([45.0, 100.0])


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_g65_rejects_more_than_four_nested_macro_levels(language):
    source = """\
G65 P100
M30
O100
G65 P200
M99
O200
G65 P300
M99
O300
G65 P400
M99
O400
G65 P500
M99
O500
M99
"""

    result = execute(source, language=language)

    assert not result.ok
    assert any(diagnostic.code == "CALL_DEPTH_EXCEEDED" for diagnostic in result.diagnostics)
