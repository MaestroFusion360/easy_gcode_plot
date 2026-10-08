"""Native SINUMERIK expressions, bounded flow and circular drilling regressions."""

import math
from pathlib import Path

import pytest

from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import export_result
from app.gcode.export.full import export_full_mill_program
from app.gcode.kernel import execute
from app.gcode.kernel.api.resources import ExecutionLimits
from app.gcode.kernel.frontend import program as frontend_program
from app.gcode.kernel.frontend import sinumerik
from app.gcode.kernel.frontend.ast import SinumerikFlowAstNode, _build_program_ast_python
from app.gcode.kernel.milling import executor, sinumerik_parameters

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/milling/sinumerik"


def native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


def parameters(result):
    return dict(result.execution_steps[-1].sinumerik_parameters)


def test_degree_trigonometry_and_precedence_in_drilling_macro():
    result = native(
        "R1=100\nR2=18\nR3=10\nR6=360./R3\nR7=0\nR8=R7*R6+R2\nR9=R1*COS(R8)\nR10=R1*SIN(R8)\nG0 X=(R9+1)-1 Y=R10\nM30"
    )
    assert result.ok and result.complete and not result.diagnostics
    values = parameters(result)
    assert values[6] == 36 and values[8] == 18
    assert values[9] == pytest.approx(100 * math.cos(math.radians(18)))
    assert values[10] == pytest.approx(100 * math.sin(math.radians(18)))
    assert (result.motions[-1].end_x, result.motions[-1].end_y) == pytest.approx((values[9], values[10]))
    assert all(not step.variables for step in result.execution_steps)


def test_while_has_native_ast_and_finishes_at_ten_without_motion():
    result = native("R1=0\nWHILE R1<10\nR1=R1+1\nENDWHILE\nM30")
    assert result.ok and result.complete and not result.diagnostics
    assert not result.motions and parameters(result)[1] == 10
    assert isinstance(result.program.ast.nodes[1], SinumerikFlowAstNode)
    assert result.program.ast == _build_program_ast_python(result.program.blocks)


def test_nested_loops_pair_by_stack_and_skip_zero_iteration_body():
    result = native(
        "R1=0\nR3=0\nWHILE R1<3\nR2=0\nWHILE R2<2\nR3=R3+1\n"
        "R2=R2+1\nENDWHILE\nR1=R1+1\nENDWHILE\nWHILE 0\nG0 X999\nENDWHILE\nM30"
    )
    assert result.ok and result.complete and not result.motions
    assert parameters(result) == {1: 3, 2: 2, 3: 6}


@pytest.mark.parametrize(
    "source,code,line",
    [
        ("WHILE 1\nG0 X999", "INVALID_SINUMERIK_FLOW", 1),
        ("ENDWHILE\nG0 X999", "INVALID_SINUMERIK_FLOW", 1),
        ("R1=1+\nG0 X999", "INVALID_SINUMERIK_EXPRESSION", 1),
        ("R1=1/0\nG0 X999", "INVALID_SINUMERIK_EXPRESSION", 1),
        ("R1=SQRT(-1)\nG0 X999", "INVALID_SINUMERIK_EXPRESSION", 1),
        ("R1=R99+1\nG0 X999", "UNDEFINED_SINUMERIK_PARAMETER", 1),
        ("R1=1\nWHILE R99<2\nG0 X999\nENDWHILE", "UNDEFINED_SINUMERIK_PARAMETER", 2),
        ("R1=1\nX=SIN()\nG0 X999", "INVALID_SINUMERIK_EXPRESSION", 2),
        ("R1=1\nX=R1**2\nG0 X999", "INVALID_SINUMERIK_EXPRESSION", 2),
        ("R1=" + "(" * 34 + "1" + ")" * 34, "INVALID_SINUMERIK_EXPRESSION", 1),
        ("R1=" + "+".join(["1"] * 150), "INVALID_SINUMERIK_EXPRESSION", 1),
    ],
)
def test_errors_fail_closed_with_source_location(source, code, line):
    result = native(source)
    assert not result.ok and not result.complete and not result.motions
    assert result.diagnostics[0].code == code
    assert result.diagnostics[0].line == line
    assert result.diagnostics[0].raw == source.splitlines()[line - 1]


@pytest.mark.parametrize("limits", [ExecutionLimits(macro_iterations=3), ExecutionLimits(executed_blocks=12)])
def test_infinite_loop_consumes_shared_budget(limits):
    result = native("R1=1\nWHILE R1>0\nR1=R1\nENDWHILE\nG0 X999", limits=limits)
    assert not result.ok and not result.complete and not result.motions
    assert result.diagnostics[-1].code == "RESOURCE_LIMIT"


def test_cancellation_checkpoint_inside_expression_loop():
    calls = 0

    def cancel():
        nonlocal calls
        calls += 1
        return calls > 200

    result = native("R1=1\nWHILE R1>0\nR1=R1\nENDWHILE\nG0 X999", cancelled=cancel)
    assert not result.ok and not result.complete and not result.motions
    assert result.diagnostics[-1].code == "EXECUTION_CANCELLED"


