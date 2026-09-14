"""Turning and milling tool-library dialogs and editors."""

import copy
import csv
import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.tools.definitions import (
    AUTO_TIP_ORIENTATIONS,
    AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION,
    DEFAULT_AUTO_TIP_ORIENTATION,
    DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION,
    MILLING_TOOL_LABELS,
    TURNING_APPLICATIONS,
    TURNING_INSERT_TYPES,
    TURNING_TOOL_LABELS,
    tool_applications,
)
from app.tools.milling_geometry import (
    default_cutting_height,
    default_drill_tip_angle,
    default_shank_diameter,
    default_tip_diameter,
)
from app.ui.generated.milling_tools import Ui_MillingToolsDlg
from app.ui.generated.turning_tools import Ui_TurningToolsDlg
from app.ui.tool_library_preview import ToolLibraryPreviewPane


def _export_tool_file(path: str, kind: str, key: str, spec: dict) -> None:
    """Export one normalized tool record as JSON or one-row CSV."""
    target = Path(path)
    record = {"library": kind, "tool": key, **spec}
    if target.suffix.lower() == ".csv":
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(record))
            writer.writeheader()
            writer.writerow(record)
        return
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


_TURNING_INSERT_ORDER = ("diamond_80", "diamond_35", "square", "round", "triangle")


def _turning_category(tool_type: str) -> str:
    if tool_type in TURNING_INSERT_TYPES:
        return "insert"
    if tool_type == "groove":
        return "groove"
    if tool_type == "thread":
        return "thread"
    if tool_type == "drill":
        return "drill"
    if tool_type == "tap":
        return "tap"
    return "insert"


def _directions_for_tool(spec: dict[str, object]) -> set[str]:
    applications = set(tool_applications(spec))
    if applications:
        return applications
    tool_type = str(spec.get("type", ""))
    orientation = spec.get("tipOrientation")
    by_direction = AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION.get(tool_type, {})
    matching = {direction for direction, orientations in by_direction.items() if orientation in orientations}
    if matching:
        return matching
    if orientation in (1, 2):
        return {"id"}
    if orientation in (6, 7):
        return {"face"}
    return {"od"}


