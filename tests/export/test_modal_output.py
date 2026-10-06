"""EXPANDED modal F output keeps arcs explicit and optional."""

from __future__ import annotations

from app.cli import main
from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program
from app.gcode.export.full import normalize_full_program
from app.gcode.kernel import execute

SOURCE = "G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nX20\nX30\nM30"


def test_modal_feed_default_suppresses_repeated_feed():
    result = execute(SOURCE, language="fanuc_mill")
    text = convert_resolved_program(result, "fanuc_mill", ExportOptions(delimiter=True))

    assert text.count("F100") == 1
    assert text.count("G1 ") == 3


def test_modal_feed_can_be_disabled():
    result = execute(SOURCE, language="fanuc_mill")
    text = convert_resolved_program(result, "fanuc_mill", ExportOptions(delimiter=True, modal_feed=False))

    assert text.count("F100") == 3


def test_feed_mode_change_restates_feed():
    source = "G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nG95\nG1 X20 Y0 Z0 F100\nG94\nG1 X30 Y0 Z0 F100\nM30"
    result = execute(source, language="fanuc_mill")
    text = convert_resolved_program(result, "fanuc_mill", ExportOptions(delimiter=True))

    assert text.count("F100") == 3


def test_full_circle_arcs_are_explicit_on_both_halves():
    result = execute("G21 G17 G90\nG0 X10 Y0\nG2 X10 Y0 I-10 J0 F100\nM30", language="fanuc_mill")
    text = convert_resolved_program(result, "fanuc_mill", ExportOptions(arc_mode=2, delimiter=True))

    arc_lines = [line for line in text.splitlines() if line.startswith("G2 ")]
    assert len(arc_lines) == 2
    assert all(" R10" in line and "X" in line for line in arc_lines)


def test_cli_no_modal_feed_flag_restates_every_feed(tmp_path):
    source = tmp_path / "part.nc"
    source.write_text("G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nX20\nM30\n", encoding="utf-8")
    output = tmp_path / "out.nc"

    assert main(["export", str(source), "--lang", "fanuc_mill", "--no-modal-feed", "-o", str(output)]) == 0
    assert output.read_text(encoding="utf-8").count("F100") == 2


def test_full_program_output_is_not_modalised():
    source = "G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nG1 X20 Y0 Z0 F100\nM30\n"
    result = execute(source, language="fanuc_mill")

    text = normalize_full_program(result, source, ExportOptions(delimiter=True))
    # FULL is source-preserving; modal F only affects EXPANDED output.
    assert text.count("F100") == 2
