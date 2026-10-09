"""Command line interface contracts for trace, parse, analyze, and export."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.cli import main
from app.gcode import batch
from app.gcode.kernel import execute

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize("matches", [True, False])
def test_cli_compares_generated_native_cycle_nc_with_reference(tmp_path, capsys, matches):
    source = tmp_path / "source.nc"
    output = tmp_path / "actual.mpf"
    reference = tmp_path / "expected.mpf"
    source.write_text("G21 G17 G90\nG0 X0 Y0 Z5\nG98 G81 X2 Y3 Z-5 R2 F100\nG80\nM30\n", encoding="utf-8")
    expected = (
        "G290\nG17 G90 G94 G40 D0 G54\nG710\nG90\nG0 X0 Z5\nG90\nG17\nG94\nG0 X2 Y3\nF100\n"
        "MCALL CYCLE81(5,2,0,-5,,0,0,1,12)\nX2 Y3\nMCALL\nG90\nM30\n"
    )
    baseline = expected if matches else expected.replace("F100", "F200")
    reference.write_bytes(baseline.replace("\n", "\r\n").encode("utf-8"))
    arguments = [
        "export",
        str(source),
        "--lang",
        "fanuc_mill",
        "--post-profile",
        "sinumerik_840d",
        "-o",
        str(output),
        "--compare-with",
        str(reference),
    ]
    assert main(arguments) == (0 if matches else 1)
    terminal = capsys.readouterr()
    assert terminal.err == ""
    assert output.read_text(encoding="utf-8") == expected
    if matches:
        assert "Comparison: MATCH" in terminal.out
        assert "@@" not in terminal.out
    else:
        assert "Comparison: DIFFERENT" in terminal.out
        diff = terminal.out[terminal.out.index("--- ") :]
        assert diff.startswith(f"--- {reference.as_posix()}\n+++ {output.as_posix()}\n@@")
        assert "-F200\n+F100\n" in diff
        assert main(arguments) == 1
        repeated = capsys.readouterr().out
        assert repeated[repeated.index("--- ") :] == diff
    assert reference.read_bytes() == baseline.replace("\n", "\r\n").encode("utf-8")


def test_cli_comparison_detects_missing_final_newline(tmp_path, capsys):
    source = tmp_path / "source.nc"
    output = tmp_path / "actual.nc"
    reference = tmp_path / "expected.nc"
    source.write_text("M30\n", encoding="utf-8")
    reference.write_bytes(b"M30")
    assert (
        main(
            [
                "export",
                str(source),
                "--mode",
                "full",
                "-o",
                str(output),
                "--compare-with",
                str(reference),
            ]
        )
        == 1
    )
    assert "-M30\n\\ No newline at end of file\n+M30\n" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["same_file", "missing", "dxf"])
def test_cli_comparison_preflight_returns_error_without_writing(tmp_path, capsys, failure):
    source = tmp_path / "source.nc"
    output = tmp_path / "actual.nc"
    reference = output if failure == "same_file" else tmp_path / "expected.nc"
    source.write_text("M30\n", encoding="utf-8")
    if failure != "missing":
        reference.write_bytes(b"reference\n")
    arguments = ["export", str(source), "-o", str(output), "--compare-with", str(reference)]
    if failure == "dxf":
        arguments += ["--format", "dxf"]
    assert main(arguments) == 2
    assert "Export error:" in capsys.readouterr().err
    if failure == "same_file":
        assert output.read_bytes() == b"reference\n"
    else:
        assert not output.exists()


@pytest.mark.parametrize("language", ["fanuc_mill", "fanuc_turn"])
def test_cli_batch_enables_shared_arc_autodetection(tmp_path, monkeypatch, language):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "arc.nc"
    source.write_text("G17 G90\nG0 X10 Y0\nG2 X20 Y10 I10 J10\nM30\n", encoding="utf-8")
    calls = []
    original = batch.execute_program

    def capture_execution(*args, **kwargs):
        calls.append(kwargs.get("autodetect_arc_type", True))
        return original(*args, **kwargs)

    monkeypatch.setattr(batch, "execute_program", capture_execution)
    main(["batch", str(source_dir), "--lang", language, "-o", str(tmp_path / "report")])
    assert calls == [True]


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

    batch_source = tmp_path / "batch-source"
    batch_source.mkdir()
    (batch_source / source.name).write_bytes(source.read_bytes())
    report_dir = tmp_path / "report"
    assert main(["batch", str(batch_source), "--lang", "fanuc_mill", "-o", str(report_dir)]) == 0
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
                "full",
                "--leading-zero",
                "-o",
                str(exported),
            ]
        )
        == 0
    )

    lines = exported.read_text(encoding="utf-8").splitlines()
    assert not any(re.search(r"\bG7[0-6]\b", line) for line in lines)
    assert any("G2" in line or "G02" in line for line in lines)
    replay = execute(exported.read_text(encoding="utf-8"), language="fanuc_turn")
    assert replay.ok and replay.complete


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


@pytest.mark.parametrize(("kind", "extension"), [("report", ".json"), ("html", ".html")])
def test_cli_batch_rejects_generated_output_that_reenters_scan(tmp_path, kind, extension):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "part.nc").write_text("M30\n", encoding="utf-8")
    arguments = ["batch", str(corpus), "--extensions", extension]
    if kind == "report":
        arguments += ["-o", str(corpus / "report")]
    else:
        arguments += ["--html", str(corpus / "html"), "-o", str(tmp_path / "report")]

    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2
    assert not (corpus / kind).exists()


def test_cli_batch_reports_use_atomic_writes(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "part.nc").write_text("M30\n", encoding="utf-8")
    output = tmp_path / "report"
    calls = []
    original = batch.atomic_write_text

    def capture(path, text, *, encoding="utf-8"):
        calls.append(Path(path).name)
        return original(path, text, encoding=encoding)

    monkeypatch.setattr(batch, "atomic_write_text", capture)
    assert main(["batch", str(corpus), "-o", str(output)]) == 0
    assert calls == ["batch_report.json", "batch_report.csv"]


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
    assert full_output.read_text(encoding="utf-8") == source_text
    capsys.readouterr()

    assert main(["export", str(source), "--lang", "fanuc_mill", "--mode", "expanded", "-o", str(expanded_output)]) == 0
    expanded = expanded_output.read_text(encoding="utf-8")
    assert "X10" in expanded
    assert "G291" in expanded


def test_cli_expanded_can_select_sinumerik_post(tmp_path):
    source = tmp_path / "source.nc"
    source.write_text("G21 G17 G90\nG0 X0 Y0\nM30\n")
    output = tmp_path / "out.mpf"
    assert (
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--target-dialect",
                "sinumerik_iso",
                "--mode",
                "expanded",
                "-o",
                str(output),
            ]
        )
        == 0
    )
    assert output.read_text().startswith("G291\n")


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
                "sinumerik_iso",
                "--mode",
                "full",
                "-o",
                str(tmp_path / "out.mpf"),
            ]
        )
    assert exc.value.code == 2
