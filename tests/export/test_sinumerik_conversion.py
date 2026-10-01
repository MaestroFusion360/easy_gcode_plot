"""Fail-closed SINUMERIK ISO conversion across core, CLI, and GUI paths."""

from threading import Event

import pytest

from app.cli import main
from app.gcode.export.dispatch import export_program
from app.gcode.export.mill import export_full_mill_program
from app.gcode.export.options import MILL_FULL_PROGRAM_MODE, ExportOptions
from app.gcode.export.service import ExportRequest, export_file
from app.gcode.export.sinumerik import convert_full_program_to_sinumerik
from app.gcode.export.validation import validate_full_program_dialect_conversion
from app.gcode.kernel.io import read_nc_text
from app.gcode.program_execution import execute_program
from app.ui.windows.main_window_file_ops import _convert_full_program_dialect, _write_export

THREE_AXIS = "O1234\nG90 G0 X0 Y0 Z100\nG1 X10 Y20 Z30 F100\nG49\nM30\n"
UNSUPPORTED = [
    ("4ax_table_a", "G90 G0 Z100\nA90\nG91 G28 Z0\nM30\n", "4-axis"),
    ("4ax_table_b", "G90 G0 Z100\nB90\nG91 G28 Z0\nM30\n", "4-axis"),
    ("4ax_table_c", "G90 G0 Z100\nC90\nG91 G28 Z0\nM30\n", "4-axis"),
    ("5ax_table_ac_angled", "G90 G0 Z100\nG43.4 H2\nG1 X10 Y20 Z30 A30 C45 F100\nG49\nM30\n", "5-axis / TCP"),
    ("5ax_table_bc_angled", "G90 G0 Z100\nG43.4 H2\nG1 X10 Y20 Z30 B30 C45 F100\nG49\nM30\n", "5-axis / TCP"),
    ("5ax_table_ac_angled", "G90 G0 Z100\nG1 X10 Y20 Z30 A30 C45 F100\nM30\n", "5-axis / TCP"),
    ("5ax_table_ac_angled", "G90 G0 Z100\nA30 C45\nG1 X10 Y20 F100\nM30\n", "5-axis / TCP"),
    (None, "G43.4 H2\nM30\n", "5-axis / TCP"),
    ("4ax_table_a", THREE_AXIS, "4-axis"),
    ("4ax_table_b", THREE_AXIS, "4-axis"),
    ("4ax_table_c", THREE_AXIS, "4-axis"),
    ("5ax_table_ac_angled", THREE_AXIS, "5-axis / TCP"),
    ("5ax_table_bc_angled", THREE_AXIS, "5-axis / TCP"),
    (None, "G90 G0 X10 A30\nM30\n", "4-axis"),
    (None, "G90 G0 X10 A30 C45\nM30\n", "5-axis / TCP"),
    (None, "G68.2 X0 Y0 Z0 I0 J30 K0\nM30\n", "5-axis / TCP"),
    (None, "G90 G0 X1\nTRAORI\nM30\n", "5-axis / TCP"),
    (None, "G90 G0 X1\nTRAFOOF\nM30\n", "5-axis / TCP"),
    (None, "G90 G0 X1\nCYCLE800()\nM30\n", "5-axis / TCP"),
    (None, "G290\nTRAORI\nG291\nG0 X1\nM30\n", "5-axis / TCP"),
]


def message(axis_kind):
    return f"SINUMERIK ISO export for {axis_kind} programs is not supported yet"


def test_three_axis_conversion_is_supported_and_does_not_synthesize_native_commands():
    converted = convert_full_program_to_sinumerik(THREE_AXIS)
    assert converted == "G291\n" + THREE_AXIS
    assert not any(command in converted for command in ("TRAORI", "TRAFOOF", "G290", "CYCLE800"))
    assert convert_full_program_to_sinumerik(converted) == converted


@pytest.mark.parametrize("profile", [None])
def test_three_axis_export_without_rotary_profile_is_supported(tmp_path, profile):
    source = tmp_path / "source.nc"
    output = tmp_path / "output.mpf"
    source.write_text(THREE_AXIS)
    exported = export_file(
        source,
        output,
        ExportRequest(
            language="fanuc_mill",
            mode="full",
            target_dialect="sinumerik840d",
            kinematics=profile,
        ),
    )
    assert exported.execution.ok and exported.execution.complete
    assert output.read_text() == "G291\n" + THREE_AXIS


