"""Execution, playback, auto-refresh, and statistics helpers for the main window."""

import logging
from copy import deepcopy
from functools import partial
from math import asin, ceil, floor, pi, sqrt
from threading import Event
from time import perf_counter

from PyQt6.QtCore import QCoreApplication

from app.gcode.core import last_index
from app.gcode.kernel import execute
from app.gcode.trace_tools import RenderLimitExceeded, render_trace, trace_statistics
from app.tools.setup import refresh_setup
from app.ui.plot.playback import build_playback_movements
from app.ui.windows.execution_worker import run_execution

AUTO_REFRESH_MAX_POINTS = 20000
AUTO_REFRESH_DELAY_MS = 500
LOGGER = logging.getLogger(__name__)
PLAYBACK_INTERVALS_MS = (1000, 250, 100, 40, 10)


def _arc_points_per_circle(result, tolerance_value: float) -> int:
    radii = [motion.arc.radius for motion in result.motions if motion.arc is not None]
    if not radii:
        return 3
    radius = max(radii)
    tolerance = min(max(float(tolerance_value), 1e-9), radius * 2)
    angle = 2.0 * asin(sqrt((tolerance / radius) * 0.5))
    return max(3, ceil(pi / angle)) if angle > 0 else 3


def _calculate_source(
    snapshot_source,
    *,
    current_tools,
    previous_inference,
    turning,
    setup_unit_scale,
    turning_tools,
    milling_tools,
    correction_enabled,
    render,
    arc_tolerance,
    max_points,
    is_cancelled,
    **snapshot_options,
):
    updated_tools = current_tools
    inferred = refresh_setup(
        snapshot_source,
        updated_tools,
        previous_inference,
        turning=turning,
        default_unit_scale=setup_unit_scale,
    )
    # Keep kernel inputs detached from the setup installed back on the window.
    snapshot_options["tools"] = deepcopy(turning_tools) if correction_enabled else {}
    snapshot_options["milling_tools"] = deepcopy(milling_tools) if correction_enabled else {}
    execution_started = perf_counter()
    result = execute(snapshot_source, **snapshot_options)
    execution_ms = (perf_counter() - execution_started) * 1000.0
    points = None
    render_limited = False
    if render and result is not None and result.motions:
        try:
            points = render_trace(
                result,
                lathe_radius_view=turning,
                arc_points_per_circle=_arc_points_per_circle(result, arc_tolerance),
                max_points=max_points,
                cancelled=is_cancelled,
            )
        except RenderLimitExceeded:
            render_limited = True
        except InterruptedError:
            return result, None, updated_tools, inferred, execution_ms, False
    return result, points, updated_tools, inferred, execution_ms, render_limited


def playback_interval_ms(speed: int) -> int:
    """Map CNCEditor-compatible speed level 1..5 to a timer interval."""
    level = max(1, min(5, int(speed)))
    return PLAYBACK_INTERVALS_MS[level - 1]


def playback_speed_level(interval_ms: int) -> int:
    """Map a legacy timer interval to its nearest speed level."""
    interval = max(1, int(interval_ms))
    return min(range(1, 6), key=lambda level: abs(playback_interval_ms(level) - interval))


