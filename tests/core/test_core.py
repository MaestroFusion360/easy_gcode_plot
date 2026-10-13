from __future__ import annotations

import pytest

from app.gcode.core import format_gcode_number
from app.gcode.kernel.program import eval_words, parse_program


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        (0, "0"),
        (12, "12"),
        (1.2344, "1.234"),
        (1.230, "1.23"),
        (-0.125, "-0.125"),
    ],
)
def test_gcode_number_formatting(value, expected):
    assert format_gcode_number(value) == expected


def test_parser_preserves_repeated_g_words_and_eval_words_keeps_all_values():
    program = parse_program(["G18 G21 G0 X10"])
    block = program.blocks[0]
    assert [word.letter + word.expr for word in block.parsed_words] == ["G18", "G21", "G0", "X10"]

    words = eval_words(block.parsed_words, {})
    assert words["G"] == 0.0
    assert words.all("G") == (18.0, 21.0, 0.0)
