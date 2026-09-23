"""SQLite persistence contracts for reusable G-code snippets."""

from __future__ import annotations

import json
import sqlite3

import pytest

from app.gcode.snippets import SnippetLibrary


def test_snippet_library_persists_crud_and_explicit_order(tmp_path):
    database = tmp_path / "snippets.db"
    with SnippetLibrary(str(database)) as library:
        first = library.add("Facing", "G1 X0")
        second = library.add("Drilling", "G81 Z-5")
        library.update_body(first.id, "G1 X10")
        library.rename(second.id, "Bolt circle")
        library.reorder([second.id, first.id])

    with SnippetLibrary(str(database)) as library:
        records = library.list_snippets()
        assert [(item.name, item.body) for item in records] == [
            ("Bolt circle", "G81 Z-5"),
            ("Facing", "G1 X10"),
        ]
        library.delete(second.id)
        assert [(item.name, item.sort_order) for item in library.list_snippets()] == [("Facing", 0)]


def test_snippet_names_are_case_insensitively_unique(tmp_path):
    with SnippetLibrary(str(tmp_path / "snippets.db")) as library:
        library.add("Probe")
        with pytest.raises(sqlite3.IntegrityError):
            library.add("probe")


def test_legacy_text_snippets_are_imported_once_in_saved_order(tmp_path):
    directory = tmp_path / "snippets"
    directory.mkdir()
    (directory / "A.txt").write_text("A body", encoding="utf-8")
    (directory / "B.txt").write_text("B body", encoding="utf-8")
    (directory / ".order.json").write_text(json.dumps(["B.txt", "A.txt"]), encoding="utf-8")

    with SnippetLibrary(str(tmp_path / "snippets.db")) as library:
        assert library.import_legacy_directory(directory) == 2
        assert [item.name for item in library.list_snippets()] == ["B", "A"]
        (directory / "C.txt").write_text("C body", encoding="utf-8")
        assert library.import_legacy_directory(directory) == 0
        assert [item.name for item in library.list_snippets()] == ["B", "A"]
