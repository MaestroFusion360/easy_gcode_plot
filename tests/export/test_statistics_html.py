"""Statistics export shares measurements with Qt without embedding the NC trace."""

import json

import pytest

from app.cli import main
from app.gcode.kernel import execute
from app.gcode.statistics_report import LABELS, statistics_html, write_statistics_html
from app.gcode.trace_tools import trace_statistics


def test_portable_statistics_are_escaped_and_contain_all_tool_sections():
    result = execute("G21 G90\nT1 M6\nG1 X25.4 F25.4\nT2 M6\nG1 X50.8\nM30", language="fanuc_mill")
    report = statistics_html(trace_statistics(result), LABELS, inches=True, title="<script>bad</script>", portable=True)
    assert "<script>bad</script>" not in report
    assert "&lt;script&gt;bad&lt;/script&gt;" in report
    assert "Tool T1" in report and "Tool T2" in report
    assert "<select" in report
    assert "2.000 in" in report
    assert "G1 X25.4" not in report


def test_statistics_html_cannot_replace_input(tmp_path):
    path = tmp_path / "input.nc"
    path.write_text("M30")
    with pytest.raises(ValueError, match="source program"):
        write_statistics_html(path, "report", source_path=path)
    assert path.read_text() == "M30"


def test_each_tool_bounds_include_arc_extrema_and_only_its_movements():
    result = execute(
        "G21 G90 G17\nT1 M6\nG0 X10 Y0\nG3 X-10 Y0 I-10 J0 F100\nT2 M6\nG0 X50 Y50 Z20\nG1 X60\nM30",
        language="fanuc_mill",
    )
    assert result.ok, result.diagnostics
    stats = trace_statistics(result)
    assert stats["per_tool"]["T1"]["bounds"] == ((-10, 10), (0, 10), (0, 0))
    assert stats["per_tool"]["T2"]["bounds"] == ((-10, 60), (0, 50), (0, 20))
    assert stats["bounds"] == ((-10, 60), (0, 50), (0, 20))
    report = statistics_html(stats, LABELS, selected="T1")
    assert "-10.000 mm / 10.000 mm" in report
    assert "-10.000 mm / 60.000 mm" not in report
    assert "X min / max" in report and "Y min / max" in report and "Z min / max" in report
    assert "Z min:" not in report


def test_cli_analyze_exports_html_for_partial_execution(tmp_path):
    source, output = tmp_path / "input.nc", tmp_path / "statistics.html"
    source.write_text("T1\nG1 X10 F100\nG2 X100 Z100 R1\nM30")
    assert main(["analyze", str(source), "--html", str(output)]) == 2
    report = output.read_text(encoding="utf-8")
    assert "PARTIAL / INVALID" in report
    assert "UNKNOWN" in report
    assert "<select" in report


@pytest.mark.parametrize("suffix", [".mpf", ".MPF", ".spf", ".SPF"])
def test_cli_analyze_detects_sinumerik_file_without_lang(tmp_path, capsys, suffix):
    source, output = tmp_path / ("input" + suffix), tmp_path / "statistics.html"
    source.write_text("G17 G710 G90 G94\nT1 M6\nG0 X10 Y0\nG3 X0 Y10 CR=10 F100\nM30\n")
    assert main(["analyze", str(source), "--html", str(output)]) == 0
    terminal = capsys.readouterr().out
    assert "Result: CLEAN" in terminal
    assert "Motions: 2" in terminal
    assert "UNSUPPORTED_SINUMERIK_ISO_T" not in terminal
    report = output.read_text(encoding="utf-8")
    assert "Tool T1" in report
    assert "25.708 mm" in report


def test_cli_explicit_turning_mode_is_not_overridden_by_extension(tmp_path, capsys):
    source = tmp_path / "input.mpf"
    source.write_text("G0 X10\nM30\n")
    assert main(["analyze", str(source), "--lang", "fanuc_turn"]) == 2
    assert "UNSUPPORTED_SINUMERIK_ISO_T" in capsys.readouterr().out


