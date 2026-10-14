"""Text diff and QAction integration against real Qt and MDI buffers."""

# Regression assertions deliberately inspect MDI buffers and worker lifecycle.
# pylint: disable=protected-access

from time import monotonic, sleep

import pytest
from PyQt6.QtCore import QFile, Qt, QThreadPool
from PyQt6.QtGui import QTextFormat
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QPlainTextEdit

from app import i18n, settings
from app.main_window import MainWindow
from app.ui.dialogs import compare


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    settings.get_settings().setValue("GENERAL/AUTO_UPDATE", False)
    owner = MainWindow()
    yield owner
    owner.compareDlg.reject()
    QThreadPool.globalInstance().waitForDone(5000)
    owner.autoUpdateTimer.stop()
    owner.timer.stop()
    owner.deleteLater()
    qt_app.processEvents()


def _wait_result(dialog):
    deadline = monotonic() + 10
    while dialog._result is None or dialog._worker is not None or dialog._pending is not None:
        assert monotonic() < deadline, dialog.ui.statusLabel.text()
        QTest.qWait(5)
    return dialog._result


def _two_documents(window, left, right):
    window.ui.editor.setText(right)
    window.newFile()
    window.ui.editor.setText(left)
    window.ui.actionCompare.trigger()
    return window.compareDlg, _wait_result(window.compareDlg)


@pytest.mark.parametrize(
    ("left", "right", "kinds"),
    [
        ("", "", []),
        ("G0 X1\nM30\n", "G0 X1\nM30\n", ["equal", "equal"]),
        ("G0 X1\n", "G0 X2\n", ["changed"]),
        ("G0 X1\nM30\n", "G0 X1\nG1 X2\nM30\n", ["equal", "added", "equal"]),
        ("G0 X1\nG1 X2\nM30\n", "G0 X1\nM30\n", ["equal", "removed", "equal"]),
        ("", "\n", ["added"]),
        ("\n", "", ["removed"]),
        ("G0 X1\n\nM30\n", "G0 X1\nM30\n", ["equal", "removed", "equal"]),
        ("G0 X1\r\nM30\r\n", "G0 X1\nM30\n", ["equal", "equal"]),
        ("M30", "M30\n", ["changed"]),
    ],
)
def test_line_diff_handles_changes_blanks_empty_and_line_endings(left, right, kinds):
    result = compare.compare_texts(left, right)
    assert [row.kind for row in result.rows] == kinds
    assert len(result.text("left").split("\n")) == len(result.text("right").split("\n"))


def test_reordered_blocks_remain_text_changes():
    result = compare.compare_texts("G0 X1\nG1 X2\nM30\n", "G1 X2\nG0 X1\nM30\n")
    assert {row.kind for row in result.rows} == {"equal", "added", "removed"}
    assert result.rows[-1].left == result.rows[-1].right == "M30\n"


def test_aligned_padding_is_on_the_opposite_side_of_additions_and_removals():
    added = compare.compare_texts("G0 X1\nM30\n", "G0 X1\nG1 X2\nM30\n")
    assert added.rows[1].left is None
    assert added.text("left") == "G0 X1\n\nM30"
    assert added.kinds("left") == ["equal"] * 3
    assert added.kinds("right") == ["equal", "added", "equal"]
    removed = compare.compare_texts("G0 X1\nG1 X2\nM30\n", "G0 X1\nM30\n")
    assert removed.rows[1].right is None
    assert removed.kinds("left") == ["equal", "removed", "equal"]


def test_compare_action_reuses_menu_toolbar_hotkey_and_customization_identity(window):
    action = window.ui.actionCompare
    assert action.text() == "Compare"
    assert action in window.ui.menuCNC_Functions.actions()
    assert action in window.ui.cncToolBar.actions()
    assert window.hotkeyActions["actionCompare"] is action
    assert window.toolbarSettings.commands["actionCompare"][0] is action
    assert not action.icon().isNull()
    assert QFile(":/resource/icons/compare.png").exists()
    action.trigger()
    assert window.compareDlg.isVisible()
    window.compareDlg.reject()
    button = window.ui.cncToolBar.widgetForAction(action)
    button.click()
    assert window.compareDlg.isVisible()


