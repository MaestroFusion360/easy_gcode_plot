from __future__ import annotations

import pytest

from app.gcode.core import (
    calculate_scene_geometry,
    calculate_toolpath_metrics,
    format_gcode_number,
    has_motion,
    last_index,
)
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


def test_list_and_motion_helpers_have_exact_semantics():
    assert last_index([10, 20, 10, 30], 10) == 2
    assert last_index([1, 2, 3], 4) is None
    assert has_motion([0, 0, 3], [0, 0, 4], [0, 0, 0]) is True
    assert has_motion([2, 2, 2], [3, 3, 3], [4, 4, 4]) is False


def test_toolpath_metrics_use_destination_feed_and_zero_feed_is_zero_time():
    lengths, times, has_points = calculate_toolpath_metrics([0, 3], [0, 4], [0, 0], [100, 5])
    assert lengths == pytest.approx([5.0])
    assert times == pytest.approx([1.0])
    assert has_points is True

    lengths, times, has_points = calculate_toolpath_metrics([0, 3], [0, 4], [0, 0], [100, 0])
    assert lengths == pytest.approx([5.0])
    assert times == [0]
    assert has_points is True

    assert calculate_toolpath_metrics([], [], [], []) == ([], [], False)


def test_scene_geometry_has_exact_center_and_distance():
    center, distance = calculate_scene_geometry([-2, 2], [-3, 3], [10, 20])
    assert center == pytest.approx((0, 0, 15))
    assert distance == pytest.approx(10.5)


def test_parser_preserves_repeated_g_words_and_eval_words_keeps_all_values():
    program = parse_program(["G18 G21 G0 X10"])
    block = program.blocks[0]
    assert [word.letter + word.expr for word in block.parsed_words] == ["G18", "G21", "G0", "X10"]

    words = eval_words(block.parsed_words, {})
    assert words["G"] == 0.0
    assert words.all("G") == (18.0, 21.0, 0.0)
