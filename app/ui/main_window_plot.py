"""OpenGL rendering, view, grid, and trajectory-picking helpers for the main window."""

import math

from PyQt6.QtGui import QColor, QVector3D, QVector4D
from PyQt6.QtWidgets import QMenu
from pyqtgraph.opengl import GLGridItem, GLScatterPlotItem

from app.gcode.core import calculate_scene_geometry
from app.ui.axis_triad import AxisTriadItem
from app.ui.plot_grid import adaptive_grid_geometry
from app.ui.plot_navigation import point_segment_distance as _point_segment_distance
from app.ui.toolpath_vbo import ToolpathVboItem, segments_from_render_points

PICK_DISTANCE_PX = 8.0
CURSOR_SIZE_PX = 7.0
RAPID_COLOR = "#d02020"


class MainWindowPlotMixin:
    def zoomIn(self):
        """Zoom in on the plot."""
        dist = self.ui.graphicsView.opts["distance"]
        self.ui.graphicsView.setCameraPosition(distance=dist * 0.9)
        self._update_adaptive_grid()

    def zoomOut(self):
        """Zoom out on the plot."""
        dist = self.ui.graphicsView.opts["distance"]
        self.ui.graphicsView.setCameraPosition(distance=dist * 1.1)
        self._update_adaptive_grid()

    def gridChecked(self):
        """Toggle plot grid visibility and refresh the view."""
        self.plotGrid = self.ui.actionGrid.isChecked()
        self.loadPlot()
        self._create_trace_items()
        if self.execution_result is not None and self.execution_result.motions:
            self.valueHandler(self.ui.horizontalSlider.value(), sync_editor=False)

    def plotContextMenu(self, point):
        """Show context menu for plot view controls."""
        menu = QMenu()
        menu.addAction(self.ui.actionFitToView)
        menu.addSeparator()
        menu.addAction(self.ui.actionZoom_In)
        menu.addAction(self.ui.actionZoom_Out)
        menu.addSeparator()
        menu.addAction(self.ui.action3D)
        menu.addAction(self.ui.actionTop)
        menu.addAction(self.ui.actionFront)
        menu.addAction(self.ui.actionLeft)
        menu.addSeparator()
        menu.addAction(self.ui.actionGrid)
        menu.exec(self.ui.graphicsView.mapToGlobal(point))

    def fitToView(self):
        """Center and fit the complete rendered toolpath in the active plot projection."""
        if not self.render_points:
            return

        bounds = tuple(
            (min(values), max(values))
            for values in (
                [point.x for point in self.render_points],
                [point.y for point in self.render_points],
                [point.z for point in self.render_points],
            )
        )
        spans = tuple(high - low for low, high in bounds)
        center = QVector3D(*(low + span / 2.0 for (low, _high), span in zip(bounds, spans)))
        mode = "lathe" if self.latheMode else getattr(self, "_view_mode", "3d")

        view = self.ui.graphicsView
        aspect = max(float(view.width()), 1.0) / max(float(view.height()), 1.0)
        half_fov = math.radians(max(float(view.opts.get("fov", 60.0)), 0.01) / 2.0)
        if mode == "lathe":
            # Keep the established turning fit behavior independent from milling views.
            half_extent = max(spans[2] / 2.0, spans[0] / (2.0 * aspect))
            half_extent = max(half_extent, 0.5)
            distance = half_extent * 1.1 / math.tan(half_fov)
        else:
            # CNCEditor fits all eight bounds corners after the active view rotation.
            # GLViewWidget's fov is horizontal, so vertical view-space extent must
            # be multiplied by width/height when converted to camera distance.
            matrix = view.viewMatrix()
            corners = [matrix * QVector4D(x, y, z, 1.0) for x in bounds[0] for y in bounds[1] for z in bounds[2]]
            view_center = matrix * QVector4D(center, 1.0)
            tangent = math.tan(half_fov)
            distance = max(
                max(abs(corner.x() - view_center.x()), abs(corner.y() - view_center.y()) * aspect, 0.5)
                / (0.9 * tangent)
                + (corner.z() - view_center.z())
                for corner in corners
            )

        view.opts["center"] = center
        view.setCameraPosition(distance=distance)
        self.dist = distance
        self._update_adaptive_grid()

    def _create_trace_items(self):
        """Attach the persistent VBO toolpath and lightweight cursor overlay."""
        width = getattr(self, "plotLineWidth", 1.5)
        toolpath_item = getattr(self, "_toolpath_item", None)
        execution_result = getattr(self, "execution_result", None)
        if toolpath_item is None and execution_result is not None:
            toolpath_item = ToolpathVboItem()
            toolpath_item.set_segments(
                segments_from_render_points(self.render_points, execution_result.motions),
                len(execution_result.motions),
            )
            self._toolpath_item = toolpath_item
        if toolpath_item is not None:
            toolpath_item.set_style(
                rapid_color=getattr(self, "plotRapidColor", RAPID_COLOR),
                linear_color=self.plotLineColor,
                arc_color=getattr(self, "plotArcColor", "#008000"),
                width=width,
            )
            if toolpath_item not in self.ui.graphicsView.items:
                self.ui.graphicsView.addItem(toolpath_item)

        if getattr(self, "_cursor_item", None) is None:
            self._cursor_item = GLScatterPlotItem(
                pos=[],
                color=QColor(getattr(self, "plotCurrentColor", self.plotLineColor)),
                size=CURSOR_SIZE_PX,
                pxMode=True,
            )
            self._cursor_item.setGLOptions("translucent")
        if self._cursor_item not in self.ui.graphicsView.items:
            self.ui.graphicsView.addItem(self._cursor_item)

    def _set_trace_geometry(self):
        """Pack new trace geometry once; GPU upload remains paint-lazy."""
        if getattr(self, "_toolpath_item", None) is None:
            self._toolpath_item = ToolpathVboItem()
        result = self.execution_result
        motions = result.motions if result is not None else ()
        self._toolpath_item.set_segments(
            segments_from_render_points(self.render_points, motions),
            len(motions),
        )

    def _dispose_trace_item(self):
        """Release trajectory buffers before the owning GL view disappears."""
        toolpath_item = getattr(self, "_toolpath_item", None)
        if toolpath_item is not None:
            toolpath_item.dispose()
        self._toolpath_item = None

    def _project_world_to_screen(self, x, y, z):
        """Project one world point to GLViewWidget pixel coordinates."""
        view = self.ui.graphicsView
        viewport = view.getViewport()
        try:
            projection = view.projectionMatrix(viewport, viewport)
        except TypeError:  # pyqtgraph < 0.14 compatibility
            projection = view.projectionMatrix(viewport)  # pylint: disable=no-value-for-parameter
        clip = projection * view.viewMatrix() * QVector4D(float(x), float(y), float(z), 1.0)
        w = clip.w()
        if abs(w) < 1e-12:
            return None
        ndc_x = clip.x() / w
        ndc_y = clip.y() / w
        vx, vy, vw, vh = viewport
        return (
            vx + (ndc_x + 1.0) * 0.5 * vw,
            vy + (1.0 - (ndc_y + 1.0) * 0.5) * vh,
        )

    def _pick_trace_at(self, position):
        """Select the nearest trajectory segment on Shift+Click in a 2D view."""
        view_mode = "lathe" if self.latheMode else getattr(self, "_view_mode", "3d")
        if view_mode not in {"lathe", "top", "front", "left"} or not self.render_points:
            return False

        px = float(position.x())
        py = float(position.y())
        best_distance = PICK_DISTANCE_PX
        best_motion = None
        projected_previous = self._project_world_to_screen(
            self.render_points[0].x, self.render_points[0].y, self.render_points[0].z
        )
        for current in self.render_points[1:]:
            projected_current = self._project_world_to_screen(current.x, current.y, current.z)
            if projected_previous is not None and projected_current is not None:
                distance = _point_segment_distance(
                    px, py, projected_previous[0], projected_previous[1], projected_current[0], projected_current[1]
                )
                if distance <= best_distance:
                    best_distance = distance
                    best_motion = current.motion_index
            projected_previous = projected_current

        result = self.execution_result
        if result is None or best_motion is None or not 0 <= best_motion < len(result.motions):
            return False
        self.ui.horizontalSlider.setValue(best_motion + 1)
        self._sync_editor_to_motion(best_motion)
        source_block = result.motions[best_motion].source_block
        if source_block is not None:
            self.ui.statusbar.showMessage(
                f"Trajectory source: line {source_block + 1}, motion {best_motion + 1} (Shift+Click)", 5000
            )
        return True

    def _sync_editor_to_motion(self, idx):
        result = self.execution_result
        if result is None or not 0 <= idx < len(result.motions):
            return
        block = result.motions[idx].source_block
        if block is None or block < 0 or block >= self.ui.editor.lines():
            return
        if self.ui.editor.getCursorPosition()[0] == block:
            return
        self._syncing_cursor = True
        try:
            self.ui.editor.setCursorPosition(block, 0)
        finally:
            self._syncing_cursor = False

    def clearPlot(self):
        """Reset authoritative execution and render/playback state."""
        self._dispose_trace_item()
        self.execution_result = None
        self.render_points = []
        self._motion_render_end = []
        self._source_motion_index = {}
        self._syncing_cursor = False
        self._drawing_item = None
        self._arc_item = None
        self._rapid_item = None
        self._cursor_item = None
        self._lathe_grid_item = None
        self._lathe_grid_center = (0.0, 0.0)
        self._milling_grid_item = None
        self._milling_grid_center = (0.0, 0.0, 0.0)
        self.timer.stop()
        self.step = 0
        for widget in (
            self.ui.lineEditX,
            self.ui.lineEditY,
            self.ui.lineEditZ,
            self.ui.lineEdit_I,
            self.ui.lineEdit_J,
            self.ui.lineEdit_K,
            self.ui.lineEditFeed,
        ):
            widget.clear()
        self.ui.horizontalSlider.setMinimum(1)
        self.ui.horizontalSlider.setMaximum(1)
        self.ui.horizontalSlider.setValue(1)
        self.ui.actionStep_Backward.setEnabled(False)
        self.ui.actionStep_Forward.setEnabled(False)
        self.ui.actionPlay.setChecked(False)
        self.ui.actionPlay.setEnabled(False)
        self.ui.actionStop.setEnabled(False)
        self.loadPlot()

    def valueHandler(self, value, *, sync_editor=True):
        """Display one logical motion and optionally synchronize the editor cursor."""
        result = self.execution_result
        if result is None or not result.motions:
            return
        idx = max(0, min(len(result.motions) - 1, value - 1))
        motion = result.motions[idx]
        scale_x = 0.5 if self.latheMode else 1.0
        self.ui.lineEditX.setText(str(round(motion.end_x * scale_x, 3)))
        self.ui.lineEditY.setText(str(round(motion.end_y, 3)))
        self.ui.lineEditZ.setText(str(round(motion.end_z, 3)))
        self.ui.lineEdit_I.setText("" if motion.i is None else str(round(motion.i, 3)))
        self.ui.lineEdit_J.setText("" if motion.j is None else str(round(motion.j, 3)))
        self.ui.lineEdit_K.setText("" if motion.k is None else str(round(motion.k, 3)))
        self.ui.lineEditFeed.setText("Rapid" if motion.move == 0 else ("" if motion.feed is None else str(motion.feed)))
        if getattr(self, "_toolpath_item", None) is None or self._cursor_item is None:
            self._create_trace_items()
        self._toolpath_item.set_visible_logical_count(idx + 1)
        end = self._motion_render_end[idx] if idx < len(self._motion_render_end) else len(self.render_points)
        if end > 0:
            point = self.render_points[min(end, len(self.render_points)) - 1]
            self._cursor_item.setData(
                pos=[(point.x, point.y, point.z)],
                color=QColor(self.plotCurrentColor),
                size=CURSOR_SIZE_PX,
                pxMode=True,
            )
        if sync_editor:
            self._sync_editor_to_motion(idx)

    def loadPlot(self):
        """Redraw axes, background, and the active orthographic grid."""
        self.ui.graphicsView.clear()
        self._cursor_item = None
        self._lathe_grid_item = None
        self._lathe_grid_center = (0.0, 0.0)
        self._milling_grid_item = None
        self._milling_grid_center = (0.0, 0.0, 0.0)
        self.ui.graphicsView.setBackgroundColor(self.plotBackground)
        if self.plotGrid:
            if self.latheMode:
                self._lathe_grid_item = GLGridItem()
                self._lathe_grid_item.setColor(QColor(self.plotGridColor))
                self._lathe_grid_item.rotate(90, 1, 0, 0)
                self.ui.graphicsView.addItem(self._lathe_grid_item)
            else:
                self._milling_grid_item = GLGridItem()
                self._milling_grid_item.setColor(QColor(self.plotGridColor))
                view_mode = getattr(self, "_view_mode", "3d")
                if view_mode == "front":
                    self._milling_grid_item.rotate(90, 1, 0, 0)
                elif view_mode == "left":
                    self._milling_grid_item.rotate(90, 0, 1, 0)
                self.ui.graphicsView.addItem(self._milling_grid_item)
            self._update_adaptive_grid()

        if self.plotAxes:
            if getattr(self, "_axis_triad_item", None) is None:
                self._axis_triad_item = AxisTriadItem()
            self.ui.graphicsView.addItem(self._axis_triad_item)

    def _adaptive_grid_size(self):
        view = self.ui.graphicsView
        return adaptive_grid_geometry(
            view.opts["distance"], view.opts["fov"], view.height(), viewport_width=view.width()
        )

    def _update_adaptive_grid(self):
        """Update the active 2D/orthographic grid after zoom, pan, or resize."""
        axis_triad = getattr(self, "_axis_triad_item", None)
        if axis_triad is not None:
            axis_triad.sync_screen_size()
        if self.latheMode:
            self._update_lathe_grid()
        else:
            self._update_milling_grid()

    def _update_lathe_grid(self):
        """Adapt the single XZ lathe grid to the current camera zoom."""
        grid = getattr(self, "_lathe_grid_item", None)
        if grid is None or not self.latheMode or not self.plotGrid:
            return
        spacing, size = self._adaptive_grid_size()
        if self.plotGridStep > 0:
            spacing = self.plotGridStep
        grid.setSize(size, size)
        grid.setSpacing(spacing, spacing)
        center = self.ui.graphicsView.opts["center"]
        snapped_x = round(center.x() / spacing) * spacing
        snapped_z = round(center.z() / spacing) * spacing
        old_x, old_z = getattr(self, "_lathe_grid_center", (0.0, 0.0))
        grid.translate(snapped_x - old_x, 0.0, snapped_z - old_z)
        self._lathe_grid_center = (snapped_x, snapped_z)

    def _update_milling_grid(self):
        """Adapt the active milling grid in Top, Front, and Left views only."""
        grid = getattr(self, "_milling_grid_item", None)
        view_mode = getattr(self, "_view_mode", "3d")
        if grid is None or self.latheMode or not self.plotGrid:
            return

        spacing, size = self._adaptive_grid_size()
        if self.plotGridStep > 0:
            spacing = self.plotGridStep
        grid.setSize(size, size)
        grid.setSpacing(spacing, spacing)
        center = self.ui.graphicsView.opts["center"]
        if view_mode == "top":
            snapped = (round(center.x() / spacing) * spacing, round(center.y() / spacing) * spacing, 0.0)
        elif view_mode == "front":
            snapped = (round(center.x() / spacing) * spacing, 0.0, round(center.z() / spacing) * spacing)
        elif view_mode == "left":
            snapped = (0.0, round(center.y() / spacing) * spacing, round(center.z() / spacing) * spacing)
        else:
            snapped = (round(center.x() / spacing) * spacing, round(center.y() / spacing) * spacing, 0.0)

        old = getattr(self, "_milling_grid_center", (0.0, 0.0, 0.0))
        grid.translate(snapped[0] - old[0], snapped[1] - old[1], snapped[2] - old[2])
        self._milling_grid_center = snapped

    def plotCurLine(self):
        """Map the current source line to its last logical motion."""
        if self._syncing_cursor or getattr(self, "_plot_source_stale", False):
            return
        line = self.ui.editor.getCursorPosition()[0]
        idx = self._source_motion_index.get(line)
        if idx is not None:
            self.ui.horizontalSlider.setValue(idx + 1)

    def setView(self, fov, elevation, azimuth, use_calc_dist=True, dist_scale=6000):
        """Set camera view with optional distance recalculation."""
        if use_calc_dist:
            self.calcDist()
            dist = self.dist * dist_scale
        else:
            dist = self.dist
        self.ui.graphicsView.opts["fov"] = fov
        self.ui.graphicsView.setCameraPosition(distance=dist, elevation=elevation, azimuth=azimuth)
        self._update_adaptive_grid()

    def _refresh_view_plot(self):
        self.loadPlot()
        self._create_trace_items()
        if self.execution_result is not None and self.execution_result.motions:
            self.valueHandler(self.ui.horizontalSlider.value(), sync_editor=False)

    def refreshPlotView(self):
        """Redraw the plot after user-facing visual options change."""
        self._refresh_view_plot()

    def view3d(self):
        """Set 3D camera angle with grid disabled."""
        self._view_mode = "3d"
        self.ui.actionGrid.setEnabled(True)
        self.setView(60, 30, -45, use_calc_dist=False, dist_scale=1)
        self._refresh_view_plot()

    def viewTop(self):
        """Switch camera to a top-down orthographic view."""
        self._view_mode = "top"
        self.ui.actionGrid.setEnabled(True)
        self.setView(0.01, 90, -90)
        self._refresh_view_plot()

    def viewFront(self):
        """Switch camera to a front orthographic view."""
        self._view_mode = "front"
        self.ui.actionGrid.setEnabled(True)
        self.setView(0.01, 0, -90)
        self._refresh_view_plot()

    def viewLeft(self):
        """Switch camera to a left orthographic view."""
        self._view_mode = "left"
        self.ui.actionGrid.setEnabled(True)
        self.setView(0.01, 0, 180)
        self._refresh_view_plot()

    def calcDist(self):
        """Calculate camera center/distance from sampled render points."""
        if not self.render_points:
            return
        xs = [p.x for p in self.render_points]
        ys = [p.y for p in self.render_points]
        zs = [p.z for p in self.render_points]
        center, self.dist = calculate_scene_geometry(xs, ys, zs)
        self.ui.graphicsView.opts["center"] = QVector3D(*center)
