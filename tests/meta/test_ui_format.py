from scripts.check_ui_format import check_file


def test_ui_format_checker_reports_whitespace_and_xml_errors(tmp_path):
    ui_file = tmp_path / "bad.ui"
    ui_file.write_text("<ui>\t<widget>  \n</ui>", encoding="utf-8")

    errors = check_file(ui_file)

    assert "missing final newline" in errors
    assert "line 1: tab character" in errors
    assert "line 1: trailing whitespace" in errors
    assert any(error.startswith("invalid XML:") for error in errors)