@pytest.mark.parametrize("profile, source, axis_kind", UNSUPPORTED)
def test_core_converter_rejects_unverified_multi_axis(profile, source, axis_kind, monkeypatch):
    def unexpected_mode_insertion(*args):
        pytest.fail("Unsupported conversion must not generate even the G291 mode switch")

    monkeypatch.setattr("app.gcode.export.sinumerik._full_program_mode_insertion", unexpected_mode_insertion)
    with pytest.raises(ValueError) as error:
        convert_full_program_to_sinumerik(source, execution_options={"kinematics": profile})
    assert str(error.value) == message(axis_kind)


@pytest.mark.parametrize("profile, source, axis_kind", UNSUPPORTED)
def test_export_service_fails_before_creating_or_overwriting_nc(tmp_path, profile, source, axis_kind):
    input_path = tmp_path / "source.nc"
    output = tmp_path / "output.mpf"
    input_path.write_text(source)
    request = ExportRequest(language="fanuc_mill", mode="full", target_dialect="sinumerik840d", kinematics=profile)
    for existing in (False, True):
        if existing:
            output.write_text("existing output")
        exported = export_file(input_path, output, request)
        assert not exported.execution.ok and not exported.execution.complete
        assert exported.output_size_bytes == 0
        assert exported.execution.diagnostics[-1].message == message(axis_kind)
        assert exported.execution.diagnostics[-1].status == "unsupported"
        if existing:
            assert output.read_text() == "existing output"
        else:
            assert not output.exists()


@pytest.mark.parametrize("profile, source, axis_kind", UNSUPPORTED)
def test_cli_rejects_multi_axis_with_explicit_error(tmp_path, capsys, profile, source, axis_kind):
    input_path = tmp_path / "source.nc"
    output = tmp_path / "output.mpf"
    input_path.write_text(source)
    args = [
        "export",
        str(input_path),
        "--lang",
        "fanuc_mill",
        "--mode",
        "full",
        "--target-dialect",
        "sinumerik840d",
        "-o",
        str(output),
    ]
    if profile:
        args.extend(["--kinematics", profile])
    assert main(args) == 2
    captured = capsys.readouterr()
    assert message(axis_kind) in captured.out + captured.err
    assert not output.exists()


@pytest.mark.parametrize("profile, source, axis_kind", UNSUPPORTED)
def test_gui_rejects_multi_axis_before_writing(tmp_path, profile, source, axis_kind):
    options = {"kinematics": profile}
    result, _, _ = execute_program(source, language="fanuc_mill", **options)
    output = tmp_path / "output.mpf"
    output.write_text("existing output")
    with pytest.raises(ValueError) as error:
        _write_export(
            None,
            dxf_export=False,
            path=str(output),
            result=result,
            render_points=(),
            lathe_mode=False,
            text_snapshot=(source, MILL_FULL_PROGRAM_MODE, 0, ExportOptions(), "utf-8", 2, "fanuc", options),
            cancellation=Event(),
        )
    assert str(error.value) == message(axis_kind)
    assert output.read_text() == "existing output"


@pytest.mark.parametrize("profile, source, axis_kind", UNSUPPORTED)
def test_validation_cannot_bypass_unsupported_source(profile, source, axis_kind, monkeypatch):
    result, _, _ = execute_program(source, language="fanuc_mill", kinematics=profile)

    def unexpected_execution(*args, **kwargs):
        pytest.fail("Unsupported source must be rejected before target validation")

    monkeypatch.setattr("app.gcode.export.validation.execute_program", unexpected_execution)
    with pytest.raises(ValueError) as error:
        validate_full_program_dialect_conversion(
            result,
            "G291\n" + THREE_AXIS,
            "fanuc_mill",
            source_dialect="sinumerik",
            execution_options={"kinematics": profile},
        )
    assert str(error.value) == message(axis_kind)


@pytest.mark.parametrize("activation", ["G043.4", "G43.40", "g43.4", "#1=43.4\nG#1"])
def test_tcp_rejection_uses_evaluated_kernel_words(activation):
    with pytest.raises(ValueError, match="5-axis / TCP"):
        convert_full_program_to_sinumerik(
            activation + " H2\nM30\n", execution_options={"kinematics": "5ax_table_ac_angled"}
        )


def test_commands_mentioned_only_in_comments_are_preserved():
    source = "N10G0X1 (G43.4 TRAORI) ; TRAFOOF CYCLE800 G290\r\nM30\r\n"
    assert convert_full_program_to_sinumerik(source) == "G291\r\n" + source


