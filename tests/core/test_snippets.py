"""SQLite persistence contracts for reusable G-code snippets."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

import pytest

from app.gcode.kernel import execute
from app.gcode.snippets import snippets as snippets_module
from app.gcode.snippets.snippet_defaults import LANGUAGES, default_snippets
from app.gcode.snippets.snippet_templates import TemplateContext, TemplateError, render
from app.gcode.snippets.snippets import SnippetLibrary


def test_refresh_defaults_restores_standard_text_and_preserves_custom_records_images_and_order(tmp_path, monkeypatch):
    path = str(tmp_path / "snippets.db")
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        original = {item.name: item for item in library.list_snippets()}
        other_language = library.list_snippets("heidenhain")
        library.update_body(original["Toolchange"].id, "USER TOOLCHANGE")
        library.rename(original["Program End"].id, "My program end")
        library.delete(original["Comment"].id)
        library.update_content(original["Circular Move"].id, original["Circular Move"].body, b"user picture")
        custom = library.add("My template", "USER TEXT")
        before = library.list_snippets()

    sources = {language: default_snippets(language) for language, _label in LANGUAGES}
    revised = tuple((name, body + "; revised\n") for name, body in sources["fanuc_mill"])
    sources["fanuc_mill"] = (*revised, ("New example", "NEW"))
    monkeypatch.setattr(snippets_module, "default_snippets", sources.__getitem__)
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        assert library.refresh_defaults("fanuc_mill", {"Circular Move": b"bundled", "Rapid Move": b"rapid"}) == (
            len(original) - 2,
            3,
        )
        after = library.list_snippets()
        by_name = {item.name: item for item in after}
        assert by_name["Program Start"].body.endswith("; revised\n")
        assert by_name["Toolchange"].body == dict(sources["fanuc_mill"])["Toolchange"]
        assert by_name["My program end"].id == original["Program End"].id
        assert by_name["Program End"].id != original["Program End"].id
        assert by_name["Comment"].body == dict(sources["fanuc_mill"])["Comment"]
        assert by_name["My template"].id == custom.id and by_name["My template"].body == "USER TEXT"
        assert by_name["New example"].body == "NEW"
        assert [(item.id, item.sort_order) for item in after[: len(before)]] == [
            (item.id, item.sort_order) for item in before
        ]
        assert library.image(original["Circular Move"].id) == b"user picture"
        assert library.image(original["Rapid Move"].id) == b"rapid"
        assert library.list_snippets("heidenhain") == other_language
        assert library.refresh_defaults("fanuc_mill") == (0, 0)

    with SnippetLibrary(path) as library:
        assert library.refresh_defaults("fanuc_mill") == (0, 0)
        library.update_body(original["Program Start"].id, "USER START")
        sources["fanuc_mill"] = tuple((name, body + "; second revision\n") for name, body in sources["fanuc_mill"])
        library.refresh_defaults("fanuc_mill")
        records = {item.name: item for item in library.list_snippets()}
        assert records["Program Start"].body == dict(sources["fanuc_mill"])["Program Start"]
        assert records["My template"].body == "USER TEXT"
        assert records["Circular Move"].body.endswith("; second revision\n")


def test_refresh_defaults_rolls_back_text_and_restored_records_when_picture_write_fails(tmp_path):
    path = str(tmp_path / "snippets.db")
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        original = {item.name: item for item in library.list_snippets()}
        library.update_body(original["Program Start"].id, "USER START")
        library.delete(original["Comment"].id)
        before = library.list_snippets()
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TRIGGER reject_picture BEFORE INSERT ON snippet_images "
                "BEGIN SELECT RAISE(ABORT, 'picture write failed'); END"
            )
        with pytest.raises(sqlite3.IntegrityError, match="picture write failed"):
            library.refresh_defaults("fanuc_mill", {"Rapid Move": b"picture"})
        assert library.list_snippets() == before
        assert library.image(original["Rapid Move"].id) is None
        with sqlite3.connect(path) as connection:
            connection.execute("DROP TRIGGER reject_picture")
        library.refresh_defaults("fanuc_mill")
        restored = {item.name: item for item in library.list_snippets()}
        assert restored["Program Start"].body != "USER START"
        assert "Comment" in restored


def test_explicit_refresh_restores_standard_text_without_replacing_its_record(tmp_path):
    with SnippetLibrary(str(tmp_path / "snippets.db")) as library:
        custom = library.add("Program Start", "MY PROGRAM")
        library.ensure_defaults()
        assert library.refresh_defaults("fanuc_mill") == (1, 0)
        assert library.list_snippets()[0].id == custom.id
        assert library.list_snippets()[0].body == dict(default_snippets("fanuc_mill"))["Program Start"]


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


def test_bad_legacy_encoding_does_not_abort_valid_imports(tmp_path, caplog):
    directory = tmp_path / "snippets"
    directory.mkdir()
    (directory / "A.txt").write_text("G1 X1", encoding="utf-8")
    (directory / "B.txt").write_bytes(b"\xff")
    (directory / "C.txt").write_text("G1 X3", encoding="utf-8")
    (directory / ".order.json").write_bytes(b"\xff")
    database = tmp_path / "snippets.db"
    with SnippetLibrary(str(database)) as library:
        assert library.import_legacy_directory(directory) == 2
        assert [(record.name, record.body) for record in library.list_snippets()] == [("A", "G1 X1"), ("C", "G1 X3")]
    with SnippetLibrary(str(database)) as library:
        assert len(library.list_snippets()) == 2
    assert "B.txt" in caplog.text
    assert (directory / "B.txt").read_bytes() == b"\xff"


def _v1_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO meta VALUES ('schema_version', '1');
            INSERT INTO meta VALUES ('legacy_text_snippets_imported_v1', '1');
            CREATE TABLE snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                body TEXT NOT NULL, sort_order INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX idx_snippets_sort_order ON snippets(sort_order);
            INSERT INTO snippets VALUES (7, 'Program Start', 'CUSTOM #1=42', 0, 'created', 'updated');
            INSERT INTO snippets VALUES (12, 'My tool', 'T7 M6', 1, 'created2', 'updated2');
        """)


