"""Two-point ruler using the plot's existing projection and geometry."""

# pylint: disable=protected-access  # This controller is part of the owning plot implementation.

import math

import numpy as np
from OpenGL import GL
from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QHeaderView, QTableWidgetItem
from pyqtgraph.opengl import GLLinePlotItem, GLScatterPlotItem

from app.ui.generated.dialogs.measure import Ui_MeasureDialog
from app.ui.plot.geometry_picking import pick_grid, pick_segments, pick_triangles, plane_point, view_projection


class PlotRuler(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.action = window.ui.actionMeasure
        self.dialog = QDialog(
            window, Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint
        )
        self.ui = Ui_MeasureDialog()
        self.ui.setupUi(self.dialog)
        self.dialog.setWindowIcon(self.action.icon())
        # Reserve five font-scaled lines before showing the first short prompt.
        self.ui.statusLabel.setFixedHeight(self.ui.statusLabel.fontMetrics().lineSpacing() * 5 + 8)
        table = self.ui.coordinatesTable
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setMinimumWidth(390)
        table.setFixedHeight(table.horizontalHeader().sizeHint().height() + 3 * table.rowHeight(0) + 4)
        self.ui.inchesCheck.setChecked(window.defaultUnits == "inch")
        self.ui.inchesCheck.toggled.connect(self._units_changed)
        table.itemChanged.connect(self._coordinate_changed)
        self.ui.buttonBox.rejected.connect(self.dialog.reject)
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self.reset)
        self.dialog.finished.connect(lambda: self.action.setChecked(False))
        self.action.toggled.connect(self.toggle)
        self.line = GLLinePlotItem(width=1.2, antialias=True, color=QColor("#2389ee"))
        self.points = GLScatterPlotItem(size=7, pxMode=True, color=QColor("#2389ee"))
        for item in (self.line, self.points):
            item.setGLOptions({GL.GL_DEPTH_TEST: False, GL.GL_BLEND: True, "glDepthMask": (False,)})
            item.setDepthValue(1000)
        self.first = self.second = None
        self.fixed = False
        self.plane = None
        self._context_key = None
        self._trace_key = None
        self._trace_source = None
        self._trace_segments = np.empty((0, 2, 3))
        self._hover = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._preview)
        window.ui.graphicsView.setMouseTracking(True)
        self.sync_view()

    @property
    def active(self):
        return self.action.isChecked() and self.action.isEnabled()

    def sync_view(self):
        plane = "xz" if getattr(self.window, "latheMode", False) else self.window._milling_view_plane()
        key = (plane, bool(getattr(self.window, "latheMode", False)))
        if key != self._context_key:
            self.reset()
        self._context_key = key
        self.plane = plane
        self.action.setEnabled(plane is not None)
        if plane is None:
            self.action.setChecked(False)

    def toggle(self, enabled):
        self.reset()
        self.window.ui.graphicsView.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)
        if enabled:
            self.dialog.show()
            self.window.ui.graphicsView.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.dialog.hide()

    def reset(self):
        self._timer.stop()
        self.first = self.second = None
        self.fixed = False
        self._fill_coordinates()
        self.ui.statusLabel.setText(self.tr("Select the first geometry point."))
        self.restore_overlay()

    def restore_overlay(self):
        view = self.window.ui.graphicsView
        for item in (self.line, self.points):
            if item in view.items:
                view.removeItem(item)
        if self.first is None or not self.active:
            return
        positions = [self.first] if self.second is None else [self.first, self.second]
        self.points.setData(pos=np.asarray(positions), size=7)
        view.addItem(self.points)
        if self.second is not None:
            self.line.setData(pos=np.asarray(positions))
            view.addItem(self.line)

    def handle_event(self, event):
        kind = event.type()
        if not self.active or kind not in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove):
            return False
        if kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.reset()
            return True
        if kind == QEvent.Type.KeyPress or event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return False
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.click(event.position())
            return True
        if kind == QEvent.Type.MouseMove and not event.buttons():
            self._hover = event.position()
            if not self._timer.isActive():
                self._timer.start()
            return True
        return False

    def _toolpath_pick(self, position, matrix, viewport):
        item = getattr(self.window, "_toolpath_item", None)
        if item is None or item not in self.window.ui.graphicsView.items or not item.visible():
            return None
        key = (item.visible_logical_count, item.show_rapid)
        if item.source_segments is not self._trace_source or key != self._trace_key:
            self._trace_segments = np.asarray(
                [
                    (s.start, s.end)
                    for s in item.source_segments
                    if s.logical_index < item.visible_logical_count and (s.move != 0 or item.show_rapid)
                ]
            ).reshape(-1, 2, 3)
            self._trace_key = key
            self._trace_source = item.source_segments
        return pick_segments(position, self._trace_segments, matrix, viewport)

    def pick(self, position):
        matrix, viewport = view_projection(self.window.ui.graphicsView)
        position = (position.x(), position.y())
        trace = self._toolpath_pick(position, matrix, viewport)
        if trace is not None:
            return trace.point
        edges, facets = [], []
        for entry in getattr(self.window, "_stl_entries", ()):
            overlay = entry.section_overlay or entry.overlay
            if overlay.item not in self.window.ui.graphicsView.items or not overlay.item.visible():
                continue
            triangles, segments = overlay.pick_geometry()
            edge = pick_segments(position, segments, matrix, viewport)
            if edge is not None:
                edges.append(edge)
            facet = pick_triangles(position, triangles, matrix, viewport)
            if facet is not None:
                facets.append(facet)
        if edges:
            return min(edges, key=lambda hit: (hit.pixels, hit.depth)).point
        if facets:
            return min(facets, key=lambda hit: hit.depth).point
        return self._grid_pick(position, matrix, viewport)

    def _grid_pick(self, position, matrix, viewport):
        attribute = "_lathe_grid_item" if self.window.latheMode else "_milling_grid_item"
        grid = getattr(self.window, attribute, None)
        if (
            not self.window.plotGrid
            or grid is None
            or grid not in self.window.ui.graphicsView.items
            or not grid.visible()
        ):
            return None
        hit = pick_grid(position, grid, matrix, viewport)
        return hit.point if hit is not None else None

    def click(self, position):
        self._timer.stop()
        point = self.pick(position)
        if point is None:
            self.ui.statusLabel.setText(self.tr("No geometry at this point."))
            return
        if self.first is None or self.fixed:
            self.first, self.second, self.fixed = point, None, False
            self.ui.statusLabel.setText(self.tr("Select the second geometry point."))
        else:
            self.second, self.fixed = point, True
        self.update_result()

    def _preview(self):
        if not self.active or self.first is None or self.fixed or self._hover is None:
            return
        point = self.pick(self._hover)
        if point is None:
            matrix, viewport = view_projection(self.window.ui.graphicsView)
            point = plane_point((self._hover.x(), self._hover.y()), matrix, viewport, self.plane, self.first)
        self.second = point
        self.update_result()

    def update_result(self):
        self._fill_coordinates()
        if self.first is None or self.second is None:
            self.restore_overlay()
            return
        units = "in" if self.ui.inchesCheck.isChecked() else "mm"
        scale = self._unit_scale()
        axes = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}[self.plane]
        delta = [b - a for a, b in zip(self.first, self.second)]
        distance = math.hypot(*(delta[i] for i in axes)) / scale
        text = self.tr("Distance in plane: {0} {1}").format(f"{distance:.3f}", units)
        text += " | " + self.tr("3D distance: {0} {1}").format(f"{math.hypot(*delta) / scale:.3f}", units)
        if self.fixed:
            text += "\n" + self.tr("Measurement fixed. Click to start another.")
        self.ui.statusLabel.setText(text)
        self.restore_overlay()

    def _unit_scale(self):
        return 25.4 if self.ui.inchesCheck.isChecked() else 1.0

    def _fill_coordinates(self):
        table = self.ui.coordinatesTable
        blocked = table.blockSignals(True)
        scale = self._unit_scale()
        lathe = self.window.latheMode
        table.setHorizontalHeaderLabels(["X (D)" if lathe else "X", "Y", "Z"])
        for col in range(3):
            factor = (2.0 if lathe and col == 0 else 1.0) / scale
            values = ["", "", ""]
            if self.first is not None:
                values[0] = f"{self.first[col] * factor:.3f}"
            if self.second is not None:
                values[1] = f"{self.second[col] * factor:.3f}"
                if self.first is not None:
                    values[2] = f"{(self.second[col] - self.first[col]) * factor:.3f}"
            for row, text in enumerate(values):
                item = QTableWidgetItem(text)
                if row == 2:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, col, item)
        table.blockSignals(blocked)

    def _units_changed(self):
        self._timer.stop()
        self.update_result()

    def _coordinate_changed(self, item):
        if item.row() not in (0, 1):
            return
        try:
            value = float(item.text().strip().replace(",", "."))
            diameter = self.window.latheMode and item.column() == 0
            value = value * self._unit_scale() / (2.0 if diameter else 1.0)
            if not math.isfinite(value):
                raise ValueError
        except ValueError:
            self._fill_coordinates()
            self.ui.statusLabel.setText(self.tr("Enter a finite numeric coordinate."))
            return
        self._timer.stop()
        point = list((self.first if item.row() == 0 else self.second) or (0.0, 0.0, 0.0))
        point[item.column()] = value
        if item.row() == 0:
            self.first = tuple(point)
        else:
            self.first = self.first or (0.0, 0.0, 0.0)
            self.second = tuple(point)
        self.fixed = self.second is not None
        self.ui.statusLabel.setText(self.tr("Select the second geometry point."))
        self.update_result()
