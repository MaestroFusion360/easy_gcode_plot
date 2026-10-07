"""Manual-based TCP transitions and resolved home/reference export contracts."""

import pytest

from app.gcode.export.common import ExportLimitation, ExportOptions
from app.gcode.export.expanded import convert_resolved_program
from app.gcode.kernel import execute
from app.gcode.kernel.milling.kinematics import load_catalog, point_orientation, transform_vector

PROFILES = (("5ax_table_ac_angled", "A"), ("5ax_table_bc_angled", "B"))


def point(motion, end=False):
    return (motion.end_x, motion.end_y, motion.end_z) if end else (motion.start_x, motion.start_y, motion.start_z)


@pytest.mark.parametrize("profile,axis", PROFILES)
@pytest.mark.parametrize("angle", (-30, 30))
@pytest.mark.parametrize("mode", ("G90", "G91"))
def test_activation_block_executes_in_old_frame(profile, axis, angle, mode):
    r = execute(
        f"G90 G0 {axis}{angle}\nG0 X10 Y20 Z30\n{mode} G1 G43.4 Z10 F100\nG1 X20\nM30",
        language="fanuc_mill",
        kinematics=profile,
    )
    assert r.ok and r.complete, r.diagnostics
    matrix = point_orientation(load_catalog()[profile], {axis: angle})
    expected = transform_vector(matrix, (10, 20, 10 if mode == "G90" else 40))
    assert point(r.motions[1], True) == pytest.approx(expected)
    assert point(r.motions[2]) == pytest.approx(expected)
    assert r.motions[1].orientation == matrix
    assert r.motions[2].orientation is None


@pytest.mark.parametrize("profile,axis", PROFILES)
@pytest.mark.parametrize("cancel", ("G49", "G43 H1"))
def test_cancellation_index_matches_separate_blocks(profile, axis, cancel):
    prefix = f"G90 G0 {axis}30\nG0 X10 Y20 Z30\nG43.4\nG1 X15 F100\n"
    together = execute(prefix + f"{cancel} G0 {axis}60\nG0 X20\nM30", language="fanuc_mill", kinematics=profile)
    separate = execute(prefix + f"{cancel}\nG0 {axis}60\nG0 X20\nM30", language="fanuc_mill", kinematics=profile)
    assert together.ok and together.complete and separate.ok and separate.complete
    assert point(together.motions[-1]) == pytest.approx(point(separate.motions[-1]))
    assert point(together.motions[-1], True) == pytest.approx(point(separate.motions[-1], True))
    edges = [e.kind for e in together.events if e.kind.startswith(("TCP_", "ROTARY_"))]
    assert edges[-2:] == ["TCP_CONTROL_OFF", "ROTARY_INDEX"]


@pytest.mark.parametrize("profile,axis", PROFILES)
def test_cancelled_tcp_does_not_allow_simultaneous_feed(profile, axis):
    r = execute(f"G43.4\nG49 G1 X20 {axis}60 F100\nM30", language="fanuc_mill", kinematics=profile)
    assert not r.ok and not r.complete
    assert r.diagnostics[-1].code == "UNSUPPORTED_SIMULTANEOUS_ROTARY_MOTION"


@pytest.mark.parametrize(
    "profile,axis,code",
    (
        (None, "A", "ROTARY_KINEMATICS_REQUIRED"),
        ("5ax_table_ac_angled", "B", "UNCONFIGURED_ROTARY_AXIS"),
        ("5ax_table_bc_angled", "A", "UNCONFIGURED_ROTARY_AXIS"),
    ),
)
def test_zero_rotary_word_still_requires_configured_axis(profile, axis, code):
    r = execute(f"G0 {axis}0\nG1 X10 F100\nM30", language="fanuc_mill", kinematics=profile)
    assert not r.ok and not r.complete and not r.motions
    assert r.diagnostics[-1].code == code


