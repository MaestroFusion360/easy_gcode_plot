"""Native turning dimensions, mode boundaries and independent cycle goldens."""

import math
from pathlib import Path

import pytest

from app.gcode.execution.source import language_for_path
from app.gcode.kernel import execute
from app.gcode.kernel.api.resources import ExecutionLimits
from app.gcode.kernel.frontend.sinumerik_turning import parse_sinumerik_turning_program
from app.tools.discovery import discover_tools

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/turning/sinumerik"


def native(source, **options):
    return execute(source, language="fanuc_turn", source_dialect="sinumerik", **options)


def clean(source, **options):
    result = native(source, **options)
    assert result.ok and result.complete, result.diagnostics
    return result


@pytest.mark.parametrize("name", ["sample_cycles.mpf", "sample_no_cycles.mpf"])
def test_cam_program_executes_with_original_source_ownership(name):
    path = FIXTURES / name
    source = path.read_text()
    result = clean(source)
    assert result.program_end == "M30"
    assert language_for_path(path) == "fanuc_turn"
    assert result.source_dialect == "sinumerik"
    assert result.motions and any(m.threading for m in result.motions)
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)
    for motion in result.motions:
        assert motion.source_raw == source.splitlines()[motion.source_block]
        assert motion.x_scale == 0.5
        if motion.threading:
            assert motion.feed_mode == "per_revolution" and motion.feed == 1


@pytest.mark.parametrize("mode, expected", [("DIAMON", 24), ("DIAMOF", 48), ("DIAM90", 28)])
def test_diameter_modes_absolute_and_incremental(mode, expected):
    result = clean(f"{mode}\nG0 X20 Z0\nG1 X=IC(4) Z-1 F100")
    assert result.motions[-1].end_x == expected


def test_native_g71_is_metric_and_g70_does_not_scale_feed():
    result = clean("G71 G18 G90\nG0 X20\nG70\nG1 X1 Z-1 F2\nG710\nG1 Z-30 F2")
    assert result.motions[1].end_x == 25.4
    assert result.motions[1].end_z == -25.4
    assert result.motions[1].feed == result.motions[2].feed == 2
    assert clean("G700\nG1 X1 F2").motions[0].feed == 50.8


@pytest.mark.parametrize("legacy_arc_type", [1, 2, 3])
def test_frame_x_and_arc_i_are_radii_even_in_diameter_mode(legacy_arc_type):
    result = clean("DIAMON\nTRANS X5 Z3\nG0 X20 Z0\nG3 X0 Z-10 I-10 K0 F100", source_arc_type=legacy_arc_type)
    arc = result.motions[-1].arc
    assert arc.radius == pytest.approx(10)
    assert arc.center == pytest.approx((5, 0, 3))
    assert result.motions[-1].end_x == 10


@pytest.mark.parametrize("system, feed_mode", [("A", "G99"), ("B", "G95")])
def test_native_iso_switch_preserves_tool_position_and_wcs(system, feed_mode):
    result = clean(
        f"DIAMON\nT1 D1\nG55 G0 X20 Z2\nG291\n{feed_mode}\nG1 Z-5 F0.2\nG290\nG71\nG1 X18",
        lathe_gcode_system=system,
        wcs_offsets={55: (10, 4)},
    )
    assert result.motions[-1].end_x == 28
    assert result.motions[-1].end_z == -1
    assert all(m.tool == "T0001" for m in result.motions)
    assert [e.code for e in result.events if e.kind == "source_mode_change"] == ["G291", "G290"]


@pytest.mark.parametrize("bad", ["G291 G0 X5", "G291\nDIAMON", "G291\nG71 U2", "G290\nG65 P1"])
def test_unsupported_mode_semantics_keep_valid_prefix(bad):
    result = native("G0 X20\n" + bad)
    assert not result.ok and not result.complete
    assert len(result.motions) == 1 and result.motions[0].end_x == 20
    assert result.diagnostics[0].line >= 2


def test_css_limit_and_g97_freeze_current_rpm():
    result = clean("G0 X20\nLIMS=1000\nG96 S150 M3\nG97\nG1 X10 F100")
    assert result.motions[-1].spindle_rpm == 1000
    assert result.motions[-1].spindle_mode == "rpm"


def thread_program(variant=1, idle=0):
    return f"G18 G95\nT3 D1\nG97 S500 M3\nG0 X24 Z2\nCYCLE97(1,,0,-10,20,20,0,0,2,0,0,0,4,{idle},{variant},1)\nM30"


@pytest.mark.parametrize("variant, depths", [(1, [0.5, 1, 1.5, 2]), (3, [1, 2**0.5, 3**0.5, 2])])
def test_cycle97_independent_radial_infeed_golden(variant, depths):
    result = clean(thread_program(variant, idle=1))
    cuts = [m for m in result.motions if m.threading]
    assert [m.end_x for m in cuts] == pytest.approx([20 - 2 * d for d in depths] + [16])
    assert all(m.start_z == 0 and m.end_z == -10 and m.feed == 1 for m in cuts)
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == (24, 2)


