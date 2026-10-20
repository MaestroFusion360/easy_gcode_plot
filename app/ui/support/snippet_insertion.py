"""Insert rendered snippet text into the Scintilla G-code editor."""

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QDialog, QMessageBox

from app.gcode.snippets.snippet_templates import RenderedSnippet, TemplateError, parameters, render
from app.ui.dialogs import snippet_insert
from app.ui.support.snippet_preview import error_text


def insert_rendered(editor, rendered: RenderedSnippet) -> None:
    """Replace the selection as one undo action and honor the cursor marker."""
    start = editor.SendScintilla(editor.SCI_GETSELECTIONSTART)
    editor.beginUndoAction()
    try:
        editor.replaceSelectedText(rendered.text)
        if rendered.cursor is not None:
            prefix = rendered.text[: rendered.cursor].encode("utf-8")
            editor.SendScintilla(editor.SCI_GOTOPOS, start + len(prefix))
    finally:
        editor.endUndoAction()


def insert_snippet(editor, source, context, *, picture=None, parent=None) -> bool:
    """Run the same insertion workflow from the manager and snippet panel."""
    try:
        requested = parameters(source)
        if requested:
            dialog = snippet_insert.SnippetInsertDialog(source, context, picture, parent)
            try:
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return False
                resolved = dialog.rendered
            finally:
                dialog.deleteLater()
        else:
            resolved = render(source, {}, context)
    except TemplateError as exc:
        QMessageBox.warning(parent, QCoreApplication.translate("SnippetsDialog", "Insert"), error_text(exc))
        return False
    if resolved is None:
        return False
    insert_rendered(editor, resolved)
    return True
