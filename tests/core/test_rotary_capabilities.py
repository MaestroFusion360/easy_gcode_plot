"""Profile geometry, rather than IDs, controls all rotary trace consumers."""

import json
from dataclasses import replace

import pytest

from app.gcode.export import ExportOptions, convert_resolved_program
from app.gcode.export.preflight import _has_unreconstructable_non_tcp_rotary_motion
from app.gcode.export.service import ExportRequest, export_file
from app.gcode.kernel import execute
from app.gcode.kernel.milling.kinematics import (
    CATALOG_PATH,
    RotaryAxis,
    effective_orientation,
    load_catalog,
    point_orientation,
    profile_document,
    save_profile_override,
)

_BUILTIN_ITEMS = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["profiles"]
_BUILTIN_IDS = tuple(item["id"] for item in _BUILTIN_ITEMS)
_ORDERED_BRANCH_IDS = tuple(
    item["id"] for item in _BUILTIN_ITEMS if any(len(item[key]) == 2 for key in ("table", "head"))
)


def _indexed_source(item, angles):
    joints = item["table"] + item["head"]
    words = " ".join(f"{joint['address']}{angles[joint['address']]}" for joint in joints)
    return f"G90 G0 {words}\nG0 X7 Y11 Z13\nM30"


def _pose(result):
    assert result.ok and result.complete, result.diagnostics
    motion = result.motions[-1]
    return (motion.end_x, motion.end_y, motion.end_z), motion.tool_orientation


@pytest.mark.parametrize("profile_id", _BUILTIN_IDS)
def test_every_profile_uses_persisted_signed_vectors_in_kernel(profile_id):
    original = profile_document(profile_id)
    joints = original["table"] + original["head"]
    angles = {joint["address"]: 17 + 14 * index for index, joint in enumerate(joints)}
    source = _indexed_source(original, angles)
    baseline_point, baseline_orientation = _pose(execute(source, language="fanuc_mill", kinematics=profile_id))
    for branch in ("table", "head"):
        for index, joint in enumerate(original[branch]):
            edited = profile_document(profile_id)
            edited["id"] = f"user_{profile_id}_{branch}_{index}"
            edited[branch][index]["axis"] = [-value for value in joint["axis"]]
            save_profile_override(edited["id"], edited)
            changed = execute(source, language="fanuc_mill", kinematics=edited["id"])
            inverse_angles = dict(angles)
            inverse_angles[joint["address"]] *= -1
            expected = execute(_indexed_source(original, inverse_angles), language="fanuc_mill", kinematics=profile_id)
            changed_point, changed_orientation = _pose(changed)
            expected_point, expected_orientation = _pose(expected)
            assert changed_point == pytest.approx(expected_point)
            for actual_row, expected_row in zip(changed_orientation, expected_orientation, strict=True):
                assert actual_row == pytest.approx(expected_row)
            assert changed_orientation != baseline_orientation
            if branch == "table":
                assert changed_point != pytest.approx(baseline_point)
            else:
                assert changed_point == pytest.approx(baseline_point)


@pytest.mark.parametrize("profile_id", _ORDERED_BRANCH_IDS)
def test_every_two_joint_branch_uses_persisted_rotation_order(profile_id):
    item = profile_document(profile_id)
    branch = next(key for key in ("table", "head") if len(item[key]) == 2)
    angles = {joint["address"]: 27 + 16 * index for index, joint in enumerate(item[branch])}
    source = _indexed_source(item, angles)
    baseline_point, baseline_orientation = _pose(execute(source, language="fanuc_mill", kinematics=profile_id))
    item["id"] = "user_reordered_" + profile_id
    item[branch].reverse()
    save_profile_override(item["id"], item)
    point, orientation = _pose(execute(source, language="fanuc_mill", kinematics=item["id"]))
    assert orientation != baseline_orientation
    if branch == "table":
        assert point != pytest.approx(baseline_point)
    else:
        assert point == pytest.approx(baseline_point)


@pytest.mark.parametrize("profile_id", _BUILTIN_IDS)
def test_catalog_tcp_support_is_explicit_and_does_not_accept_head_or_mixed_layouts(profile_id):
    supported = {"5ax_table_ac", "5ax_table_bc", "5ax_table_ac_angled", "5ax_table_bc_angled"}
    item = profile_document(profile_id)
    angles = {joint["address"]: 17 + 14 * index for index, joint in enumerate(item["table"] + item["head"])}
    words = " ".join(f"{address}{angle}" for address, angle in angles.items())
    source = f"G0 Z10\nG43.4\nG1 X5 {words} F100\nG49\nM30"
    result = execute(source, language="fanuc_mill", kinematics=profile_id)
    if profile_id in supported:
        point, _ = _pose(result)
        assert point == pytest.approx((5, 0, 10))
    else:
        assert not result.ok
        assert result.diagnostics[-1].code == "TCP_KINEMATICS_REQUIRED"