class _TurningToolEditor(QDialog):
    """Category-oriented editor backed by the existing turning-tool identifiers."""

    def __init__(self, parent=None, tool_code=None, spec=None):
        super().__init__(parent)
        spec = spec or {}
        self._updating = True
        self._initial_type = str(spec.get("type", "diamond_80"))
        self._initial_tip_orientation = int(spec["tipOrientation"]) if "tipOrientation" in spec else None
        self.setWindowTitle("Edit Tool" if tool_code else "Add Tool")
        self.setModal(True)
        self.setMinimumWidth(620)

        form = QFormLayout()
        self.toolCode = QLineEdit(tool_code or "T0101", self)
        form.addRow("T code", self.toolCode)

        category_layout = QHBoxLayout()
        self.categoryGroup = QButtonGroup(self)
        self.categoryButtons = {}
        for key, label in (
            ("insert", "Cutting tool"),
            ("groove", "Groove"),
            ("thread", "Thread"),
            ("drill", "Drill"),
            ("tap", "Tap"),
        ):
            button = QRadioButton(label, self)
            self.categoryGroup.addButton(button)
            self.categoryButtons[key] = button
            category_layout.addWidget(button)
        form.addRow("Category", category_layout)

        direction_layout = QHBoxLayout()
        self.directionChecks = {}
        for key, label in (("od", "OD"), ("id", "ID"), ("face", "Face")):
            checkbox = QCheckBox(label, self)
            self.directionChecks[key] = checkbox
            direction_layout.addWidget(checkbox)
        direction_layout.addStretch()
        form.addRow("Machining direction", direction_layout)

        self.insertType = QComboBox(self)
        self.grooveType = QComboBox(self)
        self.threadType = QComboBox(self)
        self.threadType.addItem(TURNING_TOOL_LABELS["thread"], "thread")
        self.drillType = QComboBox(self)
        self.drillType.addItem(TURNING_TOOL_LABELS["drill"], "drill")
        self.tapType = QComboBox(self)
        self.tapType.addItem(TURNING_TOOL_LABELS["tap"], "tap")
        self.toolType = self.insertType  # Compatibility alias for existing callers/tests.
        form.addRow("Turning tool", self.insertType)
        form.addRow("Groove type", self.grooveType)
        form.addRow("Thread type", self.threadType)
        form.addRow("Drill type", self.drillType)
        form.addRow("Tap type", self.tapType)

        self.noseRadius = QDoubleSpinBox(self)
        self.noseRadius.setDecimals(3)
        self.noseRadius.setRange(0.0, 999999.999)
        self.noseRadius.setValue(float(spec.get("noseRadius", 0.4)))
        self.tipOrientation = QComboBox(self)
        self.insertLength = QDoubleSpinBox(self)
        self.insertLength.setDecimals(3)
        self.insertLength.setRange(0.001, 10000.0)
        self.insertLength.setValue(float(spec.get("insertLength", self._default_insert_length(self._initial_type))))
        self.width = QDoubleSpinBox(self)
        self.width.setDecimals(3)
        self.width.setRange(0.001, 10000.0)
        self.width.setValue(float(spec.get("width", 3.0)))
        self.diameter = QDoubleSpinBox(self)
        self.diameter.setDecimals(3)
        self.diameter.setRange(0.001, 10000.0)
        self.diameter.setValue(float(spec.get("diameter", 10.0)))
        self.length = QDoubleSpinBox(self)
        self.length.setDecimals(3)
        self.length.setRange(0.001, 100000.0)
        self.length.setValue(float(spec.get("length", 50.0)))
        self.tipAngle = QDoubleSpinBox(self)
        self.tipAngle.setDecimals(1)
        self.tipAngle.setRange(1.0, 179.0)
        self.tipAngle.setValue(float(spec.get("tipAngle", 118.0)))
        self.threadAngle = QDoubleSpinBox(self)
        self.threadAngle.setDecimals(1)
        self.threadAngle.setRange(1.0, 179.0)
        self.threadAngle.setValue(float(spec.get("threadAngle", 60.0)))
        self.threadTipWidth = QDoubleSpinBox(self)
        self.threadTipWidth.setDecimals(3)
        self.threadTipWidth.setRange(0.001, 10000.0)
        self.threadTipWidth.setValue(float(spec.get("threadTipWidth", 0.8)))
        self.threadCornerRadius = QDoubleSpinBox(self)
        self.threadCornerRadius.setDecimals(3)
        self.threadCornerRadius.setRange(0.0, 10000.0)
        self.threadCornerRadius.setValue(float(spec.get("threadCornerRadius", 0.1)))
        self.threadHelp = QLabel(self)
        self.threadHelp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.threadHelp.setPixmap(QPixmap(":/resource/icons/thread.png"))
        self.description = QLineEdit(str(spec.get("description", "")), self)

        form.addRow("Nose radius, mm", self.noseRadius)
        form.addRow("Tip orientation", self.tipOrientation)
        form.addRow("Length/Diameter, mm", self.insertLength)
        form.addRow("Groove width, mm", self.width)
        form.addRow("Tool diameter, mm", self.diameter)
        form.addRow("Tool length, mm", self.length)
        form.addRow("Tip angle, deg", self.tipAngle)
        form.addRow("Thread geometry", self.threadHelp)
        form.addRow("E, deg", self.threadAngle)
        form.addRow("EX, mm", self.threadTipWidth)
        form.addRow("RC, mm", self.threadCornerRadius)
        form.addRow("Description", self.description)
        self._form = form

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttonBox.accepted.connect(self.validateAndAccept)
        self.buttonBox.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttonBox)

        category = _turning_category(self._initial_type)
        self.categoryButtons[category].setChecked(True)
        initial_spec = {**spec, "type": self._initial_type}
        for direction in _directions_for_tool(initial_spec):
            self.directionChecks[direction].setChecked(True)
        self._refresh_type_choices(self._initial_type)
        self._last_insert_type = self.insertType.currentData()
        self._connect_signals()
        self._updating = False
        self.updateTurningFields()
        self.toolCode.selectAll()
        self.toolCode.setFocus()

    @staticmethod
    def _default_insert_length(tool_type) -> float:
        return 16.0 if tool_type == "diamond_35" else 12.0

    def _connect_signals(self):
        for button in self.categoryButtons.values():
            button.toggled.connect(self.updateTurningFields)
        for checkbox in self.directionChecks.values():
            checkbox.toggled.connect(self._direction_changed)
        self.insertType.currentIndexChanged.connect(self._insert_type_changed)
        self.grooveType.currentIndexChanged.connect(self.updateTurningFields)

    def _insert_type_changed(self, *_args):
        tool_type = self.insertType.currentData()
        previous = getattr(self, "_last_insert_type", None)
        if tool_type is not None and (
            previous is None or abs(self.insertLength.value() - self._default_insert_length(previous)) < 1e-9
        ):
            self.insertLength.setValue(self._default_insert_length(tool_type))
        self._last_insert_type = tool_type
        self.updateTurningFields()

    def category(self) -> str:
        return next((key for key, button in self.categoryButtons.items() if button.isChecked()), "insert")

    def selectedDirections(self) -> set[str]:
        return {key for key, checkbox in self.directionChecks.items() if checkbox.isChecked()}

    def currentToolType(self):
        combo = {
            "insert": self.insertType,
            "groove": self.grooveType,
            "thread": self.threadType,
            "drill": self.drillType,
            "tap": self.tapType,
        }.get(self.category())
        return combo.currentData() if combo is not None else None

    def serializedToolType(self):
        """Return the canonical geometry type; applicability is serialized separately."""
        return self.currentToolType()

    def _direction_changed(self, *_args):
        if self._updating:
            return
        if not self.selectedDirections():
            self._updating = True
            self.directionChecks["od"].setChecked(True)
            self._updating = False
        self._refresh_type_choices(self.currentToolType())
        self.updateTurningFields()

    def _refresh_type_choices(self, requested_type=None):
        directions = self.selectedDirections() or {"od"}
        insert_directions = directions & {"od", "id"} or {"od"}
        requested_type = str(requested_type or "")
        insert_types = [
            tool_type
            for tool_type in _TURNING_INSERT_ORDER
            if set(AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION[tool_type]) & insert_directions
        ]
        groove_types = ["groove"] if directions else []
        self._populate_combo(self.insertType, insert_types, requested_type)
        self._populate_combo(self.grooveType, groove_types, requested_type)

    @staticmethod
    def _populate_combo(combo, tool_types, requested_type):
        combo.blockSignals(True)
        combo.clear()
        for tool_type in tool_types:
            combo.addItem(TURNING_TOOL_LABELS[tool_type], tool_type)
        selected = combo.findData(requested_type)
        combo.setCurrentIndex(selected if selected >= 0 else (0 if combo.count() else -1))
        combo.blockSignals(False)

    def updateTurningFields(self, *_args):
        if self._updating:
            return
        category = self.category()
        directional = category in {"insert", "groove", "thread"}
        for checkbox in self.directionChecks.values():
            checkbox.setEnabled(directional)
        self._refresh_type_choices(self.currentToolType())
        for name, combo in (
            ("insert", self.insertType),
            ("groove", self.grooveType),
            ("thread", self.threadType),
            ("drill", self.drillType),
            ("tap", self.tapType),
        ):
            self._set_row_visible(combo, category == name)
        tool_type = self.currentToolType()
        insert = category == "insert" and tool_type in TURNING_INSERT_TYPES
        groove = category == "groove" and tool_type == "groove"
        thread = category == "thread" and tool_type == "thread"
        axial = category in {"drill", "tap"}
        self._set_row_visible(self.noseRadius, insert or groove)
        self._set_row_visible(self.tipOrientation, insert or groove or thread)
        self._set_row_visible(self.insertLength, insert or thread)
        self._set_row_visible(self.width, groove)
        self._set_row_visible(self.diameter, axial)
        self._set_row_visible(self.length, axial)
        self._set_row_visible(self.tipAngle, axial)
        self._set_row_visible(self.threadHelp, thread)
        self._set_row_visible(self.threadAngle, thread)
        self._set_row_visible(self.threadTipWidth, thread)
        self._set_row_visible(self.threadCornerRadius, thread)
        self._sync_tip_orientation_choices(tool_type)

    def _set_row_visible(self, widget, visible):
        widget.setVisible(visible)
        label = self._form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _sync_tip_orientation_choices(self, tool_type):
        by_direction = AUTO_TIP_ORIENTATIONS_BY_TOOL_DIRECTION.get(tool_type)
        if by_direction is not None:
            directions = self.selectedDirections() or {"od"}
            if tool_type != "groove":
                directions = directions & {"od", "id"} or {"od"}
            choices = tuple(
                sorted({orientation for direction in directions for orientation in by_direction.get(direction, ())})
            )
            if not choices:
                choices = AUTO_TIP_ORIENTATIONS[tool_type]
            preferred = DEFAULT_AUTO_TIP_ORIENTATION[tool_type]
            if len(directions) == 1:
                direction = next(iter(directions))
                preferred = DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION[tool_type].get(direction, preferred)
            default = preferred if preferred in choices else choices[0]
        else:
            choices, default = (), 1
        current = self.tipOrientation.currentData()
        requested = self._initial_tip_orientation if self._initial_tip_orientation is not None else current
        orientation = int(requested) if requested is not None and int(requested) in choices else default
        self.tipOrientation.blockSignals(True)
        self.tipOrientation.clear()
        for value in choices:
            self.tipOrientation.addItem(QIcon(f":/resource/icons/orientation_box/P{value}.png"), f"P{value}", value)
        self.tipOrientation.setCurrentIndex(self.tipOrientation.findData(orientation))
        self.tipOrientation.blockSignals(False)
        self._initial_tip_orientation = None

    def validateAndAccept(self):
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        if not digits.isdigit() or not 1 <= len(digits) <= 4:
            QMessageBox.warning(self, "Turning Tools", "T code must contain 1 to 4 digits.")
            return
        if self.currentToolType() is None:
            QMessageBox.warning(self, "Turning Tools", "Select an available tool type.")
            return
        self.accept()

    def value(self):
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        key = f"T{int(digits):04d}"
        tool_type = self.serializedToolType()
        spec = {"type": tool_type}
        description = " ".join(self.description.text().split())
        if description:
            spec["description"] = description
        if tool_type in TURNING_INSERT_TYPES:
            selected = self.selectedDirections() & {"od", "id"}
            spec["applications"] = [item for item in TURNING_APPLICATIONS if item in selected]
            spec.update(
                noseRadius=self.noseRadius.value(),
                tipOrientation=int(self.tipOrientation.currentData()),
                insertLength=self.insertLength.value(),
            )
        elif tool_type == "groove":
            selected = self.selectedDirections()
            spec["applications"] = [item for item in TURNING_APPLICATIONS if item in selected]
            spec.update(
                width=self.width.value(),
                noseRadius=self.noseRadius.value(),
                tipOrientation=int(self.tipOrientation.currentData()),
            )
        elif tool_type == "thread":
            selected = self.selectedDirections() & {"od", "id"}
            spec["applications"] = [item for item in TURNING_APPLICATIONS if item in selected]
            spec.update(
                insertLength=self.insertLength.value(),
                threadAngle=self.threadAngle.value(),
                threadTipWidth=self.threadTipWidth.value(),
                threadCornerRadius=self.threadCornerRadius.value(),
                tipOrientation=int(self.tipOrientation.currentData()),
            )
        elif tool_type in {"drill", "tap"}:
            spec.update(diameter=self.diameter.value(), length=self.length.value(), tipAngle=self.tipAngle.value())
        return key, spec


