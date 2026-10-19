# Easy G-Code Plot — Roadmap

## Current direction

Current development baseline: **2.9.0**. Release status and completed changes are recorded separately in [CHANGELOG](CHANGELOG.md).

The application has a shared CNC kernel and services used by the PyQt6 GUI and CLI. Further development should reuse execution, geometry, export and diagnostics rather than duplicate them.

### Current boundaries

- **NC languages:** FANUC/ISO, supported SINUMERIK milling/turning subsets, and native Heidenhain iTNC 530 Klartext. Unsupported controller constructs must be reported explicitly.
- **Simulation:** GPU-based three-axis milling-stock removal, with playback and STL export. Tilted-tool removal and undercuts are outside the verified model.
- **Generation:** hole/grid and pocket tools already generate supported ISO G-code and iTNC Klartext; a general post-aware generator pipeline is not yet implemented.
- **Rotary kinematics:** configurable profiles exist, but not every machine configuration has verified geometry.

## Priority A — Post-aware generators and NC presets

Use the selected post profile and existing export formatting for generated NC programs, without adding per-generator formatters.

- Reuse the existing rules for units, numeric formatting, address order and supported cycles.
- Keep geometric planning and preview separate from NC text generation.
- Explicitly reject unsupported post/operation combinations.
- Verify generated programs by parsing/executing them and, where applicable, comparing their geometry with the preview.
- Extend practical workflows: hole patterns, drilling/tapping, thread milling, pockets and approach/retract paths.
- Extend the existing FANUC Mill/Lathe, SINUMERIK Mill/Lathe and iTNC Klartext snippet libraries with verified operations and validated fields. Current templates, pictures and insertion behavior are described in [FAQ](FAQ.md#where-are-snippets-stored).

Keep library opening non-destructive. The existing explicit Update Defaults action restores standard text and deleted standard entries only for the selected controller, retains custom-named records and existing pictures, and fills missing bundled diagrams.

## Priority B — Verified Heidenhain iTNC 530 extensions

Extend the existing native Klartext lexer, AST and execution subset only where documented semantics or real reference programs support the behavior.

- Expand bounded Q/QL/QR expressions and control flow with clear limits and diagnostics.
- Validate cycle 220/221, 251/252 and 262 trajectories against independent references before expanding cycle coverage.
- Investigate remaining RND/CHF, spatial corner and PLANE/TCPM limitations using reproducible examples.
- Preserve native constructs; do not interpret unsupported Klartext as FANUC/ISO.
- Maintain Python/Cython parity and separate input support from output-post capabilities.
- Update GUI highlighting and diagnostics together with verified parser/executor changes.

## Priority C — Contour editor and DXF import

Add a focused contour-construction workflow for milling and turning:

- Manual coordinate entry and line/arc segments.
- DXF contour import.
- Editing, reordering and deleting segments.
- Open/closed contour checks and preview before insertion or export.

Reuse existing geometry services. Do not build a general-purpose CAD subsystem.

## Development rules

For every feature: **reuse the kernel/service → define the shared contract → integrate the GUI and CLI where relevant → add regression tests → verify packaged builds**.

Keep GPU simulation and existing CNC behavior intact. Base extensions on verified reference programs and update CHANGELOG and the relevant documentation when behavior changes.
