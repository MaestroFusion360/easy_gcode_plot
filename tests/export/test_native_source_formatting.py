"""Native Full Program formatting preserves functions and multi-axis state."""

import pytest

from app.gcode.export.dispatch import export_program
from app.gcode.export.options import MILL_FULL_PROGRAM_MODE, ExportOptions
from app.gcode.export.service import ExportRequest, export_file
from app.gcode.export.source_formatting import format_full_program_source
from app.gcode.export.validation import _motion_trace_signature
from app.gcode.program_execution import execute_program
from app.ui.windows.main_window_file_ops import _convert_full_program_dialect


def test_gui_native_source_formatting_preserves_expressions_comments_and_crlf():
    source = "\r\n".join(
        [
            "%_N_FORMAT_MPF",
            "; setup",
            "G710 G17 G90 G94",
            "DEF REAL _step",
            "_step=1",
            'MSG("G1 X2 keep text")',
            "G0 X1 Y0",
            "G3 X0 Y=IC(_step) CR=1 F100",
            "CYCLE800()",
            "M30",
            "",
        ]
    )
    original = execute_program(source, language="fanuc_mill", source_dialect="sinumerik")[0]
    assert original.ok, original.diagnostics
    formatted = export_program(
        original,
        source,
        mode=MILL_FULL_PROGRAM_MODE,
        lathe_mode=False,
        options=ExportOptions(
            sequence_numbers=True,
            sequence_start=10,
            sequence_increment=10,
            delimiter=True,
            leading_zero=True,
            comment_style="parentheses",
        ),
    )
    assert formatted.startswith("%_N_FORMAT_MPF\r\n; setup\r\nN10 G710")
    assert 'MSG("G1 X2 keep text")' in formatted
    assert "Y=IC(_step) CR=1" in formatted and "CYCLE800()" in formatted
    assert "\n" not in formatted.replace("\r\n", "")
    target = execute_program(formatted, language="fanuc_mill", source_dialect="sinumerik")[0]
    assert target.ok and target.complete
    assert _motion_trace_signature(target) == _motion_trace_signature(original)
    assert (
        _convert_full_program_dialect(
            source,
            original,
            3,
            "sinumerik",
            ExportOptions(
                sequence_numbers=True,
                sequence_start=10,
                sequence_increment=10,
                delimiter=True,
                leading_zero=True,
                comment_style="parentheses",
            ),
            {},
        )
        == formatted
    )


def test_native_comment_removal_keeps_parentheses_and_quoted_semicolons():
    source = 'MSG("G1 X2; note") ; comment\nG1 X=IC(1) F100 ; cut\nCYCLE800()\n'
    formatted = format_full_program_source(source, ExportOptions(include_comments=False), native=True)
    assert 'MSG("G1 X2; note")' in formatted and "IC(1)" in formatted and "CYCLE800()" in formatted
    assert "; comment" not in formatted and "; cut" not in formatted


@pytest.mark.parametrize("fixture", ["sinumerik_traori_ac.mpf", "sinumerik_cycle800.mpf"])
def test_cli_native_multiaxis_source_formatting_preserves_geometry_and_orientation(tmp_path, fixture_text, fixture):
    source = fixture_text("milling/sinumerik/" + fixture)
    source_path, output_path = tmp_path / fixture, tmp_path / "formatted.mpf"
    source_path.write_text(source)
    request = ExportRequest(
        language="fanuc_mill",
        target_dialect="sinumerik_native",
        mode="full",
        kinematics="5ax_table_ac_angled",
        sequence_numbers=True,
        sequence_start=100,
        sequence_increment=5,
        spaces=True,
        leading_zero=True,
    )
    exported = export_file(source_path, output_path, request)
    assert exported.execution.ok and output_path.exists()
    formatted = output_path.read_text()
    assert "N100 G710" in formatted
    target = execute_program(
        formatted, language="fanuc_mill", source_dialect="sinumerik", kinematics="5ax_table_ac_angled"
    )[0]
    assert target.ok and target.complete
    assert _motion_trace_signature(target) == _motion_trace_signature(exported.execution)
    assert [step.rotary_angles for step in target.execution_steps] == [
        step.rotary_angles for step in exported.execution.execution_steps
    ]
    assert [step.twp_orientation for step in target.execution_steps] == [
        step.twp_orientation for step in exported.execution.execution_steps
    ]
    assert [motion.tool_orientation for motion in target.motions] == [
        motion.tool_orientation for motion in exported.execution.motions
    ]


def test_native_numbering_does_not_rewrite_jump_targets():
    with pytest.raises(ValueError, match="GOTO"):
        format_full_program_source("N10 G0 X0\nGOTOF N10\n", ExportOptions(sequence_numbers=True), native=True)
