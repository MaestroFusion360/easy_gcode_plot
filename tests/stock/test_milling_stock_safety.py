"""Stock export topology, resource limits and cancellation without a GL driver."""

# pylint: disable=protected-access

from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from app.gcode.stock import MillingStockSpec, write_milling_stock_stl
from app.gcode.stock.milling_stock_stl import StockStlOptions
from app.gcode.stock.milling_stock_types import MillingStockSnapshot
from app.ui.plot import milling_stock_overlay as overlay
from app.ui.plot.milling_stock_gpu import GpuStock


@pytest.mark.parametrize("options", [None, StockStlOptions(edge_length=0.8)])
@pytest.mark.parametrize("pattern", ["hole", "edge", "empty"])
def test_through_cut_has_closed_oriented_mesh(tmp_path, options, pattern):
    height = np.ones((6, 6))
    if pattern == "hole":
        height[1:4, 1:4] = 0
    elif pattern == "edge":
        height[:3, :3] = 0
    else:
        height[:] = 0
    stock = MillingStockSnapshot(MillingStockSpec(0, 5, 0, 5, 0, 1), height, height * 0, 1, 1)
    path = tmp_path / "stock.stl"
    count = write_milling_stock_stl(path, stock, options=options)
    dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attr", "<u2")])
    triangles = np.fromfile(path, dtype=dtype, offset=84)["vertices"]
    assert len(triangles) == count
    if pattern == "empty":
        assert count == 0
        return
    _, indices = np.unique(np.round(triangles.reshape(-1, 3), 6), axis=0, return_inverse=True)
    faces = indices.reshape(-1, 3)
    edges = np.stack((faces, np.roll(faces, -1, axis=1)), axis=-1).reshape(-1, 2)
    _, edge_ids, counts = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
    assert np.all(counts == 2)
    orientation = np.where(edges[:, 0] < edges[:, 1], 1, -1)
    assert np.all(np.bincount(edge_ids, weights=orientation) == 0)
    canonical = np.sort(faces, axis=1)
    assert len(np.unique(canonical, axis=0)) == len(faces)


def test_gpu_budget_includes_padding_and_mip_levels(monkeypatch):
    gpu = GpuStock(memory_budget=512 * 1024**2)
    frame = SimpleNamespace(timeline=SimpleNamespace(spec=MillingStockSpec(0, 300, 0, 300, -5, 0)), edge_error=0.05)
    monkeypatch.setattr("app.ui.plot.milling_stock_gpu.GL.glGetIntegerv", lambda _: 32768)
    # No GL allocation must occur before the memory check.
    with pytest.raises(ValueError, match="budget"):
        gpu._allocate(frame)
    assert gpu.texture == 0


def test_cancelled_gpu_update_invalidates_partial_state():
    gpu = GpuStock()
    gpu.key = object()
    with pytest.raises(InterruptedError):
        gpu.update(None, cancelled=lambda: True)
    assert gpu.key is None


@pytest.mark.parametrize("size, shape", [(200, 8192), (300, 16384)])
def test_default_four_gib_budget_accepts_large_stock_without_gl(size, shape):
    gpu = GpuStock()
    frame = SimpleNamespace(timeline=SimpleNamespace(spec=MillingStockSpec(0, size, 0, size, -5, 0)), edge_error=0.05)
    assert gpu.memory_budget == 4 * 1024**3
    _, actual, _ = gpu.validate_frame(frame)
    assert actual == (shape, shape)
    assert frame.edge_error == 0.05
    assert gpu.texture == 0


def test_four_gib_budget_rejects_oversized_stock_before_gl(monkeypatch):
    gpu = GpuStock()
    frame = SimpleNamespace(timeline=SimpleNamespace(spec=MillingStockSpec(0, 600, 0, 600, -5, 0)), edge_error=0.05)
    monkeypatch.setattr(
        "app.ui.plot.milling_stock_gpu.GL.glGetIntegerv", lambda _: pytest.fail("GL called before budget check")
    )
    with pytest.raises(ValueError, match="4096.0 MiB"):
        gpu._allocate(frame)
    assert gpu.texture == 0


def test_paint_reports_driver_failure_once_and_restores_gl_state(monkeypatch):
    calls, failures = [], []
    item = overlay.MillingStockOverlayItem()
    frame = SimpleNamespace(timeline=object(), surface_error=0.01, edge_error=0.05)
    item._frame = frame
    item.renderFailed.connect(lambda *args: failures.append(args))
    monkeypatch.setattr(overlay.QOpenGLContext, "currentContext", lambda: object())
    monkeypatch.setattr(overlay.GL, "glGetIntegerv", lambda _: 7)
    monkeypatch.setattr(overlay.GL, "glGetIntegeri_v", lambda *_: 8)
    for name in (
        "glUseProgram",
        "glBindVertexArray",
        "glBindBufferBase",
        "glBindBuffer",
        "glBindTexture",
        "glActiveTexture",
    ):
        monkeypatch.setattr(overlay.GL, name, lambda *args, name=name: calls.append((name, args)))
    error = RuntimeError("GPU memory exhausted")

    def fail(_frame):
        calls.append(("update", ()))
        raise error

    item._gpu = SimpleNamespace(initialize=lambda _: None, update=fail)
    item.paint()
    restored = list(calls)
    item.paint()
    assert calls == restored
    assert failures == [(frame.timeline, error)]
    assert ("glUseProgram", (7,)) in calls
    assert ("glBindVertexArray", (7,)) in calls
    assert calls[-1] == ("glActiveTexture", (7,))
    frame.edge_error = 0.1
    assert item._frame_error(frame) is None


