"""Adding a controller catalog must not reset existing user snippets."""

import pkgutil

from app import gcode
from app.gcode.snippets import snippets as snippets_module
from app.gcode.snippets.snippet_defaults import LANGUAGES, default_snippets
from app.gcode.snippets.snippets import SnippetLibrary


def test_snippets_are_discoverable_without_namespace_packages():
    packages = {module.name for module in pkgutil.walk_packages(gcode.__path__, "app.gcode.") if module.ispkg}
    assert {"app.gcode.snippets", "app.gcode.snippets.snippet_catalog"} <= packages


def test_new_type_b_catalog_is_seeded_without_resetting_existing_catalogs(tmp_path, monkeypatch):
    path = str(tmp_path / "snippets.db")
    with monkeypatch.context() as patch:
        patch.setattr(snippets_module, "LANGUAGES", tuple(item for item in LANGUAGES if item[0] != "fanuc_b_turn"))
        with SnippetLibrary(path) as library:
            library.ensure_defaults()
            records = {item.name: item for item in library.list_snippets("fanuc_turn")}
            library.update_body(records["Program Start"].id, "USER PROGRAM START")
            library.delete(records["Comment"].id)
            previous = library.list_snippets("fanuc_turn")

    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        assert library.list_snippets("fanuc_turn") == previous
        added = library.list_snippets("fanuc_b_turn")
        assert [(item.name, item.body) for item in added] == list(default_snippets("fanuc_b_turn"))
        library.delete(added[0].id)
        retained = library.list_snippets("fanuc_b_turn")

    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        assert library.list_snippets("fanuc_turn") == previous
        assert library.list_snippets("fanuc_b_turn") == retained
