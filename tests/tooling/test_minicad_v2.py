"""Strict physical geometry exchange independent of the MiniCAD installation."""

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

from app.gcode.execution.program import execute_program
from app.integration.minicad_bundle import apply_bundle, read_bundle
from app.tools.discovery_rules import _migrate_thread_mill_rule, default_profile, validate_profile
from app.tools.milling_geometry import milling_tool_profile
from app.tools.validation import normalized_program_milling_tools
from app.ui.dialogs.tool_dialogs import _MillingToolEditor
from app.ui.plot.milling_tool_preview import MillingToolPreviewItem


def payload(tmp_path, kind="thread_mill"):
    nc = b"G21 G90 G54\nT1 M6\nM30\n"
    (tmp_path / "program.nc").write_bytes(nc)
    tool = {
        "number": 1,
        "name": "Physical cutter",
        "h": 7,
        "d": 8,
        "type": kind,
        "diameter": 10,
        "length": 50,
        "fluteLength": 30,
        "bodyLength": 20,
        "shankDiameter": 6,
        "cornerRadius": 0,
    }
    if kind == "thread_mill":
        tool.update(threadProfile="single_form", threadRootDiameter=8, threadAngle=60, threadTipWidth=0.1)
    return {
        "version": 2,
        "dialect": "fanuc_mill",
        "units": "mm",
        "nc": "program.nc",
        "stock": {"xmin": -20, "xmax": 20, "ymin": -20, "ymax": 20, "zmin": -10, "zmax": 0},
        "tools": [tool],
        "coordinates": {"wcs": "G54", "x": 0, "y": 0, "z": 0},
        "sha256": {"program.nc": hashlib.sha256(nc).hexdigest()},
    }


def load(tmp_path, data):
    path = tmp_path / "simulation.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return read_bundle(path)


def test_thread_profile_normalization_preview_and_program_assignment(tmp_path):
    app = QApplication.instance() or QApplication([])
    data = payload(tmp_path)
    bundle = load(tmp_path, data)
    tool = bundle.tools["T1"]
    profile = milling_tool_profile(tool)
    assert profile[0] == (0, 4)
    assert max(radius for _, radius in profile) == 5
    assert profile[-1] == (50, 3)
    assert len(profile) > 4
    assert normalized_program_milling_tools(bundle.tools)["T1"]["threadProfile"] == "single_form"
    item = MillingToolPreviewItem()
    assert item.show_tool(tool, (3, 4, 5))
    vertices = item.meshes[0].opts["meshdata"].vertexes()
    assert float(vertices[:, 2].max()) == 50
    assert float(vertices[:, 2].min()) == 0
    assert item.transform().column(3).z() == 5
    library = {"T1": {"type": "mill_flat", "diameter": 99}}
    window = SimpleNamespace(millingTools={}, millingToolLibrary=deepcopy(library), wcsOffsets={"G54": (99, 0, 0)})
    apply_bundle(window, bundle)
    assert window.millingTools == bundle.tools
    assert window.millingToolLibrary == library
    assert window.wcsOffsets == {"G54": (99, 0, 0)}
    window.millingTools["T1"]["diameter"] = 12
    assert bundle.tools["T1"]["diameter"] == 10
    assert app is not None


@pytest.mark.parametrize(
    "change",
    (
        lambda d: d["tools"][0].pop("fluteLength"),
        lambda d: d["tools"][0].update(length=51),
        lambda d: d["tools"][0].update(diameter=True),
        lambda d: d["tools"][0].update(threadProfile="unknown"),
        lambda d: d["tools"].append(deepcopy(d["tools"][0])),
        lambda d: d["tools"][0].update(number=2),
        lambda d: d["tools"][0].update(threadRootDiameter=20),
        lambda d: d["tools"][0].update(shankDiameter=float("nan")),
        lambda d: d["coordinates"].update(x=20),
        lambda d: d["sha256"].update({"program.nc": "0" * 64}),
        lambda d: d.update(dialect="sinumerik"),
        lambda d: d["tools"][0].update(cuttingHeight=999),
        lambda d: d["stock"].pop("xmin"),
        lambda d: d["coordinates"].pop("z"),
    ),
)
def test_malformed_v2_rejected(tmp_path, change):
    data = payload(tmp_path)
    change(data)
    with pytest.raises(ValueError):
        load(tmp_path, data)


def test_legacy_v1_still_loads(tmp_path):
    data = payload(tmp_path, "mill_flat")
    data.update(version=1, tool={"number": 1, "diameter": 10, "type": "mill_flat"})
    bundle = load(tmp_path, data)
    assert bundle.version == 1
    assert bundle.tool_diameter == 10


def test_thread_editor_retains_profile_and_shank(tmp_path):
    app = QApplication.instance() or QApplication([])
    tool = load(tmp_path, payload(tmp_path)).tools["T1"]
    editor = _MillingToolEditor(tool_code="T1", spec=tool)
    key, result = editor.value()
    assert key == "T1"
    for field in ("threadProfile", "threadRootDiameter", "threadAngle", "threadTipWidth", "shankDiameter"):
        assert result[field] == tool[field]
    assert app is not None


def test_bundle_table_is_authoritative_over_comment_inference(tmp_path):
    bundle = load(tmp_path, payload(tmp_path))
    rules = default_profile()
    for entry in rules["types"]:
        if entry[1] == "thread_mill":
            entry[0] = "SPECIAL"
    source = "G21 G90 G54\nT1 M6 (SPECIAL)\nS1000 M3\nG0 X0 Y0 Z5\nG1 Z-1 F100\nG0 Z5\nM5\nM30\n"
    result, tools, inferred = execute_program(
        source, language="fanuc_mill", current_tools=bundle.tools, discovery_rules=rules, authoritative_tools=True
    )
    assert result.ok and result.complete
    assert tools == bundle.tools and inferred == {}


def test_old_recognition_settings_keep_user_rules_when_type_is_added():
    profile = default_profile()
    profile["types"] = [entry for entry in profile["types"] if entry[1] != "thread_mill"]
    profile["types"][0][0] = "CUSTOM"
    _migrate_thread_mill_rule(profile)
    assert profile["types"][0][0] == "CUSTOM"
    assert validate_profile(profile) == profile


def test_unsplit_legacy_length_and_explicit_shank_preview():
    app = QApplication.instance() or QApplication([])
    item = MillingToolPreviewItem()
    assert item.show_tool({"type": "mill_flat", "diameter": 10, "length": 50, "shankDiameter": 10}, (0, 0, 0))
    assert item.meshes
    assert app is not None