class MainWindowExecutionMixin:
    def timerEvent(self, event):
        """Advance playback by logical CNC motion, not editor line."""
        if event.timerId() != self.timer.timerId():
            return super().timerEvent(event)
        maximum = self.ui.horizontalSlider.maximum()
        value = self.ui.horizontalSlider.value()
        if maximum <= 0 or value >= maximum:
            LOGGER.debug(
                "playback_reached_end value=%d maximum=%d stock_animation=%s",
                value,
                maximum,
                getattr(self, "_stock_animation_active", False),
            )
            if getattr(self, "_stock_animation_active", False):
                self.ui.actionPlay.setChecked(False)
                self.timer.stop()
            else:
                self.stop()
            return
        self.ui.horizontalSlider.setValue(value + 1)

    def backward(self):
        """Move one logical motion backward."""
        self._pause_playback()
        value = self.ui.horizontalSlider.value()
        self.ui.horizontalSlider.setValue(max(self.ui.horizontalSlider.minimum(), value - 1))

    def forward(self):
        """Move one logical motion forward."""
        self._pause_playback()
        value = self.ui.horizontalSlider.value()
        self.ui.horizontalSlider.setValue(min(self.ui.horizontalSlider.maximum(), value + 1))

    def play(self):
        """Start or pause playback of toolpath highlighting."""
        if self.ui.actionPlay.isChecked():
            stock_playback = (
                self.latheMode and getattr(self, "stockEnabled", False) and hasattr(self, "_start_stock_animation")
            )
            if stock_playback:
                if not self._start_stock_animation():
                    self.ui.actionPlay.setChecked(False)
                    self.timer.stop()
                    return
            elif self.ui.horizontalSlider.value() >= self.ui.horizontalSlider.maximum():
                self.ui.horizontalSlider.setValue(self.ui.horizontalSlider.minimum())
            self.timer.start(self.speedTimer, self)
            LOGGER.info(
                "playback_started lathe=%s stock_animation=%s value=%d maximum=%d interval_ms=%d",
                self.latheMode,
                getattr(self, "_stock_animation_active", False),
                self.ui.horizontalSlider.value(),
                self.ui.horizontalSlider.maximum(),
                self.speedTimer,
            )
        else:
            self.timer.stop()
            LOGGER.info(
                "playback_paused stock_animation=%s value=%d maximum=%d",
                getattr(self, "_stock_animation_active", False),
                self.ui.horizontalSlider.value(),
                self.ui.horizontalSlider.maximum(),
            )

    def stop(self):
        """Stop playback, completing a stock preview before restoring the trace."""
        if getattr(self, "_kernel_execution_active", False):
            self._kernel_cancel_requested = True
            self.ui.statusbar.showMessage(QCoreApplication.translate("MainWindow", "Cancelling CNC execution..."))
            return
        stock_animation = bool(getattr(self, "_stock_animation_active", False))
        self.ui.actionPlay.setChecked(False)
        self.timer.stop()
        self.step = 0
        if stock_animation:
            maximum = self.ui.horizontalSlider.maximum()
            self.ui.horizontalSlider.blockSignals(True)
            self.ui.horizontalSlider.setValue(maximum)
            self.ui.horizontalSlider.blockSignals(False)
            self._leave_stock_animation()
            if self.execution_result is not None and self.execution_result.motions:
                self.valueHandler(maximum, sync_editor=False)
        else:
            self.ui.horizontalSlider.setValue(0)
        LOGGER.info(
            "playback_stopped stock_animation=%s value=%d maximum=%d",
            stock_animation,
            self.ui.horizontalSlider.value(),
            self.ui.horizontalSlider.maximum(),
        )

    def _pause_playback(self):
        if self.ui.actionPlay.isChecked():
            self.ui.actionPlay.setChecked(False)
        self.timer.stop()

    def sliderDrag(self):
        """Synchronize editor cursor with the selected logical motion."""
        if self.ui.actionPlay.isChecked():
            self.timer.stop()
            self.ui.actionPlay.setChecked(False)
        value = self.ui.horizontalSlider.value()
        if value > 0:
            self._sync_editor_to_motion(self._playback_movements[value - 1].motion_end - 1)

    def scheduleAutoUpdate(self):
        """Mark the displayed trace stale and optionally debounce its refresh."""
        if getattr(self, "_loading_document", False):
            return
        self.autoUpdateTimer.stop()
        if getattr(self, "_stock_animation_active", False):
            self.ui.actionPlay.setChecked(False)
            self.timer.stop()
            self._leave_stock_animation()
        self._plot_source_stale = True
        self._deferred_execution_result = None
        self._deferred_execution_source = None
        if hasattr(self, "updateExecutionStatus"):
            self.updateExecutionStatus("STALE")
        if getattr(self, "autoUpdateEnabled", True):
            self.autoUpdateTimer.start()

    def _calculate_editor_source(self, *, show_errors=True, render=False, max_points=None):
        if getattr(self, "_kernel_execution_active", False):
            self._kernel_cancel_requested = True
            return None, None, False

        source = self.ui.editor.text()
        language = "fanuc_turn" if self.latheMode else "fanuc_mill"
        turning = bool(self.latheMode)
        default_unit_scale = 25.4 if getattr(self, "defaultUnits", "mm") == "inch" else 1.0
        home_x = self.xPosMach * 2.0 if turning else self.xPosMach
        wcs_offsets = deepcopy(getattr(self, "wcsOffsets", None))
        if turning and wcs_offsets is not None:
            wcs_offsets = {code: (values[0] * 2.0, *values[1:]) for code, values in wcs_offsets.items()}

        attribute = "tools" if turning else "millingTools"
        turning_tools = deepcopy(getattr(self, "tools", {}) or {})
        milling_tools = deepcopy(getattr(self, "millingTools", {}) or {})
        current_tools = turning_tools if turning else milling_tools
        inference = deepcopy(getattr(self, "program_tool_inference", {}) or {})
        previous_inference = deepcopy(inference.get(attribute, {}))
        correction_enabled = bool(getattr(self, "correctionEnabled", True))
        arc_tolerance = float(getattr(self, "arcTolerance", 0.01))

        self._kernel_execution_active = True
        self._kernel_cancel_requested = False
        cancellation = Event()

        def cancelled():
            return cancellation.is_set() or bool(self._kernel_cancel_requested)

        options = deepcopy(
            {
                "language": language,
                "source_arc_type": 1 if turning else getattr(self, "arc_type", 1),
                "default_unit_scale": default_unit_scale,
                "home_x": home_x,
                "home_y": self.yPosMach,
                "home_z": self.zPosMach,
                "wcs_offsets": wcs_offsets,
                "emulate_g28_home": getattr(self, "homeConfigured", True),
                "cancelled": cancelled,
            }
        )

        calculate = partial(
            _calculate_source,
            current_tools=current_tools,
            previous_inference=previous_inference,
            turning=turning,
            setup_unit_scale=default_unit_scale,
            turning_tools=turning_tools,
            milling_tools=milling_tools,
            correction_enabled=correction_enabled,
            render=render,
            arc_tolerance=arc_tolerance,
            max_points=max_points,
            is_cancelled=cancelled,
        )

        try:
            result, points, updated_tools, inferred, execution_ms, render_limited = run_execution(
                self,
                calculate,
                source,
                options,
                cancellation.set,
                title=QCoreApplication.translate("MainWindow", "CNC execution"),
                status_text=QCoreApplication.translate("MainWindow", "Executing CNC program…"),
                cancelling_text=QCoreApplication.translate("MainWindow", "Cancelling CNC execution…"),
            )
        finally:
            self._kernel_execution_active = False

        setattr(self, attribute, updated_tools)
        inference[attribute] = inferred
        self.program_tool_inference = inference
        self._last_execution_ms = execution_ms
        LOGGER.debug(
            "execution language=%s ok=%s complete=%s motions=%d steps=%d diagnostics=%d duration_ms=%.3f "
            "source_chars=%d",
            language,
            result.ok,
            getattr(result, "complete", result.ok),
            len(result.motions),
            len(getattr(result, "execution_steps", ())),
            len(result.diagnostics),
            self._last_execution_ms,
            len(source),
        )
        if result.diagnostics and show_errors:
            self.ui.statusbar.showMessage("; ".join(f"{d.code}: {d.message}" for d in result.diagnostics), 10000)
        return result, points, render_limited

    def _execute_editor_source(self, *, show_errors=True):
        result, _points, _render_limited = self._calculate_editor_source(show_errors=show_errors)
        return result

    def discover_program_tools(self, source):
        attribute = "tools" if self.latheMode else "millingTools"
        current = getattr(self, attribute, None)
        if current is None:
            current = {}
            setattr(self, attribute, current)
        inference = getattr(self, "program_tool_inference", {})
        inference[attribute] = refresh_setup(
            source,
            current,
            inference.get(attribute, {}),
            turning=self.latheMode,
            default_unit_scale=25.4 if getattr(self, "defaultUnits", "mm") == "inch" else 1.0,
        )
        self.program_tool_inference = inference

    def arcPointsPerCircle(self, result):
        """Convert the configured maximum chord error to a sampling count."""
        return _arc_points_per_circle(result, self.arcTolerance)

    def analyzeEditorSource(self):
        """Return a fresh kernel analysis for read-only UI consumers."""
        return self._execute_editor_source(show_errors=False)

    def _countProgramPoints(self):
        result = self.execution_result or self._execute_editor_source(show_errors=False)
        if result is None or not result.motions:
            return 0
        return len(
            render_trace(
                result,
                lathe_radius_view=self.latheMode,
                arc_points_per_circle=self.arcPointsPerCircle(result),
            )
        )

    def autoUpdate(self):
        """Debounced refresh for programs whose sampled render path is small."""
        if getattr(self, "_kernel_execution_active", False):
            return False
        if getattr(self, "_stock_animation_active", False):
            self._clear_stock_animation()
        auto_limit = max(1, int(getattr(self, "autoUpdateMaxSegments", AUTO_REFRESH_MAX_POINTS)))
        result, points, render_limited = self._calculate_editor_source(
            show_errors=False,
            render=True,
            max_points=auto_limit,
        )
        if result is None or not result.motions:
            if hasattr(self, "updateExecutionStatus"):
                self.updateExecutionStatus(result=result, elapsed_ms=getattr(self, "_last_execution_ms", None))
            return
        if render_limited:
            self._auto_update_deferred = True
            self._deferred_execution_result = result
            self._deferred_execution_source = self.ui.editor.text()
            self.ui.statusbar.showMessage(
                f"Trajectory exceeds the Auto Update limit of {auto_limit:,} points; press Update.", 10000
            )
            return
        if points is None:
            return
        self._auto_update_deferred = False
        self._finishDataUpdate(result, points)

    def _render_existing_result(self, result):
        cancellation = Event()
        self._kernel_execution_active = True
        self._kernel_cancel_requested = False
        try:
            try:
                return run_execution(
                    self,
                    lambda _source, **_options: render_trace(
                        result,
                        lathe_radius_view=self.latheMode,
                        arc_points_per_circle=self.arcPointsPerCircle(result),
                        cancelled=cancellation.is_set,
                    ),
                    "",
                    {},
                    cancellation.set,
                    title=QCoreApplication.translate("MainWindow", "CNC execution"),
                    status_text=QCoreApplication.translate("MainWindow", "Building toolpath…"),
                    cancelling_text=QCoreApplication.translate("MainWindow", "Cancelling toolpath calculation…"),
                )
            except InterruptedError:
                return None
        finally:
            self._kernel_execution_active = False

    def updateData(self, *, show_errors=True):
        """Execute editor source through the single authoritative CNC kernel."""
        if getattr(self, "_kernel_execution_active", False):
            return False
        if hasattr(self, "updateExecutionStatus"):
            self.updateExecutionStatus("UPDATING")
        if getattr(self, "_stock_animation_active", False):
            self.ui.actionPlay.setChecked(False)
            self.timer.stop()
            self._clear_stock_animation()
        if hasattr(self, "autoUpdateTimer"):
            self.autoUpdateTimer.stop()
        source = self.ui.editor.text()
        deferred_result = getattr(self, "_deferred_execution_result", None)
        if deferred_result is not None and getattr(self, "_deferred_execution_source", None) == source:
            result = deferred_result
            points = self._render_existing_result(result)
        else:
            self._deferred_execution_result = None
            self._deferred_execution_source = None
            result, points, _render_limited = self._calculate_editor_source(
                show_errors=show_errors,
                render=True,
            )
        if result is None or not result.motions:
            self.clearPlot()
            if hasattr(self, "updateExecutionStatus"):
                self.updateExecutionStatus(result=result, elapsed_ms=getattr(self, "_last_execution_ms", None))
            return False
        if points is None:
            return False
        self._finishDataUpdate(result, points)
        self._auto_update_deferred = False
        return True

    def _finishDataUpdate(self, result=None, points=None, playback_value=None):
        """Bind ``ExecutionResult`` to render, statistics and playback consumers."""
        started = perf_counter()
        result = result if result is not None else self.execution_result
        if result is None:
            return False
        render_started = perf_counter()
        if points is None:
            points = render_trace(
                result,
                lathe_radius_view=self.latheMode,
                arc_points_per_circle=self.arcPointsPerCircle(result),
            )
        self._deferred_execution_result = None
        self._deferred_execution_source = None
        self.execution_result = result
        self.render_points = points
        self._plot_source_stale = False
        if hasattr(self, "updateExecutionStatus"):
            self.updateExecutionStatus(result=result, elapsed_ms=getattr(self, "_last_execution_ms", None))
        render_ms = (perf_counter() - render_started) * 1000.0
        self._playback_movements, self._motion_to_playback = build_playback_movements(result.motions)
        self._source_motion_index = {}
        self._motion_unit_scales = []
        for step in result.execution_steps:
            self._motion_unit_scales.extend([float(step.unit_scale)] * step.emitted_count)
        if len(self._motion_unit_scales) < len(result.motions):
            self._motion_unit_scales.extend([1.0] * (len(result.motions) - len(self._motion_unit_scales)))
        else:
            del self._motion_unit_scales[len(result.motions) :]
        for idx, motion in enumerate(result.motions):
            if motion.source_block is not None:
                # A canned-cycle source block can expand to many motions.  An
                # editor click should select the first generated motion, while
                # playback still walks all generated motions normally.
                self._source_motion_index.setdefault(motion.source_block, self._motion_to_playback[idx])

        self._motion_render_end = [0] * len(result.motions)
        for point_index, point in enumerate(self.render_points, start=1):
            if 0 <= point.motion_index < len(self._motion_render_end):
                self._motion_render_end[point.motion_index] = point_index
        last = 0
        for idx, end in enumerate(self._motion_render_end):
            if end:
                last = end
            self._motion_render_end[idx] = last
        pack_started = perf_counter()
        self._set_trace_geometry()
        pack_ms = (perf_counter() - pack_started) * 1000.0
        statistics_started = perf_counter()
        self.calcDist()
        statistics_ms = (perf_counter() - statistics_started) * 1000.0
        enabled = bool(result.motions)
        self.ui.actionStep_Backward.setEnabled(enabled)
        self.ui.actionStep_Forward.setEnabled(enabled)
        self.ui.actionPlay.setEnabled(enabled)
        self.ui.actionStop.setEnabled(enabled)
        self.ui.horizontalSlider.blockSignals(True)
        self.ui.horizontalSlider.setMinimum(0)
        playback_count = len(self._playback_movements)
        self.ui.horizontalSlider.setMaximum(playback_count)
        self.ui.horizontalSlider.setPageStep(max(1, playback_count // 10))
        if getattr(self, "_fit_view_after_program_load", False) or playback_value is None:
            playback_value = playback_count
        playback_value = max(0, min(int(playback_value), playback_count))
        self.ui.horizontalSlider.setValue(playback_value)
        self.ui.horizontalSlider.blockSignals(False)
        if hasattr(self, "_refresh_auto_stock_suggestion"):
            self._refresh_auto_stock_suggestion()
        scene_started = perf_counter()
        self.loadPlot()
        self._create_trace_items()
        if hasattr(self, "_update_stock_outline"):
            self._update_stock_outline()
        if result.motions:
            self.valueHandler(playback_value, sync_editor=False)
        if getattr(self, "_fit_view_after_program_load", False):
            self._fit_view_after_program_load = False
            self.fitToView()
        LOGGER.info(
            "plot_updated total_ms=%.3f render_ms=%.3f pack_ms=%.3f statistics_ms=%.3f scene_ms=%.3f "
            "motions=%d render_points=%d lathe=%s playback=%d",
            (perf_counter() - started) * 1000.0,
            render_ms,
            pack_ms,
            statistics_ms,
            (perf_counter() - scene_started) * 1000.0,
            len(result.motions),
            len(self.render_points),
            self.latheMode,
            playback_value,
        )

    def lstExport(self):
        """Compatibility hook: export data now comes directly from ExecutionResult."""
        return list(self.execution_result.motions) if self.execution_result is not None else []

    def toolPath(self):
        """Return trace-based path length and estimated machining time."""
        if self.execution_result is None or not self.execution_result.motions:
            return ""
        stats = trace_statistics(
            self.execution_result,
            lathe_radius_view=self.latheMode,
            rapid_feed=self.rapidFeed,
        )
        time_value = stats["total_time_min"]
        if time_value is None:
            time_text = "UNKNOWN"
        else:
            time_min = float(time_value)
            time_sec = time_min * 60
            time_text = "{h:02}:{m:02}:{s:02}".format(
                h=floor(time_min / 60), m=floor(time_min % 60), s=floor(time_sec % 60)
            )
        return (
            self.co
            + f"Toolpath Length: {float(stats['total_length']):.3f}"
            + self.ci
            + "\n"
            + self.co
            + f"Machining Time: {time_text}"
            + self.ci
            + "\n"
        )

    def toolPathLimits(self):
        """Return min/max extents from the authoritative trace."""
        if self.execution_result is None or not self.execution_result.motions:
            return ""
        stats = trace_statistics(
            self.execution_result,
            lathe_radius_view=False,
            rapid_feed=self.rapidFeed,
        )
        bounds = stats["bounds"]
        if bounds is None:
            return ""
        (xmin, xmax), (ymin, ymax), (zmin, zmax) = bounds
        return (
            self.co
            + f"X MIN: {round(xmin, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"Y MIN: {round(ymin, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"Z MIN: {round(zmin, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"X MAX: {round(xmax, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"Y MAX: {round(ymax, 3)}"
            + self.ci
            + "\n"
            + self.co
            + f"Z MAX: {round(zmax, 3)}"
            + self.ci
        )

    def statistics(self):
        """Display path length, machining time, and limits in the statistics window."""
        if self.execution_result is not None and self.execution_result.motions:
            stats = trace_statistics(self.execution_result, rapid_feed=self.rapidFeed)
            self.statisticsDlg.show_statistics(stats)
        else:
            self.statisticsDlg.show_report("No Data Available")

    def list_rindex(self, li, x):
        """Return the last index of x in list li."""
        return last_index(li, x)