@pytest.mark.parametrize("profile_id", ["5ax_table_ac", "5ax_table_bc", "5ax_table_ac_angled", "5ax_table_bc_angled"])
def test_user_copy_preserves_tcp_and_expanded_export(profile_id):
    profile = replace(load_catalog()[profile_id], id="user_copy", enabled=True)
    source = "G90 G0 Z10\nG43.4\nG1 X5 A10 B10 C20 F300\nG49\nM30"
    tilt = profile.table_rotary_axes[0].address
    source = source.replace("A10 B10", tilt + "10")
    baseline = execute(source, language="fanuc_mill", kinematics=load_catalog()[profile_id])
    copied = execute(source, language="fanuc_mill", kinematics=profile)
    assert baseline.ok and copied.ok, copied.diagnostics
    assert copied.motions == baseline.motions
    text = convert_resolved_program(copied, "fanuc_mill_multiaxis", ExportOptions())
    replay = execute(text, language="fanuc_mill", kinematics=profile)
    assert replay.ok and replay.complete, replay.diagnostics
    assert replay.motions[-1].end_x == pytest.approx(copied.motions[-1].end_x)


@pytest.mark.parametrize("change", ["order", "spin_direction", "head", "parallel"])
def test_tcp_checks_geometry_and_order(change):
    profile = load_catalog()["5ax_table_bc"]
    tilt, spin = profile.table_rotary_axes
    if change == "order":
        profile = replace(profile, table_rotary_axes=(spin, tilt))
    elif change == "spin_direction":
        profile = replace(profile, table_rotary_axes=(tilt, RotaryAxis("C", (1, 0, 0))))
    elif change == "head":
        profile = replace(profile, table_rotary_axes=(spin,), head_rotary_axes=(tilt,))
    else:
        profile = replace(profile, table_rotary_axes=(RotaryAxis("B", (0, 0, 1)), spin))
    assert not profile.tcp_table_supported
    result = execute("G43.4\nM30", language="fanuc_mill", kinematics=profile)
    assert not result.ok
    assert result.diagnostics[-1].code == "TCP_KINEMATICS_REQUIRED"


def test_reordering_user_joints_changes_composition_in_execution():
    profile = load_catalog()["5ax_table_bc"]
    reversed_profile = replace(profile, id="user_reverse", table_rotary_axes=profile.table_rotary_axes[::-1])
    source = "G90 G0 B40 C70\nG0 Z10\nM30"
    before = execute(source, language="fanuc_mill", kinematics=profile)
    after = execute(source, language="fanuc_mill", kinematics=reversed_profile)
    assert before.ok and after.ok, after.diagnostics
    assert before.motions[-1].end_x != pytest.approx(after.motions[-1].end_x)
    expected = point_orientation(reversed_profile, {"B": 40, "C": 70})
    assert after.motions[-1].end_x == pytest.approx(10 * expected[0][2])
    assert after.motions[-1].tool_orientation == effective_orientation(reversed_profile, {"B": 40, "C": 70})


@pytest.mark.parametrize("sign", [1, -1])
def test_signed_vertical_c_copy_reaches_compensation_and_export(sign):
    profile = replace(load_catalog()["4ax_table_c"], id="user_c", table_rotary_axes=(RotaryAxis("C", (0, 0, sign)),))
    result = execute("G90 G0 X10\nG1 C90 F100\nM30", language="fanuc_mill", kinematics=profile)
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_y == pytest.approx(10 * sign)
    assert not _has_unreconstructable_non_tcp_rotary_motion(result)
    text = convert_resolved_program(result, "fanuc_mill_multiaxis", ExportOptions())
    replay = execute(text, language="fanuc_mill", kinematics=profile)
    assert replay.ok, replay.diagnostics
    assert replay.motions[-1].end_y == pytest.approx(10 * sign)
    compensated = execute("G0 X10\nG41 D1 G1 C90 F100\nM30", language="fanuc_mill", kinematics=profile)
    assert any(d.code == "UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION" for d in compensated.diagnostics)
    tilted = replace(profile, table_rotary_axes=(RotaryAxis("C", (0, 1, 0)),))
    assert not tilted.continuous_c_table


