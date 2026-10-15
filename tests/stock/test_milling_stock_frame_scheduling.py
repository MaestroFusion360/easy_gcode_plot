"""Regression cases for interrupted GPU stock frames and STL export ownership."""

# pylint: disable=protected-access

from types import SimpleNamespace

import pytest

from app.main_window import MainWindow
from app.ui.windows import main_window_milling_stock as module


class _Signal:
    def connect(self, callback):
        self.callback = callback


class _Worker:
    instances = []

    def __init__(self, timeline, item, count, replay_budget):
        self.timeline = timeline
        self.count = count
        self.replay_budget = replay_budget
        self.finished = _Signal()
        self.interrupted = False
        self.running = False
        self.deleted = False
        self.error = None
        self.tiles = None
        self.instances.append(self)

    def start(self):
        self.running = True

    def isRunning(self):
        return self.running

    def requestInterruption(self):
        self.interrupted = True

    def isInterruptionRequested(self):
        return self.interrupted

    def deleteLater(self):
        self.deleted = True


class _Control:
    def __init__(self, value=0):
        self.enabled = True
        self.current_value = value

    def setEnabled(self, enabled):
        self.enabled = enabled

    def isEnabled(self):
        return self.enabled

    def value(self):
        return self.current_value


class _FakeWindow(module.MainWindowMillingStockMixin):
    def __init__(self):
        MainWindow._initialize_stock_runtime(self)
        self._stock_timeline = SimpleNamespace(motion_count=0)
        self.execution_result = object()
        self._playback_movements = [SimpleNamespace(motion_end=1), SimpleNamespace(motion_end=2)]
        self._stock_animation_active = True
        self._milling_frame_worker = None
        self._milling_pending_count = None
        self._milling_pending_quality = None
        self._milling_retired_workers = set()
        self._milling_stock_item = SimpleNamespace(set_colors=lambda *_: None, calculated_snapshot=lambda *_: None)
        self.plotStockColor = "#ffffff"
        self.plotCutColor = "#000000"
        self.latheMode = False
        self._sender = None
        self.messages = []
        self.ui = SimpleNamespace(
            horizontalSlider=_Control(value=1),
            actionStockPlayback=_Control(),
            actionSaveStockStl=_Control(),
            statusbar=SimpleNamespace(showMessage=lambda *args: self.messages.append(args)),
        )

    def sender(self):
        return self._sender

    def _pause_playback(self):
        pass


@pytest.mark.parametrize(
    ("dialect", "supported"),
    [("fanuc", True), ("sinumerik", True), ("heidenhain", True), ("other", False)],
)
def test_three_axis_stock_dialect_gate(monkeypatch, dialect, supported):
    window = _FakeWindow()
    window.execution_result = SimpleNamespace(
        complete=True,
        motions=[object()],
        language="fanuc_mill",
        source_dialect=dialect,
        rotary_angles=(),
        execution_steps=(),
    )
    monkeypatch.setattr(window, "millingStockDialogSpec", lambda: None)
    failures = []
    monkeypatch.setattr(window, "_notify_milling_stock_failure", failures.append)

    assert window._start_milling_stock_animation() is False
    rejected = any("requires FANUC" in message[0] for message in window.messages)
    assert rejected is (not supported)
    if supported:
        assert [str(error) for error in failures] == ["No toolpath bounds"]


def test_interrupted_worker_restarts_when_slider_returns_to_same_count(monkeypatch):
    monkeypatch.setattr(module, "MillingStockFrameWorker", _Worker)
    _Worker.instances = []
    window = _FakeWindow()
    window._apply_milling_stock_frame(1)
    original = window._milling_frame_worker
    window._apply_milling_stock_frame(2)
    assert original.isInterruptionRequested()
    window._apply_milling_stock_frame(1)
    assert window._milling_pending_count == 1

    original.running = False
    original.error = InterruptedError("Superseded")
    window._sender = original
    window._finish_milling_stock_frame()
    assert window._milling_frame_worker is not original
    assert window._milling_frame_worker.count == 1


