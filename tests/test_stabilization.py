"""Independent semantic contracts for the stabilization pass."""

import math

import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.resources import ExecutionLimits
from app.gcode.trace_tools import render_trace, trace_statistics


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_dwell_consumes_x_and_standalone_feed_is_modal(language):
    result = execute("G1 X10 F100\nG4 X2\nF200\nG1 X20\nM30", language)
    assert result.ok, result.diagnostics
    assert [m.end_x for m in result.motions] == [10, 20]
    assert result.motions[-1].feed == 200
    assert [s.value for s in result.signals if s.kind == "dwell"] == [2]


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
@pytest.mark.parametrize("expression", ["[10/0]", "[1+]", "BOGUS[1]", "[1]garbage", "[1e309]"])
def test_expression_failure_never_produces_a_coordinate(language, expression):
    result = execute(f"G1 X{expression}\nM30", language)
    assert not result.ok
    assert result.diagnostics


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_indirect_variable_is_dereferenced(language):
    result = execute("#1=42\nG1 X#[1] F100\nM30", language)
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_x == 42


def test_optional_cycle_does_not_hide_unexecuted_contour():
    result = execute("G0 X20 Z0\n/G70 P100 Q110\nN100 G1 X10 Z-5\nN110 G1 Z-10\nM30", skip_optional_blocks=True)
    assert result.ok, result.diagnostics
    assert [(m.end_x, m.end_z) for m in result.motions] == [(20, 0), (10, -5), (10, -10)]


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_signals_follow_executed_occurrences(language):
    result = execute("M98 P100 L2\nM30\nO100\nM8\nG1 U1 X1 F100\nM9\nM99\nM3", language)
    assert result.ok, result.diagnostics
    assert [s.code for s in result.signals] == ["M08", "M09", "M08", "M09", "M30"]


def test_turn_full_circle_has_analytical_geometry():
    result = execute("G0 X20 Z0\nG2 X20 Z0 I-5 K0 F100\nM30")
    assert result.ok, result.diagnostics
    assert len(result.motions) == 2
    assert result.motions[-1].arc.sweep == pytest.approx(2 * math.pi)


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_invalid_radius_is_diagnostic(language):
    result = execute("G0 X20 Z0\nG2 X40 Z0 R1\nM30", language)
    assert not result.ok
    assert any(d.code == "INVALID_GEOMETRY" for d in result.diagnostics)


@pytest.mark.parametrize("source", ["GOTO99", "M98", "M98 P999", "M98 P1.5", "WHILE[1]DO1\nM30", "END1"])
@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_invalid_flow_is_not_fallthrough(source, language):
    result = execute(source + "\nG1 X20", language)
    assert not result.ok
    assert result.diagnostics


def test_turn_statistics_use_physical_radius_for_length_and_runtime_feed_mode():
    result = execute("G21 G18 G97 S1000 G99\nG0 X20 Z0\nG1 X40 Z0 F0.1\nM30")
    assert result.ok, result.diagnostics
    stats = trace_statistics(result)
    assert stats["lengths"][-1] == pytest.approx(10.0)
    assert stats["total_time_min"] == pytest.approx(0.1 + 0.001)
    assert stats["time_complete"] is True


def test_turn_statistics_report_unknown_time_when_feed_per_revolution_has_no_rpm():
    result = execute("G21 G18 G99\nG1 X20 F0.1\nM30")
    assert result.ok, result.diagnostics
    stats = trace_statistics(result)
    assert stats["total_time_min"] is None
    assert stats["known_time_min"] == 0.0
    assert stats["unknown_time_motion_count"] == 1
    assert stats["time_complete"] is False


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_execution_budget_failure_is_structured_and_incomplete(language):
    result = execute(
        "#1=0\nWHILE[#1 LT 20] DO1\n#1=#1+1\nEND1\nM30",
        language,
        limits=ExecutionLimits(macro_iterations=2),
    )
    assert not result.ok
    assert result.complete is False
    assert any(d.code == "RESOURCE_LIMIT" and d.status == "resource_limit" for d in result.diagnostics)


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_modal_state_on_m98_block_is_active_inside_subprogram(language):
    source = "G21\nG20 M98 P100 M8\nM30\nO100\nG1 X1 F1\nM99"
    result = execute(source, language)
    assert result.ok, result.diagnostics
    assert result.motions[0].end_x == pytest.approx(25.4)
    assert result.motions[0].feed == pytest.approx(25.4)
    call_step = next(step for step in result.execution_steps if step.source_block == 1)
    assert call_step.unit_scale == pytest.approx(25.4)
    assert [signal.code for signal in call_step.signals] == ["M08"]