class TurningTools(QDialog):
    """Dialog for editing turning tool-nose compensation definitions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_TurningToolsDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.ui.titleLabel.setText("Turning Tool Geometry")
        self.ui.helpLabel.setText(
            "Select a tool to preview it. Geometry drives compensation, 3D playback and Stock Removal."
        )
        self.ui.toolTable.horizontalHeaderItem(3).setText("Geometry")
        self.pendingTools = {}
        self.ui.addButton.clicked.connect(self.addTool)
        self.ui.editButton.clicked.connect(self.editTool)
        self.ui.removeButton.clicked.connect(self.removeTool)
        self.duplicateButton = self._add_action_button("Duplicate", self.duplicateTool)
        self.exportButton = self._add_action_button("Export...", self.exportTool)
        self.previewPane = ToolLibraryPreviewPane("turning", self)
        self.preview = self.previewPane.preview
        self._install_preview_splitter()
        self.ui.toolTable.itemSelectionChanged.connect(self.updatePreview)
        self.ui.toolTable.doubleClicked.connect(self.editTool)
        self.accepted.connect(self.applyValues)
        self.loadValues()

    def _install_preview_splitter(self):
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.verticalLayout.replaceWidget(self.ui.toolTable, splitter)
        self.ui.toolTable.setParent(splitter)
        splitter.addWidget(self.ui.toolTable)
        splitter.addWidget(self.previewPane)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([520, 300])
        self.previewSplitter = splitter

    def _add_action_button(self, text, callback):
        button = QPushButton(text, self)
        self.ui.toolButtonsLayout.insertWidget(self.ui.toolButtonsLayout.count() - 3, button)
        button.clicked.connect(callback)
        return button

    def showEvent(self, event):
        """Discard stale pending edits and reload the current tool table."""
        self.loadValues()
        super().showEvent(event)

    def loadValues(self):
        """Copy the current tool map into the dialog editing buffer."""
        self.pendingTools = copy.deepcopy(getattr(self.parent(), "tools", {}))
        self.refreshTable()

    def refreshTable(self, selected_key=None):
        """Rebuild the visible table from the pending tool map."""
        table = self.ui.toolTable
        table.setRowCount(0)
        selected_row = -1
        for row, key in enumerate(sorted(self.pendingTools)):
            spec = self.pendingTools[key]
            tool_type = str(spec.get("type", ""))
            is_insert = tool_type in TURNING_INSERT_TYPES
            has_orientation = is_insert or tool_type in {"groove", "thread"}
            default_orientation = DEFAULT_AUTO_TIP_ORIENTATION.get(tool_type, 1)
            orientation_value = int(spec.get("tipOrientation", default_orientation))
            orientation = f"P{orientation_value}" if has_orientation else "—"
            if tool_type in {"drill", "tap"}:
                geometry = f"D{float(spec.get('diameter', 0.0)):g}"
            elif tool_type == "thread":
                geometry = (
                    f"E{float(spec.get('threadAngle', 60.0)):g} EX{float(spec.get('threadTipWidth', 0.8)):g} "
                    f"RC{float(spec.get('threadCornerRadius', 0.1)):g} "
                    f"L{float(spec.get('insertLength', 12.0)):g}"
                )
            elif tool_type == "groove":
                geometry = f"R{float(spec.get('noseRadius', 0.0)):g} W{float(spec.get('width', 0.0)):g}"
            else:
                default_length = 16.0 if tool_type == "diamond_35" else 12.0
                geometry = (
                    f"R{float(spec.get('noseRadius', 0.0)):g} L{float(spec.get('insertLength', default_length)):g}"
                    if is_insert
                    else "—"
                )
            values = (
                orientation,
                key,
                TURNING_TOOL_LABELS.get(tool_type, tool_type),
                geometry,
                str(spec.get("description", "")),
            )
            table.insertRow(row)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0 and has_orientation:
                    item.setIcon(QIcon(f":/resource/icons/orientation_box/P{orientation_value}.png"))
                table.setItem(row, column, item)
            if key == selected_key:
                selected_row = row
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        if selected_row >= 0:
            table.selectRow(selected_row)
        elif table.rowCount():
            table.selectRow(0)
        self.updatePreview()

    def selectedTool(self):
        """Return the T code from the selected table row."""
        row = self.ui.toolTable.currentRow()
        if row < 0:
            return None
        item = self.ui.toolTable.item(row, 1)
        return item.text() if item is not None else None

    def addTool(self):
        """Open the tool editor for a new definition."""
        editor = _TurningToolEditor(self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        key, spec = editor.value()
        self.pendingTools[key] = spec
        self.refreshTable(key)

    def editTool(self, *_args):
        """Edit the currently selected tool definition."""
        key = self.selectedTool()
        if key is None:
            return
        editor = _TurningToolEditor(self, key, self.pendingTools[key])
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        new_key, spec = editor.value()
        if new_key != key:
            self.pendingTools.pop(key, None)
        self.pendingTools[new_key] = spec
        self.refreshTable(new_key)

    def removeTool(self):
        """Remove the selected pending tool definition."""
        key = self.selectedTool()
        if key is None:
            return
        self.pendingTools.pop(key, None)
        self.refreshTable()

    def updatePreview(self):
        """Preview the selected tool and clear the pane when the table is empty."""
        key = self.selectedTool()
        self.preview.set_tool(self.pendingTools.get(key) if key is not None else None)

    def duplicateTool(self):
        """Duplicate the selected definition to the first free turning T code."""
        key = self.selectedTool()
        if key is None:
            return
        free_key = next(
            (f"T{number:04d}" for number in range(1, 10000) if f"T{number:04d}" not in self.pendingTools), None
        )
        if free_key is None:
            QMessageBox.warning(self, "Turning Tools", "No free T code is available.")
            return
        self.pendingTools[free_key] = copy.deepcopy(self.pendingTools[key])
        self.refreshTable(free_key)

    def exportTool(self, path=None):
        """Export the selected turning tool to JSON or CSV."""
        key = self.selectedTool()
        if key is None:
            return
        if not isinstance(path, str):
            path, _selected = QFileDialog.getSaveFileName(
                self, "Export Turning Tool", f"{key}.json", "JSON (*.json);;CSV (*.csv)"
            )
        if path:
            _export_tool_file(path, "turning", key, self.pendingTools[key])

    def applyValues(self):
        """Commit the tool table to the main window and refresh the trace."""
        self.parent().tools = copy.deepcopy(self.pendingTools)
        self.parent().updateData()


_MILLING_TOOL_TYPES = MILLING_TOOL_LABELS


class _MillingToolEditor(QDialog):
    """Add/Edit dialog for milling tool geometry."""

    def __init__(self, parent=None, tool_code=None, spec=None):
        super().__init__(parent)
        spec = spec or {}
        self.setWindowTitle("Edit Milling Tool" if tool_code else "Add Milling Tool")
        self.setModal(True)
        self.setMinimumWidth(420)

        form = QFormLayout()
        self.toolCode = QLineEdit(tool_code or "T1", self)
        self.toolType = QComboBox(self)
        for key, label in _MILLING_TOOL_TYPES.items():
            self.toolType.addItem(label, key)
        type_index = self.toolType.findData(str(spec.get("type", "mill_flat")))
        self.toolType.setCurrentIndex(max(0, type_index))

        self.diameter = QDoubleSpinBox(self)
        self.diameter.setDecimals(3)
        self.diameter.setRange(0.0, 10000.0)
        self.diameter.setValue(float(spec.get("diameter", 10.0)))

        self.cornerRadius = QDoubleSpinBox(self)
        self.cornerRadius.setDecimals(3)
        self.cornerRadius.setRange(0.0, 10000.0)
        self.cornerRadius.setValue(float(spec.get("cornerRadius", 0.0)))

        self.length = QDoubleSpinBox(self)
        self.length.setDecimals(3)
        self.length.setRange(0.0, 10000.0)
        self.length.setValue(float(spec.get("length", 50.0)))

        tool_type = str(spec.get("type", "mill_flat"))
        diameter = self.diameter.value()
        length = self.length.value()

        self.cuttingHeight = QDoubleSpinBox(self)
        self.cuttingHeight.setDecimals(3)
        self.cuttingHeight.setRange(0.0, 10000.0)
        self.cuttingHeight.setValue(
            float(spec.get("cuttingHeight", default_cutting_height(tool_type, diameter, length)))
        )

        self.shankDiameter = QDoubleSpinBox(self)
        self.shankDiameter.setDecimals(3)
        self.shankDiameter.setRange(0.0, 10000.0)
        self.shankDiameter.setValue(float(spec.get("shankDiameter", default_shank_diameter(diameter))))

        self.tipDiameter = QDoubleSpinBox(self)
        self.tipDiameter.setDecimals(3)
        self.tipDiameter.setRange(0.0, 10000.0)
        self.tipDiameter.setValue(float(spec.get("tipDiameter", default_tip_diameter(diameter))))

        self.chamferAngle = QDoubleSpinBox(self)
        self.chamferAngle.setDecimals(1)
        self.chamferAngle.setRange(1.0, 179.0)
        self.chamferAngle.setValue(float(spec.get("chamferAngle", 90.0)))

        self.tipAngle = QDoubleSpinBox(self)
        self.tipAngle.setDecimals(1)
        self.tipAngle.setRange(1.0, 179.0)
        self.tipAngle.setValue(float(spec.get("tipAngle", default_drill_tip_angle())))

        self.description = QLineEdit(str(spec.get("description", "")), self)

        form.addRow("T code", self.toolCode)
        form.addRow("Type", self.toolType)
        form.addRow("Diameter, mm", self.diameter)
        form.addRow("Corner radius, mm", self.cornerRadius)
        form.addRow("Length, mm", self.length)
        form.addRow("Cutting height, mm", self.cuttingHeight)
        form.addRow("Shank diameter, mm", self.shankDiameter)
        form.addRow("Tip diameter, mm", self.tipDiameter)
        form.addRow("Chamfer angle, deg", self.chamferAngle)
        form.addRow("Tip angle, deg", self.tipAngle)
        form.addRow("Description", self.description)
        self._shapeRows = {
            self.cuttingHeight: form.labelForField(self.cuttingHeight),
            self.shankDiameter: form.labelForField(self.shankDiameter),
            self.tipDiameter: form.labelForField(self.tipDiameter),
            self.chamferAngle: form.labelForField(self.chamferAngle),
            self.tipAngle: form.labelForField(self.tipAngle),
        }

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttonBox.accepted.connect(self.validateAndAccept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttonBox)

        self.toolType.currentIndexChanged.connect(self.updateRadiusField)
        self.diameter.valueChanged.connect(self.updateBallRadius)
        self.updateRadiusField()
        self.toolCode.selectAll()
        self.toolCode.setFocus()

    def currentType(self):
        """Return the stable milling tool type key."""
        return str(self.toolType.currentData())

    def updateRadiusField(self, *_args):
        """Expose only geometry fields meaningful for the selected cutter type."""
        tool_type = self.currentType()
        self.cornerRadius.setEnabled(tool_type == "mill_bull")
        if tool_type == "mill_ball":
            self.cornerRadius.setValue(self.diameter.value() / 2.0)
        elif tool_type != "mill_bull":
            self.cornerRadius.setValue(0.0)

        stepped = tool_type in {"face_mill", "slot_mill"}
        chamfer = tool_type == "chamfer_mill"
        for field in (self.cuttingHeight, self.shankDiameter):
            field.setVisible(stepped)
            self._shapeRows[field].setVisible(stepped)
        for field in (self.tipDiameter, self.chamferAngle):
            field.setVisible(chamfer)
            self._shapeRows[field].setVisible(chamfer)
        axial = tool_type == "drill"
        self.tipAngle.setVisible(axial)
        self._shapeRows[self.tipAngle].setVisible(axial)

    def updateBallRadius(self, *_args):
        """Keep ball radius equal to half of tool diameter."""
        if self.currentType() == "mill_ball":
            self.cornerRadius.setValue(self.diameter.value() / 2.0)

    def validateAndAccept(self):
        """Accept only valid compact tool numbers and physical geometry."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        if not digits.isdigit() or digits.startswith("0") or not 1 <= int(digits) <= 99:
            QMessageBox.warning(self, "Milling Tools", "T code must be T1-T99 without leading zeros.")
            return
        if self.diameter.value() <= 0.0 or self.length.value() <= 0.0:
            QMessageBox.warning(self, "Milling Tools", "Diameter and length must be greater than zero.")
            return
        tool_type = self.currentType()
        if tool_type == "mill_bull" and self.cornerRadius.value() > self.diameter.value() / 2.0:
            QMessageBox.warning(self, "Milling Tools", "Bull corner radius cannot exceed half the diameter.")
            return
        if tool_type in {"face_mill", "slot_mill"}:
            if not 0.0 < self.cuttingHeight.value() <= self.length.value():
                QMessageBox.warning(self, "Milling Tools", "Cutting height must be within the total tool length.")
                return
            if not 0.0 < self.shankDiameter.value() < self.diameter.value():
                QMessageBox.warning(self, "Milling Tools", "Shank diameter must be smaller than cutter diameter.")
                return
        if tool_type == "chamfer_mill" and not 0.0 <= self.tipDiameter.value() < self.diameter.value():
            QMessageBox.warning(self, "Milling Tools", "Chamfer tip diameter must be smaller than cutter diameter.")
            return
        self.accept()

    def value(self):
        """Return compact T1-T99 tool code and milling geometry."""
        raw = self.toolCode.text().strip().upper()
        digits = raw[1:] if raw.startswith("T") else raw
        key = f"T{int(digits)}"
        tool_type = self.currentType()
        diameter = self.diameter.value()
        radius = self.cornerRadius.value()
        if tool_type == "mill_ball":
            radius = diameter / 2.0
        elif tool_type != "mill_bull":
            radius = 0.0
        spec = {
            "type": tool_type,
            "diameter": diameter,
            "cornerRadius": radius,
            "length": self.length.value(),
        }
        if tool_type in {"face_mill", "slot_mill"}:
            spec.update(
                cuttingHeight=self.cuttingHeight.value(),
                shankDiameter=self.shankDiameter.value(),
            )
        elif tool_type == "chamfer_mill":
            spec.update(
                tipDiameter=self.tipDiameter.value(),
                chamferAngle=self.chamferAngle.value(),
            )
        elif tool_type == "drill":
            spec["tipAngle"] = self.tipAngle.value()
        description = " ".join(self.description.text().split())
        if description:
            spec["description"] = description
        return key, spec