def test_goto_and_if_use_ast_labels_without_skipped_geometry():
    source = "R1=0\nN10 R1=R1+1\nIF R1<3 GOTO N10\nGOTO N30\nG0 X999\nN30 G0 X=R1\nM30"
    result = native(source)
    assert result.ok and result.complete and not result.diagnostics
    assert parameters(result)[1] == 3
    assert len(result.motions) == 1 and result.motions[0].end_x == 3
    text = export_full_mill_program(result, source.splitlines(), ExportOptions(delimiter=True))
    replay = native(text)
    assert replay.ok and replay.complete and parameters(replay)[1] == 3
    assert "N10" in text and "N30" in text
    with pytest.raises(ValueError, match="Sequence numbers"):
        export_full_mill_program(result, source.splitlines(), ExportOptions(sequence_numbers=True))


@pytest.mark.parametrize("operation", ["GOTO N99", "IF 0 GOTO N99", "GOTO N10\nN10 G0 X1\nN10 G0 X2"])
def test_missing_or_duplicate_jump_target_fails_closed(operation):
    result = native(operation + "\nG0 X999")
    assert not result.ok and not result.complete and not result.motions
    assert result.diagnostics[0].code in {"FLOW_TARGET_MISSING", "INVALID_SINUMERIK_FLOW"}


@pytest.mark.parametrize("operation", ["GOTOF N10", "GOTOB N10", "GOTOC N10", "RET", "IF 1 GOTOF N10"])
def test_unverified_direction_and_return_forms_remain_closed(operation):
    result = native(operation + "\nN10 G0 X999")
    assert not result.ok and not result.complete and not result.motions
    assert result.diagnostics[0].code == "UNSUPPORTED_SINUMERIK_FLOW"


def test_mcall_cycle83_inside_while():
    source = "R1=0\nG90 G17 G54\nG0 X0 Y0 Z10\nMCALL CYCLE83(10,5,2,-12,0,3,0,0,0,0,0)\n"
    result = native(source + "WHILE R1<2\nG91 G1 X1\nR1=R1+1\nENDWHILE\nMCALL\nM30")
    assert result.ok and result.complete and not result.diagnostics
    assert parameters(result)[1] == 2
    assert len({motion.end_x for motion in result.motions if motion.cycle_generated}) == 2


def test_actual_circular_drilling_fixture():
    result = native((FIXTURES / "macro_drilling.mpf").read_text())
    assert result.ok and result.complete and result.program_end == "M30" and not result.diagnostics
    assert len(result.motions) == 33
    cuts = [motion for motion in result.motions if motion.cycle_generated and motion.move == 1]
    assert len(cuts) == 10
    for index, motion in enumerate(cuts):
        angle = math.radians(18 + 36 * index)
        assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx(
            (100 * math.cos(angle), 100 * math.sin(angle), -20)
        )
        assert motion.start_z == 5
    assert parameters(result)[6] == 36 and parameters(result)[7] == 10 and parameters(result)[8] == 342
    assert parameters(result)[11] == pytest.approx(100 * math.cos(math.radians(342)))
    assert parameters(result)[12] == pytest.approx(100 * math.sin(math.radians(342)))
    assert result.motions[-1].end_z == 0 and not result.motions[-1].cycle_generated
    assert all(not step.variables for step in result.execution_steps)


def test_macro_native_and_portable_parser_executor_parity(monkeypatch):
    source = (FIXTURES / "macro_drilling.mpf").read_text() + "\n"
    accelerated = native(source)
    monkeypatch.setattr(executor, "_execute_simple_blocks", None)
    monkeypatch.setattr(frontend_program, "native_symbol", lambda *_: None)
    monkeypatch.setattr(sinumerik, "build_program_ast", _build_program_ast_python)
    assert native(source) == accelerated


def test_macro_execution_consumes_compiled_expression_trees(monkeypatch):
    source = (FIXTURES / "macro_drilling.mpf").read_text()

    def resolved(_program):
        def forbidden(_expression):
            pytest.fail("Runtime reparsed a native macro expression")

        monkeypatch.setattr(sinumerik_parameters, "compile_expression", forbidden)
        return {}

    result = native(source, tool_resolver=resolved)
    assert result.ok and result.complete and not result.diagnostics
    assert parameters(result)[7] == 10


def test_cycle_arguments_accept_compiled_expressions():
    source = "R1=10\nG0 Z20\nMCALL CYCLE81(5+COS(0),0,5,-R1*2)\nX=R1+2\nMCALL\nM30"
    result = native(source)
    assert result.ok and result.complete and not result.diagnostics
    cuts = [motion for motion in result.motions if motion.cycle_generated and motion.move == 1]
    assert len(cuts) == 1 and cuts[0].end_x == 12 and cuts[0].end_z == -20


def test_compact_sequence_labels_are_preserved_for_native_jumps():
    result = native("GOTO N10\nG0 X999\nN10G0 X1\nM30")
    assert result.ok and result.complete and len(result.motions) == 1 and result.motions[0].end_x == 1


