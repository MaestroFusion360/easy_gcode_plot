"""Real Fusion AC/BC programs through the public Expanded Export and Trace CLI."""

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/milling"
# Input XYZ has 0.001 mm precision; output XYZ has six decimal places.
TCP_TOLERANCE_MM = 0.000002
AXIS_TOLERANCE_DEG = 0.000002


def _cli(arguments):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "cli_main.py"), *map(str, arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Result: CLEAN" in result.stdout, result.stdout


def _trace(source, output, kinematics):
    _cli(["trace", source, "--lang", "fanuc_mill", "--kinematics", kinematics, "-o", output])
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["ok"] and document["complete"]
    assert document["diagnostics"] == []
    assert document["kinematics_profile"] == kinematics
    return document


def _axis_error_degrees(first, second):
    if first is None or second is None:
        assert first == second
        return 0.0
    a, b = [row[2] for row in first], [row[2] for row in second]
    # atan2 avoids acos amplification near an exactly matching unit vector.
    cross = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    return math.degrees(math.atan2(math.hypot(*cross), sum(x * y for x, y in zip(a, b, strict=True))))


def _motion_state(trace, motion):
    abc, modes = [0.0, 0.0, 0.0], {"TCP": False, "TWP": False}
    for event in trace["events"]:
        if event["source_block"] > motion["source_block"]:
            continue
        if event["new_abc"] is not None:
            abc = event["new_abc"]
        for prefix, mode in (("TCP_CONTROL", "TCP"), ("TILTED_WORK_PLANE", "TWP")):
            if event["kind"].startswith(prefix):
                modes[mode] = event["kind"].endswith("_ON")
    controls = [s["kind"] for s in trace["signals"] if s["block_index"] <= motion["source_block"]]
    return abc, modes, controls


def _compare(source, target):
    assert len(source["motions"]) == len(target["motions"]), "Lost or additional movements"

    def mode_edges(trace):
        return [e["kind"] for e in trace["events"] if e["kind"].startswith(("TCP_CONTROL_", "TILTED_WORK_PLANE_"))]

    assert mode_edges(source) == mode_edges(target)
    source_frames = [e for e in source["events"] if e["kind"] == "TILTED_WORK_PLANE_ON"]
    target_frames = [e for e in target["events"] if e["kind"] == "TILTED_WORK_PLANE_ON"]
    for a, b in zip(source_frames, target_frames, strict=True):
        assert a["twp_origin"] == pytest.approx(b["twp_origin"], abs=TCP_TOLERANCE_MM)
        for row_a, row_b in zip(a["twp_orientation"], b["twp_orientation"], strict=True):
            assert row_a == pytest.approx(row_b, abs=1e-8)
    deviations = []
    orientation_errors = []
    for index, (a, b) in enumerate(zip(source["motions"], target["motions"], strict=True)):
        error = max(
            math.dist([a[f"{edge}_{axis}"] for axis in "xyz"], [b[f"{edge}_{axis}"] for axis in "xyz"])
            for edge in ("start", "end")
        )
        assert error <= TCP_TOLERANCE_MM, (index, a["source_raw"], b["source_raw"], error)
        deviations.append(error)
        for key in ("tool_orientation", "start_tool_orientation"):
            angle = _axis_error_degrees(a[key], b[key])
            assert angle <= AXIS_TOLERANCE_DEG, (index, key, angle)
            orientation_errors.append(angle)
        for key in ("move", "feed", "feed_mode", "tool", "spindle_rpm"):
            assert a[key] == b[key], (index, key, a[key], b[key])
        abc_a, modes_a, controls_a = _motion_state(source, a)
        abc_b, modes_b, controls_b = _motion_state(target, b)
        assert abc_a == pytest.approx(abc_b, abs=AXIS_TOLERANCE_DEG)
        assert modes_a == modes_b, (index, modes_a, modes_b)
        assert controls_a == controls_b, (index, controls_a, controls_b)
    return {
        "max_tcp_mm": max(deviations),
        "max_tcp_motion": deviations.index(max(deviations)),
        "max_axis_deg": max(orientation_errors),
        "motions": len(deviations),
    }


@pytest.mark.parametrize("kin", ("ac", "bc"))
@pytest.mark.parametrize("controller", ("fanuc", "sin840d"))
def test_real_indexed_cli_conversion(kin, controller):
    folder, extension, target = (
        ("fanuc", "nc", "sinumerik_840d_multiaxis")
        if controller == "fanuc"
        else ("sinumerik", "mpf", "fanuc_mill_multiaxis")
    )
    source = FIXTURES / folder / f"test_5ax_{kin}_{controller}.{extension}"
    # Keep every trace, export and diagnostic in the requested tmp directory.
    output = ROOT / "tmp/conversion_tests" / f"{kin}_{controller}"
    output.mkdir(parents=True, exist_ok=True)
    kinematics = f"5ax_table_{kin}"
    original = _trace(source, output / "source.json", kinematics)
    assert original["source_dialect"] == ("fanuc" if controller == "fanuc" else "sinumerik")
    converted = output / ("converted.mpf" if controller == "fanuc" else "converted.nc")
    _cli(
        [
            "export",
            source,
            "--mode",
            "expanded",
            "--lang",
            "fanuc_mill",
            "--kinematics",
            kinematics,
            "--post-profile",
            target,
            "--no-comments",
            "-o",
            converted,
        ]
    )
    replay = _trace(converted, output / "replay.json", kinematics)
    assert replay["source_dialect"] != original["source_dialect"]
    report = _compare(original, replay)
    text = converted.read_text(encoding="utf-8")
    commands = (
        ("CYCLE800(", "CYCLE800()", "D1\nTRAORI", "TRAFOOF\nD0")
        if controller == "fanuc"
        else ("G68.2", "G53.1", "G69", "G43.4 H2", "G49")
    )
    assert all(command in text for command in commands)
    if controller == "sin840d":
        lines = text.splitlines()
        first_work_z = next(i for i, line in enumerate(lines) if "Z" in line and "X" in line and line.startswith("G0 "))
        assert lines.index("G43 H2") < first_work_z < lines.index("G43.4 H2")
    (output / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


@pytest.mark.parametrize("kin", ("ac", "bc"))
def test_original_controller_pair_working_path(kin):
    output = ROOT / "tmp/conversion_tests" / f"pair_{kin}"
    output.mkdir(parents=True, exist_ok=True)
    a = _trace(FIXTURES / "fanuc" / f"test_5ax_{kin}_fanuc.nc", output / "fanuc.json", f"5ax_table_{kin}")
    b = _trace(FIXTURES / "sinumerik" / f"test_5ax_{kin}_sin840d.mpf", output / "sinumerik.json", f"5ax_table_{kin}")
    # Both CAM posts share the approach, cut and Z retract. FANUC additionally
    # returns X/Y home, so their complete programs intentionally differ.
    assert len(a["motions"]) == len(b["motions"]) + 1
    for first, second in zip(a["motions"][:-1], b["motions"], strict=True):
        for edge in ("start", "end"):
            assert (
                math.dist([first[f"{edge}_{axis}"] for axis in "xyz"], [second[f"{edge}_{axis}"] for axis in "xyz"])
                <= TCP_TOLERANCE_MM
            )
        assert _axis_error_degrees(first["tool_orientation"], second["tool_orientation"]) <= AXIS_TOLERANCE_DEG
        assert first["move"] == second["move"]