def test_milling_unknown_position_command_fails_closed_without_losing_prior_trace():
    result = execute("G21 G90\nG1 X10 F100\nG123 X20\nG1 X30\nM30", "fanuc_mill")
    assert not result.ok
    assert result.complete is False
    assert [(motion.end_x, motion.end_y, motion.end_z) for motion in result.motions] == [(10.0, 0.0, 0.0)]
    diagnostic = next(d for d in result.diagnostics if d.code == "UNSUPPORTED_G_CODE")
    assert diagnostic.severity == "error"
    assert diagnostic.status == "unsupported"


def test_turn_css_statistics_are_resolved_from_surface_speed_and_g50_limit(fixture_text):
    result = execute(fixture_text("turning/basic_turning_cycles.NC"), "fanuc_turn")
    assert result.ok, result.diagnostics
    stats = trace_statistics(result)
    assert stats["total_time_min"] is not None
    assert stats["unknown_time_motion_count"] == 0
    assert stats["time_complete"] is True


def test_milling_unknown_non_motion_header_with_k_is_warning_not_position_failure():
    result = execute("G1901 K2\nG21 G17 G90\nG0 X1 Y2\nM30", "fanuc_mill")
    assert result.ok, result.diagnostics
    warning = next(d for d in result.diagnostics if d.code == "UNSUPPORTED_G_CODE")
    assert warning.severity == "warning"
    assert (result.motions[-1].end_x, result.motions[-1].end_y) == pytest.approx((1.0, 2.0))


def test_turning_rejects_milling_y_axis_instead_of_silently_ignoring_it():
    result = execute("G21 G17 G90\nG0 X0 Y10\nM30", "fanuc_turn")
    assert not result.ok
    assert any(d.code == "UNSUPPORTED_AXIS" and d.severity == "error" for d in result.diagnostics)


def test_milling_tool_table_applies_g41_geometry_to_g17_contour():
    source = """\
G21 G17 G90
T1 M6
G0 X0 Y0
G1 G41 X10 Y0 F100
G1 X10 Y10
G40 G1 X0 Y10
M30
"""
    result = execute(
        source,
        "fanuc_mill",
        milling_tools={
            "T1": {
                "type": "mill_flat",
                "diameter": 10.0,
                "cornerRadius": 0.0,
                "length": 50.0,
            }
        },
    )
    assert result.ok, result.diagnostics
    compensated = [motion for motion in result.motions if motion.compensation_applied]
    assert len(compensated) == 2
    assert all(motion.tool == "T1" for motion in compensated)
    assert (compensated[0].end_x, compensated[0].end_y) == pytest.approx((5.0, 0.0))
    assert (compensated[1].end_x, compensated[1].end_y) == pytest.approx((5.0, 10.0))


