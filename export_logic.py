"""Export logic separated from main window."""

import numpy as np
from math import sqrt, pi, cos, sin


def export_pgm(self):
    """Generate the exportable program text based on parsed toolpath data."""

    self.lstExport()
    lst = []
    st = self.seqNumStart
    incr = self.seqNumIncr

    if self.seqNumSpacing == False:
        seq_delim = ""
    else:
        seq_delim = " "

    if self.delim == False:
        delim = ""
    else:
        delim = " "

    if self.leadingZero:
        g_fmt = "G0"
        m_fmt = "M0"
    else:
        g_fmt = "G"
        m_fmt = "M"

    if self.safLine:
        saf_line = (
            g_fmt
            + "0"
            + delim
            + "G17"
            + delim
            + "G40"
            + delim
            + "G49"
            + delim
            + "G80"
            + delim
            + "G90"
        )
        lst.append(saf_line)

    if self.lang < 4:
        prevMove = 0
        prevArcPlane = 17
        prevMode = 90
        prevX = 0
        prevY = 0
        prevZ = 0
        prevTool = 0
        prevSpeed = 0
        prevFeed = 0
        prevCorRad = 40
        prevCycleDrill = 80
        prevCycleZ = 0
        prevCycleR = 0
        prevCycleP = 0
        prevCycleQ = 0
        prevCorD = 0
        first_move = True

        for i in range(len(self.lstProgram)):
            posMode = ""
            toolchange = ""
            self.progressBar.setValue(int((i * 100) / len(self.lstProgram)))
            # Move
            if (
                self.lstProgram[i][0] != None
                and self.lstProgram[i][15] == None
                and self.lstProgram[i][25] == 80
            ):
                if self.forceAdr:
                    move = g_fmt + str(self.lstProgram[i][0]) + delim
                else:
                    if prevMove != self.lstProgram[i][0] or first_move:
                        prevMove = self.lstProgram[i][0]
                        move = g_fmt + str(self.lstProgram[i][0]) + delim
                    else:
                        move = ""
            else:
                move = ""

            # Arc Plane
            if (
                self.lstProgram[i][1] != None
                and self.lstProgram[i][15] == None
                and self.lstProgram[i][25] == 80
            ):
                if self.forceAdr:
                    arcPlane = "G" + str(self.lstProgram[i][1]) + delim
                else:
                    if prevArcPlane != self.lstProgram[i][1] or first_move:
                        prevArcPlane = self.lstProgram[i][1]
                        arcPlane = "G" + str(prevArcPlane) + delim
                    else:
                        arcPlane = ""
            else:
                arcPlane = ""

            # ABS mode
            if self.incrMode:
                prevMode = 91
                if self.lstProgram[i][2] != None and self.lstProgram[i][15] == None:
                    if self.forceAdr:
                        posMode = "G" + str(prevMode) + delim
                    else:
                        if first_move:
                            posMode = "G" + str(prevMode) + delim
                        else:
                            posMode = ""
            else:
                if self.lstProgram[i][2] != None and self.lstProgram[i][15] == None:
                    if self.forceAdr:
                        posMode = "G" + str(self.lstProgram[i][2]) + delim
                    else:
                        if prevMode != self.lstProgram[i][2] or first_move:
                            prevMode = self.lstProgram[i][2]
                            posMode = "G" + str(prevMode) + delim
                        else:
                            posMode = ""
                else:
                    posMode = ""

            # Cycle Drill
            if self.lstProgram[i][25] > 80:
                if self.forceAdr:
                    prevCycleDrill = self.lstProgram[i][25]
                    cycleDrill = "G" + str(prevCycleDrill) + delim
                else:
                    if prevCycleDrill != self.lstProgram[i][25]:
                        prevCycleDrill = self.lstProgram[i][25]
                        cycleDrill = "G" + str(prevCycleDrill) + delim
                    else:
                        cycleDrill = ""
            else:
                if prevCycleDrill != self.lstProgram[i][25]:
                    prevCycleDrill = self.lstProgram[i][25]
                    cycleDrill = "G" + str(prevCycleDrill) + delim
                else:
                    cycleDrill = ""

            # X coord
            if self.lstProgram[i][2] == 90 and self.incrMode == False:
                if self.lstProgram[i][3] != None and self.lstProgram[i][15] == None:
                    if self.forceAdr:
                        x = "X" + self.floatToStr(self.lstProgram[i][3]) + delim
                    else:
                        if prevX != self.lstProgram[i][3] or first_move:
                            prevX = self.lstProgram[i][3]
                            x = "X" + self.floatToStr(self.lstProgram[i][3]) + delim
                        else:
                            x = ""
                else:
                    x = ""
            else:
                if self.lstProgram[i][6] != None and self.lstProgram[i][15] == None:
                    if self.forceAdr:
                        x = "X" + self.floatToStr(self.lstProgram[i][6]) + delim
                    else:
                        if self.lstProgram[i][6] != 0:
                            x = "X" + self.floatToStr(self.lstProgram[i][6]) + delim
                        else:
                            x = ""
                else:
                    x = ""

            # Y coord
            if self.lstProgram[i][2] == 90 and self.incrMode == False:
                if self.lstProgram[i][4] != None and self.lstProgram[i][15] == None:
                    if self.forceAdr:
                        y = "Y" + self.floatToStr(self.lstProgram[i][4]) + delim
                    else:
                        if prevY != self.lstProgram[i][4] or first_move:
                            first_move = False
                            prevY = self.lstProgram[i][4]
                            y = "Y" + self.floatToStr(self.lstProgram[i][4]) + delim
                        else:
                            y = ""
                else:
                    y = ""
            else:
                if self.lstProgram[i][7] != None and self.lstProgram[i][15] == None:
                    if self.forceAdr:
                        y = "Y" + self.floatToStr(self.lstProgram[i][7]) + delim
                    else:
                        first_move = False
                        if self.lstProgram[i][7] != 0:
                            y = "Y" + self.floatToStr(self.lstProgram[i][7]) + delim
                        else:
                            y = ""
                else:
                    y = ""

            # Z coord
            if self.lstProgram[i][25] == 80:
                if self.lstProgram[i][2] == 90 and self.incrMode == False:
                    if self.lstProgram[i][5] != None and self.lstProgram[i][15] == None:
                        if self.forceAdr:
                            z = "Z" + self.floatToStr(self.lstProgram[i][5]) + delim
                        else:
                            if prevZ != self.lstProgram[i][5]:
                                prevZ = self.lstProgram[i][5]
                                z = "Z" + self.floatToStr(self.lstProgram[i][5]) + delim
                            else:
                                z = ""
                    else:
                        z = ""
                else:
                    if self.lstProgram[i][8] != None and self.lstProgram[i][15] == None:
                        if self.forceAdr:
                            z = "Z" + self.floatToStr(self.lstProgram[i][8]) + delim
                        else:
                            if self.lstProgram[i][8] != 0:
                                z = "Z" + self.floatToStr(self.lstProgram[i][8]) + delim
                            else:
                                z = ""
                    else:
                        z = ""
            else:
                z = ""

            # Cycle Z
            if self.lstProgram[i][25] > 80:
                if self.forceAdr:
                    cycleZ = "Z" + self.floatToStr(self.lstProgram[i][26]) + delim
                else:
                    if prevCycleZ != self.lstProgram[i][26]:
                        prevCycleZ = self.lstProgram[i][26]
                        cycleZ = "Z" + self.floatToStr(prevCycleZ) + delim
                    else:
                        cycleZ = ""
            else:
                cycleZ = ""

            # Cycle R
            if self.lstProgram[i][27] != None and self.lstProgram[i][25] > 80:
                if self.forceAdr:
                    cycleR = "R" + self.floatToStr(self.lstProgram[i][27]) + delim
                else:
                    if prevCycleR != self.lstProgram[i][27]:
                        prevCycleR = self.lstProgram[i][27]
                        cycleR = "R" + self.floatToStr(prevCycleR) + delim
                    else:
                        cycleR = ""
            else:
                cycleR = ""

            # Cycle P
            if self.lstProgram[i][28] != None and self.lstProgram[i][25] > 81:
                if self.forceAdr:
                    cycleP = "P" + self.floatToStr(self.lstProgram[i][28]) + delim
                else:
                    if prevCycleP != self.lstProgram[i][28]:
                        prevCycleP = self.lstProgram[i][28]
                        cycleP = "P" + self.floatToStr(prevCycleP) + delim
                    else:
                        cycleP = ""
            else:
                cycleP = ""

            # Cycle Q
            if self.lstProgram[i][29] != None and self.lstProgram[i][25] == 83:
                if self.forceAdr:
                    cycleQ = "Q" + self.floatToStr(self.lstProgram[i][29]) + delim
                else:
                    if prevCycleQ != self.lstProgram[i][29]:
                        prevCycleQ = self.lstProgram[i][29]
                        cycleQ = "Q" + self.floatToStr(prevCycleQ) + delim
                    else:
                        cycleQ = ""
            else:
                cycleQ = ""

            # Feed
            if self.lstProgram[i][11] != 0 and self.lstProgram[i][15] == None:
                if self.forceAdr:
                    feed = "F" + self.floatToStr(self.lstProgram[i][11]) + delim
                else:
                    if prevFeed != self.lstProgram[i][11]:
                        prevFeed = self.lstProgram[i][11]
                        feed = "F" + self.floatToStr(self.lstProgram[i][11]) + delim
                    else:
                        feed = ""
            else:
                feed = ""

            feed_cycle = feed

            # WCS
            if self.lstProgram[i][12] != None:
                posWcs = "G" + str(self.lstProgram[i][12]) + delim
            else:
                posWcs = ""

            # Tool number
            if self.lstProgram[i][14] != 0 and prevTool != self.lstProgram[i][14]:
                prevTool = self.lstProgram[i][14]
                if self.leadingZero:
                    tool = "T{:02d}".format(self.lstProgram[i][14]) + delim
                else:
                    tool = "T{:d}".format(self.lstProgram[i][14]) + delim
            else:
                tool = ""

            # M6
            toolchange = ""
            if self.lstProgram[i][15] != None:
                if tool != "":
                    first_move = True
                    toolchange = m_fmt + str(self.lstProgram[i][15]) + delim

            # Speed
            if self.lstProgram[i][16] != 0:
                if self.lstProgram[i][17] != None and self.lstProgram[i][17] < 5:
                    prevSpeed = self.lstProgram[i][16]
                    speed = "S{:d}".format(self.lstProgram[i][16]) + delim
                else:
                    if prevSpeed != self.lstProgram[i][16]:
                        prevSpeed = self.lstProgram[i][16]
                        speed = "S{:d}".format(self.lstProgram[i][16]) + delim
                    else:
                        speed = ""
            else:
                speed = ""

            # Speed M code
            if self.lstProgram[i][17] != None:
                speed_code = m_fmt + str(self.lstProgram[i][17]) + delim
            else:
                speed_code = ""

            # Coolant
            if self.lstProgram[i][18] != None:
                coolant = m_fmt + str(self.lstProgram[i][18]) + delim
            else:
                coolant = ""

            # Stop Program
            if self.lstProgram[i][19] != None:
                stopPrgm = m_fmt + str(self.lstProgram[i][19]) + delim
            else:
                stopPrgm = ""

            # Correction Length
            if self.lstProgram[i][20] != None:
                corLen = "G" + str(self.lstProgram[i][20]) + delim
                if self.lstProgram[i][5] == None:
                    z = "Z" + self.floatToStr(prevZ) + delim
            else:
                corLen = ""

            # CorH
            if self.lstProgram[i][21] != None:
                if self.leadingZero:
                    corH = "H{:02d}".format(self.lstProgram[i][21]) + delim
                else:
                    corH = "H{:d}".format(self.lstProgram[i][21]) + delim
            else:
                corH = ""

            # Correction Radius
            if prevCorRad != self.lstProgram[i][22]:
                prevCorRad = self.lstProgram[i][22]
                corRad = "G" + str(prevCorRad) + delim
            else:
                corRad = ""

            # CorD
            if prevCorD != self.lstProgram[i][23]:
                prevCorD = self.lstProgram[i][23]
                if self.leadingZero:
                    corD = "D{:02d}".format(prevCorD) + delim
                else:
                    corD = "D{:d}".format(prevCorD) + delim
            else:
                corD = ""

            # Comment
            if self.lstProgram[i][24] != None:
                comment = self.co + self.lstProgram[i][24] + self.ci + delim
            else:
                comment = ""

            # G28
            if self.lstProgram[i][13] != None:

                if self.lstProgram[i][13] == 1:
                    g28line = "G28" + delim + "X0" + delim
                elif self.lstProgram[i][13] == 2:
                    g28line = "G28" + delim + "Y0" + delim
                elif self.lstProgram[i][13] == 3:
                    g28line = "G28" + delim + "Z0" + delim
                elif self.lstProgram[i][13] == 4:
                    g28line = "G28" + delim + "X0" + delim + "Y0" + delim
                elif self.lstProgram[i][13] == 5:
                    g28line = "G28" + delim + "X0" + delim + "Z0" + delim
                elif self.lstProgram[i][13] == 6:
                    g28line = "G28" + delim + "Y0" + delim + "Z0" + delim
                elif self.lstProgram[i][13] == 7:
                    g28line = "G28" + delim + "X0" + delim + "Y0" + delim + "Z0" + delim
                else:
                    g28line = ""

                line = (
                    move + posMode + g28line + speed_code + comment + coolant + stopPrgm
                )

                if line != "":
                    lst.append(line.rstrip())
                continue

            # Output line
            if self.lstProgram[i][0] != None and self.lstProgram[i][0] == 0:
                line = (
                    move
                    + arcPlane
                    + corLen
                    + corH
                    + corRad
                    + corD
                    + cycleDrill
                    + posWcs
                    + posMode
                    + x
                    + y
                    + z
                    + cycleZ
                    + cycleR
                    + cycleP
                    + cycleQ
                    + feed_cycle
                    + tool
                    + toolchange
                    + speed
                    + speed_code
                    + coolant
                    + stopPrgm
                    + comment
                )
            elif self.lstProgram[i][0] != None and self.lstProgram[i][0] == 1:
                line = (
                    move
                    + arcPlane
                    + corLen
                    + corH
                    + corRad
                    + corD
                    + posWcs
                    + posMode
                    + x
                    + y
                    + z
                    + tool
                    + toolchange
                    + speed
                    + speed_code
                    + feed
                    + coolant
                    + stopPrgm
                    + comment
                )
            elif self.lstProgram[i][0] != None and self.lstProgram[i][0] > 1:

                if i == 0:
                    continue

                if self.lstProgram[i][1] not in (17, 18, 19):
                    continue

                k = 0
                radius = 0
                p0 = p1 = p2 = p3 = None
                adr_I = adr_J = adr_K = adr_I2 = adr_J2 = adr_K2 = ""

                x1 = self.lstProgram[i - 1][3]
                y1 = self.lstProgram[i - 1][4]
                z1 = self.lstProgram[i - 1][5]

                x2 = self.lstProgram[i][3]
                y2 = self.lstProgram[i][4]
                z2 = self.lstProgram[i][5]

                if x1 is None:
                    x1 = 0
                if y1 is None:
                    y1 = 0
                if z1 is None:
                    z1 = 0
                if x2 is None:
                    x2 = 0
                if y2 is None:
                    y2 = 0
                if z2 is None:
                    z2 = 0

                if self.lstProgram[i][1] == 17:
                    xc = self.lstProgram[i][9]
                    yc = self.lstProgram[i][10]

                    if xc is None:
                        xc = 0
                    if yc is None:
                        yc = 0

                    xc1 = xc - x1
                    yc1 = yc - y1

                    radius = sqrt((x1 - xc) ** 2 + (y1 - yc) ** 2)
                    k = (z2 or 0) - (z1 or 0)

                    p0 = [x1, y1]
                    p1 = [xc, yc]
                    p2 = [x2, y2]
                    p3 = [xc + radius, yc]

                    adr_I = "I" + self.floatToStr(xc) + delim
                    adr_J = "J" + self.floatToStr(yc) + delim
                    adr_K = ""
                    adr_I2 = "I" + self.floatToStr(xc1) + delim
                    adr_J2 = "J" + self.floatToStr(yc1) + delim
                    adr_K2 = ""

                elif self.lstProgram[i][1] == 18:
                    xc = self.lstProgram[i][9]
                    zc = self.lstProgram[i][10]

                    if xc is None:
                        xc = 0
                    if zc is None:
                        zc = 0

                    xc1 = xc - x1
                    zc1 = zc - z1

                    radius = sqrt((x1 - xc) ** 2 + (z1 - zc) ** 2)
                    k = y2 - y1

                    p0 = [x1, z1]
                    p1 = [xc, zc]
                    p2 = [x2, z2]
                    p3 = [xc + radius, zc]

                    adr_I = "I" + self.floatToStr(xc) + delim
                    adr_J = ""
                    adr_K = "K" + self.floatToStr(zc) + delim
                    adr_I2 = "I" + self.floatToStr(xc1) + delim
                    adr_J2 = ""
                    adr_K2 = "K" + self.floatToStr(zc1) + delim

                elif self.lstProgram[i][1] == 19:
                    yc = self.lstProgram[i][9]
                    zc = self.lstProgram[i][10]

                    if yc is None:
                        yc = 0
                    if zc is None:
                        zc = 0

                    yc1 = yc - y1
                    zc1 = zc - z1

                    radius = sqrt((y1 - yc) ** 2 + (z1 - zc) ** 2)
                    k = x2 - x1

                    p0 = [y1, z1]
                    p1 = [yc, zc]
                    p2 = [y2, z2]
                    p3 = [yc + radius, zc]

                    adr_I = ""
                    adr_J = "J" + self.floatToStr(yc) + delim
                    adr_K = "K" + self.floatToStr(zc) + delim
                    adr_I2 = ""
                    adr_J2 = "J" + self.floatToStr(yc1) + delim
                    adr_K2 = "K" + self.floatToStr(zc1) + delim

                if self.lang == 0:

                    line = (
                        move
                        + arcPlane
                        + posMode
                        + corRad
                        + corD
                        + posWcs
                        + x
                        + y
                        + z
                        + adr_I2
                        + adr_J2
                        + adr_K2
                        + speed
                        + speed_code
                        + feed
                        + coolant
                        + stopPrgm
                        + comment
                    )

                elif self.lang == 1:

                    line = (
                        move
                        + arcPlane
                        + posMode
                        + corRad
                        + corD
                        + posWcs
                        + x
                        + y
                        + z
                        + adr_I
                        + adr_J
                        + adr_K
                        + speed
                        + speed_code
                        + feed
                        + coolant
                        + stopPrgm
                        + comment
                    )

                elif self.lang == 2:

                    v0 = np.array(p1) - np.array(p0)
                    v1 = np.array(p1) - np.array(p2)
                    if self.lstProgram[i][0] == 2:
                        if self.lstProgram[i][1] == 18:
                            angle = np.arctan2(np.linalg.det([v0, v1]), np.dot(v0, v1))
                        else:
                            angle = np.arctan2(np.linalg.det([v1, v0]), np.dot(v1, v0))
                    else:
                        if self.lstProgram[i][1] == 18:
                            angle = np.arctan2(np.linalg.det([v1, v0]), np.dot(v1, v0))
                        else:
                            angle = np.arctan2(np.linalg.det([v0, v1]), np.dot(v0, v1))

                    if angle <= 0:
                        angle = angle + 2 * pi

                    if angle >= pi:
                        if self.arc_type == 2:
                            line = (
                                move
                                + arcPlane
                                + posMode
                                + corRad
                                + corD
                                + posWcs
                                + x
                                + y
                                + z
                                + adr_I
                                + adr_J
                                + adr_K
                                + speed
                                + speed_code
                                + feed
                                + coolant
                                + stopPrgm
                                + comment
                            )
                        else:
                            line = (
                                move
                                + arcPlane
                                + posMode
                                + corRad
                                + corD
                                + posWcs
                                + x
                                + y
                                + z
                                + adr_I2
                                + adr_J2
                                + adr_K2
                                + speed
                                + speed_code
                                + feed
                                + coolant
                                + stopPrgm
                                + comment
                            )
                    else:
                        adr_R = "R" + self.floatToStr(radius) + delim
                        line = (
                            move
                            + arcPlane
                            + posMode
                            + corRad
                            + corD
                            + posWcs
                            + x
                            + y
                            + z
                            + adr_R
                            + speed
                            + speed_code
                            + feed
                            + coolant
                            + stopPrgm
                            + comment
                        )

                elif self.lang == 3:
                    points = 314

                    v0 = np.array(p1) - np.array(p0)
                    v1 = np.array(p1) - np.array(p2)
                    v2 = np.array(p1) - np.array(p3)

                    startAngle = np.arctan2(np.linalg.det([v2, v0]), np.dot(v2, v0))

                    if startAngle < 0:
                        startAngle = startAngle + 2 * pi

                    if self.lstProgram[i][0] == 2:
                        if self.lstProgram[i][1] == 18:
                            angle = np.arctan2(np.linalg.det([v0, v1]), np.dot(v0, v1))
                        else:
                            angle = np.arctan2(np.linalg.det([v1, v0]), np.dot(v1, v0))
                    else:
                        if self.lstProgram[i][1] == 18:
                            angle = np.arctan2(np.linalg.det([v1, v0]), np.dot(v1, v0))
                        else:
                            angle = np.arctan2(np.linalg.det([v0, v1]), np.dot(v0, v1))

                    if angle <= 0:
                        angle = angle + 2 * pi

                    step = k / ((angle * points) / (2 * pi))

                    if self.lstProgram[i][0] == 2 and self.lstProgram[i][1] != 18:
                        angle = -1 * abs(angle)
                    elif self.lstProgram[i][0] == 3 and self.lstProgram[i][1] == 18:
                        angle = -1 * abs(angle)

                    prev_x = x1
                    prev_y = y1
                    prev_z = z1

                    if prev_x is None:
                        prev_x = 0
                    if prev_y is None:
                        prev_y = 0
                    if prev_z is None:
                        prev_z = 0

                    for point in range(1, points):

                        if self.lstProgram[i][0] == 2:
                            if self.lstProgram[i][1] == 18:
                                delta = (point * 2 * pi) / points
                                if delta >= angle:
                                    break
                            else:
                                delta = -1 * (point * 2 * pi) / points
                                if delta <= angle:
                                    break
                        else:
                            if self.lstProgram[i][1] == 18:
                                delta = -1 * (point * 2 * pi) / points
                                if delta <= angle:
                                    break
                            else:
                                delta = (point * 2 * pi) / points
                                if delta >= angle:
                                    break

                        if self.lstProgram[i][1] == 17:
                            x3 = xc + radius * cos(startAngle + delta)
                            y3 = yc + radius * sin(startAngle + delta)
                            z3 = z1 + step * point

                        elif self.lstProgram[i][1] == 18:
                            x3 = xc + radius * cos(startAngle + delta)
                            y3 = y1 + step * point
                            z3 = zc + radius * sin(startAngle + delta)

                        elif self.lstProgram[i][1] == 19:
                            x3 = x1 + step * point
                            y3 = yc + radius * cos(startAngle + delta)
                            z3 = zc + radius * sin(startAngle + delta)

                        if self.lstProgram[i][2] == 90:
                            x = "X" + self.floatToStr(x3) + delim
                            y = "Y" + self.floatToStr(y3) + delim
                            z = "Z" + self.floatToStr(z3) + delim
                        else:
                            x4 = x3 - prev_x
                            y4 = y3 - prev_y
                            z4 = z3 - prev_z

                            prev_x = x3
                            prev_y = y3
                            prev_z = z3

                            x = "X" + self.floatToStr(x4) + delim
                            y = "Y" + self.floatToStr(y4) + delim
                            z = "Z" + self.floatToStr(z4) + delim

                        if point == 1:
                            line = (
                                g_fmt
                                + "1"
                                + delim
                                + "G"
                                + str(self.lstProgram[i][2])
                                + delim
                                + x
                                + y
                                + z
                                + feed
                                + coolant
                                + stopPrgm
                                + comment
                            )
                        else:
                            line = x + y + z

                        lst.append(line.rstrip())

                    if self.lstProgram[i][2] == 90:
                        line = (
                            "X"
                            + self.floatToStr(x2)
                            + delim
                            + "Y"
                            + self.floatToStr(y2)
                            + delim
                            + "Z"
                            + self.floatToStr(z2)
                        )
                    else:
                        x2_val = x2 or 0
                        y2_val = y2 or 0
                        z2_val = z2 or 0
                        prev_x_val = prev_x or 0
                        prev_y_val = prev_y or 0
                        prev_z_val = prev_z or 0

                        line = (
                            "X"
                            + self.floatToStr(x2_val - prev_x_val)
                            + delim
                            + "Y"
                            + self.floatToStr(y2_val - prev_y_val)
                            + delim
                            + "Z"
                            + self.floatToStr(z2_val - prev_z_val)
                        )

            else:
                line = (
                    corLen
                    + corH
                    + z
                    + corRad
                    + corD
                    + cycleDrill
                    + posWcs
                    + tool
                    + toolchange
                    + speed
                    + speed_code
                    + coolant
                    + stopPrgm
                    + comment
                )

            if line != "":
                lst.append(line.rstrip())

    else:
        for i in range(len(self.lst_points)):
            self.progressBar.setValue(int((i * 100) / len(self.lst_points)))

            x = "X" + self.floatToStr(self.lst_points[i][0]) + delim
            y = "Y" + self.floatToStr(self.lst_points[i][1]) + delim
            z = "Z" + self.floatToStr(self.lst_points[i][2]) + delim
            feed = "F" + self.floatToStr(self.lst_feed[i]) + delim

            if self.lst_feed[i] == self.rapidFeed:
                line = g_fmt + "0" + delim + x + y + z
            else:
                line = g_fmt + "1" + delim + x + y + z + feed

            if i == 0:
                lst.append(line.rstrip())
            else:
                if line.rstrip() != lst[-1]:
                    lst.append(line.rstrip())

    if self.endPgmExp != "":
        lst.append(self.endPgmExp.upper())
    txt = ""
    lst1 = []
    lst1.append(self.er)
    if self.startPgmExp != "":
        lst1.append(self.startPgmExp.upper())

    if self.seqNum:
        for i in range(len(lst)):
            line = "N" + str(st) + seq_delim + str(lst[i])
            st = st + incr
            lst1.append(line)
    else:
        lst1.extend(lst)

    toolpath = self.toolPath()
    if toolpath != "":
        lst1.append(toolpath)
    limits = self.toolPathLimits()
    if limits != "":
        lst1.append(limits)
    lst1.append(self.er)
    txt = "\n".join(lst1)

    return txt
