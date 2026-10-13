"""In-memory stock snapshots retain the simulated coordinates and resolution."""

import numpy as np
import pytest

from app.gcode.stock.milling_stock import MillingStockSnapshot, MillingStockSpec, milling_stock_mesh_triangles


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
