"""Command line interface contracts for trace, parse, analyze, and export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cli import main
from app.gcode import batch

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize("language, expected", [("fanuc_mill", True), ("fanuc_turn", False)])
def test_cli_batch_enables_arc_autodetection_for_milling(tmp_path, monkeypatch, language, expected):
    source = tmp_path / "arc.nc"
    source.write_text("G17 G90\nG0 X10 Y0\nG2 X20 Y10 I10 J10\nM30\n", encoding="utf-8")
    calls = []
    original = batch.execute_program

    def capture_execution(*args, **kwargs):
        calls.append(kwargs["autodetect_arc_type"])
        return original(*args, **kwargs)

    monkeypatch.setattr(batch, "execute_program", capture_execution)
    main(["batch", str(tmp_path), "--lang", language, "-o", str(tmp_path / "report")])
    assert calls == [expected]


def test_cli_help_describes_every_command(capsys):
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    for command in ("parse", "trace", "analyze", "export", "batch", "batch-export"):
        assert any(line.strip().startswith(f"{command} ") for line in output.splitlines())
        assert f"usage: python -m app {command} " in output
    for option in ("--lang", "--encoding", "--output", "--output-dir", "--mode", "--extensions", "--top-level-only"):
        assert option in output

    with pytest.raises(SystemExit) as exc:
        main(["batch", "--help"])
    assert exc.value.code == 0
    assert "--extensions" in capsys.readouterr().out

    with pytest.raises(SystemExit) as exc:
        main(["batch-export", "--help"])
    assert exc.value.code == 0
    assert "--arc-type" in capsys.readouterr().out


def test_cli_trace_uses_program_tool_geometry_for_milling_compensation(tmp_path):
    source = tmp_path / "compensated.nc"
    output = tmp_path / "trace.json"
    source.write_text(
        "G21 G17 G90\nT3 M6 (D=6 FLAT END MILL)\nG0 X0 Y0\nG1 G41 X10 Y0 F100\nG1 X10 Y10\nG40 G1 X20 Y10\nM30\n",
        encoding="utf-8",
    )

    assert main(["trace", str(source), "--lang", "fanuc_mill", "-o", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert not any(item["code"] == "UNVERIFIED_CUTTER_COMPENSATION" for item in result["diagnostics"])
    assert any(motion["compensation_applied"] for motion in result["motions"])

    report_dir = tmp_path / "report"
    assert main(["batch", str(tmp_path), "--lang", "fanuc_mill", "-o", str(report_dir)]) == 0
    report = json.loads((report_dir / "batch_report.json").read_text(encoding="utf-8"))
    assert report["files"][0]["status"] == "CLEAN"


def test_cli_trace_serializes_one_logical_arc(tmp_path):
    source = tmp_path / "arc.nc"
    output = tmp_path / "trace.json"
    source.write_text("G0 X0 Z0\nG2 X10 Z0 R5 F100\nM30\n", encoding="utf-8")

    assert main(["trace", str(source), "--output", str(output)]) == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["complete"] is True
    assert len(data["motions"]) == 1
    assert data["motions"][0]["move"] == 2
    assert data["motions"][0]["radius"] == 5.0


def test_cli_reads_cp1251_through_shared_nc_text_contract(tmp_path, capsys):
    source = tmp_path / "cp1251.nc"
    source.write_bytes("(ПРОГРАММА)\nG21 G18\nG0 X20 Z0\nM30\n".encode("cp1251"))

    assert main(["parse", str(source), "--encoding", "cp1251"]) == 0
    output = capsys.readouterr().out
    assert "Parse:" in output
    assert "Result: CLEAN" in output
    assert "Instructions:" in output


def test_cli_parse_returns_structured_error_code(tmp_path, capsys):
    source = tmp_path / "bad.nc"
    source.write_text("G1 X#999 Z0\n", encoding="utf-8")

    assert main(["parse", str(source)]) == 2
    output = capsys.readouterr().out
    assert "Result: ERRORS" in output
    assert "UNDEFINED_MACRO" in output


def test_cli_analyze_and_export_consume_same_execution_result(tmp_path):
    source = tmp_path / "line.nc"
    analysis = tmp_path / "analysis.json"
    exported = tmp_path / "expanded.nc"
    source.write_text("G0 X3 Z4\nG1 X6 Z8 F10\nM30\n", encoding="utf-8")

    assert main(["analyze", str(source), "-o", str(analysis)]) == 0
    assert main(["export", str(source), "--leading-zero", "-o", str(exported)]) == 0
    analysis_data = json.loads(analysis.read_text(encoding="utf-8"))
    assert analysis_data["complete"] is True
    assert analysis_data["motion_count"] == 2
    assert "G01 X6 Z8 F10" in exported.read_text(encoding="utf-8")


def test_cli_commands_print_terminal_results_without_json(tmp_path, capsys):
    source = tmp_path / "line.nc"
    source.write_text("G0 X3 Z4\nM30\n", encoding="utf-8")

    for command in ("parse", "trace", "analyze"):
        assert main([command, str(source)]) == 0
        output = capsys.readouterr().out
        assert f"{command.capitalize()}: {source}" in output
        assert "Result: CLEAN" in output
        assert not output.lstrip().startswith("{")

    destination = tmp_path / "expanded.nc"
    assert main(["export", str(source), "-o", str(destination)]) == 0
    output = capsys.readouterr().out
    assert f"Export: {source}" in output
    assert f"Output: {destination}" in output


def test_cli_cycle_export_includes_complete_final_id_g71_contour(tmp_path):
    exported = tmp_path / "cycle71-id-expanded.nc"

    assert (
        main(
            [
                "export",
                str(FIXTURES / "turning" / "cycle71_ID.nc"),
                "--mode",
                "cycles",
                "--leading-zero",
                "-o",
                str(exported),
            ]
        )
        == 0
    )

    lines = exported.read_text(encoding="utf-8").splitlines()
    # Preserve analytical arcs through the configured ID tool-nose correction,
    # rather than checking a long sampled polyline.
    assert any(line.startswith("G02 ") and " R1.9 " in line for line in lines)
    assert any(line.startswith("G02 ") and " R2.7 " in line for line in lines)
    assert lines[-4:] == ["G01 X75.3 Z-145.8 F0.25", "G01 X74.9 Z-145.6 F0.25", "G00 X74.9 Z1", "G00 X72 Z1"]


def test_cli_rejects_cycle_mode_for_milling(tmp_path):
    source = tmp_path / "mill.nc"
    output = tmp_path / "expanded.nc"
    source.write_text("G21 G17 G0 X0 Y0 Z0\nM30\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--mode",
                "cycles",
                "-o",
                str(output),
            ]
        )
    assert exc.value.code == 2


def test_cli_export_rejects_invalid_partial_execution(tmp_path, capsys):
    source = tmp_path / "invalid_arc.nc"
    output = tmp_path / "invalid_arc_export.nc"
    source.write_text("G21 G17 G90\nG1 X10 Y0 F100\nG2 X20 Y0 R1\nM30\n", encoding="utf-8")

    assert main(["export", str(source), "--lang", "fanuc_mill", "-o", str(output)]) == 2
    assert not output.exists()
    terminal = capsys.readouterr().out
    assert "Result: ERRORS" in terminal
    assert "INVALID_GEOMETRY" in terminal


def test_cli_batch_writes_production_json_and_csv_report(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    nested = corpus / "nested"
    nested.mkdir(parents=True)
    (corpus / "ok.nc").write_text("G21 G18\nG0 X20 Z0\nM30\n", encoding="utf-8")
    (corpus / "warning.nc").write_text("G21 G18\nM123\nM30\n", encoding="utf-8")
    (nested / "error.nc").write_text("G21 G18\nG123 X10 Z0\nM30\n", encoding="utf-8")
    (corpus / "ignored.md").write_text("G123 X10 Z0\n", encoding="utf-8")
    output_dir = tmp_path / "report"

    assert main(["batch", str(corpus), "-o", str(output_dir)]) == 2

    stdout = capsys.readouterr().out
    report = json.loads((output_dir / "batch_report.json").read_text(encoding="utf-8"))
    csv_text = (output_dir / "batch_report.csv").read_text(encoding="utf-8-sig")

    assert "Analyzing NC programs in" in stdout
    assert "Result: ERRORS" in stdout
    assert "[CLEAN] ok.nc" in stdout
    assert "[ERRORS] nested/error.nc" in stdout
    assert "[WARNINGS] warning.nc" in stdout
    assert "G123" in stdout
    assert str(output_dir / "batch_report.json") in stdout
    assert report["status"] == "ERRORS"
    assert report["summary"]["files_total"] == 3
    assert report["summary"]["CLEAN"] == 1
    assert report["summary"]["WARNINGS"] == 1
    assert report["summary"]["ERRORS"] == 1
    assert report["summary"]["unsupported_g_codes"] == [{"code": "G123", "occurrences": 1, "files": 1}]
    assert report["summary"]["unsupported_m_codes"] == [{"code": "M123", "occurrences": 1, "files": 1}]
    assert [item["path"] for item in report["files"]] == ["nested/error.nc", "ok.nc", "warning.nc"]
    assert "nested/error.nc,ERRORS" in csv_text
    assert "ok.nc,CLEAN" in csv_text
    assert "warning.nc,WARNINGS" in csv_text


def test_cli_batch_top_level_only_and_custom_extensions(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    nested = corpus / "nested"
    nested.mkdir(parents=True)
    (corpus / "main.mpf").write_text("G21 G17 G90\nG0 X0 Y0 Z0\nM30\n", encoding="utf-8")
    (nested / "nested.mpf").write_text("G21 G17 G90\nG0 X1 Y1 Z1\nM30\n", encoding="utf-8")
    output_dir = tmp_path / "report"

    assert (
        main(
            [
                "batch",
                str(corpus),
                "--lang",
                "fanuc_mill",
                "--extensions",
                ".mpf",
                "--top-level-only",
                "-o",
                str(output_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()
    report = json.loads((output_dir / "batch_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "CLEAN"
    assert report["summary"]["files_total"] == 1
    assert report["files"][0]["path"] == "main.mpf"


def test_cli_batch_reports_decode_failure_without_aborting_other_files(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "ok.nc").write_text("G21 G18\nG0 X20 Z0\nM30\n", encoding="utf-8")
    (corpus / "bad.nc").write_bytes(b"\xff\xfe\xfd")
    output_dir = tmp_path / "report"

    assert main(["batch", str(corpus), "-o", str(output_dir)]) == 2
    capsys.readouterr()
    report = json.loads((output_dir / "batch_report.json").read_text(encoding="utf-8"))

    assert report["summary"]["files_total"] == 2
    assert report["summary"]["CLEAN"] == 1
    assert report["summary"]["ERRORS"] == 1
    failed = next(item for item in report["files"] if item["path"] == "bad.nc")
    assert failed["diagnostics"][0]["code"] == "FILE_PROCESSING_ERROR"


def test_cli_batch_does_not_disguise_analyzer_failure_as_file_error(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "program.nc").write_text("M30\n", encoding="utf-8")

    def fail_execute(*_args, **_kwargs):
        raise RuntimeError("analyzer failed")

    monkeypatch.setattr("app.gcode.program_execution.execute", fail_execute)
    with pytest.raises(RuntimeError, match="analyzer failed"):
        main(["batch", str(corpus), "-o", str(tmp_path / "report")])


def test_cli_batch_empty_directory_is_no_files(tmp_path, capsys):
    corpus = tmp_path / "empty"
    corpus.mkdir()
    output_dir = tmp_path / "report"

    assert main(["batch", str(corpus), "-o", str(output_dir)]) == 2
    capsys.readouterr()
    report = json.loads((output_dir / "batch_report.json").read_text(encoding="utf-8"))

    assert report["status"] == "NO_FILES"
    assert report["summary"]["files_total"] == 0
    assert report["scan_warnings"] == ["No matching NC files found"]


@pytest.mark.parametrize(
    ("profile", "rotary_word"),
    [("5ax_table_ac_angled", "A30 C45"), ("5ax_table_bc_angled", "B30 C45")],
)
def test_cli_g43_4_full_program_is_verbatim_and_expanded_export_is_rejected(tmp_path, capsys, profile, rotary_word):
    source = tmp_path / "tcp.nc"
    full_output = tmp_path / "tcp_full.nc"
    expanded_output = tmp_path / "tcp_expanded.nc"
    source_text = f"G90 G0 X0 Y0 Z0\nG43.4 H1\nG1 X10 Y20 Z30 {rotary_word} F100\nG49\nM30\n"
    source.write_text(source_text, encoding="utf-8")

    assert (
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--kinematics",
                profile,
                "--mode",
                "full",
                "-o",
                str(full_output),
            ]
        )
        == 0
    )
    assert full_output.read_text(encoding="utf-8") == source_text
    capsys.readouterr()

    assert (
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--kinematics",
                profile,
                "--mode",
                "expanded",
                "-o",
                str(expanded_output),
            ]
        )
        == 2
    )
    assert not expanded_output.exists()
    output = capsys.readouterr().out
    assert "UNSUPPORTED_TCP_EXPANDED_EXPORT" in output


def test_cli_exports_sinumerik_iso_m_from_mpf_as_fanuc_full_program(tmp_path, capsys):
    source = tmp_path / "part.mpf"
    full_output = tmp_path / "part_full.nc"
    expanded_output = tmp_path / "part_expanded.nc"
    source_text = "%_N_PART_MPF\nG291\nG21 G90\nG0 X0 Y0\nG1 X10 F100\nM30\n"
    source.write_text(source_text, encoding="utf-8")

    assert main(["export", str(source), "--lang", "fanuc_mill", "--mode", "full", "-o", str(full_output)]) == 0
    assert full_output.read_text(encoding="utf-8") == source_text.replace("G291\n", "")
    capsys.readouterr()

    assert main(["export", str(source), "--lang", "fanuc_mill", "--mode", "expanded", "-o", str(expanded_output)]) == 0
    expanded = expanded_output.read_text(encoding="utf-8")
    assert "X10" in expanded
    assert "G291" not in expanded


def test_sinumerik_dialect_conversion_rejects_expanded_mode(tmp_path):
    source = tmp_path / "source.nc"
    source.write_text("G21 G17 G90\nG0 X0 Y0\nM30\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--target-dialect",
                "sinumerik840d",
                "--mode",
                "expanded",
                "-o",
                str(tmp_path / "out.mpf"),
            ]
        )
    assert exc.value.code == 2


def test_cli_full_program_adds_and_removes_sinumerik_mode_without_expanding(tmp_path, capsys):
    fanuc_source = tmp_path / "source.nc"
    sinumerik_output = tmp_path / "converted.mpf"
    fanuc_output = tmp_path / "roundtrip.nc"
    original = "O1234\nG21 G17 G90\nT1 M6\nG0 X0 Y0 Z5\nG1 X10 Y0 Z-1 F100\nM30\n"
    fanuc_source.write_text(original, encoding="utf-8")

    assert (
        main(
            [
                "export",
                str(fanuc_source),
                "--lang",
                "fanuc_mill",
                "--target-dialect",
                "sinumerik840d",
                "--mode",
                "full",
                "-o",
                str(sinumerik_output),
            ]
        )
        == 0
    )
    converted = sinumerik_output.read_text(encoding="utf-8")
    assert converted == "G291\n(O1234)\n" + original.split("\n", 1)[1]
    assert "ANALYSIS ONLY" not in converted
    capsys.readouterr()

    assert (
        main(
            [
                "export",
                str(sinumerik_output),
                "--lang",
                "fanuc_mill",
                "--mode",
                "full",
                "-o",
                str(fanuc_output),
            ]
        )
        == 0
    )
    assert fanuc_output.read_text(encoding="utf-8") == original.replace("O1234", "(O1234)", 1)
    capsys.readouterr()


@pytest.mark.parametrize(
    "source, diagnostic",
    [
        ("G291\nG21 G17 G90\nG0 X0 Y0\nM98 P1000\nM30\n", "M98"),
    ],
)
def test_sinumerik_target_fails_closed_for_semantics_it_cannot_preserve(tmp_path, capsys, source, diagnostic):
    input_path = tmp_path / "source.nc"
    output_path = tmp_path / "result.mpf"
    input_path.write_text(source, encoding="utf-8")

    assert (
        main(
            [
                "export",
                str(input_path),
                "--lang",
                "fanuc_mill",
                "--target-dialect",
                "sinumerik840d",
                "--mode",
                "full",
                "-o",
                str(output_path),
            ]
        )
        == 2
    )
    assert not output_path.exists()
    captured = capsys.readouterr()
    assert diagnostic.lower() in captured.err.lower() or diagnostic.lower() in captured.out.lower()


@pytest.mark.parametrize(
    "cycle",
    [
        "G82 X10 Y20 Z-2 R1 P100 F100",
        "G86 X10 Y20 Z-2 R1 F100",
    ],
)
def test_sinumerik_full_program_conversion_preserves_cycle_signals(tmp_path, capsys, cycle):
    source = tmp_path / "cycle.nc"
    output = tmp_path / "cycle.mpf"
    source_text = f"G21 G17 G90\nG0 X0 Y0 Z5\n{cycle}\nG80\nM30\n"
    source.write_text(source_text, encoding="utf-8")

    assert (
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--target-dialect",
                "sinumerik840d",
                "--mode",
                "full",
                "-o",
                str(output),
            ]
        )
        == 0
    )
    assert output.read_text(encoding="utf-8") == "G291\n" + source_text
    capsys.readouterr()


def test_sinumerik_target_rejects_unverified_cutter_compensation(tmp_path, capsys):
    source = tmp_path / "compensation.nc"
    output = tmp_path / "compensation.mpf"
    source.write_text("G21 G17 G90\nG0 X0 Y0 Z5\nG41 D1\nG1 X10 F100\nG40\nM30\n", encoding="utf-8")

    assert (
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--target-dialect",
                "sinumerik840d",
                "--mode",
                "full",
                "-o",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()
    assert "UNVERIFIED_TARGET_CUTTER_COMPENSATION" in capsys.readouterr().out


def test_sinumerik_target_rejects_turning_export(tmp_path):
    source = tmp_path / "part.nc"
    source.write_text("G21 G90\nM30\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_turn",
                "--target-dialect",
                "sinumerik840d",
                "--mode",
                "full",
                "-o",
                str(tmp_path / "out.mpf"),
            ]
        )
    assert exc.value.code == 2
