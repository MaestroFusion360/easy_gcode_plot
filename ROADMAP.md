# Easy G-Code Plot — Roadmap

## Current direction

Current development baseline: **2.1.0**, **not released**. Three-axis milling stock removal is now implemented. The current phase focuses on testing, performance tuning and fixing the new simulation alongside the existing turning, execution and export workflows.

The 1.9.x stabilization phase is complete; its delivered changes are recorded under versions 1.9.5–1.9.8 in [CHANGELOG](CHANGELOG.md). This roadmap tracks current validation and future work rather than repeating completed stabilization tasks.

## 2.1.0 — Validation before release

- Verify milling stock removal on real CAM programs, including large files and ball-mill finishing.
- Check all playback speeds, rapid slider seeks, rewind, tool changes and cancellation, keeping the stock and tool position synchronized.
- Verify the five fixed Accuracy levels across playback speeds and GPU memory limits.
- Verify STL export tolerances, units, closed surfaces, cancellation and import into CAD tools.
- Keep turning behavior covered by regressions while validating GPU milling removal and packaged Windows/Linux builds.
- Fix issues found during this phase before deciding on a release. The version number does not mark a published release or completed validation.

---

# After 2.1.0 — Product workflow expansion

The next stage is focused on features that reduce the need to leave Easy G-Code Plot for CIMCO, Vericut, or external helper tools.

## Priority A — Universal 2D Ruler + Insert Mesh into Plot View

**First priority for the next user-facing feature.** Provide a common way to measure NC toolpaths and STL geometry directly in the existing Plot View, including the machined stock obtained from three-axis simulation.

### Universal 2D Ruler

Extend the **existing Shift + Click 2D picker** instead of implementing an unrelated selection system.

- Support **Top, Front, Left, and Lathe** views.
- Select two geometry points and show their positions, the in-plane coordinate differences, and the straight-line distance in the current view.
- Use actual model/toolpath coordinates and the selected view's coordinate system, **not screen-pixel distances**.
- Work with CNC toolpath geometry and STL Objects in the Plot View.
- Support point selection on the **facets of transparent STL objects** and on **visible STL cross-section/clip contours**, respecting the current visibility and clipping state.
- Reuse existing picking where possible and provide appropriate geometry-based selection for mesh triangles and section edges.
- Show a clear visual ruler: first point, second point, connecting segment, and numerical result with units. Allow measurement reset/replacement without disturbing normal navigation.
- In Lathe mode, preserve the application's existing X radius/diameter presentation rules; do not silently mix radial and diametral values.
- Measurement interactions must not change the NC editor's caret, selection, or scroll position.

**Initial scope:** two-point linear measurements and coordinate differences only. Radius fitting, diameter detection, surface fitting, advanced dimensional inspection, and a separate measurement editor are **not** part of this first feature.

### Insert Mesh into Plot View

Add **Insert Mesh into Plot View** to the **3D Stock Removal context menu**.

- Capture the **current** machined-stock state at the active playback/TrackBar position.
- Reuse the existing GPU stock readback and STL mesh-construction path to build a mesh **in memory**.
- Insert the result directly into the existing **Plot View / STL Objects** workflow; do not require exporting and re-importing an STL file, and do not create temporary STL files.
- Preserve coordinates, units, orientation, and the current stock geometry so the inserted mesh aligns with the NC toolpath.
- Insert a **snapshot**, not a live link: subsequent playback or seeking must not silently alter the inserted object.
- Treat the result as an ordinary STL Object, so existing visibility, transparency, clipping/cross-section, object inspection, and the Universal 2D Ruler work the same as for imported STL files.
- Generate the mesh **on demand**, not during each simulation frame. Keep the GPU stock-removal playback path independent of mesh extraction.
- Respect the geometric resolution of the current simulated stock; do not claim finer dimensional accuracy than the source heightfield supports.

### Acceptance criteria

- A two-point ruler works on toolpaths in Top, Front, Left, and Lathe views.
- The same ruler works on imported STL objects, transparent meshes, and displayed section contours.
- **Insert Mesh into Plot View** transfers the stock at the selected simulation position without writing an STL file.
- The inserted mesh can be inspected and measured through the existing STL Objects workflow.
- Measurement coordinates and units are correct; ruler interactions do not disrupt CNC text editing, camera/navigation, or other Plot View tools.
- Existing GPU stock removal, turning behavior, and rendering performance remain unaffected.

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

# Priority order after 2.1.0

Recommended sequence:

1. Structured rotary kinematics editor extending the existing JSON workflow.
2. Embedded console panel.
3. Report templates.
4. Post-aware generators and additional NC templates.
5. Initial snippet presets.
6. Contour editor / DXF contour workflow.
7. Further stock shapes, collision checks and verified stock-simulation extensions.

The first five items mostly expose or extend capabilities already present in the architecture. Contour authoring and broader stock-simulation geometry remain larger follow-up tasks; the initial three-axis milling simulation is already implemented in 2.0.0.

---

# Development rule

For every new post-2.1 feature:

```text
existing kernel/service first
→ shared API/contract
→ GUI workflow
→ CLI/batch integration where relevant
→ regression tests
→ packaged-build verification
```

Avoid creating GUI-only implementations of logic that already belongs in the execution, export, tool, report, or generator layers.

The main objective after 2.1.0 is not feature count by itself. It is to make Easy G-Code Plot capable of covering a larger part of the real NC editing, analysis, conversion and preparation workflow without forcing the user back into another application for routine operations.
