"""Command line interface contracts for trace, parse, analyze, and export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cli import main

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


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
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True


def test_cli_parse_returns_structured_error_code(tmp_path, capsys):
    source = tmp_path / "bad.nc"
    source.write_text("G1 X#999 Z0\n", encoding="utf-8")

    assert main(["parse", str(source)]) == 2
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert data["complete"] is False
    assert data["diagnostics"][0]["code"] == "UNDEFINED_MACRO"


def test_cli_analyze_and_export_consume_same_execution_result(tmp_path):
    source = tmp_path / "line.nc"
    analysis = tmp_path / "analysis.json"
    exported = tmp_path / "expanded.nc"
    source.write_text("G0 X3 Z4\nG1 X6 Z8 F10\nM30\n", encoding="utf-8")

    assert main(["analyze", str(source), "-o", str(analysis)]) == 0
    assert main(["export", str(source), "-o", str(exported)]) == 0
    analysis_data = json.loads(analysis.read_text(encoding="utf-8"))
    assert analysis_data["complete"] is True
    assert analysis_data["motion_count"] == 2
    assert "G01 X6 Z8 F10" in exported.read_text(encoding="utf-8")


def test_cli_cycle_export_includes_complete_final_id_g71_contour(tmp_path):
    exported = tmp_path / "cycle71-id-expanded.nc"

    assert (
        main(
            [
                "export",
                str(FIXTURES / "turning" / "cycle71_ID.nc"),
                "--mode",
                "cycles",
                "-o",
                str(exported),
            ]
        )
        == 0
    )

    lines = exported.read_text(encoding="utf-8").splitlines()
    contour_start = lines.index("G00 X89.6 Z1")
    contour = lines[contour_start:-2]
    assert contour[0] == "G00 X89.6 Z1"
    assert contour[1] == "G01 X89.568007 Z0.075386 F0.25"
    assert "G01 X84.219901 Z-30.027723 F0.25" in contour
    assert "G01 X76.447921 Z-29.933473 F0.25" in contour
    assert contour[-1] == "G01 X75.3 Z-145 F0.25"
    assert len(contour) > 100
    assert "G00 X89.8 Z1" not in lines
    assert lines[-2:] == ["G00 X72 Z-145", "G00 X72 Z1"]


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
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert any(item["code"] == "INVALID_GEOMETRY" for item in data["diagnostics"])
