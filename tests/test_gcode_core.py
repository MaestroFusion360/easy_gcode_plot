import pytest

from app.gcode.core import (
    calculate_scene_geometry,
    calculate_toolpath_metrics,
    format_gcode_number,
    has_motion,
    last_index,
)


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
def test_format_gcode_number(value, expected):
    assert format_gcode_number(value) == expected


def test_last_index_returns_last_duplicate():
    assert last_index([10, 20, 10, 30], 10) == 2


def test_last_index_returns_none_when_missing():
    assert last_index([1, 2, 3], 4) is None


def test_has_motion_detects_real_coordinate_change():
    assert has_motion([0, 0, 3], [0, 0, 4], [0, 0, 0]) is True


def test_has_motion_regression_repeated_points_are_not_motion():
    assert has_motion([2, 2, 2], [3, 3, 3], [4, 4, 4]) is False


def test_calculate_toolpath_metrics_uses_destination_feed():
    lengths, times, has_points = calculate_toolpath_metrics(
        [0, 3],
        [0, 4],
        [0, 0],
        [100, 5],
    )

    assert lengths == pytest.approx([5.0])
    assert times == pytest.approx([1.0])
    assert has_points is True


def test_calculate_toolpath_metrics_regression_zero_feed_has_zero_time():
    lengths, times, has_points = calculate_toolpath_metrics(
        [0, 3],
        [0, 4],
        [0, 0],
        [100, 0],
    )

    assert lengths == pytest.approx([5.0])
    assert times == [0]
    assert has_points is True


def test_calculate_toolpath_metrics_empty_input_matches_existing_false_result():
    lengths, times, has_points = calculate_toolpath_metrics([], [], [], [])

    assert lengths == []
    assert times == []
    assert has_points is False


def test_calculate_scene_geometry_preserves_existing_xy_distance_formula():
    center, distance = calculate_scene_geometry(
        [-2, 2],
        [-3, 3],
        [10, 20],
    )

    assert center == pytest.approx((0, 0, 15))
    assert distance == 10.5
