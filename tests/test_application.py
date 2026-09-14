from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QLocale
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDoubleSpinBox

from app import application
from app.ui.numeric_input import install_decimal_separator_filter


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    ("language", "text"),
    [(QLocale.Language.Russian, "1.25"), (QLocale.Language.English, "1,25")],
)
def test_double_spin_boxes_accept_both_decimal_separator_keys(qt_app, language, text):
    event_filter = install_decimal_separator_filter(qt_app)
    spin = QDoubleSpinBox()
    spin.setRange(-100.0, 100.0)
    spin.setDecimals(3)
    spin.setLocale(QLocale(language))
    spin.show()
    spin.setFocus()
    spin.lineEdit().selectAll()

    QTest.keyClicks(spin, text)

    assert spin.value() == pytest.approx(1.25)
    qt_app.removeEventFilter(event_filter)


def test_run_schedules_settled_fit_for_visible_stock_in_persisted_lathe_mode(monkeypatch):
    events = []

    class FakeApplication:
        def __init__(self, _argv):
            events.append("app")

        def exec(self):
            events.append("exec")
            return 17

    class FakeWindow:
        latheMode = True

        def show(self):
            events.append("show")

        def stockOutlineBounds(self):
            events.append("bounds")
            return ((-25.0, 25.0), (0.0, 0.0), (-100.0, 2.0))

        def fitToView(self):
            events.append("fit")

    def single_shot(delay, callback):
        events.append(("timer", delay))
        callback()

    monkeypatch.setattr(application, "QApplication", FakeApplication)
    monkeypatch.setattr(application, "MainWindow", FakeWindow)
    monkeypatch.setattr(application, "QTimer", SimpleNamespace(singleShot=single_shot))
    monkeypatch.setattr(application, "install_decimal_separator_filter", lambda _app: None)

    assert application.run() == 17
    assert events == [
        "app",
        "show",
        ("timer", application.STARTUP_LATHE_FIT_DELAY_MS),
        "bounds",
        "fit",
        "exec",
    ]


def test_run_does_not_fit_lathe_view_when_stock_is_not_visible(monkeypatch):
    events = []

    class FakeApplication:
        def __init__(self, _argv):
            pass

        def exec(self):
            return 0

    class FakeWindow:
        latheMode = True

        def show(self):
            pass

        def stockOutlineBounds(self):
            events.append("bounds")

        def fitToView(self):
            events.append("fit")

    monkeypatch.setattr(application, "QApplication", FakeApplication)
    monkeypatch.setattr(application, "MainWindow", FakeWindow)
    monkeypatch.setattr(application, "QTimer", SimpleNamespace(singleShot=lambda _delay, callback: callback()))
    monkeypatch.setattr(application, "install_decimal_separator_filter", lambda _app: None)

    assert application.run() == 0
    assert events == ["bounds"]


def test_run_does_not_force_fit_for_milling_mode(monkeypatch):
    fitted = []

    class FakeApplication:
        def __init__(self, _argv):
            pass

        def exec(self):
            return 0

    class FakeWindow:
        latheMode = False

        def show(self):
            pass

        def stockOutlineBounds(self):
            fitted.append("bounds")
            return ((0.0, 1.0),) * 3

        def fitToView(self):
            fitted.append("fit")

    monkeypatch.setattr(application, "QApplication", FakeApplication)
    monkeypatch.setattr(application, "MainWindow", FakeWindow)
    monkeypatch.setattr(application, "QTimer", SimpleNamespace(singleShot=lambda *_args: fitted.append("timer")))
    monkeypatch.setattr(application, "install_decimal_separator_filter", lambda _app: None)

    assert application.run() == 0
    assert fitted == []
