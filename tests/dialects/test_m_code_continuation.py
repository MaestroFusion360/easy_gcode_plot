"""Unknown auxiliary M codes warn without interrupting trustworthy motion."""

import re
from dataclasses import replace

import pytest

from app.gcode.kernel import execute


@pytest.fixture(params=["fanuc_mill", "fanuc_turn_a", "fanuc_turn_b", "sinumerik_native", "sinumerik_iso"])
def controller(request):
    name = request.param
    if name.startswith("sinumerik"):
        return ("G291\n" if name.endswith("iso") else ""), {
            "language": "fanuc_mill",
            "source_dialect": "sinumerik",
        }
    if name.startswith("fanuc_turn"):
        return "", {"language": "fanuc_turn", "lathe_gcode_system": name[-1].upper()}
    return "", {"language": "fanuc_mill"}


@pytest.mark.parametrize("code", [50, 123, 999, 50.5])
@pytest.mark.parametrize("block", ["N80 M9 M{code}", "N80 G1 X2 Z2 F100 M{code} M9"])
def test_unknown_m_preserves_execution_and_known_words(controller, code, block):
    prefix, options = controller
    source = prefix + "G0 X1 Z1 M8\n" + block.format(code=code) + "\nG1 X3 Z3 F100\nM30\nG0 X99"
    result = execute(source, **options)
    baseline = execute(source.replace(f"M{code}", ""), **options)
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "UNSUPPORTED_M_CODE" and diagnostic.severity == "warning"
    assert diagnostic.status == "unverified"
    assert diagnostic.line == len(prefix.splitlines()) + 2 and diagnostic.raw == block.format(code=code)
    assert f"M{code}" in diagnostic.message
    assert [replace(motion, source_raw="") for motion in result.motions] == [
        replace(motion, source_raw="") for motion in baseline.motions
    ]
    assert result.motions[-1].end_x == result.motions[-1].end_z == 3
    assert result.signals == baseline.signals


@pytest.mark.parametrize("end", ["M2", "M30"])
@pytest.mark.parametrize("block", ["M50 {end}", "{end} M50"])
def test_unknown_m_does_not_override_program_end(controller, end, block):
    prefix, options = controller
    result = execute(prefix + "G0 X1 Z1\n" + block.format(end=end) + "\nG0 X99 Z99", **options)
    assert result.ok and result.complete and result.program_end == ("M02" if end == "M2" else end)
    assert len(result.motions) == 1
    assert all(d.severity == "warning" for d in result.diagnostics)


def test_m99_retains_controller_return_or_rejection_semantics(controller):
    prefix, options = controller
    result = execute(prefix + "G0 X1 Z1\nM99\nG0 X99 Z99", **options)
    assert len(result.motions) == 1
    if options.get("source_dialect") == "sinumerik":
        assert not result.ok and not result.complete
        assert result.diagnostics[-1].code == "UNSUPPORTED_SINUMERIK_M_CODE"
    else:
        assert result.ok and result.complete and result.program_end == "M99"


@pytest.mark.parametrize("code", ["M0", "M1"])
def test_machine_stop_signals_do_not_stop_trace_execution(controller, code):
    prefix, options = controller
    result = execute(prefix + "G0 X1 Z1\n" + code + "\nG1 X2 Z2 F100\nM30", **options)
    assert result.ok and result.complete and not result.diagnostics
    assert result.motions[-1].end_x == result.motions[-1].end_z == 2


@pytest.mark.parametrize("prefix", ["", "G291\n"])
@pytest.mark.parametrize("block", ["M98 P123", "T2 M98 P123", "M19", "M29", "M98 P123 M30"])
def test_unmodeled_sinumerik_m_codes_never_dispatch_fanuc_calls(prefix, block):
    result = execute(
        prefix + "G0 X1\n" + block + "\nG1 X2 F100\nM30", language="fanuc_mill", source_dialect="sinumerik"
    )
    assert result.ok and result.complete, result.diagnostics
    if not prefix and block == "M19":
        assert not result.diagnostics
        assert any(signal.kind == "spindle_orient" for signal in result.signals)
    else:
        assert result.diagnostics and all(
            d.code == "UNSUPPORTED_M_CODE" and d.severity == "warning" for d in result.diagnostics
        )
    assert not any(event.kind == "subprogram_start" for event in result.events)
    assert result.motions[-1].end_x == (1 if "M30" in block else 2)


def test_nx_fixture_unknown_m_codes_preserve_entire_toolpath(fixture_text):
    source = fixture_text("milling/sinumerik/text_NX.mpf")
    options = {"language": "fanuc_mill", "source_dialect": "sinumerik", "kinematics": "5ax_table_bc_angled"}
    result = execute(source, **options)
    baseline = execute(re.sub(r"\bM(?:50|27|29|51|65)\b", "", source), **options)

    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    assert baseline.ok and baseline.complete and baseline.program_end == "M30"
    assert len(result.motions) == 571
    assert [replace(motion, source_raw="") for motion in result.motions] == [
        replace(motion, source_raw="") for motion in baseline.motions
    ]
    assert all(d.severity == "warning" for d in result.diagnostics)
    m_warnings = [d for d in result.diagnostics if d.code == "UNSUPPORTED_M_CODE"]
    assert [(d.line, d.cnc_codes) for d in m_warnings] == [
        (8, ("M50",)),
        (640, ("M27",)),
        (641, ("M29",)),
        (641, ("M51",)),
        (641, ("M65",)),
    ]
    assert all(d.status == "unverified" and d.raw == source.splitlines()[d.line - 1] for d in m_warnings)
    assert [d.code for d in baseline.diagnostics] == ["UNMODELED_SINUMERIK_NATIVE"]
    assert any(motion.cycle_generated and motion.end_z == -6.1835 for motion in result.motions)
    final = result.motions[-1]
    assert (final.end_x, final.end_y, final.end_z) == (-365.0, 224.0, 610.0)
