"""SINUMERIK source facts, runtime semantics and contiguous acceleration."""

# pylint: disable=protected-access
import csv
import gc
import sys
from dataclasses import FrozenInstanceError, replace
from statistics import median
from time import perf_counter

import pytest

from app import cli
from app.gcode.batch import analyze_directory, write_batch_reports
from app.gcode.batch_export import export_directory, write_export_reports
from app.gcode.export.service import ExportRequest
from app.gcode.kernel import execute
from app.gcode.kernel.api.resources import ExecutionBudget, SemanticError, active_budget
from app.gcode.kernel.frontend import sinumerik
from app.gcode.kernel.frontend.ast import SinumerikAstNode, _build_program_ast_python
from app.gcode.kernel.frontend.model import Program
from app.gcode.kernel.milling import executor


def _native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


def test_rotary_is_rejected_in_both_modes_and_fanuc_still_executes():
    for axis, profile in (("A", "4ax_table_a"), ("B", "4ax_table_b"), ("C", "4ax_table_c")):
        source = f"G0 {axis}10\nM30"
        for prefix in ("", "G291\n"):
            result = _native(prefix + source, kinematics=profile)
            assert not result.ok and not result.complete
            assert result.diagnostics[0].code == "UNSUPPORTED_SINUMERIK_ROTARY"
            assert not result.motions and not any(event.kind == "ROTARY_INDEX" for event in result.events)
        fanuc = execute(source, language="fanuc_mill", kinematics=profile)
        assert fanuc.ok and fanuc.complete
        assert dict(fanuc.rotary_angles)[axis] == 10


def test_mixed_arc_modes_are_resolved_per_motion_with_wcs_and_helix():
    source = (
        "G17 G90 G0 X10 Y0 Z0\nG3 X0 Y10 Z-1 I=AC(0) J=AC(0) F100\nG291\n"
        "G3 X-10 Y0 Z-2 I0 J-10\nG290\nG3 X0 Y-10 Z-3 I=AC(0) J=AC(0)\nM30"
    )
    for legacy_mode in (1, 2, 3):
        result = _native(source, source_arc_type=legacy_mode, autodetect_arc_type=True, wcs_offsets={54: (20, 30, 40)})
        assert result.ok and result.complete and not result.diagnostics
        arcs = [motion for motion in result.motions if motion.arc]
        assert [motion.source_arc_type for motion in arcs] == [1, 1, 1]
        assert [motion.arc.radius for motion in arcs] == pytest.approx([10, 10, 10])
        assert [(motion.arc.center[0], motion.arc.center[1]) for motion in arcs] == [(20, 30)] * 3
        assert result.source_dialect == "sinumerik"


def test_result_family_is_immutable_and_reaches_cli_documents():
    for dialect, source in (("fanuc", "G0 X1"), ("sinumerik", "G0 X1\nG291\nG290")):
        result = execute(source, language="fanuc_mill", source_dialect=dialect)
        assert result.source_dialect == dialect
        assert cli._result_document(result, include_motions=True)["source_dialect"] == dialect
        assert cli._analysis_document(result)["source_dialect"] == dialect
        with pytest.raises(FrozenInstanceError):
            result.source_dialect = "changed"


def test_batch_classifies_structured_sinumerik_codes_and_excludes_syntax(tmp_path):
    sources = {
        "macro.mpf": "G65 P9000",
        "call.spf": "M98 P100",
        "return.mpf": "M99",
        "iso.mpf": "G291\nG66",
        "m.mpf": "M19",
        "syntax.mpf": "TRAORI",
    }
    for name, source in sources.items():
        (tmp_path / name).write_text(source)
    report = analyze_directory(tmp_path, language="fanuc_mill", encoding="utf-8")
    assert {item["code"] for item in report["summary"]["unsupported_g_codes"]} == {"G65", "G66"}
    assert {item["code"] for item in report["summary"]["unsupported_m_codes"]} == {"M98", "M99", "M19"}
    assert all(item["source_dialect"] == "sinumerik" for item in report["files"])
    _, csv_path = write_batch_reports(report, tmp_path / "reports")
    with csv_path.open(encoding="utf-8-sig") as stream:
        assert all(row["source_dialect"] == "sinumerik" for row in csv.DictReader(stream))