def rough_program(reference='"START:END"'):
    return (
        f"G18 G95\nG0 X30 Z2\nCYCLE95({reference},2,0,0,0,0.2,0.1,0.1,1,0,0,1)\n"
        "M30\nSTART:\nG0 X20 Z0\nG1 Z-10\nX24\nZ-20\nEND:"
    )


def test_cycle95_local_contour_after_m30_does_not_run_as_main_program():
    result = clean(rough_program())
    cuts = [
        m
        for m in result.motions
        if m.source_kind == "cycle" and m.move == 1 and m.start_x == m.end_x and m.start_z == 0
    ]
    assert [m.end_x for m in cuts] == pytest.approx([30 - 10 / 3, 30 - 20 / 3, 20])
    assert [m.end_z for m in cuts] == [-20, -10, -10]
    assert result.motions[-1].end_z == 2 and result.motions[-1].end_x == 30
    assert all(m.source_block <= 2 for m in result.motions)


@pytest.mark.parametrize("reference", ['"MISSING:END"', '"END:START"', '"other.spf"'])
def test_invalid_contour_reference_is_not_silently_skipped(reference):
    result = native(rough_program(reference))
    assert not result.ok and len(result.motions) == 1


@pytest.mark.parametrize("variant", range(1, 9))
def test_cycle93_rectangular_variants_have_expected_depth_and_width(variant):
    longitudinal = variant % 2
    angle = 0 if longitudinal else 90
    source = f"T2 D1\nG0 X30 Z2\nG95 F0.1\nCYCLE93(20,0,6,2,{angle},0,0,0,0,0,0,0,0,1,0,{variant},1)"
    result = clean(source, tools={"T0002": {"type": "groove", "width": 2, "noseRadius": 0}})
    cuts = [m for m in result.motions if m.source_kind == "cycle" and m.move == 1]
    width_sign = (1 if variant in {1, 3} else -1) if longitudinal else (1 if variant in {4, 8} else -1)
    depth_sign = (-1 if variant in {1, 5} else 1) if longitudinal else (1 if variant in {2, 4} else -1)
    assert (cuts[-2].end_x, cuts[-2].end_z) == (
        20 + (4 * depth_sign if longitudinal else 8 * width_sign),
        4 * width_sign if longitudinal else 2 * depth_sign,
    )
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == (30, 2)


def test_cycle_budget_and_cancellation_are_enforced():
    result = native(thread_program(), limits=ExecutionLimits(cycle_iterations=2))
    assert not result.ok and result.diagnostics[-1].code == "RESOURCE_LIMIT"
    assert not native(thread_program(), cancelled=lambda: True).ok


def test_ast_is_reused_for_tool_discovery_and_execution():
    source = (FIXTURES / "sample_cycles.mpf").read_text()
    program = parse_sinumerik_turning_program(source)
    tools = discover_tools(source, turning=True, source_dialect="sinumerik", program=program)
    result = clean(source, parsed_program=program, tools=tools)
    assert result.program is program
    assert tools["T0003"]["type"] == "thread"
    assert tools["T0005"]["type"] == "drill"


def test_common_cam_turning_cycles_agree_between_supplied_files():
    results = [clean(path.read_text()) for path in sorted(FIXTURES.glob("*.mpf"))]

    def geometry(result):
        return [
            (m.move, m.start_x, m.start_z, m.end_x, m.end_z, m.feed, m.threading)
            for m in result.motions
            if "CYCLE95(" in m.source_raw or "CYCLE97(" in m.source_raw
        ]

    assert geometry(results[0]) and geometry(results[0]) == geometry(results[1])


def test_cli_selects_native_turning_from_mpf(tmp_path, capsys):
    from app.cli import main  # pylint: disable=import-outside-toplevel

    output = tmp_path / "turning.html"
    assert main(["analyze", str(FIXTURES / "sample_cycles.mpf"), "--html", str(output)]) == 0
    assert "UNSUPPORTED_SINUMERIK" not in capsys.readouterr().out
    assert output.exists()


def test_numeric_contour_bounds_include_endpoint_motion_blocks():
    named = rough_program()
    numeric = (
        named.replace('"START:END"', '"N100:N130"')
        .replace("START:\nG0", "N100 G0")
        .replace("G1 Z-10", "N110 G1 Z-10")
        .replace("\nX24", "\nN120 X24")
        .replace("Z-20\nEND:", "N130 G1 Z-20")
    )
    before, after = clean(named), clean(numeric)
    assert [(m.end_x, m.end_z) for m in before.motions] == [(m.end_x, m.end_z) for m in after.motions]


