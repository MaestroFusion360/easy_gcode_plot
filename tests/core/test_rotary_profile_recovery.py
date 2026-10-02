"""Strict core loading and editor recovery of malformed user overrides."""

import json

import pytest

from app.gcode.kernel.milling.kinematics import (
    CATALOG_PATH,
    InvalidKinematicsProfile,
    load_catalog,
    profile_document,
    save_profile_override,
    user_catalog_path,
)


@pytest.mark.parametrize(
    "damaged",
    [
        b"{broken json\n",
        b"\xff\xfeinvalid encoding",
        b'{"schema_version": 2, "profiles": []}',
        b'{"schema_version": 1, "profiles": [{"id": "4ax_table_b"}]}',
        b'{"schema_version": 1, "profiles": [{"id":"unknown","name":"Unknown","enabled":true,'
        b'"table":[{"address":"B","axis":[0,1,0]}],"head":[]}]}',
    ],
)
def test_editor_recovers_builtin_and_preserves_damaged_bytes(damaged):
    original = CATALOG_PATH.read_bytes()
    path = user_catalog_path()
    path.write_bytes(damaged)
    with pytest.raises(InvalidKinematicsProfile):
        load_catalog()
    edited = profile_document("4ax_table_b")
    assert edited["id"] == "4ax_table_b"
    assert path.read_bytes() == damaged
    edited["table"][0]["axis"] = [0, -1, 0]
    save_profile_override("4ax_table_b", edited)
    assert load_catalog()["4ax_table_b"].table_rotary_axes[0].axis == (0, -1, 0)
    backups = list(path.parent.glob("rotary_profiles.json.invalid-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == damaged
    assert CATALOG_PATH.read_bytes() == original


def test_invalid_editor_input_does_not_replace_or_back_up_damaged_file():
    path = user_catalog_path()
    path.write_text("{broken", encoding="utf-8")
    edited = profile_document("4ax_table_b")
    edited["table"][0]["axis"] = [0, 0, 0]
    with pytest.raises(InvalidKinematicsProfile):
        save_profile_override("4ax_table_b", edited)
    assert path.read_text(encoding="utf-8") == "{broken"
    assert not list(path.parent.glob("*.bak"))


def test_editing_valid_profile_preserves_other_overrides_and_creates_no_backup():
    first = profile_document("4ax_table_a")
    first["table"][0]["axis"] = [-1, 0, 0]
    save_profile_override("4ax_table_a", first)
    second = profile_document("4ax_table_b")
    second["name"] = "Edited B table"
    save_profile_override("4ax_table_b", second)
    assert profile_document("4ax_table_a") == first
    assert profile_document("4ax_table_b") == second
    document = json.loads(user_catalog_path().read_text(encoding="utf-8"))
    assert len(document["profiles"]) == 2
    assert not list(user_catalog_path().parent.glob("*.bak"))


def test_unknown_profile_cannot_be_created_during_recovery():
    path = user_catalog_path()
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(InvalidKinematicsProfile, match="Unknown profile"):
        profile_document("unknown")
    with pytest.raises(InvalidKinematicsProfile, match="Unknown profile"):
        save_profile_override("unknown", {"id": "unknown"})
    assert path.read_text(encoding="utf-8") == "{broken"