def test_compare_visibility_and_shortcut_round_trip_preserves_existing_commands(window):
    values = dict(window.hotkeys, actionCompare="Ctrl+Alt+F10", actionNew="Ctrl+Alt+N")
    window.setHotkeys(values)
    window.toolbarSettings.apply(dict(window.toolbarSettings.selected, actionCompare=False), persist=True)
    window.saveSettings()
    restored = MainWindow()
    try:
        assert restored.ui.actionCompare.shortcut().toString() == "Ctrl+Alt+F10"
        assert restored.ui.actionNew.shortcut().toString() == "Ctrl+Alt+N"
        assert restored.ui.actionCompare not in restored.ui.cncToolBar.actions()
        assert restored.ui.actionCompare in restored.ui.menuCNC_Functions.actions()
        restored.optionsDlg.load_values()
        assert "actionCompare" in restored.optionsDlg.hotkeyEditor.values
        restored.optionsDlg.restore_defaults()
        assert "actionCompare" in restored.optionsDlg.hotkeyEditor.values
    finally:
        restored.deleteLater()


def test_default_sources_are_active_and_other_document_with_unsaved_memory_text(window, tmp_path):
    first = tmp_path / "first.nc"
    first.write_text("G0 X1", encoding="utf-8")
    window.loadFile(str(first))
    window.ui.editor.setCursorPosition(0, 5)
    QTest.keyClicks(window.ui.editor, "1")
    assert window.ui.editor.isModified()
    window.newFile()
    QTest.keyClicks(window.ui.editor, "G0 X22")
    window.ui.editor.setSelection(0, 0, 0, 2)
    before = (window.ui.editor.text(), window.ui.editor.getSelection(), window.ui.editor.isModified())
    documents = tuple(window._documents)
    window.ui.actionCompare.trigger()
    dialog = window.compareDlg
    result = _wait_result(dialog)
    assert dialog.ui.leftCombo.currentIndex() == 1
    assert dialog.ui.rightCombo.currentIndex() == 0
    assert "new 2" in dialog.ui.leftCombo.currentText()
    assert result.text("left") == "G0 X22"
    assert result.text("right") == "G0 X11"
    assert first.read_text(encoding="utf-8") == "G0 X1"
    dialog.close()
    assert tuple(window._documents) == documents
    assert window._active_document_index == 1
    assert (window.ui.editor.text(), window.ui.editor.getSelection(), window.ui.editor.isModified()) == before
    assert window.ui.editor.isUndoAvailable()
    window.ui.editor.undo()
    assert window.ui.editor.text() != "G0 X22"
    assert window._activate_document(0)
    assert window.ui.editor.isModified() and window.ui.editor.isUndoAvailable()
    window.ui.editor.undo()
    assert window.ui.editor.text() == "G0 X1"


def test_duplicate_filenames_show_distinguishable_full_paths(window, tmp_path):
    for directory in ("first", "second"):
        path = tmp_path / directory / "same.nc"
        path.parent.mkdir()
        path.write_text("M30", encoding="utf-8")
        window.loadFile(str(path))
    window.ui.actionCompare.trigger()
    dialog = window.compareDlg
    _wait_result(dialog)
    names = [dialog.ui.leftCombo.itemText(i) for i in range(2)]
    assert str(tmp_path / "first" / "same.nc") in names[0]
    assert str(tmp_path / "second" / "same.nc") in names[1]
    assert names[0] != names[1]


def test_both_browse_buttons_load_disk_snapshots_without_opening_mdi(window, tmp_path, monkeypatch):
    a, b = tmp_path / "a.nc", tmp_path / "b.ptp"
    a.write_text("(Проверка)\nG0 X1\n", encoding="utf-8")
    b.write_bytes("(Проверка)\nG0 X2\n".encode("cp1251"))
    paths = iter((str(a), str(b)))
    monkeypatch.setattr(compare.QFileDialog, "getOpenFileName", lambda *_args: (next(paths), ""))
    window.ui.editor.setText("G0 X999")
    original = (tuple(window._documents), window._active_document_index, window.curFile, window.ui.editor.text())
    window.ui.actionCompare.trigger()
    dialog = window.compareDlg
    dialog.ui.leftOpenButton.click()
    dialog.ui.rightOpenButton.click()
    result = _wait_result(dialog)
    assert result.text("left") == "(Проверка)\nG0 X1"
    assert result.text("right") == "(Проверка)\nG0 X2"
    assert [row.kind for row in result.rows] == ["equal", "changed"]
    dialog.reject()
    assert (
        tuple(window._documents),
        window._active_document_index,
        window.curFile,
        window.ui.editor.text(),
    ) == original


