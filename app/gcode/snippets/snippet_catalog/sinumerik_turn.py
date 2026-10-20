"""Editable sinumerik_turn starter templates."""

SNIPPETS = (
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
    ("Program End", "SUPA G0 Z0 D0\nM9\nM5\nM30\n"),
    ("Retract Home Z", "SUPA G0 Z0 D0\n"),
    ("Comment", "; {{?Text=COMMENT}}\n"),
    ("Rapid Move", "G0 X{{?X=40|number}} Z{{?Z=5|number}}\n"),
    ("Linear Move", "G1 X{{?X=30|number}} Z{{?Z=-20|number}} F{{?Feed=0.2|number|gt=0}}\n"),
    (
        "Circular Move",
        "G{{?Plane=18|int|choices=17,18,19}} G3 X{{?X=0|number}} Z{{?Z=-10|number}} "
        "CR={{?R=10|number}} F{{?Feed=0.2|number|gt=0}}\n",
    ),
    ("Dwell (G4)", "G4 F{{?Seconds=1|number|min=0}}\n"),
    ("Threading (G33)", "G33 X{{?X=18|number}} Z{{?Z=-20|number}} K{{?Pitch=1.5|number|gt=0}}\n"),
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
)
