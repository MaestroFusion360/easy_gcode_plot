"""Managed user post profiles; validation and serialization stay in the exporter."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app import paths
from app.gcode.file_io import atomic_export
from app.gcode.post_profiles import load_post_profile

BUILTIN_LABELS = {
    "fanuc_mill": "FANUC milling",
    "sinumerik_iso": "SINUMERIK 840D ISO-M (G291)",
    "sinumerik_840d": "SINUMERIK 840D native",
    "heidenhain_itnc530": "Heidenhain iTNC 530",
    "fanuc_mill_multiaxis": "FANUC milling (multi-axis)",
    "sinumerik_840d_multiaxis": "SINUMERIK 840D native (multi-axis)",
    "fanuc_lathe_a": "FANUC lathe A",
    "fanuc_lathe_b": "FANUC lathe B",
}


@dataclass(frozen=True)
class UserPostProfile:
    path: str
    name: str
    machine: str | None
    error: str = ""


class PostProfileLibrary:
    """Keep imported originals and bundled posts outside all write operations."""

    def __init__(self, directory=None):
        self.directory = Path(directory or Path(paths.config_dir()) / "post-profiles").resolve()

    def managed_path(self, path):
        candidate = Path(path).resolve()
        if candidate.parent != self.directory or candidate.suffix.lower() != ".json":
            raise ValueError("Only profiles in the user post-profile directory can be changed")
        return candidate

    def list_profiles(self):
        profiles = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                self.managed_path(path)
                profile = self.load(path)
                profiles.append(UserPostProfile(str(path), self.name(profile, path.stem), profile["machine"]))
            except (OSError, ValueError) as exc:
                profiles.append(UserPostProfile(str(path), path.stem, None, str(exc)))
        return sorted(profiles, key=lambda item: (item.name.casefold(), item.path))

    @staticmethod
    def name(profile, fallback):
        return str(profile.get("name") or profile.get("id") or fallback)

    @staticmethod
    def load(target):
        try:
            return load_post_profile(str(target))
        except (KeyError, TypeError, UnicodeError) as exc:
            raise ValueError(f"Invalid post profile: {exc}") from exc

    def save(self, profile, path=None):
        target = self.managed_path(path) if path else self.directory / f"{uuid4().hex}.json"
        text = json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + "\n"

        def write(temporary):
            temporary.write_text(text, encoding="utf-8")
            self.load(temporary)

        atomic_export(target, write)
        return str(target)

    def validate(self, profile):
        with tempfile.TemporaryDirectory(prefix="easy-gcode-post-") as directory:
            temporary = Path(directory) / "profile.json"
            temporary.write_text(json.dumps(profile, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            return self.load(temporary)

    def import_profile(self, source, *, machine=None):
        profile = self.load(source)
        if machine is not None and profile["machine"] != machine:
            raise ValueError(f"This profile is for {profile['machine']}; select a {machine} profile")
        return self.save(profile)

    def duplicate(self, source, name):
        profile = self.load(source)
        # id participates in controller-specific serialization; rename only name.
        profile["name"] = self._valid_name(name)
        return self.save(profile)

    def rename(self, path, name):
        path = self.managed_path(path)
        profile = self.load(path)
        profile["name"] = self._valid_name(name)
        return self.save(profile, path)

    def remove(self, path):
        self.managed_path(path).unlink()

    @staticmethod
    def _valid_name(name):
        name = str(name).strip()
        if not name:
            raise ValueError("Profile name must not be empty")
        return name
