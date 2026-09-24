from subprocess import CompletedProcess

from scripts import check_qt_sources


def _resource_module(*, timestamp: int, data: bytes = b"data") -> str:
    resource_struct = b"\0" * 14 + timestamp.to_bytes(8, "big")
    return f"""qt_resource_data = {data!r}
qt_resource_name = b'name'
qt_resource_struct = {resource_struct!r}

def qInitResources():
    QtCore.qRegisterResourceData(0x03, qt_resource_struct, qt_resource_name, qt_resource_data)
"""


def test_ui_check_detects_stale_generated_module(tmp_path, monkeypatch):
    ui_root = tmp_path / "app/ui/generated/dialogs"
    ui_root.mkdir(parents=True)
    (ui_root / "example.ui").write_text("<ui/>", encoding="utf-8")
    (ui_root / "example.py").write_text("old", encoding="utf-8")
    output = tmp_path / "output"
    (output / "dialogs").mkdir(parents=True)
    (output / "dialogs/example.py").write_text("new", encoding="utf-8")
    monkeypatch.setattr(check_qt_sources, "ROOT", tmp_path)
    monkeypatch.setattr(check_qt_sources, "UI_ROOT", ui_root.parent)
    monkeypatch.setattr(check_qt_sources.subprocess, "run", lambda *_args, **_kwargs: CompletedProcess([], 0))

    assert "differs from" in check_qt_sources.check_ui_modules(output)[0]


def test_translation_check_detects_placeholder_mismatch(tmp_path, monkeypatch):
    translations = tmp_path / "translations"
    translations.mkdir()
    (translations / "test.ts").write_text(
        "<TS><context><message><source>Value %1</source><translation>Значение</translation></message></context></TS>",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_qt_sources, "ROOT", tmp_path)
    monkeypatch.setattr(check_qt_sources.subprocess, "run", lambda *_args, **_kwargs: CompletedProcess([], 0))

    assert "placeholder mismatch" in check_qt_sources.check_translations(tmp_path)[0]


def test_resource_check_detects_stale_embedded_files(tmp_path, monkeypatch):
    resources = tmp_path / "app/resources"
    resources.mkdir(parents=True)
    (resources / "files_res.py").write_text("old icon bytes", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    (output / "files_res.py").write_text("new icon bytes", encoding="utf-8")
    monkeypatch.setattr(check_qt_sources, "ROOT", tmp_path)
    monkeypatch.setattr(check_qt_sources.subprocess, "run", lambda *_args, **_kwargs: CompletedProcess([], 0))

    assert "regenerate resources" in check_qt_sources.check_resources(output)[0]


def test_resource_check_ignores_rcc_v3_timestamps(tmp_path, monkeypatch):
    resources = tmp_path / "app/resources"
    resources.mkdir(parents=True)
    (resources / "files_res.py").write_text(_resource_module(timestamp=1), encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    (output / "files_res.py").write_text(_resource_module(timestamp=2), encoding="utf-8")
    monkeypatch.setattr(check_qt_sources, "ROOT", tmp_path)
    monkeypatch.setattr(check_qt_sources.subprocess, "run", lambda *_args, **_kwargs: CompletedProcess([], 0))

    assert check_qt_sources.check_resources(output) == []


def test_resource_check_still_detects_changed_payload(tmp_path, monkeypatch):
    resources = tmp_path / "app/resources"
    resources.mkdir(parents=True)
    (resources / "files_res.py").write_text(_resource_module(timestamp=1, data=b"old"), encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    (output / "files_res.py").write_text(_resource_module(timestamp=2, data=b"new"), encoding="utf-8")
    monkeypatch.setattr(check_qt_sources, "ROOT", tmp_path)
    monkeypatch.setattr(check_qt_sources.subprocess, "run", lambda *_args, **_kwargs: CompletedProcess([], 0))

    assert "regenerate resources" in check_qt_sources.check_resources(output)[0]