def test_validation_rejects_native_tcp_without_surrogate():
    result, _, _ = execute_program(THREE_AXIS, language="fanuc_mill")
    with pytest.raises(ValueError, match="5-axis / TCP"):
        validate_full_program_dialect_conversion(
            result, "G291\nTRAORI\nM30\n", "fanuc_mill", source_dialect="sinumerik"
        )


def test_gui_validates_geometry_after_formatting():
    source = "O1\nG90 G0 X10\nM30\n"
    result, _, _ = execute_program(source, language="fanuc_mill")
    with pytest.raises(ValueError, match="changes resolved motion geometry"):
        _convert_full_program_dialect(source, result, 2, "fanuc", ExportOptions(start_program="O2\nG0 X20"), {})


def test_gui_rejects_program_end_that_changes_machine_signals():
    source = "O1\nG90 G0 X10\nM30\n"
    result, _, _ = execute_program(source, language="fanuc_mill")
    with pytest.raises(ValueError, match="changes machine signals"):
        _convert_full_program_dialect(source, result, 2, "fanuc", ExportOptions(end_program="M2"), {})


@pytest.mark.parametrize("profile, source, axis_kind", UNSUPPORTED[:7])
def test_fanuc_full_program_export_still_uses_existing_kernel(tmp_path, profile, source, axis_kind):
    input_path = tmp_path / "source.nc"
    output = tmp_path / "output.nc"
    input_path.write_text(source)
    original, _, _ = execute_program(
        read_nc_text(input_path), language="fanuc_mill", kinematics=profile, autodetect_arc_type=True
    )
    exported = export_file(input_path, output, ExportRequest(language="fanuc_mill", mode="full", kinematics=profile))
    assert exported.execution == original
    assert output.exists() == (original.ok and original.complete)


def test_batch_export_rejects_multi_axis_without_creating_nc(tmp_path, capsys):
    source_root = tmp_path / "source"
    source_root.mkdir()
    output = tmp_path / "output"
    source_root.joinpath("part.nc").write_text(UNSUPPORTED[0][1])
    assert (
        main(
            [
                "batch-export",
                str(source_root),
                "--lang",
                "fanuc_mill",
                "--mode",
                "full",
                "--target-dialect",
                "sinumerik840d",
                "--kinematics",
                "4ax_table_a",
                "-o",
                str(output),
            ]
        )
        == 2
    )
    capsys.readouterr()
    assert not list(output.rglob("*.mpf"))


@pytest.mark.parametrize(
    "profile, source, axis_kind", UNSUPPORTED[:3] + [case for case in UNSUPPORTED if case[1] == THREE_AXIS]
)
def test_as_source_iso_full_program_export_cannot_bypass_restriction(tmp_path, profile, source, axis_kind):
    iso_source = "G291\n" + source
    options = {"kinematics": profile, "source_dialect": "sinumerik", "home_z": 500}
    result, _, _ = execute_program(iso_source, language="fanuc_mill", **options)
    assert result.ok and result.complete
    with pytest.raises(ValueError) as error:
        export_program(result, iso_source, mode=MILL_FULL_PROGRAM_MODE, lathe_mode=False, options=ExportOptions())
    assert str(error.value) == message(axis_kind)
    with pytest.raises(ValueError) as error:
        export_full_mill_program(result, iso_source.splitlines())
    assert str(error.value) == message(axis_kind)
    output = tmp_path / "output.mpf"
    with pytest.raises(ValueError) as error:
        _write_export(
            None,
            dxf_export=False,
            path=str(output),
            result=result,
            render_points=(),
            lathe_mode=False,
            text_snapshot=(iso_source, MILL_FULL_PROGRAM_MODE, 0, ExportOptions(), "utf-8", 0, "sinumerik", options),
            cancellation=Event(),
        )
    assert str(error.value) == message(axis_kind)
    assert not output.exists()


@pytest.mark.parametrize("target_source", ["G291\nG0 X1 A30 C45\nM30\n", "G291\nG43.4 H2\nM30\n"])
def test_validation_rejects_unsupported_target_even_with_three_axis_source(target_source):
    result, _, _ = execute_program(THREE_AXIS, language="fanuc_mill")
    with pytest.raises(ValueError, match="5-axis / TCP"):
        validate_full_program_dialect_conversion(
            result,
            target_source,
            "fanuc_mill",
            source_dialect="sinumerik",
            execution_options={"kinematics": "5ax_table_ac_angled"},
        )
