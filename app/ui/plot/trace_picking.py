"""Depth-aware selection of sampled toolpath segments in the plot camera."""

import numpy as np


def _clip_segments(clip):
    """Clip homogeneous line segments to all six camera frustum planes."""
    lower = np.zeros(len(clip))
    upper = np.ones(len(clip))
    valid = np.ones(len(clip), dtype=bool)
    for axis in range(3):
        for sign in (-1, 1):
            values = clip[:, :, 3] + sign * clip[:, :, axis]
            delta = values[:, 1] - values[:, 0]
            crossing = -values[:, 0] / np.where(delta != 0, delta, 1)
            lower = np.where((values[:, 0] < 0) & (delta > 0), np.maximum(lower, crossing), lower)
            upper = np.where((values[:, 1] < 0) & (delta < 0), np.minimum(upper, crossing), upper)
            valid &= ~np.all(values < 0, axis=1)
    valid &= lower <= upper
    delta = clip[:, 1] - clip[:, 0]
    clipped = np.stack((clip[:, 0] + lower[:, None] * delta, clip[:, 0] + upper[:, None] * delta), axis=1)
    valid &= np.all(clipped[:, :, 3] > 1e-12, axis=1)
    return clipped, valid


def _chunk_hit(position, points, matrix, viewport, tolerance, depth_aware):
    clip = np.concatenate((points, np.ones((*points.shape[:2], 1))), axis=2) @ matrix.T
    clip, valid = _clip_segments(clip)
    ndc = clip[:, :, :3] / np.where(clip[:, :, 3:4] > 1e-12, clip[:, :, 3:4], 1)
    x, y, width, height = viewport
    screen = np.stack((x + (ndc[:, :, 0] + 1) * width / 2, y + (1 - ndc[:, :, 1]) * height / 2), axis=2)
    delta = screen[:, 1] - screen[:, 0]
    progress = np.clip(
        np.sum((position - screen[:, 0]) * delta, axis=1) / np.maximum(np.sum(delta * delta, axis=1), 1e-30), 0, 1
    )
    distance = np.linalg.norm(screen[:, 0] + progress[:, None] * delta - position, axis=1)
    depth = ndc[:, 0, 2] + progress * (ndc[:, 1, 2] - ndc[:, 0, 2])
    if not depth_aware:
        depth = np.zeros(len(points))
    indices = np.flatnonzero(valid & np.isfinite(distance) & (distance <= tolerance))
    if indices.size == 0:
        return None
    index = indices[np.lexsort((indices, distance[indices], depth[indices]))[0]]
    return float(depth[index]), float(distance[index]), int(index)


class TracePicker:
    """Keep CPU geometry once; project bounded chunks only when clicked."""

    def __init__(self, segments, motion_to_playback=None):
        self.points = np.asarray([(segment.start, segment.end) for segment in segments], dtype=float).reshape(-1, 2, 3)
        self.motions = np.asarray([segment.logical_index for segment in segments], dtype=int)
        self.rapid = np.asarray([segment.move == 0 for segment in segments], dtype=bool)
        self.playback = self.motions if motion_to_playback is None else np.asarray(motion_to_playback)[self.motions]

    def pick(self, position, matrix, viewport, *, show_rapid=True, tolerance=8.0, visible_count=None, depth_aware=True):
        transform = np.asarray(matrix.copyDataTo()).reshape(4, 4)
        best = None
        for start in range(0, len(self.points), 65536):
            indices = np.arange(start, min(start + 65536, len(self.points)))
            if not show_rapid:
                indices = indices[~self.rapid[indices]]
            if visible_count is not None:
                indices = indices[self.playback[indices] < visible_count]
            hit = _chunk_hit(np.asarray(position), self.points[indices], transform, viewport, tolerance, depth_aware)
            if hit is not None:
                candidate = (*hit[:2], int(indices[hit[2]]))
                best = candidate if best is None else min(best, candidate)
        return None if best is None else int(self.motions[best[2]])
