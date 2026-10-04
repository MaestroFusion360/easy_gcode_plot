"""Minimal CAM R state and native analytical multiple-turn arcs."""

import math

import pytest

from app.gcode.export.dxf import build_dxf_document
from app.gcode.export.trace import export_result
from app.gcode.kernel import execute
from app.gcode.kernel.frontend.ast import SinumerikAstNode, _build_program_ast_python
from app.gcode.trace_tools import motion_length, sample_motion, trace_statistics
from app.ui.plot.playback import build_playback_movements


def native(source):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik")


def test_native_dwell_seconds_preserve_modal_feed_and_resolve_parameters():
    result = native("R1=2\nG1 X1 F100\nG4 F=R1\nX2\nM30")
    assert result.ok and result.complete
    assert [motion.feed for motion in result.motions] == [100, 100]
    assert (
        sum(signal.value for step in result.execution_steps for signal in step.signals if signal.kind == "dwell") == 2
    )


def test_native_negative_dwell_fails_closed():
    assert not native("G4 F-1").ok


def test_native_revolution_dwell_warns_without_changing_spindle_or_time():
    result = native("S500 M3\nG1 X1 F100\nG4 S2\nX2\nM30")
    assert result.ok and result.complete
    assert [motion.spindle_rpm for motion in result.motions] == [500, 500]
    assert [motion.feed for motion in result.motions] == [100, 100]
    assert any(d.code == "UNMODELED_SINUMERIK_NATIVE" and d.severity == "warning" for d in result.diagnostics)
    assert not any(signal.kind == "dwell" for step in result.execution_steps for signal in step.signals)


def test_r_parameters_keep_native_ast_and_never_enter_macro_b_state():
    result = native("R1=500\nR2=1200\nR10=3.5\nS=R2 M3\nG1 X=R10 Y=R10 Z=R10 F=R1\nR10=-2\nX=R10\nM30")
    assert result.ok and result.complete and not result.diagnostics
    assert isinstance(result.program.ast.nodes[0], SinumerikAstNode)
    assert result.program.ast == _build_program_ast_python(result.program.blocks)
    assert result.program.ast.nodes[0].native_syntax.parameter_assignment == (1, "500")
    assert result.motions[0].feed == 500
    assert result.motions[0].spindle_rpm == 1200
    assert result.motions[-1].end_x == -2
    assert all(not step.variables for step in result.execution_steps)
    assert not native("G1 X=R10").ok


def test_r_parameters_in_centers_cycles_and_across_mode_switches():
    result = native(
        "R1=0\nR2=500\nR3=1.25\nS=R2 M3\nG0 X10\nG3 X0 Y10 I=AC(R1) J=AC(R1) F=R2\nG291\nG290\n"
        "MCALL CYCLE84(5,0,2,-9,,0,3,,R3,0,R2,R2)\nX2\nMCALL\nM30"
    )
    assert result.ok and result.complete and not result.diagnostics
    assert result.motions[1].arc.center == (0, 0, 0)
    assert [m.feed for m in result.motions if m.cycle_generated and m.move == 1] == [625, 625]
    assert not native("R1=2\nG291\nG1 X=R1").ok


def test_mcall_r_parameters_are_rechecked_at_each_hole():
    result = native("S500 M3\nR1=1.25\nMCALL CYCLE84(5,0,2,-9,,0,3,,R1,0,500,500)\nX2\nR1=2\nX3\nMCALL\nM30")
    assert result.ok and result.complete
    assert [m.feed for m in result.motions if m.move == 1] == [625, 625, 1000, 1000]


@pytest.mark.parametrize(
    "source", ["X=R99", "R1=R2+10", "R1=1\nF=R1*0.8", "R1=1\nIF R1==1 GOTO10", "R[1]=2", "$AA_IM[X]=2"]
)
def test_unmodeled_r_language_fails_closed(source):
    result = native(source)
    assert not result.ok and not result.complete and not result.motions


@pytest.mark.parametrize(
    "plane,position,end,center",
    [
        (17, "X10", "X0 Y10 Z-6", "I=AC(0) J=AC(0)"),
        (18, "X10", "X0 Z10 Y-6", "I=AC(0) K=AC(0)"),
        (19, "Y10", "Y0 Z10 X-6", "J=AC(0) K=AC(0)"),
    ],
)
@pytest.mark.parametrize("move", [2, 3])
def test_turn_is_one_analytical_motion_with_total_sweep_and_trace_replay(plane, position, end, center, move):
    result = native(f"G{plane} G0 {position}\nG{move} {end} {center} TURN=3 F100\nM30")
    assert result.ok and result.complete and len(result.motions) == 2
    arc = result.motions[-1]
    assert arc.arc.sweep > 3 * math.tau
    assert motion_length(arc) == pytest.approx(math.hypot(10 * arc.arc.sweep, 6))
    points = sample_motion(arc, 1, arc_points_per_circle=100)
    assert len(points) > 300
    replay = execute(export_result(result), language="fanuc_mill")
    assert replay.ok and replay.complete
    assert sum(m.arc.sweep for m in replay.motions if m.arc) == pytest.approx(arc.arc.sweep, abs=1e-6)
    assert sum(map(motion_length, replay.motions)) == pytest.approx(sum(map(motion_length, result.motions)), abs=1e-5)


@pytest.mark.parametrize("turn", ["-1", "1.5", "1000"])
def test_invalid_turn_fails_before_arc(turn):
    result = native("G0 X10\nG3 X0 Y10 I=AC(0) J=AC(0) TURN=" + turn)
    assert not result.ok and len(result.motions) == 1
    assert result.diagnostics[0].code == "UNSUPPORTED_SINUMERIK_TURN"


def test_turn_full_circle_adds_revolutions_to_base_circle():
    result = native("G0 X10\nG3 I=AC(0) J=AC(0) TURN=2 F100\nM30")
    assert result.ok
    assert result.motions[-1].arc.sweep == pytest.approx(3 * math.tau)
    assert result.motions[-1].arc.full_circle


def test_turn_render_statistics_playback_and_dxf_preserve_all_revolutions():
    result = native("G0 X10\nG3 I=AC(0) J=AC(0) TURN=2 F100\nM30")
    statistics = trace_statistics(result)
    assert statistics["feed_length"] == pytest.approx(30 * math.tau)
    assert statistics["feed_time_min"] == pytest.approx(30 * math.tau / 100)
    assert statistics["bounds"] == ((-10, 10), (-10, 10), (0, 0))
    movements, mapping = build_playback_movements(result.motions)
    assert len(movements) == 2 and mapping == (0, 1)
    entities = list(build_dxf_document(result).modelspace())
    polyline = next(entity for entity in entities if entity.dxftype() in ("LWPOLYLINE", "POLYLINE"))
    vertices = list(polyline.get_points()) if polyline.dxftype() == "LWPOLYLINE" else list(polyline.points())
    assert len(vertices) > 100
