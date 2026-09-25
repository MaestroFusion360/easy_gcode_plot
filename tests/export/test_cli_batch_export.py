"""Shared single/batch CLI export behavior and source safety."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import ezdxf
import pytest

from app.cli import main
from app.gcode.program_execution import execute_program


@pytest.mark.parametrize(
    "language,mode,extra",
    [
        ("fanuc_turn", "full", []),
        ("fanuc_turn", "expanded", []),
        ("fanuc_turn", "expanded", ["--no-comments", "--no-spaces"]),
        ("fanuc_turn", "expanded", ["--sequence-numbers", "--sequence-start", "10", "--sequence-increment", "10"]),
        ("fanuc_mill", "full", []),
        ("fanuc_mill", "expanded", []),
        ("fanuc_mill", "expanded", ["--arc-type", "ijk-relative"]),
        ("fanuc_mill", "expanded", ["--arc-type", "ijk-absolute"]),
        ("fanuc_mill", "expanded", ["--arc-type", "radius"]),
        ("fanuc_mill", "expanded", ["--arc-type", "linearized"]),
        ("fanuc_mill", "expanded", ["--units", "mm"]),
        ("fanuc_mill", "expanded", ["--units", "inch"]),
    ],
)
def test_single_and_batch_export_are_byte_identical(tmp_path, language, mode, extra):
    root = tmp_path / "source"
    root.mkdir()
    source = root / "part.nc"
    if language == "fanuc_mill":
        source.write_text("O1234\nG21 G17 G90\nG0 X0 Y0\nG2 X10 Y10 I10 J0 F100\nM30\n", encoding="utf-8")
    else:
        source.write_text("O1234\nG21 G18 G90\nG0 X0 Z0\nG1 X20 Z10 F100\nM30\n", encoding="utf-8")
    original = source.read_bytes()
    single = tmp_path / "single.nc"
    batch_root = tmp_path / "batch"
    common = ["--lang", language, "--mode", mode, *extra]
    assert main(["export", str(source), *common, "-o", str(single)]) == 0
    assert main(["batch-export", str(root), *common, "-o", str(batch_root)]) == 0
    assert single.read_bytes() == (batch_root / "part.nc").read_bytes()
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "units,source_code,target_code,source_position",
    [
        ("inch", "G21", "G20", 25.4),
        ("mm", "G20", "G21", 1.0),
    ],
)
def test_unit_conversion_preserves_physical_geometry(tmp_path, units, source_code, target_code, source_position):
    source = tmp_path / "source.nc"
    output = tmp_path / "output.nc"
    source.write_text(f"{source_code} G17 G90\nG0 X0 Y0\nG1 X{source_position} Y0 F25.4\nM30\n", encoding="utf-8")
    assert main(["export", str(source), "--lang", "fanuc_mill", "--units", units, "-o", str(output)]) == 0
    exported = output.read_text(encoding="utf-8")
    assert target_code in exported
    before, *_ = execute_program(source.read_text(encoding="utf-8"), language="fanuc_mill")
    after, *_ = execute_program(exported, language="fanuc_mill")
    assert after.ok and after.complete
    assert after.motions[-1].end_x == pytest.approx(before.motions[-1].end_x, abs=1e-4)


def test_dxf_inches_scale_resolved_geometry(tmp_path):
    source = tmp_path / "part.nc"
    source.write_text("G21 G17 G90\nG0 X0 Y0\nG1 X25.4 Y0 F100\nM30\n", encoding="utf-8")
    output = tmp_path / "part.dxf"
    assert (
        main(["export", str(source), "--lang", "fanuc_mill", "--format", "dxf", "--units", "inch", "-o", str(output)])
        == 0
    )
    document = ezdxf.readfile(output)
    assert document.units == 1
    lines = list(document.modelspace().query("LINE"))
    assert lines[-1].dxf.end.x == pytest.approx(1.0)


def test_single_and_batch_dxf_are_byte_identical(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    source = root / "part.nc"
    source.write_text("G21 G17 G90\nG0 X0 Y0\nG1 X10 Y0 F100\nM30\n", encoding="utf-8")
    single = tmp_path / "single.dxf"
    batch = tmp_path / "batch"
    options = ["--lang", "fanuc_mill", "--format", "dxf", "--units", "inch"]
    assert main(["export", str(source), *options, "-o", str(single)]) == 0
    assert main(["batch-export", str(root), *options, "-o", str(batch)]) == 0
    assert single.read_bytes() == (batch / "part.dxf").read_bytes()


def test_full_batch_does_not_assign_one_fake_program_number_to_every_file(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "first.nc").write_text("G21 G18\nG0 X10 Z0\nM30\n", encoding="utf-8")
    (root / "second.nc").write_text("G21 G18\nG0 X20 Z0\nM30\n", encoding="utf-8")
    output = tmp_path / "output"
    assert main(["batch-export", str(root), "--mode", "full", "-o", str(output)]) == 0
    assert "O0001" not in (output / "first.nc").read_text(encoding="utf-8")
    assert "O0001" not in (output / "second.nc").read_text(encoding="utf-8")


@pytest.mark.parametrize("mode", ["full", "expanded"])
def test_no_comments_omits_source_and_generated_annotations(tmp_path, mode):
    source = tmp_path / "part.nc"
    source.write_text("O1234 (SOURCE)\nG21 G18\nG0 X10 Z0 ; NOTE\nM30\n", encoding="utf-8")
    output = tmp_path / "part-out.nc"
    assert main(["export", str(source), "--mode", mode, "--no-comments", "-o", str(output)]) == 0
    text = output.read_text(encoding="utf-8")
    assert "SOURCE" not in text
    assert "NOTE" not in text
    assert "EXPANDED" not in text
    assert "(" not in text and ";" not in text


def test_turning_safety_line_keeps_turning_plane(tmp_path):
    source = tmp_path / "turn.nc"
    source.write_text("G21 G18\nG0 X10 Z0\nM30\n", encoding="utf-8")
    output = tmp_path / "out.nc"
    assert main(["export", str(source), "--safety-line", "-o", str(output)]) == 0
    assert "G0 G18 G40 G80" in output.read_text(encoding="utf-8")


def test_incremental_milling_export_preserves_geometry(tmp_path):
    source = tmp_path / "source.nc"
    source.write_text("G21 G17 G90\nG0 X10 Y10\nG1 X20 Y15 F100\nM30\n", encoding="utf-8")
    output = tmp_path / "incremental.nc"
    assert main(["export", str(source), "--lang", "fanuc_mill", "--coordinates", "incremental", "-o", str(output)]) == 0
    text = output.read_text(encoding="utf-8")
    assert "G91" in text
    before, *_ = execute_program(source.read_text(encoding="utf-8"), language="fanuc_mill")
    after, *_ = execute_program(text, language="fanuc_mill")
    assert after.motions[-1].end_x == pytest.approx(before.motions[-1].end_x)
    assert after.motions[-1].end_y == pytest.approx(before.motions[-1].end_y)


@pytest.mark.parametrize("arc_type", ["ijk-relative", "ijk-absolute", "radius", "linearized"])
def test_milling_arc_export_preserves_end_geometry(tmp_path, arc_type):
    source = tmp_path / "arc.nc"
    output = tmp_path / "converted.nc"
    source.write_text("G21 G17 G90\nG0 X0 Y0\nG2 X10 Y10 I10 J0 F100\nM30\n", encoding="utf-8")
    assert (
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--arc-type",
                arc_type,
                "--units",
                "inch",
                "-o",
                str(output),
            ]
        )
        == 0
    )
    before, *_ = execute_program(source.read_text(encoding="utf-8"), language="fanuc_mill", autodetect_arc_type=True)
    after, *_ = execute_program(output.read_text(encoding="utf-8"), language="fanuc_mill", autodetect_arc_type=True)
    assert after.ok and after.complete
    assert after.motions[-1].end_x == pytest.approx(before.motions[-1].end_x, abs=1e-4)
    assert after.motions[-1].end_y == pytest.approx(before.motions[-1].end_y, abs=1e-4)


@pytest.mark.parametrize("fixture", ["contur_2d.nc", "flange_plate_benchmark.nc"])
def test_expanded_milling_restores_absolute_mode_after_home_return(tmp_path, fixture):
    source = Path(__file__).resolve().parents[1] / "fixtures" / "milling" / fixture
    output = tmp_path / "expanded.nc"
    assert main(["export", str(source), "--lang", "fanuc_mill", "-o", str(output)]) == 0
    before, *_ = execute_program(source.read_text(encoding="utf-8"), language="fanuc_mill", autodetect_arc_type=True)
    after, *_ = execute_program(output.read_text(encoding="utf-8"), language="fanuc_mill", autodetect_arc_type=True)
    assert after.ok and after.complete
    assert len(after.motions) == len(before.motions)
    for original, exported in zip(before.motions, after.motions, strict=True):
        assert (exported.end_x, exported.end_y, exported.end_z) == pytest.approx(
            (original.end_x, original.end_y, original.end_z), abs=1e-3
        )


def test_batch_report_and_bad_file_isolation(tmp_path):
    root = tmp_path / "source"
    nested = root / "nested"
    nested.mkdir(parents=True)
    good = nested / "good.nc"
    good.write_text("G21 G18\nG0 X10 Z0\nM30\n", encoding="utf-8")
    (root / "bad.nc").write_bytes(b"\xff\xff")
    output = tmp_path / "out"
    assert main(["batch-export", str(root), "-o", str(output)]) == 2
    report = json.loads((output / "batch_export_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "ERRORS"
    assert report["summary"]["files_total"] == 2
    assert report["summary"]["exported"] == 1
    assert [item["input_relative_path"] for item in report["files"]] == ["bad.nc", "nested/good.nc"]
    assert report["files"][0]["output_path"] is None
    assert (output / "nested" / "good.nc").exists()
    with (output / "batch_export_report.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2


def test_batch_dxf_preserves_tree_and_honors_discovery_options(tmp_path):
    root = tmp_path / "source"
    nested = root / "nested"
    nested.mkdir(parents=True)
    for path in (root / "top.mpf", nested / "child.mpf"):
        path.write_text("G21 G17 G90\nG0 X0 Y0\nG1 X10 Y0 F100\nM30\n", encoding="utf-8")
    output = tmp_path / "dxf"
    assert (
        main(
            [
                "batch-export",
                str(root),
                "--lang",
                "fanuc_mill",
                "--format",
                "dxf",
                "--extensions",
                ".mpf",
                "--top-level-only",
                "-o",
                str(output),
            ]
        )
        == 0
    )
    assert (output / "top.dxf").exists()
    assert not (output / "nested" / "child.dxf").exists()
    report = json.loads((output / "batch_export_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["files_total"] == 1
    assert report["files"][0]["output_relative_path"] == "top.dxf"


def test_batch_export_recognizes_fanuc_programs_named_as_part_numbers(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    for name in ("O30", "1580.000.03-1UST", "1580.000.03-2UST"):
        (root / name).write_text("%\nO1234\nG21 G17 G90\nG0 X0 Y0 Z5\nM30\n%\n", encoding="utf-8")
    (root / "drawing.pdf").write_bytes(b"%PDF-1.4\n1 0 obj\n")
    (root / "photo.jpg").write_bytes(b"\xff\xd8\x00G21\nG0 X0\n")
    output = tmp_path / "output"

    assert main(["batch-export", str(root), "--lang", "fanuc_mill", "-o", str(output)]) == 0
    assert sorted(path.name for path in output.glob("*.nc")) == [
        "1580.000.03-1UST.nc",
        "1580.000.03-2UST.nc",
        "O30.nc",
    ]
    report = json.loads((output / "batch_export_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["files_total"] == 3


def test_custom_extensions_limit_batch_discovery(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "O30").write_text("O30\nG0 X0\nM30\n", encoding="utf-8")
    (root / "part.mpf").write_text("O31\nG0 X0\nM30\n", encoding="utf-8")
    output = tmp_path / "output"

    assert main(["batch-export", str(root), "--extensions", ".mpf", "-o", str(output)]) == 0
    report = json.loads((output / "batch_export_report.json").read_text(encoding="utf-8"))
    assert [item["input_relative_path"] for item in report["files"]] == ["part.mpf"]


def test_invalid_execution_writes_no_export_and_next_file_runs(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "bad.nc").write_text("G21 G17 G90\nG2 X10 Y0 R1\nM30\n", encoding="utf-8")
    (root / "good.nc").write_text("G21 G17 G90\nG0 X10 Y0\nM30\n", encoding="utf-8")
    output = tmp_path / "output"
    assert main(["batch-export", str(root), "--lang", "fanuc_mill", "-o", str(output)]) == 2
    assert not (output / "bad.nc").exists()
    assert (output / "good.nc").exists()
    report = json.loads((output / "batch_export_report.json").read_text(encoding="utf-8"))
    assert report["files"][0]["diagnostics"][0]["code"] == "INVALID_GEOMETRY"


def test_unexpected_export_bug_propagates(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "part.nc").write_text("M30\n", encoding="utf-8")

    def fail(*_args, **_kwargs):
        raise RuntimeError("internal regression")

    monkeypatch.setattr("app.gcode.export.service.execute_program", fail)
    with pytest.raises(RuntimeError, match="internal regression"):
        main(["batch-export", str(root), "-o", str(tmp_path / "output")])


def test_batch_rejects_output_under_source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "part.nc").write_text("M30\n", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["batch-export", str(root), "-o", str(root / "output")])
    assert error.value.code == 2
    assert not (root / "output").exists()


def test_batch_detects_output_name_collisions(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    for name in ("part.nc", "part.tap"):
        (root / name).write_text("M30\n", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["batch-export", str(root), "-o", str(tmp_path / "output")])
    assert error.value.code == 2


@pytest.mark.parametrize(
    "args",
    [
        ["--format", "dxf", "--no-comments"],
        ["--mode", "full", "--units", "inch"],
        ["--mode", "full", "--arc-type", "radius"],
        ["--lang", "fanuc_turn", "--arc-type", "radius"],
        ["--sequence-increment", "10"],
    ],
)
def test_single_and_batch_share_option_validation(tmp_path, args):
    root = tmp_path / "source"
    root.mkdir()
    source = root / "part.nc"
    source.write_text("M30\n", encoding="utf-8")
    for command, target in (("export", source), ("batch-export", root)):
        with pytest.raises(SystemExit) as error:
            main([command, str(target), *args, "-o", str(tmp_path / command)])
        assert error.value.code == 2


def test_batch_empty_directory_reports_no_files(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    output = tmp_path / "output"
    assert main(["batch-export", str(root), "-o", str(output)]) == 2
    report = json.loads((output / "batch_export_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "NO_FILES"
