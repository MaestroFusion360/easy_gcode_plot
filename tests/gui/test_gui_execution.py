# pylint: disable=protected-access
from __future__ import annotations

from threading import Event, get_ident
from types import SimpleNamespace

import pytest
from gcode_samples import MILLING_ARC_PLANES, TURNING_PARTIAL_TRACE
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QWidget

from app import main_window
from app.gcode.kernel import execute
from app.ui.windows import execution_worker, main_window_execution
from app.ui.windows.execution_worker import run_execution
from app.ui.windows.main_window_execution import MainWindowExecutionMixin


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_execution_worker_keeps_gui_responsive_and_cancel_waits_for_completion(qt_app, monkeypatch):
    monkeypatch.setattr(execution_worker, "EXECUTION_DIALOG_DELAY_MS", 20)
    owner = QWidget()
    cancelled = Event()
    worker_done = Event()
    gui_thread = get_ident()
    observations = []

    def work(source, **options):
        observations.append(get_ident() != gui_thread)
        assert cancelled.wait(5), "GUI timer failed to deliver cancellation"
        worker_done.set()
        return source

    def cancel_dialog():
        dialog = qt_app.activeModalWidget()
        if dialog is not None:
            observations.append(get_ident() == gui_thread)
            dialog.reject()

    timer = QTimer()
    timer.timeout.connect(cancel_dialog)
    timer.start(10)
    try:
        assert run_execution(owner, work, "snapshot", {}, cancelled.set) == "snapshot"
    finally:
        timer.stop()
        owner.close()
    assert worker_done.is_set()
    assert observations and all(observations)


def test_fast_execution_worker_finishes_without_opening_modal_dialog(qt_app):
    owner = QWidget()
    try:
        for value in range(25):
            assert run_execution(owner, lambda source, **_options: source, value, {}, lambda: None) == value
            assert qt_app.activeModalWidget() is None
    finally:
        owner.close()


def test_execution_worker_can_run_without_modal_feedback_while_processing_gui_events(qt_app):
    owner = QWidget()
    released = Event()
    observations = []

    def work(source, **_options):
        assert released.wait(2), "GUI events were not pumped while non-modal execution was running"
        return source

    def release_worker():
        observations.append(qt_app.activeModalWidget() is None)
        released.set()

    QTimer.singleShot(20, release_worker)
    try:
        assert (
            run_execution(
                owner,
                work,
                "snapshot",
                {},
                lambda: None,
                show_dialog=False,
            )
            == "snapshot"
        )
    finally:
        owner.close()

    assert observations == [True]


def test_execution_dialog_stays_visible_through_gui_completion(qt_app):
    owner = QWidget()
    worker_released = Event()
    cancelled = Event()
    observations = []

    def work(source, **_options):
        assert worker_released.wait(2)
        return source

    def complete(result):
        dialog = qt_app.activeModalWidget()
        observations.append(dialog is not None and dialog.isVisible())
        observations.append(dialog is not None and dialog.ui.statusLabel.isVisible())
        observations.append(dialog is not None and dialog.ui.cancelButton.isVisible())
        observations.append(dialog is not None and dialog.ui.cancelButton.isEnabled())
        dialog.ui.cancelButton.click()
        observations.append(cancelled.is_set())
        return result

    QTimer.singleShot(20, worker_released.set)
    try:
        assert run_execution(owner, work, "snapshot", {}, cancelled.set, completion=complete) == "snapshot"
    finally:
        owner.close()

    assert observations == [True, True, True, True, True]
    assert qt_app.activeModalWidget() is None


def test_execution_dialog_uses_complete_dark_palette(qt_app, monkeypatch):
    monkeypatch.setattr(execution_worker.theme, "current_theme", lambda: "dark")
    owner = QWidget()
    dialog = execution_worker._ExecutionDialog(
        owner,
        lambda: None,
        title="Execution",
        status_text="Working",
        cancelling_text="Cancelling",
    )
    try:
        assert dialog.autoFillBackground()
        assert "background-color: #1f1f1f" in dialog.styleSheet()
        assert dialog.palette().color(QPalette.ColorRole.Window).name() == "#1f1f1f"
        assert dialog.ui.statusLabel.palette().color(QPalette.ColorRole.WindowText).name() == "#e6e6e6"
        assert dialog.ui.cancelButton.palette().color(QPalette.ColorRole.Button).name() == "#333337"
    finally:
        dialog.close()
        owner.close()