def test_milling_cutter_compensation_visualizes_helical_g17_path():
    source = """\
G21 G17 G90
T2 M6
G0 X0 Y0 Z0
G1 G41 Y50 F100
G2 J-50 Z-1
G2 J-50 Z-2
G40 G1 Y60
M30
"""
    result = execute(
        source,
        "fanuc_mill",
        milling_tools={
            "T2": {
                "type": "mill_flat",
                "diameter": 10.0,
                "cornerRadius": 0.0,
                "length": 50.0,
            }
        },
    )
    assert result.ok, result.diagnostics
    compensated = [motion for motion in result.motions if motion.compensation_applied]
    assert len(compensated) == 3
    assert all(motion.tool == "T2" for motion in compensated)
    assert all(motion.compensation_status == "APPLIED" for motion in compensated)
    assert compensated[1].arc is not None
    assert compensated[2].arc is not None
    assert compensated[1].arc.radius == pytest.approx(55.0)
    assert compensated[2].arc.radius == pytest.approx(55.0)
    assert compensated[1].start_z == pytest.approx(0.0)
    assert compensated[1].end_z == pytest.approx(-1.0)
    assert compensated[2].end_z == pytest.approx(-2.0)


def test_milling_compensation_entry_arc_and_exit_match_cnckernelcli_state_machine():
    source = """\
G21 G17 G90 G40
T1 M6
G0 X0 Y0
G1 Z-1 F300
G41 G1 X5 F100
G3 X0 Y5 I-5 J0
G40 G1 X0 Y0
M30
"""
    result = execute(
        source,
        "fanuc_mill",
        milling_tools={
            "T1": {
                "type": "mill_flat",
                "diameter": 6.0,
                "cornerRadius": 0.0,
                "length": 50.0,
            }
        },
    )
    assert result.ok, result.diagnostics
    entry = next(m for m in result.motions if m.source_kind == "cutter_compensation_entry")
    arc = next(m for m in result.motions if m.source_kind == "cutter_compensation" and m.move == 3)
    exit_motion = next(m for m in result.motions if m.source_kind == "cutter_compensation_exit")
    assert (entry.end_x, entry.end_y) == pytest.approx((2.0, 0.0))
    assert (arc.start_x, arc.start_y) == pytest.approx((2.0, 0.0))
    assert arc.arc is not None
    assert arc.arc.radius == pytest.approx(2.0)
    assert (exit_motion.start_x, exit_motion.start_y) == pytest.approx((arc.end_x, arc.end_y))
    points = render_trace(result)
    assert any((point.x, point.y) == pytest.approx((2.0, 0.0)) for point in points)


def test_milling_compensation_builds_outside_corner_transition():
    source = """\
G21 G17 G90 G40
T1 M6
G0 X-72 Y-72
G1 Z-10 F3000
G41 G1 X-40 F1200
G1 X-40 Y30
G1 X40 Y30
G40 G1 Y-72
M30
"""
    result = execute(
        source,
        "fanuc_mill",
        milling_tools={
            "T1": {
                "type": "mill_flat",
                "diameter": 6.0,
                "cornerRadius": 0.0,
                "length": 50.0,
            }
        },
    )
    assert result.ok, result.diagnostics
    entry = next(m for m in result.motions if m.source_kind == "cutter_compensation_entry")
    assert (entry.end_x, entry.end_y) == pytest.approx((-43.0, -72.0))
    transition = next(m for m in result.motions if m.source_kind == "cutter_compensation_transition")
    assert transition.arc is not None
    assert transition.arc.radius == pytest.approx(3.0)
    assert transition.compensation_applied is True


def test_milling_compensation_uses_configured_tool_diameter_in_rendered_geometry():
    source = """\
G21 G17 G90 G40
T1 M6
G0 X0 Y0
G41 G1 X10 Y0 F100
G1 X10 Y20
G40 G1 X0 Y20
M30
"""
    small = execute(
        source,
        "fanuc_mill",
        milling_tools={"T1": {"type": "mill_flat", "diameter": 6.0, "length": 50.0}},
    )
    large = execute(
        source,
        "fanuc_mill",
        milling_tools={"T1": {"type": "mill_flat", "diameter": 10.0, "length": 50.0}},
    )
    assert small.ok and large.ok
    small_entry = next(m for m in small.motions if m.source_kind == "cutter_compensation_entry")
    large_entry = next(m for m in large.motions if m.source_kind == "cutter_compensation_entry")
    assert small_entry.end_x == pytest.approx(7.0)
    assert large_entry.end_x == pytest.approx(5.0)
