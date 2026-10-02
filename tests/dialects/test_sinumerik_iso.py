"""SINUMERIK ISO Dialect M compatibility and whitelist regression tests."""

import pytest

from app.gcode.kernel.api.engine import execute
from app.gcode.kernel.milling.sinumerik_iso import ISO_M_EXECUTABLE_G_CODES


def _iso(source: str):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik")


@pytest.mark.parametrize(
    ("iso_code", "fanuc_code", "unit_scale"),
    [("G20", "G20", 25.4), ("G70", "G20", 25.4), ("G21", "G21", 1.0), ("G71", "G21", 1.0)],
)
def test_iso_m_units_and_aliases_match_fanuc_mill_state(iso_code, fanuc_code, unit_scale):
    iso_result = _iso(f"G291\n{iso_code}\nG0 X1 Y0\nM30")
    fanuc_result = _iso(f"G291\n{fanuc_code}\nG0 X1 Y0\nM30")

    assert iso_result.ok and iso_result.complete, iso_result.diagnostics
    assert iso_result.execution_steps[-1].unit_scale == pytest.approx(unit_scale)
    assert iso_result.motions[-1].end_x == pytest.approx(unit_scale)
    assert [step.unit_scale for step in iso_result.execution_steps] == [
        step.unit_scale for step in fanuc_result.execution_steps
    ]


@pytest.mark.parametrize(
    "source",
    [
        "G291\nG58\nG0 X1 Y0\nG59\nG0 X2 Y0\nM30",
        "G291\nG90\nG68 X0 Y0 R90\nG0 X1 Y0\nG69\nM30",
        "G291\nG69\nM30",
        "G291\nG17 G90 G0 Z5\nG85 X0 Y0 Z-2 R1 F100\nG80\nM30",
        "G291\nG17 G90 G0 Z5\nG86 X0 Y0 Z-2 R1 F100\nG80\nM30",
    ],
)
def test_iso_m_commands_with_matching_kernel_semantics_execute(source):
    result = _iso(source)
    assert result.ok and result.complete, result.diagnostics


def test_iso_m_g91_incremental_positioning_applies_each_block_once():
    result = _iso("G291\nG90 G0 X10\nG91\nG1 X5 F100\nM30")

    assert result.ok and result.complete, result.diagnostics
    assert result.motions[-1].end_x == pytest.approx(15.0)


def test_iso_m_g58_g59_offsets_change_resolved_machine_position():
    result = execute(
        "G291\nG90\nG58\nG0 X1 Y0 Z0\nG59\nG0 X2 Y0 Z0\nM30",
        language="fanuc_mill",
        source_dialect="sinumerik",
        wcs_offsets={58: (10.0, 20.0, 30.0), 59: (100.0, 200.0, 300.0)},
    )

    assert result.ok and result.complete, result.diagnostics
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == pytest.approx(
        (102.0, 200.0, 300.0)
    )


def test_iso_m_g51_uses_modeled_thousandth_scale_weighting():
    result = _iso("G291\nG51 X0 Y0 P2000\nG1 X10\nM30")

    assert result.ok and result.complete, result.diagnostics
    assert result.motions[-1].end_x == pytest.approx(20.0)


@pytest.mark.parametrize(
    "source",
    [
        "G291\nG91\nG68 X0 Y0 R90\nM30",
        "G291\nG68 X0 Y0 R90 I1\nM30",
        "G291\nG68 X0 Y0 R90 J1\nM30",
        "G291\nG68 X0 Y0 R90 K1\nM30",
    ],
)
def test_iso_m_g68_rejects_incremental_and_3d_forms(source):
    result = _iso(source)

    assert not result.ok and not result.complete
    assert any(item.code == "UNSUPPORTED_SINUMERIK_ISO_G_CODE" for item in result.diagnostics)


@pytest.mark.parametrize("extra", ["Z5", "M3", "F100", "P123", "A10"])
def test_iso_m_g68_rejects_words_outside_the_modeled_xy_contract(extra):
    result = _iso(f"G291\nG90\nG68 X0 Y0 R90 {extra}\nM30")

    assert not result.ok and not result.complete
    expected = "UNSUPPORTED_SINUMERIK_ROTARY" if extra == "A10" else "INVALID_SINUMERIK_ISO_G68"
    assert any(item.code == expected for item in result.diagnostics)


def test_iso_m_g68_rotates_xy_motion_about_absolute_center():
    result = _iso("G291\nG90\nG0 X0 Y0\nG68 X0 Y0 R90\nG0 X1 Y0\nG69\nM30")

    assert result.ok and result.complete, result.diagnostics
    assert (result.motions[-1].end_x, result.motions[-1].end_y) == pytest.approx((0.0, 1.0))


