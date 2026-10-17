# Easy G-Code Plot — Roadmap

## Current direction

Current development baseline: **2.8.0**. This is the current code baseline; publication/release status is tracked separately. Completed work belongs in [CHANGELOG](CHANGELOG.md), not in the list of future features.

The 2.0.0 GPU milling-stock milestone, the 2.1.x validation and workflow fixes, toolbar customization in 2.3.x and MDI/Compare in 2.4.0, and the first native Heidenhain iTNC 530 Klartext implementation and GUI stabilization in 2.5.0 are recorded in CHANGELOG.

Development now focuses on expanding useful NC workflows **without duplicating the execution engine, export formatting, or geometry logic**.

## Current baseline and known boundaries

- **CNC and GUI:** shared kernel/services behind CLI and PyQt6 GUI; multiple NC documents with isolated editor, execution, plot and stock state. The 2.5.0 work made MainWindow state ownership explicit and added real Qt regressions for Options and MDI, including stale-result protection.
- **Milling stock:** GPU-based three-axis height-field removal (OpenGL 4.3), playback and STL export. It supports the verified three-axis model; undercuts and tilted cutter removal are outside that model. Further geometry types require separate models and reference cases.
- **Heidenhain iTNC 530 input:** native Klartext lexer/AST and a defined execution subset, including L and supported circular motions, APPR/DEP, tool and spindle state. RND tangent arcs and CHF straight-line chamfers are constructed in the programmed contour before the existing RL/RR solver; block-local feeds and geometric errors retain source ownership. See [verified geometry and boundaries in the FAQ](FAQ.md#how-is-the-itnc-implementation-verified). The runtime executes bounded Q/QL/QR arithmetic, trigonometry, label calls/repeats and conditional flow. Current cycle coverage includes drilling/boring/tapping, DEF-active patterns 220/221, pockets 251/252 and thread milling 262. Pocket/thread cycles require XY/Z, R0 and configured cutter geometry; helical/reciprocating pocket roughing additionally requires an explicit tool ANGLE. Missing data and unsupported variants are diagnosed. Internal cycle passes still need independent controller references.
- **Heidenhain output:** an existing `heidenhain_itnc530` EXPANDED post target, distinct from native-source input coverage. Klartext FULL formatting remains unsupported; `.h` source filenames are preserved where applicable.
- **Generators:** existing hole/grid and pocket workflows emit **ISO G-code and native iTNC Klartext** where supported. The 2.5.0 work added native L/CR fragments and CC/CP helical output, with shared preview/generation validations. This is **not yet a general post-aware generator framework**.
- **Rotary kinematics:** configurable profiles and Options editing are implemented. Additional pivot/offset geometry and broader machine-layout verification are future work, not implicit support claims.
- **SINUMERIK milling cycles:** classic 01/2008 POCKET3/4, HOLES1/2 with supported MCALL drilling and CYCLE90 execute documented subsets. Extended pocket/thread signatures, preformed-blank variants and broader TCP/plane combinations remain outside that subset. Input execution does not expand the native output-post cycle vocabulary.
- **SINUMERIK turning:** bounded native XZ and ISO-T execution, including supported CYCLE93/95/97 and centerline drilling variants. CYCLE95 automatic nose compensation, controller-equivalent pass optimization, ISO turning canned cycles and a native Siemens turning output post remain future work; see [current coverage](FAQ.md#is-sinumerik-lathe-supported).

---

## Priority A — Integrated workflow tools

### Embedded console panel

Add an in-application console/dock for expert workflows without requiring a separate terminal. The console must call existing services or CLI contracts, **not** introduce a second G-code interpreter.

Candidate commands:

```text
analyze current
export expanded
show diagnostics
show tools
run batch
inspect post
inspect kinematics
```

Keep document selection, cancellation, output destinations and error reporting consistent with the current GUI and CLI.

### Report templates

Make HTML/statistics report presentation configurable without changing how metrics are calculated. Support:

- report title, header and company/project metadata;
- optional sections and table columns;
- per-tool statistics sections;
- units and precision;
- HTML styling and saved reusable templates.

Keep the report data model separate from templates, and preserve current HTML/CLI output behavior unless a template is explicitly selected.

---

## Priority B — Generators and reusable NC creation

**Keep this work on the roadmap.** Version 2.5.0 added iTNC output for existing hole/pocket calculator workflows; it did not complete the wider generator plan.

### Deterministic post-aware generators

Route NC emission through the selected post profile and the shared export formatting rules instead of adding a separate formatter for every generator or controller.

Requirements:

- deterministic output for each explicitly supported controller/profile;
- preserve the existing ISO and native iTNC workflows;
- share units, number formatting, address order and supported cycle conventions with export;
- keep geometric planning and live preview independent from textual NC emission;
- reject unsupported operations or post/profile combinations explicitly;
- test generated NC by parsing/executing it and comparing its geometry with the generator preview where meaningful.

Additional templates/workflows:

- hole patterns and grids, including post-specific canned-cycle emission;
- drilling cycles and tapping;
- thread milling;
- circular and rectangular pockets with finishing options;
- common milling approach/retract patterns.

### Initial snippet presets

Ship editable/removable starting presets for:

- FANUC Lathe;
- FANUC Mill;
- SINUMERIK Mill Native;
- Heidenhain iTNC Klartext **only for verified native syntax**, if useful.

Do not replace or overwrite users' existing snippets when installing or updating presets.

---

## Priority C — Heidenhain iTNC semantics beyond the current subset

The initial lexer, native AST, and bounded Klartext executor are already delivered. Future work should be driven by actual reference programs rather than a claim of complete iTNC compatibility.

RND/CHF geometry is implemented in 2.6.0 for planar local corners, including line/arc RND combinations. The reference corpus includes `6bas154.h` (explicit T4 Ø6 in regression setup) and the manual's `LINEAR` chamfer example. Version 2.7.0 adds the supported PLANE SPATIAL/RESET and AC/BC M128/TCPM input subset. Full-circle/multi-turn neighbors, spatial corners, ambiguous tangent solutions and corners that consume an entire neighboring element remain explicitly diagnosed boundaries; broader controller behavior requires independent reference cases.

- Extend the existing bounded Q/QL/QR expression and control-flow runtime with defined scope, limits and diagnostics.
- Independently confirm the implemented 220/221, 251/252 and 262 cycle geometry against documented examples and controller trajectories before treating it as reference behavior. Extend `LBL` and cycle coverage only from documented semantics and real use cases.
- Preserve native constructs in the AST; do not silently reinterpret unknown Klartext as FANUC/ISO.
- Maintain Python/Cython parity and separate input-support tables from postprocessor output-support tables.
- Extend GUI syntax/diagnostic integration together with the implementation, not before it.

---

## Priority D — Geometry authoring

### Contour editor

Add a dedicated, limited dialog for **NC contour construction** in milling and turning:

- manual coordinate entry;
- line and arc segments;
- DXF contour import;
- edit, reorder and delete segments;
- open/closed contour validation;
- preview before insertion or export.

Reuse existing geometric operations where possible. Do not turn this into a general-purpose parametric CAD subsystem.

---

## Priority E — Further stock-simulation development

The GPU three-axis milling simulator was introduced in 2.0.0 and subsequently validated and refined. Retain its working compute-shader architecture.

Possible extensions:

- additional stock shapes beyond the current rectangular blank;
- collision checks against remaining milling stock;
- indexed/multiaxis removal **only** after a suitable geometric model and independently verifiable reference cases are defined.

Do not replace GPU removal with a CPU implementation or treat performance optimizations as required without reproducible measurements. Keep numerical/geometrical correctness and real-program regression evidence as acceptance criteria.

---

## Rotary Kinematics — future geometry extensions

- Add rotary pivot locations and machine offsets **only** with a defined kernel contract and verified reference programs.
- Continue practical verification of available head, mixed table/head and angled configurations.
- Distinguish configured/available profiles from geometrically verified machine configurations in UI and documentation.

---

## Recommended sequence

1. Embedded console panel and report templates.
2. Post-aware generators and additional NC templates; initial snippet presets.
3. Verified extensions to native Heidenhain iTNC semantics.
4. Contour editor and DXF contour workflow.
5. Additional stock shapes, collision checks, and verified stock-simulation extensions.
6. Further rotary geometry only when supported by reference programs.

This order is a planning preference, not a promise of release versions. Small corrective work and regressions can proceed independently.

## Development rule

For each new feature:

```text
existing kernel/service first
→ shared API/contract
→ GUI workflow
→ CLI/batch integration where relevant
→ regression tests and real reference programs
→ packaged-build verification
```

Do not create GUI-only copies of logic owned by the CNC kernel, execution, export, tools, reporting or generator layers. Preserve the already validated GPU and CNC behavior, distinguish supported functionality from unmodeled controller semantics, and update CHANGELOG and bilingual documentation when functionality changes.

**Objective:** broaden real NC editing, analysis, conversion, preparation and verification workflows while keeping existing behavior reliable and the codebase maintainable.
