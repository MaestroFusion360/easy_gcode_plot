"""Editable fanuc_turn starter templates."""

SNIPPETS = (
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
    ("Program End", "G28 W0\nM9\nM5\nM30\n%\n"),
    ("Retract Home Z", "G28 W0\n"),
    ("Comment", "({{?Text=COMMENT}})\n"),
    ("Rapid Move", "G0 X{{?X=40|number}} Z{{?Z=5|number}}\n"),
    ("Linear Move", "G1 X{{?X=30|number}} Z{{?Z=-20|number}} F{{?Feed=0.2|number|gt=0}}\n"),
    (
        "Circular Move",
        "G{{?Plane=18|int|choices=17,18,19}} G3 X{{?X=0|number}} Z{{?Z=-10|number}} "
        "R{{?R=10|number}} F{{?Feed=0.2|number|gt=0}}\n",
    ),
    ("Dwell (G4)", "G4 X{{?Seconds=1|number|min=0}}\n"),
    ("Threading (G32)", "G32 X{{?X=18|number}} Z{{?Z=-20|number}} F{{?Pitch=1.5|number|gt=0}}\n"),
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
    (
        "Finishing (G70)",
        "G70 P{{?StartBlock=10|int|min=1}} Q{{?EndBlock=20|int|min=1}} F{{?Feed=0.2|number|gt=0}}\n",
    ),
    (
        "Facing Roughing (G72)",
        "G72 W{{?CutDepth=2|number|gt=0}} R{{?Retract=0.5|number|min=0}}\n"
        "G72 P{{?StartBlock=10|int|min=1}} Q{{?EndBlock=20|int|min=1}} "
        "U{{?FinishX=0.3|number}} W{{?FinishZ=0.1|number}} F{{?Feed=0.25|number|gt=0}}\n",
    ),
    (
        "Pattern Roughing (G73)",
        "G73 U{{?ReliefX=2|number|gt=0}} W{{?ReliefZ=1|number|min=0}} R{{?Passes=3|int|min=1}}\n"
        "G73 P{{?StartBlock=10|int|min=1}} Q{{?EndBlock=20|int|min=1}} "
        "U{{?FinishX=0.3|number}} W{{?FinishZ=0.1|number}} F{{?Feed=0.25|number|gt=0}}\n",
    ),
    (
        "Grooving (G75)",
        "G75 R{{?Retract=0.5|number|min=0}}\n"
        "G75 X{{?X=18|number}} Z{{?Z=-20|number}} P{{?StepMicrons=1000|int|min=1}} "
        "Q{{?PeckMicrons=3000|int|min=1}} F{{?Feed=0.1|number|gt=0}}\n",
    ),
    ("Simple Turning (G90)", "G90 X{{?X=18|number}} Z{{?Z=-20|number}} F{{?Feed=0.2|number|gt=0}}\n"),
    ("Simple Threading (G92)", "G92 X{{?X=18|number}} Z{{?Z=-20|number}} F{{?Pitch=1.5|number|gt=0}}\n"),
    ("Simple Facing (G94)", "G94 X{{?X=18|number}} Z{{?Z=-20|number}} F{{?Feed=0.2|number|gt=0}}\n"),
)