def test_export_uses_executed_snapshot_after_user_profile_is_edited():
    item = profile_document("5ax_table_bc")
    item["id"] = "user_tcp"
    save_profile_override(item["id"], item)
    result = execute("G0 Z10\nG43.4\nG1 B30 C20 F100\nG49\nM30", language="fanuc_mill", kinematics=item["id"])
    assert result.ok, result.diagnostics
    item["table"].reverse()
    save_profile_override(item["id"], item)
    assert not load_catalog()[item["id"]].tcp_table_supported
    assert "G43.4" in convert_resolved_program(result, "fanuc_mill_multiaxis", ExportOptions())


def test_head_vector_changes_tool_orientation_without_rotating_workpiece_points():
    profile = load_catalog()["4ax_head_b"]
    reversed_profile = replace(profile, id="user_head", head_rotary_axes=(RotaryAxis("B", (0, -1, 0)),))
    source = "G90 G0 B90\nG0 Z10\nM30"
    before = execute(source, language="fanuc_mill", kinematics=profile)
    after = execute(source, language="fanuc_mill", kinematics=reversed_profile)
    assert before.ok and after.ok
    assert after.motions[-1].end_z == before.motions[-1].end_z == 10
    assert after.motions[-1].tool_orientation[0][2] == pytest.approx(-before.motions[-1].tool_orientation[0][2])


@pytest.mark.parametrize("profile_id", ["5ax_table_ac_angled", "5ax_table_bc_angled"])
def test_native_swivel_and_traori_accept_user_copies(profile_id):
    profile = replace(load_catalog()[profile_id], id="user_native")
    tilt = profile.table_rotary_axes[0].address
    source = (
        'CYCLE800(2,"TISCH",200000,57,0,0,50,-15,0,0,0,0,0,1,,1)\n'
        "G0 X1 Y2 Z3\nCYCLE800()\nTRAORI\n"
        f"G1 X5 {tilt}=10 C=20 F300\nTRAFOOF\nM30"
    )
    before = execute(source, language="fanuc_mill", source_dialect="sinumerik", kinematics=load_catalog()[profile_id])
    after = execute(source, language="fanuc_mill", source_dialect="sinumerik", kinematics=profile)
    assert before.ok and after.ok, after.diagnostics
    assert before.motions == after.motions
    assert {event.kind for event in after.events} >= {"TILTED_WORK_PLANE_ON", "TCP_CONTROL_ON"}
    text = convert_resolved_program(after, "sinumerik_840d_multiaxis", ExportOptions())
    replay = execute(text, language="fanuc_mill", source_dialect="sinumerik", kinematics=profile)
    assert replay.ok and replay.complete, replay.diagnostics


def test_dmg_frame_only_accepts_matching_geometry_with_any_id():
    profile = replace(load_catalog()["5ax_table_bc_angled"], id="user_dmg")
    source = 'CYCLE800(0,"DMG",220000,57,0,0,0,0,0,0,0,0,0,0,,1)\nG0 Z5\nM30'
    result = execute(source, language="fanuc_mill", source_dialect="sinumerik", kinematics=profile)
    assert result.ok and result.complete, result.diagnostics
    tilt, spin = profile.table_rotary_axes
    wrong = replace(profile, table_rotary_axes=(replace(tilt, axis=(0, 1, 0)), spin))
    rejected = execute(source, language="fanuc_mill", source_dialect="sinumerik", kinematics=wrong)
    assert not rejected.ok
    assert rejected.diagnostics[-1].code == "UNSUPPORTED_SINUMERIK_CYCLE800"


def test_user_copy_twp_passes_export_service_preflight(tmp_path):
    item = profile_document("5ax_table_ac_angled")
    item["id"] = "user_twp"
    save_profile_override(item["id"], item)
    source = tmp_path / "source.nc"
    source.write_text("G68.2 X0 Y0 Z0 I0 J-15 K0\nG53.1\nG0 Z5\nG1 X10 F100\nG69\nM30", encoding="utf-8")
    target = tmp_path / "target.nc"
    exported = export_file(source, target, ExportRequest("fanuc_mill", "fanuc_mill_multiaxis", kinematics=item["id"]))
    assert exported.execution.ok and exported.output_size_bytes > 0, exported.execution.diagnostics
    replay = execute(target.read_text(encoding="utf-8"), language="fanuc_mill", kinematics=item["id"])
    assert replay.ok and replay.complete, replay.diagnostics
