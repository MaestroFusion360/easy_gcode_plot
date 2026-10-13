"""In-memory stock snapshots retain the simulated coordinates and resolution."""

import numpy as np
import pytest

from app.gcode.stock import milling_stock_export as module
from app.gcode.stock.milling_stock_export import milling_stock_mesh_triangles
from app.gcode.stock.milling_stock_types import MillingStockSnapshot, MillingStockSpec


def snapshot():
    height = np.array([[0, 0, 0], [0, -2, 0], [0, 0, 0]], dtype=np.float32)
    return MillingStockSnapshot(MillingStockSpec(10, 12, 20, 22, -5, 0), height, height * 0, 1, 1)


def test_mesh_snapshot_preserves_origin_bounds_and_cut_height_without_mutating_source():
    stock = snapshot()
    height = stock.height.copy()
    triangles = milling_stock_mesh_triangles(stock)
    vertices = triangles.reshape(-1, 3)
    assert vertices.min(axis=0) == pytest.approx((10, 20, -5))
    assert vertices.max(axis=0) == pytest.approx((12, 22, 0))
    assert np.any(np.all(np.isclose(vertices, (11, 21, -2)), axis=1))
    np.testing.assert_array_equal(stock.height, height)
    retained = triangles.copy()
    stock.height[:] = -5
    np.testing.assert_array_equal(triangles, retained)


def test_mesh_budget_rejects_without_coarsening_stock():
    stock = snapshot()
    height = stock.height.copy()
    with pytest.raises(ValueError, match="triangle limit"):
        milling_stock_mesh_triangles(stock, max_triangles=1)
    np.testing.assert_array_equal(stock.height, height)


def test_mesh_cancel_and_completely_removed_stock():
    stock = snapshot()
    with pytest.raises(InterruptedError):
        milling_stock_mesh_triangles(stock, cancelled=lambda: True)
    stock.height[:] = stock.spec.z_min
    with pytest.raises(ValueError, match="no remaining material"):
        milling_stock_mesh_triangles(stock)


def test_simplification_bounds_mesh_without_changing_simulation():
    x, y = np.meshgrid(np.linspace(0, 2, 65), np.linspace(0, 2, 65))
    height = (-2 + np.sin(x * 17) * np.sin(y * 19)).astype(np.float32)
    stock = MillingStockSnapshot(MillingStockSpec(10, 12, 20, 22, -5, 0), height, height * 0, 2 / 64, 2 / 64)
    original = height.copy()
    report = {}
    triangles = milling_stock_mesh_triangles(stock, max_triangles=4096, simplify=True, report=report)
    assert report == {"simplified": True, "triangles": len(triangles)}
    assert 0 < len(triangles) <= 4096
    vertices = triangles.reshape(-1, 3)
    assert vertices.min(axis=0) == pytest.approx((10, 20, -5))
    assert vertices.max(axis=0)[:2] == pytest.approx((12, 22))
    np.testing.assert_array_equal(stock.height, original)
    assert stock.nx == stock.ny == 64
    # Every directed edge has one reverse edge in this closed, oriented mesh.
    edges = np.concatenate([triangles[:, [i, (i + 1) % 3]] for i in range(3)])
    directed = {tuple(edge.ravel()) for edge in edges}
    assert len(directed) == len(edges)
    assert directed == {tuple(edge[::-1].ravel()) for edge in edges}


def test_under_budget_mesh_retains_exact_geometry_with_simplification_enabled():
    stock = snapshot()
    report = {}
    exact = milling_stock_mesh_triangles(stock)
    actual = milling_stock_mesh_triangles(stock, simplify=True, report=report)
    np.testing.assert_array_equal(actual, exact)
    assert report == {"simplified": False, "triangles": len(exact)}


def test_simplification_remains_cancellable_without_changing_source(monkeypatch):
    stock = snapshot()
    original = stock.height.copy()
    resample = module._bounded_export_surface  # pylint: disable=protected-access
    cancelled = False

    def cancel_resampling(source, check, **options):
        nonlocal cancelled
        cancelled = True
        return resample(source, check, **options)

    monkeypatch.setattr(module, "_bounded_export_surface", cancel_resampling)
    with pytest.raises(InterruptedError):
        milling_stock_mesh_triangles(stock, max_triangles=16, simplify=True, cancelled=lambda: cancelled)
    np.testing.assert_array_equal(stock.height, original)
