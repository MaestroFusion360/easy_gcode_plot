# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False
"""C-double convex clipping for the turning collision section, without Python point loops."""

from cpython.mem cimport PyMem_Malloc, PyMem_Free
from libc.math cimport fabs


cdef struct Point:
    double x
    double z


cdef double _area(Point* points, Py_ssize_t count) noexcept:
    cdef Py_ssize_t i, j
    cdef double area = 0.0
    for i in range(count):
        j = (i + 1) % count
        area += points[i].x * points[j].z - points[j].x * points[i].z
    return area * 0.5


cdef object _clip(object polygon, object boundary):
    cdef Py_ssize_t count = len(polygon), edges = len(boundary)
    cdef Py_ssize_t capacity = count + edges + 1
    cdef Py_ssize_t i, j, size
    cdef Point *source = NULL
    cdef Point *target = NULL
    cdef Point *walls = NULL
    cdef Point a, b, previous, point
    cdef double xmin, xmax, zmin, zmax, bxmin, bxmax, bzmin, bzmax
    cdef double before, after, direction, progress
    cdef bint unchanged = True
    if count < 3 or edges < 3:
        return ()
    source = <Point*>PyMem_Malloc(capacity * sizeof(Point))
    target = <Point*>PyMem_Malloc(capacity * sizeof(Point))
    walls = <Point*>PyMem_Malloc(edges * sizeof(Point))
    if source == NULL or target == NULL or walls == NULL:
        PyMem_Free(source)
        PyMem_Free(target)
        PyMem_Free(walls)
        raise MemoryError()
    try:
        for i in range(count):
            source[i].x, source[i].z = polygon[i]
        for i in range(edges):
            walls[i].x, walls[i].z = boundary[i]
        xmin = xmax = source[0].x
        zmin = zmax = source[0].z
        for i in range(1, count):
            xmin = min(xmin, source[i].x)
            xmax = max(xmax, source[i].x)
            zmin = min(zmin, source[i].z)
            zmax = max(zmax, source[i].z)
        bxmin = bxmax = walls[0].x
        bzmin = bzmax = walls[0].z
        for i in range(1, edges):
            bxmin = min(bxmin, walls[i].x)
            bxmax = max(bxmax, walls[i].x)
            bzmin = min(bzmin, walls[i].z)
            bzmax = max(bzmax, walls[i].z)
        if xmax <= bxmin or xmin >= bxmax or zmax <= bzmin or zmin >= bzmax:
            return ()
        direction = 1.0 if _area(walls, edges) > 0 else -1.0
        for j in range(edges):
            if count == 0:
                return ()
            a, b = walls[j], walls[(j + 1) % edges]
            previous = source[count - 1]
            before = direction * ((b.x - a.x) * (previous.z - a.z) - (b.z - a.z) * (previous.x - a.x))
            size = 0
            for i in range(count):
                point = source[i]
                after = direction * ((b.x - a.x) * (point.z - a.z) - (b.z - a.z) * (point.x - a.x))
                if (before >= 0) != (after >= 0):
                    progress = before / (before - after)
                    target[size].x = previous.x + progress * (point.x - previous.x)
                    target[size].z = previous.z + progress * (point.z - previous.z)
                    size += 1
                if after >= 0:
                    target[size] = point
                    size += 1
                else:
                    unchanged = False
                previous, before = point, after
            source, target = target, source
            count = size
        if count < 3 or fabs(_area(source, count)) <= 1e-9:
            return ()
        if unchanged:
            return polygon
        return tuple((source[i].x, source[i].z) for i in range(count))
    finally:
        PyMem_Free(source)
        PyMem_Free(target)
        PyMem_Free(walls)


def clip_regions(regions, bands):
    """Clip and deduplicate a batch of convex damage polygons against material bands."""
    cdef object region, band, clipped
    cdef dict result = {}
    for region in regions:
        for band in bands:
            clipped = _clip(region, band)
            if clipped:
                result[clipped] = None
    return tuple(result)


def swept_profile_spans(points, z_values, Py_ssize_t first, Py_ssize_t last):
    """The existing horizontal-span algorithm, compiled across a complete profile range."""
    cdef Py_ssize_t count = len(points), index, i, j
    cdef Point *polygon = NULL
    cdef Point a, b
    cdef double z, progress, x, low, high
    cdef bint found
    cdef list spans = []
    if count == 0 or first > last:
        return spans
    if first < 0 or last >= len(z_values):
        raise IndexError("Turning profile range is out of bounds")
    polygon = <Point*>PyMem_Malloc(count * sizeof(Point))
    if polygon == NULL:
        raise MemoryError()
    try:
        for i in range(count):
            polygon[i].x, polygon[i].z = points[i]
        for index in range(first, last + 1):
            z = z_values[index]
            found = False
            low = high = 0.0
            for i in range(count):
                a, b = polygon[i], polygon[(i + 1) % count]
                if fabs(b.z - a.z) <= 1e-9:
                    if fabs(z - a.z) <= 1e-9:
                        if not found:
                            low, high = min(a.x, b.x), max(a.x, b.x)
                        else:
                            low, high = min(low, a.x, b.x), max(high, a.x, b.x)
                        found = True
                    continue
                if z < min(a.z, b.z) - 1e-9 or z > max(a.z, b.z) + 1e-9:
                    continue
                progress = (z - a.z) / (b.z - a.z)
                if -1e-9 <= progress <= 1.0 + 1e-9:
                    x = a.x + progress * (b.x - a.x)
                    if not found:
                        low = high = x
                    else:
                        low, high = min(low, x), max(high, x)
                    found = True
            if found:
                spans.append((index, (low, high)))
        return spans
    finally:
        PyMem_Free(polygon)
