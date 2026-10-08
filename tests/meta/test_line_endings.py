"""Repository normalization preserves file content, binary assets and ignored outputs."""

import subprocess

from scripts.check_line_endings import check_repository


def _git(root, *arguments):
    return subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True).stdout


def test_repository_line_endings_check_fix_and_idempotence(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / ".gitattributes").write_bytes(b"* text=auto eol=crlf\n*.sh text eol=lf\n*.asset binary\n")
    (tmp_path / ".gitignore").write_bytes(b"ignored/\n")
    tracked = tmp_path / "tracked.txt"
    tracked.write_bytes(b"original\n")
    _git(tmp_path, "add", ".")
    original_index = _git(tmp_path, "show", ":tracked.txt")
    tracked.write_bytes(b"dirty\r\nsecond\nthird\rno-final-newline")
    bare_cr = tmp_path / "bare-cr.txt"
    bare_cr.write_bytes(b"one\rtwo\r")
    unicode_file = tmp_path / "файл.txt"
    unicode_file.write_bytes(b"\xef\xbb\xbf" + "Текст\n".encode("utf-8"))
    legacy_encoding = tmp_path / "legacy.nc"
    legacy_encoding.write_bytes("Комментарий\nG0 X1\n".encode("cp1251"))
    shell = tmp_path / "run.sh"
    shell.write_bytes(b"#!/bin/bash\r\necho test\r\n")
    extensionless = tmp_path / "start"
    extensionless.write_bytes(b"#!/usr/bin/env -S bash -e\r\necho test\r\n")
    binary = tmp_path / "data.asset"
    binary.write_bytes(b"binary format without NUL\r\nunchanged\n")
    nul_file = tmp_path / "bytes.dat"
    nul_file.write_bytes(b"\0binary\n")
    ignored = tmp_path / "ignored" / "output.txt"
    ignored.parent.mkdir()
    ignored.write_bytes(b"leave generated output\n")
    contents = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file() and ".git" not in path.parts}

    assert check_repository(tmp_path) == 1
    assert all(path.read_bytes() == content for path, content in contents.items())
    assert check_repository(tmp_path, fix=True) == 0
    assert tracked.read_bytes() == b"dirty\r\nsecond\r\nthird\r\nno-final-newline"
    assert bare_cr.read_bytes() == b"one\r\ntwo\r\n"
    assert unicode_file.read_bytes() == b"\xef\xbb\xbf" + "Текст\r\n".encode("utf-8")
    assert legacy_encoding.read_bytes() == "Комментарий\r\nG0 X1\r\n".encode("cp1251")
    assert shell.read_bytes() == b"#!/bin/bash\necho test\n"
    assert extensionless.read_bytes() == b"#!/usr/bin/env -S bash -e\necho test\n"
    for path in (binary, nul_file, ignored):
        assert path.read_bytes() == contents[path]
    assert _git(tmp_path, "show", ":tracked.txt") == original_index
    assert check_repository(tmp_path) == 0
    normalized = {path: path.read_bytes() for path in contents}
    assert check_repository(tmp_path, fix=True) == 0
    assert all(path.read_bytes() == content for path, content in normalized.items())
