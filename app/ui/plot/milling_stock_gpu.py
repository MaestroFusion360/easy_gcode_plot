"""Persistent GPU stock state; CPU supplies immutable cutter sweeps only."""

import logging
import math
from dataclasses import dataclass

import numpy as np
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader

from app.gcode.stock.milling_stock import MillingStockSnapshot
from app.gcode.stock.milling_stock_sweep import CutterSweep, compact_profile
from app.tools.milling_geometry import milling_geometry
from app.ui.plot import milling_stock_shaders as shaders

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class StockFrame:
    timeline: object
    count: int
    revision: int
    sweeps: tuple
    surface_error: float
    edge_error: float


class GpuStock:
    """Compute removal in RG32F dexels, then ray-cast their maximum hierarchy."""

    def __init__(self, memory_budget=4 * 1024**3):
        self.memory_budget = memory_budget
        self.context = None
        self.texture = 0
        self.key = None
        self.count = 0
        self.sweeps = ()
        self._snapshot_cache = None

    def initialize(self, context):
        if self.context is context:
            return
        major = int(GL.glGetIntegerv(GL.GL_MAJOR_VERSION))
        minor = int(GL.glGetIntegerv(GL.GL_MINOR_VERSION))
        if (major, minor) < (4, 3):
            raise RuntimeError(f"GPU stock removal requires OpenGL 4.3; current context is {major}.{minor}")
        LOGGER.info("milling_stock_gpu_initialize opengl=%d.%d budget_bytes=%d", major, minor, self.memory_budget)
        self.remove = compileProgram(compileShader(shaders.REMOVE, GL.GL_COMPUTE_SHADER))
        self.reduce = compileProgram(compileShader(shaders.REDUCE, GL.GL_COMPUTE_SHADER))
        self.display = compileProgram(
            compileShader(shaders.VERTEX, GL.GL_VERTEX_SHADER),
            compileShader(shaders.FRAGMENT, GL.GL_FRAGMENT_SHADER),
        )
        self.vao = GL.glGenVertexArrays(1)
        self.profile_buffer = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_SHADER_STORAGE_BUFFER, self.profile_buffer)
        GL.glBufferData(GL.GL_SHADER_STORAGE_BUFFER, 8, np.zeros(2, dtype=np.float32), GL.GL_STREAM_DRAW)
        GL.glBindBufferBase(GL.GL_SHADER_STORAGE_BUFFER, 0, self.profile_buffer)
        self.context = context
        self.texture = 0
        self.key = None
        self.locations = {}

    def uniform(self, program, name):
        key = program, name
        if key not in self.locations:
            self.locations[key] = GL.glGetUniformLocation(program, name)
        return self.locations[key]

    def _rectangle(self, program, first, last, cancelled=None):
        if cancelled is not None:
            # Bound individual dispatches so a snapshot can stop between tiles.
            for y in range(int(first[1]), int(last[1]), 256):
                for x in range(int(first[0]), int(last[0]), 256):
                    if cancelled():
                        raise InterruptedError("Stock snapshot cancelled")
                    self._rectangle(program, (x, y), (min(x + 256, last[0]), min(y + 256, last[1])))
            return
        GL.glUniform2i(self.uniform(program, "first"), *map(int, first))
        GL.glUniform2i(self.uniform(program, "last"), *map(int, last))
        width, height = np.asarray(last) - first
        if width > 0 and height > 0:
            GL.glDispatchCompute((int(width) + 7) // 8, (int(height) + 7) // 8, 1)
            GL.glMemoryBarrier(GL.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | GL.GL_TEXTURE_FETCH_BARRIER_BIT)

    def validate_frame(self, frame):
        """Check padded texture storage on the CPU before publishing a frame."""
        spec = frame.timeline.spec
        extent = np.asarray((spec.x_max - spec.x_min, spec.y_max - spec.y_min))
        cells = np.maximum(1, np.ceil(extent / (frame.edge_error / math.sqrt(2))).astype(np.int64)) + 1
        shape = tuple(1 << (int(n) - 1).bit_length() for n in cells)
        levels = max(shape).bit_length()
        required = sum(max(1, shape[0] >> level) * max(1, shape[1] >> level) * 8 for level in range(levels))
        if required > self.memory_budget:
            raise ValueError(
                f"Stock Accuracy needs {required / 1024**2:.1f} MiB for GPU texture storage; "
                f"the budget is {self.memory_budget / 1024**2:.1f} MiB. "
                "Choose a lower Stock Accuracy or smaller stock. Accuracy was not reduced."
            )
        return cells, shape, levels

    def _allocate(self, frame, cancelled=None):
        cells, shape, levels = self.validate_frame(frame)
        spec = frame.timeline.spec
        self.origin = np.asarray((spec.x_min, spec.y_min, spec.z_min), dtype=np.float64)
        self.extent = np.asarray((spec.x_max, spec.y_max, spec.z_max)) - self.origin
        # Heights are samples at patch vertices, including the stock boundary.
        self.cells = cells
        self.pitch = self.extent[:2] / (self.cells - 1)
        self.shape = shape
        limit = int(GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE))
        if max(self.shape) > limit:
            raise ValueError(
                f"Stock Accuracy needs {self.cells[0]} x {self.cells[1]} GPU dexels; "
                f"this GPU supports textures up to {limit}. Accuracy was not reduced."
            )
        self.levels = levels
        LOGGER.info(
            "milling_stock_gpu_allocate cells=%s shape=%s levels=%d budget_bytes=%d",
            tuple(self.cells),
            self.shape,
            self.levels,
            self.memory_budget,
        )
        if self.texture:
            GL.glDeleteTextures([self.texture])
        self.texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        GL.glTexStorage2D(GL.GL_TEXTURE_2D, self.levels, GL.GL_RG32F, *self.shape)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST_MIPMAP_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glUseProgram(self.remove)
        GL.glBindImageTexture(0, self.texture, 0, False, 0, GL.GL_READ_WRITE, GL.GL_RG32F)
        GL.glUniform1i(self.uniform(self.remove, "reset"), 1)
        GL.glUniform1f(self.uniform(self.remove, "top"), 0)
        self._rectangle(self.remove, (0, 0), self.shape, cancelled)
        GL.glUniform1f(self.uniform(self.remove, "top"), float(self.extent[2]))
        self._rectangle(self.remove, (0, 0), self.cells, cancelled)
        GL.glUniform1i(self.uniform(self.remove, "reset"), 0)
        self.count = 0
        self.sweeps = ()

    def _cut(self, sweep, cancelled=None):
        geometry = milling_geometry(sweep.tool)
        if geometry is None:
            raise ValueError("Invalid milling cutter geometry")
        profile = np.asarray(compact_profile(sweep.profile), dtype=np.float32)
        radius = max(r for _, r in sweep.profile)
        tool_kind = geometry["type"]
        kind = {"mill_ball": 1, "mill_bull": 2, "taper_ball_mill": 3}.get(tool_kind, 0)
        GL.glBindBuffer(GL.GL_SHADER_STORAGE_BUFFER, self.profile_buffer)
        GL.glBufferData(GL.GL_SHADER_STORAGE_BUFFER, profile.nbytes, profile, GL.GL_STREAM_DRAW)
        GL.glBindBufferBase(GL.GL_SHADER_STORAGE_BUFFER, 0, self.profile_buffer)
        GL.glUniform1i(self.uniform(self.remove, "profileCount"), len(profile))
        GL.glUniform1i(self.uniform(self.remove, "kind"), kind)
        GL.glUniform1i(self.uniform(self.remove, "rapid"), int(sweep.rapid))
        GL.glUniform1f(self.uniform(self.remove, "radius"), radius)
        GL.glUniform1f(self.uniform(self.remove, "ballRadius"), float(geometry["diameter"]) / 2)
        GL.glUniform1f(self.uniform(self.remove, "corner"), float(geometry.get("cornerRadius", 0)))
        GL.glUniform1f(self.uniform(self.remove, "taperAngle"), math.radians(float(geometry.get("taperAngle", 6))))
        GL.glUniform1i(self.uniform(self.remove, "isArc"), int(sweep.planar_arc is not None))
        dirty = None
        points = np.asarray(sweep.points) - self.origin
        if sweep.planar_arc is not None:
            cx, cy, angle, clockwise = sweep.planar_arc
            center = np.asarray((cx, cy)) - self.origin[:2]
            start = math.atan2(points[0, 1] - center[1], points[0, 0] - center[0])
            GL.glUniform4f(self.uniform(self.remove, "arc"), *map(float, center), start, -angle if clockwise else angle)
            GL.glUniform1f(self.uniform(self.remove, "pathRadius"), float(np.linalg.norm(points[0, :2] - center)))
            segments = ((points[0], points[-1]),)
        else:
            segments = zip(points, points[1:])
        for begin, end in segments:
            if cancelled is not None and cancelled():
                raise InterruptedError("Stock snapshot cancelled")
            if sweep.planar_arc is not None:
                low, high = sweep.bounds
                low, high = low - self.origin[:2], high - self.origin[:2]
            else:
                low, high = np.minimum(begin[:2], end[:2]) - radius, np.maximum(begin[:2], end[:2]) + radius
            first = np.maximum(0, np.floor(low / self.pitch).astype(int))
            last = np.minimum(self.cells, np.ceil(high / self.pitch).astype(int) + 1)
            if np.any(last <= first):
                continue
            GL.glUniform3f(self.uniform(self.remove, "begin"), *map(float, begin))
            GL.glUniform3f(self.uniform(self.remove, "end"), *map(float, end))
            self._rectangle(self.remove, first, last, cancelled)
            dirty = (first, last) if dirty is None else (np.minimum(dirty[0], first), np.maximum(dirty[1], last))
        return dirty

    def update(self, frame, *, cancelled=None):
        try:
            self._update(frame, cancelled)
        except Exception:
            # A partially updated texture must be rebuilt before the next draw.
            self.key = None
            self._snapshot_cache = None
            raise

    def _update(self, frame, cancelled):
        if cancelled is not None and cancelled():
            raise InterruptedError("Stock snapshot cancelled")
        key = frame.timeline, frame.surface_error, frame.edge_error
        reset = self.key != key or frame.count < self.count
        if reset or frame.count != self.count or frame.sweeps != self.sweeps:
            self._snapshot_cache = None
        if reset:
            self._allocate(frame, cancelled)
            self.key = key
        dirty = (np.asarray((0, 0)), np.asarray(self.shape)) if reset else None
        GL.glUseProgram(self.remove)
        GL.glBindImageTexture(0, self.texture, 0, False, 0, GL.GL_READ_WRITE, GL.GL_RG32F)
        GL.glUniform2f(self.uniform(self.remove, "pitch"), *map(float, self.pitch))
        for sweep in frame.sweeps[len(self.sweeps) :]:
            changed = self._cut(sweep, cancelled)
            if changed is not None:
                dirty = (
                    changed if dirty is None else (np.minimum(dirty[0], changed[0]), np.maximum(dirty[1], changed[1]))
                )
        if dirty is not None:
            GL.glUseProgram(self.reduce)
            first, last = dirty
            for level in range(1, self.levels):
                first, last = first // 2, (last + 1) // 2
                size = np.maximum(1, np.asarray(self.shape) >> level)
                last = np.minimum(last, size)
                GL.glBindImageTexture(0, self.texture, level - 1, False, 0, GL.GL_READ_ONLY, GL.GL_RG32F)
                GL.glBindImageTexture(1, self.texture, level, False, 0, GL.GL_WRITE_ONLY, GL.GL_RG32F)
                self._rectangle(self.reduce, first, last, cancelled)
        self.count, self.sweeps = frame.count, frame.sweeps

    def draw(self, mvp, colors):
        inverse, invertible = mvp.inverted()
        if not invertible:
            return
        GL.glUseProgram(self.display)
        GL.glUniformMatrix4fv(self.uniform(self.display, "mvp"), 1, False, np.asarray(mvp.data(), dtype=np.float32))
        GL.glUniformMatrix4fv(
            self.uniform(self.display, "inverseMvp"), 1, False, np.asarray(inverse.data(), dtype=np.float32)
        )
        GL.glUniform4f(self.uniform(self.display, "viewport"), *map(float, GL.glGetIntegerv(GL.GL_VIEWPORT)))
        GL.glUniform3f(self.uniform(self.display, "origin"), *map(float, self.origin))
        GL.glUniform3f(self.uniform(self.display, "extent"), *map(float, self.extent))
        GL.glUniform2f(self.uniform(self.display, "pitch"), *map(float, self.pitch))
        GL.glUniform2i(self.uniform(self.display, "cells"), *map(int, self.cells - 1))
        GL.glUniform1i(self.uniform(self.display, "maxLevel"), self.levels - 1)
        for name, color in zip(("stockColor", "cutColor", "rapidColor"), colors):
            GL.glUniform4f(self.uniform(self.display, name), *(np.asarray(color, dtype=float) / 255))
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        GL.glUniform1i(self.uniform(self.display, "stock"), 0)
        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)

    @property
    def bytes(self):
        return (
            sum(max(1, self.shape[0] >> level) * max(1, self.shape[1] >> level) * 8 for level in range(self.levels))
            if self.texture
            else 0
        )

    def destroy(self):
        if self.context is None:
            return
        if self.texture:
            GL.glDeleteTextures([self.texture])
        GL.glDeleteBuffers(1, [self.profile_buffer])
        GL.glDeleteVertexArrays(1, [self.vao])
        for program in (self.remove, self.reduce, self.display):
            GL.glDeleteProgram(program)
        self.context = None
        self.texture = 0
        self.key = None
        self._snapshot_cache = None

    def snapshot(self, timeline):
        if self._snapshot_cache is not None and self._snapshot_cache[0] is timeline:
            return self._snapshot_cache[1]
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        data = np.empty((self.shape[1], self.shape[0], 2), dtype=np.float32)
        GL.glMemoryBarrier(GL.GL_TEXTURE_UPDATE_BARRIER_BIT)
        GL.glGetTexImage(GL.GL_TEXTURE_2D, 0, GL.GL_RG, GL.GL_FLOAT, data)
        nx, ny = map(int, self.cells)
        height = data[:ny, :nx, 0].copy() + np.float32(timeline.spec.z_min)
        rapid = data[:ny, :nx, 1] > 0.5
        height.flags.writeable = rapid.flags.writeable = False
        snapshot = MillingStockSnapshot(timeline.spec, height, rapid, *map(float, self.pitch))
        self._snapshot_cache = timeline, snapshot
        return snapshot


def prepare_frame(timeline, surface_error, edge_error, cancelled):
    """Resolve trajectories to a geometric tolerance; never evaluate a surface."""
    timeline.surface_error = surface_error
    cache = timeline.__dict__.setdefault("_gpu_frames", {})
    previous_count, previous = cache.get(surface_error, (0, ()))
    count = timeline.motion_count
    if count < previous_count:
        previous = tuple(sweep for sweep in previous if sweep.order < count)
        previous_count = count
    sweeps = []
    for index in range(previous_count, count):
        if cancelled():
            raise InterruptedError("Stock frame superseded")
        sweep = timeline.sweep_at(index)
        if sweep is None:
            continue
        resolved = (
            sweep
            if sweep.contour_error == surface_error
            else CutterSweep.from_motion(
                timeline.motions[sweep.order],
                sweep.tool,
                sweep.profile,
                sweep.order,
                contour_error=surface_error,
            )
        )
        sweeps.append(resolved)
    current = previous + tuple(sweeps)
    cache[surface_error] = count, current
    return StockFrame(timeline, count, timeline.revision, current, surface_error, edge_error)
