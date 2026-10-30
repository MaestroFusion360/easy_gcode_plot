# pylint: disable=protected-access

import json
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QLocale
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDoubleSpinBox

from app import application
from app.integration.minicad_bundle import read_bundle
from app.ui.support.numeric_input import install_decimal_separator_filter


@pytest.fixture(autouse=True)
def isolated_simulation_listener(monkeypatch):
    monkeypatch.setattr(application, "SimulationSession", lambda _callback: SimpleNamespace(listen=lambda: True))


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
    monkeypatch.setattr(application.theme, "apply_application_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(application.i18n, "install_translator", lambda *_args, **_kwargs: False)

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
    monkeypatch.setattr(application.theme, "apply_application_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(application.i18n, "install_translator", lambda *_args, **_kwargs: False)

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
    monkeypatch.setattr(application.theme, "apply_application_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(application.i18n, "install_translator", lambda *_args, **_kwargs: False)

    assert application.run() == 0
    assert fitted == []


@pytest.mark.parametrize("diameter", [10.0, 6.0])
@pytest.mark.parametrize("include_stl", [False, True])
def test_bundle_tool_replaces_program_tool_before_simulation(tmp_path, diameter, include_stl):
    tools = {"T1": {"type": "mill_flat", "diameter": 80.0}}
    bundle = SimpleNamespace(
        bounds=(-5, 105, -5, 105, -10, 0),
        origin=(0, 0, 0),
        tool_number=1,
        tool_diameter=diameter,
        tool_type="mill_flat",
        stl=tmp_path / "stock.stl" if include_stl else None,
    )
    observed = []
    imports = []
    window = SimpleNamespace(
        _document_reload_busy=lambda: False,
        _document_index_for_path=lambda _path: None,
        loadFile=lambda _path, **_kwargs: True,
        autoUpdateTimer=SimpleNamespace(stop=lambda: None),
        millingTools=tools,
        importStl=imports.append,
        latheMode=False,
        isMinimized=lambda: False,
        raise_=lambda: None,
        activateWindow=lambda: None,
        ensure_simulation_ready=lambda turning: observed.append((turning, tools["T1"].copy())),
    )
    application._start_cli_simulation(window, tmp_path / "program.nc", "fanuc_mill", bundle)
    assert imports == ([str(bundle.stl)] if include_stl else [])
    assert list(tools) == ["T1"]
    assert observed[0][0] is False
    assert observed[0][1]["diameter"] == diameter
    assert observed[0][1]["type"] == "mill_flat"


@pytest.mark.parametrize("include_stl", [False, True])
def test_read_simulation_bundle_with_optional_stl(tmp_path, include_stl):

    (tmp_path / "program.nc").write_text("G21\nG54\nT1 M6\nM30\n", encoding="ascii")
    data = {
        "version": 1,
        "units": "mm",
        "nc": "program.nc",
        "stock": dict(zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), (-5, 105, -5, 105, -10, 0))),
        "tool": {"number": 1, "diameter": 10, "type": "mill_flat"},
        "coordinates": {"wcs": "G54", "x": 0, "y": 0, "z": 0},
    }
    if include_stl:
        data["stl"] = "stock.stl"
        (tmp_path / "stock.stl").write_bytes(b"reference model")
    manifest = tmp_path / "simulation.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    bundle = read_bundle(manifest)
    assert bundle.stl == (tmp_path / "stock.stl" if include_stl else None)
    assert bundle.tool_number == 1 and bundle.tool_diameter == 10
    assert bundle.bounds == (-5, 105, -5, 105, -10, 0)


def test_run_forwards_simulation_without_creating_another_window(monkeypatch, tmp_path):
    forwarded = []
    monkeypatch.setattr(application, "QApplication", lambda _argv: object())
    monkeypatch.setattr(application, "forward_simulation", lambda *args: forwarded.append(args) or True)

    def unexpected_window():
        pytest.fail("A forwarded simulation must not create a second window")

    monkeypatch.setattr(application, "MainWindow", unexpected_window)
    path = tmp_path / "program.nc"
    assert application.run(startup_file=path, simulate=True, language="fanuc_mill") == 0
    assert forwarded == [(path, "fanuc_mill", None)]


def test_simulation_waits_for_reload_dialog_instead_of_losing_request(monkeypatch, tmp_path):
    callbacks = []
    monkeypatch.setattr(
        application, "QTimer", SimpleNamespace(singleShot=lambda _delay, callback: callbacks.append(callback))
    )
    loads = []
    window = SimpleNamespace(
        _document_reload_busy=lambda: True,
        _document_index_for_path=lambda _path: None,
        loadFile=lambda path, **_kwargs: loads.append(path) or False,
    )
    path = tmp_path / "program.nc"
    application._start_cli_simulation(window, path, "fanuc_mill")
    assert not loads
    assert len(callbacks) == 1
    window._document_reload_busy = lambda: False
    callbacks[0]()
    assert loads == [str(path)]
