"""Unified current-program setup and persistent tool-library dialog."""

from copy import deepcopy

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QSizePolicy, QTableWidgetItem

from app.settings import save_library_changes
from app.tools.definitions import (
    DEFAULT_AUTO_TIP_ORIENTATION,
    MILLING_TOOL_LABELS,
    TURNING_INSERT_TYPES,
    TURNING_TOOL_LABELS,
)
from app.ui.dialogs.tool_dialogs import _export_tool_library, _MillingToolEditor, _TurningToolEditor
from app.ui.generated.editors.tool_library import Ui_ToolLibraryDialog


class ToolLibraryDialog(QDialog):
    """Show temporary program T slots and reusable saved tools in one window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ToolLibraryDialog()
        self.ui.setupUi(self)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.pages = {
            "milling": {
                "widget": self.ui.millingTab,
                "program": self.ui.millingProgramTable,
                "library": self.ui.millingLibraryTable,
                "previewPane": self.ui.millingPreviewPane,
            },
            "turning": {
                "widget": self.ui.turningTab,
                "program": self.ui.turningProgramTable,
                "library": self.ui.turningLibraryTable,
                "previewPane": self.ui.turningPreviewPane,
            },
        }
        self.pages["milling"]["previewPane"].set_kind("milling")
        self.pages["turning"]["previewPane"].set_kind("turning")
        self._library_original = {}
        self._library_working = {}
        self._preview_sources = {"milling": None, "turning": None}
        for kind in ("milling", "turning"):
            self.pages[kind]["preview"] = self.pages[kind]["previewPane"].preview
            splitter = getattr(self.ui, f"{kind}Splitter")
            splitter.setStretchFactor(0, 2)
            splitter.setStretchFactor(1, 1)
            self.pages[kind]["widget"].setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
            getattr(self.ui, f"{kind}TablesWidget").setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
            )
            self.pages[kind]["previewPane"].setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
            for source in ("program", "library"):
                table = self.pages[kind][source]
                table.verticalHeader().setVisible(False)
                table.horizontalHeader().setStretchLastSection(True)
        self.begin_session()
        self._connect_actions()

    def _connect_actions(self):
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)
        self.ui.tabs.currentChanged.connect(self._refresh_active_preview)
        for kind in ("milling", "turning"):
            prefix = kind
            program_table = self.pages[kind]["program"]
            library_table = self.pages[kind]["library"]
            program_table.itemSelectionChanged.connect(lambda k=kind: self._preview_selected(k, "program"))
            library_table.itemSelectionChanged.connect(lambda k=kind: self._preview_selected(k, "library"))
            program_table.doubleClicked.connect(lambda _index, k=kind: self.edit_program_tool(k))
            library_table.doubleClicked.connect(lambda _index, k=kind: self.edit_library_tool(k))
            getattr(self.ui, f"{prefix}EditProgramButton").clicked.connect(
                lambda _checked=False, k=kind: self.edit_program_tool(k)
            )
            getattr(self.ui, f"{prefix}AssignButton").clicked.connect(
                lambda _checked=False, k=kind: self.assign_from_library(k)
            )
            getattr(self.ui, f"{prefix}SaveButton").clicked.connect(
                lambda _checked=False, k=kind: self.save_program_to_library(k)
            )
            getattr(self.ui, f"{prefix}AddLibraryButton").clicked.connect(
                lambda _checked=False, k=kind: self.add_library_tool(k)
            )
            getattr(self.ui, f"{prefix}EditLibraryButton").clicked.connect(
                lambda _checked=False, k=kind: self.edit_library_tool(k)
            )
            getattr(self.ui, f"{prefix}DuplicateLibraryButton").clicked.connect(
                lambda _checked=False, k=kind: self.duplicate_library_tool(k)
            )
            getattr(self.ui, f"{prefix}ExportLibraryButton").clicked.connect(
                lambda _checked=False, k=kind: self.export_library_tool(k)
            )
            getattr(self.ui, f"{prefix}RemoveLibraryButton").clicked.connect(
                lambda _checked=False, k=kind: self.remove_library_tool(k)
            )

    def showEvent(self, event):
        parent = self.parent()
        if parent is not None:
            parent.discover_program_tools(parent.ui.editor.text())
            self.ui.tabs.setCurrentIndex(1 if parent.latheMode else 0)
        self.begin_session()
        self.refresh()
        super().showEvent(event)

    def begin_session(self):
        for kind in ("milling", "turning"):
            attribute = "turningToolLibrary" if kind == "turning" else "millingToolLibrary"
            library = deepcopy(getattr(self.parent(), attribute, {}))
            self._library_original[kind] = library
            self._library_working[kind] = deepcopy(library)
            self._preview_sources[kind] = None

    def refresh(self, kind=None, selected_program=None, selected_library=None):
        kinds = (kind,) if kind else ("milling", "turning")
        for item in kinds:
            self._fill_table(item, "program", self._program_tools(item), selected_program)
            self._fill_table(item, "library", self.library_tools(item), selected_library)
            source = "program" if selected_program is not None else "library" if selected_library is not None else None
            self._set_preview(item, source)

    def _fill_table(self, kind, source, tools, selected_key=None):
        table = self.pages[kind][source]
        table.blockSignals(True)
        table.setRowCount(0)
        selected_row = -1
        for row, key in enumerate(sorted(tools)):
            spec = tools[key]
            values = (key, self._type_label(kind, spec), self._geometry(kind, spec), str(spec.get("description", "")))
            table.insertRow(row)
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
            if key == selected_key:
                selected_row = row
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        if selected_row >= 0:
            table.selectRow(selected_row)
        else:
            table.clearSelection()
        table.blockSignals(False)

    def _program_tools(self, kind):
        return getattr(self.parent(), "tools" if kind == "turning" else "millingTools", {})

    def library_tools(self, kind):
        return self._library_working[kind]

    @staticmethod
    def _type_label(kind, spec):
        labels = TURNING_TOOL_LABELS if kind == "turning" else MILLING_TOOL_LABELS
        tool_type = str(spec.get("type", ""))
        return labels.get(tool_type, tool_type or "Unknown")

    @staticmethod
    def _geometry(kind, spec):
        if kind == "milling":
            diameter = float(spec.get("diameter", 0.0))
            radius = float(spec.get("cornerRadius", 0.0))
            length = float(spec.get("length", 0.0))
            return f"D{diameter:g}  R{radius:g}  L{length:g}"
        tool_type = str(spec.get("type", ""))
        if tool_type in {"drill", "tap"}:
            return f"D{float(spec.get('diameter', 0.0)):g}  L{float(spec.get('length', 0.0)):g}"
        if tool_type == "groove":
            return f"W{float(spec.get('width', 0.0)):g}  R{float(spec.get('noseRadius', 0.0)):g}"
        if tool_type == "thread":
            return f"E{float(spec.get('threadAngle', 60.0)):g}  EX{float(spec.get('threadTipWidth', 0.8)):g}"
        if tool_type in TURNING_INSERT_TYPES:
            orientation = int(spec.get("tipOrientation", DEFAULT_AUTO_TIP_ORIENTATION.get(tool_type, 1)))
            return f"P{orientation}  R{float(spec.get('noseRadius', 0.0)):g}  L{float(spec.get('insertLength', 0.0)):g}"
        return "—"

    def _selected_key(self, kind, source):
        table = self.pages[kind][source]
        selected_rows = table.selectionModel().selectedRows()
        row = selected_rows[0].row() if selected_rows else -1
        item = table.item(row, 0) if row >= 0 else None
        return item.text() if item is not None else None

    def _preview_selected(self, kind, source):
        self._set_preview(kind, source)

    def _set_preview(self, kind, source):
        self._preview_sources[kind] = source
        if source is None:
            self.pages[kind]["preview"].set_tool(None)
            return
        key = self._selected_key(kind, source)
        tools = self._program_tools(kind) if source == "program" else self.library_tools(kind)
        self.pages[kind]["preview"].set_tool(tools.get(key) if key else None)
        if key:
            self.pages[kind]["previewPane"].fit_preview()

    def _refresh_active_preview(self, _index=None):
        kind = "turning" if self.ui.tabs.currentWidget() is self.ui.turningTab else "milling"
        self._set_preview(kind, self._preview_sources[kind])

    @staticmethod
    def _editor_type(kind):
        return _TurningToolEditor if kind == "turning" else _MillingToolEditor

    def edit_program_tool(self, kind):
        key = self._selected_key(kind, "program")
        if key is None:
            return
        tools = self._program_tools(kind)
        editor = self._editor_type(kind)(self, key, tools[key])
        editor.toolCode.setEnabled(False)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        _key, spec = editor.value()
        tools[key] = deepcopy(spec)
        self.parent().updateData()
        self.refresh(kind, selected_program=key)

    def assign_from_library(self, kind):
        program_key = self._selected_key(kind, "program")
        library_key = self._selected_key(kind, "library")
        if program_key is None or library_key is None:
            return
        self._program_tools(kind)[program_key] = deepcopy(self.library_tools(kind)[library_key])
        self.parent().updateData()
        self.refresh(kind, selected_program=program_key, selected_library=library_key)

    def save_program_to_library(self, kind):
        program_key = self._selected_key(kind, "program")
        if program_key is None:
            return
        library = self.library_tools(kind)
        editor = self._editor_type(kind)(self, program_key, self._program_tools(kind)[program_key])
        editor.setWindowTitle(QCoreApplication.translate("ToolLibraryDialog", "Save Tool to Library"))
        editor.reservedCodes = set(library) - {program_key}
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        key, spec = editor.value()
        if key in library and not self._confirm_replace(key):
            return
        self._persist_library_change(kind, key, spec)

    def add_library_tool(self, kind):
        library = self.library_tools(kind)
        editor = self._editor_type(kind)(self)
        editor.reservedCodes = set(library)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        key, spec = editor.value()
        self._persist_library_change(kind, key, spec)

    def edit_library_tool(self, kind):
        key = self._selected_key(kind, "library")
        if key is None:
            return
        library = self.library_tools(kind)
        editor = self._editor_type(kind)(self, key, library[key])
        editor.reservedCodes = set(library) - {key}
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        new_key, spec = editor.value()
        self._persist_library_change(kind, new_key, spec, previous_key=key)

    def duplicate_library_tool(self, kind):
        key = self._selected_key(kind, "library")
        if key is None:
            return
        library = self.library_tools(kind)
        if kind == "turning":
            new_key = next((f"T{number:04d}" for number in range(1, 10000) if f"T{number:04d}" not in library), None)
        else:
            new_key = next((f"T{number}" for number in range(1, 100) if f"T{number}" not in library), None)
        if new_key is None:
            QMessageBox.warning(
                self,
                QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                QCoreApplication.translate("ToolLibraryDialog", "No free tool number is available."),
            )
            return
        self._persist_library_change(kind, new_key, deepcopy(library[key]))

    def export_library_tool(self, kind, path=None):
        library = self.library_tools(kind)
        if not isinstance(path, str):
            path, _selected = QFileDialog.getSaveFileName(
                self,
                "Export Saved Library",
                f"{kind}_tools.json",
                "JSON (*.json);;CSV (*.csv)",
            )
        if path:
            _export_tool_library(path, kind, library)

    def remove_library_tool(self, kind):
        key = self._selected_key(kind, "library")
        if key is None:
            return
        answer = QMessageBox.question(
            self,
            QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
            QCoreApplication.translate("ToolLibraryDialog", "Remove saved tool {0}?").format(key),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._persist_library_change(kind, None, None, previous_key=key)

    def _confirm_replace(self, key):
        answer = QMessageBox.question(
            self,
            QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
            QCoreApplication.translate("ToolLibraryDialog", "Saved tool {0} already exists. Replace it?").format(key),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _persist_library_change(self, kind, key, spec, previous_key=None):
        edited = deepcopy(self.library_tools(kind))
        if previous_key is not None:
            edited.pop(previous_key, None)
        if key is not None:
            edited[key] = deepcopy(spec)
        self._library_working[kind] = edited
        self.refresh(kind, selected_library=key)
        return True

    def accept(self):
        if not save_library_changes(self._library_original, self._library_working):
            QMessageBox.warning(
                self,
                QCoreApplication.translate("ToolLibraryDialog", "Tool Library"),
                QCoreApplication.translate("ToolLibraryDialog", "Could not save the tool library. Please retry."),
            )
            return
        for kind in ("milling", "turning"):
            if self._library_working[kind] == self._library_original[kind]:
                continue
            attribute = "turningToolLibrary" if kind == "turning" else "millingToolLibrary"
            setattr(self.parent(), attribute, deepcopy(self._library_working[kind]))
        super().accept()

    def reject(self):
        self.begin_session()
        super().reject()
