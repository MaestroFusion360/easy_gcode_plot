# cython: boundscheck=False, wraparound=False, cdivision=True
"""Legacy vertex packing entry point retained for the native build script."""

from libc.math cimport sqrt, floor, fmin, fmax, INFINITY


cdef inline int _preview_face(const float[:, :] height, const unsigned char[:, :] rapid,
                             int x, int y, int face, float base, float top,
                             float* high, float* low) noexcept nogil:
    cdef int nx=x, ny=y, flag
    high[0] = height[y,x]
    low[0] = base
    if high[0] <= base+1e-7:
        return -1
    flag = 2 if rapid[y,x] else (1 if high[0] < top-1e-6 else 0)
    if face == 0:
        return flag
    if face == 2:
        ny -= 1
    elif face == 3:
        nx += 1
    elif face == 4:
        ny += 1
    else:
        nx -= 1
    if 0 <= nx < height.shape[1] and 0 <= ny < height.shape[0]:
        low[0] = fmax(base,height[ny,nx])
        if rapid[ny,nx]:
            flag = 2
        elif flag == 0 and height[ny,nx] < top-1e-6:
            flag = 1
    return flag if high[0] > low[0]+1e-7 else -1


cdef inline void _preview_vertex(unsigned char[:, ::1] output, Py_ssize_t index,
                                  float x, float y, float z,
                                  const unsigned char[:, :, ::1] palette,
                                  int face, int flag) noexcept nogil:
    cdef float* position = <float*>&output[index,0]
    cdef int channel
    position[0], position[1], position[2] = x,y,z
    for channel in range(4):
        output[index,12+channel] = palette[face,flag,channel]


def preview_vertices(const float[:, :] height, const unsigned char[:, :] rapid,
                     int x0, int x1, int y0, int y1,
                     double origin_x, double origin_y, double dx, double dy,
                     float base, float top, const unsigned char[:, :, ::1] palette,
                     unsigned char[:, ::1] output):
    """Pack exposed cache faces directly; no Python arrays per face or triangle."""
    cdef int face, outer, inner, stop, begin, x, y, flag, next_flag, corner, vertex
    cdef int outer0, outer1, inner0, inner1, ix0, ix1, iy0, iy1
    cdef float high, low, next_high, next_low, ax, ay, bx, by, z
    cdef float vx[4]
    cdef float vy[4]
    cdef float vz[4]
    cdef int corners[6]
    cdef Py_ssize_t count=0
    corners[:] = [0,1,2,0,2,3]
    with nogil:
        for face in range(6):
            if face == 1:
                continue
            outer0,outer1 = (x0,x1) if face == 3 or face == 5 else (y0,y1)
            inner0,inner1 = (y0,y1) if face == 3 or face == 5 else (x0,x1)
            for outer in range(outer0,outer1):
                inner = inner0
                while inner < inner1:
                    x,y = (outer,inner) if face == 3 or face == 5 else (inner,outer)
                    flag = _preview_face(height,rapid,x,y,face,base,top,&high,&low)
                    if flag < 0:
                        inner += 1
                        continue
                    begin = inner
                    inner += 1
                    while inner < inner1:
                        x,y = (outer,inner) if face == 3 or face == 5 else (inner,outer)
                        next_flag = _preview_face(height,rapid,x,y,face,base,top,&next_high,&next_low)
                        if flag != next_flag or high != next_high or low != next_low:
                            break
                        inner += 1
                    if face == 3 or face == 5:
                        ix0 = outer
                        ix1 = outer + 1
                        iy0 = begin
                        iy1 = inner
                    else:
                        ix0 = begin
                        ix1 = inner
                        iy0 = outer
                        iy1 = outer + 1
                    ax,bx = origin_x+ix0*dx,origin_x+ix1*dx
                    ay,by = origin_y+iy0*dy,origin_y+iy1*dy
                    if face == 0:
                        vx[:] = [ax,bx,bx,ax]
                        vy[:] = [ay,ay,by,by]
                        vz[:] = [high,high,high,high]
                    else:
                        if face == 2:
                            by = ay
                        elif face == 3:
                            ax = bx
                        elif face == 4:
                            z = ax
                            ax,bx = bx,z
                            ay = by
                        else:
                            bx = ax
                            z = ay
                            ay,by = by,z
                        vx[:] = [ax,ax,bx,bx]
                        vy[:] = [ay,ay,by,by]
                        vz[:] = [high,low,low,high]
                    for vertex in range(6):
                        corner = corners[vertex]
                        _preview_vertex(output,count,vx[corner],vy[corner],vz[corner],palette,face,flag)
                        count += 1
    return count
