"""Exercise every real turning fixture through the CLI batch and both post systems."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cli import main
from app.gcode.kernel import execute
from app.gcode.program_execution import execute_program

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "turning"


def _assert_same_execution(expected, actual):
    assert actual.ok and actual.complete, actual.diagnostics
    assert not actual.diagnostics
    assert len(actual.motions) == len(expected.motions)
    for before, after in zip(expected.motions, actual.motions, strict=True):
        assert (after.move, after.threading, after.feed_mode) == (before.move, before.threading, before.feed_mode)
        assert (after.start_x, after.start_z, after.end_x, after.end_z) == pytest.approx(
            (before.start_x, before.start_z, before.end_x, before.end_z),
            abs=1e-5,
        )
        assert after.feed == pytest.approx(before.feed, abs=1e-5)
        assert after.spindle_rpm == pytest.approx(before.spindle_rpm, abs=1e-5)
        assert after.surface_speed_m_min == pytest.approx(before.surface_speed_m_min, abs=1e-5)
        assert after.spindle_limit_rpm == before.spindle_limit_rpm
        if before.arc is not None:
            assert after.arc is not None
            assert after.arc.radius == pytest.approx(before.arc.radius, abs=1e-5)
            assert after.arc.sweep == pytest.approx(before.arc.sweep, abs=1e-5)


def test_all_turning_fixtures_batch_a_to_b_and_back(tmp_path):
    output_b, output_a = tmp_path / "type_b", tmp_path / "type_a"
    # This source currently fails with the automatically inferred nose geometry
    # even before posting. Require its diagnostic; do not hide it as a skip.
    assert (
        main(
            [
                "batch-export",
                str(FIXTURES),
                "--lang",
                "fanuc_turn",
                "--lathe-gcode-system",
                "A",
                "--target-dialect",
                "fanuc_lathe_b",
                "-o",
                str(output_b),
            ]
        )
        == 2
    )
    report = json.loads((output_b / "batch_export_report.json").read_text(encoding="utf-8"))
    errors = {item["input_relative_path"]: item for item in report["files"] if item["status"] == "ERRORS"}
    assert set(errors) == {"lathe_cnc_macro_test.nc"}
    diagnostic = errors["lathe_cnc_macro_test.nc"]["diagnostics"][0]
    assert diagnostic["code"] == "EXECUTION_ERROR" and "compensated segments" in diagnostic["message"]
    assert report["summary"]["exported"] == 14
    assert (
        main(
            [
                "batch-export",
                str(output_b),
                "--extensions",
                ".nc",
                "--lang",
                "fanuc_turn",
                "--lathe-gcode-system",
                "B",
                "--target-dialect",
                "fanuc_lathe_a",
                "-o",
                str(output_a),
            ]
        )
        == 0
    )
    report_a = json.loads((output_a / "batch_export_report.json").read_text(encoding="utf-8"))
    a_output_by_input = {entry["input_relative_path"]: entry["output_relative_path"] for entry in report_a["files"]}
    for item in report["files"]:
        if item["status"] == "ERRORS":
            continue
        name = item["input_relative_path"]
        b_rel = item["output_relative_path"]
        assert b_rel in a_output_by_input, f"Missing second-pass export for {b_rel}"
        a_rel = a_output_by_input[b_rel]
        source, _, _ = execute_program(
            (FIXTURES / name).read_text(encoding="utf-8-sig"),
            language="fanuc_turn",
            lathe_gcode_system="A",
            autodetect_arc_type=True,
        )
        b = execute((output_b / b_rel).read_text(encoding="utf-8"), language="fanuc_turn", lathe_gcode_system="B")
        a = execute((output_a / a_rel).read_text(encoding="utf-8"), language="fanuc_turn", lathe_gcode_system="A")
        _assert_same_execution(source, b)
        _assert_same_execution(source, a)


def test_type_a_source_cannot_be_posted_after_selecting_source_type_b(tmp_path):
    output = tmp_path / "invalid.nc"
    assert (
        main(
            [
                "export",
                str(FIXTURES / "lathe_cycles_example.nc"),
                "--lang",
                "fanuc_turn",
                "--lathe-gcode-system",
                "B",
                "--target-dialect",
                "fanuc_lathe_b",
                "-o",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()
    result = execute((FIXTURES / "lathe_cycles_example.nc").read_text(encoding="utf-8"), lathe_gcode_system="B")
    assert not result.ok
    assert any(d.severity == "error" and "selected source is Type B" in d.message for d in result.diagnostics)