def test_m19_preserves_spindle_and_position_and_emits_no_motion():
    result = native("S800 M3\nG0 X1 Y2 Z3\nM19\nM4\nM5\nM3\nM30")
    assert result.ok and result.complete and not result.diagnostics and len(result.motions) == 1
    before, orient = result.execution_steps[1:3]
    assert orient.position == before.position and orient.rotary_angles == before.rotary_angles
    assert orient.spindle_rpm == before.spindle_rpm == 800
    assert orient.spindle_running and before.spindle_running
    assert not orient.emitted_count and [signal.kind for signal in orient.signals] == ["spindle_orient"]
    assert [signal.kind for signal in result.signals] == [
        "spindle_cw",
        "spindle_orient",
        "spindle_ccw",
        "spindle_stop",
        "spindle_cw",
        "program_end",
    ]


def test_native_css_modes_keep_surface_speed_without_inventing_rpm():
    source = "G96 S100 F0.2 M3\nG1 X10\nG961 S200 F100\nX20\nG97 S800 F0.1\nG971 S900 F100\nM30"
    result = native(source)
    assert result.ok and result.complete and not result.diagnostics
    first, _, second, _, third, fourth, _ = result.execution_steps
    assert (first.spindle_mode, first.feed_mode, first.surface_speed_m_min, first.spindle_rpm) == (
        "css",
        "per_revolution",
        100,
        None,
    )
    assert (second.spindle_mode, second.feed_mode, second.surface_speed_m_min, second.spindle_rpm) == (
        "css",
        "per_minute",
        200,
        None,
    )
    assert (third.spindle_mode, third.feed_mode, third.spindle_rpm) == ("rpm", "per_revolution", 800)
    assert (fourth.spindle_mode, fourth.feed_mode, fourth.spindle_rpm) == ("rpm", "per_minute", 900)
    assert all(m.spindle_mode == "css" and m.spindle_rpm is None for m in result.motions)
    text = export_full_mill_program(result, source.splitlines(), ExportOptions(delimiter=True))
    assert native(text).ok
    with pytest.raises(ValueError, match="CSS"):
        export_result(result, ExportOptions(), target="sinumerik_840d")


@pytest.mark.parametrize("code", [96, 97, 961, 971])
def test_spindle_modes_implicit_feed_and_explicit_feed_afterwards(code):
    result = native(f"G{code} S100\nS200\nG94\nM30")
    assert result.ok and not result.diagnostics
    assert result.execution_steps[0].feed_mode == ("per_revolution" if code in (96, 97) else "per_minute")
    assert result.execution_steps[1].spindle_rpm == (None if code in (96, 961) else 200)
    assert result.execution_steps[2].feed_mode == "per_minute"


@pytest.mark.parametrize("operation", ["ANG=30", "G1 X20 ANG=30", "SCALE X2", "ASCALE Y2", "MIRROR X0", "AMIRROR Z0"])
def test_recognized_unmodeled_geometry_never_fabricates_a_trajectory(operation):
    result = native(operation + "\nG0 X999")
    assert not result.ok and not result.complete and not result.motions
    assert result.diagnostics[0].code == "UNMODELED_SINUMERIK_GEOMETRY"


@pytest.mark.parametrize("code", [17, 96, 97, 99])
def test_unmodeled_native_m_flow_fails_closed(code):
    result = native(f"M{code}\nG0 X999")
    assert not result.ok and not result.complete and not result.motions
    assert result.diagnostics[0].code == "UNSUPPORTED_SINUMERIK_M_CODE"


def test_auxiliary_m66_and_m98_preserve_warning_and_avoid_fanuc_dispatch():
    result = native("M66\nM98 P100\nG0 X1\nM30\nO100\nG0 X999\nM99")
    assert result.ok and result.complete and len(result.motions) == 1 and result.motions[0].end_x == 1
    assert all(d.code == "UNSUPPORTED_M_CODE" and d.severity == "warning" for d in result.diagnostics)
    assert not any("SUBPROGRAM" in event.kind for event in result.events)


def test_full_and_expanded_macro_exports_replay_resolved_geometry():
    source = (FIXTURES / "macro_drilling.mpf").read_text()
    result = native(source)
    full = export_full_mill_program(result, source.splitlines(), ExportOptions(delimiter=True))
    assert "WHILE" in full and "COS(R8)" in full and "R7=R7+1" in full
    replay = native(full)
    assert replay.ok and replay.complete and len(replay.motions) == 33 and parameters(replay)[7] == 10
    expanded = export_result(result, ExportOptions(delimiter=True, decimal_places=6), target="fanuc_mill")
    replay = execute(expanded, language="fanuc_mill")
    assert replay.ok and replay.complete and len(replay.motions) == len(result.motions)
    for before, after in zip(result.motions, replay.motions, strict=True):
        assert (before.end_x, before.end_y, before.end_z) == pytest.approx(
            (after.end_x, after.end_y, after.end_z), abs=2e-6
        )
