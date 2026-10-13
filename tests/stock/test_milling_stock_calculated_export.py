"""Fast export preserves the calculated surface, volume and closed topology."""

# pylint: disable=import-outside-toplevel,use-implicit-booleaness-not-len

from dataclasses import replace

import numpy as np
import pytest

from app.gcode.stock.milling_stock_export import write_milling_stock_stl
from app.gcode.stock.milling_stock_stl import StockStlOptions
from app.gcode.stock.milling_stock_types import MillingStockSnapshot, MillingStockSpec


@pytest.fixture(scope="session")
def calculated_qt_app():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _read(path):
    dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])
    return np.fromfile(path, dtype=dtype, offset=84)["vertices"].astype(float)


def _assert_closed(triangles):
    _, index = np.unique(np.round(triangles.reshape(-1, 3), 6), axis=0, return_inverse=True)
    faces = index.reshape(-1, 3)
    edges = np.stack((faces, np.roll(faces, -1, axis=1)), axis=-1).reshape(-1, 2)
    _, index, counts = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
    assert np.all(counts == 2)
    direction = np.where(edges[:, 0] < edges[:, 1], 1, -1)
    assert np.all(np.bincount(index, weights=direction) == 0)


@pytest.mark.parametrize("pattern", ["flat", "pocket", "through", "edge", "saddle", "empty"])
def test_compact_export_preserves_volume_and_oriented_closed_mesh(tmp_path, pattern):
    height = np.ones((24, 32))
    if pattern in {"pocket", "through", "edge"}:
        start = 0 if pattern == "edge" else 7
        height[start:17, start:23] = 0.4 if pattern == "pocket" else 0
    elif pattern == "saddle":
        y, x = np.mgrid[:24, :32]
        height = 0.1 + x * y / 1000
    elif pattern == "empty":
        height[:] = 0
    stock = MillingStockSnapshot(MillingStockSpec(0, 31, 0, 23, 0, 1), height, height * 0, 1, 1)
    old, compact = tmp_path / "old.stl", tmp_path / "compact.stl"
    write_milling_stock_stl(old, stock)
    write_milling_stock_stl(compact, stock, options=StockStlOptions(calculated=True))
    original, actual = _read(old), _read(compact)
    if pattern == "empty":
        assert not len(actual)
        return
    _assert_closed(actual)

    def volume(faces):
        return np.einsum("ij,ij->", faces[:, 0], np.cross(faces[:, 1], faces[:, 2])) / 6

    assert volume(actual) == pytest.approx(volume(original), rel=1e-6)
    if pattern == "flat":
        assert len(actual) <= 16


def test_calculated_export_never_refines_or_replays_and_preserves_units(tmp_path, monkeypatch):
    from app.gcode.stock import milling_stock_export as module

    def unexpected(*_args, **_kwargs):
        pytest.fail("Calculated export must not refine or regenerate stock")

    monkeypatch.setattr(module, "limit_edges", unexpected)
    height = np.ones((65, 129))
    height[16:48, 32:96] = 0.25
    stock = MillingStockSnapshot(MillingStockSpec(0, 128, 0, 64, 0, 1), height, height * 0, 1, 1)
    options = StockStlOptions(linear_deviation=0.001, edge_length=0.05, calculated=True)
    mm, inches = tmp_path / "mm.stl", tmp_path / "in.stl"
    write_milling_stock_stl(mm, stock, options=options)
    write_milling_stock_stl(inches, stock, options=replace(options, units="in"))
    np.testing.assert_allclose(_read(inches) * 25.4, _read(mm), atol=1e-5)
    assert len(_read(mm)) < 4 * stock.nx * stock.ny / 4


def test_large_flat_snapshot_exports_only_boundary_faces(tmp_path):
    height = np.ones((2049, 2049), dtype=np.float32)
    stock = MillingStockSnapshot(MillingStockSpec(0, 100, 0, 100, 0, 1), height, height * 0, 100 / 2048, 100 / 2048)
    output = tmp_path / "flat.stl"
    count = write_milling_stock_stl(output, stock, options=StockStlOptions(calculated=True))
    assert count <= 16
    assert output.stat().st_size == 84 + count * 50


