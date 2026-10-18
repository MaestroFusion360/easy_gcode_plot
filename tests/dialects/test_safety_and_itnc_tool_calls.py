"""Safety-block cancellation and native cycle tool-call geometry regressions."""

import copy
import math
from dataclasses import replace

import pytest

from app.gcode.kernel import execute


@pytest.mark.parametrize("codes", ["G0 G80", "G80 G0", "G1 G80", "G80 G1"])
@pytest.mark.parametrize("active", [False, True])
def test_explicit_move_and_cycle_cancel_are_order_independent(codes, active):
    cycle = "G99 G81 X0 Z-5 R2 F100\n" if active else ""
    result = execute(f"G90 G0 Z10\n{cycle}{codes} X10 Z8 F200\nX20\nM30", "fanuc_mill")
    assert result.ok and result.complete, result.diagnostics
    assert not result.diagnostics
    assert [(m.end_x, m.end_z) for m in result.motions[-2:]] == [(10, 8), (20, 8)]
    expected_move = 0 if "G0" in codes else 1
    assert [m.move for m in result.motions[-2:]] == [expected_move, expected_move]
    assert not any(m.cycle_generated for m in result.motions[-2:])


@pytest.mark.parametrize("codes", ["G0 G1 G80", "G80 G81", "G0 G81 G80"])
def test_real_motion_conflicts_remain_errors(codes):
    result = execute(f"G0 Z10\n{codes} X99\nM30", "fanuc_mill")
    assert not result.ok
    assert any(d.code == "MODAL_GROUP_CONFLICT" for d in result.diagnostics)
    assert all(m.end_x != 99 for m in result.motions)


def pocket_definition(finishing=False):
    values = {
        200: 2,
        201: -4,
        202: 4,
        203: 0,
        204: 10,
        206: 100,
        207: 300,
        215: 2 if finishing else 1,
        223: 40,
        338: 0,
        351: 1,
        366: 1,
        368: 0,
        369: 0,
        370: 1,
        385: 300,
    }
    return "CYCL DEF 252 POCKET\n" + "\n".join(f"Q{key}={value}" for key, value in values.items())


def native(source, tools=None, **options):
    return execute(source, "fanuc_mill", source_dialect="heidenhain", milling_tools=tools, **options)


def test_default_plunge_angle_matches_explicit_three_degrees():
    source = "TOOL CALL 1 Z S1000\nL Z10 R0 FMAX M3\n" + pocket_definition() + "\nCYCL CALL\nM30"
    tools = {"T1": {"type": "mill_flat", "diameter": 10}}
    assumed = native(source, tools)
    explicit = native(source, {"T1": {**tools["T1"], "ANGLE": 3}})
    assert assumed.ok and explicit.ok, (assumed.diagnostics, explicit.diagnostics)
    assert assumed.motions == explicit.motions
    assert [d.code for d in assumed.diagnostics] == ["HEIDENHAIN_DEFAULT_PLUNGE_ANGLE"]
    assert not explicit.diagnostics


@pytest.mark.parametrize("delta", [0.5, -0.5])
@pytest.mark.parametrize("scale", [1.0, 25.4])
def test_dr_changes_cycle_radius_without_mutating_tools(delta, scale):
    source = (
        f"TOOL CALL 1 Z S1000 DL+0.5 DR{delta:+}\nL Z10 R0 FMAX M3\n"
        "CYCL DEF 208 BORE\nQ200=2\nQ201=-4\nQ206=100\nQ334=2\n"
        "Q203=0\nQ204=10\nQ335=40\nQ342=0\nCYCL CALL\nM30"
    )
    tools = {"T1": {"type": "mill_flat", "diameter": 10 * scale}}
    original = copy.deepcopy(tools)
    result = native(source, tools, default_unit_scale=scale)
    assert result.ok and result.complete, result.diagnostics
    assert tools == original
    arcs = [m for m in result.motions if m.move in (2, 3)]
    assert arcs
    assert all(math.hypot(m.start_x, m.start_y) == pytest.approx((15 - delta) * scale) for m in arcs)
    assert {d.code for d in result.diagnostics} == {
        "HEIDENHAIN_TOOL_RADIUS_DELTA",
        "HEIDENHAIN_TOOL_LENGTH_DELTA_IGNORED",
    }


def test_pocket_dr_is_call_local_and_does_not_accumulate():
    setup = "TOOL CALL 1 Z S1000 DR+0.5\nL Z10 R0 FMAX M3\n"
    body = pocket_definition() + "\nCYCL CALL\n"
    source = setup + body + "TOOL CALL 1 Z\nCYCL CALL\nM30"
    tools = {"T1": {"type": "mill_flat", "diameter": 10, "ANGLE": 3}}
    result = native(source, tools)
    effective = native(setup.replace(" DR+0.5", "") + body + "M30", {"T1": {**tools["T1"], "diameter": 11}})
    base = native(setup.replace(" DR+0.5", "") + body + "M30", tools)
    assert result.ok and effective.ok and base.ok, result.diagnostics
    first = [m for m in result.motions if m.source_kind == "cycle"]
    expected = [m for r in (effective, base) for m in r.motions if m.source_kind == "cycle"]

    def geometry(m):
        return replace(m, source_block=None, source_raw=None, source_nlabel=None)

    assert [geometry(m) for m in first] == [geometry(m) for m in expected]


@pytest.mark.parametrize("angle", [0, -1, 90, float("nan")])
def test_explicit_invalid_plunge_angle_is_not_replaced_by_default(angle):
    source = "TOOL CALL 1 Z\nL Z10 R0 FMAX M3\n" + pocket_definition() + "\nCYCL CALL\nM30"
    result = native(source, {"T1": {"type": "mill_flat", "diameter": 10, "ANGLE": angle}})
    assert not result.ok
    assert result.diagnostics[-1].code == "INVALID_HEIDENHAIN_POCKET"


def test_dl_keeps_nominal_tip_path_and_reports_warning():
    result = native("TOOL CALL 1 Z DL+0.5\nL X2 Z5 F100\nM30")
    assert result.ok and result.motions[-1].end_z == 5
    assert [d.code for d in result.diagnostics] == ["HEIDENHAIN_TOOL_LENGTH_DELTA_IGNORED"]


def test_finishing_without_allowance_is_explicit_no_cut():
    source = "TOOL CALL 1 Z\nL Z10 R0 FMAX M3\n" + pocket_definition(True) + "\nCYCL CALL\nM30"
    result = native(source, {"T1": {"type": "mill_flat", "diameter": 10}})
    assert result.ok and result.complete, result.diagnostics
    assert all(m.move == 0 for m in result.motions)
    assert [d.code for d in result.diagnostics] == ["HEIDENHAIN_POCKET_NO_FINISHING_ALLOWANCE"]
