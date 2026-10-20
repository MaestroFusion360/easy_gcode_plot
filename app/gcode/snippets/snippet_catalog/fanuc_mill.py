"""Editable fanuc_mill starter templates."""

SNIPPETS = (
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
    ("Program End", "G28 G91 Z0\nM9\nM5\nM30\n%\n"),
    ("Retract Home Z", "G28 G91 Z0\n"),
    ("Dwell (G4)", "G4 X{{?Seconds=1|number|min=0}}\n"),
    ("Comment", "({{?Text=COMMENT}})\n"),
    ("Rapid Move", "G0 X{{?X=0|number}} Y{{?Y=0|number}} Z{{?Z=0|number}}\n"),
    ("Linear Move", "G1 X{{?X=20|number}} Y{{?Y=10|number}} Z{{?Z=0|number}} F{{?Feed=300|number|gt=0}}\n"),
    (
        "Circular Move",
        "G{{?Plane=17|int|choices=17,18,19}} G3 X{{?X=0|number}} Y{{?Y=10|number}} "
        "Z{{?Z=0|number}} R{{?R=10|number}} F{{?Feed=300|number|gt=0}}\n",
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
)