@pytest.mark.parametrize("calculated", [True, False], ids=["auto", "maximum-quality"])
def test_export_budget_preserves_source_and_roundtrips_through_importer(tmp_path, monkeypatch, calculated):
    from app.gcode.stock import milling_stock_export as module
    from app.ui.plot.stl import MAX_STL_TRIANGLES, read_stl

    monkeypatch.setattr(module, "MAX_STOCK_STL_TRIANGLES", 4096)
    y, x = np.mgrid[:129, :129]
    height = (1 + 0.2 * np.sin(x / 8) * np.cos(y / 8)).astype(np.float32)
    original = height.copy()
    stock = MillingStockSnapshot(MillingStockSpec(0, 16, 0, 16, 0, 2), height, height * 0, 0.125, 0.125)
    options = StockStlOptions(linear_deviation=0.001, angular_deviation=1, edge_length=0.05, calculated=calculated)
    output = tmp_path / "bounded.stl"
    report = {}
    count = write_milling_stock_stl(output, stock, options=options, report=report)
    assert report == {"simplified": True, "triangles": count}
    assert 0 < count <= module.MAX_STOCK_STL_TRIANGLES < MAX_STL_TRIANGLES
    assert output.stat().st_size == 84 + 50 * count
    mesh = read_stl(output)
    assert mesh.triangle_count == count
    _assert_closed(mesh.triangles)
    np.testing.assert_array_equal(height, original)
    assert mesh.triangles[..., 0].min() == 0
    assert mesh.triangles[..., 0].max() == 16
    assert mesh.triangles[..., 1].min() == 0
    assert mesh.triangles[..., 1].max() == 16


@pytest.mark.parametrize("calculated", [True, False], ids=["auto", "maximum-quality"])
def test_dense_export_is_small_enough_for_gui_reimport(tmp_path, calculated, calculated_qt_app):
    from app.gcode.stock.milling_stock_export import MAX_STOCK_STL_TRIANGLES
    from app.main_window import MainWindow

    y, x = np.mgrid[:401, :401]
    height = (1 + 0.2 * np.sin(x / 8) * np.cos(y / 8)).astype(np.float32)
    stock = MillingStockSnapshot(MillingStockSpec(0, 100, 0, 100, 0, 2), height, height * 0, 0.25, 0.25)
    output = tmp_path / "dense.stl"
    report = {}
    options = StockStlOptions(linear_deviation=0.001, angular_deviation=1, edge_length=0.05, calculated=calculated)
    count = write_milling_stock_stl(output, stock, options=options, report=report)
    assert report["simplified"]
    assert count <= MAX_STOCK_STL_TRIANGLES
    assert output.stat().st_size <= 84 + MAX_STOCK_STL_TRIANGLES * 50
    window = MainWindow()
    try:
        assert window.importStl(str(output)) is True
        # Inspect the imported overlay to verify the complete GUI import path.
        assert window._stl_entries[0].overlay.mesh.triangle_count == count  # pylint: disable=protected-access
    finally:
        window.deleteLater()
        calculated_qt_app.processEvents()


def test_cancellation_during_budget_retry_preserves_existing_file(tmp_path, monkeypatch):
    from app.gcode.stock import milling_stock_export as module

    monkeypatch.setattr(module, "MAX_STOCK_STL_TRIANGLES", 100)
    stock = MillingStockSnapshot(MillingStockSpec(0, 8, 0, 8, 0, 1), np.ones((9, 9)), np.zeros((9, 9)), 1, 1)
    output = tmp_path / "existing.stl"
    output.write_bytes(b"Existing model")

    def cancel_retry(*_args):
        raise InterruptedError("Stock STL export cancelled")

    monkeypatch.setattr(module, "_bounded_export_surface", cancel_retry)
    with pytest.raises(InterruptedError):
        write_milling_stock_stl(output, stock)
    assert output.read_bytes() == b"Existing model"
    assert not list(tmp_path.glob("*.tmp"))
