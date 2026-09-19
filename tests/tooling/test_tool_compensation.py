from __future__ import annotations

import pytest

from app.gcode.kernel.compensation import geometry
from app.gcode.kernel.compensation.turning import ToolCompensationError, joins, nose
from app.gcode.kernel.model import Motion, Point2

TOOL = {
    "type": "diamond_80",
    "applications": ["od"],
    "noseRadius": 1.0,
    "tipOrientation": 9,
}


def _motion(
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    move: int = 1,
    mode: int = 41,
    tool: str = "T0101",
    i: float | None = None,
    k: float | None = None,
) -> Motion:
    return Motion(
        move=move,
        start=Point2(*start),
        end=Point2(*end),
        i=i,
        k=k,
        compensation_mode=mode,
        tool=tool,
    )


@pytest.mark.parametrize(
    ("orientation", "expected"),
    [(1, (0.8, 0.8)), (5, (0.0, 0.8)), (9, (0.0, 0.0))],
)
def test_tip_orientation_vector_covers_diagonal_axial_and_center_references(orientation, expected):
    assert nose.tip_orientation_vector(orientation, 0.8) == expected


@pytest.mark.parametrize("orientation", [0, 10, "bad"])
def test_tip_orientation_rejects_values_outside_fanuc_range(orientation):
    with pytest.raises(ToolCompensationError, match="range 1-9"):
        nose.tip_orientation_vector(orientation, 0.8)


@pytest.mark.parametrize(
    ("mode", "expected_x"),
    [(41, 18.0), (42, 22.0)],
)
def test_straight_cut_offsets_to_the_correct_side_in_diameter_coordinates(mode, expected_x):
    primitive = nose.offset_motion(  # pylint: disable=protected-access
        _motion((20.0, 0.0), (20.0, -10.0), mode=mode),
        radius=1.0,
        orientation=9,
    )

    assert primitive.start.x * 2.0 == pytest.approx(expected_x)
    assert primitive.end.x * 2.0 == pytest.approx(expected_x)


@pytest.mark.parametrize(
    ("mode", "expected_corner"),
    [(41, Point2(18.0, -11.0)), (42, Point2(22.0, -9.0))],
)
def test_compensation_joins_both_corner_handednesses_without_a_gap(mode, expected_corner):
    motions = [
        _motion((20.0, 5.0), (20.0, 0.0), mode=mode),
        _motion((20.0, 0.0), (20.0, -10.0), mode=mode),
        _motion((20.0, -10.0), (40.0, -10.0), mode=mode),
    ]

    result = nose.apply_tool_nose_compensation(motions, {"T0101": TOOL})

    assert result[1].end == expected_corner
    assert result[2].start == expected_corner
    assert all(item.compensation_applied for item in result)


def test_zero_length_transition_uses_only_the_tip_reference_translation():
    primitive = nose.offset_motion(  # pylint: disable=protected-access
        _motion((20.0, -4.0), (20.0, -4.0)),
        radius=2.0,
        orientation=1,
    )

    assert primitive.start == geometry.Vec2(12.0, -2.0)  # pylint: disable=protected-access
    assert primitive.end == primitive.start


def test_parallel_disconnected_segments_fail_instead_of_inventing_a_corner():
    first = nose.offset_motion(  # pylint: disable=protected-access
        _motion((20.0, 0.0), (20.0, -10.0)), 1.0, 9
    )
    second = nose.offset_motion(  # pylint: disable=protected-access
        _motion((40.0, -10.0), (40.0, -20.0)), 1.0, 9
    )

    with pytest.raises(ToolCompensationError, match="do not intersect"):
        joins.join_primitives(first, second)  # pylint: disable=protected-access


def test_arc_that_collapses_under_compensation_is_rejected():
    arc = _motion((20.0, 0.0), (0.0, 10.0), move=3, mode=41, i=-20.0, k=0.0)

    with pytest.raises(ToolCompensationError, match="collapses"):
        nose.offset_motion(arc, radius=10.0, orientation=9)  # pylint: disable=protected-access


def test_invalid_arc_center_is_rejected_before_offsetting():
    arc = _motion((20.0, 0.0), (0.0, 9.0), move=3, mode=41, i=-20.0, k=0.0)

    with pytest.raises(ToolCompensationError, match="Invalid tool compensation arc"):
        nose.offset_motion(arc, radius=1.0, orientation=9)  # pylint: disable=protected-access


def test_compensation_exit_starts_at_the_actual_compensated_endpoint():
    cutting = _motion((20.0, 0.0), (20.0, -10.0))
    exit_move = _motion((20.0, -10.0), (40.0, 0.0), mode=40)

    result = nose.apply_tool_nose_compensation([cutting, exit_move], {"T0101": TOOL})

    assert result[1].start == result[0].end
    assert result[1].source_kind == "tool_compensation_exit"


def test_missing_tool_is_reported_and_keeps_the_nominal_trace():
    motion = _motion((20.0, 0.0), (20.0, -10.0), tool="T9999")

    assert nose.missing_compensation_tools([motion], {}) == ("T9999",)
    assert nose.apply_tool_nose_compensation([motion], {}) == [motion]


@pytest.mark.parametrize(
    ("tool", "message"),
    [
        ({**TOOL, "type": "drill"}, "requires a turning tool"),
        ({**TOOL, "noseRadius": 0.0}, "must be positive"),
    ],
)
def test_unsafe_tool_definitions_are_rejected(tool, message):
    with pytest.raises(ToolCompensationError, match=message):
        nose.apply_tool_nose_compensation(
            [_motion((20.0, 0.0), (20.0, -10.0))],
            {"T0101": tool},
        )
