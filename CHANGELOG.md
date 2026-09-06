# Changelog

## 1.2.6 - Unreleased

- Run PyInstaller in a disposable `uv --isolated` environment so release packaging cannot mutate the developer `.venv` or leave a second project venv, while test, lint and sync scripts honor an explicitly activated environment.
- Reorganized the main-window GUI layer: `app/main_window.py` now composes focused file, editor, execution/playback and plot mixins under `app/ui/`, and the existing settings/grid/navigation helpers were moved into the same UI package.
- Replaced the stale `app/ui/untitled.ui` Designer source with the canonical `app/ui/generated/main_window.ui`, synchronized with the current editor, plot view, settings actions and two-toolbar layout.
- Fixed drag-and-drop to accept local files only and open the first dropped local file deterministically instead of silently using the last URL.
- Fixed stale toolpath display after edits by invalidating the previous execution/render state before the debounced auto-refresh; oversized, invalid or render-limited edits no longer leave an old trajectory visible.
- Fixed whitespace cleanup so multiple parenthesized comments on one line are preserved independently instead of being concatenated/duplicated.
- Hardened GUI export by aborting when execution fails and reporting output-file errors through the GUI.
- Added PySide6 6.11 as a development-only Qt code-generation toolchain plus PowerShell scripts for regenerating `.ui` and `.qrc` Python modules and converting generated imports back to PyQt6.
- Made Qt generation atomic and deterministic, with automatic `.ui` discovery, resource-manifest validation, path-independent execution, PyQt6 enum normalization and functional regression tests for changed or broken inputs.
- Kept PySide6 out of packaged builds by synchronizing the PyInstaller stage without the dev dependency group.
- Added separate Qt Designer-based `Tokens` and `Options` dialogs to the Settings menu instead of folding either feature into the main-window controller.
- Added a read-only Tokens diagnostic table backed by the existing parser AST and execution diagnostics, with detailed FANUC address groups, status coloring, live refresh, multi-row clipboard copy, CSV export and column reset.
- Added persistent General, Editor and Plot options for file encoding, default file type and units, logging, G41/G42 correction, arc tolerance, editor presentation, plot colors, line width, axes, and fixed/adaptive grid selection, with native color pickers and restore-defaults support.
- Exposed the current UI language in Options as a disabled selector pending complete runtime localization support.
- Simplified Settings menu labels, assigned F2 to Options, and added compact FANUC P1-P9 tip-orientation icons to the turning-tool editor and table without changing control or row heights.
- Matched Tokens validation colors to the Tkinter view: pale green for parsed rows and pale red for every suspicious row.
- Added a resource-backed Fit to View command to the plot context menu, centering the complete toolpath in turning mode and fitting milling bounds from all eight view-rotated corners with CNCEditor-compatible 0.9 padding.
- Added UTF-8 and Windows-1251 document loading and saving through the selected file encoding.
- Fixed the new Options integration so default editor mode persists, default units initialize execution until explicit G20/G21, editor font changes are reapplied to the active lexer, and correction/unit/arc-tolerance changes refresh the current execution instead of leaving a stale trace.
- Made the logging toggle functional with a per-user `main.log` and project-owned file handler instead of disabling the process-wide root logger.
- Fixed Tokens support classification to follow kernel diagnostics, include supported modal/cycle codes, and keep fractional G words distinct instead of coercing them through `int(float(...))`.
- Preserved pre-existing turning diagnostics when execution later fails, and removed duplicate cycle-budget checkpoints from G71/G72/G76 iteration paths.
- Added a Windows codegen regression that verifies committed Qt generated modules exactly match the current `.ui` and `.qrc` sources.
- Updated imports, tests and README for the new UI module layout and generation workflow.

## 1.2.5 - 2026-09-06

- Stopped coercing fractional G/M words to the nearest integer code; unsupported fractional controller codes are now preserved as distinct values and reported diagnostically instead of being executed as another command.
- Fixed relative-center export for turning G18 arcs with non-zero X starts by keeping diameter-space motion coordinates and physical/radius-space arc centers consistent.
- Added bounded trace rendering so point limits are enforced during arc/helix tessellation instead of only after the full sampled trajectory has already been created.
- Fixed `M98 ... L<n>` resource accounting so each repeated subprogram execution consumes the `subprogram_calls` budget.
- Fixed editor font persistence by using the same `EDITOR/FONT_*` settings keys for saving and loading.
- Reduced `main_window.py` by extracting existing settings persistence and plot viewport/navigation responsibilities without changing the current GUI behavior.
- Added regression coverage for fractional G/M handling, turning arc export, bounded rendering, repeated subprogram accounting and editor settings persistence.

## 1.2.4 - Unreleased

- Updated README and project documentation to reflect the current execution architecture, milling cutter compensation and tool configuration.

## 1.2.3 - 2026-09-05

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
