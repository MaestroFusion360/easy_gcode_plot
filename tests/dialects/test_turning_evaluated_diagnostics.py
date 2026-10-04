"""Evaluated turning commands share diagnostics across kernel and export."""

import pytest

from app.gcode.batch import execute_analysis_program
from app.gcode.export.service import ExportRequest, export_file
from app.gcode.kernel import execute


@pytest.mark.parametrize("system", ["A", "B"])
@pytest.mark.parametrize("code", [17, 19, 123, 200, 999, 1.1])
def test_unknown_computed_g_matches_literal_and_blocks_export(tmp_path, system, code):
    results = []
    for dynamic in (False, True):
        command = f"#1={code}\nG#1" if dynamic else f"G{code}"
        source = f"G1 F100\n{command} X10 Z0\nM30"
        result = execute(source, language="fanuc_turn", lathe_gcode_system=system)
        assert not result.ok and not result.motions
        results.append([(d.code, d.message, d.severity, d.status) for d in result.diagnostics])
        path = tmp_path / f"input-{dynamic}.nc"
        path.write_text(source, newline="\n")
        output = tmp_path / f"output-{dynamic}.nc"
        output.write_text("PREVIOUS OUTPUT")
        exported = export_file(
            path, output, ExportRequest(language="fanuc_turn", mode="expanded", lathe_gcode_system=system)
        )
        assert not exported.execution.ok
        assert output.read_text() == "PREVIOUS OUTPUT"
    assert results[0] == results[1]


@pytest.mark.parametrize("code", [7, 19, 123, 999, 3.1])
def test_computed_m_warning_matches_kernel_analysis_and_export(tmp_path, code):
    signatures = []
    for dynamic in (False, True):
        source = (f"#1={code}\nM#1" if dynamic else f"M{code}") + "\nG1 X10 F100\nM30"
        kernel = execute(source, language="fanuc_turn")
        analysis = execute_analysis_program(source, language="fanuc_turn")
        path = tmp_path / f"input-{dynamic}.nc"
        path.write_text(source, newline="\n")
        exported = export_file(
            path, tmp_path / f"output-{dynamic}.nc", ExportRequest(language="fanuc_turn", mode="expanded")
        )
        assert kernel.ok and kernel.complete
        assert kernel.diagnostics == analysis.diagnostics == exported.execution.diagnostics
        assert len(kernel.diagnostics) == 1
        assert kernel.diagnostics[0].code == "UNSUPPORTED_M_CODE"
        signatures.append((kernel.diagnostics[0].message, kernel.diagnostics[0].severity))
    assert signatures[0] == signatures[1]


def test_unknown_codes_in_unexecuted_branch_do_not_report_execution_errors():
    result = execute("GOTO10\nG123 X10\nM123\nN10 G1 X20 F100\nM30", language="fanuc_turn")
    assert result.ok and result.complete and not result.diagnostics
    assert result.motions[-1].end_x == 20


def test_unknown_g_does_not_connect_trace_across_unknown_position():
    result = execute("G1 X10 F100\n#1=123\nG#1 X20\nG1 X30\nG1 X40\nM30", language="fanuc_turn")
    assert not result.ok
    assert not any(m.start_x == 10 and m.end_x == 30 for m in result.motions)
    assert result.motions[-1].start_x == 30 and result.motions[-1].end_x == 40


def test_milling_unknown_xyz_diagnostic_describes_suppressed_trace():
    result = execute("G1 X10 F100\nG123 X20\nG1 X30\nG1 X40", language="fanuc_mill")
    assert [(motion.start_x, motion.end_x) for motion in result.motions] == [(0, 10), (30, 40)]
    assert "unknown until absolute positions are restored" in result.diagnostics[0].message


def test_computed_g_warning_survives_later_fatal_macro_error():
    result = execute("#1=999\nG#1\nGOTO999", language="fanuc_turn")
    assert not result.ok and not result.complete
    assert [d.code for d in result.diagnostics] == ["UNSUPPORTED_G_CODE", "FLOW_TARGET_MISSING"]
