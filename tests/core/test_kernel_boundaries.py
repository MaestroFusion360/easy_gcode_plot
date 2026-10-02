"""Reproducibility, immutable frontend graphs and process-local boundaries."""

import csv
import gc
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from threading import Barrier

import pytest

from app.cli import _analysis_document, _result_document, main
from app.gcode.kernel import execute
from app.gcode.kernel.frontend.ast import ProgramAst
from app.gcode.kernel.frontend.model import Program
from app.gcode.kernel.frontend.program import _parse_program_python, parse_program
from app.gcode.kernel.milling.kinematics import RotaryAxis, load_catalog


def test_concurrent_kernel_execution_never_changes_process_gc(monkeypatch):
    barrier = Barrier(2)
    original = gc.isenabled()

    def forbidden():
        pytest.fail("Kernel must not change process-global GC")

    monkeypatch.setattr(gc, "disable", forbidden)
    monkeypatch.setattr(gc, "enable", forbidden)

    def run(offset):
        barrier.wait(timeout=10)
        result = execute(f"#1={offset}\nG90 G1 X#1 F100\nM30", language="fanuc_mill")
        assert result.ok and result.complete, result.diagnostics
        assert gc.isenabled() == original
        return result.motions[-1].end_x

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, (10, 20))) == [10, 20]
    assert gc.isenabled() == original


def test_ast_label_maps_are_immutable_defensive_copies():
    labels = {10: 0}
    ast = ProgramAst((), labels, {})
    labels[10] = 99
    assert ast.nlabel_to_index[10] == 0
    with pytest.raises(TypeError):
        ast.nlabel_to_index[10] = 1
    with pytest.raises(TypeError):
        ast.olabel_to_index[9000] = 1


def test_program_rejects_ast_divergence_and_regenerates_derived_view():
    program = parse_program("O100\nN10 G0 X1\nM30")
    with pytest.raises(ValueError, match="does not match"):
        Program(program.blocks, ProgramAst((), {}, {}))
    assert Program(program.blocks).ast == program.ast
    with pytest.raises(FrozenInstanceError):
        program.ast.nodes[0].raw = "O999"
    assert _parse_program_python(program_block.raw for program_block in program.blocks) == program


def test_same_profile_id_different_math_is_recorded_in_reports():
    original = load_catalog()["4ax_table_b"]
    reversed_axis = replace(original, table_rotary_axes=(RotaryAxis("B", (0.0, -1.0, 0.0)),))
    source = "G90 G0 B90\nG0 Z10\nM30"
    first = execute(source, language="fanuc_mill", kinematics=original)
    second = execute(source, language="fanuc_mill", kinematics=reversed_axis)
    assert first.ok and second.ok
    assert first.kinematics_profile == second.kinematics_profile
    assert first.kinematics_fingerprint != second.kinematics_fingerprint
    assert first.motions[-1].end_x == pytest.approx(-second.motions[-1].end_x)
    for report in (_analysis_document(first), _result_document(first, include_motions=False)):
        assert report["kinematics_definition"]["table_rotary_axes"][0]["axis"] == [0, 1, 0]
        assert report["kinematics_fingerprint"] == first.kinematics_fingerprint


@pytest.mark.parametrize("command", ["batch", "batch-export"])
def test_batch_json_and_csv_record_effective_kinematics(tmp_path, command):
    source = tmp_path / "source"
    source.mkdir()
    (source / "part.nc").write_text("G90 G0 B90\nG0 Z10\nM30", encoding="utf-8")
    output = tmp_path / "reports"
    args = [command, str(source), "--lang", "fanuc_mill", "--kinematics", "4ax_table_b", "-o", str(output)]
    if command == "batch-export":
        args.extend(["--mode", "full"])
    assert main(args) == 0
    name = "batch_export_report" if command == "batch-export" else "batch_report"
    report = json.loads((output / f"{name}.json").read_text(encoding="utf-8"))["files"][0]
    with (output / f"{name}.csv").open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert len(report["kinematics_fingerprint"]) == 64
    assert row["kinematics_fingerprint"] == report["kinematics_fingerprint"]
    assert json.loads(row["kinematics_definition"]) == report["kinematics_definition"]
    assert report["kinematics_definition"]["table_rotary_axes"][0]["axis"] == [0, 1, 0]
