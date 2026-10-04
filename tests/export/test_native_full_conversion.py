"""Native Full Program conversion must preserve executed semantics."""

import pytest

from app.cli import main
from app.gcode.export.native_layout import format_native_tool_changes
from app.gcode.export.options import ExportOptions
from app.gcode.export.service import ExportRequest, export_file
from app.gcode.export.sinumerik import convert_full_program_to_fanuc, convert_full_program_to_sinumerik
from app.gcode.export.validation import validate_full_program_dialect_conversion
from app.gcode.program_execution import execute_program
from app.gcode.trace_tools import motion_length
from app.ui.windows.main_window_file_ops import _convert_full_program_dialect


def execute(source, dialect="sinumerik"):
    return execute_program(source, language="fanuc_mill", source_dialect=dialect)[0]


def test_native_cycle_export_does_not_print_negative_zero():
    source = "G710\nG0 X-1 Z10\nF100\nMCALL CYCLE81(5,0,2,-5,,0,0,0,0)\nX-0.000000000000001\nMCALL\nM30"
    output = convert_full_program_to_fanuc(source)
    assert "X-0" not in output


@pytest.mark.parametrize("units,expected", [("G710", "G21"), ("G700", "G20")])
def test_native_units_are_normalized_before_target_validation(units, expected):
    source = f"G290\nG17 {units} G90 G94\nG0 X0 Y0\nG1 X10 F100\nM30\n"
    converted = convert_full_program_to_fanuc(source)
    assert expected in converted and units not in converted and "G290" not in converted
    target = execute(converted, "fanuc")
    assert target.ok and target.complete and not target.diagnostics
    validate_full_program_dialect_conversion(execute(source), converted, "fanuc_mill", source_dialect="fanuc")


def test_inverse_time_feed_is_preserved_on_every_motion():
    source = "G710 G0 X0\nG93 G1 X10 F2\nX20\nM30\n"
    converted = convert_full_program_to_fanuc(source)
    target = execute(converted, "fanuc")
    assert target.ok and target.complete and not target.diagnostics
    assert [(m.feed_mode, m.feed) for m in target.motions] == [("inverse_time", 2), ("inverse_time", 2)]
    with pytest.raises(ValueError, match="geometry"):
        validate_full_program_dialect_conversion(
            execute(source), converted.replace("G93", "G94"), "fanuc_mill", source_dialect="fanuc"
        )


@pytest.mark.parametrize("metadata", ["G601", "G641", "G642", "G645", "DIAMOF"])
def test_safe_source_warning_is_retained_without_blocking(metadata):
    source = f"G710\n{metadata}\nG0 X0\nG1 X10 F100\nM30\n"
    result = execute(source)
    warnings = result.diagnostics
    assert result.ok and result.complete and warnings
    converted = convert_full_program_to_fanuc(source, source_result=result)
    assert metadata not in converted
    assert result.diagnostics == warnings
    assert not execute(converted, "fanuc").diagnostics


@pytest.mark.parametrize("unsafe", ["G999", "TRANS X10", "AROT Z30", "ORIWKS", "DIAMON", "RNDM=2", "G4 S2", "TRAORI"])
def test_unknown_or_unrepresentable_native_semantics_still_block(unsafe):
    source = f"G710\n{unsafe}\nG0 X0\nG1 X10 F100\nM30\n"
    with pytest.raises(ValueError):
        convert_full_program_to_fanuc(source)


def test_length_only_unit_switches_preserve_independent_feed_units():
    source = "G70 G1 X1 F2\nG700 X2\nG71 X60\nG710 X70\nM30\n"
    converted = convert_full_program_to_fanuc(source)
    target = execute(converted, "fanuc")
    assert [m.end_x for m in target.motions] == pytest.approx([25.4, 50.8, 60, 70])
    assert [m.feed for m in target.motions] == pytest.approx([2, 50.8, 50.8, 2])


def test_native_parameters_radius_increment_and_dwell_use_core_words():
    source = "G710 G17 G90\nDEF REAL _length\n_length=1\nG0 X=_length Y0\nG3 X0 Y=IC(1) CR=1 F100\nG4 F2\nM30\n"
    converted = convert_full_program_to_fanuc(source)
    assert "DEF" not in converted and "IC(" not in converted and "CR=" not in converted
    assert "R1" in converted and "P2000" in converted
    target = execute(converted, "fanuc")
    assert target.ok and not target.diagnostics and target.motions[-1].arc is not None


@pytest.mark.parametrize("style, comment", [("parentheses", "(CONTOUR)"), ("semicolon", ";CONTOUR")])
def test_comments_and_missing_feed_are_not_silently_lost(style, comment):
    source = "G710\nT1 (flat end mill D=6)\nG0 X0\nG1 X10 ;contour\nM30\n"
    converted = convert_full_program_to_fanuc(source, export_options=ExportOptions(comment_style=style))
    assert "FLAT END MILL D=6" in converted and comment in converted
    assert execute(converted, "fanuc").motions[-1].feed == execute(source).motions[-1].feed