@pytest.mark.parametrize("profile,axis", PROFILES)
@pytest.mark.parametrize("target", ("fanuc_mill_multiaxis", "sinumerik_840d_multiaxis"))
@pytest.mark.parametrize("incremental", (False, True))
def test_activation_export_replay(profile, axis, target, incremental):
    source = f"G90 G0 {axis}30\nG0 X10 Y20 Z30\nG1 G43.4 Z40 F100\nG1 X20\nG49\nM30"
    r = execute(source, language="fanuc_mill", kinematics=profile)
    text = convert_resolved_program(r, target, ExportOptions(delimiter=True, incremental=incremental))
    replay = execute(
        text,
        language="fanuc_mill",
        kinematics=profile,
        source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc",
    )
    assert replay.ok and replay.complete, (text, replay.diagnostics)
    assert len(r.motions) == len(replay.motions), text
    for original, exported in zip(r.motions, replay.motions):
        assert point(original) == pytest.approx(point(exported), abs=0.002), text
        assert point(original, True) == pytest.approx(point(exported, True), abs=0.002), text


@pytest.mark.parametrize("profile,axis", PROFILES)
def test_traori_first_transform_alias(profile, axis):
    prefix = f"G0 {axis}=30\nG0 X10 Y20 Z30\n"
    suffix = f"\nG1 X20 {axis}=45 C=90 F100\nTRAFOOF\nM30"
    a = execute(prefix + "TRAORI" + suffix, language="fanuc_mill", source_dialect="sinumerik", kinematics=profile)
    b = execute(prefix + "TRAORI(1)" + suffix, language="fanuc_mill", source_dialect="sinumerik", kinematics=profile)
    assert a.ok and b.ok and a.complete and b.complete, b.diagnostics
    assert a.rotary_angles == b.rotary_angles
    assert [point(m, True) for m in a.motions] == [point(m, True) for m in b.motions]


def test_inactive_cycle800_reset_has_no_false_edge():
    r = execute("CYCLE800()\nCYCLE800()\nG1 X10 F100\nM30", language="fanuc_mill", source_dialect="sinumerik")
    assert r.ok and r.complete
    assert not any(e.kind == "TILTED_WORK_PLANE_OFF" for e in r.events)


def test_cycle800_index_records_changed_axes():
    r = execute(
        'CYCLE800(0,"TISCH",200000,57,0,0,0,30,0,0,0,0,0,1,0,0)\nM30',
        language="fanuc_mill",
        source_dialect="sinumerik",
        kinematics="5ax_table_ac_angled",
    )
    assert r.ok and r.complete, r.diagnostics
    event = next(e for e in r.events if e.kind == "ROTARY_INDEX")
    assert event.axes == tuple(axis for i, axis in enumerate("ABC") if event.old_abc[i] != event.new_abc[i])
    assert event.axes


@pytest.mark.parametrize(
    "source,code",
    (
        ("G43.4\nG68.2 X0 Y0 Z0 I0 J30 K0", "UNSUPPORTED_TCP_TWP_COMPOSITION"),
        ("G81 Z-2 R1 F100\nG43.4", "UNSUPPORTED_TCP_CYCLE"),
        ("G43.4\nG81 Z-2 R1 F100", "UNSUPPORTED_TCP_CYCLE"),
        ("G41\nG43.4", "UNSUPPORTED_TCP_CUTTER_COMPENSATION"),
        ("G43.4\nG42 G1 X10 F100", "UNSUPPORTED_TCP_CUTTER_COMPENSATION"),
        ("G43.4\nG49 G2 X10 I5 F100", "UNSUPPORTED_TCP_CANCEL_MOTION"),
    ),
)
def test_tcp_rejects_unmodeled_combinations(source, code):
    r = execute(source + "\nM30", language="fanuc_mill", kinematics="5ax_table_bc_angled")
    assert not r.ok and not r.complete
    assert r.diagnostics[-1].code == code
    assert r.diagnostics[-1].line == 2


@pytest.mark.parametrize(
    "source",
    (
        "G81 Z-2 R1 F100\nG80 G43.4\nG1 X10 F100",
        "G41\nG40 G43.4\nG1 X10 F100",
        "G43.4\nG49\nG81 Z-2 R1 F100",
    ),
)
def test_tcp_explicit_cancellation_restores_supported_modes(source):
    r = execute(source + "\nM30", language="fanuc_mill", kinematics="5ax_table_bc_angled")
    assert r.ok and r.complete, r.diagnostics


