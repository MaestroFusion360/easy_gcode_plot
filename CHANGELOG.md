# Changelog

## 1.2.3 - Unreleased

- Stabilized the execution pipeline around one runtime `ExecutionResult` with resolved modal state, machine signals and execution occurrences; removed duplicate turning execution/scanning paths.
- Moved analytical arc resolution into the kernel, removed consumer-side I/2I best-fit heuristics, and fixed resolved-arc export across unit/coordinate conversions.
- Hardened runtime semantics for subprogram state, unsupported position-changing G-codes and cycle/resource limits with explicit structured diagnostics.
- Updated statistics to use physical turning geometry and executed feed/spindle state, reporting unresolved machining time as unknown instead of guessing.
- Restored milling cutter-compensation visualization for configured G17 line/arc/helix paths and standardized milling tool identities to compact `T1`-`T99`.

## 1.2.2 - Unreleased

- Fixed FANUC milling `G53` handling. `G53` is now executed as a non-modal move in machine coordinates instead of being treated as an unsupported G-code.
- Preserved the currently active `G54-G59` work coordinate system across `G53`; subsequent milling moves return to the active WCS normally.
- Fixed milling diagnostics so unsupported or currently unmodeled G-codes no longer discard an otherwise valid Motion Trace.
- Changed unknown milling G-codes to informational `UNVERIFIED` warnings instead of fatal execution errors where safe to continue.
- Made unknown `M00-M199` codes non-fatal for visualization and trace execution; unsupported M-codes are reported without breaking the remaining program plot.
- Preserved all successfully resolved motions before and after unsupported controller words instead of returning an empty trace.
- Added regression coverage for `G53` machine-coordinate motion and tolerant handling of unknown G/M codes.

## 1.2.1 - 2026-09-04

- Updated application icons `app/resources/icons/logo.png` and `logo.ico`.
- Refactored the About dialog into a dedicated Qt Designer form and generated PyQt6 UI module.
- Updated the About dialog layout, application description, MIT license text and copyright information.
- Added persistent WCS configuration for `G54-G59` with full `X/Y/Z` offsets and configurable `G28` home coordinates.
- Extended WCS handling so milling uses full XYZ offsets while turning continues to use the relevant X/Z components.
- Fixed the public milling execution path so configured `wcs_offsets` are passed into the milling kernel.
- Split the previous generic Tools dialog into separate `Turning Tools` and `Milling Tools` dialogs.
- Moved `WCS`, `Turning Tools` and `Milling Tools` from `CNC Functions` to the `Settings` menu.
- Added persistent milling tool definitions with tool type, diameter, corner radius, length and description.
- Added milling tool presets for flat end mills, bull-nose mills, ball end mills and drills.
- Kept milling tool configuration informational only; it does not modify Motion Trace or milling geometry.
- Retained turning tool settings for the existing tool-nose compensation workflow.
- Regenerated Qt resource bindings so updated application artwork is used by the packaged UI.

## 1.2.0 — 2026-09-04

- Added source-aware expanded program export for both machine modes: `EXPANDED TURN PROGRAM` in Lathe Mode and `EXPANDED MILL PROGRAM` in Milling Mode; CLI `--mode program` supports both languages while `--mode cycles` remains turning-only.
- Rebuilt turning program export around actual execution-step order instead of `TraceMotion.source_block`, so G72/G73 profile provenance and repeated subprogram execution do not corrupt ordering.
- Preserved `M2`/`M02`/`M30` exactly, kept short and packed T words unchanged, and preserved source controller words such as G50/G96/G97/G98/G99 in expanded turning output; preservation is pass-through and does not imply complete execution semantics for those controls.
- Preserved source unit mode by scaling normalized trace geometry back to the active G20/G21 units at each executed block.
- Added one logical cycle group per executed cycle invocation, including G72/G73 and finish cycles.
- Added Shift+Click trajectory picking in turning and milling orthographic 2D views with source-line/playback synchronization.
- Rendered G0 rapid motions separately in red while preserving the configured cutting-path color.
- Added persistent File -> Recent Files MRU handling with missing-file cleanup and Clear Recent.
- Made the playback cursor a small fixed-pixel marker so its apparent size no longer changes with zoom.
- Replaced the GUI-owned parallel `lst*` CNC execution model with a shared native Python `ExecutionResult`/logical Motion Trace.
- Added a staged lexer/AST/semantic execution kernel and standalone CLI for `fanuc_turn` and `fanuc_mill`.
- Integrated FANUC turning cycles G70–G76, modal turning cycles, G83/G84, Macro B/control flow, M98/M99, WCS/reference handling and tool-nose compensation.
- Added native XYZ milling trace execution with G17/G18/G19 arcs/helixes and drilling cycles.
- Added source-aware expanded milling-program reconstruction in actual execution-step order, including canned-cycle expansion, repeated M98/M99 execution, comments, T/M6, S/M, WCS, G43/H controls and exact M2/M02/M30 preservation.
- Made unmodeled milling G41/G42 cutter-radius and G43 tool-length geometry explicit: their modal state is tracked and the resolver emits `UNVERIFIED` warnings instead of silently treating the geometry as fully modeled.
- Added fail-closed handling for undefined macros and unknown/reference-changing coordinate semantics; G30 no longer reuses the primary G28 reference implicitly.
- Preserved repeated address words/modal G codes in source parsing.
- Kept arcs logical until rendering/export sampling and moved statistics to the authoritative trace.
- Reworked GUI playback/source synchronization around logical motions and indexed source mapping.
- Replaced the legacy exporter with a trace-based exporter while retaining GUI arc-format, incremental, sequence, header/footer and safety-line options.
- Added machine signals/program-end data to execution results.
- Removed the legacy `app/gcode/processing.py` execution engine and duplicate kernel export/statistics paths.
- Expanded regression coverage against donor FANUC turning/milling programs.
