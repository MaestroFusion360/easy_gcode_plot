"""Read failures and output collisions never destroy a source program."""

import os
import subprocess
from pathlib import Path

import pytest

from app.cli import main
from app.gcode.batch.analysis import analyze_directory
from app.gcode.batch.export import export_directory
from app.gcode.export.service import ExportRequest
from app.gcode.file_io import atomic_write_text


@pytest.mark.parametrize("command", ["parse", "trace", "analyze"])
@pytest.mark.parametrize("invalid", ["missing", "encoding", "directory"])
def test_cli_read_errors_return_two_without_traceback(tmp_path, capsys, command, invalid):
    source = tmp_path / "input.nc"
    if invalid == "encoding":
        source.write_bytes(b"\xff")
    elif invalid == "directory":
        source.mkdir()
    assert main([command, str(source), "--lang", "fanuc_mill"]) == 2
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["trace", "analyze"])
@pytest.mark.parametrize("alias", ["same", "relative", "hardlink"])
def test_cli_rejects_source_as_output_before_writing(tmp_path, capsys, monkeypatch, command, alias):
    source = tmp_path / "input.nc"
    original = "G1 X10 F100\nM30\n"
    source.write_text(original, encoding="utf-8")
    output = source
    if alias == "relative":
        monkeypatch.chdir(tmp_path)
        output = Path("input.nc")
    elif alias == "hardlink":
        output = tmp_path / "alias.nc"
        output.hardlink_to(source)
    assert main([command, str(source), "--lang", "fanuc_mill", "-o", str(output)]) == 2
    assert source.read_text(encoding="utf-8") == original and output.read_text(encoding="utf-8") == original
    assert "source file" in capsys.readouterr().err


def test_cli_rejects_json_html_collision_before_either_is_written(tmp_path, capsys):
    source = tmp_path / "input.nc"
    source.write_text("G1 X10 F100\nM30")
    output = tmp_path / "report.html"
    output.write_text("EXISTING REPORT")
    assert main(["analyze", str(source), "--lang", "fanuc_mill", "-o", str(output), "--html", str(output)]) == 2
    assert output.read_text() == "EXISTING REPORT"
    terminal = capsys.readouterr()
    assert "HTML statistics:" not in terminal.out
    assert "Output paths" in terminal.err


def test_cli_output_io_failure_is_controlled(tmp_path, capsys, monkeypatch):
    source = tmp_path / "input.nc"
    source.write_text("G1 X10 F100\nM30")

    def fail(*_args, **_kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr("app.cli.atomic_write_text", fail)
    assert main(["trace", str(source), "--lang", "fanuc_mill", "-o", str(tmp_path / "trace.json")]) == 2
    assert "simulated disk failure" in capsys.readouterr().err


def test_atomic_report_write_preserves_previous_output_on_commit_failure(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("PREVIOUS REPORT")

    def fail(*_args):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(OSError, match="replace failure"):
        atomic_write_text(output, "NEW REPORT")
    assert output.read_text() == "PREVIOUS REPORT"
    assert not list(tmp_path.glob(".report.json.*"))


def test_batch_export_preflights_other_sources_before_any_write(tmp_path):
    source_root = tmp_path / "source"
    nested = source_root / "source"
    nested.mkdir(parents=True)
    first = source_root / "part.nc"
    second = nested / "part.nc"
    first.write_text("G1 X1 F100\nM30\n", encoding="utf-8")
    second.write_text("G1 X99 F100\nM30\n", encoding="utf-8")
    originals = {path: path.read_bytes() for path in (first, second)}

    with pytest.raises(ValueError, match="input file"):
        export_directory(source_root, tmp_path, ExportRequest(language="fanuc_mill"))

    assert {path: path.read_bytes() for path in originals} == originals
    assert not (tmp_path / "part.nc").exists()


def test_batch_export_rejects_resolved_destination_aliases(tmp_path):
    source_root = tmp_path / "source"
    for folder, position in (("a", 1), ("b", 99)):
        directory = source_root / folder
        directory.mkdir(parents=True)
        (directory / "part.nc").write_text(f"G1 X{position} F100\nM30\n", encoding="utf-8")
    output = tmp_path / "output"
    (output / "a").mkdir(parents=True)
    try:
        (output / "b").symlink_to(output / "a", target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            pytest.skip(f"Directory symlinks unavailable: {error}")
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(output / "b"), str(output / "a")],
            capture_output=True,
            check=False,
        )
        if junction.returncode:
            pytest.skip(f"Directory aliases unavailable: {error}")

    with pytest.raises(ValueError, match="same output"):
        export_directory(source_root, output, ExportRequest(language="fanuc_mill"))

    assert not (output / "a" / "part.nc").exists()


def test_batch_html_preflights_other_sources_before_any_write(tmp_path):
    source_root = tmp_path / "source"
    nested = source_root / "source"
    nested.mkdir(parents=True)
    first = source_root / "part.nc.html"
    second = nested / "part.nc"
    first.write_text("G1 X1 F100\nM30\n", encoding="utf-8")
    second.write_text("G1 X99 F100\nM30\n", encoding="utf-8")
    originals = {path: path.read_bytes() for path in (first, second)}

    with pytest.raises(ValueError, match="input file"):
        analyze_directory(source_root, language="fanuc_mill", extensions=(".nc", ".html"), html_dir=tmp_path)

    assert {path: path.read_bytes() for path in originals} == originals
    assert not (tmp_path / "part.nc.html.html").exists()


def test_batch_export_allows_noncolliding_ancestor_output(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / "part.nc"
    source.write_text("G1 X1 F100\nM30\n", encoding="utf-8")
    original = source.read_bytes()

    report = export_directory(source_root, tmp_path, ExportRequest(language="fanuc_mill"))

    assert report["summary"]["exported"] == 1
    assert (tmp_path / "part.nc").exists()
    assert source.read_bytes() == original
