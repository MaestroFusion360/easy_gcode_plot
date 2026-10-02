"""Regression coverage for the controller boundary and dispatch bypasses."""

from dataclasses import replace

from app.gcode.kernel.api.engine import execute
from app.gcode.kernel.frontend.program import parse_program
from app.gcode.kernel.milling.state import MillState
from app.gcode.kernel.runtime.capabilities import controller_capability_gate
from app.gcode.kernel.runtime.execution import ProgramRuntime
from app.gcode.source_mode import source_dialect_for_path


def _sinumerik(source):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik")


def test_mpf_spf_container_is_native_even_without_siemens_signature():
    for path in ("part.mpf", "PART.SPF"):
        dialect = source_dialect_for_path(path, "G0 X10\nM30")
        assert dialect == "sinumerik"
        result = execute("G0 X10\nM30", language="fanuc_mill", source_dialect=dialect)
        assert result.ok and result.complete
        assert result.motions[-1].end_x == 10
        assert not any(event.kind.startswith("SINUMERIK_") for event in result.events)


def test_runtime_mode_switches_only_when_blocks_are_executed():
    program = parse_program("G0 X1\nG291\nG290")
    runtime = ProgramRuntime.create(program)
    runtime.controller_mode = "sinumerik_native"
    state = MillState()
    for block, expected in zip(program.blocks, ("sinumerik_native", "sinumerik_iso", "sinumerik_native")):
        evaluated = runtime.evaluate_block(block)
        _, diagnostic, _ = controller_capability_gate(runtime, block, evaluated, state=state)
        assert diagnostic is None
        assert runtime.controller_mode == expected


def test_native_common_iso_core_matches_fanuc_geometry_and_signals():
    source = (
        "G21 G90 G17\nT1 M6\nS1200 M3\nG0 X0 Y0 Z0\nG1 X10 F100\n"
        "G2 X20 Y0 I15 J0\nG3 X10 Y0 I15 J0\nG18\nG19\nG17\n"
        "G91\nG1 X1\nG4 P1\nM5\nM30"
    )
    native = _sinumerik(source)
    fanuc = execute(source, language="fanuc_mill", source_arc_type=2)
    assert native.ok and native.complete, native.diagnostics
    assert tuple(replace(motion, source_arc_type=None) for motion in native.motions) == fanuc.motions
    assert native.signals == fanuc.signals
    assert native.events == fanuc.events


def test_rejected_flow_never_reaches_fanuc_dispatch(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("FANUC dispatch must not run")

    monkeypatch.setattr(ProgramRuntime, "dispatch_program_flow", forbidden)
    monkeypatch.setattr(ProgramRuntime, "dispatch_g65", forbidden)
    for operation in ("M98 P123", "M99", "G65 P123", "G74 X10"):
        result = _sinumerik("G291\n" + operation + "\nG0 X99")
        assert not result.ok and not result.complete
        assert result.diagnostics[0].status == "unsupported"
        assert result.diagnostics[0].line == 2
        assert not result.motions


def test_macro_b_is_rejected_before_evaluation_or_dispatch(monkeypatch):
    original = ProgramRuntime.evaluate_block

    def guarded(self, block):
        assert block.index == 0, "Macro expression must not be evaluated"
        return original(self, block)

    monkeypatch.setattr(ProgramRuntime, "evaluate_block", guarded)
    for operation in ("#1=10", "G1 X#1", "IF [1 EQ 1] THEN #1=2", "WHILE [1 EQ 1] DO1", "GOTO 10", "END1"):
        result = _sinumerik("G291\n" + operation + "\nG0 X99")
        assert not result.ok and not result.complete
        assert result.diagnostics[0].code == "UNSUPPORTED_SINUMERIK_ISO_MACRO"
        assert not result.motions


def test_unknown_native_syntax_cannot_be_partially_executed():
    for operation in ("TRAORI", "CYCLE800(1,2,3)", "R1=R2+10", "G1 X=R99", "TRANS X10", "CALL PART"):
        result = _sinumerik("G0 X1\n" + operation + "\nG0 X99")
        assert not result.ok and not result.complete
        assert result.diagnostics[0].status == "unsupported"
        assert result.motions[-1].end_x == 1


def test_switch_changes_later_blocks_without_looking_ahead():
    result = _sinumerik("G0 X1\nG291\nG70\nG0 X2\nG290\nG1 X3 F100\nG70\nG0 X99")
    assert not result.ok and not result.complete
    assert [event.code for event in result.events if event.kind.startswith("SINUMERIK_")] == ["G291", "G290"]
    assert result.motions[-1].end_x == 3 * 25.4
    assert result.diagnostics[0].line == 7


def test_iso_modal_cycle_cannot_leak_into_native_coordinates():
    result = _sinumerik("G291\nG81 Z-2 R1 F100\nG290\nX99")
    assert not result.ok and not result.complete
    assert result.diagnostics[0].line == 3
    assert not any(motion.end_x == 99 for motion in result.motions)


def test_native_rejects_iso_only_cycles_and_tcp_before_state_changes():
    for operation in ("G81 X10 Z-2 R1 F100", "G43.4 H1", "G68.2 X10 I0 J0 K0", "T2 M98 P123"):
        result = _sinumerik(operation + "\nG0 X99")
        assert not result.ok and not result.complete
        assert result.diagnostics[0].status == "unsupported"
        assert not result.motions
        assert not any(event.kind == "TOOL_CHANGE" for event in result.events)
