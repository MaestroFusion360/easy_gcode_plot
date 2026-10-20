"""Editable heidenhain starter templates."""

SNIPPETS = (
    (
        "Program Start",
        "BEGIN PGM {{?Program=DEMO}} MM\n"
        "BLK FORM 0.1 Z X{{?MinX=-50:+|number}} Y{{?MinY=-50:+|number}} Z{{?MinZ=-20:+|number}}\n"
        "BLK FORM 0.2 X{{?MaxX=50:+|number|gt=MinX}} Y{{?MaxY=50:+|number|gt=MinY}} "
        "Z{{?MaxZ=0:+|number|gt=MinZ}}\n"
        "; {{date}} {{time}}\n{{cursor}}",
    ),
    (
        "Toolchange",
        "; T{{Tool}} {{?ToolType=END MILL}} TOOL TABLE {{Tool}} DIA={{?Diameter=10|number|gt=0}}\n"
        "L Z{{?SafeZ=50:+|number}} R0 FMAX M5\nTOOL CALL {{?Tool=1|int|min=0}} Z "
        "S{{?RPM=2000|int|min=1|max=30000}}\nL Z{{SafeZ:+}} R0 FMAX "
        "M{{?SpindleDirection=3|int|choices=3,4}}\nM8\n",
    ),
    (
        "Toolchange (Drill)",
        "; T{{Tool}} DRILL TOOL TABLE {{Tool}} DIA={{?Diameter=10|number|gt=0}}"
        " POINT={{?PointAngle=118|number|gt=0|lt=180}} DEG\n"
        "L Z{{?SafeZ=50:+|number}} R0 FMAX M5\nTOOL CALL {{?Tool=1|int|min=0}} Z "
        "S{{?RPM=2000|int|min=1|max=30000}}\nL Z{{SafeZ:+}} R0 FMAX "
        "M{{?SpindleDirection=3|int|choices=3,4}}\nM8\n",
    ),
    ("Program End", "L Z+0 R0 FMAX M91\nM9\nM5\nEND PGM {{?Program=DEMO}} MM\n"),
    ("Retract Home Z", "L Z+0 R0 FMAX M91\n"),
    ("Comment", "; {{?Text=COMMENT}}\n"),
    ("Rapid Move", "L X{{?X=0:+|number}} Y{{?Y=0:+|number}} Z{{?Z=0:+|number}} R0 FMAX\n"),
    ("Linear Move", "L X{{?X=20:+|number}} Y{{?Y=10:+|number}} Z{{?Z=0:+|number}} R0 F{{?Feed=300|number|gt=0}}\n"),
    (
        "Circular Move",
        "CR X{{?X=0:+|number}} Y{{?Y=10:+|number}} Z{{?Z=0:+|number}} "
        "R{{?R=10:+|number}} DR+ F{{?Feed=300|number|gt=0}}\n",
    ),
    (
        "Drilling",
        "CYCL DEF 203 UNIVERSAL DRILLING ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;DEPTH ~\n"
        " Q206={{?Q206=150:+|number|min=1|max=30000}} ;PLUNGING FEED ~\n"
        " Q202={{?Q202=3:+|number|gt=0}} ;INFEED DEPTH ~\n"
        " Q210={{?Q210=0:+|number|min=0}} ;DWELL AT TOP ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q212={{?Q212=0:+|number|min=0}} ;DECREMENT ~\n"
        " Q213={{?Q213=0:+|int|min=0}} ;CHIP BREAKS ~\n"
        " Q205={{?Q205=1:+|number|gt=0|max=Q202}} ;MINIMUM INFEED ~\n"
        " Q211={{?Q211=0:+|number|min=0}} ;DWELL AT BOTTOM ~\n"
        " Q208={{?Q208=500:+|number|min=1|max=30000}} ;RETRACTION FEED ~\n"
        " Q256={{?Q256=0.2:+|number|min=0}} ;CHIP BREAK DISTANCE\nCYCL CALL\n",
    ),
    (
        "Drilling (CYCL DEF 200)",
        "CYCL DEF 200 DRILLING ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;DEPTH ~\n"
        " Q206={{?Q206=150:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q202={{?Q202=3:+|number|gt=0}} ;PECKING DEPTH ~\n"
        " Q210={{?Q210=0:+|number|min=0}} ;DWELL AT TOP ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q211={{?Q211=0:+|number|min=0}} ;DWELL AT BOTTOM\n"
        "CYCL CALL\n",
    ),
    (
        "Reaming (CYCL DEF 201)",
        "CYCL DEF 201 REAMING ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;DEPTH ~\n"
        " Q206={{?Q206=150:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q211={{?Q211=0:+|number|min=0}} ;DWELL AT BOTTOM ~\n"
        " Q208={{?Q208=300:+|number|gt=0}} ;RETRACTION FEED ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE\n"
        "CYCL CALL\n",
    ),
    (
        "Boring (CYCL DEF 202)",
        "CYCL DEF 202 BORING ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;DEPTH ~\n"
        " Q206={{?Q206=150:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q211={{?Q211=0:+|number|min=0}} ;DWELL AT BOTTOM ~\n"
        " Q208={{?Q208=300:+|number|gt=0}} ;RETRACTION FEED ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q214={{?Q214=1:+|int|choices=1,2,3,4}} ;RETRACT DIRECTION ~\n"
        " Q336={{?Q336=0:+|number}} ;SPINDLE ANGLE\n"
        "CYCL CALL\n",
    ),
    (
        "Back Boring (CYCL DEF 204)",
        "CYCL DEF 204 BACK BORING ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q249={{?Q249=5:+|number|gt=0}} ;COUNTERBORE DEPTH ~\n"
        " Q250={{?Q250=20:+|number|gt=0}} ;MATERIAL THICKNESS ~\n"
        " Q251={{?Q251=3.5:+|number|gt=0}} ;OFF-CENTER DISTANCE ~\n"
        " Q252={{?Q252=15:+|number|gt=0}} ;TOOL EDGE HEIGHT ~\n"
        " Q253={{?Q253=750:+|number|gt=0}} ;PRE-POSITION FEED ~\n"
        " Q254={{?Q254=200:+|number|gt=0}} ;BORING FEED ~\n"
        " Q255={{?Q255=0:+|number|min=0}} ;DWELL ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q214={{?Q214=1:+|int|choices=1,2,3,4}} ;DISENGAGE DIRECTION ~\n"
        " Q336={{?Q336=0:+|number}} ;SPINDLE ANGLE\n"
        "CYCL CALL\n",
    ),
    (
        "Universal Pecking (CYCL DEF 205)",
        "CYCL DEF 205 UNIVERSAL PECKING ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;DEPTH ~\n"
        " Q206={{?Q206=150:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q202={{?Q202=3:+|number|gt=0}} ;PECKING DEPTH ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q212={{?Q212=0:+|number|min=0}} ;DECREMENT ~\n"
        " Q205={{?Q205=1:+|number|gt=0|max=Q202}} ;MINIMUM INFEED ~\n"
        " Q258={{?Q258=0.5:+|number|min=0}} ;UPPER STOP DISTANCE ~\n"
        " Q259={{?Q259=0.5:+|number|min=0}} ;LOWER STOP DISTANCE ~\n"
        " Q257={{?Q257=0:+|number|min=0}} ;CHIP BREAK DEPTH ~\n"
        " Q256={{?Q256=0.2:+|number|min=0}} ;CHIP BREAK RETRACT ~\n"
        " Q211={{?Q211=0:+|number|min=0}} ;DWELL AT BOTTOM\n"
        "CYCL CALL\n",
    ),
    (
        "Tapping with Floating Holder (CYCL DEF 206)",
        "CYCL DEF 206 TAPPING NEW ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;THREAD DEPTH ~\n"
        " Q206={{?Q206=300:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q211={{?Q211=0:+|number|min=0}} ;DWELL AT BOTTOM ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE\n"
        "CYCL CALL\n",
    ),
    (
        "Rigid Tapping (CYCL DEF 207)",
        "CYCL DEF 207 RIGID TAPPING ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;THREAD DEPTH ~\n"
        " Q239={{?Q239=1.5:+|number|gt=0}} ;THREAD PITCH ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q336={{?Q336=0:+|number}} ;SPINDLE ANGLE\n"
        "CYCL CALL\n",
    ),
    (
        "Bore Milling (CYCL DEF 208)",
        "CYCL DEF 208 BORE MILLING ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;DEPTH ~\n"
        " Q206={{?Q206=150:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q334={{?Q334=1.5:+|number|gt=0}} ;INFEED DEPTH ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q335={{?Q335=25:+|number|gt=0}} ;BORE DIAMETER ~\n"
        " Q342={{?Q342=0:+|number|min=0}} ;ROUGHING DIAMETER\n"
        "CYCL CALL\n",
    ),
    (
        "Chip-Break Tapping (CYCL DEF 209)",
        "CYCL DEF 209 TAPPING W/ CHIP BRKG ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;THREAD DEPTH ~\n"
        " Q239={{?Q239=1.5:+|number|gt=0}} ;THREAD PITCH ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q257={{?Q257=5:+|number|gt=0}} ;CHIP BREAK DEPTH ~\n"
        " Q256={{?Q256=2:+|number|min=0}} ;CHIP BREAK RETRACT ~\n"
        " Q336={{?Q336=0:+|number}} ;SPINDLE ANGLE\n"
        "CYCL CALL\n",
    ),
    (
        "Centering (CYCL DEF 240)",
        "CYCL DEF 240 CENTERING ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q343={{?Q343=0:+|int|choices=0,1}} ;DEPTH OR DIAMETER ~\n"
        " Q201={{?Q201=-2:+|number|lt=0}} ;CENTERING DEPTH ~\n"
        " Q344={{?Q344=-10:+|number}} ;CENTER DIAMETER ~\n"
        " Q206={{?Q206=150:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q211={{?Q211=0:+|number|min=0}} ;DWELL AT BOTTOM ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE\n"
        "CYCL CALL\n",
    ),
    (
        "Single-Lip Deep Drilling (CYCL DEF 241)",
        "CYCL DEF 241 SINGLE-LIP D.H.DRLNG ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q201={{?Q201=-80:+|number|lt=0}} ;DEPTH ~\n"
        " Q206={{?Q206=150:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q211={{?Q211=0.25:+|number|min=0}} ;DWELL AT DEPTH ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q379={{?Q379=7.5:+|number|min=0}} ;STARTING POINT ~\n"
        " Q253={{?Q253=750:+|number|gt=0}} ;PRE-POSITION FEED ~\n"
        " Q208={{?Q208=1000:+|number|gt=0}} ;RETRACTION FEED ~\n"
        " Q426={{?Q426=3:+|int|choices=3,4,5}} ;SPINDLE DIRECTION ~\n"
        " Q427={{?Q427=25:+|int|gt=0}} ;ENTRY SPEED ~\n"
        " Q428={{?Q428=500:+|int|gt=0}} ;DRILL SPEED ~\n"
        " Q429={{?Q429=8:+|int|min=0}} ;COOLANT ON M ~\n"
        " Q430={{?Q430=9:+|int|min=0}} ;COOLANT OFF M ~\n"
        " Q435={{?Q435=0:+|number|min=0}} ;DWELL DEPTH\n"
        "CYCL CALL\n",
    ),
    (
        "Circular Hole Pattern (CYCL DEF 220)",
        "; Define a machining cycle before this hole pattern.\n"
        "CYCL DEF 220 POLAR PATTERN ~\n"
        " Q216={{?Q216=0:+|number}} ;CENTER X ~\n"
        " Q217={{?Q217=0:+|number}} ;CENTER Y ~\n"
        " Q244={{?Q244=60:+|number|gt=0}} ;PITCH CIRCLE DIAMETER ~\n"
        " Q245={{?Q245=0:+|number}} ;START ANGLE ~\n"
        " Q246={{?Q246=360:+|number}} ;STOP ANGLE ~\n"
        " Q247={{?Q247=0:+|number}} ;ANGLE STEP ~\n"
        " Q241={{?Q241=6:+|int|min=1}} ;NUMBER OF HOLES ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q301={{?Q301=1:+|int|choices=0,1}} ;CLEARANCE MOVE ~\n"
        " Q365={{?Q365=0:+|int|choices=0,1}} ;LINE OR ARC\n",
    ),
    (
        "Grid Hole Pattern (CYCL DEF 221)",
        "; Define a machining cycle before this hole pattern.\n"
        "CYCL DEF 221 CARTESIAN PATTERN ~\n"
        " Q225={{?Q225=0:+|number}} ;START X ~\n"
        " Q226={{?Q226=0:+|number}} ;START Y ~\n"
        " Q237={{?Q237=20:+|number}} ;COLUMN SPACING ~\n"
        " Q238={{?Q238=20:+|number}} ;ROW SPACING ~\n"
        " Q242={{?Q242=3:+|int|min=1}} ;COLUMNS ~\n"
        " Q243={{?Q243=2:+|int|min=1}} ;ROWS ~\n"
        " Q224={{?Q224=0:+|number}} ;ROTATION ANGLE ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q301={{?Q301=1:+|int|choices=0,1}} ;CLEARANCE MOVE\n",
    ),
    (
        "Rectangular Pocket (CYCL DEF 251)",
        "CYCL DEF 251 RECTANGULAR POCKET ~\n"
        " Q215={{?Q215=1:+|int|choices=0,1,2}} ;MACHINING OPERATION ~\n"
        " Q218={{?Q218=60:+|number|gt=0}} ;LENGTH X ~\n"
        " Q219={{?Q219=40:+|number|gt=0}} ;LENGTH Y ~\n"
        " Q220={{?Q220=5:+|number|min=0}} ;CORNER RADIUS ~\n"
        " Q224={{?Q224=0:+|number}} ;ROTATION ANGLE ~\n"
        " Q201={{?Q201=-10:+|number|lt=0}} ;DEPTH ~\n"
        " Q367={{?Q367=0:+|int|choices=0,1,2,3,4}} ;POCKET POSITION ~\n"
        " Q202={{?Q202=3:+|number|gt=0}} ;PLUNGING DEPTH ~\n"
        " Q207={{?Q207=500:+|number|gt=0}} ;MILLING FEED ~\n"
        " Q206={{?Q206=150:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q385={{?Q385=500:+|number|gt=0}} ;FINISHING FEED ~\n"
        " Q368={{?Q368=0.2:+|number|min=0}} ;SIDE ALLOWANCE ~\n"
        " Q369={{?Q369=0:+|number|min=0}} ;FLOOR ALLOWANCE ~\n"
        " Q338={{?Q338=3:+|number|gt=0}} ;FINISHING INFEED ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q351={{?Q351=1:+|int|choices=-1,1}} ;CLIMB OR UP-CUT ~\n"
        " Q370={{?Q370=1:+|number|gt=0|max=1.99}} ;PATH OVERLAP ~\n"
        " Q366={{?Q366=0:+|int|choices=0,1,2}} ;PLUNGING STRATEGY\n"
        "CYCL CALL\n",
    ),
    (
        "Circular Pocket (CYCL DEF 252)",
        "CYCL DEF 252 CIRCULAR POCKET ~\n"
        " Q215={{?Q215=1:+|int|choices=0,1,2}} ;MACHINING OPERATION ~\n"
        " Q223={{?Q223=40:+|number|gt=0}} ;POCKET DIAMETER ~\n"
        " Q368={{?Q368=0.2:+|number|min=0}} ;SIDE ALLOWANCE ~\n"
        " Q207={{?Q207=500:+|number|gt=0}} ;MILLING FEED ~\n"
        " Q351={{?Q351=1:+|int|choices=-1,1}} ;CLIMB OR UP-CUT ~\n"
        " Q201={{?Q201=-10:+|number|lt=0}} ;DEPTH ~\n"
        " Q202={{?Q202=3:+|number|gt=0}} ;PLUNGING DEPTH ~\n"
        " Q369={{?Q369=0:+|number|min=0}} ;FLOOR ALLOWANCE ~\n"
        " Q206={{?Q206=150:+|number|gt=0}} ;PLUNGING FEED ~\n"
        " Q338={{?Q338=3:+|number|gt=0}} ;FINISHING INFEED ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q370={{?Q370=1:+|number|gt=0|max=1.99}} ;PATH OVERLAP ~\n"
        " Q366={{?Q366=0:+|int|choices=0,1}} ;PLUNGING STRATEGY ~\n"
        " Q385={{?Q385=500:+|number|gt=0}} ;FINISHING FEED\n"
        "CYCL CALL\n",
    ),
    (
        "Thread Milling (CYCL DEF 262)",
        "CYCL DEF 262 THREAD MILLING ~\n"
        " Q335={{?Q335=10:+|number|gt=0}} ;THREAD DIAMETER ~\n"
        " Q239={{?Q239=1.5:+|number|gt=0}} ;THREAD PITCH ~\n"
        " Q201={{?Q201=-20:+|number|lt=0}} ;THREAD DEPTH ~\n"
        " Q355={{?Q355=0:+|int|min=0}} ;THREADS PER STEP ~\n"
        " Q253={{?Q253=750:+|number|gt=0}} ;PRE-POSITION FEED ~\n"
        " Q351={{?Q351=1:+|int|choices=-1,1}} ;CLIMB OR UP-CUT ~\n"
        " Q200={{?Q200=2:+|number|min=0}} ;SET-UP CLEARANCE ~\n"
        " Q203={{?Q203=0:+|number}} ;SURFACE ~\n"
        " Q204={{?Q204=50:+|number|min=Q200}} ;SECOND CLEARANCE ~\n"
        " Q207={{?Q207=500:+|number|gt=0}} ;MILLING FEED\n"
        "CYCL CALL\n",
    ),
)