def test_execution_worker_architecture_does_not_create_nested_event_loop(qt_app, monkeypatch):
    class NestedEventLoopForbidden:
        ProcessEventsFlag = QEventLoop.ProcessEventsFlag

        def __init__(self, *_args, **_kwargs):
            raise AssertionError("nested QEventLoop is forbidden in execution worker")

    monkeypatch.setattr(execution_worker, "QEventLoop", NestedEventLoopForbidden)
    owner = QWidget()
    released = Event()

    def work(source, **_options):
        assert released.wait(2), "GUI events were not pumped while execution worker was running"
        return source

    QTimer.singleShot(20, released.set)
    try:
        assert run_execution(owner, work, "snapshot", {}, lambda: None) == "snapshot"
    finally:
        owner.close()


def test_execution_worker_propagates_errors_and_clears_active_flag(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("worker failed")

    monkeypatch.setattr("app.gcode.program_execution.execute", fail)
    window = _gui_execution_harness("G1 X1", lathe_mode=False)
    with pytest.raises(ValueError, match="worker failed"):
        MainWindowExecutionMixin._calculate_editor_source(window)
    assert window._kernel_execution_active is False


def test_window_calculation_can_cancel_during_tool_discovery():
    checks = 0

    def cancelled():
        nonlocal checks
        checks += 1
        return checks >= 3

    with pytest.raises(InterruptedError, match="Tool discovery cancelled"):
        main_window_execution._calculate_source(
            "G1 X1 Y1 F100\n" * 10_000,
            current_tools={},
            previous_inference={},
            turning=False,
            correction_enabled=True,
            render=True,
            arc_tolerance=0.001,
            max_points=None,
            is_cancelled=cancelled,
            language="fanuc_mill",
            cancelled=cancelled,
        )

    assert checks == 3


class _Editor:
    def __init__(self, text: str):
        self._text = text

    def text(self):
        return self._text


class _StatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message, timeout):
        self.messages.append((message, timeout))


def _gui_execution_harness(source: str, *, lathe_mode: bool):
    return SimpleNamespace(
        ui=SimpleNamespace(editor=_Editor(source), statusbar=_StatusBar()),
        latheMode=lathe_mode,
        xPosMach=0.0,
        yPosMach=0.0,
        zPosMach=0.0,
    )


def test_gui_executes_editor_source_through_same_kernel_contract():
    window = _gui_execution_harness(MILLING_ARC_PLANES, lathe_mode=False)

    gui_result, _points, _render_limited = main_window.MainWindow._calculate_editor_source(
        window,
        show_errors=False,
    )
    direct_result = execute(
        MILLING_ARC_PLANES,
        language="fanuc_mill",
        home_x=0.0,
        home_y=0.0,
        home_z=0.0,
        emulate_g28_home=True,
    )

    assert gui_result.ok == direct_result.ok
    assert gui_result.motions == direct_result.motions
    assert gui_result.diagnostics == direct_result.diagnostics


def test_gui_forwards_xyz_wcs_tools_and_g28_configuration_to_kernel(monkeypatch):
    captured = {}
    expected = SimpleNamespace(ok=True, diagnostics=(), motions=())

    def fake_execute(source, **kwargs):
        captured["source"] = source
        captured.update(kwargs)
        return expected

    monkeypatch.setattr("app.gcode.program_execution.execute", fake_execute)
    tools = {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 1}}
    offsets = {54: (10.0, 20.0, -2.0)}
    window = SimpleNamespace(
        ui=SimpleNamespace(editor=_Editor("G54\nG1 X20 Y30 Z-5"), statusbar=_StatusBar()),
        latheMode=False,
        xPosMach=100.0,
        yPosMach=200.0,
        zPosMach=50.0,
        homeConfigured=False,
        defaultUnits="inch",
        wcsOffsets=offsets,
        tools=tools,
        maxGeneratedMotions=345678,
    )

    result, _points, _render_limited = main_window.MainWindow._calculate_editor_source(window, show_errors=False)

    assert result is expected
    assert captured["language"] == "fanuc_mill"
    assert captured["default_unit_scale"] == 25.4
    assert captured["tools"] == {}
    assert captured["milling_tools"] == {}
    assert captured["wcs_offsets"] == offsets
    assert captured["home_x"] == 100.0
    assert captured["home_y"] == 200.0
    assert captured["home_z"] == 50.0
    assert captured["emulate_g28_home"] is False
    assert captured["limits"].generated_motions == 345678
    assert callable(captured["cancelled"])


def test_reentrant_gui_execution_requests_cancellation():
    window = _gui_execution_harness("G1 X20", lathe_mode=True)
    window._kernel_execution_active = True
    window._kernel_cancel_requested = False

    result, _points, _render_limited = main_window.MainWindow._calculate_editor_source(window, show_errors=False)

    assert result is None
    assert window._kernel_cancel_requested is True