@pytest.mark.parametrize("error", [OSError("read failed"), UnicodeError("decode failed")])
def test_browse_errors_preserve_selection_and_do_not_crash(window, monkeypatch, error):
    dialog, previous = _two_documents(window, "G0 X1", "G0 X2")
    monkeypatch.setattr(compare.QFileDialog, "getOpenFileName", lambda *_args: ("broken.nc", ""))

    def fail(*_args):
        raise error

    monkeypatch.setattr(compare, "_read_editor_text", fail)
    notices = []
    monkeypatch.setattr(compare.QMessageBox, "warning", lambda *args: notices.append(args))
    selected = dialog.ui.leftCombo.currentIndex()
    dialog.ui.leftOpenButton.click()
    assert notices and "broken.nc" in notices[0][2]
    assert dialog.ui.leftCombo.currentIndex() == selected
    assert dialog._result is previous


def test_memory_document_can_be_compared_with_its_own_disk_version(window, tmp_path, monkeypatch):
    path = tmp_path / "edited.nc"
    path.write_text("G0 X1", encoding="utf-8")
    window.loadFile(str(path))
    window.ui.editor.setCursorPosition(0, 5)
    QTest.keyClicks(window.ui.editor, "2")
    monkeypatch.setattr(compare.QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    window.ui.actionCompare.trigger()
    dialog = window.compareDlg
    dialog.ui.rightOpenButton.click()
    result = _wait_result(dialog)
    assert result.text("left") == "G0 X12"
    assert result.text("right") == "G0 X1"
    assert result.rows[0].kind == "changed"
    assert len(window._documents) == 1
    assert window.ui.editor.isModified()


def test_binary_decode_failure_uses_existing_error_handling(window, tmp_path, monkeypatch):
    path = tmp_path / "binary.nc"
    path.write_bytes(b"\xffG0\x00X1")
    monkeypatch.setattr(compare.QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    notices = []
    monkeypatch.setattr(compare.QMessageBox, "warning", lambda *args: notices.append(args))
    window.ui.actionCompare.trigger()
    dialog = window.compareDlg
    selected = dialog.ui.leftCombo.currentIndex()
    dialog.ui.leftOpenButton.click()
    assert notices
    assert dialog.ui.leftCombo.currentIndex() == selected
    assert len(window._documents) == 1


def test_worker_failure_is_reported_without_terminating_ui(window, monkeypatch):
    def fail(*_args):
        raise MemoryError()

    monkeypatch.setattr(compare, "compare_texts", fail)
    window.newFile()
    window.ui.actionCompare.trigger()
    dialog = window.compareDlg
    deadline = monotonic() + 10
    while dialog._worker is not None:
        assert monotonic() < deadline
        QTest.qWait(5)
    assert dialog.ui.statusLabel.text() == "Comparison failed: MemoryError"
    assert dialog.isVisible()
    assert len(window._documents) == 2


@pytest.mark.parametrize("name", ["light", "dark"])
@pytest.mark.parametrize(
    ("left", "right", "side", "kind"),
    [
        ("G0 X1\n", "G0 X2\n", "left", "changed"),
        ("M30\n", "G0 X2\nM30\n", "right", "added"),
        ("G0 X2\nM30\n", "M30\n", "left", "removed"),
    ],
)
def test_diff_highlighting_is_full_width_on_correct_side_in_both_themes(window, name, left, right, side, kind):
    window.uiTheme = name
    dialog, _result = _two_documents(window, left, right)
    editor = getattr(dialog.ui, side + "Editor")
    selections = editor.extraSelections()
    assert len(selections) == 1
    color = selections[0].format.background().color()
    assert selections[0].format.property(QTextFormat.Property.FullWidthSelection)
    if kind == "changed":
        assert 35 <= color.hue() <= 65
    elif kind == "added":
        assert 80 <= color.hue() <= 170
    else:
        assert color.hue() < 20 or color.hue() > 330
    if kind != "changed":
        other = dialog.ui.rightEditor if side == "left" else dialog.ui.leftEditor
        assert not other.extraSelections()


@pytest.mark.parametrize("text", ["", "M30\n", "\n\n"])
def test_identical_sources_have_no_highlights(window, text):
    dialog, _result = _two_documents(window, text, text)
    assert not dialog.ui.leftEditor.extraSelections()
    assert not dialog.ui.rightEditor.extraSelections()
    assert dialog.ui.statusLabel.text() == "Files are identical."


def test_combobox_changes_recompare_automatically(window):
    dialog, result = _two_documents(window, "G0 X1", "G0 X2")
    assert result.rows[0].kind == "changed"
    dialog.ui.rightCombo.setCurrentIndex(dialog.ui.leftCombo.currentIndex())
    result = _wait_result(dialog)
    assert result.rows[0].kind == "equal"
    assert not dialog.ui.leftEditor.extraSelections()


def test_editors_are_read_only_copyable_resizable_and_scroll_in_sync(window):
    text = "\n".join(f"G1 X{i} F100" for i in range(500))
    dialog, _result = _two_documents(window, text, text)
    left, right = dialog.ui.leftEditor, dialog.ui.rightEditor
    assert left.isReadOnly() and right.isReadOnly()
    assert left.lineWrapMode() == right.lineWrapMode() == QPlainTextEdit.LineWrapMode.NoWrap
    assert left.font().fixedPitch() or left.font().family() == "Courier New"
    left.selectAll()
    left.copy()
    assert QApplication.clipboard().text() == text
    before = left.toPlainText()
    QTest.keyClicks(left, "changed")
    assert left.toPlainText() == before
    left.moveCursor(left.textCursor().MoveOperation.Start)
    a, b = left.verticalScrollBar(), right.verticalScrollBar()
    assert a.maximum() > 120 and a.maximum() == b.maximum()
    left_spy, right_spy = QSignalSpy(a.valueChanged), QSignalSpy(b.valueChanged)
    a.setValue(120)
    assert a.value() == b.value() == 120
    assert left.firstVisibleBlock().blockNumber() == right.firstVisibleBlock().blockNumber() == 120
    b.setValue(60)
    assert a.value() == b.value() == 60
    assert left.firstVisibleBlock().blockNumber() == right.firstVisibleBlock().blockNumber() == 60
    assert len(left_spy) + len(right_spy) == 4
    QTest.keyClick(right, Qt.Key.Key_PageDown)
    assert a.value() == b.value()
    assert left.firstVisibleBlock().blockNumber() == right.firstVisibleBlock().blockNumber()
    initial = dialog.ui.splitter.sizes()
    assert abs(initial[0] - initial[1]) <= 1
    dialog.ui.splitter.setSizes([300, 700])
    assert dialog.ui.splitter.sizes()[0] < dialog.ui.splitter.sizes()[1]


def test_horizontal_scroll_moves_both_viewports_without_recursion(window):
    text = "G1 " + "X123456789 " * 200
    dialog, _result = _two_documents(window, text, text)
    left, right = dialog.ui.leftEditor, dialog.ui.rightEditor
    a, b = left.horizontalScrollBar(), right.horizontalScrollBar()
    a.setValue(120)
    assert a.value() == b.value() == 120
    assert left.cursorRect().x() == right.cursorRect().x()
    b.setValue(60)
    assert a.value() == b.value() == 60
    assert left.cursorRect().x() == right.cursorRect().x()


def test_refresh_reloads_disk_sources_and_preserves_unsaved_mdi(window, tmp_path, monkeypatch):
    path = tmp_path / "external.nc"
    path.write_text("G0 X1", encoding="utf-8")
    monkeypatch.setattr(compare.QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    window.ui.editor.setText("G0 X2")
    window.ui.editor.setModified(True)
    window.ui.actionCompare.trigger()
    dialog = window.compareDlg
    dialog.ui.rightOpenButton.click()
    assert _wait_result(dialog).text("right") == "G0 X1"
    assert not dialog.ui.refreshButton.icon().isNull()
    path.write_text("G0 X2", encoding="utf-8")
    dialog.ui.refreshButton.click()
    result = _wait_result(dialog)
    assert result.text("right") == "G0 X2"
    assert result.rows[0].kind == "equal"
    assert window.ui.editor.text() == "G0 X2" and window.ui.editor.isModified()
    assert len(window._documents) == 1
    assert dialog.ui.rightCombo.count() == 2


def test_refresh_read_failure_retains_previous_comparison(window, tmp_path, monkeypatch):
    path = tmp_path / "external.nc"
    path.write_text("G0 X1", encoding="utf-8")
    monkeypatch.setattr(compare.QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    dialog, _result = _two_documents(window, "G0 X2", "G0 X3")
    dialog.ui.rightOpenButton.click()
    previous = _wait_result(dialog)
    path.unlink()
    notices = []
    monkeypatch.setattr(compare.QMessageBox, "warning", lambda *args: notices.append(args))
    dialog.ui.refreshButton.click()
    assert notices and str(path) in notices[0][2]
    assert dialog._result is previous


def test_refresh_reloads_both_external_files(window, tmp_path, monkeypatch):
    a, b = tmp_path / "a.nc", tmp_path / "b.nc"
    a.write_text("G0 X1", encoding="utf-8")
    b.write_text("G0 X2", encoding="utf-8")
    paths = iter((str(a), str(b)))
    monkeypatch.setattr(compare.QFileDialog, "getOpenFileName", lambda *_args: (next(paths), ""))
    window.ui.actionCompare.trigger()
    dialog = window.compareDlg
    dialog.ui.leftOpenButton.click()
    dialog.ui.rightOpenButton.click()
    _wait_result(dialog)
    a.write_text("G0 X3", encoding="utf-8")
    b.write_text("G0 X3", encoding="utf-8")
    dialog.ui.refreshButton.click()
    result = _wait_result(dialog)
    assert result.text("left") == result.text("right") == "G0 X3"
    assert result.rows[0].kind == "equal"


def test_late_worker_result_cannot_overwrite_newer_selection(window, monkeypatch):
    original = compare.compare_texts

    def slow(left, right):
        sleep(0.03)
        return original(left, right)

    monkeypatch.setattr(compare, "compare_texts", slow)
    dialog, _result = _two_documents(window, "G0 X1", "G0 X2")
    dialog.ui.rightCombo.setCurrentIndex(1)
    dialog.ui.rightCombo.setCurrentIndex(0)
    dialog.ui.rightCombo.setCurrentIndex(1)
    result = _wait_result(dialog)
    assert result.rows[0].kind == "equal"


def test_close_with_running_diff_and_reopen_is_safe(window, monkeypatch):
    original = compare.compare_texts

    def slow(left, right):
        sleep(0.03)
        return original(left, right)

    monkeypatch.setattr(compare, "compare_texts", slow)
    window.ui.editor.setText("G0 X1")
    window.newFile()
    window.ui.editor.setText("G0 X2")
    window.ui.actionCompare.trigger()
    window.compareDlg.close()
    window.ui.actionCompare.trigger()
    result = _wait_result(window.compareDlg)
    assert result.rows[0].kind == "changed"
    assert len(window._documents) == 2


def test_russian_compare_strings_use_compiled_catalog(qt_app):
    i18n.uninstall_translators(qt_app)
    assert i18n.install_translator(qt_app, "ru")
    owner = MainWindow()
    try:
        assert owner.ui.actionCompare.text() == "Сравнить"
        owner.ui.actionCompare.trigger()
        assert owner.compareDlg.windowTitle() == "Сравнение"
        assert owner.compareDlg.ui.leftLabel.text() == "Файл A"
        assert owner.compareDlg.ui.leftCombo.placeholderText() == "Выбери документ или открой файл"
    finally:
        owner.compareDlg.reject()
        owner.deleteLater()
        qt_app.processEvents()
        i18n.uninstall_translators(qt_app)


def test_large_repetitive_nc_program_remains_aligned():
    lines = ["G1 X1 F100\n"] * 20000
    right = lines.copy()
    right[10000] = "G1 X2 F100\n"
    result = compare.compare_texts("".join(lines), "".join(right))
    assert len(result.rows) == 20000
    assert sum(row.kind == "changed" for row in result.rows) == 1
    assert result.rows[10000].right == "G1 X2 F100\n"
