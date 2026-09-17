"""Turning tool editor UI behavior."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.tool_dialogs import _TurningToolEditor


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_turning_tip_orientation_icons_are_visible_and_library_table_shows_orientation(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(window)
    assert [editor.tipOrientation.itemData(index) for index in range(editor.tipOrientation.count())] == [3, 4]
    assert all(not editor.tipOrientation.itemIcon(index).isNull() for index in range(editor.tipOrientation.count()))

    window.tools = {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 7}}
    window.toolLibraryDlg.refresh("turning", selected_program="T0101")
    geometry = window.toolLibraryDlg.pages["turning"]["program"].item(0, 2)
    assert geometry.text().startswith("P7")
    editor.deleteLater()
    window.deleteLater()


@pytest.mark.parametrize("direction", ["face", "od", "id"])
def test_groove_width_is_editable_and_saved(qt_app, direction):
    window = MainWindow()
    editor = _TurningToolEditor(window, tool_code="T0808")
    editor.categoryButtons["groove"].setChecked(True)
    editor.directionChecks[direction].setChecked(True)
    for key, checkbox in editor.directionChecks.items():
        if key != direction:
            checkbox.setChecked(False)
    editor.grooveType.setCurrentIndex(editor.grooveType.findData("groove"))
    editor.width.setValue(6.5)

    assert editor.width.isEnabled()
    expected = {"type": "groove", "applications": [direction], "width": 6.5}
    expected["noseRadius"] = 0.4
    if direction == "od":
        expected["tipOrientation"] = 3
        assert [editor.tipOrientation.itemText(index) for index in range(editor.tipOrientation.count())] == ["P3", "P4"]
    elif direction == "id":
        expected["tipOrientation"] = 2
        assert [editor.tipOrientation.itemText(index) for index in range(editor.tipOrientation.count())] == ["P1", "P2"]
    else:
        expected["tipOrientation"] = 3
        assert [editor.tipOrientation.itemText(index) for index in range(editor.tipOrientation.count())] == ["P2", "P3"]
    assert editor.value() == ("T0808", expected)
    editor.deleteLater()
    window.deleteLater()


def test_turning_editor_separates_categories_and_restores_triangle_insert(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(window)

    assert list(editor.categoryButtons) == ["insert", "groove", "thread", "drill", "tap"]
    assert editor.categoryButtons["thread"].isEnabled()
    assert editor.threadType.findData("thread") >= 0
    assert editor.insertType.findData("square") >= 0
    assert editor.insertType.findData("round") >= 0
    assert editor.insertType.findData("triangle") >= 0
    assert editor.grooveType.findData("groove") >= 0
    assert editor.threadHelp.isHidden()
    editor.deleteLater()
    window.deleteLater()


def test_turning_editor_serializes_thread_geometry(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(
        window,
        tool_code="T0909",
        spec={
            "type": "thread",
            "applications": ["od"],
            "insertLength": 12.0,
            "threadAngle": 60.0,
            "threadTipWidth": 0.8,
            "threadCornerRadius": 0.1,
            "tipOrientation": 8,
        },
    )

    assert editor.category() == "thread"
    assert editor.currentToolType() == "thread"
    assert editor.threadType.itemIcon(0).isNull()
    assert editor.categoryButtons["thread"].icon().isNull()
    assert editor.threadHelp.pixmap() is not None
    assert not editor.threadHelp.pixmap().isNull()
    assert not editor.threadHelp.isHidden()
    assert editor._form.labelForField(editor.threadCornerRadius).text() == "RC, mm"  # pylint: disable=protected-access
    assert editor.threadCornerRadius.decimals() == 3
    assert editor.value() == (
        "T0909",
        {
            "type": "thread",
            "applications": ["od"],
            "insertLength": 12.0,
            "threadAngle": 60.0,
            "threadTipWidth": 0.8,
            "threadCornerRadius": 0.1,
            "tipOrientation": 8,
        },
    )
    editor.deleteLater()
    window.deleteLater()


@pytest.mark.parametrize(
    ("direction", "orientations"),
    [("od", [3, 4]), ("id", [1, 2]), ("face", [3, 4])],
)
def test_turning_editor_auto_orientations_follow_machining_direction(qt_app, direction, orientations):
    window = MainWindow()
    editor = _TurningToolEditor(window)

    editor.directionChecks[direction].setChecked(True)
    for key, checkbox in editor.directionChecks.items():
        if key != direction:
            checkbox.setChecked(False)

    assert [editor.tipOrientation.itemData(index) for index in range(editor.tipOrientation.count())] == orientations
    assert all(value not in orientations for value in (5, 8, 9))
    editor.deleteLater()
    window.deleteLater()


@pytest.mark.parametrize(
    ("tool_type", "orientations"),
    [("diamond_35", [1, 2, 6, 7]), ("diamond_35", [3, 4, 7, 8])],
)
def test_diamond_35_uses_forming_tool_orientations(qt_app, tool_type, orientations):
    window = MainWindow()
    editor = _TurningToolEditor(
        window,
        tool_code="T0101",
        spec={"type": tool_type, "noseRadius": 0.4, "tipOrientation": orientations[0]},
    )

    assert editor.insertType.currentText() == "Diamond 35"
    assert [editor.tipOrientation.itemData(index) for index in range(editor.tipOrientation.count())] == orientations
    editor.deleteLater()
    window.deleteLater()


def test_turning_insert_combo_uses_insert_shape_names(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(window)

    labels = [editor.insertType.itemText(index) for index in range(editor.insertType.count())]
    assert labels == ["Diamond 80", "Diamond 35", "Square", "Round", "Triangle"]
    editor.deleteLater()
    window.deleteLater()


def test_turning_type_controls_expose_exactly_nine_canonical_types(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(window)
    combo_types = {
        combo.itemData(index)
        for combo in (editor.insertType, editor.grooveType, editor.threadType, editor.drillType, editor.tapType)
        for index in range(combo.count())
    }

    assert combo_types == {
        "diamond_80",
        "diamond_35",
        "square",
        "round",
        "triangle",
        "groove",
        "thread",
        "drill",
        "tap",
    }
    editor.deleteLater()
    window.deleteLater()


def test_od_and_id_checkboxes_merge_family_orientations_without_duplicate_shapes(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(window)
    editor.directionChecks["id"].setChecked(True)
    editor.insertType.setCurrentIndex(editor.insertType.findData("diamond_35"))

    labels = [editor.insertType.itemText(index) for index in range(editor.insertType.count())]
    orientations = [editor.tipOrientation.itemData(index) for index in range(editor.tipOrientation.count())]
    assert labels == ["Diamond 80", "Diamond 35", "Square", "Round", "Triangle"]
    assert orientations == [1, 2, 3, 4, 6, 7, 8]
    editor.tipOrientation.setCurrentIndex(editor.tipOrientation.findData(1))
    assert editor.value()[1]["type"] == "diamond_35"
    assert editor.value()[1]["applications"] == ["od", "id"]
    editor.tipOrientation.setCurrentIndex(editor.tipOrientation.findData(4))
    assert editor.value()[1]["type"] == "diamond_35"
    assert editor.value()[1]["applications"] == ["od", "id"]
    editor.deleteLater()
    window.deleteLater()


def test_switching_diamond_direction_keeps_shape_and_changes_internal_variant(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(window)
    editor.insertType.setCurrentIndex(editor.insertType.findData("diamond_35"))
    editor.directionChecks["id"].setChecked(True)
    editor.directionChecks["od"].setChecked(False)

    assert editor.insertType.currentText() == "Diamond 35"
    assert editor.insertType.currentData() == "diamond_35"
    assert editor.value()[1]["applications"] == ["id"]
    assert [editor.tipOrientation.itemData(index) for index in range(editor.tipOrientation.count())] == [1, 2, 6, 7]
    editor.deleteLater()
    window.deleteLater()


@pytest.mark.parametrize(
    ("tool_type", "direction", "orientations"),
    [
        ("round", "od", [8]),
        ("round", "id", [7]),
        ("square", "od", [3]),
        ("square", "id", [2]),
        ("triangle", "od", [3]),
        ("triangle", "id", [2]),
        ("thread", "od", [8]),
        ("thread", "id", [6]),
    ],
)
def test_shape_specific_auto_orientations(qt_app, tool_type, direction, orientations):
    window = MainWindow()
    editor = _TurningToolEditor(window)
    category = "thread" if tool_type == "thread" else "insert"
    editor.categoryButtons[category].setChecked(True)
    editor.directionChecks[direction].setChecked(True)
    for key in ("od", "id"):
        if key != direction:
            editor.directionChecks[key].setChecked(False)
    if category == "insert":
        editor.insertType.setCurrentIndex(editor.insertType.findData(tool_type))

    assert [editor.tipOrientation.itemData(index) for index in range(editor.tipOrientation.count())] == orientations
    editor.deleteLater()
    window.deleteLater()


def test_turning_editor_replaces_orientation_outside_auto_set(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(
        window,
        tool_code="T0101",
        spec={"type": "triangle", "noseRadius": 0.4, "tipOrientation": 9},
    )

    assert editor.tipOrientation.currentData() == 3
    assert editor.tipOrientation.currentText() == "P3"
    assert editor.value()[1]["tipOrientation"] == 3
    editor.deleteLater()
    window.deleteLater()


@pytest.mark.parametrize(
    ("tool_type", "expected"), [("diamond_80", 12.0), ("diamond_80", 12.0), ("diamond_35", 16.0), ("diamond_35", 16.0)]
)
def test_turning_editor_insert_length_defaults_and_serializes(qt_app, tool_type, expected):
    window = MainWindow()
    editor = _TurningToolEditor(
        window,
        tool_code="T0101",
        spec={"type": tool_type, "noseRadius": 0.4, "tipOrientation": 3 if tool_type.startswith("od") else 2},
    )

    assert editor.insertLength.value() == expected
    assert editor.value()[1]["insertLength"] == expected
    editor.deleteLater()
    window.deleteLater()
