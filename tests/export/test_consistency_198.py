"""Shared GUI/API/CLI execution and export regressions."""

import json
from dataclasses import replace

import ezdxf
import pytest

from app.cli import main
from app.gcode.export.expanded import export_result
from app.gcode.export_file import ExportRequest, export_file, write_export
from app.gcode.kernel import execute
from app.gcode.kernel.api.resources import ExecutionLimits
from app.settings import GENERATED_MOTIONS_DEFAULT


def test_kernel_and_gui_share_default_motion_budget():
    assert ExecutionLimits().generated_motions == GENERATED_MOTIONS_DEFAULT
    source = "G21 G17 G90\nG0 Z5\nG99 G83 X1 Y0 Z-70000 R1 Q1 F100\nG80\nM30"
    result = execute(source, "fanuc_mill")
    assert result.ok and result.complete, result.diagnostics
    assert len(result.motions) > 200000
    limited = execute(source, "fanuc_mill", limits=ExecutionLimits(generated_motions=20))
    assert not limited.ok
    assert any(d.code == "RESOURCE_LIMIT" for d in limited.diagnostics)


@pytest.mark.parametrize("mode", ["full", "expanded"])
def test_cli_formatting_matches_shared_export_request(tmp_path, mode):
    source = tmp_path / "part.nc"
    source.write_text("G21 G90 G17\nG1 X1.23456 Y2 F100\nM30", encoding="utf-8")
    actual, expected = tmp_path / "actual.nc", tmp_path / "expected.nc"
    flags = [
        "--start-program",
        "O1234",
        "--end-program",
        "M2",
        "--comment-style",
        "semicolon",
        "--decimal-places",
        "3",
        "--force-decimal",
        "--plus-output",
    ]
    assert main(["export", str(source), "--lang", "fanuc_mill", "--mode", mode, *flags, "-o", str(actual)]) == 0
    request = ExportRequest(
        language="fanuc_mill",
        mode=mode,
        start_program="O1234",
        end_program="M2",
        comment_style="semicolon",
        decimal_places=3,
        decimal_places_explicit=True,
        force_decimal=True,
        force_decimal_explicit=True,
        plus_output=True,
        plus_output_explicit=True,
    )
    export_file(source, expected, request)
    assert actual.read_bytes() == expected.read_bytes()
    if mode == "expanded":
        assert "X+1.235" in actual.read_text()
    else:
        assert "X1.23456" in actual.read_text()


@pytest.mark.parametrize(
    "flag,value",
    [
        ("--start-program", "O1"),
        ("--end-program", "M2"),
        ("--comment-style", "semicolon"),
        ("--decimal-places", "3"),
        ("--force-decimal", None),
        ("--plus-output", None),
    ],
)
def test_cli_rejects_nc_formatting_for_dxf(tmp_path, flag, value):
    source = tmp_path / "part.nc"
    source.write_text("G1 X1 F100\nM30")
    with pytest.raises(SystemExit) as error:
        main(
            [
                "export",
                str(source),
                "--format",
                "dxf",
                flag,
                *([] if value is None else [value]),
                "-o",
                str(tmp_path / "out.dxf"),
            ]
        )
    assert error.value.code == 2


@pytest.mark.parametrize("mode_line", ["G290", "G291"])
def test_direct_and_file_auto_posts_match_sinumerik_source(tmp_path, mode_line):
    source = tmp_path / "part.mpf"
    text = f"{mode_line}\nG90 G17\nG1 X10 Y5 F100\nM30"
    source.write_text(text, encoding="utf-8")
    result = execute(text, "fanuc_mill", source_dialect="sinumerik")
    output = tmp_path / "out.mpf"
    export_file(source, output, ExportRequest(language="fanuc_mill"))
    assert export_result(result) == output.read_text(encoding="utf-8")
    assert output.read_text().splitlines()[0] == mode_line


def test_shared_dxf_writes_partial_geometry_but_nc_remains_blocked(tmp_path):
    source = "G1 X2 Y3 Z4 F100\nM30"
    result = replace(execute(source, "fanuc_mill"), ok=False, complete=False)
    dxf, nc = tmp_path / "partial.dxf", tmp_path / "partial.nc"
    exported = write_export(result, source, dxf, ExportRequest(language="fanuc_mill", format="dxf"))
    assert exported.output_size_bytes > 0
    entity = list(ezdxf.readfile(dxf).modelspace())[0]
    assert tuple(entity.dxf.end) == pytest.approx((2, 3, 4))
    write_export(result, source, nc, ExportRequest(language="fanuc_mill"))
    assert not nc.exists()


def test_batch_export_detects_each_source_machine_without_lang(tmp_path):
    inputs, outputs = tmp_path / "inputs", tmp_path / "outputs"
    inputs.mkdir()
    (inputs / "mill.mpf").write_text("G290\nG90 G17\nG1 X10 Y5 F100\nM30")
    (inputs / "lathe.nc").write_text("G21 G18\nG1 X20 Z-5 F100\nM30")
    assert main(["batch-export", str(inputs), "-o", str(outputs)]) == 0
    report = json.loads((outputs / "batch_export_report.json").read_text())
    assert all(item["ok"] for item in report["files"])
    assert (outputs / "mill.mpf").read_text().startswith("G290\n")
    assert (outputs / "lathe.nc").exists()


def test_batch_partial_dxf_keeps_output_path_and_execution_error(tmp_path):
    inputs, outputs = tmp_path / "inputs", tmp_path / "outputs"
    inputs.mkdir()
    (inputs / "part.nc").write_text("G17 G90\nG1 X2 Y3 F100\nG2 X100 Y100 R1\nM30")
    assert main(["batch-export", str(inputs), "--lang", "fanuc_mill", "--format", "dxf", "-o", str(outputs)]) == 2
    report = json.loads((outputs / "batch_export_report.json").read_text())
    item = report["files"][0]
    assert item["status"] == "ERRORS" and not item["ok"]
    assert item["output_relative_path"] == "part.dxf"
    assert item["output_size_bytes"] > 0
    assert (outputs / "part.dxf").exists()


def test_batch_auto_accepts_milling_kinematics_without_explicit_lang(tmp_path):
    inputs, outputs = tmp_path / "inputs", tmp_path / "outputs"
    inputs.mkdir()
    (inputs / "part.mpf").write_text("G290\nG90 G17\nG1 X10 Y5 F100\nM30")
    assert main(["batch-export", str(inputs), "--kinematics", "5ax_table_ac", "-o", str(outputs)]) == 0


@pytest.mark.parametrize("value", ["-1", "13"])
def test_cli_rejects_invalid_decimal_precision(tmp_path, value):
    with pytest.raises(SystemExit) as error:
        main(["export", str(tmp_path / "input.nc"), "--decimal-places", value, "-o", str(tmp_path / "out.nc")])
    assert error.value.code == 2


@pytest.mark.parametrize(
    "language,source",
    [
        ("fanuc_mill", "G17 G90\nG0 X10 Y0\nG3 X0 Y10 I0 J0 F100\nM30"),
        ("fanuc_turn", "G18 G90\nG0 X20 Z0\nG2 X0 Z10 I0 K0 F100\nM30"),
    ],
)
def test_cli_commands_use_same_arc_detection(tmp_path, language, source):
    path = tmp_path / "part.nc"
    path.write_text(source)
    for command in ("parse", "trace", "analyze"):
        assert main([command, str(path), "--lang", language]) == 0
    assert main(["export", str(path), "--lang", language, "-o", str(tmp_path / "out.nc")]) == 0
