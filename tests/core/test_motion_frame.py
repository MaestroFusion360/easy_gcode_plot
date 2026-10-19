"""Analytical rigid-frame checks for arc geometry and source ownership."""

import math

import pytest

from app.gcode.kernel.geometry.motion_frame import motion_frame
from app.gcode.kernel.types import ArcGeometry, TraceMotion


@pytest.mark.parametrize(
    "plane,start,end,normal,display_start,display_end,display_normal",
    [
        (17, (2, 0, 0), (0, 2, 0), (0, 0, 1), (15, -17, 29), (13, -17, 31), (0, -1, 0)),
        (18, (0, 0, 2), (2, 0, 0), (0, 1, 0), (13, -19, 29), (15, -17, 29), (0, 0, 1)),
        (19, (0, 2, 0), (0, 0, 2), (1, 0, 0), (13, -17, 31), (13, -19, 29), (1, 0, 0)),
    ],
)
def test_rotated_translated_arcs_preserve_geometry_and_source(
    plane, start, end, normal, display_start, display_end, display_normal
):
    motion = TraceMotion(
        move=3,
        start_x=start[0],
        start_y=start[1],
        start_z=start[2],
        end_x=end[0],
        end_y=end[1],
        end_z=end[2],
        i=-start[0],
        j=-start[1],
        k=-start[2],
        plane=plane,
        arc=ArcGeometry(center=(0, 0, 0), radius=2, sweep=math.pi / 2, plane=plane, clockwise=False, full_circle=False),
        orientation=((1, 0, 0), (0, 0, -1), (0, 1, 0)),
        orientation_offset=(13, -17, 29),
        absolute_center_offset=(1, 2, 3),
        source_block=7,
        source_raw="N80 G3",
        feed=120,
        tool=4,
        additional_turns=2,
    )
    display = motion_frame(motion, local=False)
    assert (display.start_x, display.start_y, display.start_z) == pytest.approx(display_start)
    assert (display.end_x, display.end_y, display.end_z) == pytest.approx(display_end)
    assert display.arc.center == pytest.approx((13, -17, 29))
    assert display.arc.normal == pytest.approx(display_normal)
    assert (display.i, display.j, display.k) == pytest.approx(
        tuple(center - point for center, point in zip(display.arc.center, display_start))
    )
    assert display.absolute_center_offset == pytest.approx((14, -20, 31))
    restored = motion_frame(display, local=True)
    assert (restored.start_x, restored.start_y, restored.start_z) == pytest.approx(start)
    assert (restored.end_x, restored.end_y, restored.end_z) == pytest.approx(end)
    assert restored.arc.center == pytest.approx((0, 0, 0))
    assert restored.arc.normal == pytest.approx(normal)
    assert restored.absolute_center_offset == pytest.approx((1, 2, 3))
    assert restored.arc.sweep == motion.arc.sweep
    assert restored.arc.radius == 2 and not restored.arc.clockwise
    assert (restored.source_block, restored.source_raw, restored.feed, restored.tool, restored.additional_turns) == (
        7,
        "N80 G3",
        120,
        4,
        2,
    )


def test_unoriented_motion_keeps_identity_and_absent_arc_offsets():
    motion = TraceMotion(move=1, start_x=0, start_z=0, end_x=10, end_z=5)
    assert motion_frame(motion, local=True) is motion
    assert motion_frame(motion, local=False) is motion


def test_rotated_linear_motion_does_not_acquire_ijk_or_arc_geometry():
    motion = TraceMotion(
        move=1,
        start_x=0,
        start_z=0,
        end_x=10,
        end_z=5,
        orientation=((1, 0, 0), (0, 0, -1), (0, 1, 0)),
        orientation_offset=(13, -17, 29),
    )
    display = motion_frame(motion, local=False)
    assert (display.end_x, display.end_y, display.end_z) == pytest.approx((23, -22, 29))
    assert (display.i, display.j, display.k, display.arc) == (None, None, None, None)