def test_gui_and_cli_share_native_conversion_and_keep_source_warnings(tmp_path):
    source = "G710\nG601\nG0 X0\nG1 X10 F100\nM30\n"
    result = execute(source)
    gui = _convert_full_program_dialect(source, result, 1, "sinumerik", ExportOptions(), {})
    input_path, output = tmp_path / "source.mpf", tmp_path / "output.nc"
    input_path.write_text(source, newline="")
    exported = export_file(input_path, output, ExportRequest(language="fanuc_mill", mode="full"))
    assert exported.execution.diagnostics == result.diagnostics
    validate_full_program_dialect_conversion(result, gui, "fanuc_mill", source_dialect="fanuc")
    validate_full_program_dialect_conversion(result, output.read_text(), "fanuc_mill", source_dialect="fanuc")


def test_reverse_native_full_conversion_stays_prohibited(tmp_path):
    source = "G21 G0 X0\nG1 X10 F100\nM30\n"
    input_path, output = tmp_path / "source.nc", tmp_path / "output.mpf"
    input_path.write_text(source)
    with pytest.raises(ValueError):
        export_file(
            input_path, output, ExportRequest(language="fanuc_mill", mode="full", target_dialect="sinumerik_native")
        )
    assert not output.exists()
    with pytest.raises(ValueError, match="Unknown target"):
        _convert_full_program_dialect(source, execute(source, "fanuc"), 3, "fanuc", ExportOptions(), {})


def test_existing_fanuc_iso_conversion_remains_source_preserving():
    source = "G21 G0 X0\nG1 X10 F100\nM30\n"
    iso = convert_full_program_to_sinumerik(source)
    assert iso == "G291\n" + source
    assert convert_full_program_to_fanuc(iso) == source


def test_empty_cycle800_reset_is_not_multiaxis_conversion():
    source = "G710 G17 G90\nG0 Z15\nG1 Z-5 F100\nG0 Z15\nCYCLE800()\nM30\n"
    result = execute(source)
    assert result.ok and result.complete and not result.rotary_axes
    assert not any(e.kind == "TILTED_WORK_PLANE_ON" for e in result.events)
    converted = convert_full_program_to_fanuc(source, source_result=result)
    assert "CYCLE800" not in converted
    validate_full_program_dialect_conversion(result, converted, "fanuc_mill", source_dialect="fanuc")


def test_frame_reset_does_not_allow_active_cycle800_or_reverse_native_export():
    source = 'G710\nCYCLE800(2,"TISCH",200000,57,0,0,50,-15,0,0,0,0,0,1,,1)\nG0 Z5\nCYCLE800()\nM30\n'
    result = execute_program(
        source, language="fanuc_mill", source_dialect="sinumerik", kinematics="5ax_table_ac_angled"
    )[0]
    assert result.ok and result.complete
    with pytest.raises(ValueError, match="5-axis / TCP"):
        convert_full_program_to_fanuc(source, source_result=result)
    with pytest.raises(ValueError, match="5-axis / TCP"):
        convert_full_program_to_sinumerik("G21\nCYCLE800()\nM30\n")


def test_cli_exports_actual_correction_program_with_reset_and_compensation(tmp_path, fixture_text, capsys):
    source = fixture_text("milling/correction_sin840d.mpf")
    input_path, output = tmp_path / "correction.mpf", tmp_path / "converted.nc"
    input_path.write_text(source)
    assert (
        main(
            [
                "export",
                str(input_path),
                "--lang",
                "fanuc_mill",
                "--target-dialect",
                "fanuc_mill",
                "--mode",
                "full",
                "-o",
                str(output),
            ]
        )
        == 0
    )
    assert "CLEAN" in capsys.readouterr().out
    converted = output.read_text()
    assert "CYCLE800" not in converted and "SUPA" not in converted and "G710" not in converted
    assert "G41" in converted and "G40" in converted
    result, target = execute(source), execute(converted, "fanuc")
    assert target.ok and target.complete and not target.diagnostics
    validate_full_program_dialect_conversion(result, converted, "fanuc_mill", source_dialect="fanuc")
    original_cam = execute(fixture_text("milling/correction_fanuc.nc"), "fanuc")
    assert original_cam.ok and original_cam.complete

    # CAM splits circular moves differently and rounds coordinates/feed.
    def cutting_length(r):
        return sum(motion_length(m) for m in r.motions if m.move != 0)

    assert cutting_length(target) == pytest.approx(cutting_length(original_cam), abs=0.02)


