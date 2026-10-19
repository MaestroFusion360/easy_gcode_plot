"""Editable starter examples, kept separate from persistence and controller execution."""

from app.gcode.snippet_examples import formula_examples

LANGUAGES = (
    ("fanuc_mill", "Fanuc"),
    ("sinumerik_mill", "Sinumerik"),
    ("heidenhain", "Heidenhain"),
    ("fanuc_turn", "Fanuc Lathe"),
    ("sinumerik_turn", "Sinumerik Lathe"),
)

_DEFAULTS = {
    "fanuc_mill": (
        (
            "Program Start",
            "%\nO{{?Program=1000|int|min=1}}\nG21 G17 G90 G94 G40 G49 G80\nG54\n({{date}} {{time}})\n{{cursor}}",
        ),
        (
            "Toolchange",
            "(T{{Tool}} {{?ToolType=END MILL}} H{{LengthOffset}} DIA={{?Diameter=10|number|gt=0}})\n"
            "G0 Z{{?SafeZ=50|number}}\nM5\nM9\nT{{?Tool=1|int|min=0}} M6\n"
            "S{{?RPM=2000|int|gt=0}} M{{?SpindleDirection=3|int|choices=3,4}}\n"
            "G43 H{{?LengthOffset=1|int|min=0}} Z{{SafeZ}}\nM8\n",
        ),
        (
            "Toolchange (Drill)",
            "(T{{Tool}} DRILL H{{LengthOffset}} DIA={{?Diameter=10|number|gt=0}}"
            " POINT={{?PointAngle=118|number|gt=0|lt=180}} DEG)\n"
            "G0 Z{{?SafeZ=50|number}}\nM5\nM9\nT{{?Tool=1|int|min=0}} M6\n"
            "S{{?RPM=2000|int|gt=0}} M{{?SpindleDirection=3|int|choices=3,4}}\n"
            "G43 H{{?LengthOffset=1|int|min=0}} Z{{SafeZ}}\nM8\n",
        ),
        ("Program End", "G0 Z{{?SafeZ=50|number}}\nM9\nM5\nM30\n%\n"),
        ("Retract Home Z", "G28 G91 Z0\n"),
        ("Comment", "({{?Text=COMMENT}})\n"),
        ("Rapid Move", "G0 X{{?X=0|number}} Y{{?Y=0|number}} Z{{?Z=0|number}}\n"),
        ("Linear Move", "G1 X{{?X=20|number}} Y{{?Y=10|number}} Z{{?Z=0|number}} F{{?Feed=300|number|gt=0}}\n"),
        (
            "Circular Move",
            "G17 G3 X{{?X=0|number}} Y{{?Y=10|number}} Z{{?Z=0|number}} R{{?R=10|number}} F{{?Feed=300|number|gt=0}}\n",
        ),
        (
            "Drilling",
            "G{{?ReturnMode=98|int|choices=98,99}} G83 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "Q{{?Peck=3|number|gt=0}} F{{?Feed=150|number|gt=0}}\nG80\n",
        ),
        (
            "High-Speed Peck Drilling (G73)",
            "G{{?ReturnMode=98|int|choices=98,99}} G73 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "Q{{?Peck=3|number|gt=0}} F{{?Feed=150|number|gt=0}}\n"
            "G80\n",
        ),
        (
            "Left-Hand Tapping (G74)",
            "G{{?ReturnMode=98|int|choices=98,99}} G74 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "F{{?Feed=625|number|gt=0}}\n"
            "G80\n",
        ),
        (
            "Fine Boring (G76)",
            "G{{?ReturnMode=98|int|choices=98,99}} G76 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "P{{?Dwell=0.5|number|min=0}} Q{{?Shift=0.2|number|gt=0}} F{{?Feed=150|number|gt=0}}\n"
            "G80\n",
        ),
        (
            "Drilling (G81)",
            "G{{?ReturnMode=98|int|choices=98,99}} G81 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "F{{?Feed=150|number|gt=0}}\n"
            "G80\n",
        ),
        (
            "Spot Drilling (G82)",
            "G{{?ReturnMode=98|int|choices=98,99}} G82 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "P{{?Dwell=0.5|number|min=0}} F{{?Feed=150|number|gt=0}}\n"
            "G80\n",
        ),
        (
            "Right-Hand Tapping (G84)",
            "G{{?ReturnMode=98|int|choices=98,99}} G84 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "F{{?Feed=625|number|gt=0}}\n"
            "G80\n",
        ),
        (
            "Reaming (G85)",
            "G{{?ReturnMode=98|int|choices=98,99}} G85 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "F{{?Feed=150|number|gt=0}}\n"
            "G80\n",
        ),
        (
            "Boring, Spindle Stop (G86)",
            "G{{?ReturnMode=98|int|choices=98,99}} G86 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "F{{?Feed=150|number|gt=0}}\n"
            "G80\n",
        ),
        (
            "Back Boring (G87)",
            "G{{?ReturnMode=98|int|choices=98,99}} G87 Z{{?Z=-10|number|gt=ReturnZ}} R{{?ReturnZ=-20|number}} "
            "Q{{?Shift=0.2|number|gt=0}} F{{?Feed=150|number|gt=0}}\n"
            "G80\n",
        ),
        (
            "Boring with Dwell (G89)",
            "G{{?ReturnMode=98|int|choices=98,99}} G89 Z{{?Z=-20|number|lt=ReturnZ}} R{{?ReturnZ=2|number}} "
            "P{{?Dwell=0.5|number|min=0}} F{{?Feed=150|number|gt=0}}\n"
            "G80\n",
        ),
    ),
    "sinumerik_mill": (
        ("Program Start", "; PROGRAM START\nG71 G17 G90 G40 G94\nMCALL\nG54\n; {{date}} {{time}}\n{{cursor}}"),
        (
            "Toolchange",
            "; T{{Tool}} {{?ToolType=END MILL}} D{{CuttingEdge}} DIA={{?Diameter=10|number|gt=0}}\n"
            "G0 Z{{?SafeZ=50|number}}\nM5\nM9\nT{{?Tool=1|int|min=0}}\nM6\nD{{?CuttingEdge=1|int|min=0}}\n"
            "S{{?RPM=2000|int|gt=0}} M{{?SpindleDirection=3|int|choices=3,4}}\nM8\n",
        ),
        (
            "Toolchange (Drill)",
            "; T{{Tool}} DRILL D{{CuttingEdge}} DIA={{?Diameter=10|number|gt=0}}"
            " POINT={{?PointAngle=118|number|gt=0|lt=180}} DEG\n"
            "G0 Z{{?SafeZ=50|number}}\nM5\nM9\nT{{?Tool=1|int|min=0}}\nM6\nD{{?CuttingEdge=1|int|min=0}}\n"
            "S{{?RPM=2000|int|gt=0}} M{{?SpindleDirection=3|int|choices=3,4}}\nM8\n",
        ),
        ("Program End", "G0 Z{{?SafeZ=50|number}}\nM9\nM5\nM30\n"),
        ("Retract Home Z", "SUPA G0 Z0 D0\n"),
        ("Comment", "; {{?Text=COMMENT}}\n"),
        ("Rapid Move", "G0 X{{?X=0|number}} Y{{?Y=0|number}} Z{{?Z=0|number}}\n"),
        ("Linear Move", "G1 X{{?X=20|number}} Y{{?Y=10|number}} Z{{?Z=0|number}} F{{?Feed=300|number|gt=0}}\n"),
        (
            "Circular Move",
            "G17 G3 X{{?X=0|number}} Y{{?Y=10|number}} Z{{?Z=0|number}} "
            "CR={{?R=10|number}} F{{?Feed=300|number|gt=0}}\n",
        ),
        (
            "Drilling",
            "F{{?Feed=150|number|gt=0}}\nMCALL CYCLE83("
            "{{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|gt=0}},"
            "{{?FDEP=-3|number|optional|oneof=FDPR|lt=RFP}},{{?FDPR=|number|optional|gt=0}},"
            "{{?DAM=0|number|min=0}},{{?DTB=0|number|min=0}},{{?DTS=0|number|min=0}},"
            "{{?FRF=1|number|min=0|max=1}},{{?VARI=1|int|choices=0,1}})\n",
        ),
        (
            "Drilling (CYCLE81)",
            "MCALL\n"
            "F{{?Feed=150|number|gt=0}}\n"
            "MCALL CYCLE81({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}})\n"
            "G0 X=IC(0) Y=IC(0)\nMCALL\n",
        ),
        (
            "Counterboring (CYCLE82)",
            "MCALL\n"
            "F{{?Feed=150|number|gt=0}}\n"
            "MCALL CYCLE82({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}},"
            "{{?DTB=0.5|number|min=0}})\n"
            "G0 X=IC(0) Y=IC(0)\nMCALL\n",
        ),
        (
            "Rigid Tapping (CYCLE84)",
            "MCALL\n"
            "G94\n"
            "S{{?SST=500|int|gt=0}} M3\n"
            "MCALL CYCLE84({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}},"
            "{{?DTB=0|number|min=0}},{{?SDAC=3|int|choices=3,4,5}},,{{?PIT=1.5|number|gt=0}},"
            "0,{{SST}},{{SST}},3,0,0,{{?VARI=0|int|choices=0,1,2}},"
            "{{?DAM=0|number|min=0}},{{?VRT=0|number|min=0}})\n"
            "G0 X=IC(0) Y=IC(0)\nMCALL\n",
        ),
        (
            "Reaming (CYCLE85)",
            "MCALL\n"
            "F{{?Feed=150|number|gt=0}}\n"
            "MCALL CYCLE85({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}},"
            "{{?DTB=0|number|min=0}},{{?FFR=150|number|gt=0}},{{?RFF=300|number|gt=0}})\n"
            "G0 X=IC(0) Y=IC(0)\nMCALL\n",
        ),
        (
            "Fine Boring (CYCLE86)",
            "MCALL\n"
            "F{{?Feed=150|number|gt=0}}\n"
            "MCALL CYCLE86({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}},"
            "{{?DTB=0|number|min=0}},{{?SDIR=3|int|choices=3,4}},{{?RPA=0|number}},{{?RPO=0|number}},"
            "{{?RPAP=0|number}},{{?POSS=0|number}})\n"
            "G0 X=IC(0) Y=IC(0)\nMCALL\n",
        ),
        (
            "Boring with Manual Stop (CYCLE87)",
            "MCALL\n"
            "F{{?Feed=150|number|gt=0}}\n"
            "MCALL CYCLE87({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}},"
            "{{?SDIR=3|int|choices=3,4}})\n"
            "G0 X=IC(0) Y=IC(0)\nMCALL\n",
        ),
        (
            "Boring with Feed Retract (CYCLE89)",
            "MCALL\n"
            "F{{?Feed=150|number|gt=0}}\n"
            "MCALL CYCLE89({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}},"
            "{{?DTB=0.5|number|min=0}})\n"
            "G0 X=IC(0) Y=IC(0)\nMCALL\n",
        ),
        (
            "Row of Holes (HOLES1)",
            "MCALL\n"
            "G17 G90 G40\n"
            "F{{?Feed=150|number|gt=0}}\n"
            "MCALL CYCLE81({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}})\n"
            "HOLES1({{?SPCA=0|number}},{{?SPCO=0|number}},{{?STA1=0|number}},{{?FDIS=0|number}},"
            "{{?DBH=20|number|gt=0}},{{?NUM=5|int|min=1}})\n"
            "MCALL\n",
        ),
        (
            "Bolt Circle (HOLES2)",
            "MCALL\n"
            "G17 G90 G40\n"
            "F{{?Feed=150|number|gt=0}}\n"
            "MCALL CYCLE81({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}})\n"
            "HOLES2({{?CPA=0|number}},{{?CPO=0|number}},{{?RAD=30|number|gt=0}},{{?STA1=0|number}},"
            "{{?INDA=60|number}},{{?NUM=6|int|min=1}})\n"
            "MCALL\n",
        ),
        (
            "Rectangular Pocket (POCKET3)",
            "MCALL\n"
            "G17 G90 G40\n"
            "POCKET3({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-10|number|lt=RFP}},{{?LENG=60|number|gt=0}},{{?WID=40|number|gt=0}},"
            "{{?CRAD=5|number|min=0}},{{?PA=0|number}},{{?PO=0|number}},{{?STA=0|number}},"
            "{{?MID=3|number|gt=0}},{{?FAL=0.2|number|min=0}},{{?FALD=0|number|min=0}},"
            "{{?FFP1=500|number|gt=0}},{{?FFD=150|number|gt=0}},{{?CDIR=0|int|choices=0,1,2,3}},"
            "{{?VARI=11|int|choices=1,2,11,12}},{{?MIDA=5|number|gt=0}})\n",
        ),
        (
            "Circular Pocket (POCKET4)",
            "MCALL\n"
            "G17 G90 G40\n"
            "POCKET4({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-10|number|lt=RFP}},{{?PRAD=20|number|gt=0}},{{?PA=0|number}},{{?PO=0|number}},"
            "{{?MID=3|number|gt=0}},{{?FAL=0.2|number|min=0}},{{?FALD=0|number|min=0}},"
            "{{?FFP1=500|number|gt=0}},{{?FFD=150|number|gt=0}},{{?CDIR=0|int|choices=0,1,2,3}},"
            "{{?VARI=11|int|choices=1,2,11,12}},{{?MIDA=5|number|gt=0}})\n",
        ),
        (
            "Thread Milling (CYCLE90)",
            "MCALL\n"
            "G17 G90 G40\n"
            "CYCLE90({{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}},"
            "{{?DIATH=10|number|gt=0}},{{?KDIAM=8|number|gt=0}},{{?PIT=1.5|number|gt=0}},"
            "{{?FFR=300|number|gt=0}},{{?CDIR=3|int|choices=2,3}},{{?TYPTH=0|int|choices=0,1}},"
            "{{?CPA=0|number}},{{?CPO=0|number}})\n",
        ),
    ),
    "heidenhain": (
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
        ("Program End", "L Z{{?SafeZ=50:+|number}} R0 FMAX\nM9\nM5\nEND PGM {{?Program=DEMO}} MM\n"),
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
    ),
    "fanuc_turn": (
        (
            "Program Start",
            "%\nO{{?Program=1000|int|min=1}}\n(FANUC LATHE G-CODE SYSTEM A)\n"
            "G21 G18 G40 G80\nG54\nG99\n({{date}} {{time}})\n{{cursor}}",
        ),
        (
            "Toolchange",
            "(T{{Tool}} {{?ToolType=TURNING TOOL}} OFFSET {{ToolOffset}}"
            " NOSE R={{?NoseRadius=0.8|number|min=0}} INSERT={{?InsertType=CNMG120408}})\n"
            "G0 X{{?SafeX=100|number}}\nG0 Z{{?SafeZ=100|number}}\nM5\nM9\n"
            "T{{?Tool=01|int|min=0|max=99|width=2}}{{?ToolOffset=01|int|min=0|max=99|width=2}}\n"
            "G97 S{{?RPM=1000|int|gt=0}} M{{?SpindleDirection=3|int|choices=3,4}}\nM8\n",
        ),
        (
            "Toolchange (Drill)",
            "(T{{Tool}} DRILL OFFSET {{ToolOffset}} DIA={{?Diameter=10|number|gt=0}}"
            " POINT={{?PointAngle=118|number|gt=0|lt=180}} DEG)\n"
            "G0 X{{?SafeX=100|number}}\nG0 Z{{?SafeZ=100|number}}\nM5\nM9\n"
            "T{{?Tool=01|int|min=0|max=99|width=2}}{{?ToolOffset=01|int|min=0|max=99|width=2}}\n"
            "G97 S{{?RPM=1000|int|gt=0}} M{{?SpindleDirection=3|int|choices=3,4}}\nM8\n",
        ),
        ("Program End", "G0 X{{?SafeX=100|number}}\nG0 Z{{?SafeZ=100|number}}\nM9\nM5\nM30\n%\n"),
        ("Retract Home Z", "G28 U0 W0\n"),
        ("Comment", "({{?Text=COMMENT}})\n"),
        ("Rapid Move", "G0 X{{?X=40|number}} Z{{?Z=5|number}}\n"),
        ("Linear Move", "G1 X{{?X=30|number}} Z{{?Z=-20|number}} F{{?Feed=0.2|number|gt=0}}\n"),
        ("Circular Move", "G18 G3 X{{?X=0|number}} Z{{?Z=-10|number}} R{{?R=10|number}} F{{?Feed=0.2|number|gt=0}}\n"),
        (
            "Drilling",
            "G74 R{{?Retract=0.5|number|min=0}}\nG74 "
            "{{?X=|number|optional|prefix=X}} {{?Z=-20|number|optional|oneof=X|prefix=Z}} "
            "{{?StepMicrons=|int|optional|min=1|prefix=P}} "
            "{{?PeckMicrons=3000|int|optional|oneof=StepMicrons|min=1|prefix=Q}} "
            "{{?EndRelief=|number|optional|min=0|prefix=R}} "
            "F{{?Feed=0.1|number|gt=0}} {{?RPM=|int|optional|min=1|prefix=S}}\n",
        ),
        (
            "Roughing (G71)",
            "G71 U{{?CutDepth=2|number|gt=0}} R{{?Retract=0.5|number|min=0}}\n"
            "G71 P{{?StartBlock=10|int|min=1|max=99999}} Q{{?EndBlock=20|int|min=1|max=99999}} "
            "U{{?FinishX=0.3|number}} W{{?FinishZ=0.1|number}} F{{?Feed=0.25|number|gt=0}} "
            "{{?RPM=|int|optional|min=1|prefix=S}}\n",
        ),
        (
            "Threading (G76)",
            "G76 P{{?FinishPasses=02|int|min=1|max=99|width=2}}"
            "{{?Chamfer=00|int|min=0|max=99|width=2}}"
            "{{?ToolAngle=60|int|choices=0,29,30,55,60,80|width=2}} "
            "Q{{?MinCutMicrons=100|int|min=1|max=FirstCutMicrons}} R{{?FinishAllowance=0.05|number|min=0}}\n"
            "G76 X{{?X=18|number|gt=0}} Z{{?Z=-20|number}} {{?Taper=|number|optional|prefix=R}} "
            "P{{?HeightMicrons=1000|int|min=1}} Q{{?FirstCutMicrons=300|int|min=1|max=HeightMicrons}} "
            "F{{?Pitch=1.5|number|gt=0}}\n",
        ),
    ),
    "sinumerik_turn": (
        ("Program Start", "; PROGRAM START\nG290\nG71 G18 G90 G40 G95\nDIAMON\nG54\n; {{date}} {{time}}\n{{cursor}}"),
        (
            "Toolchange",
            "; T{{Tool}} {{?ToolType=TURNING TOOL}} D{{CuttingEdge}}"
            " NOSE R={{?NoseRadius=0.8|number|min=0}} INSERT={{?InsertType=CNMG120408}}\n"
            "G0 X{{?SafeX=100|number}}\nG0 Z{{?SafeZ=100|number}}\nM5\nM9\n"
            "T{{?Tool=1|int|min=0}} D{{?CuttingEdge=1|int|min=0}}\n"
            "G97 S{{?RPM=1000|int|gt=0}} M{{?SpindleDirection=3|int|choices=3,4}}\nM8\n",
        ),
        (
            "Toolchange (Drill)",
            "; T{{Tool}} DRILL D{{CuttingEdge}} DIA={{?Diameter=10|number|gt=0}}"
            " POINT={{?PointAngle=118|number|gt=0|lt=180}} DEG\n"
            "G0 X{{?SafeX=100|number}}\nG0 Z{{?SafeZ=100|number}}\nM5\nM9\n"
            "T{{?Tool=1|int|min=0}} D{{?CuttingEdge=1|int|min=0}}\n"
            "G97 S{{?RPM=1000|int|gt=0}} M{{?SpindleDirection=3|int|choices=3,4}}\nM8\n",
        ),
        ("Program End", "G0 X{{?SafeX=100|number}}\nG0 Z{{?SafeZ=100|number}}\nM9\nM5\nM30\n"),
        ("Retract Home Z", "SUPA G0 Z0 D0\n"),
        ("Comment", "; {{?Text=COMMENT}}\n"),
        ("Rapid Move", "G0 X{{?X=40|number}} Z{{?Z=5|number}}\n"),
        ("Linear Move", "G1 X{{?X=30|number}} Z{{?Z=-20|number}} F{{?Feed=0.2|number|gt=0}}\n"),
        (
            "Circular Move",
            "G18 G3 X{{?X=0|number}} Z{{?Z=-10|number}} CR={{?R=10|number}} F{{?Feed=0.2|number|gt=0}}\n",
        ),
        (
            "Drilling",
            "F{{?Feed=0.1|number|gt=0}}\nCYCLE83("
            "{{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}},"
            "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|gt=0}},"
            "{{?FDEP=-3|number|optional|oneof=FDPR|lt=RFP}},{{?FDPR=|number|optional|gt=0}},"
            "{{?DAM=0|number|min=0}},{{?DTB=0|number|min=0}},{{?DTS=0|number|min=0}},"
            "{{?FRF=1|number|min=0|max=1}},{{?VARI=1|int|choices=0,1}})\n",
        ),
        (
            "Roughing (CYCLE95)",
            'CYCLE95("{{?Contour=ROUGH_START:ROUGH_END|contour}}",'
            "{{?MID=2|number|gt=0}},{{?FALZ=0.1|number|min=0}},{{?FALX=0.3|number|min=0}},"
            "{{?FAL=0|number|min=0}},{{?FF1=0.25|number|gt=0}},{{?FF2=0.2|number|gt=0}},"
            "{{?FF3=0.2|number|gt=0}},{{?VARI=9|int|choices=1,2,3,4,5,6,7,8,9,10,11,12}},"
            "{{?DT=0|number|min=0}},{{?DAM=0|number|min=0}},{{?VRT=1|number|min=0}})\n",
        ),
        (
            "Threading (CYCLE97)",
            "CYCLE97({{?Pitch=1.5|number|gt=0}},{{?MPIT=|number|optional|gt=0}},"
            "{{?SPL=0|number}},{{?FPL=-20|number}},{{?DM1=20|number|gt=0}},{{?DM2=20|number|gt=0}},"
            "{{?APP=3|number|min=0}},{{?ROP=3|number|min=0}},{{?TDEP=1|number|gt=0}},"
            "{{?FAL=0|number|min=0}},{{?IANG=0|number|min=-90|max=90}},{{?NSP=0|number|min=0|max=360}},"
            "{{?NRC=4|int|min=1}},{{?NID=0|int|min=0}},{{?VARI=1|int|choices=1,2,3,4}},"
            "{{?NUMT=1|int|min=1}})\n",
        ),
    ),
}


def default_snippets(language_id: str) -> tuple[tuple[str, str], ...]:
    """Return ready-to-edit templates exactly as written, followed by formula examples."""
    return _DEFAULTS[language_id] + formula_examples(language_id)
