# Easy G-Code Plot — Roadmap

## Current direction

Current baseline: **1.9.6**. This roadmap tracks remaining work and future priorities. Release history is maintained in [CHANGELOG](CHANGELOG.md).

Until **2.0.0**, the project is in **feature freeze**.

The goal is not to add new user-facing capabilities, but to stabilize the existing system, remove heuristic behavior, close architectural debt, and make all existing layers predictable across GUI, CLI, export, visualization, Tool Library, generators, reports, tests, Windows and Linux.

The export refactor and multiaxis export work are considered architectural completion of the existing export subsystem rather than new product features.

---

# 1.9.x → 2.0.0 — Stabilization phase

## Remaining stabilization work toward 2.0.0

### Milling verification priority

Focus the next geometry/post audit on `fanuc_mill` and native SINUMERIK milling:

- indexed 3+1 motion on configured single rotary axes;
- indexed 3+2 machining with working-plane and WCS transformations;
- simultaneous four-axis motion, starting with the supported table-C contract;
- five-axis TCP motion on the supported AC/BC profiles, including arcs and orientation changes.

Use real CAM programs, independently specified geometry and export/re-execution comparisons. Test configured tools, compensation on/off, units, reference returns and displaced WCS origins. Verify native compatibility across cycle interface generations. Extend spatial-arc verification to indexed/TCP frames and target-controller arc reconstruction; planar G2/G3 coverage does not establish support for arbitrary spatial arcs.

### Export limitations and verification

- Reconstruct tilted working planes, including `G68.2/G53.1` and native `CYCLE800`, in target-controller output. These remain unsupported in EXPANDED even where source execution is supported.
- Reconstruct target frame offsets for indexed export about a displaced WCS origin. The current diagnostic is `UNSUPPORTED_INDEXED_WCS_EXPANDED_EXPORT`.
- Extend continuous rotary reconstruction beyond the verified table-C and AC/BC TCP subsets only when replay can verify the resulting geometry and state.
- Add semantic drilling-cycle reconstruction for supported FANUC turning operations; reading and plotting these operations does not imply cycle reconstruction in EXPANDED.

The [README export model](README.md#export-model), [English FAQ](FAQ.md#export) and [Russian FAQ](FAQ_RU.md#экспорт) describe the current user contract. The items above extend that contract and require semantic replay verification before becoming supported.

### Post profile hardening

Increase test coverage for JSON post profiles:

- `supports.axes`;
- TCP support;
- word order;
- required/modal words;
- absolute/incremental output;
- modal motion;
- IJK absolute/relative;
- radius arcs;
- linearized arcs;
- decimals;
- sign output;
- leading zero;
- delimiter;
- safety/start/end program blocks;
- reference move syntax;
- TCP on/off commands.

Where possible, validate profiles through:

```text
source
→ execute
→ export
→ re-execute exported NC
→ compare trajectory/orientation semantics
```

---

## 1.9.x — Bugfix and heuristic cleanup

No feature expansion.

Priority areas:

- eliminate remaining heuristic interpretation where deterministic semantics are available;
- improve source-line diagnostics and remove misleading global diagnostics;
- keep warnings separate from true export blockers;
- fix GUI/CLI behavior mismatches;
- fix Windows/Linux differences;
- verify packaged builds, not only source-tree execution;
- improve cancellation and long-program behavior;
- continue regression coverage for real CAM programs;
- keep batch export as a semantic regression tool;
- fix edge cases in FANUC and SINUMERIK dialect handling;
- harden Tool Library data flow and current-program tool handling;
- stabilize reports, generators, snippets, and export dialogs without adding new capabilities.

---

# 2.0.0 — Stable baseline

2.0.0 should mark the point where the existing product surface is considered technically coherent and stable.

Expected baseline:

- GUI works as the main desktop workflow;
- CLI is stable and shares the same kernel/export contracts;
- visualization is reliable;
- Tool Library is reliable;
- three-axis export/conversion is stable;
- multiaxis export has a deterministic supported contract;
- FANUC/SINUMERIK execution paths are covered by real fixtures;
- GUI/CLI/batch use shared execution and export services;
- Windows and Linux build paths are validated;
- diagnostics identify the real source frame;
- batch semantic regression prevents silent export corruption;
- no known major architectural subsystem remains on a legacy path.

2.0.0 is the end of the stabilization phase, not the end of development.

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

## Priority E — Milling stock removal

Add material-removal simulation for milling.

This is expected to be the most technically expensive post-2.0 feature.

Initial scope should be **3-axis only**.

Possible staged implementation:

1. simple rectangular/cylindrical stock;
2. cutter swept-volume removal;
3. playback/rewind synchronization;
4. remaining-stock visualization;
5. collision checks against remaining stock;
6. only after the 3-axis model is stable, consider indexed/multiaxis extension.

The implementation should prefer deterministic geometry over visual approximation.

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
10. 3-axis milling stock removal.

The first eight items mostly expose or extend capabilities already present in the architecture. The last two introduce substantially larger geometry subsystems and should remain later work.

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
