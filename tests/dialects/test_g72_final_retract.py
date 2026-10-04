"""The final facing contour must escape before returning to the cycle start."""

import pytest

from app.gcode.kernel.frontend.model import Point2, ProfileSegment
from app.gcode.kernel.turning.cycles.g72 import build_g72_facing


@pytest.mark.parametrize("stock_x,end_x,sign_x", [(24, 10, 1), (6, 20, -1)])
@pytest.mark.parametrize("stock_z,end_z,sign_z", [(2, -10, 1), (-12, 0, -1)])
def test_g72_final_contour_retract_then_z_then_x(stock_x, end_x, sign_x, stock_z, end_z, sign_z):
    start_x = 20 if sign_x == 1 else 10
    start_z = 0 if sign_z == 1 else -10
    profile = [ProfileSegment(0, 1, Point2(start_x, start_z), Point2(end_x, end_z), False, 0, False, Point2(0, 0))]
    motions = build_g72_facing(profile, stock_x, stock_z, 2, 0.2, 0, 0, 100)
    assert len(motions) >= 3
    retract, axial, radial = motions[-3], motions[-2], motions[-1]
    assert retract.start == profile[-1].end
    assert retract.end == Point2(end_x + sign_x * 0.4, end_z + sign_z * 0.2)
    assert axial.start == retract.end
    assert axial.end == radial.start == Point2(retract.end.x, stock_z)
    assert radial.end == Point2(stock_x, stock_z)
    assert all(m.move == 0 for m in (retract, axial, radial))
