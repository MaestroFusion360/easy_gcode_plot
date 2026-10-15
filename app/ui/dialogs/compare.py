"""Read-only, aligned text comparison of existing documents or disk snapshots."""

# The comparison adapter reads the owner's MDI buffers without activating them.
# pylint: disable=protected-access

from __future__ import annotations

from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from pathlib import Path
from threading import Event

from PyQt6.Qsci import QsciDocument, QsciScintilla
from PyQt6.QtCore import QObject, QRunnable, QSignalBlocker, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QColor, QFontDatabase, QIcon, QTextCursor, QTextFormat
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QTextEdit

from app.ui.generated.dialogs.compare import Ui_CompareDialog
from app.ui.support.file_drop import FileDropTarget
from app.ui.windows.main_window_file_ops import NC_FILE_FILTER, _read_editor_text


@dataclass(frozen=True)
class DiffRow:
    left: str | None
    right: str | None
    kind: str


@dataclass(frozen=True)
class TextDiff:
    rows: tuple[DiffRow, ...]

    def text(self, side):
        return "\n".join((getattr(row, side) or "").removesuffix("\n") for row in self.rows)

    def kinds(self, side):
        return [row.kind if getattr(row, side) is not None else "equal" for row in self.rows]


def compare_texts(left: str, right: str) -> TextDiff:
    """Align logical lines, retaining blanks and the final-newline distinction.

    Line endings are normalized; no NC parsing or document mutation occurs.
    The popular-line heuristic limits repeated-line matching in large programs.
    """
    a = left.replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)
    b = right.replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)
    prefix, suffix = _equal_edges(a, b)
    rows = [DiffRow(line, line, "equal") for line in a[:prefix]]
    tail = a[len(a) - suffix :]
    a, b = a[prefix : len(a) - suffix], b[prefix : len(b) - suffix]
    for tag, i, end_a, j, end_b in SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            rows.extend(DiffRow(line, line, "equal") for line in a[i:end_a])
            continue
        paired = min(end_a - i, end_b - j) if tag == "replace" else 0
        rows.extend(DiffRow(a[i + n], b[j + n], "changed") for n in range(paired))
        rows.extend(DiffRow(line, None, "removed") for line in a[i + paired : end_a])
        rows.extend(DiffRow(None, line, "added") for line in b[j + paired : end_b])
    rows.extend(DiffRow(line, line, "equal") for line in tail)
    return TextDiff(tuple(rows))


def _equal_edges(a, b):
    """Keep unchanged edges precise even when most NC lines are repetitive."""
    length = min(len(a), len(b))
    prefix = 0
    while prefix < length and a[prefix] == b[prefix]:
        prefix += 1
    suffix = 0
    while suffix < length - prefix and a[-suffix - 1] == b[-suffix - 1]:
        suffix += 1
    return prefix, suffix


@dataclass(frozen=True)
class CompareSource:
    name: str
    document: object = None
    text: str | None = None
    path: str | None = None


class _DiffSignals(QObject):
    finished = pyqtSignal(int, object, str)


class _DiffJob(QRunnable):
    """Pool-owned work survives closing the dialog without owning any widgets."""

    def __init__(self, revision, left, right):
        super().__init__()
        self.revision, self.left, self.right = revision, left, right
        self.cancelled = Event()
        self.signals = _DiffSignals()

    def run(self):
        result, error = None, ""
        try:
            if not self.cancelled.is_set():
                result = compare_texts(self.left, self.right)
            if self.cancelled.is_set():
                result = None
        except Exception as exc:  # A worker exception must not terminate Qt's event loop.
            error = str(exc) or type(exc).__name__
        self.signals.finished.emit(self.revision, result, error)


_DIFF_COLORS = {
    "light": {"changed": "#fff1b8", "added": "#d7f5d7", "removed": "#fbd6d6"},
    "dark": {"changed": "#574815", "added": "#214c35", "removed": "#5a2d32"},
}


def _highlight_spans(kinds):
    start = 0
    for end in range(1, len(kinds) + 1):
        if end == len(kinds) or kinds[end] != kinds[start]:
            if kinds[start] != "equal":
                yield start, end - 1, kinds[start]
            start = end


class CompareDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.ui = Ui_CompareDialog()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon(":/resource/icons/compare.png"))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self._revision = 0
        self._worker = None
        self._pending = None
        self._result = None
        self._reader = None
        self._syncing_scroll = False
        self.ui.splitter.setChildrenCollapsible(False)
        self.ui.splitter.setSizes([550, 550])
        for combo in (self.ui.leftCombo, self.ui.rightCombo):
            combo.currentIndexChanged.connect(self._selection_changed)
        self.ui.leftOpenButton.clicked.connect(lambda: self._browse(self.ui.leftCombo))
        self.ui.rightOpenButton.clicked.connect(lambda: self._browse(self.ui.rightCombo))
        self._file_drop_targets = []
        for panel, editor, combo in (
            (self.ui.leftPanel, self.ui.leftEditor, self.ui.leftCombo),
            (self.ui.rightPanel, self.ui.rightEditor, self.ui.rightCombo),
        ):
            self._file_drop_targets.append(
                FileDropTarget(
                    (panel, editor, editor.viewport(), combo),
                    lambda paths, target=combo: self._open_disk_source(target, paths[0]),
                    parent=self,
                    max_files=1,
                )
            )
        self.ui.refreshButton.clicked.connect(self._refresh)
        for source, target in (
            (self.ui.leftEditor, self.ui.rightEditor),
            (self.ui.rightEditor, self.ui.leftEditor),
        ):
            for accessor in ("verticalScrollBar", "horizontalScrollBar"):
                scrollbar = getattr(target, accessor)()
                getattr(source, accessor)().valueChanged.connect(
                    lambda value, target_bar=scrollbar: self._sync_scroll(target_bar, value)
                )
        self.ui.buttonBox.rejected.connect(self.reject)

    def showEvent(self, event):
        self._configure_editors()
        self._load_documents()
        super().showEvent(event)
        self._selection_changed()

    def _configure_editors(self):
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setFixedPitch(True)
        font.setPointSize(max(9, int(getattr(self.parent(), "sizeTxt", 12))))
        for editor in (self.ui.leftEditor, self.ui.rightEditor):
            editor.setFont(font)
        theme = "dark" if self.parent().uiTheme == "dark" else "light"
        self._colors = _DIFF_COLORS[theme]
        for kind, label in (
            ("changed", self.ui.changedLabel),
            ("added", self.ui.addedLabel),
            ("removed", self.ui.removedLabel),
        ):
            label.setStyleSheet(f"background-color: {self._colors[kind]}; padding: 3px 6px;")

    def _load_documents(self):
        owner = self.parent()
        sources = []
        for index, item in enumerate(owner._documents):
            path = owner.curFile if index == owner._active_document_index else item.file_name
            name = f"{Path(path).name} — {path}" if path else f"new {item.untitled_number}"
            sources.append(CompareSource(name, document=item))
        active = owner._active_document_index
        other = next((i for i in range(len(sources)) if i != active), -1)
        for combo, selected in ((self.ui.leftCombo, active), (self.ui.rightCombo, other)):
            with QSignalBlocker(combo):
                combo.clear()
                for source in sources:
                    combo.addItem(source.name, source)
                    combo.setItemData(combo.count() - 1, source.name, Qt.ItemDataRole.ToolTipRole)
                combo.setCurrentIndex(selected)

    def _source_text(self, source):
        if source.document is None:
            return source.text
        owner = self.parent()
        if source.document is owner._documents[owner._active_document_index]:
            return owner.ui.editor.text()
        # QsciDocument has no text accessor. A detached view reads its shared
        # buffer without activating it or touching the visible editor's state.
        if self._reader is None:
            self._reader = QsciScintilla(self)
            self._reader.hide()
        try:
            self._reader.setDocument(source.document.document)
            return self._reader.text()
        finally:
            self._reader.setDocument(QsciDocument())

    def _browse(self, combo):
        path, _filter = QFileDialog.getOpenFileName(self, self.tr("Open NC program"), "", NC_FILE_FILTER)
        if not path:
            return
        self._open_disk_source(combo, path)

    def _read_disk_source(self, path):
        """Read a disk snapshot and report failures consistently for open/refresh."""
        try:
            text, _encoding = _read_editor_text(path, getattr(self.parent(), "fileEncoding", "utf-8"))
        except (OSError, UnicodeError) as exc:
            QMessageBox.warning(
                self,
                self.tr("Compare"),
                self.tr("Cannot read file %1:\n%2").replace("%1", path).replace("%2", str(exc)),
            )
            return None
        return text

    def _open_disk_source(self, combo, path):
        text = self._read_disk_source(path)
        if text is None:
            return False
        name = self.tr("%1 (disk)").replace("%1", f"{Path(path).name} — {path}")
        combo.addItem(name, CompareSource(name, text=text, path=path))
        combo.setItemData(combo.count() - 1, path, Qt.ItemDataRole.ToolTipRole)
        combo.setCurrentIndex(combo.count() - 1)
        return True

    def _refresh(self):
        updates = []
        for combo in (self.ui.leftCombo, self.ui.rightCombo):
            source = combo.currentData()
            if source is None or source.path is None:
                continue
            text = self._read_disk_source(source.path)
            if text is None:
                return
            updates.append((combo, replace(source, text=text)))
        for combo, source in updates:
            combo.setItemData(combo.currentIndex(), source)
        self._selection_changed()

    def _selection_changed(self, _index=None):
        self._revision += 1
        self._pending = None
        if self._worker is not None:
            self._worker.cancelled.set()
        self._clear_result()
        left, right = self.ui.leftCombo.currentData(), self.ui.rightCombo.currentData()
        for combo in (self.ui.leftCombo, self.ui.rightCombo):
            source = combo.currentData()
            combo.setToolTip(source.name if source is not None else combo.placeholderText())
        if left is None or right is None:
            self.ui.statusLabel.setText(self.tr("Select two sources to compare."))
            return
        self._pending = (self._revision, self._source_text(left), self._source_text(right))
        self.ui.statusLabel.setText(self.tr("Comparing..."))
        self._start_pending()

    def _start_pending(self):
        if self._worker is not None or self._pending is None:
            return
        worker = _DiffJob(*self._pending)
        self._pending = None
        self._worker = worker
        worker.signals.finished.connect(self._comparison_finished, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(worker)

    def _comparison_finished(self, revision, result, error):
        self._worker = None
        if revision == self._revision and self.isVisible():
            if error:
                self.ui.statusLabel.setText(self.tr("Comparison failed: %1").replace("%1", error))
            elif result is not None:
                self._show_result(result)
        self._start_pending()

    def _show_result(self, result):
        self._result = result
        for side, editor in (("left", self.ui.leftEditor), ("right", self.ui.rightEditor)):
            with QSignalBlocker(editor.verticalScrollBar()):
                editor.setPlainText(result.text(side))
                self._highlight(editor, result.kinds(side))
                editor.verticalScrollBar().setValue(0)
        counts = {kind: sum(row.kind == kind for row in result.rows) for kind in self._colors}
        if not any(counts.values()):
            self.ui.statusLabel.setText(self.tr("Files are identical."))
        else:
            self.ui.statusLabel.setText(
                self.tr("Changed: %1 | Added: %2 | Removed: %3")
                .replace("%1", str(counts["changed"]))
                .replace("%2", str(counts["added"]))
                .replace("%3", str(counts["removed"]))
            )

    def _highlight(self, editor, kinds):
        selections = []
        document = editor.document()
        for first, last, kind in _highlight_spans(kinds):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(document.findBlockByNumber(first))
            end = document.findBlockByNumber(last)
            selection.cursor.setPosition(end.position(), QTextCursor.MoveMode.KeepAnchor)
            selection.format.setBackground(QColor(self._colors[kind]))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selections.append(selection)
            if first != last:
                # A multiline selection paints its final block only up to the
                # caret. Give that block its own full-width, empty selection.
                final = QTextEdit.ExtraSelection()
                final.cursor = QTextCursor(end)
                final.format = selection.format
                selections.append(final)
        editor.setExtraSelections(selections)

    def _sync_scroll(self, scrollbar, value):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        try:
            # QPlainTextEdit also listens to valueChanged to move its viewport.
            # Blocking that signal updates the thumb but leaves the text behind.
            scrollbar.setValue(value)
        finally:
            self._syncing_scroll = False

    def _clear_result(self):
        self._result = None
        for editor in (self.ui.leftEditor, self.ui.rightEditor):
            editor.setExtraSelections([])
            editor.clear()

    def done(self, result):
        self._revision += 1
        self._pending = None
        if self._worker is not None:
            self._worker.cancelled.set()
        self._clear_result()
        for combo in (self.ui.leftCombo, self.ui.rightCombo):
            with QSignalBlocker(combo):
                combo.clear()
        super().done(result)
