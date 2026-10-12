"""Physical export tolerances, output units and edge limits."""

# pylint: disable=import-outside-toplevel,protected-access

from dataclasses import replace

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from app.gcode.stock import MillingStockSpec, MillingStockTimeline, write_milling_stock_stl
from app.gcode.stock.milling_stock_stl import StockStlOptions
from app.main_window import MainWindow
from app.ui.dialogs.stock_stl_export_dialog import StockStlExportDialog
from app.ui.plot.milling_stock_gpu import prepare_frame


@pytest.fixture(scope="session")
def export_qt_app():
    return QApplication.instance() or QApplication([])


def vertices(path):
    dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])
    return np.fromfile(path, dtype=dtype, offset=84)["vertices"].astype(float)


@pytest.mark.parametrize(
    "changes",
    [
        {"linear_deviation": 0},
        {"linear_deviation": 1.01},
        {"angular_deviation": 0.9},
        {"angular_deviation": 91},
        {"edge_length": 0.049},
        {"edge_length": 101},
        {"linear_deviation": float("nan")},
        {"units": "cm"},
    ],
)
def test_invalid_export_options_are_rejected(changes):
    with pytest.raises(ValueError):
        replace(StockStlOptions(), **changes).validate()


def test_edge_limit_and_inches_apply_to_the_whole_closed_stock(tmp_path, gpu_stock):
    timeline = MillingStockTimeline([], MillingStockSpec(0, 4, 0, 3, -2, 0, 1))
    gpu_stock.update(prepare_frame(timeline, 0.1, 1, lambda: False))
    stock = gpu_stock.snapshot(timeline)
    options = StockStlOptions(edge_length=1)
    mm, inches = tmp_path / "mm.stl", tmp_path / "in.stl"
    write_milling_stock_stl(mm, stock, options=options)
    write_milling_stock_stl(inches, stock, options=replace(options, units="in"))
    triangles = vertices(mm)
    np.testing.assert_allclose(vertices(inches) * 25.4, triangles, atol=1e-6)
    lengths = np.linalg.norm(triangles - np.roll(triangles, -1, axis=1), axis=2)
    assert lengths.max() <= 1.000001
    points = np.round(triangles.reshape(-1, 3), 6)
    _, indices = np.unique(points, axis=0, return_inverse=True)
    faces = indices.reshape(-1, 3)
    edges = np.sort(np.stack((faces, np.roll(faces, -1, axis=1)), axis=-1).reshape(-1, 2), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    assert np.all(counts == 2)


def test_dialog_units_preserve_metric_thresholds_and_values(export_qt_app):
    app = export_qt_app
    window = MainWindow()
    try:
        dialog = StockStlExportDialog(window)
        dialog.linear.setValue(0.001)
        dialog.edge.setValue(0.05)
        dialog.units.setCurrentIndex(1)
        assert dialog.options() == StockStlOptions("in", 0.001, 90, 0.05, calculated=True)
        dialog.units.setCurrentIndex(0)
        assert dialog.options() == StockStlOptions("mm", 0.001, 90, 0.05, calculated=True)
        assert dialog.linear.value() == 0.001
        assert not dialog.linear.isEnabled()
        dialog.calculated.setChecked(False)
        assert dialog.linear.isEnabled()
        assert not dialog.options().calculated
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_linear_deviation_refines_gpu_bilinear_surface(tmp_path):
    """Deviation must follow the rendered heightfield, not split flat facets."""
    from app.gcode.stock.milling_stock import MillingStockSnapshot

    spec = MillingStockSpec(0, 1, 0, 1, -1, 1)
    stock = MillingStockSnapshot(
        spec, np.array([[0, 0], [0, 1]], dtype=np.float32), np.zeros((2, 2), dtype=bool), 1.0, 1.0
    )
    coarse = StockStlOptions(linear_deviation=1.0, angular_deviation=90, edge_length=10)
    fine = replace(coarse, linear_deviation=0.01)
    coarse_path, fine_path = tmp_path / "coarse.stl", tmp_path / "fine.stl"
    coarse_count = write_milling_stock_stl(coarse_path, stock, options=coarse)
    fine_count = write_milling_stock_stl(fine_path, stock, options=fine)
    assert fine_count > coarse_count
    refined = vertices(fine_path).reshape(-1, 3)
    diagonal_midpoint = refined[(np.abs(refined[:, 0] - 0.5) < 1e-7) & (np.abs(refined[:, 1] - 0.5) < 1e-7)]
    assert np.any(np.abs(diagonal_midpoint[:, 2] - 0.25) < 1e-6)


def test_angular_deviation_refines_gpu_bilinear_surface(tmp_path):
    """Angular deviation must influence the STL, independently of edge length."""
    from app.gcode.stock.milling_stock import MillingStockSnapshot

    spec = MillingStockSpec(0, 1, 0, 1, -1, 1)
    stock = MillingStockSnapshot(
        spec, np.array([[0, 0], [0, 1]], dtype=np.float32), np.zeros((2, 2), dtype=bool), 1.0, 1.0
    )
    coarse = StockStlOptions(linear_deviation=1.0, angular_deviation=90, edge_length=10)
    fine = replace(coarse, angular_deviation=10)
    coarse_count = write_milling_stock_stl(tmp_path / "coarse.stl", stock, options=coarse)
    fine_count = write_milling_stock_stl(tmp_path / "fine.stl", stock, options=fine)
    assert fine_count > coarse_count


def test_dialog_defaults_match_current_stock_accuracy_not_saved_export_values(export_qt_app):
    from types import SimpleNamespace

    window = MainWindow()
    try:
        window._milling_stock_item = SimpleNamespace(surface_error=0.01, edge_error=0.05)
        window.settings.setValue("STOCK_STL/LINEAR", 1.0)
        window.settings.setValue("STOCK_STL/EDGE", 100.0)
        dialog = StockStlExportDialog(window)
        assert dialog.options() == StockStlOptions("mm", 0.01, 90, 0.05, calculated=True)
        assert not any(spin.isEnabled() for spin in (dialog.linear, dialog.angular, dialog.edge))
    finally:
        window._milling_stock_item = None
        window.close()
        window.deleteLater()
        export_qt_app.processEvents()
