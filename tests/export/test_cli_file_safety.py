"""Read failures and output collisions never destroy a source program."""

from pathlib import Path

import pytest

from app.cli import main
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