def test_iso_m_g85_returns_to_r_plane_with_feed_motion():
    result = _iso("G291\nG17 G90 G0 Z5\nG85 X0 Y0 Z-2 R1 F100\nG80\nM30")

    assert result.ok and result.complete, result.diagnostics
    cycle_motions = [motion for motion in result.motions if motion.cycle_generated]
    assert [motion.move for motion in cycle_motions] == [0, 1, 1]
    assert [motion.end_z for motion in cycle_motions] == pytest.approx([1.0, -2.0, 1.0])


def test_iso_m_g86_emits_spindle_stop_signal():
    result = _iso("G291\nG17 G90 G0 Z5\nG86 X0 Y0 Z-2 R1 F100\nG80\nM30")

    assert result.ok and result.complete, result.diagnostics
    assert [(signal.kind, signal.code) for signal in result.signals if signal.code == "G86"] == [
        ("spindle_stop", "G86")
    ]
    assert any(motion.cycle_generated and motion.end_z == pytest.approx(-2.0) for motion in result.motions)


@pytest.mark.parametrize("p_number", [1, 48])
def test_iso_m_g54_p_extended_work_offsets_map_to_supported_range(p_number):
    result = execute(
        f"G291\nG90\nG54 P{p_number}\nG0 X1 Y2 Z3\nM30",
        language="fanuc_mill",
        source_dialect="sinumerik",
        wcs_offsets={1000 + p_number: (10.0, 20.0, 30.0)},
    )

    assert result.ok and result.complete, result.diagnostics
    assert result.execution_steps[-1].active_wcs == 1000 + p_number
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == pytest.approx(
        (11.0, 22.0, 33.0)
    )


@pytest.mark.parametrize("source", ["G291\nG54 P0\nM30", "G291\nG54 P49\nM30"])
def test_iso_m_g54_p_rejects_out_of_range_extended_work_offsets(source):
    result = _iso(source)
    assert not result.ok and not result.complete
    assert any(item.code == "INVALID_SINUMERIK_ISO_EXTENDED_WCS" for item in result.diagnostics)


@pytest.mark.parametrize(
    "source,offset_id,extended",
    [
        ("G291\nG10 L2 P1 X10 Y20 Z30\nM30", 54, False),
        ("G291\nG10 L20 P48 X10 Y20 Z30\nM30", 48, True),
    ],
)
def test_iso_m_g10_supported_work_offset_forms(source, offset_id, extended):
    result = _iso(source)
    assert result.ok and result.complete, result.diagnostics
    offsets = dict(result.extended_wcs_offsets if extended else result.wcs_offsets)
    assert offsets[offset_id] == pytest.approx((10.0, 20.0, 30.0))


@pytest.mark.parametrize(
    "gcode",
    [
        "G2.2",
        "G3.2",
        "G5.1",
        "G7.1",
        "G10.6",
        "G12.1",
        "G13.1",
        "G30.1",
        "G43.4",
        "G50.1",
        "G51.1",
        "G53.1",
        "G54.1",
        "G68.2",
        "G72.1",
        "G72.2",
        "G83.5",
        "G83.6",
        "G87.5",
        "G87.6",
        "G92.1",
        "G74",
        "G87",
        "G65",
    ],
)
def test_iso_m_non_whitelisted_g_codes_fail_closed(gcode):
    result = _iso(f"G291\n{gcode}\nM30")

    assert not result.ok and not result.complete
    assert any(item.code == "UNSUPPORTED_SINUMERIK_ISO_G_CODE" for item in result.diagnostics)


def test_iso_m_executable_whitelist_contains_only_integer_g_codes():
    assert ISO_M_EXECUTABLE_G_CODES
    assert all(isinstance(code, int) for code in ISO_M_EXECUTABLE_G_CODES)


@pytest.mark.parametrize(
    "source,kinematics",
    [
        (
            "G90 G0 X0 Y0 Z0 A0 C0\nG43.4 H1\nG1 X10 Y20 Z30 A30 C45 F100\nG49\nM30",
            "5ax_table_ac_angled",
        ),
        (
            "G0 X0 Y0 Z0\nG68.2 X0 Y0 Z-50 I0 J90 K0\nG53.1\nG0 X10 Y20 Z-5\nG69\nM30",
            "5ax_table_ac_angled",
        ),
        (
            "G0 X0 Y0 Z0\nG68.2 X0 Y0 Z-50 I0 J90 K0\nG0 X10 Y20 Z-5\nG69\nM30",
            "5ax_table_ac_angled",
        ),
    ],
)
def test_fanuc_multiaxis_codes_remain_available_without_g291(source, kinematics):
    result = execute(source, language="fanuc_mill", kinematics=kinematics)
    assert result.ok and result.complete, result.diagnostics