def test_contour_start_at_current_position_still_defines_first_point():
    source = (
        rough_program()
        .replace("G0 X30 Z2", "G0 X30 Z0")
        .replace("G0 X20 Z0", "G0 X30 Z0")
        .replace("G1 Z-10", "G1 X20 Z-10")
    )
    assert clean(source).program_end == "M30"


def test_native_full_export_is_rejected_before_rewriting_source(tmp_path):
    from app.gcode.export.service import ExportRequest, export_file  # pylint: disable=import-outside-toplevel

    output = tmp_path / "normalized.mpf"
    result = export_file(FIXTURES / "sample_no_cycles.mpf", output, ExportRequest(language="fanuc_turn", mode="full"))
    assert not result.execution.ok and not output.exists()
    assert result.execution.diagnostics[-1].code == "UNSUPPORTED_SINUMERIK_TURNING_FULL_EXPORT"


@pytest.mark.parametrize("variant", range(1, 13))
def test_cycle95_longitudinal_facing_internal_and_finishing_variants(variant):
    base = (variant - 1) % 4 + 1
    internal, facing = base in {3, 4}, base in {2, 4}
    if facing:
        origin = (30, -8 if internal else 4)
        contour = "G0 X30 Z-4\nG1 X20\nZ-2\nX10"
    else:
        origin = (10 if internal else 30, 2)
        contour = "G0 X20 Z0\nG1 Z-10\nX24\nZ-20"
    source = (
        f'G0 X{origin[0]} Z{origin[1]}\nCYCLE95("START:END",2,0,0,0,0.2,0.1,0.1,{variant},0,0,1)\n'
        f"M30\nSTART:\n{contour}\nEND:"
    )
    result = clean(source)
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == origin
    if variant >= 5:
        endpoint = (10, -2) if facing else (24, -20)
        assert any(m.move == 1 and (m.end_x, m.end_z) == endpoint and m.feed == 0.1 for m in result.motions)


@pytest.mark.parametrize("variant, expected", [(1, (18.8, 13.6)), (2, (22.8, 17.6))])
def test_cycle97_taper_extends_pitch_path_through_approach_and_runout(variant, expected):
    source = f"G97 S500 M3\nG0 X30 Z5\nCYCLE97(1,,0,-10,20,16,2,1,1,0,0,0,1,0,{variant},1)"
    cuts = [m for m in clean(source).motions if m.threading]
    assert len(cuts) == 1
    assert (cuts[0].start_x, cuts[0].end_x) == pytest.approx(expected)
    assert (cuts[0].start_z, cuts[0].end_z) == (2, -11)


def test_cycle95_reports_unmodeled_automatic_nose_compensation():
    source = "T1 D1\n" + rough_program()
    result = clean(source, tools={"T0001": {"type": "diamond", "noseRadius": 0.4}})
    notice = result.diagnostics[0]
    assert notice.code == "UNVERIFIED_SINUMERIK_CYCLE95_NOSE_COMPENSATION"
    assert notice.severity == "warning" and notice.line == 4


def test_native_scalar_loop_preserves_occurrences():
    result = clean("R1=0\nWHILE R1<3\nR1=R1+1\nG1 X=R1*2 F100\nENDWHILE\nM30")
    assert [m.end_x for m in result.motions] == [2, 4, 6]
    assert [s.occurrence for s in result.execution_steps if s.source_block == 3] == [0, 1, 2]


def test_cycle95_arc_roughing_respects_chord_tolerance_and_finish_keeps_arc():
    source = (
        'G0 X50 Z2\nCYCLE95("START:END",2,0,0,0,0.2,0.1,0.1,9,0,0,1)\nM30\n'
        "START:\nG0 X40 Z0\nG3 X0 Z-20 I-20 K0\nG1 Z-25\nEND:"
    )
    result = clean(source, arc_tolerance=0.001)
    assert any(m.arc and m.arc.radius == pytest.approx(20) for m in result.motions)
    rough = [m for m in result.motions if m.move == 1 and m.feed == 0.2 and -20 <= m.end_z <= 0]
    assert rough
    assert all(math.hypot(m.end_x / 2, m.end_z) >= 20 - 0.001 - 1e-8 for m in rough)


def test_centerline_tapping_uses_pitch_only_on_synchronized_feed_moves():
    result = clean("G94\nS500 M3\nG0 Z10\nCYCLE84(5,0,2,,9,0.2,3,,1.25,0,500,0,3,0,0,0)")
    cuts = [m for m in result.motions if m.threading]
    assert len(cuts) == 2
    assert all(m.move == 1 and m.feed == 1.25 and m.feed_mode == "per_revolution" for m in cuts)
    assert all(not m.threading for m in result.motions if m.move == 0)
    assert {s.kind for s in result.signals} >= {"rigid_tapping", "spindle_sync", "spindle_reverse"}
