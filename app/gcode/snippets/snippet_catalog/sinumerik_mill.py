"""Editable sinumerik_mill starter templates."""

SNIPPETS = (
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
    ("Program End", "SUPA G0 Z0 D0\nM9\nM5\nM30\n"),
    ("Retract Home Z", "SUPA G0 Z0 D0\n"),
    ("Dwell (G4)", "G4 F{{?Seconds=1|number|min=0}}\n"),
    ("Comment", "; {{?Text=COMMENT}}\n"),
    ("Rapid Move", "G0 X{{?X=0|number}} Y{{?Y=0|number}} Z{{?Z=0|number}}\n"),
    ("Linear Move", "G1 X{{?X=20|number}} Y{{?Y=10|number}} Z{{?Z=0|number}} F{{?Feed=300|number|gt=0}}\n"),
    (
        "Circular Move",
        "G{{?Plane=17|int|choices=17,18,19}} G3 X{{?X=0|number}} Y{{?Y=10|number}} "
        "Z{{?Z=0|number}} CR={{?R=10|number}} F{{?Feed=300|number|gt=0}}\n",
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
)
