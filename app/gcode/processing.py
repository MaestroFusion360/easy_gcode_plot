"""G-code parsing and toolpath generation for the main window."""

import re
import time
from math import atan2, cos, pi, sin, sqrt

from PyQt6.QtWidgets import QMessageBox

from app.gcode.core import calculate_toolpath_metrics, has_motion


class GcodeProcessingMixin:
    """Parse editor contents and generate points for plotting."""

    def checkCode(self):
        """Run G-code conversion and verify that motion exists."""
        start = time.time()
        self.convert()
        end = time.time()
        print(f"Сonvert Execution time: {(end - start) * 1000:.3f} ms")
        return has_motion(self.lstCoord_X, self.lstCoord_Y, self.lstCoord_Z)

    def convert(self):
        """Parse raw editor G-code into structured motion lists."""
        self.clearPlot()
        text = self.ui.editor.text().upper()
        lines = text.splitlines(True)

        prevMove = 0
        prevTool = 0
        prevSpeed = 0
        prevFeed = 0
        prevCorRad = 40
        prevCorD = 0
        prevPosMode = 90
        if self.latheMode:
            prevArcPlane = 18
        else:
            prevArcPlane = 17
        prev_g81 = 80
        Z_cycle = 0
        prevQ = 0
        prevP = 0
        CoordX_abs = self.xPosMach
        CoordY_abs = self.yPosMach
        CoordZ_abs = self.zPosMach
        prevCoordI = None
        prevCoordJ = None
        prevCoordK = None
        prevCoordR = None
        homePos = 0

        for i, line in enumerate(lines):
            self.progressBar.setValue(int((i * 100) / len(lines)))

            comment = "".join(re.findall(r"\(.*?\)", line))
            if comment:
                self.lstComment.append(comment.replace("(", "").replace(")", ""))
                line = line.replace(comment, "")
            else:
                self.lstComment.append(None)

            move = "".join(re.findall(r"G0?[0-3](?=\D)", line))
            coordX = "".join(re.findall(r"X[-+]?[0-9]*\.?[0-9]+", line))
            coordY = "".join(re.findall(r"Y[-+]?[0-9]*\.?[0-9]+", line))
            coordZ = "".join(re.findall(r"Z[-+]?[0-9]*\.?[0-9]+", line))
            coordI = "".join(re.findall(r"I[-+]?[0-9]*\.?[0-9]+", line))
            coordJ = "".join(re.findall(r"J[-+]?[0-9]*\.?[0-9]+", line))
            coordK = "".join(re.findall(r"K[-+]?[0-9]*\.?[0-9]+", line))
            coordR = "".join(re.findall(r"R[-+]?[0-9]*\.?[0-9]+", line))
            tool = "".join(re.findall(r"T[0-9]{1,4}", line))
            speed = "".join(re.findall(r"S[0-9]{1,5}", line))
            feed = "".join(re.findall(r"F[0-9]*\.?[0-9]+", line))
            posMode = "".join(re.findall(r"G9[0,1](?=\D)", line))
            arcPlane = "".join(re.findall(r"G1[7-9](?=\D)", line))
            wcs = "".join(re.findall(r"G5[4-9](?=\D)", line))
            g81 = "".join(re.findall(r"G8[0-4](?=\D)", line))
            P_cycle = "".join(re.findall(r"P[-+]?[0-9]*\.?[0-9]+", line))
            Q_cycle = "".join(re.findall(r"Q[-+]?[0-9]*\.?[0-9]+", line))
            corLen = "".join(re.findall(r"G43(?=\D)", line))
            corRad = "".join(re.findall(r"G4[0-2](?=\D)", line))
            corH = "".join(re.findall(r"H[0-9]{1,4}", line))
            corD = "".join(re.findall(r"D[0-9]{1,4}", line))
            toolchange = "".join(re.findall(r"M0?6(?=\D)", line))
            stopPgrm = "".join(re.findall(r"M0?[0,1](?=\D)", line))
            spindelCode = "".join(re.findall(r"M0?[3-5](?=\D)", line))
            coolant = "".join(re.findall(r"M0?[7-9](?=\D)", line))
            homePosLine = "".join(re.findall(r"G28.*", line))

            if homePosLine:
                xHomeCoord = "".join(re.findall(r"[X][-+]?[0-9]*\.?[0-9]+", homePosLine))
                yHomeCoord = "".join(re.findall(r"[Y][-+]?[0-9]*\.?[0-9]+", homePosLine))
                zHomeCoord = "".join(re.findall(r"[Z][-+]?[0-9]*\.?[0-9]+", homePosLine))

                if xHomeCoord:
                    # G28X0 - 1
                    homePos = 1
                    if yHomeCoord:
                        # G28X0Y0 - 4
                        homePos = 4
                        if zHomeCoord:
                            # G28X0Y0Z0 - 7
                            homePos = 7
                    elif zHomeCoord:
                        # G28X0Z0 - 5
                        homePos = 5
                elif yHomeCoord:
                    # G28Y0 - 2
                    homePos = 2
                    if zHomeCoord:
                        # G28Y0Z0 - 6
                        homePos = 6
                elif zHomeCoord:
                    # G28Z0 - 3
                    homePos = 3
                else:
                    homePos = 0
                if homePos != 0:
                    self.lstHomePos.append(homePos)
                else:
                    self.lstHomePos.append(None)
            else:
                homePos = 0
                self.lstHomePos.append(None)

            line1 = (
                move
                + arcPlane
                + posMode
                + coordX
                + coordY
                + coordZ
                + coordI
                + coordJ
                + coordK
                + coordR
                + tool
                + speed
                + feed
                + comment
                + stopPgrm
                + spindelCode
                + toolchange
                + coolant
                + wcs
                + corLen
                + corRad
                + corH
                + corD
                + g81
                + Q_cycle
                + P_cycle
            )

            if line1 == "":
                self.lstUnknownWords.append(line)
            else:
                self.lstUnknownWords.append(None)

            if toolchange:
                self.lstToolChange.append(int(toolchange.replace("M", "")))
            else:
                self.lstToolChange.append(None)

            if g81:
                prev_g81 = int(g81.replace("G", ""))
                prevMove = 0
            self.lstCycleDrill.append(prev_g81)

            if move and prev_g81 == 80:
                prevMove = int(move.replace("G", ""))
            self.lstMove.append(prevMove)

            if posMode:
                prevPosMode = int(posMode.replace("G", ""))
            self.lstPosMode.append(prevPosMode)

            if arcPlane:
                prevArcPlane = int(arcPlane.replace("G", ""))
            self.lstArcPlane.append(prevArcPlane)

            if coordX:
                if prevPosMode == 90:
                    CoordX_abs = float(coordX.replace("X", ""))
                else:
                    if homePos == 0:
                        CoordX_abs = CoordX_abs + float(coordX.replace("X", ""))
                    elif homePos == 1 or homePos == 4 or homePos == 5 or homePos == 7:
                        CoordX_abs = self.xPosMach
                self.lstCoord_X.append(CoordX_abs)
            else:
                self.lstCoord_X.append(CoordX_abs)

            if coordY:
                if prevPosMode == 90:
                    CoordY_abs = float(coordY.replace("Y", ""))
                else:
                    if homePos == 0:
                        CoordY_abs = CoordY_abs + float(coordY.replace("Y", ""))
                    elif homePos == 2 or homePos == 4 or homePos > 5:
                        CoordY_abs = self.yPosMach
                self.lstCoord_Y.append(CoordY_abs)
            else:
                self.lstCoord_Y.append(CoordY_abs)

            if coordZ:
                if prevPosMode == 90:
                    if prev_g81 == 80:
                        CoordZ_abs = float(coordZ.replace("Z", ""))
                        Z_cycle = 0
                    else:
                        Z_cycle = float(coordZ.replace("Z", ""))
                else:
                    if prev_g81 == 80:
                        CoordZ_abs = CoordZ_abs + float(coordZ.replace("Z", ""))
                        Z_cycle = 0
                    else:
                        Z_cycle = Z_cycle + float(coordZ.replace("Z", ""))

                    if homePos == 3 or homePos > 4:
                        CoordZ_abs = self.zPosMach

                self.lstCoord_Z.append(CoordZ_abs)
                self.lstCycleZ.append(Z_cycle)
            else:
                if prev_g81 == 80:
                    Z_cycle = 0
                self.lstCoord_Z.append(CoordZ_abs)
                self.lstCycleZ.append(Z_cycle)

            if coordI:
                prevCoordI = float(coordI.replace("I", ""))
            else:
                prevCoordI = None
            self.lstCoord_I.append(prevCoordI)

            if coordJ:
                prevCoordJ = float(coordJ.replace("J", ""))
            else:
                prevCoordJ = None
            self.lstCoord_J.append(prevCoordJ)

            if coordK:
                prevCoordK = float(coordK.replace("K", ""))
            else:
                prevCoordK = None
            self.lstCoord_K.append(prevCoordK)

            if coordR:
                prevCoordR = float(coordR.replace("R", ""))
            else:
                if prev_g81 == 80:
                    prevCoordR = None
            self.lstCoord_R.append(prevCoordR)

            if P_cycle:
                prevP = float(P_cycle.replace("P", ""))
            else:
                if prev_g81 < 82 or prev_g81 > 83:
                    prevP = None
            self.lstCycleP.append(prevP)

            if Q_cycle:
                prevQ = float(Q_cycle.replace("Q", ""))
            else:
                if prev_g81 != 83:
                    prevQ = None
            self.lstCycleQ.append(prevQ)

            if tool:
                prevTool = int(tool.replace("T", ""))
            self.lstTool.append(prevTool)

            if speed:
                prevSpeed = int(speed.replace("S", ""))
            self.lstSpeed.append(prevSpeed)

            if feed:
                prevFeed = float(feed.replace("F", ""))
            self.lstFeed.append(prevFeed)

            if wcs:
                self.lstWcs.append(int(wcs.replace("G", "")))
            else:
                self.lstWcs.append(None)

            if corLen:
                self.lstCorLen.append(int(corLen.replace("G", "")))
            else:
                self.lstCorLen.append(None)

            if corH:
                self.lstCorH.append(int(corH.replace("H", "")))
            else:
                self.lstCorH.append(None)

            if corRad:
                prevCorRad = int(corRad.replace("G", ""))
            self.lstCorRad.append(prevCorRad)

            if corD:
                prevCorD = int(corD.replace("D", ""))
            self.lstCorD.append(prevCorD)

            if stopPgrm:
                self.lstPgmStop.append(int(stopPgrm.replace("M", "")))
            else:
                self.lstPgmStop.append(None)

            if spindelCode:
                self.lstSpeedCode.append(int(spindelCode.replace("M", "")))
            else:
                self.lstSpeedCode.append(None)

            if coolant:
                self.lstCoolant.append(int(coolant.replace("M", "")))
            else:
                self.lstCoolant.append(None)

        self.progressBar.setValue(0)

    def circular(self, move, plane, x1, y1, z1, i, j, x2, y2, z2, r, f, num):
        """Generate interpolated circular/helix points for plotting."""
        lst = []
        xc = x1
        yc = y1
        radius = 0
        if self.arc_type == 1:
            xc = x1 + i
            yc = y1 + j
            radius = sqrt((x1 - xc) ** 2 + (y1 - yc) ** 2)
        elif self.arc_type == 2:
            xc = i
            yc = j
            radius = sqrt((x1 - xc) ** 2 + (y1 - yc) ** 2)
        elif self.arc_type == 3:
            if r == 0:
                return []
            d = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
            h = sqrt(r**2 - (d / 2) ** 2)
            radius = abs(r)
            if r > 0:
                if move == 2:
                    xc = x1 + (x2 - x1) / 2 + h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 - h * (x2 - x1) / d
                else:
                    xc = x1 + (x2 - x1) / 2 - h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 + h * (x2 - x1) / d
            elif r < 0:
                if move == 2:
                    xc = x1 + (x2 - x1) / 2 - h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 + h * (x2 - x1) / d
                else:
                    xc = x1 + (x2 - x1) / 2 + h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 - h * (x2 - x1) / d
        else:
            return []

        k = (z2 or 0) - (z1 or 0)
        zc = z1

        v0 = (xc - x1, yc - y1)
        v1 = (xc - x2, yc - y2)
        v2 = (0 - radius, 0)

        startAngle = atan2(v0[1], v0[0]) - atan2(v2[1], v2[0])
        angle = atan2(v1[1], v1[0]) - atan2(v0[1], v0[0])

        if startAngle < 0:
            startAngle = startAngle + 2 * pi

        if move == 2:
            angle = atan2(v0[1], v0[0]) - atan2(v1[1], v1[0])
        else:
            angle = atan2(v1[1], v1[0]) - atan2(v0[1], v0[0])

        if angle <= 0:
            angle = angle + 2 * pi

        # tolerance = 2 * pi/points
        points = (angle * 314) / (2 * pi)
        step = k / points
        points = int(points)

        if move == 2:
            angle = -1 * abs(angle)

        for point in range(1, points):
            delta = point * angle / points
            x = xc + radius * cos(startAngle + delta)
            y = yc + radius * sin(startAngle + delta)
            z = z1 + step * point
            if plane == 17:
                lst.append([x, y, z, xc, yc, zc, xc, yc, f, num])
            elif plane == 18:
                lst.append([x, z, y, xc, zc, yc, xc, yc, f, num])
            elif plane == 19:
                lst.append([z, x, y, zc, xc, yc, xc, yc, f, num])

        if plane == 17:
            lst.append([x2, y2, z2, xc, yc, zc, xc, yc, f, num])
        elif plane == 18:
            lst.append([x2, z2, y2, xc, zc, yc, xc, yc, f, num])
        elif plane == 19:
            lst.append([z2, x2, y2, zc, xc, yc, xc, yc, f, num])

        return lst

    def calcTime(self):
        """Calculate path lengths and estimated time from toolpath data."""
        self.lst_toolpath, self.lst_toolpathTime, has_points = calculate_toolpath_metrics(
            self.x_axis, self.y_axis, self.z_axis, self.lst_feed
        )
        return has_points

    def addValues(self, x, y, z, i, j, k, xc, yc, f, num):
        """Add a single motion point and accompanying metadata."""
        self.x_axis.append(x)
        self.y_axis.append(y)
        self.z_axis.append(z)
        self.i_axis.append(i)
        self.j_axis.append(j)
        self.k_axis.append(k)
        self.lstCenter_X.append(xc)
        self.lstCenter_Y.append(yc)
        self.lst_feed.append(f)
        self.lst_block.append(num)

    def cycleDrill(self, cycle, posMode, x, y, z, r, z_cycle, q, feed, i):
        """Expand drilling cycles into discrete motion points."""
        if cycle > 80:
            if posMode == 90:
                z_ref = r
                z_end = z_cycle
            else:
                z_ref = z + r
                z_end = z + z_cycle

            if cycle == 83 and q != 0:
                z_cycle = z_ref
                ost = abs(z_end - z_ref) % q

                if ost > 0:
                    numbers = int(abs(z_end - z_ref) // q)
                else:
                    numbers = int(abs(z_end - z_ref) / q) - 1

                self.addValues(x, y, z, None, None, None, None, None, self.rapidFeed, i)

                for num in range(numbers):
                    z_cycle = z_cycle - q

                    self.addValues(x, y, z_ref, None, None, None, None, None, self.rapidFeed, i)

                    if num == 0:
                        self.addValues(x, y, z_cycle, None, None, None, None, None, feed, i)
                        self.addValues(x, y, z_ref, None, None, None, None, None, self.rapidFeed, i)
                    else:
                        self.addValues(
                            x,
                            y,
                            z_cycle + q,
                            None,
                            None,
                            None,
                            None,
                            None,
                            self.rapidFeed,
                            i,
                        )
                        self.addValues(x, y, z_cycle, None, None, None, None, None, feed, i)
                        self.addValues(x, y, z_ref, None, None, None, None, None, self.rapidFeed, i)

                self.addValues(x, y, z_cycle, None, None, None, None, None, self.rapidFeed, i)
                self.addValues(x, y, z_end, None, None, None, None, None, feed, i)

            else:
                self.addValues(x, y, z, None, None, None, None, None, self.rapidFeed, i)
                self.addValues(x, y, z_ref, None, None, None, None, None, self.rapidFeed, i)
                self.addValues(x, y, z_end, None, None, None, None, None, feed, i)

    def _arcPointCount(self, move, plane, x1, y1, z1, i, j, x2, y2, z2, r):
        """Return the number of points ``circular`` would append for one arc.

        Mirrors the geometry/counting part of ``circular`` without building the
        interpolated coordinate lists.
        """
        if plane not in (17, 18, 19):
            return 0
        xc = x1
        yc = y1
        if self.arc_type == 1:
            xc = x1 + i
            yc = y1 + j
        elif self.arc_type == 2:
            xc = i
            yc = j
        elif self.arc_type == 3:
            if r == 0:
                return 0
            d = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
            h = sqrt(r * r - (d / 2) ** 2)
            if r > 0:
                if move == 2:
                    xc = x1 + (x2 - x1) / 2 + h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 - h * (x2 - x1) / d
                else:
                    xc = x1 + (x2 - x1) / 2 - h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 + h * (x2 - x1) / d
            else:
                if move == 2:
                    xc = x1 + (x2 - x1) / 2 - h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 + h * (x2 - x1) / d
                else:
                    xc = x1 + (x2 - x1) / 2 + h * (y2 - y1) / d
                    yc = y1 + (y2 - y1) / 2 - h * (x2 - x1) / d
        else:
            return 0

        v0 = (xc - x1, yc - y1)
        v1 = (xc - x2, yc - y2)
        if move == 2:
            angle = atan2(v0[1], v0[0]) - atan2(v1[1], v1[0])
        else:
            angle = atan2(v1[1], v1[0]) - atan2(v0[1], v0[0])
        if angle <= 0:
            angle = angle + 2 * pi

        points = int((angle * 314) / (2 * pi))
        return points if points >= 1 else 1

    def _cycleDrillCount(self, cycle, posMode, z, r, z_cycle, q):
        """Return the number of points ``cycleDrill`` would append."""
        if cycle <= 80:
            return 0
        if posMode == 90:
            z_ref = r
            z_end = z_cycle
        else:
            z_ref = z + r
            z_end = z + z_cycle

        if cycle == 83 and q != 0:
            span = abs(z_end - z_ref)
            if span % q > 0:
                numbers = int(span // q)
            else:
                numbers = int(span / q) - 1
            count = 1  # initial addValues
            if numbers > 0:
                count += numbers  # one addValues per loop iteration
                count += 2  # first iteration adds two extra points
            if numbers > 1:
                count += 3 * (numbers - 1)  # remaining iterations add three extra
            count += 2  # trailing z_cycle and z_end points
            return count
        return 3

    def _countProgramPoints(self):
        """Estimate how many toolpath points ``addMotion`` would generate.

        Runs over the already parsed move lists (produced by ``convert``) and
        mirrors the counting logic of ``addMotion``/``cycleDrill``/``circular``
        without allocating the interpolated points. This keeps the automatic
        refresh decision cheap even for arc- or cycle-heavy programs.
        """
        text = self.ui.editor.text().upper()
        lst_pgm = text.splitlines(True)
        total = 0

        for i in range(len(self.lstMove)):
            m30 = "".join(re.findall(r"M30", lst_pgm[i]))
            m2 = "".join(re.findall(r"M[0]?2(?=\D)", lst_pgm[i]))
            blockskip = "".join(re.findall(r"^\/.*", lst_pgm[i]))
            if m30 or m2:
                break
            if blockskip:
                continue

            scale = 0.5 if self.latheMode else 1
            if i > 0:
                prev_x = self.lstCoord_X[i - 1] * scale
                prev_y = self.lstCoord_Y[i - 1]
                prev_z = self.lstCoord_Z[i - 1]
            else:
                prev_x = prev_y = prev_z = 0

            x = self.lstCoord_X[i] * scale
            y = self.lstCoord_Y[i]
            z = self.lstCoord_Z[i]
            cx = self.lstCoord_I[i] if self.lstCoord_I[i] is not None else 0
            cy = self.lstCoord_J[i] if self.lstCoord_J[i] is not None else 0
            cz = self.lstCoord_K[i] if self.lstCoord_K[i] is not None else 0
            adr_r = self.lstCoord_R[i] if self.lstCoord_R[i] is not None else 0
            q = self.lstCycleQ[i] if self.lstCycleQ[i] is not None else 0

            move = self.lstMove[i]
            plane = self.lstArcPlane[i]
            if move == 0:
                if self.lstCycleDrill[i] > 80:
                    total += self._cycleDrillCount(
                        self.lstCycleDrill[i], self.lstPosMode[i], z, adr_r, self.lstCycleZ[i], q
                    )
                total += 1
            elif move == 1:
                total += 1
            elif move == 2:
                if plane == 17:
                    total += self._arcPointCount(2, 17, prev_x, prev_y, prev_z, cx, cy, x, y, z, adr_r)
                elif plane == 18:
                    total += self._arcPointCount(3, 18, prev_x, prev_z, prev_y, cx, cz, x, z, y, adr_r)
                elif plane == 19:
                    total += self._arcPointCount(2, 19, prev_y, prev_z, prev_x, cy, cz, y, z, x, adr_r)
            elif move == 3:
                if plane == 17:
                    total += self._arcPointCount(3, 17, prev_x, prev_y, prev_z, cx, cy, x, y, z, adr_r)
                elif plane == 18:
                    total += self._arcPointCount(2, 18, prev_x, prev_z, prev_y, cx, cz, x, z, y, adr_r)
                elif plane == 19:
                    total += self._arcPointCount(3, 19, prev_y, prev_z, prev_x, cy, cz, y, z, x, adr_r)

        return total

    def addMotion(self):
        """Populate plotting arrays based on parsed moves and feed values."""
        text = self.ui.editor.text().upper()
        lst_pgm = text.splitlines(True)
        try:
            start = time.time()

            for i in range(len(self.lstMove)):
                self.progressBar.setValue(int((i * 100) / len(self.lstMove)))

                m30 = "".join(re.findall(r"M30", lst_pgm[i]))
                m2 = "".join(re.findall(r"M[0]?2(?=\D)", lst_pgm[i]))
                blockskip = "".join(re.findall(r"^\/.*", lst_pgm[i]))

                if m30 or m2:
                    break

                if blockskip:
                    continue

                if self.latheMode:
                    scale = 0.5
                    feed = self.lstFeed[i] * self.lstSpeed[i]
                else:
                    scale = 1
                    feed = self.lstFeed[i]

                if i > 0:
                    prev_x = self.lstCoord_X[i - 1] * scale
                    prev_y = self.lstCoord_Y[i - 1]
                    prev_z = self.lstCoord_Z[i - 1]
                else:
                    prev_x = 0
                    prev_y = 0
                    prev_z = 0

                x = self.lstCoord_X[i] * scale
                y = self.lstCoord_Y[i]
                z = self.lstCoord_Z[i]

                if self.lstCoord_I[i] != None:
                    cx = self.lstCoord_I[i]
                else:
                    cx = 0

                if self.lstCoord_J[i] != None:
                    cy = self.lstCoord_J[i]
                else:
                    cy = 0

                if self.lstCoord_K[i] != None:
                    cz = self.lstCoord_K[i]
                else:
                    cz = 0

                if self.lstCoord_R[i] != None:
                    adr_R = self.lstCoord_R[i]
                else:
                    adr_R = 0

                if self.lstCycleQ[i] != None:
                    q = self.lstCycleQ[i]
                else:
                    q = 0

                self.lstX_incr.append(x - prev_x)
                self.lstY_incr.append(y - prev_y)
                self.lstZ_incr.append(z - prev_z)

                if self.lstMove[i] == 0:
                    if self.lstCycleDrill[i] > 80:
                        self.cycleDrill(
                            self.lstCycleDrill[i],
                            self.lstPosMode[i],
                            x,
                            y,
                            z,
                            adr_R,
                            self.lstCycleZ[i],
                            q,
                            feed,
                            i,
                        )

                    self.addValues(x, y, z, None, None, None, None, None, self.rapidFeed, i)

                elif self.lstMove[i] == 1:
                    self.addValues(x, y, z, None, None, None, None, None, feed, i)

                elif self.lstMove[i] > 1:
                    lst = []
                    if self.lstMove[i] == 2:
                        if self.lstArcPlane[i] == 17:
                            lst = self.circular(
                                2,
                                17,
                                prev_x,
                                prev_y,
                                prev_z,
                                cx,
                                cy,
                                x,
                                y,
                                z,
                                adr_R,
                                feed,
                                i,
                            )
                        elif self.lstArcPlane[i] == 18:
                            lst = self.circular(
                                3,
                                18,
                                prev_x,
                                prev_z,
                                prev_y,
                                cx,
                                cz,
                                x,
                                z,
                                y,
                                adr_R,
                                feed,
                                i,
                            )
                        elif self.lstArcPlane[i] == 19:
                            lst = self.circular(
                                2,
                                19,
                                prev_y,
                                prev_z,
                                prev_x,
                                cy,
                                cz,
                                y,
                                z,
                                x,
                                adr_R,
                                feed,
                                i,
                            )
                    elif self.lstMove[i] == 3:
                        if self.lstArcPlane[i] == 17:
                            lst = self.circular(
                                3,
                                17,
                                prev_x,
                                prev_y,
                                prev_z,
                                cx,
                                cy,
                                x,
                                y,
                                z,
                                adr_R,
                                feed,
                                i,
                            )
                        elif self.lstArcPlane[i] == 18:
                            lst = self.circular(
                                2,
                                18,
                                prev_x,
                                prev_z,
                                prev_y,
                                cx,
                                cz,
                                x,
                                z,
                                y,
                                adr_R,
                                feed,
                                i,
                            )
                        elif self.lstArcPlane[i] == 19:
                            lst = self.circular(
                                3,
                                19,
                                prev_y,
                                prev_z,
                                prev_x,
                                cy,
                                cz,
                                y,
                                z,
                                x,
                                adr_R,
                                feed,
                                i,
                            )
                    if not lst:
                        continue

                    l = list(zip(*lst))
                    self.x_axis.extend(l[0])
                    self.y_axis.extend(l[1])
                    self.z_axis.extend(l[2])
                    self.i_axis.extend(l[3])
                    self.j_axis.extend(l[4])
                    self.k_axis.extend(l[5])
                    self.lstCenter_X.extend(l[6])
                    self.lstCenter_Y.extend(l[7])
                    self.lst_feed.extend(l[8])
                    self.lst_block.extend(l[9])

        except Exception as e:
            # logging.exception(str(e))
            QMessageBox.warning(self, "Easy G-code Plot", str(e))

        else:
            end = time.time()
            self.progressBar.setValue(0)
            print(f"Сycle Execution time: {(end - start) * 1000:.3f} ms")
            self.ui.statusbar.showMessage(f"Сycle Execution time: {(end - start) * 1000:.3f} ms", 10000)

            self.lst_points = list(zip(self.x_axis, self.y_axis, self.z_axis))
