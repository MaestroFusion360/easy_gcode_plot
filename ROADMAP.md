# Easy G-Code Plot — Roadmap

## Current direction

Current development baseline: **2.0.0**, **not released**. Three-axis milling stock removal is now implemented. The current phase focuses on testing, performance tuning and fixing the new simulation alongside the existing turning, execution and export workflows.

The 1.9.x stabilization phase is complete; its delivered changes are recorded under versions 1.9.5–1.9.8 in [CHANGELOG](CHANGELOG.md). This roadmap tracks current validation and future work rather than repeating completed stabilization tasks.

## 2.0.0 — Validation before release

- Verify milling stock removal on real CAM programs, including large files and ball-mill finishing.
- Check all playback speeds, rapid slider seeks, rewind, tool changes and cancellation, keeping the stock and tool position synchronized.
- Verify the five fixed Accuracy levels across playback speeds and GPU memory limits.
- Verify STL export tolerances, units, closed surfaces, cancellation and import into CAD tools.
- Keep turning behavior covered by regressions while validating GPU milling removal and packaged Windows/Linux builds.
- Fix issues found during this phase before deciding on a release. The version number does not mark a published release or completed validation.

---

# After 2.0.0 — Product workflow expansion

The next stage is focused on features that reduce the need to leave Easy G-Code Plot for CIMCO, Vericut, or external helper tools.

## Priority A — User-facing configuration workflows

### Tool Library import/export

Add GUI actions for importing and exporting configured tools from the **current program tool set**, not only tools already stored in the library.

Goals:

- move selected current tools into Tool Library;
- export selected/current tools;
- import saved tool sets;
- preserve geometry, offsets, type and metadata deterministically.

### Postprocessor management in GUI

Allow users to manage post profiles without editing project files manually.

Needed workflow:

- add existing JSON post profile;
- duplicate profile;
- rename profile;
- remove profile;
- reload profile list;
- validate profile before activation.

### Postprocessor editor

Add a simple dedicated dialog for editing and saving JSON post profiles.

The editor should expose the supported post contract rather than arbitrary free-form JSON wherever practical:

- machine type;
- axes;
- motion syntax;
- arc syntax;
- word order;
- required/modal words;
- formatting;
- program wrappers;
- safety line;
- TCP on/off;
- reference movements.

Raw JSON view may remain available for advanced editing.

### Rotary kinematics editor

The current GUI already provides JSON editing, validation and saved overrides for existing rotary profiles through Options. Extend this into a structured editor with profile creation and guided geometry fields.

Minimum scope:

- rotary axis type;
- A/B/C axis assignment;
- axis direction/sign;
- table/head arrangement;
- pivot/offset values;
- axis limits where relevant;
- preset templates for common 4-axis and 5-axis layouts.

---

## Priority B — Integrated workflow tools

### Embedded console panel

Add an in-application console/dock instead of requiring a separate terminal application.

The console should act as a frontend to existing application services/CLI capabilities rather than creating a second execution engine.

Possible commands/workflows:

```text
analyze current
export expanded
show diagnostics
show tools
run batch
inspect post
inspect kinematics
```

The main goal is diagnostics, automation and expert access without leaving the GUI.

### Report templates

Replace hardcoded report formatting with configurable templates.

Support at minimum:

- report title/header;
- company/project metadata;
- visible sections;
- table columns;
- tool statistics sections;
- units/precision;
- HTML styling;
- reusable saved templates.

The report data model should remain separate from the template layer.

---

## Priority C — Generators and reusable NC creation

### Deterministic post-aware generators

Extend coordinate/pocket/hole generators so generated NC is emitted through a selected post profile.

Goals:

- deterministic controller syntax;
- same formatting rules as normal export;
- no generator-specific private formatter.

Add generator templates for:

- hole patterns;
- drilling cycles;
- tapping;
- thread milling;
- pockets;
- common milling approach/retract patterns.

### Initial snippet presets

Ship useful initial presets for:

- FANUC Lathe;
- FANUC Mill;
- SINUMERIK Mill Native.

Presets should remain editable and removable by the user.

---

## Priority D — Geometry authoring

### Contour editor

Add a dedicated contour dialog for creating milling and turning contours.

Input methods:

- manual coordinate entry;
- line/arc segments;
- import from DXF;
- edit/reorder/delete segments;
- close/open contour validation;
- preview before insertion/export.

Keep this intentionally limited to NC contour construction rather than evolving into a general CAD system.

---

## Priority E — Further stock simulation development

Three-axis milling stock removal is part of the 2.0.0 development baseline. Continue work on this foundation after its current validation phase:

- additional stock shapes beyond the current rectangular milling blank;
- collision checks against remaining stock;
- indexed/multiaxis removal only after the three-axis model is stable and its geometry can be verified.

---

# Priority order after 2.0.0

Recommended sequence:

1. Tool Library import/export workflow.
2. Postprocessor management GUI.
3. Postprocessor editor.
4. Structured rotary kinematics editor extending the existing JSON workflow.
5. Embedded console panel.
6. Report templates.
7. Post-aware generators and additional NC templates.
8. Initial snippet presets.
9. Contour editor / DXF contour workflow.
10. Further stock shapes, collision checks and verified stock-simulation extensions.

The first eight items mostly expose or extend capabilities already present in the architecture. Contour authoring and broader stock-simulation geometry remain larger follow-up tasks; the initial three-axis milling simulation is already implemented in 2.0.0.

---

# Development rule

For every new post-2.0 feature:

```text
existing kernel/service first
→ shared API/contract
→ GUI workflow
→ CLI/batch integration where relevant
→ regression tests
→ packaged-build verification
```

Avoid creating GUI-only implementations of logic that already belongs in the execution, export, tool, report, or generator layers.

The main objective after 2.0.0 is not feature count by itself. It is to make Easy G-Code Plot capable of covering a larger part of the real NC editing, analysis, conversion and preparation workflow without forcing the user back into another application for routine operations.