def test_lathe_execution_always_uses_relative_arc_offsets(monkeypatch):
    captured = {}
    expected = SimpleNamespace(ok=True, diagnostics=(), motions=())

    def fake_execute(source, **kwargs):
        del source
        captured.update(kwargs)
        return expected

    monkeypatch.setattr("app.gcode.program_execution.execute", fake_execute)
    window = _gui_execution_harness("G18 G2 X20 Z-10 I-10 K0", lathe_mode=True)
    window.arc_type = 2

    result, _points, _render_limited = main_window.MainWindow._calculate_editor_source(window, show_errors=False)
    assert result is expected
    assert captured["source_arc_type"] == 1


def test_gui_keeps_partial_turning_trace_renderable_when_kernel_reports_unsupported_cycle():
    execution_window = _gui_execution_harness(
        TURNING_PARTIAL_TRACE,
        lathe_mode=True,
    )
    result, _points, _render_limited = main_window.MainWindow._calculate_editor_source(
        execution_window,
        show_errors=False,
    )

    captured = []
    cleared = []

    window = SimpleNamespace(
        ui=SimpleNamespace(editor=_Editor(TURNING_PARTIAL_TRACE)),
        _calculate_editor_source=lambda **_kwargs: (result, [], False),
        latheMode=True,
        arcPointsPerCircle=lambda result: 314,
        clearPlot=lambda: cleared.append(True),
        _finishDataUpdate=lambda result=None, points=None, playback_value=None: captured.append(result),
    )

    assert main_window.MainWindow.updateData(window) is True
    assert cleared == []
    assert captured == [result]
    assert result.ok is False
    assert [(motion.end_x, motion.end_z) for motion in result.motions] == pytest.approx(
        [(20, 5), (18, 2), (30, 10), (25, 0)]
    )


def test_auto_update_schedule_marks_trace_stale_without_moving_old_slider():
    calls = []

    class Timer:
        def stop(self):
            calls.append("stop")

        def start(self):
            calls.append("start")

    class Window(MainWindowExecutionMixin):
        def __init__(self):
            self.autoUpdateTimer = Timer()
            self.autoUpdateEnabled = True
            self.execution_result = object()
            self.render_points = [object()]

        def clearPlot(self):
            calls.append("clear")
            self.execution_result = None
            self.render_points = []

    window = Window()
    window.scheduleAutoUpdate()

    assert calls == ["stop", "start"]
    assert window._plot_source_stale is True


def test_programmatic_file_load_does_not_schedule_auto_update():
    calls = []

    class Timer:
        def stop(self):
            calls.append("stop")

        def start(self):
            calls.append("start")

    window = SimpleNamespace(_loading_document=True, autoUpdateTimer=Timer())
    MainWindowExecutionMixin.scheduleAutoUpdate(window)

    assert calls == []


def test_disabled_auto_update_marks_trace_stale_without_starting_timer():
    calls = []

    class Timer:
        def stop(self):
            calls.append("stop")

        def start(self):
            calls.append("start")

    window = SimpleNamespace(autoUpdateTimer=Timer(), autoUpdateEnabled=False)
    MainWindowExecutionMixin.scheduleAutoUpdate(window)

    assert calls == ["stop"]
    assert window._plot_source_stale is True


def test_edit_during_auto_update_cancels_current_execution_and_queues_refresh():
    calls = []

    class Timer:
        def stop(self):
            calls.append("stop")

        def start(self):
            calls.append("start")

    window = SimpleNamespace(
        autoUpdateTimer=Timer(),
        autoUpdateEnabled=True,
        _auto_update_in_progress=True,
        _kernel_execution_active=True,
    )

    MainWindowExecutionMixin.scheduleAutoUpdate(window)

    assert calls == ["stop"]
    assert window._kernel_cancel_requested is True
    assert window._auto_update_pending is True
    assert window._auto_update_show_dialog is False


def test_auto_update_requests_non_modal_execution(qt_app):
    window = main_window.MainWindow()
    captured = []
    result = SimpleNamespace(motions=())

    def calculate(**kwargs):
        captured.append(kwargs)
        return result, None, False

    window._calculate_editor_source = calculate
    window.updateExecutionStatus = lambda *args, **kwargs: None
    window.autoUpdate()

    assert captured
    assert captured[-1]["show_dialog"] is False
    assert captured[-1]["require_current_source"] is True
    window.deleteLater()


def test_machine_mode_switch_reexecutes_silently(qt_app):
    window = main_window.MainWindow()
    calls = []
    original = window._calculate_editor_source

    def capture(**kwargs):
        calls.append(kwargs["show_errors"])
        return original(**kwargs)

    window._calculate_editor_source = capture
    window.ui.editor.setText("G0 X1 Y2\nM30")
    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()

    assert calls
    assert calls[-1] is False
    window.deleteLater()
