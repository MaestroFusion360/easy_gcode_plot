"""Formatting options for source-preserving Full Program conversion."""

from __future__ import annotations

import pytest

from app.gcode.export.source_formatting import format_full_program_source
from app.gcode.exporter import ExportOptions


def test_full_program_formatter_numbers_blocks_and_pads_controller_addresses():
    source = "%\nO0001\nN5 T1 M6 H2 D3 G0 X0 (keep comment)\nM30\n%\n"
    options = ExportOptions(
        sequence_numbers=True,
        sequence_start=100,
        sequence_increment=10,
        delimiter=True,
        leading_zero=True,
    )

    formatted = format_full_program_source(source, options)

    assert formatted == "%\nO0001\nN100 T01 M06 H02 D03 G00 X0 (keep comment)\nN110 M30\n%\n"


def test_full_program_formatter_removes_old_labels_compacts_words_and_preserves_block_skip():
    source = "N5 G21 G17 G90\n/N10 G0 X0 Y0\nN20 G1 X10 F100\n"

    formatted = format_full_program_source(source, ExportOptions(sequence_numbers=False, delimiter=False))

    assert formatted == "G21G17G90\n/G0X0Y0\nG1X10F100\n"


def test_full_program_formatter_refuses_to_change_sequence_labels_used_by_goto():
    source = "N10 G0 X0\nN20 IF [#1 EQ 0] GOTO 10\n"

    with pytest.raises(ValueError, match="GOTO labels"):
        format_full_program_source(source, ExportOptions(sequence_numbers=False))


def test_full_program_formatter_applies_program_header_safety_and_end_options():
    source = "%\nO0001\nG291\nG21 G17 G90\nM30\n%\n"
    options = ExportOptions(start_program="O0002", end_program="M2", safety_line=True, delimiter=True)

    formatted = format_full_program_source(source, options)

    assert formatted == "%\nO0002\nG291\nG80\nG0 G17 G40 G49 G90\nG21 G17 G90\nM2\n%\n"


def test_leading_zero_formatting_is_idempotent_for_already_padded_addresses():
    source = "G0 G00 G1 G01 G000 G0001 M1 M01 T1 T001\n"
    options = ExportOptions(leading_zero=True, delimiter=True)

    once = format_full_program_source(source, options)
    twice = format_full_program_source(once, options)

    assert once == "G00 G00 G01 G01 G00 G01 M01 M01 T01 T01\n"
    assert twice == once


def test_disabling_leading_zeros_removes_padding_from_existing_addresses():
    source = "G000 G001 G0001 M001 T001 H002 D003\n"

    formatted = format_full_program_source(source, ExportOptions(leading_zero=False, delimiter=True))

    assert formatted == "G0 G1 G1 M1 T1 H2 D3\n"


@pytest.mark.parametrize(
    "source, expected",
    [
        ("%\nO1\nG0 X1\n%\n", "%\nO1\nG0 X1\nM30\n%\n"),
        ("G0 X1", "G0 X1\nM30\n"),
    ],
)
def test_missing_program_end_is_inserted_without_overwriting_existing_blocks(source, expected):
    assert format_full_program_source(source, ExportOptions(end_program="M30", delimiter=True)) == expected


def test_multiline_header_keeps_blocks_separate_without_final_newline():
    assert format_full_program_source("O1", ExportOptions(start_program="O2\nG21")) == "O2\nG21"