@pytest.mark.parametrize(
    "language, program, projection",
    [
        ("fanuc_mill", "G17 G90\nT1 M6\nG0 X10 Y0\nG3 X0 Y10 I-10 J0 F100\nM30", "XY"),
        ("fanuc_turn", "G18 G90\nT0101\nG0 X20 Z0\nG2 X10 Z-5 R5 F100\nM30", "XZ"),
    ],
)
def test_svg_projection_is_only_in_portable_report(language, program, projection):
    import xml.etree.ElementTree as ET  # pylint: disable=import-outside-toplevel

    result = execute(program, language=language)
    assert result.ok, result.diagnostics
    stats = trace_statistics(result)
    assert "<svg" not in statistics_html(stats, LABELS, execution=result)
    report = statistics_html(stats, LABELS, portable=True, execution=result)
    svg = report[report.index("<svg") : report.index("</svg>") + len("</svg>")]
    root = ET.fromstring(svg)
    assert projection in root.attrib["aria-label"]
    paths = list(root.iter("{http://www.w3.org/2000/svg}path"))
    assert {path.attrib["class"] for path in paths} == {"svg-cut", "svg-rapid"}
    # A quarter-circle must retain intermediate points, not become a chord.
    assert next(p for p in paths if p.attrib["class"] == "svg-cut").attrib["d"].count("L") >= 8
    assert report.index("<svg") > report.index("</section>")


def test_svg_large_trace_retains_every_motion_without_bridging():
    from dataclasses import replace  # pylint: disable=import-outside-toplevel

    result = execute("G1 X1 F100", language="fanuc_mill")
    count = 10_000
    result = replace(result, motions=result.motions * count)
    report = statistics_html(trace_statistics(result), LABELS, portable=True, execution=result)
    svg = report[report.index("<svg") : report.index("</svg>")]
    assert svg.count("M") == count
    assert svg.count("L") == count
    assert "Sampled preview" not in report
    assert len(report) < 600_000


def test_svg_uses_supplied_print_geometry_without_resampling():
    from dataclasses import replace  # pylint: disable=import-outside-toplevel

    result = execute("G17\nG0 X10 Y0\nG3 X10 Y0 I-10 J0 F100", language="fanuc_mill")
    result = replace(result, motions=(result.motions[-1],))
    segments = [((10, 0, 0), (7, 7, 0), 3, None), ((7, 7, 0), (0, 10, 0), 3, None)]
    report = statistics_html(trace_statistics(result), LABELS, portable=True, execution=result, plot_segments=segments)
    svg = report[report.index("<svg") : report.index("</svg>")]
    assert svg.count("L") == 2
    assert 'stroke="#176e54"' in svg


def test_batch_html_uses_single_file_api_and_detects_each_container(tmp_path, monkeypatch):
    from app.gcode import batch  # pylint: disable=import-outside-toplevel

    root = tmp_path / "programs"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "part.nc").write_text("T0101\nG18\nG1 X20 Z-10 F100\nM30\n")
    (root / "part.MPF").write_text("G17 G710\nT1 M6\nG0 X10\nG3 X0 Y10 CR=10 F100\nM30\n")
    (nested / "part.spf").write_text("G17 G710\nG1 X10 F100\nG2 X100 Y100 CR=1\nM30\n")
    html_dir, json_dir = tmp_path / "html", tmp_path / "summary"
    calls = []
    original = batch.analyze_file

    def captured(path, **kwargs):
        calls.append(path.name)
        return original(path, **kwargs)

    monkeypatch.setattr(batch, "analyze_file", captured)
    assert main(["batch", str(root), "--html", str(html_dir), "-o", str(json_dir), "--inches"]) == 2
    assert sorted(calls) == ["part.MPF", "part.nc", "part.spf"]
    report = json.loads((json_dir / "batch_report.json").read_text(encoding="utf-8"))
    assert report["language"] == "auto"
    assert report["summary"]["files_total"] == 3
    for row in report["files"]:
        source = root / row["path"]
        assert row["language"] == ("fanuc_turn" if source.suffix == ".nc" else "fanuc_mill")
        batch_html = html_dir / (row["path"] + ".html")
        assert batch_html.exists()
        assert row["html_report"] == str(batch_html.resolve())
        single_html = tmp_path / "single.html"
        expected_status = 2 if row["status"] == "ERRORS" else 0
        assert main(["analyze", str(source), "--html", str(single_html), "--inches"]) == expected_status
        assert batch_html.read_bytes() == single_html.read_bytes()


def test_batch_html_write_error_does_not_abort_other_files(tmp_path):
    root, output = tmp_path / "source", tmp_path / "html"
    root.mkdir()
    output.mkdir()
    (root / "a.nc").write_text("G1 X1 F100\nM30\n")
    (root / "b.nc").write_text("G1 X2 F100\nM30\n")
    (output / "a.nc.html").mkdir()
    summary = tmp_path / "summary"
    assert main(["batch", str(root), "--html", str(output), "-o", str(summary)]) == 2
    report = json.loads((summary / "batch_report.json").read_text(encoding="utf-8"))
    assert report["files"][0]["html_report"] is None
    assert report["files"][0]["diagnostics"][-1]["code"] == "HTML_REPORT_WRITE_ERROR"
    assert report["files"][1]["status"] == "CLEAN"
    assert (output / "b.nc.html").exists()