def test_v1_migration_preserves_ids_bodies_order_timestamps_and_import_marker(tmp_path):
    path = tmp_path / "snippets.db"
    _v1_database(path)
    with SnippetLibrary(str(path)) as library:
        before = library.list_snippets()
        assert [(r.id, r.name, r.body, r.sort_order, r.created_at, r.updated_at, r.language_id) for r in before] == [
            (7, "Program Start", "CUSTOM #1=42", 0, "created", "updated", "fanuc_mill"),
            (12, "My tool", "T7 M6", 1, "created2", "updated2", "fanuc_mill"),
        ]
        library.ensure_defaults()
        assert library.list_snippets()[:2] == before
        assert library.import_legacy_directory(tmp_path) == 0
        assert library.add("New").id > 12
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ("3",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()


def test_languages_have_independent_names_order_and_deletion(tmp_path):
    with SnippetLibrary(str(tmp_path / "snippets.db")) as library:
        assert library.list_languages() == list(LANGUAGES)
        a = library.add("Same", "A")
        b = library.add("Same", "B", "heidenhain")
        c = library.add("Other", "C", "heidenhain")
        with pytest.raises(sqlite3.IntegrityError):
            library.add("same", language_id="heidenhain")
        with pytest.raises(ValueError):
            library.reorder([a.id, b.id], "heidenhain")
        library.reorder([c.id, b.id], "heidenhain")
        library.delete(c.id)
        assert [(r.body, r.sort_order) for r in library.list_snippets("heidenhain")] == [("B", 0)]
        assert library.list_snippets() == [a]


def test_defaults_seed_once_and_remain_editable_and_deletable(tmp_path):
    path = str(tmp_path / "snippets.db")
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        for language_id, _ in LANGUAGES:
            assert [(r.name, r.body) for r in library.list_snippets(language_id)] == list(default_snippets(language_id))
        start, tool = library.list_snippets("heidenhain")[:2]
        library.update_body(start.id, "CUSTOM")
        library.delete(tool.id)
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        records = library.list_snippets("heidenhain")
        assert records[0].body == "CUSTOM"
        assert tool.id not in {r.id for r in records}
        assert len(library.list_snippets()) == len(default_snippets("fanuc_mill"))


def test_failed_migration_rolls_back_original_schema(tmp_path, monkeypatch):
    path = tmp_path / "snippets.db"
    _v1_database(path)
    monkeypatch.setattr(snippets_module, "_SNIPPETS_SCHEMA", "INVALID SQL")
    with pytest.raises(sqlite3.Error):
        SnippetLibrary(str(path))
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ("1",)
        assert connection.execute("SELECT id, body FROM snippets ORDER BY id").fetchall() == [
            (7, "CUSTOM #1=42"),
            (12, "T7 M6"),
        ]


@pytest.mark.parametrize("language_id", [key for key, _ in LANGUAGES])
def test_starter_fragments_execute_in_their_controller_language(language_id):
    templates = dict(default_snippets(language_id))
    operations = [name for name in templates if name not in {"Program Start", "Program End"}]
    for name in operations:
        result = _execute_template(language_id, name)
        if name in {"Drilling", "Circular Move"} or name.startswith(("Roughing", "Threading")):
            assert any(m.move != 0 for m in result.motions), (language_id, name)


def test_opening_library_preserves_edits_and_deletions(tmp_path):
    path = str(tmp_path / "snippets.db")
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        records = {record.name: record for record in library.list_snippets()}
        library.update_body(records["Program Start"].id, "USER PROGRAM")
        library.rename(records["Drilling"].id, "My drilling")
        library.delete(records["Rapid Move"].id)
        before = library.list_snippets()
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        assert library.list_snippets() == before


def test_defaults_change_only_on_explicit_refresh(tmp_path):
    path = str(tmp_path / "snippets.db")
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        original = library.list_snippets()[0]
        library.update_body(original.id, "USER PROGRAM")
        custom = library.add("Custom program", "G1 X42")
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        assert library.list_snippets()[0].body == "USER PROGRAM"
        library.refresh_defaults("fanuc_mill")
        restored = library.list_snippets()[0]
        assert (restored.id, restored.name, restored.sort_order, restored.created_at) == (
            original.id,
            original.name,
            original.sort_order,
            original.created_at,
        )
        assert restored.body == dict(default_snippets("fanuc_mill"))[original.name]
        assert library.list_snippets()[-1] == custom


def _template_setup(language_id, name):
    """Supply caller-owned positioning and profiles, keeping production snippets minimal."""
    setups = {
        "Roughing (G71)": "F0.25\nG0 X42 Z2\nN10 G0 X20\nG1 Z0\nZ-15\nX30 Z-20\nN20 X40\nG0 X42 Z2\n",
        "Roughing (CYCLE95)": (
            "F0.25\nG0 X42 Z2\nROUGH_START:\nG0 X20 Z0\nG1 Z-15\nX30 Z-20\nX40\nROUGH_END:\nG0 X42 Z2\n"
        ),
        "Threading (G76)": "G0 X24 Z2\n",
        "Threading (CYCLE97)": "G0 X30 Z5\n",
    }
    if name in {"Finishing (G70)", "Facing Roughing (G72)", "Pattern Roughing (G73)"}:
        return setups["Roughing (G71)"]
    if name in setups:
        return setups[name]
    if language_id == "heidenhain":
        if name in {"Circular Hole Pattern (CYCL DEF 220)", "Grid Hole Pattern (CYCL DEF 221)"}:
            # DEF-active patterns consume a previously defined machining cycle.
            return dict(default_snippets(language_id))["Drilling (CYCL DEF 200)"].removesuffix("CYCL CALL\n")
        return {"Circular Move": "L X+10 Y+0 Z+0 R0 FMAX\n", "Drilling": "L X+0 Y+0 Z+5 R0 FMAX\n"}.get(name, "")
    if language_id.endswith("turn"):
        return {"Circular Move": "G0 X20 Z0\n", "Drilling": "G0 Z5\nG0 X0\n"}.get(name, "")
    return {"Circular Move": "G0 X10 Y0 Z0\n", "Drilling": "G0 Z5\nG0 X0 Y0\n"}.get(name, "")


def _execute_template(language_id, name, *, values=None, **options):
    templates = dict(default_snippets(language_id))
    cycle_positions = "G0 X0 Y0\nMCALL\n" if language_id == "sinumerik_mill" and name == "Drilling" else ""
    context = TemplateContext(file=Path(__file__))
    source = "".join(
        render(part, values if part == templates[name] else None, context=context).text
        for part in (
            templates["Program Start"],
            templates["Toolchange"],
            _template_setup(language_id, name),
            templates[name],
            cycle_positions,
            templates["Program End"],
        )
    )
    if any(code in name for code in ("POCKET", "CYCLE90", "CYCL DEF 251", "CYCL DEF 252", "CYCL DEF 262")):
        options.setdefault("milling_tools", {"T1": {"type": "mill_flat", "diameter": 6.0, "length": 50.0}})
    options.setdefault("emulate_g28_home", True)
    if language_id == "fanuc_b_turn":
        options.setdefault("lathe_gcode_system", "B")
    result = execute(
        source,
        "fanuc_turn" if language_id.endswith("turn") else "fanuc_mill",
        source_dialect=language_id.split("_")[0],
        **options,
    )
    assert result.ok and result.complete, result.diagnostics
    return result


@pytest.mark.parametrize("language_id", [key for key, _ in LANGUAGES])
def test_circular_examples_are_quarter_circles_of_radius_ten(language_id):
    result = _execute_template(language_id, "Circular Move")
    arcs = [m.arc for m in result.motions if m.arc]
    assert len(arcs) == 1
    assert arcs[0].radius == pytest.approx(10)
    assert arcs[0].sweep == pytest.approx(math.pi / 2)
    assert arcs[0].plane == (18 if language_id.endswith("turn") else 17)


@pytest.mark.parametrize("language_id", ["sinumerik_mill", "sinumerik_turn"])
@pytest.mark.parametrize("solution_line", [False, True])
def test_cycle83_examples_have_constant_three_mm_infeed_and_full_retraction(language_id, solution_line):
    result = _execute_template(language_id, "Drilling", sinumerik_840d_sl=solution_line)
    cycle = [m for m in result.motions if m.source_kind == "cycle"]
    cuts = [m for m in cycle if m.move == 1 and m.end_z < m.start_z]
    assert [m.end_z for m in cuts] == pytest.approx([-3, -6, -9, -12, -15, -18, -20])
    for cut in cuts:
        position = cycle.index(cut)
        retract = cycle[position + 1]
        assert retract.move == 0 and retract.end_z == pytest.approx(5)
        assert cut.feed == (0.1 if language_id.endswith("turn") else 150)
        assert cut.feed_mode == ("per_revolution" if language_id.endswith("turn") else "per_minute")


def test_fanuc_lathe_drilling_is_axial_g74_with_three_mm_pecks():
    result = _execute_template("fanuc_turn", "Drilling")
    cycle = [m for m in result.motions if m.source_kind == "cycle"]
    cuts = [m for m in cycle if m.move == 1]
    assert [m.end_z for m in cuts] == pytest.approx([2, -1, -4, -7, -10, -13, -16, -19, -20])
    assert all(m.start_x == m.end_x == 0 for m in cycle)
    assert all(m.feed == 0.1 and m.feed_mode == "per_revolution" for m in cuts)
    assert cycle[-1].end_z == 5


def test_heidenhain_drilling_uses_numeric_retraction_feed():
    result = _execute_template("heidenhain", "Drilling")
    cycle = [m for m in result.motions if m.source_raw == "CYCL CALL"]
    cuts = [m for m in cycle if m.move == 1 and m.end_z < m.start_z]
    retracts = [m for m in cycle if m.move == 1 and m.end_z > m.start_z]
    assert [m.end_z for m in cuts] == pytest.approx([-3, -6, -9, -12, -15, -18, -20])
    assert len(retracts) == len(cuts)
    assert all(m.feed == 500 and m.end_z == 2 for m in retracts)


def test_cycle97_example_has_three_mm_approach_and_runout():
    result = _execute_template("sinumerik_turn", "Threading (CYCLE97)")
    cuts = [m for m in result.motions if m.threading]
    assert [m.end_x for m in cuts] == pytest.approx([19.5, 19, 18.5, 18])
    assert all(m.start_z == 3 and m.end_z == -23 and m.feed == 1.5 for m in cuts)


@pytest.mark.parametrize("language_id", ["fanuc_mill", "sinumerik_mill", "heidenhain"])
def test_milling_rapid_inserts_exactly_one_xyz_move(language_id):
    templates = dict(default_snippets(language_id))
    start = "L X+30 Y+20 Z-7 R0 FMAX\n" if language_id == "heidenhain" else "G0 X30 Y20 Z-7\n"
    prefix = templates["Program Start"] + templates["Toolchange"] + start
    source = prefix + templates["Rapid Move"] + templates["Program End"]
    source = render(source).text
    result = execute(source, "fanuc_mill", source_dialect=language_id.split("_")[0])
    assert result.ok and result.complete, result.diagnostics
    first_line = len(prefix.splitlines())
    end_line = first_line + len(templates["Rapid Move"].splitlines())
    moves = [m for m in result.motions if first_line <= m.source_block < end_line]
    assert len(templates["Rapid Move"].splitlines()) == 1
    assert [(m.end_x, m.end_y, m.end_z) for m in moves] == [(0, 0, 0)]


_MILLING_CYCLES = [
    (language, name)
    for language in ("fanuc_mill", "sinumerik_mill", "heidenhain")
    for name, _body in default_snippets(language)
    if any(marker in name for marker in ("(G", "(CYCLE", "(HOLES", "(POCKET", "(CYCL DEF")) and name != "Dwell (G4)"
]


@pytest.mark.parametrize("language_id,name", _MILLING_CYCLES)
def test_expanded_milling_cycles_produce_cutting_moves(language_id, name):
    result = _execute_template(language_id, name)
    assert any(m.move != 0 for m in result.motions), (language_id, name)
    assert not result.diagnostics


@pytest.mark.parametrize("cycle", [81, 82, 84, 85, 86, 87, 89])
def test_sinumerik_single_hole_templates_keep_xy_and_cancel_modal_cycle(cycle):
    templates = dict(default_snippets("sinumerik_mill"))
    body = next(body for name, body in templates.items() if name.endswith(f"(CYCLE{cycle})"))
    source = "G17 G90 G71 G94\nG0 X12 Y34 Z50\n" + render(body).text + "G0 X90 Y80\nM30\n"
    result = execute(source, "fanuc_mill", source_dialect="sinumerik")
    assert result.ok and result.complete, result.diagnostics
    cuts = [m for m in result.motions if m.move != 0]
    assert cuts
    assert all((m.start_x, m.start_y, m.end_x, m.end_y) == (12, 34, 12, 34) for m in cuts)
    assert min(m.end_z for m in cuts) == -20
    assert (result.motions[-1].end_x, result.motions[-1].end_y) == (90, 80)


@pytest.mark.parametrize("name", ["Circular Hole Pattern (CYCL DEF 220)", "Grid Hole Pattern (CYCL DEF 221)"])
def test_heidenhain_hole_patterns_call_the_previous_drilling_cycle_six_times(name):
    result = _execute_template("heidenhain", name)
    bottoms = [m for m in result.motions if m.move == 1 and m.end_z == -20]
    assert len(bottoms) == 6
    assert len({(m.end_x, m.end_y) for m in bottoms}) == 6


def test_back_boring_default_feeds_upward_and_rejects_depth_below_r_plane():
    body = dict(default_snippets("fanuc_mill"))["Back Boring (G87)"]
    with pytest.raises(TemplateError, match="Value out of range"):
        render(body, {"Z": "-25"})
    result = _execute_template("fanuc_mill", "Back Boring (G87)")
    cuts = [m for m in result.motions if m.move == 1]
    assert cuts
    assert any(m.start_z == -20 and m.end_z == -10 for m in cuts)


@pytest.mark.parametrize("name", ["Rectangular Pocket (POCKET3)", "Circular Pocket (POCKET4)"])
@pytest.mark.parametrize("mode", [1, 2, 11, 12])
def test_every_exposed_pocket_strategy_executes_with_the_templates_supplied_arguments(name, mode):
    result = _execute_template("sinumerik_mill", name, values={"VARI": str(mode)})
    assert any(m.move != 0 for m in result.motions)
    assert not result.diagnostics


@pytest.mark.parametrize(
    "name,mode",
    [
        ("Rectangular Pocket (POCKET3)", "21"),
        ("Rectangular Pocket (POCKET3)", "31"),
        ("Circular Pocket (POCKET4)", "21"),
    ],
)
def test_pocket_template_rejects_strategies_requiring_unexposed_entry_parameters(name, mode):
    source = dict(default_snippets("sinumerik_mill"))[name]
    with pytest.raises(TemplateError, match="Invalid choice"):
        render(source, {"VARI": mode})


@pytest.mark.parametrize("rpm", [250, 1250])
def test_cycle84_template_reuses_selected_speed_for_cutting_and_retraction(rpm):
    result = _execute_template("sinumerik_mill", "Rigid Tapping (CYCLE84)", values={"SST": str(rpm)})
    assert any(m.move != 0 for m in result.motions)
    assert not result.diagnostics
