"""Execution, playback, auto-refresh, and statistics helpers for the main window."""

import logging
from math import acos, ceil, floor, pi

from PyQt6.QtWidgets import QMessageBox

from app.gcode.core import last_index
from app.gcode.kernel import execute
from app.gcode.trace_tools import RenderLimitExceeded, render_trace, trace_statistics

AUTO_REFRESH_MAX_LINES = 5000
AUTO_REFRESH_MAX_POINTS = 20000
AUTO_REFRESH_DELAY_MS = 500
LOGGER = logging.getLogger(__name__)


class MainWindowExecutionMixin:
    def timerEvent(self, event):
        """Advance playback by logical CNC motion, not editor line."""
        del event
        maximum = self.ui.horizontalSlider.maximum()
        value = self.ui.horizontalSlider.value()
        if maximum <= 0 or value >= maximum:
            self.stop()
            return
        self.ui.horizontalSlider.setValue(value + 1)

    def backward(self):
        """Move one logical motion backward."""
        value = self.ui.horizontalSlider.value()
        self.ui.horizontalSlider.setValue(max(self.ui.horizontalSlider.minimum(), value - 1))

    def forward(self):
        """Move one logical motion forward."""
        value = self.ui.horizontalSlider.value()
        self.ui.horizontalSlider.setValue(min(self.ui.horizontalSlider.maximum(), value + 1))

    def play(self):
        """Start or pause playback of toolpath highlighting."""
        if self.ui.actionPlay.isChecked():
            self.timer.start(self.speedTimer, self)
        else:
            self.timer.stop()

    def stop(self):
        """Stop logical-motion playback and return to the first motion."""
        self.ui.actionPlay.setChecked(False)
        self.timer.stop()
        self.step = 0
        if self.ui.horizontalSlider.maximum() >= 1:
            self.ui.horizontalSlider.setValue(1)

    def sliderDrag(self):
        """Synchronize editor cursor with the selected logical motion."""
        if self.ui.actionPlay.isChecked():
            self.timer.stop()
            self.ui.actionPlay.setChecked(False)
        self._sync_editor_to_motion(self.ui.horizontalSlider.value() - 1)

    def scheduleAutoUpdate(self):
        """Invalidate stale execution state and restart the edit debounce timer."""
        self.autoUpdateTimer.stop()
        if getattr(self, "execution_result", None) is not None or getattr(self, "render_points", ()):
            self.clearPlot()
        self.autoUpdateTimer.start()

    def _execute_editor_source(self, *, show_errors=True):
        source = self.ui.editor.text()
        language = "fanuc_turn" if self.latheMode else "fanuc_mill"
        result = execute(
            source,
            language=language,
            source_arc_type=getattr(self, "arc_type", 1),
            default_unit_scale=25.4 if getattr(self, "defaultUnits", "mm") == "inch" else 1.0,
            tools=getattr(self, "tools", None) if getattr(self, "correctionEnabled", True) else {},
            milling_tools=getattr(self, "millingTools", None) if getattr(self, "correctionEnabled", True) else {},
            home_x=self.xPosMach,
            home_y=self.yPosMach,
            home_z=self.zPosMach,
            wcs_offsets=getattr(self, "wcsOffsets", None),
            emulate_g28_home=getattr(self, "homeConfigured", True),
        )
        LOGGER.debug(
            "execution language=%s ok=%s motions=%d diagnostics=%d",
            language,
            result.ok,
            len(result.motions),
            len(result.diagnostics),
        )
        if not result.ok and show_errors:
            message = "\n".join(f"{d.code}: {d.message}" for d in result.diagnostics) or "Unable to execute G-code"
            QMessageBox.warning(self, "Easy G-code Plot", message)
        elif result.diagnostics and show_errors:
            self.ui.statusbar.showMessage("; ".join(f"{d.code}: {d.message}" for d in result.diagnostics), 10000)
        return result

    def arcPointsPerCircle(self, result):
        """Convert the configured maximum chord error to a sampling count."""
        radii = [motion.arc.radius for motion in result.motions if motion.arc is not None]
        if not radii:
            return 3
        radius = max(radii)
        tolerance = min(max(self.arcTolerance, 1e-9), radius * 2)
        angle = acos(max(-1.0, min(1.0, 1.0 - tolerance / radius)))
        return max(3, ceil(pi / angle)) if angle > 0 else 314

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
                arc_type=self.arc_type,
                arc_points_per_circle=self.arcPointsPerCircle(result),
            )
        )

    def autoUpdate(self):
        """Debounced refresh for programs whose sampled render path is small."""
        if self.ui.editor.lines() > AUTO_REFRESH_MAX_LINES:
            return
        result = self._execute_editor_source(show_errors=False)
        if result is None or not result.motions:
            return
        try:
            points = render_trace(
                result,
                lathe_radius_view=self.latheMode,
                arc_type=self.arc_type,
                arc_points_per_circle=self.arcPointsPerCircle(result),
                max_points=AUTO_REFRESH_MAX_POINTS,
            )
        except RenderLimitExceeded:
            return
        self._finishDataUpdate(result, points)

    def updateData(self):
        """Execute editor source through the single authoritative CNC kernel."""
        if hasattr(self, "autoUpdateTimer"):
            self.autoUpdateTimer.stop()
        result = self._execute_editor_source(show_errors=True)
        if result is None or not result.motions:
            self.clearPlot()
            return False
        self._finishDataUpdate(result)
        return True

    def _finishDataUpdate(self, result=None, points=None):
        """Bind ``ExecutionResult`` to render, statistics and playback consumers."""
        if result is not None:
            self.execution_result = result
        result = self.execution_result
        if result is None:
            return
        self.render_points = (
            points
            if points is not None
            else render_trace(
                result,
                lathe_radius_view=self.latheMode,
                arc_type=self.arc_type,
                arc_points_per_circle=self.arcPointsPerCircle(result),
            )
        )
        self._source_motion_index = {}
        for idx, motion in enumerate(result.motions):
            if motion.source_block is not None:
                # A canned-cycle source block can expand to many motions.  An
                # editor click should select the first generated motion, while
                # playback still walks all generated motions normally.
                self._source_motion_index.setdefault(motion.source_block, idx)

        self._motion_render_end = [0] * len(result.motions)
        for point_index, point in enumerate(self.render_points, start=1):
            if 0 <= point.motion_index < len(self._motion_render_end):
                self._motion_render_end[point.motion_index] = point_index
        last = 0
        for idx, end in enumerate(self._motion_render_end):
            if end:
                last = end
            self._motion_render_end[idx] = last
        self.calcDist()
        enabled = bool(result.motions)
        self.ui.actionStep_Backward.setEnabled(enabled)
        self.ui.actionStep_Forward.setEnabled(enabled)
        self.ui.actionPlay.setEnabled(enabled)
        self.ui.actionStop.setEnabled(enabled)
        self.ui.horizontalSlider.blockSignals(True)
        self.ui.horizontalSlider.setMinimum(1)
        self.ui.horizontalSlider.setMaximum(max(1, len(result.motions)))
        self.ui.horizontalSlider.setPageStep(max(1, len(result.motions) // 10))
        self.ui.horizontalSlider.setValue(max(1, len(result.motions)))
        self.ui.horizontalSlider.blockSignals(False)
        self.loadPlot()
        self._create_trace_items()
        if result.motions:
            self.valueHandler(len(result.motions))

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
            arc_type=self.arc_type,
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
            arc_type=self.arc_type,
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
        """Display path length, machining time, and limits in a message box."""
        txt = self.toolPath() + self.toolPathLimits()
        if txt:
            QMessageBox.information(self, "Easy G-code Plot", txt.replace("(", "").replace(")", ""))
        else:
            QMessageBox.information(self, "Easy G-code Plot", "No Data Available")

    def list_rindex(self, li, x):
        """Return the last index of x in list li."""
        return last_index(li, x)