def test_retired_worker_must_finish_before_new_seek(monkeypatch):
    monkeypatch.setattr(module, "MillingStockFrameWorker", _Worker)
    _Worker.instances = []
    window = _FakeWindow()
    window._apply_milling_stock_frame(1)
    original = window._milling_frame_worker
    assert window._cancel_milling_seek() is False
    window._apply_milling_stock_frame(2)
    assert len(_Worker.instances) == 1
    assert window._milling_pending_count == 2

    original.running = False
    window._sender = original
    window._finish_milling_stock_frame()
    assert original.deleted
    assert window._milling_frame_worker.count == 2
    assert len(_Worker.instances) == 2


def test_finished_frame_is_published_and_logged_without_mesh_attributes(monkeypatch, caplog):
    monkeypatch.setattr(module, "MillingStockFrameWorker", _Worker)
    window = _FakeWindow()
    published = []
    window._milling_stock_item.apply_frame = lambda *args: published.append(args)
    monkeypatch.setattr(window, "_show_milling_stock_position", lambda: None)
    window._apply_milling_stock_frame(1)
    worker = window._milling_frame_worker
    worker.tiles, worker.revision, worker.mesh_seconds = object(), 1, 0.02
    window._sender = worker
    with caplog.at_level("DEBUG", logger=module.__name__):
        window._finish_milling_stock_frame()
    assert published == [(window._stock_timeline, worker.tiles, 1)]
    assert worker.deleted and window._milling_frame_worker is None
    assert "milling_stock_frame" in caplog.text
    assert "duration_ms=20.000" in caplog.text


def test_export_blocks_stock_seek_and_handles_gpu_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "MillingStockFrameWorker", _Worker)
    _Worker.instances = []
    window = _FakeWindow()
    window._stock_export_active = True
    window._apply_milling_stock_frame(1)
    window._update_milling_stock_animation_frame(1)
    assert not _Worker.instances
    assert window._milling_pending_count is None

    window._stock_export_active = False
    monkeypatch.setattr(module.StockStlExportDialog, "get_options", lambda _: object())
    monkeypatch.setattr(
        module, "QFileDialog", SimpleNamespace(getSaveFileName=lambda *_: (str(tmp_path / "part.stl"), ""))
    )

    def timed_out(*args, **kwargs):
        assert window._stock_export_active
        assert not window.ui.horizontalSlider.isEnabled()
        assert not window.ui.actionStockPlayback.isEnabled()
        raise TimeoutError("GPU snapshot timeout")

    monkeypatch.setattr(module, "run_execution", timed_out)
    window.saveMillingStockStl()
    assert window.messages[-1][0] == "GPU snapshot timeout"
    assert not window._stock_export_active
    assert window._stock_export_cancel is None
    assert window.ui.horizontalSlider.isEnabled()
    assert window.ui.actionStockPlayback.isEnabled()
    assert window.ui.actionSaveStockStl.isEnabled()


def test_export_does_not_rebuild_calculated_frame_even_when_writing_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "MillingStockFrameWorker", _Worker)
    window = _FakeWindow()
    window._stock_timeline.motion_count = 1
    monkeypatch.setattr(module.StockStlExportDialog, "get_options", lambda _: object())
    monkeypatch.setattr(
        module, "QFileDialog", SimpleNamespace(getSaveFileName=lambda *_: (str(tmp_path / "part.stl"), ""))
    )
    window._milling_stock_item.build_frame = lambda *_: (_ for _ in ()).throw(AssertionError("Frame rebuilt"))
    calls = []

    def execute(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            return object()
        raise ValueError("Writing failed")

    monkeypatch.setattr(module, "run_execution", execute)
    window.saveMillingStockStl()
    assert window._milling_frame_worker is None
    assert calls[1][1] is module.write_milling_stock_stl
    assert window.messages[-1][0] == "Writing failed"
