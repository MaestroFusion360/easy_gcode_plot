"""Optional rotary limits warn without changing execution or export contracts."""

from dataclasses import replace

import pytest

from app.gcode.export import ExportOptions, convert_resolved_program
from app.gcode.export.common import is_export_limitation
from app.gcode.kernel import execute
from app.gcode.kernel.milling.kinematics import (
    InvalidKinematicsProfile,
    kinematics_snapshot,
    load_catalog,
    parse_catalog,
    profile_document,
    profile_from_snapshot,
    rotary_limit_violations,
    save_profile_override,
)


def _limited(profile_id, minimum=-5, maximum=5):
    profile = load_catalog()[profile_id]
    return replace(
        profile,
        table_rotary_axes=tuple(
            replace(joint, minimum=minimum, maximum=maximum) for joint in profile.table_rotary_axes
        ),
        head_rotary_axes=tuple(replace(joint, minimum=minimum, maximum=maximum) for joint in profile.head_rotary_axes),
    )


@pytest.mark.parametrize(
    "limits",
    [
        {"min": 0},
        {"max": 1},
        {"min": 2, "max": 1},
        {"min": float("inf"), "max": 2},
        {"min": 0, "max": float("nan")},
        {"min": True, "max": 2},
        {"min": "0", "max": 2},
        {"min": None, "max": None},
    ],
)
def test_invalid_limits_are_rejected(limits):
    item = profile_document("4ax_table_a")
    item["table"][0].update(limits)
    with pytest.raises(InvalidKinematicsProfile):
        parse_catalog({"schema_version": 1, "profiles": [item]})


def test_limits_round_trip_legacy_and_snapshot():
    item = profile_document("4ax_table_a")
    item["id"] = "user_limits"
    save_profile_override(item["id"], item)
    original = load_catalog()[item["id"]]
    assert original.table_rotary_axes[0].minimum is None
    item["table"][0].update(min=-10, max=10)
    save_profile_override(item["id"], item)
    limited = load_catalog()[item["id"]]
    definition, fingerprint = kinematics_snapshot(limited)
    assert fingerprint != kinematics_snapshot(original)[1]
    assert profile_from_snapshot(definition) == limited
    assert rotary_limit_violations(limited, {"A": 10}) == ()
    assert rotary_limit_violations(limited, {"A": 370}) == (("A", 370, -10, 10),)
    assert all(
        joint.minimum is None
        for profile in load_catalog().values()
        if profile.id != item["id"]
        for joint in profile.table_rotary_axes + profile.head_rotary_axes
    )


@pytest.mark.parametrize("address", "ABC")
@pytest.mark.parametrize("branch", ["table", "head"])
def test_indexed_absolute_incremental_limits_warn_only_on_change(address, branch):
    profile_id = f"4ax_{branch}_{address.lower()}"
    source = f"G90 G0 {address}5\nG91 G0 {address}1\nG0 X2\nG0 {address}0\nM30"
    baseline = execute(source, language="fanuc_mill", kinematics=profile_id)
    result = execute(source, language="fanuc_mill", kinematics=_limited(profile_id))
    assert result.ok and result.complete and result.motions, result.diagnostics
    assert result.motions == baseline.motions
    warnings = [d for d in result.diagnostics if d.code == "ROTARY_AXIS_LIMIT_EXCEEDED"]
    assert len(warnings) == 1
    warning = warnings[0]
    profile = load_catalog()[profile_id]
    assert profile.name in warning.message
    assert profile.id not in warning.message
    assert (warning.line, warning.raw, warning.severity, warning.status) == (
        2,
        source.splitlines()[1],
        "warning",
        "unverified",
    )
    assert not is_export_limitation(warning)


@pytest.mark.parametrize(
    "profile_id,source,dialect,line,minimum,maximum",
    [
        ("5ax_table_ac", "G0 C=DC(30)\nG0 Z5\nM30", "sinumerik", 1, -5, 5),
        ("5ax_table_ac_angled", "G68.2 X0 Y0 Z0 I0 J-15 K0\nG53.1\nG0 Z5\nM30", "fanuc", 2, -5, 5),
        (
            "5ax_table_bc_angled",
            'CYCLE800(2,"TISCH",200000,57,0,0,50,-15,0,0,0,0,0,1,,1)\nG0 Z5\nM30',
            "sinumerik",
            1,
            -5,
            5,
        ),
        ("4ax_table_a", "G0 A15\nG28 A0\nG0 Z5\nM30", "fanuc", 2, 10, 20),
        ("4ax_table_b", "G0 B15\nG53 G0 B30\nG0 Z5\nM30", "fanuc", 2, 10, 20),
        ("4ax_table_b", "G0 B15\nG91\nG0 SUPA B30\nG90 G0 Z5\nM30", "sinumerik", 3, 10, 20),
        ("5ax_table_bc", "G0 Z10\nG43.4\nG1 B30 C20 F100\nG49\nM30", "fanuc", 3, -5, 5),
    ],
)
def test_all_rotary_state_paths_warn_without_geometry_changes(profile_id, source, dialect, line, minimum, maximum):
    baseline = execute(source, language="fanuc_mill", source_dialect=dialect, kinematics=profile_id)
    result = execute(
        source, language="fanuc_mill", source_dialect=dialect, kinematics=_limited(profile_id, minimum, maximum)
    )
    assert baseline.ok and result.ok and result.complete and result.motions, result.diagnostics
    assert result.motions == baseline.motions
    warnings = [d for d in result.diagnostics if d.code == "ROTARY_AXIS_LIMIT_EXCEEDED"]
    assert warnings and {d.line for d in warnings} == {line}
    assert all(d.severity == "warning" for d in warnings)
    within_limits = execute(
        source, language="fanuc_mill", source_dialect=dialect, kinematics=_limited(profile_id, -720, 720)
    )
    assert within_limits.ok and within_limits.complete
    assert within_limits.motions == baseline.motions
    assert not any(d.code == "ROTARY_AXIS_LIMIT_EXCEEDED" for d in within_limits.diagnostics)


def test_warning_does_not_block_expanded_tcp_export():
    source = "G0 Z10\nG43.4\nG1 B30 C20 F100\nG49\nM30"
    result = execute(source, language="fanuc_mill", kinematics=_limited("5ax_table_bc"))
    assert result.ok and any(d.code == "ROTARY_AXIS_LIMIT_EXCEEDED" for d in result.diagnostics)
    assert "G43.4" in convert_resolved_program(result, "fanuc_mill_multiaxis", ExportOptions())
