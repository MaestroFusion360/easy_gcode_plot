"""User copies, isolated recovery and lossless compatibility with old overrides."""

import json

import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.milling.kinematics import (
    CATALOG_PATH,
    InvalidKinematicsProfile,
    legacy_profile_id,
    load_catalog,
    profile_document,
    save_profile_override,
    user_catalog_path,
)


@pytest.mark.parametrize(
    "damaged", [b"{broken json\n", b"\xff\xfeinvalid encoding", b'{"schema_version": 2, "profiles": []}']
)
def test_recovery_preserves_damaged_bytes_and_installed_catalog(damaged):
    original = CATALOG_PATH.read_bytes()
    path = user_catalog_path()
    path.write_bytes(damaged)
    with pytest.raises(InvalidKinematicsProfile):
        load_catalog(ignore_user_errors=False)
    result = execute("G90 G0 B90\nG0 Z10\nM30", language="fanuc_mill", kinematics="4ax_table_b")
    assert result.ok and result.complete, result.diagnostics
    edited = profile_document("4ax_table_b")
    edited["id"] = "user_b"
    edited["table"][0]["axis"] = [0, -1, 0]
    assert path.read_bytes() == damaged
    save_profile_override("user_b", edited)
    assert load_catalog()["user_b"].table_rotary_axes[0].axis == (0, -1, 0)
    backups = list(path.parent.glob("rotary_profiles.json.invalid-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == damaged
    assert CATALOG_PATH.read_bytes() == original


def test_builtin_cannot_be_overwritten_even_during_recovery():
    path = user_catalog_path()
    path.write_text("{broken", encoding="utf-8")
    edited = profile_document("4ax_table_b")
    with pytest.raises(InvalidKinematicsProfile, match="read-only"):
        save_profile_override(edited["id"], edited)
    assert path.read_bytes() == b"{broken"
    assert not list(path.parent.glob("*.bak"))


def test_legacy_overrides_are_user_copies_and_bad_entries_are_isolated():
    edited = profile_document("4ax_table_b")
    edited["table"][0]["axis"] = [0, -1, 0]
    path = user_catalog_path()
    path.write_text(json.dumps({"schema_version": 1, "profiles": [edited, {"id": "broken"}]}), encoding="utf-8")
    original = path.read_bytes()
    catalog = load_catalog()
    migrated = legacy_profile_id("4ax_table_b")
    assert catalog["4ax_table_b"].table_rotary_axes[0].axis == (0, 1, 0)
    assert catalog[migrated].table_rotary_axes[0].axis == (0, -1, 0)
    assert path.read_bytes() == original
    edited = profile_document(migrated)
    edited["name"] = "Renamed legacy copy"
    save_profile_override(migrated, edited)
    assert profile_document(migrated) == edited
    assert next(path.parent.glob("*.bak")).read_bytes() == original
    result = execute("G90 G0 B90\nG0 Z10\nM30", language="fanuc_mill", kinematics=migrated)
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_x == pytest.approx(-10)


def test_invalid_edit_does_not_replace_or_back_up_damaged_file():
    path = user_catalog_path()
    path.write_text("{broken", encoding="utf-8")
    edited = profile_document("4ax_table_b")
    edited["id"] = "user_b"
    edited["table"][0]["axis"] = [0, 0, 0]
    with pytest.raises(InvalidKinematicsProfile):
        save_profile_override("user_b", edited)
    assert path.read_bytes() == b"{broken"
    assert not list(path.parent.glob("*.bak"))


def test_disabled_copy_stays_disabled_and_other_copies_survive_edits():
    first = profile_document("4ax_head_b")
    first["id"] = "user_head"
    save_profile_override(first["id"], first)
    second = profile_document("4ax_table_b")
    second["id"] = "user_table"
    save_profile_override(second["id"], second)
    first["name"] = "Renamed head"
    save_profile_override(first["id"], first)
    assert not load_catalog()[first["id"]].enabled
    assert profile_document(second["id"]) == second
    assert not list(user_catalog_path().parent.glob("*.bak"))
