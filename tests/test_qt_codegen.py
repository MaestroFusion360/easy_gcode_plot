from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = Path("app/ui/generated")
RESOURCE_DIR = Path("app/resources")


def _ui_mapping(root: Path) -> dict[Path, Path]:
    return {
        path: path.with_name("main_ui.py" if path.name == "main_window.ui" else f"{path.stem}.py")
        for path in sorted((root / UI_DIR).glob("*.ui"))
    }


def _generated_hashes(root: Path) -> dict[Path, str]:
    outputs = [*(_ui_mapping(root).values()), root / RESOURCE_DIR / "files_res.py"]
    return {path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest() for path in outputs}


def _create_codegen_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "project with spaces"
    ui_dir = target / UI_DIR
    icons_dir = target / RESOURCE_DIR / "icons"
    ui_dir.mkdir(parents=True)
    icons_dir.mkdir(parents=True)
    shutil.copy2(ROOT / RESOURCE_DIR / "icons/open.png", icons_dir / "open.png")
    (target / RESOURCE_DIR / "files_res.qrc").write_text(
        '<RCC><qresource prefix="resource"><file>icons/open.png</file></qresource></RCC>', encoding="utf-8"
    )
    (ui_dir / "main_window.ui").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0"><class>MainWindow</class><widget class="QMainWindow" name="MainWindow">
<property name="windowTitle"><string>Fixture Title</string></property>
<widget class="QWidget" name="centralwidget"><property name="windowIcon">
<iconset resource="../../resources/files_res.qrc">
<normaloff>:/resource/icons/open.png</normaloff></iconset></property></widget>
</widget><resources><include location="../../resources/files_res.qrc"/></resources><connections/></ui>
""",
        encoding="utf-8",
    )
    return target


def _generate(root: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ROOT / "scripts/generate-qt.ps1"),
        "-ProjectRoot",
        str(root),
        "-ToolProjectRoot",
        str(ROOT),
    ]
    return subprocess.run(command, cwd=root.parent, check=check, capture_output=True, text=True, timeout=180)


def test_qt_source_generated_mapping_and_resource_manifest_are_complete():
    mapping = _ui_mapping(ROOT)
    assert mapping
    assert ROOT / UI_DIR / "main_window.ui" in mapping
    assert mapping[ROOT / UI_DIR / "main_window.ui"] == ROOT / UI_DIR / "main_ui.py"
    assert all(target.is_file() for target in mapping.values())

    generated = {path for path in (ROOT / UI_DIR).glob("*.py") if path.name != "__init__.py"}
    assert generated == set(mapping.values()), "orphan or missing generated UI module"

    manifest_path = ROOT / RESOURCE_DIR / "files_res.qrc"
    manifest = ET.parse(manifest_path).getroot()
    entries = [node.text for node in manifest.findall(".//file")]
    assert len(entries) == len(set(entries)), "duplicate qrc entries"
    assert all((manifest_path.parent / entry).is_file() for entry in entries)

    aliases = {
        f":/{resource.attrib.get('prefix', '').strip('/')}/{node.attrib.get('alias', node.text)}"
        for resource in manifest.findall("qresource")
        for node in resource.findall("file")
    }
    for ui in mapping:
        ui_root = ET.parse(ui).getroot()
        includes = {node.attrib["location"] for node in ui_root.findall("./resources/include")}
        used = {node.text for node in ui_root.iter() if node.text and node.text.startswith(":/")}
        if used:
            assert "../../resources/files_res.qrc" in includes
            assert used <= aliases


def test_qt_generation_uses_pyside_only_as_dev_toolchain():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)
    assert any(dep.startswith("pyside6>=6.11,<7") for dep in project["dependency-groups"]["dev"])
    assert not any("pyside" in dep.lower() for dep in project["project"]["dependencies"])
    assert "--no-dev" in (ROOT / "scripts/build.ps1").read_text(encoding="utf-8")
    for generated in [*_ui_mapping(ROOT).values(), ROOT / RESOURCE_DIR / "files_res.py"]:
        content = generated.read_text(encoding="utf-8")
        assert "PySide6" not in content
        assert "PyQt6" in content
        assert not content.startswith("\ufeff")


@pytest.mark.skipif(sys.platform != "win32" or shutil.which("powershell") is None, reason="PowerShell workflow")
def test_batch_generation_tracks_changed_ui_and_resource_and_is_idempotent(tmp_path):
    project = _create_codegen_fixture(tmp_path)
    _generate(project)
    baseline = _generated_hashes(project)

    main_ui = project / UI_DIR / "main_window.ui"
    main_ui.write_text(
        main_ui.read_text(encoding="utf-8").replace("Fixture Title", "Changed Test Title", 1), encoding="utf-8"
    )
    icon = project / RESOURCE_DIR / "icons/open.png"
    icon.write_bytes(icon.read_bytes() + b"qt-codegen-test")
    _generate(project)
    changed = _generated_hashes(project)

    assert changed[Path("app/ui/generated/main_ui.py")] != baseline[Path("app/ui/generated/main_ui.py")]
    assert changed[Path("app/resources/files_res.py")] != baseline[Path("app/resources/files_res.py")]
    unrelated = set(changed) - {Path("app/ui/generated/main_ui.py"), Path("app/resources/files_res.py")}
    assert all(changed[path] == baseline[path] for path in unrelated)
    assert "from PyQt6" in (project / UI_DIR / "main_ui.py").read_text(encoding="utf-8")
    assert "import app.resources.files_res" in (project / UI_DIR / "main_ui.py").read_text(encoding="utf-8")

    _generate(project)
    assert _generated_hashes(project) == changed


@pytest.mark.skipif(sys.platform != "win32" or shutil.which("powershell") is None, reason="PowerShell workflow")
def test_broken_ui_fails_without_replacing_any_generated_target(tmp_path):
    project = _create_codegen_fixture(tmp_path)
    _generate(project)
    baseline = _generated_hashes(project)
    broken = project / UI_DIR / "main_window.ui"
    broken.write_text("<ui><broken>", encoding="utf-8")

    result = _generate(project, check=False)

    assert result.returncode != 0
    assert str(broken) in result.stdout + result.stderr
    assert _generated_hashes(project) == baseline


def test_generated_modules_import_and_qt_resource_is_registered():
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    code = (
        "from PyQt6.QtCore import QFile; "
        "import app.resources.files_res; "
        "import app.ui.generated.main_ui; "
        "assert QFile(':/resource/icons/open.png').exists()"
    )
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, check=True, timeout=30)
