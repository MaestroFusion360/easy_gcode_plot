"""Real local-socket handoff to the existing simulation instance."""

import json
from threading import Thread
from uuid import uuid4

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app.integration.minicad_bundle import read_bundle
from app.integration.simulation_session import SimulationSession, forward_simulation


def test_repeated_simulation_requests_reuse_listener_and_read_new_tool(tmp_path):
    app = QApplication.instance() or QApplication([])
    name = "easy-gcode-plot-test-" + uuid4().hex
    received = []
    listener = SimulationSession(lambda *args: received.append(args), name=name)
    assert listener.listen()
    second = SimulationSession(lambda *_args: None, name=name)
    assert not second.listen()
    path = tmp_path / "program.nc"
    path.write_text("G21\nT1 M6\nM30\n")
    manifest = tmp_path / "simulation.json"
    data = {
        "version": 1,
        "units": "mm",
        "nc": path.name,
        "stock": dict(zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), (-5, 105, -5, 105, -10, 0))),
        "tool": {"number": 1, "diameter": 10, "type": "mill_flat"},
        "coordinates": {"wcs": "G54", "x": 0, "y": 0, "z": 0},
    }
    try:
        for index, diameter in enumerate((10, 6), 1):
            data["tool"]["diameter"] = diameter
            manifest.write_text(json.dumps(data))
            bundle = read_bundle(manifest)
            results = []
            failures = []

            def send(bundle, results, failures):
                try:
                    results.append(forward_simulation(path, "fanuc_mill", bundle, name=name))
                except Exception as exc:  # report client-thread failures in the test thread
                    failures.append(exc)

            worker = Thread(target=send, args=(bundle, results, failures))
            worker.start()
            for _ in range(600):
                app.processEvents()
                if not worker.is_alive():
                    break
                QTest.qWait(10)
            worker.join(timeout=1)
            assert not worker.is_alive()
            assert not failures
            assert results == [True]
            app.processEvents()
            assert len(received) == index
            assert received[-1][2].tool_diameter == diameter
    finally:
        listener.close()
        second.close()
    assert not forward_simulation(path, "fanuc_mill", bundle, name=name)