def test_nonzero_home_supa_conversion_preserves_geometry(fixture_text):
    source = fixture_text("milling/correction_sin840d.mpf")
    options = {"home_z": 100}
    result = execute_program(source, language="fanuc_mill", source_dialect="sinumerik", **options)[0]
    assert result.ok and result.complete
    converted = convert_full_program_to_fanuc(source, source_result=result, execution_options=options)
    validate_full_program_dialect_conversion(
        result, converted, "fanuc_mill", source_dialect="fanuc", execution_options=options
    )


def test_ijk_correction_export_has_tool_offsets_and_source_modal_feeds(tmp_path, fixture_text):
    source = fixture_text("milling/correction_ijk_sin840d.mpf")
    input_path, output = tmp_path / "correction.mpf", tmp_path / "correction.nc"
    input_path.write_text(source)
    export_file(input_path, output, ExportRequest(language="fanuc_mill", mode="full", leading_zero=True))
    converted = output.read_text()
    assert "T02 M06" in converted
    assert "(2D CONTOUR1)" in converted
    assert "G43 Z15 H02" in converted
    assert converted.count("G43") == 1
    assert "G49" in converted.split("M05", 1)[1]
    assert "G01 G41 X12.4 Y-70.4 D02 F1000" in converted
    assert "G03 X0 Y-58 I-12.4 J0" in converted
    assert [line for line in converted.splitlines() if "F" in line] == [
        "G01 Z1 F333.3",
        "G01 G41 X12.4 Y-70.4 D02 F1000",
        "G01 X-65 F800",
        "G03 X-12.4 Y-70.4 I0 J-12.4 F1000",
    ]
    validate_full_program_dialect_conversion(execute(source), converted, "fanuc_mill", source_dialect="fanuc")


def test_native_offsets_follow_each_changed_tool():
    source = "G710\nT2\nM6\nD1\nG0 Z15\nG41\nG40\nD0\nT7\nM6\nD1\nG0 Z20\nG42\nG40\nM30\n"
    converted = convert_full_program_to_fanuc(source)
    assert "T2 M6" in converted and "T7 M6" in converted
    assert "G43 Z15 H2" in converted and "G43 Z20 H7" in converted
    assert "G41 D2" in converted and "G42 D7" in converted
    assert "G49" in converted and "H1" not in converted


@pytest.mark.parametrize("barrier", ["G1 Z10 F100", "/G0 Z10", "M30", "G49"])
def test_length_activation_is_not_deferred_across_cutting_optional_or_cancel_blocks(barrier):
    source = f"G43 H2\nG0 X1 Y2\n{barrier}\n"
    assert format_native_tool_changes(source) == source


def test_standalone_feed_remains_modal_without_duplicate_on_first_cut():
    converted = convert_full_program_to_fanuc("G710\nF100\nG1 X10\nX20\nM30\n")
    assert converted.count("F100") == 1


def test_length_activation_preserves_rapid_after_prior_cutting_mode():
    source = "G710\nG1 X1 F100\nT2 M6\nD1\nG0 Z15\nM30\n"
    converted = convert_full_program_to_fanuc(source)
    assert "G0 G43 Z15 H2" in converted
    validate_full_program_dialect_conversion(execute(source), converted, "fanuc_mill", source_dialect="fanuc")


@pytest.mark.parametrize("prefix", ["", "N100 ", "/N100 "])
def test_trailing_edge_selection_does_not_reactivate_cancelled_length_compensation(prefix):
    source = f"G710\nT2 M6\nD1\nG0 Z15\nG0 SUPA Z0 D0\n{prefix}D1\nCYCLE800()\nM30\n"
    converted = convert_full_program_to_fanuc(source)
    assert converted.count("G43") == 1
    assert "G43" not in converted.split("G49", 1)[1]
    validate_full_program_dialect_conversion(execute(source), converted, "fanuc_mill", source_dialect="fanuc")


@pytest.mark.parametrize("units", ["G710", "G700"])
@pytest.mark.parametrize("optional", ["", "/"])
def test_supa_preserves_wcs_incremental_mode_and_units(units, optional):
    source = f"{units} G90 G54\r\nG0 X1 Y2 Z3\r\nG91\r\n{optional}G0 SUPA Z0 D0\r\nG1 X1 Z1 F100\r\nM30\r\n"
    options = {"home_z": 500, "wcs_offsets": {54: (10, 20, 100)}}
    result = execute_program(source, language="fanuc_mill", source_dialect="sinumerik", **options)[0]
    assert result.ok and result.complete
    converted = convert_full_program_to_fanuc(source, source_result=result, execution_options=options)
    assert "G53" not in converted and "SUPA" not in converted
    supa_line = next(line for line in converted.splitlines() if "G49" in line)
    assert "X" not in supa_line and "Y" not in supa_line
    assert ("/G91\r\n" if optional else "G91\r\n") in converted
    assert "\n" not in converted.replace("\r\n", "")
    validate_full_program_dialect_conversion(
        result, converted, "fanuc_mill", source_dialect="fanuc", execution_options=options
    )
