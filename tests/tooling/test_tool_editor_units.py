"""Inches display switch in the turning and milling tool editors."""

# pylint: disable=protected-access

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.dialogs.tool_dialogs import _MillingToolEditor, _TurningToolEditor

MM_PER_INCH = 25.4


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_turning_editor_exposes_inches_switch(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(window)

    assert editor.inches.isEnabled()
    assert not editor.inches.isHidden()
    assert editor.inches.text() == "Inches"

    editor.deleteLater()
    window.deleteLater()


def test_milling_editor_exposes_inches_switch(qt_app):
    window = MainWindow()
    editor = _MillingToolEditor(window)

    assert editor.inches.isEnabled()
    assert not editor.inches.isHidden()
    assert editor.inches.text() == "Inches"

    editor.deleteLater()
    window.deleteLater()


def test_turning_editor_inches_toggle_is_display_only(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(
        window,
        tool_code="T0101",
        spec={"type": "diamond_80", "noseRadius": 0.4, "insertLength": 12.0, "tipOrientation": 3},
    )

    editor.inches.setChecked(True)
    assert editor.noseRadius.value() == pytest.approx(round(0.4 / MM_PER_INCH, 5), abs=1e-9)
    assert editor._form.labelForField(editor.noseRadius).text() == "Nose radius, in"
    # The serialized geometry stays metric even while the form shows inches.
    assert editor.value()[1]["noseRadius"] == pytest.approx(0.4, abs=1e-3)
    assert editor.value()[1]["insertLength"] == pytest.approx(12.0, abs=1e-3)

    editor.inches.setChecked(False)
    assert editor.noseRadius.value() == pytest.approx(0.4, abs=1e-3)
    assert editor._form.labelForField(editor.noseRadius).text() == "Nose radius, mm"

    editor.deleteLater()
    window.deleteLater()


def test_milling_editor_inches_toggle_is_display_only(qt_app):
    window = MainWindow()
    editor = _MillingToolEditor(
        window,
        tool_code="T1",
        spec={"type": "mill_flat", "diameter": 10.0, "length": 50.0},
    )

    editor.inches.setChecked(True)
    assert editor.diameter.value() == pytest.approx(round(10.0 / MM_PER_INCH, 5), abs=1e-9)
    # The serialized geometry stays metric even while the form shows inches.
    assert editor.value()[1]["diameter"] == pytest.approx(10.0, abs=1e-3)
    assert editor.value()[1]["length"] == pytest.approx(50.0, abs=1e-3)

    editor.inches.setChecked(False)
    assert editor.diameter.value() == pytest.approx(10.0, abs=1e-3)
    assert editor.value()[1]["diameter"] == pytest.approx(10.0, abs=1e-3)

    editor.deleteLater()
    window.deleteLater()
