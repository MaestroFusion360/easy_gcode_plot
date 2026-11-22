"""Run CNC calculations off the GUI thread with optional modal feedback.

The payload runs in a QThread, but the calling function still blocks until the
worker stops and pumps GUI events meanwhile.  That keeps the window responsive
without a nested ``QEventLoop.exec()``, at the cost of re-entrancy: any handler
reached from the pump can observe a window whose execution state is still being
replaced.  MainWindow blocks document switching during execution and checks
source ownership before publication (``_PlotCompletion.is_current`` in
``main_window_execution``).  The modal dialog is a visual guard, not a lock.
"""

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


def _create_dialog(owner, cancel, title, status_text, cancelling_text):
    """Show the modal dialog and force a full paint before the owner is filled."""
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
    # The next phase can immediately occupy the GUI thread.  Paint the complete
    # dialog now so Windows never exposes its default white client surface while
    # plot widgets are being populated.
    if dialog.layout() is not None:
        dialog.layout().activate()
    dialog.ensurePolished()
    QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
    dialog.repaint()
    return dialog


def _wait_for_worker(
    worker,
    owner,
    *,
    cancel,
    show_dialog,
    delay_ms,
    title,
    status_text,
    cancelling_text,
):
    """Join the worker, pumping events for widget owners so the window stays alive."""
    if not isinstance(owner, QWidget):
        # Non-widget consumers (including contract tests) need no event pumping.
        worker.wait()
        return None

    reveal_delay = EXECUTION_DIALOG_DELAY_MS if delay_ms is None else max(0, int(delay_ms))
    reveal_at = monotonic() + (reveal_delay / 1000.0)
    dialog = None
    while worker.isRunning():
        # Keep the GUI responsive without entering a nested QEventLoop.exec().
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
        if not worker.isRunning():
            break

        # Event handlers may release the worker during processEvents().  Do
        # not flash a dialog for an execution that has already completed.
        if show_dialog and dialog is None and worker.isRunning() and monotonic() >= reveal_at:
            dialog = _create_dialog(owner, cancel, title, status_text, cancelling_text)

        worker.wait(10)

    worker.wait()
    return dialog


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
    show_dialog=True,
):
    """Run worker and optional GUI completion, with modal feedback when requested."""
    worker = _ExecutionThread(function, source, options)
    worker.start()
    dialog = _wait_for_worker(
        worker,
        owner,
        cancel=cancel,
        show_dialog=show_dialog,
        delay_ms=delay_ms,
        title=title,
        status_text=status_text,
        cancelling_text=cancelling_text,
    )

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
