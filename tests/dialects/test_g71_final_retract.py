"""G71 final contour escape precedes the axial and radial return."""

import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.frontend.model import Point2, ProfileSegment
from app.gcode.kernel.turning.cycles.g71 import build_g71_roughing


@pytest.mark.parametrize("boring", [False, True])
@pytest.mark.parametrize("start_z,end_z", [(1, -10), (-1, 10)])
@pytest.mark.parametrize("retract", [0, 0.2])
def test_final_contour_retract_then_z_then_x(boring, start_z, end_z, retract):
    start_x, end_x, stock_x = (10, 20, 6) if boring else (20, 10, 24)
    profile = [ProfileSegment(0, 1, Point2(start_x, 0), Point2(end_x, end_z), False, 0, False, Point2(0, 0))]
    motions = build_g71_roughing(profile, stock_x, start_z, 2, retract, 0, 100, boring)
    assert len(motions) >= 2
    z_return, x_return = motions[-2], motions[-1]
    escaped_x = end_x + (-2 * retract if boring else 2 * retract)
    escaped_z = end_z + (retract if start_z >= end_z else -retract)
    assert z_return.move == x_return.move == 0
    assert z_return.start == Point2(escaped_x, escaped_z)
    assert z_return.end == x_return.start == Point2(escaped_x, start_z)
    assert x_return.end == Point2(stock_x, start_z)
    if retract:
        assert motions[-3].start == profile[-1].end
        assert motions[-3].end == z_return.start


def test_user_o0339_final_return_stays_clear_of_contour():
    source = """%
O0339(BASIC TURNING CYCLES)
G1901D300.E72.L227.K2.
N1T0909(OD ROUGH R0.8)
G50S500
G96S200M3
G0X305.Z2.
M8
G72W2.5R0.2
G72P11Q12W0.2F0.25
N11G0Z-224.7
G1X299.8
Z-222.9C1.8
N12X214.
G0Z2.
X218.
G72W2.5R0.1
G72P13Q14W0.1F0.25
N13G0Z0.
N14G1X65.
G0X214.Z1.
G71U2.5R0.2
G71P15Q16U0.2W0.1F0.25
N15G0X103.91
G1Z0.
X106.91C1.5
Z-33.1
X109.83A-30R1.8
Z-45.58
X123.81C1.
Z-48.55
X209.8C1.5
Z-222.9R2.
X299.8C1.8
N16Z-224.7
G0Z100.
M9
G28U0.W0.
M01
M30
"""
    result = execute(source, language="fanuc_turn")
    assert result.ok and result.complete, result.diagnostics
    cycle_block = next(block.index for block in result.program.blocks if block.raw.startswith("G71P"))
    motions = [motion for motion in result.motions if motion.source_block == cycle_block]
    assert len(motions) >= 3
    retract, axial, radial = motions[-3], motions[-2], motions[-1]
    assert retract.end_x - retract.start_x == pytest.approx(0.4)
    assert retract.end_z - retract.start_z == pytest.approx(0.2)
    assert axial.start_x == axial.end_x == retract.end_x
    assert axial.end_z == radial.start_z == radial.end_z == 1
    assert radial.end_x == 214
    assert not any(m.move == 0 and m.end_x == 214 and m.end_z < 0 for m in motions[-3:])
