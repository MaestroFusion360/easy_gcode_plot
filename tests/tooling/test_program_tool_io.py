"""Program tool JSON is lossless, deterministic and validated before use."""

import json
from copy import deepcopy

import pytest

from app.tools.definitions import DEFAULT_MILLING_TOOL, DEFAULT_TURNING_TOOL
from app.tools.program_io import read_program_tools, write_program_tools


@pytest.mark.parametrize(
    "kind,keys,base",
    [
        ("milling", ("T7", "FINISH TOOL"), DEFAULT_MILLING_TOOL),
        ("turning", ("T0202", "T0203"), DEFAULT_TURNING_TOOL),
    ],
)
def test_json_roundtrip_preserves_geometry_offsets_and_metadata(tmp_path, kind, keys, base):
    spec = {
        **base,
        "description": "Фреза / резец",
        "offsets": {"D": 2, "H": 7, "wear": -0.02},
        "metadata": {"manufacturer": "Workshop", "tags": ["rough", "finish"]},
    }
    tools = dict.fromkeys(keys, spec)
    before = deepcopy(tools)
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    write_program_tools(first, kind, tools)
    write_program_tools(second, kind, dict(reversed(list(tools.items()))))
    assert first.read_bytes() == second.read_bytes()
    assert read_program_tools(first, kind) == tools == before


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"version": 2, "kind": "milling", "tools": {}},
        {"version": 1, "kind": "turning", "tools": {}},
        {"version": 1, "kind": "milling", "tools": []},
        {"version": 1, "kind": "milling", "tools": {"T1": None}},
        {"version": 1, "kind": "milling", "tools": {"T1": {"type": "unknown"}}},
        {"version": 1, "kind": "milling", "tools": {"T1": {**DEFAULT_MILLING_TOOL, "diameter": -1}}},
        {"version": 1, "kind": "milling", "tools": {"T1": {**DEFAULT_MILLING_TOOL, "diameter": "oops"}}},
        {"version": 1, "kind": "milling", "tools": {"T1": {**DEFAULT_MILLING_TOOL, "metadata": float("inf")}}},
    ],
)
def test_reject_invalid_program_files(tmp_path, payload):
    source = tmp_path / "bad.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        read_program_tools(source, "milling")


@pytest.mark.parametrize(
    "text", ["{broken", '{"version":1,"version":1}', '{"version":1,"kind":"milling","tools":{},"metadata":1e999}']
)
def test_reject_malformed_duplicate_or_overflow_json(tmp_path, text):
    source = tmp_path / "bad.json"
    source.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        read_program_tools(source, "milling")


@pytest.mark.parametrize(
    "kind,tools,expected",
    [
        ("turning", {"T202": DEFAULT_TURNING_TOOL}, "T0202"),
        ("milling", {"T02": DEFAULT_MILLING_TOOL}, "T2"),
    ],
)
def test_import_normalizes_numeric_tool_aliases(tmp_path, kind, tools, expected):
    source = tmp_path / "alias.json"
    write_program_tools(source, kind, tools)
    assert list(read_program_tools(source, kind)) == [expected]


def test_conflicting_tool_aliases_are_rejected_before_write(tmp_path):
    target = tmp_path / "tools.json"
    target.write_text("previous", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate tool"):
        write_program_tools(target, "milling", {"T2": DEFAULT_MILLING_TOOL, "T02": DEFAULT_MILLING_TOOL})
    assert target.read_text() == "previous"


@pytest.mark.parametrize("filename", ["program.nc", "program.mpf", "program.txt", "program"])
def test_export_refuses_non_json_destinations_without_overwriting(tmp_path, filename):
    destination = tmp_path / filename
    original = b"G21\r\nG1 X10 F100\r\nM30\r\n"
    destination.write_bytes(original)

    with pytest.raises(ValueError, match=r"\.json file"):
        write_program_tools(destination, "milling", {"T1": DEFAULT_MILLING_TOOL})

    assert destination.read_bytes() == original


def test_export_accepts_uppercase_json_extension(tmp_path):
    destination = tmp_path / "tools.JSON"
    tools = {"T1": DEFAULT_MILLING_TOOL}
    write_program_tools(destination, "milling", tools)
    assert read_program_tools(destination, "milling") == tools