class MillingTools(QDialog):
    """Dialog for milling tool geometry stored independently from turning tools."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MillingToolsDlg()
        self.ui.setupUi(self)
        self.setWindowIcon(self.parent().windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.ui.helpLabel.setText("Select a tool to preview its 3D cutter geometry during milling playback.")
        self.pendingTools = {}
        self.ui.addButton.clicked.connect(self.addTool)
        self.ui.editButton.clicked.connect(self.editTool)
        self.ui.removeButton.clicked.connect(self.removeTool)
        self.duplicateButton = self._add_action_button("Duplicate", self.duplicateTool)
        self.exportButton = self._add_action_button("Export...", self.exportTool)
        self.previewPane = ToolLibraryPreviewPane("milling", self)
        self.preview = self.previewPane.preview
        self._install_preview_splitter()
        self.ui.toolTable.itemSelectionChanged.connect(self.updatePreview)
        self.ui.toolTable.doubleClicked.connect(self.editTool)
        self.accepted.connect(self.applyValues)
        self.loadValues()

    def _install_preview_splitter(self):
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.verticalLayout.replaceWidget(self.ui.toolTable, splitter)
        self.ui.toolTable.setParent(splitter)
        splitter.addWidget(self.ui.toolTable)
        splitter.addWidget(self.previewPane)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([580, 300])
        self.previewSplitter = splitter

    def _add_action_button(self, text, callback):
        button = QPushButton(text, self)
        self.ui.toolButtonsLayout.insertWidget(self.ui.toolButtonsLayout.count() - 3, button)
        button.clicked.connect(callback)
        return button

    def showEvent(self, event):
        """Reload saved milling data whenever the dialog is opened."""
        self.loadValues()
        super().showEvent(event)

    def loadValues(self):
        """Copy current milling tool data into the dialog editing buffer."""
        self.pendingTools = copy.deepcopy(getattr(self.parent(), "millingTools", {}))
        self.refreshTable()

    def refreshTable(self, selected_key=None):
        """Rebuild the visible milling tool table."""
        table = self.ui.toolTable
        table.setRowCount(0)
        selected_row = -1
        for row, key in enumerate(sorted(self.pendingTools)):
            spec = self.pendingTools[key]
            tool_type = str(spec.get("type", "mill_flat"))
            values = (
                key,
                _MILLING_TOOL_TYPES.get(tool_type, "Mill Flat"),
                f"{float(spec.get('diameter', 0.0)):g}",
                f"{float(spec.get('cornerRadius', 0.0)):g}",
                f"{float(spec.get('length', 0.0)):g}",
                str(spec.get("description", "")),
            )
            table.insertRow(row)
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
            if key == selected_key:
                selected_row = row
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        if selected_row >= 0:
            table.selectRow(selected_row)
        elif table.rowCount():
            table.selectRow(0)
        self.updatePreview()

    def selectedTool(self):
        """Return the selected normalized T code."""
        row = self.ui.toolTable.currentRow()
        if row < 0:
            return None
        item = self.ui.toolTable.item(row, 0)
        return item.text() if item is not None else None

    def addTool(self):
        """Add a milling tool definition."""
        editor = _MillingToolEditor(self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        key, spec = editor.value()
        self.pendingTools[key] = spec
        self.refreshTable(key)

    def editTool(self, *_args):
        """Edit the selected milling tool definition."""
        key = self.selectedTool()
        if key is None:
            return
        editor = _MillingToolEditor(self, key, self.pendingTools[key])
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        new_key, spec = editor.value()
        if new_key != key:
            self.pendingTools.pop(key, None)
        self.pendingTools[new_key] = spec
        self.refreshTable(new_key)

    def removeTool(self):
        """Remove the selected milling tool definition."""
        key = self.selectedTool()
        if key is None:
            return
        self.pendingTools.pop(key, None)
        self.refreshTable()

    def updatePreview(self):
        """Preview the selected cutter and clear the pane when the table is empty."""
        key = self.selectedTool()
        self.preview.set_tool(self.pendingTools.get(key) if key is not None else None)

    def duplicateTool(self):
        """Duplicate the selected definition to the first free milling T code."""
        key = self.selectedTool()
        if key is None:
            return
        free_key = next((f"T{number}" for number in range(1, 100) if f"T{number}" not in self.pendingTools), None)
        if free_key is None:
            QMessageBox.warning(self, "Milling Tools", "No free T code is available.")
            return
        self.pendingTools[free_key] = copy.deepcopy(self.pendingTools[key])
        self.refreshTable(free_key)

    def exportTool(self, path=None):
        """Export the selected milling tool to JSON or CSV."""
        key = self.selectedTool()
        if key is None:
            return
        if not isinstance(path, str):
            path, _selected = QFileDialog.getSaveFileName(
                self, "Export Milling Tool", f"{key}.json", "JSON (*.json);;CSV (*.csv)"
            )
        if path:
            _export_tool_file(path, "milling", key, self.pendingTools[key])

    def applyValues(self):
        """Store milling tool data and rebuild the trace with the new cutter geometry."""
        self.parent().millingTools = copy.deepcopy(self.pendingTools)
        self.parent().updateData()
