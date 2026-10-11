"""Single-flight trajectory preparation for GPU stock, without OpenGL calls."""

from time import perf_counter

from PyQt6.QtCore import QThread


class MillingStockFrameWorker(QThread):
    def __init__(self, timeline, item, count, replay_budget=None):
        super().__init__()
        self.timeline, self.item, self.count = timeline, item, count
        self.tiles = None
        self.error = None
        self.revision = timeline.revision
        self.replay_budget = replay_budget
        self.mesh_seconds = 0

    def run(self):
        try:
            deadline = None if self.replay_budget is None else perf_counter() + self.replay_budget
            while self.timeline.motion_count != self.count:
                if self.isInterruptionRequested():
                    raise InterruptedError("Stock frame superseded")
                self.timeline.set_motion_count(self.count, time_budget=0.012)
                if deadline is not None and perf_counter() >= deadline:
                    break
            started = perf_counter()
            self.tiles = self.item.build_frame(self.timeline, self.isInterruptionRequested)
            self.mesh_seconds = perf_counter() - started
            self.revision = self.timeline.revision
        except Exception as exc:
            self.error = exc
