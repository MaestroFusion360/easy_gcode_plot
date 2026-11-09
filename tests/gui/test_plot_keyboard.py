"""Keyboard camera controls must stay inactive in the fixed lathe view."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QQuaternion
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    "modifier",
    (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier),
)
def test_arrow_keys_do_not_orbit_the_lathe_plot(qt_app, modifier):
    window = MainWindow()
    try:
        window.ui.actionLatheMode.setChecked(True)
        qt_app.processEvents()
        view = window.ui.graphicsView
        assert view.opts["rotationMethod"] == "quaternion"
        before = QQuaternion(view.opts["rotation"])

        for key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            QTest.keyPress(view, key, modifier)
            QTest.keyRelease(view, key, modifier)
            qt_app.processEvents()

        assert QQuaternion(view.opts["rotation"]) == before
        assert not view.keysPressed
    finally:
        window.deleteLater()


def test_arrow_keys_still_orbit_the_milling_plot(qt_app):
    window = MainWindow()
    try:
        window.ui.actionLatheMode.setChecked(False)
        window.view3d()
        qt_app.processEvents()
        view = window.ui.graphicsView
        assert view.opts["rotationMethod"] == "euler"
        before = tuple(view.viewMatrix().data())

        QTest.keyPress(view, Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier)
        QTest.keyRelease(view, Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier)
        qt_app.processEvents()

        assert tuple(view.viewMatrix().data()) != before
    finally:
        window.deleteLater()
