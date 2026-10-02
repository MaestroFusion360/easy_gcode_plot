"""Editing, unit display and library export of the milling length split."""

# pylint: disable=protected-access

import csv
import json

import pytest
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from app.tools.definitions import DEFAULT_MILLING_TOOL
from app.ui.dialogs.tool_dialogs import _export_tool_library, _MillingToolEditor
from app.ui.dialogs.tool_library_dialog import ToolLibraryDialog
from app.ui.plot.milling_tool_preview import MillingToolPreviewItem


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_new_editor_has_editable_split_and_read_only_total(qt_app):
    editor = _MillingToolEditor()
    assert editor.length.isReadOnly()
    assert editor.value()[1] == DEFAULT_MILLING_TOOL
    editor.fluteLength.setValue(24)
    editor.bodyLength.setValue(36)
    assert editor.length.value() == 60
    assert editor.value()[1]["length"] == 60
    editor.validateAndAccept()
    assert editor.result() == QDialog.DialogCode.Accepted
    editor.deleteLater()


def test_legacy_editor_retains_total_until_user_defines_split(qt_app):
    editor = _MillingToolEditor(spec={"type": "mill_flat", "diameter": 10, "length": 73})
    assert not editor.ui.lengthsHint.isHidden()
    assert editor.fluteLength.value() == 0
    assert editor.bodyLength.value() == 0
    editor.inches.setChecked(True)
    editor.inches.setChecked(False)
    assert editor.value()[1]["length"] == pytest.approx(73, abs=1e-3)
    assert "fluteLength" not in editor.value()[1]
    editor.description.setText("Old cutter")
    editor.validateAndAccept()
    assert editor.result() == QDialog.DialogCode.Accepted
    editor.fluteLength.setValue(25)
    editor.bodyLength.setValue(48)
    assert editor.ui.lengthsHint.isHidden()
    assert editor.value()[1]["fluteLength"] == 25
    assert editor.value()[1]["bodyLength"] == 48
    assert editor.value()[1]["length"] == 73
    editor.deleteLater()


def test_split_editor_units_remain_metric_in_saved_definition(qt_app):
    editor = _MillingToolEditor(
        spec={"type": "mill_flat", "diameter": 10, "fluteLength": 25.4, "bodyLength": 12.7, "length": 999}
    )
    assert editor.length.value() == pytest.approx(38.1)
    editor.inches.setChecked(True)
    assert editor.fluteLength.value() == 1
    assert editor.bodyLength.value() == 0.5
    assert editor.length.value() == 1.5
    editor.bodyLength.setValue(0.75)
    assert editor.length.value() == 1.75
    spec = editor.value()[1]
    assert spec["fluteLength"] == pytest.approx(25.4)
    assert spec["bodyLength"] == pytest.approx(19.05)
    assert spec["length"] == spec["fluteLength"] + spec["bodyLength"]
    editor.inches.setChecked(False)
    assert editor.length.value() == pytest.approx(44.45)
    assert editor.fluteLength.value() == pytest.approx(25.4)
    editor.deleteLater()


def test_partial_edit_of_legacy_lengths_requires_positive_flute(qt_app, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, message: messages.append(message))
    editor = _MillingToolEditor(spec={"type": "mill_flat", "diameter": 10, "length": 73})
    editor.bodyLength.setValue(20)
    editor.validateAndAccept()
    assert messages == ["Flute length must be greater than zero."]
    assert editor.result() != QDialog.DialogCode.Accepted
    editor.deleteLater()


@pytest.mark.parametrize("lengths", [{"fluteLength": 25}, {"fluteLength": 25, "bodyLength": -1}])
def test_invalid_split_is_not_opened_as_an_unsplit_default(qt_app, lengths):
    with pytest.raises(ValueError, match="Invalid milling tool lengths"):
        _MillingToolEditor(spec={"type": "mill_flat", "diameter": 10, "length": 73, **lengths})


@pytest.mark.parametrize("tool_type", ["face_mill", "slot_mill"])
def test_new_stepped_editor_uses_flute_instead_of_second_cutting_height(qt_app, tool_type):
    editor = _MillingToolEditor(spec={**DEFAULT_MILLING_TOOL, "type": tool_type})
    assert editor.cuttingHeight.isHidden()
    assert not editor.shankDiameter.isHidden()
    editor.fluteLength.setValue(12)
    editor.bodyLength.setValue(58)
    assert "cuttingHeight" not in editor.value()[1]
    assert editor.value()[1]["length"] == 70
    editor.deleteLater()


def test_split_change_rebuilds_preview_even_when_total_stays_same(qt_app):
    item = MillingToolPreviewItem()
    spec = {**DEFAULT_MILLING_TOOL, "type": "taper_ball_mill", "taperAngle": 6}
    assert item.show_tool(spec, (0, 0, 0))
    first_key = item.geometry_key
    mesh = item._meshes[0]
    assert item.show_tool({**spec, "fluteLength": 20, "bodyLength": 30}, (0, 0, 0))
    assert item.geometry_key != first_key
    assert item._meshes[0] is mesh


def test_library_summary_and_exports_include_partition(qt_app, tmp_path):
    spec = {**DEFAULT_MILLING_TOOL, "fluteLength": 25, "bodyLength": 15, "length": 40}
    assert ToolLibraryDialog._geometry("milling", spec) == "D10  R0  FL25  BL15  L40"
    json_path = tmp_path / "tools.json"
    csv_path = tmp_path / "tools.csv"
    _export_tool_library(str(json_path), "milling", {"T1": spec})
    _export_tool_library(str(csv_path), "milling", {"T1": spec})
    record = json.loads(json_path.read_text(encoding="utf-8"))["tools"][0]
    assert record["fluteLength"] == 25
    assert record["bodyLength"] == 15
    assert record["length"] == 40
    assert "shaftLength" not in record
    with csv_path.open(encoding="utf-8", newline="") as stream:
        record = next(csv.DictReader(stream))
    assert record["fluteLength"] == "25"
    assert record["bodyLength"] == "15"
    assert record["length"] == "40"