def test_batch_export_preserves_source_family_in_json_and_csv(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    (root / "part.mpf").write_text("G0 X1\nM30")
    report = export_directory(root, tmp_path / "output", ExportRequest(language="fanuc_mill"))
    assert report["files"][0]["source_dialect"] == "sinumerik"
    _, csv_path = write_export_reports(report, tmp_path / "reports")
    with csv_path.open(encoding="utf-8-sig") as stream:
        assert next(csv.DictReader(stream))["source_dialect"] == "sinumerik"


def test_native_ast_is_built_once_and_rejects_divergent_source_facts(monkeypatch):
    native_parser = pytest.importorskip("app.gcode.kernel.frontend._native_parser")

    def discarded_ast(*_args):
        pytest.fail("SINUMERIK used the FANUC Program/AST parser before augmentation")

    monkeypatch.setattr(native_parser, "parse_source", discarded_ast)
    original = sinumerik.build_program_ast
    calls = []

    def counted(blocks):
        calls.append(blocks)
        return original(blocks)

    monkeypatch.setattr(sinumerik, "build_program_ast", counted)
    source = 'O100\nN10 MSG("ready")\nN20 MCALL CYCLE81(5,-1,5,-10,)\nMCALL\nG0 SUPA Z0 D0\nG2 X10 CR=10'
    program = sinumerik.parse_sinumerik_program(source)
    assert len(calls) == 1
    assert program.ast == _build_program_ast_python(program.blocks)
    assert isinstance(program.ast.nodes[1], SinumerikAstNode)
    assert program.ast.nodes[2].native_syntax.cycle_code == 81
    assert program.ast.nodes[4].native_syntax.supa
    assert dict(program.ast.nlabel_to_index) == {10: 1, 20: 2}
    assert dict(program.ast.olabel_to_index) == {100: 0}
    altered = replace(program.blocks[2], native_syntax=replace(program.blocks[2].native_syntax, cycle_code=82))
    with pytest.raises(ValueError, match="does not match"):
        Program(program.blocks[:2] + (altered,) + program.blocks[3:], program.ast)


def test_common_native_execution_uses_compiled_path_with_reference_parity(monkeypatch):
    compiled = executor._execute_simple_blocks
    if compiled is None:
        pytest.skip("Native extension required")
    consumed = []

    def instrumented(*args):
        count = compiled(*args)
        consumed.append(count)
        return count

    source = "G17 G90 G0 X10 Y0 Z0\nG3 X0 Y10 I-10 J0 F100\nX-10 Y0 I0 J-10\nG91\nG1 X2\nX3\nM30"
    monkeypatch.setattr(executor, "_execute_simple_blocks", instrumented)
    native = _native(source, wcs_offsets={54: (20, 30, 40)})
    assert sum(consumed) >= 2
    monkeypatch.setattr(executor, "_execute_simple_blocks", None)
    reference = _native(source, wcs_offsets={54: (20, 30, 40)})
    assert native == reference


@pytest.mark.parametrize(
    "operation",
    [
        "G291",
        "G290",
        'MSG("hello")',
        'WORKPIECE("",0,0,0)',
        "G2 X10 CR=10",
        "G66",
        "M19",
        "#1=1",
        "G65 P9000",
        "M98 P100",
        "M99",
        "MCALL CYCLE81(5,-1,5,-10,)",
        "G0 A10",
    ],
)
def test_controller_specific_block_stops_run_without_disabling_previous_positions(monkeypatch, operation):
    compiled = executor._execute_simple_blocks
    if compiled is None:
        pytest.skip("Native extension required")
    consumed = []

    def instrumented(program, runtime, *args):
        start = runtime.pc
        count = compiled(program, runtime, *args)
        consumed.extend(range(start, start + count))
        return count

    source = "G0 X1\nX2\nX3\n" + operation + "\nX4\nMCALL\nX5\nM30"
    monkeypatch.setattr(executor, "_execute_simple_blocks", instrumented)
    accelerated = _native(source)
    assert consumed[:2] == [1, 2]
    assert 3 not in consumed
    monkeypatch.setattr(executor, "_execute_simple_blocks", None)
    reference = _native(source)
    assert accelerated == reference


@pytest.mark.parametrize("cycle", ["CYCLE81(5,0,2,-9,)", "CYCLE84(5,0,2,-9,,0,3,,1.25,0,500,500)"])
def test_compiled_runs_resume_after_metadata_and_native_cycle_cancel(monkeypatch, cycle):
    compiled = executor._execute_simple_blocks
    if compiled is None:
        pytest.skip("Native extension required")
    runs = []

    def instrumented(program, runtime, state, *args):
        start = runtime.pc
        count = compiled(program, runtime, state, *args)
        if count:
            assert state.native_cycle is None
            runs.append(tuple(range(start, start + count)))
        return count

    source = 'S500 M3\nG0 Z10\nX1\nX2\nMSG("tap")\nX3\nX4\nMCALL ' + cycle + "\nX5\nX6\nMCALL\nX7\nX8\nM30"
    monkeypatch.setattr(executor, "_execute_simple_blocks", instrumented)
    accelerated = _native(source, wcs_offsets={54: (20, 30, 40)})
    assert accelerated.ok and accelerated.complete
    assert runs == [(2, 3), (5, 6), (11, 12)]
    monkeypatch.setattr(executor, "_execute_simple_blocks", None)
    assert accelerated == _native(source, wcs_offsets={54: (20, 30, 40)})


def test_compiled_runs_follow_mixed_native_iso_arc_modes(monkeypatch):
    compiled = executor._execute_simple_blocks
    if compiled is None:
        pytest.skip("Native extension required")
    modes = []

    def instrumented(program, runtime, state, *args):
        mode = runtime.controller_mode
        count = compiled(program, runtime, state, *args)
        if count:
            modes.append(mode)
        return count

    source = (
        "G17 G90 G0 X10 Y0\nG3 X0 Y10 I-10 J0 F100\nX-10 Y0 I0 J-10\n"
        "G291\nG0 X10 Y0\nG3 X0 Y10 I-10 J0\nX-10 Y0 I0 J-10\n"
        "G290\nG0 X10 Y0\nG3 X0 Y10 I-10 J0\nX-10 Y0 I0 J-10\nM30"
    )
    monkeypatch.setattr(executor, "_execute_simple_blocks", instrumented)
    accelerated = _native(source, wcs_offsets={54: (20, 30, 40)})
    assert accelerated.ok
    assert modes == ["sinumerik_native", "sinumerik_iso", "sinumerik_native"]
    monkeypatch.setattr(executor, "_execute_simple_blocks", None)
    assert accelerated == _native(source, wcs_offsets={54: (20, 30, 40)})


@pytest.mark.performance
@pytest.mark.parametrize("dialect", ["fanuc", "sinumerik"])
def test_large_position_runs_keep_speedup_with_controller_fallback(monkeypatch, record_property, dialect):
    compiled = executor._execute_simple_blocks
    if compiled is None:
        pytest.skip("Native extension required")
    positions = "\n".join(f"X{i % 101} Y{i % 37} Z10" for i in range(4000))
    boundary = (
        '\nMSG("tap")\nMCALL CYCLE84(5,0,2,-9,,0,3,,1.25,0,500,500)\nX2 Y3\nMCALL\nG1 Z10\n'
        if dialect == "sinumerik"
        else "\n"
    )
    source = "G17 G90 G94\nS500 M3\nG1 F200\n" + positions + boundary + positions + "\nM30"
    samples, results = [[], []], [None, None]
    for repeat in range(3):
        for index in (0, 1) if repeat % 2 == 0 else (1, 0):
            monkeypatch.setattr(executor, "_execute_simple_blocks", compiled if index == 0 else None)
            gc.collect()
            start = perf_counter()
            result = execute(source, language="fanuc_mill", source_dialect=dialect)
            samples[index].append(perf_counter() - start)
            assert result.ok and result.complete
            results[index] = result
    assert results[0] == results[1]
    fast, reference = map(median, samples)
    record_property("compiled_execution_seconds", fast)
    record_property("reference_execution_seconds", reference)
    record_property("compiled_to_reference_ratio", fast / reference)
    assert fast < reference * 0.9, f"Lost contiguous-run speedup: {fast / reference:.3f}"


def test_native_parse_fallback_and_cancellation_preserve_source_contract(monkeypatch):
    source = 'O100\nN10 MSG("ready")\nG0 X1\nMCALL CYCLE81(5,-1,5,-10,)\nMCALL'
    compiled = sinumerik.parse_sinumerik_program(source)
    monkeypatch.setitem(sys.modules, "app.gcode.kernel.frontend._native_parser", None)
    assert sinumerik.parse_sinumerik_program(source) == compiled
    token = active_budget.set(ExecutionBudget(cancelled=lambda: True))
    try:
        with pytest.raises(SemanticError, match="cancelled"):
            sinumerik.parse_sinumerik_program(source)
    finally:
        active_budget.reset(token)


def test_native_absolute_centers_preserve_vertical_planes_and_missing_address():
    for plane, position, move in ((18, "X10 Y0 Z0", "X0 Z10 I=AC(0)"), (19, "X0 Y10 Z0", "Y0 Z10 J=AC(0)")):
        result = _native(f"G{plane} G90 G0 {position}\nG2 {move} F100\nM30", wcs_offsets={54: (20, 30, 40)})
        assert result.ok and not result.diagnostics
        assert result.motions[-1].arc.plane == plane
        assert result.motions[-1].arc.center == (20, 30, 40)
        assert result.motions[-1].arc.radius == 10