@pytest.mark.parametrize(
    "dialect,command,code",
    (
        ("fanuc", "G53 G0 Z0", "G53"),
        ("fanuc", "G53 G0 Z500", "G53"),
        ("fanuc", "G91 G28 Z0", "G28"),
        ("fanuc", "G91 G28 Z10", "G28"),
        ("sinumerik", "G0 SUPA Z0", "SUPA"),
        ("sinumerik", "G0 SUPA Z500", "SUPA"),
    ),
)
@pytest.mark.parametrize("offset", ((0, 0, 0), (40, -25, 80)))
@pytest.mark.parametrize("profile,rotary", ((None, ""), ("4ax_table_b", "B30")))
def test_home_event_has_machine_target_independent_of_wcs(dialect, command, code, offset, profile, rotary):
    prefix = "G90 G0 " + rotary + "\n" if rotary else "G90\n"
    r = execute(
        prefix + "G0 X10 Y20 Z100\n" + command + "\nM30",
        language="fanuc_mill",
        source_dialect=dialect,
        kinematics=profile,
        home_z=500,
        wcs_offsets={54: offset},
    )
    assert r.ok and r.complete, r.diagnostics
    event = next(e for e in r.events if e.reference)
    assert event.kind == "home_return" and event.code == code
    assert event.axes == ("Z",) and event.reference.home_axes == ("Z",)
    assert event.reference.target[2] == 500
    assert event.reference.coordinate_space == "machine"
    assert event.reference.offset == offset
    if code == "G28":
        assert event.reference.intermediate is not None


@pytest.mark.parametrize("command", ("G53 G0 Z0", "G91 G28 Z0", "G91 G28 Z10", "G90 G28 Z0", "G53 G0 Z350"))
@pytest.mark.parametrize("target", ("fanuc_mill", "sinumerik_iso", "sinumerik_840d"))
@pytest.mark.parametrize("incremental", (False, True))
def test_reference_export_preserves_machine_commands_and_following_moves(command, target, incremental):
    source = "G90 G0 X10 Y20 Z100\n" + command + "\nG90 G1 Z120 F100\nM30"
    r = execute(source, language="fanuc_mill", home_z=500, wcs_offsets={54: (40, -25, 80)})
    text = convert_resolved_program(r, target, ExportOptions(delimiter=True, incremental=incremental))
    machine = [line for line in text.splitlines() if any(code in line for code in ("G53", "G28", "SUPA"))]
    assert machine, text
    assert all("X" not in line and "Y" not in line for line in machine), text
    replay = execute(
        text,
        language="fanuc_mill",
        source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc",
        home_z=500,
    )
    assert replay.ok and replay.complete, (text, replay.diagnostics)
    assert len(r.motions) == len(replay.motions), text
    for original, exported in zip(r.motions, replay.motions):
        assert point(original) == pytest.approx(point(exported), abs=0.002)
        assert point(original, True) == pytest.approx(point(exported, True), abs=0.002)
    assert any(e.reference for e in replay.events)


@pytest.mark.parametrize("target", ("fanuc_mill", "sinumerik_840d"))
def test_two_axis_home_stays_one_simultaneous_command(target):
    r = execute(
        "G90 G0 X10 Y20 Z100\nG53 G0 X0 Y0\nG1 Z120 F100\nM30",
        language="fanuc_mill",
        home_x=100,
        home_y=200,
        home_z=500,
    )
    text = convert_resolved_program(r, target, ExportOptions(delimiter=True))
    references = [line for line in text.splitlines() if "G53" in line or "SUPA" in line]
    assert len(references) == 1 and "X0" in references[0] and "Y0" in references[0], text
    replay = execute(
        text,
        language="fanuc_mill",
        source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc",
        home_x=100,
        home_y=200,
        home_z=500,
    )
    assert replay.ok and replay.complete
    assert point(replay.motions[1], True) == pytest.approx(point(r.motions[1], True))


def test_reference_noop_preserves_home_command():
    r = execute("G90 G0 Z500\nG53 G0 Z0\nM30", language="fanuc_mill", home_z=500)
    event = next(e for e in r.events if e.reference)
    assert event.kind == "home_return" and event.reference.segments == ()
    text = convert_resolved_program(r, "fanuc_mill", ExportOptions(delimiter=True))
    assert "G53 Z0" in text


