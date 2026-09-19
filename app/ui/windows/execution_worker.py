"""Run CNC calculations off the GUI thread with delayed modal feedback."""

from time import monotonic

from PyQt6.QtCore import QCoreApplication, QEventLoop, Qt, QThread
from PyQt6.QtWidgets import QDialog, QWidget

from app import theme
from app.ui.generated.dialogs.execution_dialog import Ui_ExecutionDialog

EXECUTION_DIALOG_DELAY_MS = 0


class _ExecutionThread(QThread):
    def __init__(self, function, source, options):
        super().__init__()
        self.function = function
        self.source = source
        self.options = options
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.function(self.source, **self.options)
        except Exception as exc:
            self.error = exc


class _ExecutionDialog(QDialog):
    def __init__(self, parent, cancel, *, title, status_text, cancelling_text):
        super().__init__(parent)
        self.ui = Ui_ExecutionDialog()
        self.ui.setupUi(self)
        theme.apply_dialog_theme(self)
        self.cancel = cancel
        self.cancelling_text = cancelling_text
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.label = self.ui.statusLabel
        self.label.setText(status_text)
        self.button = self.ui.cancelButton
        self.button.clicked.connect(self.reject)

    def reject(self):
        # Keep the owner blocked until the worker has acknowledged cancellation.
        self.cancel()
        self.label.setText(self.cancelling_text)
        self.button.setEnabled(False)


def run_execution(
    owner,
    function,
    source,
    options,
    cancel,
    *,
    title="CNC execution",
    status_text="Executing CNC program…",
    cancelling_text="Cancelling CNC execution…",
    finalizing_text="Updating plot…",
    delay_ms=None,
    completion=None,
):
    """Run worker and GUI completion while keeping one truthful busy dialog visible."""
    worker = _ExecutionThread(function, source, options)
    worker.start()
    dialog = None

    if isinstance(owner, QWidget):
        reveal_delay = EXECUTION_DIALOG_DELAY_MS if delay_ms is None else max(0, int(delay_ms))
        reveal_at = monotonic() + (reveal_delay / 1000.0)

        while worker.isRunning():
            # Keep the GUI responsive without entering a nested QEventLoop.exec().
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)

            if dialog is None and monotonic() >= reveal_at:
                dialog = _ExecutionDialog(
                    owner,
                    cancel,
                    title=title,
                    status_text=status_text,
                    cancelling_text=cancelling_text,
                )
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()
                # The next phase can immediately occupy the GUI thread.  Paint
                # the complete dialog now so Windows never exposes its default
                # white client surface while plot widgets are being populated.
                if dialog.layout() is not None:
                    dialog.layout().activate()
                dialog.ensurePolished()
                QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
                dialog.repaint()

            worker.wait(10)

        worker.wait()
    else:
        # Non-widget consumers (including contract tests) need no event pumping.
        worker.wait()

    if worker.error is not None:
        if dialog is not None:
            dialog.accept()
            dialog.deleteLater()
        raise worker.error
    result = worker.result
    try:
        if completion is not None:
            if dialog is not None:
                dialog.label.setText(finalizing_text)
                QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            result = completion(result)
    finally:
        if dialog is not None:
            dialog.accept()
            dialog.deleteLater()
    return result
