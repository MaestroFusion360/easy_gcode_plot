"""Visible examples of snippet fields, context literals and arithmetic."""


def _comment(language_id, text):
    return f"({text})\n" if language_id.startswith("fanuc") else f"; {text}\n"


def formula_examples(language_id):
    def comment(text):
        return _comment(language_id, text)

    speed = comment("D={{?D=10|number|gt=0}} mm; Vc={{?Vc=120|number|gt=0}} m/min")
    if language_id == "heidenhain":
        speed += "TOOL CALL {{?Tool=1|int|min=0}} Z S{{=1000*Vc/(PI*D):0}}\n"
    else:
        speed += ("G97 " if language_id.endswith("turn") else "") + "S{{=1000*Vc/(PI*D):0}} M3\n"
    return (
        ("Spindle speed (formula)", speed),
        (
            "Drill point (formula)",
            comment("D={{?D=10|number|gt=0}} mm; Angle={{?Angle=118|number|gt=0|lt=180}} deg")
            + comment("H={{=(D/2)/TAN(Angle/2):4}} mm"),
        ),
        (
            "MM to INCHES",
            comment("mm={{?Length=25.4|number}}; inch={{=TO_INCH(Length):4}}"),
        ),
        (
            "INCHES to MM",
            comment("inch={{?Inches=1|number}}; mm={{=TO_MM(Inches):3}}"),
        ),
        (
            "Trigonometry (formula)",
            comment("Angle={{?Angle=30|number}} deg")
            + comment("SIN={{=SIN(Angle):6}} COS={{=COS(Angle):6}} TAN={{=TAN(Angle):6}}")
            + comment("ATAN={{=ATAN(TAN(Angle)):4}} deg"),
        ),
        ("Document header", comment("{{file.name}} | {{date:DD.MM.YYYY}} {{time}}") + comment("{{file.dir}}")),
    )