def test_partial_home_is_not_serialized_as_whole_home():
    r = execute("G90 G0 X10 Y20 Z100\nG53 G0 X0 Z350\nM30", language="fanuc_mill", home_x=100, home_z=500)
    event = next(e for e in r.events if e.reference)
    assert event.reference.home_axes == ("X",)
    text = convert_resolved_program(r, "fanuc_mill", ExportOptions(delimiter=True))
    assert "G53 G0 X100 Z350" in text


@pytest.mark.parametrize("target", ("fanuc_mill", "sinumerik_840d"))
def test_g53_feed_preserves_units_and_feed_mode(target):
    r = execute("G90 G0 Z100\nG95 G53 G1 Z200 F0.2 S1000\nG1 Z120\nM30", language="fanuc_mill", home_z=500)
    text = convert_resolved_program(r, target, ExportOptions(delimiter=True, output_unit_scale=25.4))
    replay = execute(
        text,
        language="fanuc_mill",
        source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc",
        home_z=500,
    )
    assert replay.ok and replay.complete, (text, replay.diagnostics)
    assert replay.motions[1].feed_mode == "per_revolution"
    assert replay.motions[1].feed == pytest.approx(0.2, abs=0.00002)
    assert point(replay.motions[-1], True) == pytest.approx(point(r.motions[-1], True), abs=0.0001)


@pytest.mark.parametrize(
    "command,dialect",
    (("G0 SUPA X50 Y40 A30 C45", "sinumerik"), ("G53 G0 X50 Y40 A30 C45", "fanuc"), ("G91 G28 Z0 A0 C0", "fanuc")),
)
@pytest.mark.parametrize("target", ("fanuc_mill_multiaxis", "sinumerik_840d_multiaxis"))
@pytest.mark.parametrize("incremental", (False, True))
def test_machine_reference_rotary_axes_stay_in_one_command(command, dialect, target, incremental):
    source = "G90 G0 A20 C20\nG0 X10 Y20 Z100\n" + command + "\nG90 G0 X20 Y30 Z120\nG1 X25 F100\nM30"
    r = execute(source, language="fanuc_mill", source_dialect=dialect, kinematics="5ax_table_ac_angled", home_z=500)
    assert r.ok and r.complete, r.diagnostics
    text = convert_resolved_program(r, target, ExportOptions(delimiter=True, incremental=incremental))
    commands = [line for line in text.splitlines() if any(code in line for code in ("G53", "G28", "SUPA"))]
    assert len(commands) == 1 and "A" in commands[0] and "C" in commands[0], text
    replay = execute(
        text,
        language="fanuc_mill",
        source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc",
        kinematics="5ax_table_ac_angled",
        home_z=500,
    )
    assert replay.ok and replay.complete, (text, replay.diagnostics)
    assert replay.rotary_angles == r.rotary_angles, text
    assert len(replay.motions) == len(r.motions), text
    for a, b in zip(r.motions, replay.motions):
        assert point(a) == pytest.approx(point(b), abs=0.0001), text
        assert point(a, True) == pytest.approx(point(b, True), abs=0.0001), text


def test_machine_zero_cannot_silently_turn_into_configured_home():
    result = execute("G90 G0 Z100\nG91 G53 G0 Z-100\nM30", language="fanuc_mill", home_z=500)
    assert result.ok and result.complete
    event = next(event for event in result.events if event.reference is not None)
    assert event.reference.target[2] == 0 and event.reference.home_axes == ()
    with pytest.raises(ExportLimitation) as caught:
        convert_resolved_program(result, "fanuc_mill")
    assert caught.value.code == "UNSUPPORTED_REFERENCE_ZERO_EXPANDED_EXPORT"


@pytest.mark.parametrize(
    "source,code",
    (
        ("G53 G2 Z100 I5", "UNSUPPORTED_G53_MOTION"),
        ("G28 A10", "UNSUPPORTED_REFERENCE_ROTARY_INTERMEDIATE"),
    ),
)
def test_reference_rejects_unmodeled_motion_before_emitting_an_event(source, code):
    result = execute(source + "\nM30", language="fanuc_mill", kinematics="5ax_table_ac_angled", home_z=500)
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == code
    assert not any(event.reference is not None for event in result.events)
