"""EXPANDED multi-axis capability limits are UNSUPPORTED, not ERROR."""

from __future__ import annotations

import json

import pytest

from app.cli import main
from app.gcode.batch_export import export_directory
from app.gcode.export.common import ExportLimitation, ExportOptions, is_export_limitation
from app.gcode.export.expanded import convert_resolved_program, load_post_profile
from app.gcode.export_file import ExportRequest, export_file
from app.gcode.kernel import execute


def test_multiaxis_export_file_reports_limitation_not_error(tmp_path):
    source = tmp_path / "part.nc"
    source.write_text("G21 G90\nG0 B90\nG0 Z10\nM30\n", encoding="utf-8")
    output = tmp_path / "out.nc"

    result = export_file(
        source,
        output,
        ExportRequest(language="fanuc_mill", kinematics="4ax_table_b", target_dialect="fanuc_mill"),
    )

    assert not result.execution.ok
    assert not output.exists()
    limitations = [item for item in result.execution.diagnostics if is_export_limitation(item)]
    assert limitations and limitations[0].code.endswith("_EXPANDED_EXPORT")
    assert limitations[0].severity == "error"


def test_batch_export_multiaxis_status_is_unsupported(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "part.nc").write_text("G21 G90\nG0 B90\nG0 Z10\nM30\n", encoding="utf-8")

    report = export_directory(
        root,
        tmp_path / "out",
        ExportRequest(language="fanuc_mill", kinematics="4ax_table_b", target_dialect="fanuc_mill"),
    )

    assert report["status"] == "UNSUPPORTED"
    assert report["summary"]["unsupported"] == 1
    assert report["summary"]["errors"] == 0
    assert report["files"][0]["status"] == "UNSUPPORTED"
    assert not (tmp_path / "out" / "part.nc").exists()


def test_cli_multiaxis_export_is_nonzero_and_unsupported(tmp_path, capsys):
    source = tmp_path / "tcp.nc"
    source.write_text("G90 G0 X0 Y0 Z0\nG43.4 H1\nG1 X10 Y20 Z30 B30 C45 F100\nG49\nM30\n", encoding="utf-8")
    output = tmp_path / "out.nc"

    assert (
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--kinematics",
                "5ax_table_bc_angled",
                "-o",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()
    terminal = capsys.readouterr().out
    assert "UNSUPPORTED_TCP_EXPANDED_EXPORT" in terminal
    assert "Result: UNSUPPORTED" in terminal


def test_real_failure_still_reports_errors(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "bad.nc").write_text("G21 G17 G90\nG2 X10 Y0 R1\nM30\n", encoding="utf-8")

    report = export_directory(root, tmp_path / "out", ExportRequest(language="fanuc_mill", target_dialect="fanuc_mill"))

    assert report["status"] == "ERRORS"
    assert report["files"][0]["diagnostics"][0]["code"] == "INVALID_GEOMETRY"


def test_declared_supports_gate_fails_closed(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["supports"] = {
        "axes": ["X", "Y", "Z"],
        "inverseTime": True,
        "multiTurnArcs": True,
        "absoluteArcCenters": False,
    }
    post = tmp_path / "post.json"
    post.write_text(json.dumps(profile), encoding="utf-8")
    result = execute("G21 G17 G90\nG0 X10 Y0\nG3 X0 Y10 I-10 J0 F100\nM30", language="fanuc_mill")

    with pytest.raises(ExportLimitation) as excinfo:
        convert_resolved_program(result, str(post), ExportOptions(delimiter=True, arc_mode=1))
    assert excinfo.value.code.endswith("_EXPANDED_EXPORT")
