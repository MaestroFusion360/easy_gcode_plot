"""Compact controls for imported STL scene objects."""

from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ui.generated.panels.stl_objects_panel import Ui_StlObjectsPanelForm


def _spin(*, minimum=-1_000_000.0, maximum=1_000_000.0, value=0.0, decimals=4, step=1.0):
    widget = QDoubleSpinBox()
    widget.setRange(minimum, maximum)
    widget.setDecimals(decimals)
    widget.setSingleStep(step)
    widget.setValue(value)
    widget.setKeyboardTracking(False)
    return widget


def _axis_row(layout, row, widgets):
    for column, (axis, widget) in enumerate(zip("XYZ", widgets)):
        box = QWidget()
        box_layout = QHBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(3)
        box_layout.addWidget(QLabel(axis))
        box_layout.addWidget(widget)
        layout.addWidget(box, row, column)


class StlObjectsPanel(QDockWidget):
    selectionChanged = pyqtSignal(int)
    deleteRequested = pyqtSignal()
    statisticsRequested = pyqtSignal()
    pivotRequested = pyqtSignal(str, object)
    moveRequested = pyqtSignal(object)
    rotateRequested = pyqtSignal(str, float)
    mirrorRequested = pyqtSignal(str)
    scaleRequested = pyqtSignal(float)
    circularArrayRequested = pyqtSignal(int, float, str, object, bool)
    rectangularArrayRequested = pyqtSignal(int, int, int, float, float, float)
    sectionRequested = pyqtSignal(str, float, bool)
    clearSectionRequested = pyqtSignal()
    undoRequested = pyqtSignal()
    redoRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(QCoreApplication.translate("StlObjectsPanelForm", "STL Objects"), parent)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setObjectName("stlObjectsDock")
        self._section_bounds = None
        self._measurements = None
        self._build_ui()
        self._connect_signals()
        self._set_object_controls_enabled(False)

    def _build_ui(self):
        content = QWidget()
        self.ui = Ui_StlObjectsPanelForm()
        self.ui.setupUi(content)
        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(content, 1)
        wrapper = QWidget()
        wrapper.setLayout(outer)
        wrapper.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.objectList = self.ui.objectList
        self.objectList.setObjectName("stlObjectList")
        self.operationCombo = self.ui.operationCombo
        self.operationStack = self.ui.operationStack
        self.operationStack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        specs = (
            ("undoButton", "undo.png"),
            ("redoButton", "redo.png"),
            ("statisticsButton", "stat.png"),
            ("deleteButton", "remove.png"),
        )
        self.actionButtons = []
        for name, icon in specs:
            button = getattr(self.ui, name)
            button.setIcon(QIcon(f":/resource/icons/{icon}"))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setIconSize(QSize(18, 18))
            button.setMaximumHeight(30)
            button.setAutoRaise(False)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            setattr(self, name, button)
            self.actionButtons.append(button)
        self.operationCombo.setObjectName("stlOperationCombo")
        groups = (
            self._pivot_group(),
            self._position_group(),
            self._transform_group(),
            self._circular_group(),
            self._rectangular_group(),
            self._section_group(),
        )
        for index, group in enumerate(groups):
            self.operationCombo.addItem(group.title())
            page = self.operationStack.widget(index)
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(group, 0, Qt.AlignmentFlag.AlignTop)
        self.setWidget(wrapper)
        wrapper.setMinimumWidth(440)

    def _pivot_group(self):
        group = QGroupBox(QCoreApplication.translate("MainWindow", "Base point"))
        layout = QVBoxLayout(group)
        self.pivotMode = QComboBox()
        for label, data in (
            (QCoreApplication.translate("MainWindow", "Center"), "center"),
            (QCoreApplication.translate("MainWindow", "Bounding-box corner"), "min"),
            (QCoreApplication.translate("MainWindow", "Origin"), "origin"),
            (QCoreApplication.translate("MainWindow", "Custom"), "custom"),
        ):
            self.pivotMode.addItem(label, data)
        layout.addWidget(self.pivotMode)
        self.pivotDescription = QLabel()
        self.pivotDescription.setWordWrap(True)
        layout.addWidget(self.pivotDescription)
        grid = QGridLayout()
        self.pivotX, self.pivotY, self.pivotZ = (_spin() for _ in range(3))
        _axis_row(grid, 0, (self.pivotX, self.pivotY, self.pivotZ))
        layout.addLayout(grid)
        self.pivotApplyButton = QPushButton(QCoreApplication.translate("MainWindow", "Set base point"))
        self._set_action_icon(self.pivotApplyButton, "apply.png")
        layout.addWidget(self.pivotApplyButton)
        return group

    def _position_group(self):
        group = QGroupBox(QCoreApplication.translate("MainWindow", "Position"))
        layout = QVBoxLayout(group)
        grid = QGridLayout()
        self.positionX, self.positionY, self.positionZ = (_spin() for _ in range(3))
        _axis_row(grid, 0, (self.positionX, self.positionY, self.positionZ))
        layout.addLayout(grid)
        self.moveButton = QPushButton(QCoreApplication.translate("MainWindow", "Move here"))
        self._set_action_icon(self.moveButton, "apply.png")
        layout.addWidget(self.moveButton)
        return group

    def _transform_group(self):
        group = QGroupBox(QCoreApplication.translate("MainWindow", "Transform"))
        layout = QFormLayout(group)
        self.rotateAxis = QComboBox()
        self.rotateAxis.addItems(tuple("XYZ"))
        self.rotateAngle = _spin(minimum=-360_000, maximum=360_000, decimals=3)
        self.rotateButton = QPushButton(QCoreApplication.translate("MainWindow", "Rotate"))
        self._set_action_icon(self.rotateButton, "rotate.png")
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.rotateAxis)
        row_layout.addWidget(self.rotateAngle)
        row_layout.addWidget(self.rotateButton)
        layout.addRow(QCoreApplication.translate("MainWindow", "Rotation"), row)

        self.mirrorPlane = QComboBox()
        self.mirrorPlane.addItems(tuple("XYZ"))
        self.mirrorButton = QPushButton(QCoreApplication.translate("MainWindow", "Mirror"))
        self._set_action_icon(self.mirrorButton, "mirror.png")
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.mirrorPlane)
        row_layout.addWidget(self.mirrorButton)
        layout.addRow(QCoreApplication.translate("MainWindow", "Plane normal"), row)

        self.scaleFactor = _spin(minimum=1e-6, maximum=1_000_000, value=1.0, decimals=6, step=0.1)
        self.scaleButton = QPushButton(QCoreApplication.translate("MainWindow", "Scale"))
        self._set_action_icon(self.scaleButton, "scale.png")
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.scaleFactor)
        row_layout.addWidget(self.scaleButton)
        layout.addRow(QCoreApplication.translate("MainWindow", "Factor"), row)
        return group

    def _circular_group(self):
        group = QGroupBox(QCoreApplication.translate("MainWindow", "Circular array"))
        layout = QFormLayout(group)
        self.circularCount = QSpinBox()
        self.circularCount.setRange(1, 10_000)
        self.circularCount.setValue(4)
        self.circularAngle = _spin(minimum=-360_000, maximum=360_000, value=360, decimals=3)
        self.circularAxis = QComboBox()
        self.circularAxis.addItems(tuple("XYZ"))
        layout.addRow(QCoreApplication.translate("MainWindow", "Copies"), self.circularCount)
        layout.addRow(QCoreApplication.translate("MainWindow", "Total angle"), self.circularAngle)
        layout.addRow(QCoreApplication.translate("MainWindow", "Axis"), self.circularAxis)
        self.circularX, self.circularY, self.circularZ = (_spin() for _ in range(3))
        center = QWidget()
        center_grid = QGridLayout(center)
        center_grid.setContentsMargins(0, 0, 0, 0)
        _axis_row(center_grid, 0, (self.circularX, self.circularY, self.circularZ))
        layout.addRow(QCoreApplication.translate("MainWindow", "Center"), center)
        self.rotateCopies = QCheckBox(QCoreApplication.translate("MainWindow", "Rotate copies"))
        self.rotateCopies.setChecked(True)
        layout.addRow(self.rotateCopies)
        self.circularButton = QPushButton(QCoreApplication.translate("MainWindow", "Create"))
        self._set_action_icon(self.circularButton, "create.png")
        layout.addRow(self.circularButton)
        return group

    def _rectangular_group(self):
        group = QGroupBox(QCoreApplication.translate("MainWindow", "Rectangular array"))
        layout = QGridLayout(group)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(4)
        for column, label in enumerate(
            (
                QCoreApplication.translate("MainWindow", "Axis"),
                QCoreApplication.translate("MainWindow", "Count"),
                QCoreApplication.translate("MainWindow", "Step"),
            )
        ):
            layout.addWidget(QLabel(label), 0, column)
        self.rectCounts, self.rectSteps = [], []
        for row, axis in enumerate("XYZ", 1):
            count = QSpinBox()
            count.setRange(1, 10_000)
            count.setValue(1)
            step = _spin()
            self.rectCounts.append(count)
            self.rectSteps.append(step)
            layout.addWidget(QLabel(axis), row, 0)
            layout.addWidget(count, row, 1)
            layout.addWidget(step, row, 2)
        self.rectangularButton = QPushButton(QCoreApplication.translate("MainWindow", "Create"))
        self._set_action_icon(self.rectangularButton, "create.png")
        layout.addWidget(self.rectangularButton, 4, 0, 1, 3)
        return group

    def _section_group(self):
        group = QGroupBox(QCoreApplication.translate("MainWindow", "Section"))
        layout = QFormLayout(group)
        self.sectionAxis = QComboBox()
        self.sectionAxis.addItems(tuple("XYZ"))
        self.sectionOffset = _spin()
        self.sectionKeepSide = QComboBox()
        self.sectionKeepSide.addItem(QCoreApplication.translate("MainWindow", "Positive side"), True)
        self.sectionKeepSide.addItem(QCoreApplication.translate("MainWindow", "Negative side"), False)
        layout.addRow(QCoreApplication.translate("MainWindow", "Axis"), self.sectionAxis)
        layout.addRow(QCoreApplication.translate("MainWindow", "Coordinate"), self.sectionOffset)
        layout.addRow(QCoreApplication.translate("MainWindow", "Keep"), self.sectionKeepSide)
        self.sectionButton = QPushButton(QCoreApplication.translate("MainWindow", "Apply"))
        self._set_action_icon(self.sectionButton, "apply.png")
        self.clearSectionButton = QPushButton(QCoreApplication.translate("MainWindow", "Clear"))
        self._set_action_icon(self.clearSectionButton, "remove.png")
        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addWidget(self.sectionButton)
        actions_layout.addWidget(self.clearSectionButton)
        layout.addRow(actions)
        return group

    @staticmethod
    def _set_action_icon(button, filename):
        button.setIcon(QIcon(f":/resource/icons/{filename}"))
        button.setIconSize(QSize(18, 18))

    def _connect_signals(self):
        self.objectList.currentRowChanged.connect(self._selection_changed)
        self.operationCombo.currentIndexChanged.connect(self.operationStack.setCurrentIndex)
        self.undoButton.clicked.connect(lambda _checked=False: self.undoRequested.emit())
        self.redoButton.clicked.connect(lambda _checked=False: self.redoRequested.emit())
        self.statisticsButton.clicked.connect(lambda _checked=False: self.statisticsRequested.emit())
        self.deleteButton.clicked.connect(lambda _checked=False: self.deleteRequested.emit())
        self.pivotMode.currentIndexChanged.connect(self._pivot_mode_changed)
        self.pivotApplyButton.clicked.connect(self._emit_pivot)
        self.moveButton.clicked.connect(
            lambda: self.moveRequested.emit(tuple(w.value() for w in (self.positionX, self.positionY, self.positionZ)))
        )
        self.rotateButton.clicked.connect(
            lambda: self.rotateRequested.emit(self.rotateAxis.currentText(), self.rotateAngle.value())
        )
        self.mirrorButton.clicked.connect(lambda: self.mirrorRequested.emit(self.mirrorPlane.currentText()))
        self.scaleButton.clicked.connect(lambda: self.scaleRequested.emit(self.scaleFactor.value()))
        self.circularButton.clicked.connect(self._emit_circular_array)
        self.rectangularButton.clicked.connect(self._emit_rectangular_array)
        self.sectionButton.clicked.connect(
            lambda: self.sectionRequested.emit(
                self.sectionAxis.currentText(), self.sectionOffset.value(), bool(self.sectionKeepSide.currentData())
            )
        )
        self.clearSectionButton.clicked.connect(lambda: self.clearSectionRequested.emit())
        self.sectionAxis.currentTextChanged.connect(self._center_section_offset)

    def _selection_changed(self, row):
        self._set_object_controls_enabled(row >= 0)
        self.selectionChanged.emit(row)

    def _set_object_controls_enabled(self, enabled):
        self.deleteButton.setEnabled(enabled)
        self.statisticsButton.setEnabled(enabled)
        for index in range(self.operationStack.count()):
            self.operationStack.widget(index).setEnabled(enabled)

    def _sync_custom_pivot_enabled(self):
        enabled = self.pivotMode.currentData() == "custom"
        for widget in (self.pivotX, self.pivotY, self.pivotZ):
            widget.setReadOnly(not enabled)
        self.pivotApplyButton.setVisible(enabled)
        descriptions = {
            "center": QCoreApplication.translate(
                "MainWindow", "Center of the source mesh bounding box, in model coordinates."
            ),
            "min": QCoreApplication.translate(
                "MainWindow", "Minimum X, Y and Z. Shift+Click any highlighted bounding-box corner to use it."
            ),
            "origin": QCoreApplication.translate("MainWindow", "Model coordinate origin (0, 0, 0)."),
            "custom": QCoreApplication.translate("MainWindow", "Enter a point in model coordinates, then apply it."),
        }
        self.pivotDescription.setText(descriptions.get(self.pivotMode.currentData(), ""))

    def _pivot_mode_changed(self, _index):
        self._sync_custom_pivot_enabled()
        mode = self.pivotMode.currentData()
        if mode in {"center", "min", "origin"} and self.objectList.currentRow() >= 0:
            self.pivotRequested.emit(mode, None)

    def _emit_pivot(self):
        point = tuple(w.value() for w in (self.pivotX, self.pivotY, self.pivotZ))
        self.pivotRequested.emit(
            self.pivotMode.currentData(), point if self.pivotMode.currentData() == "custom" else None
        )

    def _emit_circular_array(self):
        center = tuple(w.value() for w in (self.circularX, self.circularY, self.circularZ))
        self.circularArrayRequested.emit(
            self.circularCount.value(),
            self.circularAngle.value(),
            self.circularAxis.currentText(),
            center,
            self.rotateCopies.isChecked(),
        )

    def _emit_rectangular_array(self):
        counts = tuple(widget.value() for widget in self.rectCounts)
        steps = tuple(widget.value() for widget in self.rectSteps)
        self.rectangularArrayRequested.emit(*counts, *steps)

    def set_objects(self, names, current_row=-1):
        self.objectList.blockSignals(True)
        try:
            self.objectList.clear()
            self.objectList.addItems(list(names))
            if self.objectList.count():
                self.objectList.setCurrentRow(min(max(int(current_row), 0), self.objectList.count() - 1))
            else:
                self.objectList.setCurrentRow(-1)
        finally:
            self.objectList.blockSignals(False)
        self._set_object_controls_enabled(self.objectList.currentRow() >= 0)
        self._sync_custom_pivot_enabled()

    def set_object_state(self, *, pivot_mode, pivot, world_pivot):
        index = self.pivotMode.findData(pivot_mode)
        if index >= 0:
            self.pivotMode.blockSignals(True)
            self.pivotMode.setCurrentIndex(index)
            self.pivotMode.blockSignals(False)
        for widget, value in zip((self.pivotX, self.pivotY, self.pivotZ), pivot):
            widget.setValue(float(value))
        for widget, value in zip((self.positionX, self.positionY, self.positionZ), world_pivot):
            widget.setValue(float(value))
        self._sync_custom_pivot_enabled()

    def set_history_available(self, *, undo, redo):
        self.undoButton.setEnabled(undo)
        self.redoButton.setEnabled(redo)

    def set_mesh_bounds(self, measurement):
        self._section_bounds = None if measurement is None else measurement.bounds
        self._center_section_offset()

    def set_measurements(self, measurement):
        """Compatibility method for the main window's existing panel contract."""
        self._measurements = measurement
        self.set_mesh_bounds(measurement)

    @staticmethod
    def format_measurements(measurement, *, inches=False):
        scale = 25.4 if inches else 1.0
        unit = "in" if inches else "mm"
        area_label = QCoreApplication.translate("StlStatistics", "Surface area")
        volume_label = QCoreApplication.translate("StlStatistics", "Volume")
        center_label = QCoreApplication.translate("StlStatistics", "Center of mass")
        bounds_label = QCoreApplication.translate("StlStatistics", "Bounding box")
        volume = (
            f"{measurement.volume / scale**3:.3f}"
            if measurement.volume is not None
            else QCoreApplication.translate("StlStatistics", "undefined (open mesh)")
        )
        center = (
            ", ".join(f"{value / scale:.3f}" for value in measurement.center_of_mass)
            if measurement.center_of_mass is not None
            else QCoreApplication.translate("StlStatistics", "undefined (open mesh)")
        )
        bounds = "\n".join(
            f"{axis}min = {low / scale:.3f} {unit}; "
            f"{axis}max = {high / scale:.3f} {unit}; "
            f"Length = {(high - low) / scale:.3f} {unit}"
            for axis, (low, high) in zip("XYZ", measurement.bounds)
        )
        return (
            f"{area_label}: {measurement.area / scale**2:.3f} {unit}\u00b2\n"
            f"{volume_label}: {volume} {unit}\u00b3\n"
            f"{center_label}: {center} {unit}\n"
            f"{bounds_label}:\n{bounds}"
        )

    def apply_theme(self, _theme_name):
        self.update()

    def minimumSizeHint(self):  # noqa: N802 - Qt API
        """Do not let dense controls impose a fixed minimum dock width."""
        size = super().minimumSizeHint()
        return QSize(0, size.height())

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Mid), 1))
        painter.drawLine(0, 0, 0, self.height() - 1)
        painter.end()

    def _center_section_offset(self):
        if self._section_bounds is not None:
            axis = "XYZ".index(self.sectionAxis.currentText())
            self.sectionOffset.setValue(sum(self._section_bounds[axis]) / 2)
