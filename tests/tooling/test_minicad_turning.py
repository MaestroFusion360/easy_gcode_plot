"""Turning manifests initialize the existing stock replay with strict integrity."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from app.integration.minicad_bundle import apply_bundle, read_bundle


def turning_payload(tmp_path):
    nc = b"%\nO1000\nG21 G18 G99 G54\nT0101\nM30\n%\n"
    (tmp_path / "program.nc").write_bytes(nc)
    return {
        "version": 2,
        "units": "mm",
        "dialect": "fanuc_turn",
        "nc": "program.nc",
        "stock": {"xmin": -25, "xmax": 25, "ymin": -25, "ymax": 25, "zmin": -70, "zmax": 0},
        "turningStock": {"outerDiameter": 50, "innerDiameter": 6, "length": 70, "frontZ": 0},
        "coordinates": {"wcs": "G54", "x": 0, "y": 0, "z": 0},
        "tools": [
            {
                "number": 101,
                "name": "Drill",
                "h": 0,
                "d": 0,
                "type": "drill",
                "diameter": 10,
                "length": 50,
                "tipAngle": 118,
            }
        ],
        "sha256": {"program.nc": hashlib.sha256(nc).hexdigest()},
    }


def load(tmp_path, data):
    manifest = tmp_path / "simulation.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    return read_bundle(manifest)


def test_turning_bundle_uses_cylinder_and_turning_tools_only(tmp_path):
    bundle = load(tmp_path, turning_payload(tmp_path))
    assert bundle.dialect == "fanuc_turn" and bundle.turning_stock == (50, 6, 70, 0)
    window = SimpleNamespace(millingTools={"untouched": True})
    apply_bundle(window, bundle)
    assert window.stockConfigured and window.stockEnabled
    assert window.turnStockInnerDiameter == 6 and window.turnStockLength == 70
    assert window.tools["T0101"]["diameter"] == 10
    assert window.millingTools == {"untouched": True}


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["turningStock"].update(innerDiameter=50),
        lambda d: d["stock"].update(zmin=-71),
        lambda d: d["tools"].append(d["tools"][0]),
        lambda d: d["sha256"].update({"program.nc": "0" * 64}),
        lambda d: d["tools"][0].update(diameter=-1),
        lambda d: d.update(dialect="fanuc_mill"),
    ],
)
def test_invalid_turning_bundle_is_rejected(tmp_path, change):
    data = turning_payload(tmp_path)
    change(data)
    with pytest.raises(ValueError):
        load(tmp_path, data)