def test_snapshot_deadline_discards_queued_gui_operation(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(overlay, "monotonic", lambda: now[0])

    class Ready:
        def wait(self, timeout):
            now[0] = 11.0
            return False

    # The abandoned flag is a separate event, with ordinary event semantics.
    events = iter((Event(), Ready()))
    monkeypatch.setattr(overlay, "Event", lambda: next(events))
    queued = []
    item = SimpleNamespace(
        thread=lambda: None, snapshotRequested=SimpleNamespace(emit=lambda *args: queued.append(args))
    )
    with pytest.raises(TimeoutError):
        overlay.MillingStockOverlayItem._read_snapshot(item, object())
    timeline, result, ready = queued[0]
    ready.set = lambda: None
    overlay.MillingStockOverlayItem._snapshot_on_gui(item, timeline, result, ready)
    assert isinstance(result["error"], InterruptedError)
    assert "snapshot" not in result


def test_snapshot_cancelled_before_queueing():
    with pytest.raises(InterruptedError):
        overlay.MillingStockOverlayItem._read_snapshot(None, object(), cancelled=lambda: True)


def test_snapshot_cancelled_during_gui_preparation(monkeypatch):
    cancelled = Event()
    ready = Event()
    result = {"cancelled": cancelled.is_set}
    item = SimpleNamespace(view=lambda: SimpleNamespace(context=lambda: object()), surface_error=0.01, edge_error=0.05)

    def prepare(timeline, surface, edge, check):
        cancelled.set()
        assert check()
        raise InterruptedError("Stock snapshot cancelled")

    monkeypatch.setattr(overlay, "prepare_frame", prepare)
    overlay.MillingStockOverlayItem._snapshot_on_gui(item, object(), result, ready)
    assert ready.is_set()
    assert isinstance(result["error"], InterruptedError)
    assert "snapshot" not in result


def test_gpu_dispatch_checks_cancellation_between_tiles(monkeypatch):
    gpu = GpuStock()
    calls = []
    monkeypatch.setattr(gpu, "uniform", lambda *_: 0)
    monkeypatch.setattr("app.ui.plot.milling_stock_gpu.GL.glUniform2i", lambda *_: None)
    monkeypatch.setattr("app.ui.plot.milling_stock_gpu.GL.glDispatchCompute", lambda *args: calls.append(args))
    monkeypatch.setattr("app.ui.plot.milling_stock_gpu.GL.glMemoryBarrier", lambda *_: None)
    with pytest.raises(InterruptedError):
        gpu._rectangle(0, (0, 0), (1024, 1024), cancelled=lambda: len(calls) == 1)
    assert calls == [(32, 32, 1)]


def test_calculated_snapshot_reads_displayed_gpu_without_replay_or_update(monkeypatch):
    def unexpected(*_args, **_kwargs):
        pytest.fail("Export must not prepare frames or update calculated material")

    monkeypatch.setattr(overlay, "prepare_frame", unexpected)
    monkeypatch.setattr(overlay.GL, "glUseProgram", lambda *_: None)
    monkeypatch.setattr(overlay.GL, "glBindTexture", lambda *_: None)
    timeline, snapshot = object(), object()
    frame = SimpleNamespace(timeline=timeline, surface_error=0.01, edge_error=0.05, count=42)
    gpu = SimpleNamespace(
        key=(timeline, 0.01, 0.05),
        count=42,
        initialize=unexpected,
        update=unexpected,
        snapshot=lambda source: snapshot if source is timeline else unexpected(),
    )
    view = SimpleNamespace(context=lambda: object(), makeCurrent=lambda: None, doneCurrent=lambda: None)
    item = SimpleNamespace(view=lambda: view, _gpu=gpu)
    result, ready = {"cancelled": lambda: False, "frame": frame}, Event()
    overlay.MillingStockOverlayItem._snapshot_on_gui(item, timeline, result, ready)
    assert ready.is_set()
    assert result["snapshot"] is snapshot
    assert "error" not in result


def test_calculated_snapshot_rejects_unpainted_frame_without_rebuilding_it():
    timeline = object()
    frame = SimpleNamespace(timeline=timeline, surface_error=0.01, edge_error=0.05, count=42)
    item = SimpleNamespace(
        view=lambda: SimpleNamespace(context=lambda: object()),
        _gpu=SimpleNamespace(key=(timeline, 0.01, 0.05), count=41),
    )
    result, ready = {"cancelled": lambda: False, "frame": frame}, Event()
    overlay.MillingStockOverlayItem._snapshot_on_gui(item, timeline, result, ready)
    assert ready.is_set()
    assert isinstance(result["error"], ValueError)
    assert "snapshot" not in result
