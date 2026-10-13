"""Stock-to-scene integration, cancellation and ownership without a GPU dependency."""

# pylint: disable=protected-access

from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.gcode.stock.milling_stock_types import MillingStockSnapshot, MillingStockSpec
from app.main_window import MainWindow
from app.ui.windows import stock_mesh_insert


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def capture_window(qt_app, monkeypatch):
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(False)
    window.ui.horizontalSlider.setMaximum(1)
    window.ui.horizontalSlider.setValue(1)
    stock = MillingStockSnapshot(MillingStockSpec(10, 12, 20, 22, -5, 0), np.zeros((3, 3)), np.zeros((3, 3)), 1, 1)
    window._stock_animation_active = True
    window._stock_timeline = SimpleNamespace(motion_count=2)
    window._playback_movements = [SimpleNamespace(motion_end=2)]
    window._milling_stock_item = SimpleNamespace(calculated_snapshot=lambda _timeline, cancelled: stock)
    window.ui.actionSaveStockStl.setEnabled(True)
    window.ui.actionInsertStockMesh.setEnabled(True)
    monkeypatch.setattr(window, "_pause_playback", lambda: None)
    monkeypatch.setattr(window, "_cancel_milling_seek", lambda: True)
    monkeypatch.setattr(window, "fitToView", lambda: None)

    def execute(owner, function, data, options, _cancel, **_kwargs):
        assert owner._stock_export_active
        assert not owner.ui.horizontalSlider.isEnabled()
        assert not owner.ui.actionInsertStockMesh.isEnabled()
        return function(data, **options)

    monkeypatch.setattr(stock_mesh_insert, "run_execution", execute)
    yield window, stock
    window._stock_animation_active = False
    window._milling_stock_item = None
    window.ui.editor.setModified(False)
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def test_insert_stock_snapshot_is_an_independent_aligned_stl_object(capture_window, tmp_path, monkeypatch):
    window, stock = capture_window

    def unexpected_prompt(*_args):
        pytest.fail("An exact stock mesh must not require simplification confirmation")

    monkeypatch.setattr(stock_mesh_insert.QMessageBox, "warning", unexpected_prompt)
    assert stock_mesh_insert.insert_stock_mesh(window)
    assert len(window._stl_entries) == 1
    entry = window._stl_entries[0]
    assert entry.overlay.item in window.ui.graphicsView.items
    assert entry.obj.mesh.bounds == ((10, 12), (20, 22), (-5, 0))
    triangles = entry.obj.world_triangles().copy()
    stock.height[:] = -5
    np.testing.assert_array_equal(entry.obj.world_triangles(), triangles)
    assert not list(tmp_path.glob("*.stl"))
    assert not window._stock_export_active
    assert window.ui.horizontalSlider.isEnabled() and window.ui.actionInsertStockMesh.isEnabled()


def test_insert_waits_for_the_selected_frame(capture_window):
    window, _stock = capture_window
    window._stock_timeline.motion_count = 0
    assert not stock_mesh_insert.insert_stock_mesh(window)
    assert not window._stl_entries
    assert "selected stock frame" in window.ui.statusbar.toolTip()


def test_insert_action_follows_stl_export_and_inserts_at_final_frame(capture_window):
    window, _stock = capture_window
    assert window.ui.horizontalSlider.value() == window.ui.horizontalSlider.maximum()
    window.ui.actionSaveStockStl.setEnabled(False)
    assert not window.ui.actionInsertStockMesh.isEnabled()
    window.ui.actionSaveStockStl.setEnabled(True)
    assert window.ui.actionInsertStockMesh.isEnabled()

    window.ui.actionInsertStockMesh.trigger()

    assert len(window._stl_entries) == 1
    assert window._stl_entries[0].obj.mesh.bounds == ((10, 12), (20, 22), (-5, 0))
    window._milling_stock_item = None
    window._leave_stock_animation(restore_plot=False)
    assert not window.ui.actionSaveStockStl.isEnabled()
    assert not window.ui.actionInsertStockMesh.isEnabled()
    assert len(window._stl_entries) == 1


def test_failed_capture_restores_controls_and_does_not_insert(capture_window, monkeypatch):
    window, _stock = capture_window

    def cancelled(*_args, **_kwargs):
        raise InterruptedError("cancelled")

    monkeypatch.setattr(stock_mesh_insert, "run_execution", cancelled)
    assert not stock_mesh_insert.insert_stock_mesh(window)
    assert not window._stl_entries and not window._stock_export_active
    assert window.ui.horizontalSlider.isEnabled() and window.ui.actionInsertStockMesh.isEnabled()


@pytest.mark.parametrize("accepted", [True, False])
def test_oversized_stock_requires_confirmation_before_insertion(capture_window, monkeypatch, accepted):
    window, stock = capture_window
    x, y = np.meshgrid(np.linspace(0, 2, 65), np.linspace(0, 2, 65))
    height = (-2 + np.sin(x * 17) * np.sin(y * 19)).astype(np.float32)
    stock = MillingStockSnapshot(stock.spec, height, height * 0, 2 / 64, 2 / 64)
    window._milling_stock_item.calculated_snapshot = lambda _timeline, cancelled: stock
    original = stock.height.copy()
    monkeypatch.setattr(stock_mesh_insert, "MAX_STL_TRIANGLES", 4096)
    prompts = []

    def confirm(owner, _title, message, buttons, default):
        assert owner is window and not window._stl_entries
        assert window._stock_export_active
        assert buttons == QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        assert default == QMessageBox.StandardButton.Cancel
        prompts.append(message)
        return QMessageBox.StandardButton.Ok if accepted else QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(stock_mesh_insert.QMessageBox, "warning", confirm)
    assert stock_mesh_insert.insert_stock_mesh(window) == accepted
    assert len(prompts) == 1
    assert "Quality has been reduced" in prompts[0]
    assert len(window._stl_entries) == int(accepted)
    if accepted:
        assert window._stl_entries[0].obj.mesh.triangle_count <= 4096
    np.testing.assert_array_equal(stock.height, original)
    assert stock.nx == stock.ny == 64
    assert not window._stock_export_active
    assert window.ui.horizontalSlider.isEnabled() and window.ui.actionInsertStockMesh.isEnabled()
