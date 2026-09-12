# Changelog

## 1.5.0 - 2026-09-12

- Reworked playback around an indexed logical-movement map: one trackbar position now represents one actual CNC movement while retaining the complete detailed `TraceMotion`/render range for OpenGL and Stock Removal. Arc tessellation and G71 offset-profile chords no longer inflate the slider, while real cycle and Macro B expansions remain individually playable.
- Split the legacy toolbar into independent File, Edit, CNC, View and Playback toolbars backed by the same `QAction` instances as the menus; added File Type, Fit to View and View 3D controls, standardized Paste on `Ctrl+V`, centralized icon sizing, and renamed the misleading `langCombo` to `fileTypeCombo`.
- Added persistent movable-toolbar layout using `QMainWindow.saveState()`/`restoreState()`, placed all toolbars in one row by default, and added `Reset to Default` to the toolbar context menu.
- Replaced the editor-centric Length status bar with execution-aware READY/UPDATING/OK/WARNING/ERROR/STALE state, machine mode, resolved units, source position, step/motion counts, diagnostic totals, execution time and transient progress/playback position. Cursor movement no longer reads the complete document.
- Reorganized Options into Designer-owned General, Editor, CNC / Execution, Plot and Colors tabs, with clickable color swatches plus validated hex fields, bounded numeric controls, safe handling of invalid persisted values, and correct OK/Cancel/Restore Defaults semantics without runtime layout construction.
- Made the X/Y/Z axis triad use fixed unlit colors so scene lighting and camera orientation cannot turn its arrows black, without changing STL, toolpath, Stock Removal or grid rendering.
- Added `Lathe Mode` to the view toolbar immediately before Refresh, added the resource-backed STL action beside Export Data before Undo, and placed File → Import STL directly above Clear STL.
- Added the `Show Stock` checkbox to Settings → Options → Plot immediately after Show canvas grid, with live preview/cancel handling and persistent visibility state; no separate Stock toolbar action is used.
- Added Lathe UI boundary handling for diameter-based X/I and WCS X values, disabled inapplicable WCS Y controls, and made X/Y/Z/I/J/K/F indicators follow the active G20/G21 units of each executed motion.
- Added relative I/K indication derived from resolved G18 arc centers for turning R arcs and generated contour motions, fixed Lathe source I/K semantics to relative offsets, and disabled the milling-only Settings → Arc Type menu in Lathe Mode.
- Added a bottom-left Inches switch to Toolpath Statistics that converts every displayed length, speed and XYZ bound without changing physical trace data or timing.
- Fixed G71 Type I roughing to finish with a complete contour-following pass along the signed U/W allowance profile before returning to the cycle start; OD positive U and ID negative U now leave material on the correct roughing side without duplicating the nominal finish contour.
- Fixed Stock outline settings and automatically inferred bounds being refreshed after program changes and Refresh, instead of updating only after accepting the Stock dialog.
- Fixed Lathe Play to build Stock Removal from the same current effective bounds as the visible outline, and changed Stop after Stock playback to restore the fully visible trajectory with the slider at 100%.
- Expanded application diagnostics for option changes, machine/view/playback transitions, execution and plot timing, and sampled Stock Removal performance; slow Stock frames report timeline/mesh timing, profile and mesh sizes without logging every frame.
- Added a shared Qt-free X/Z turning-tool geometry layer so the turning-tool preview and Stock Removal use the same cutter silhouette for OD80/ID80, OD35/ID35 and OD/ID groove tools.
- Changed OD80/OD35 P3 and ID80/ID35 P2 Stock Removal from the previous nose/width approximation to sampled polygon-footprint removal along the resolved `TraceMotion`, so insert angle, main-edge angle and nose radius affect the machined profile.
- Added OD Groove P3/P4 and ID Groove P1/P2 edge-reference selection, with legacy groove definitions defaulting to OD P3 and ID P2, and restricted the turning-tool editor to the valid orientation choices for each groove type.
- Changed unknown or unconfigured turning tools to leave stock unchanged instead of falling back to an implicit OD80 cutter; Stock Removal remains a geometric simulation and does not require spindle-running state.
- Added automatic turning-stock sizing from resolved G1/G2/G3 cutting motions, including cycle-generated motions and exact G18 arc extrema, while ignoring G0 positioning; the suggested bore remains zero by default.
- Added a lightweight stock outline to the normal Lathe Plot, included configured stock in Fit View bounds, hid the outline in milling and isolated Stock Removal playback, and restored it when returning to the normal lathe plot.
- Added Stock-dialog prefill from the current automatic stock suggestion without mutating persisted settings until OK is pressed, and refresh the suggestion after program or mode recalculation so stale dimensions are not reused.
- Added ordinary FANUC turning source-trace support for simplified `A`, `C` and corner-`R` programming, including compact blocks without spaces: `A` resolves the missing X/Z coordinate and `C`/`R` insert chamfer/fillet transitions through the same profile helper already used by cycle contours.
- Preserved G2/G3 `R` as arc-radius programming, applied source-unit scaling to direct-programming `C`/`R`, allowed a chamfer/fillet to consume an adjacent segment exactly, and rebuilt execution-step motion counts after inserted source transitions so playback and editor ownership remain aligned.
- Expanded regression coverage for OD/ID insert footprints, groove P orientations, reversible playback, unknown tools, automatic stock bounds/outline refresh, cycle-generated stock sizing, and ordinary source-trace A/C/R execution.
- Split the detailed user/developer reference from README into `FAQ.md`, added an offline Help → FAQ window below About, and embedded the FAQ in application resources for packaged builds.

## 1.4.2 - 2026-09-10

- Added turning Stock Removal playback driven by the resolved execution trace, with reversible OD/ID profiles, drilling, grooving, persistent stock dimensions and geometry-specific 3D tools for Face Groove, OD Groove, ID Groove, Drill, OD80/ID80 (5-degree edge) and OD35/ID35 (3-degree edge).
- Reset playback to the complete recalculated trajectory after source, mode or semantic setting changes so stale slider positions cannot hide updated geometry.
- Changed turning and milling execution to preserve trustworthy partial traces and continue after recoverable G-code, Macro B and unsupported position-changing blocks once absolute coordinates re-establish the affected axes.
- Changed invalid arc handling to skip only the unresolved motion while retaining later resolved motions.
- Separated execution traversal completeness from diagnostic success and exposed `complete` in CLI JSON output; resource limits and internal kernel failures remain terminal while preserving prior motions.
- Fixed turning G83 without Q so a new cycle does not invent or inherit peck depth, and modeled G84 tapping as a single feed stroke with return motions.
- Preserved nominal turning geometry when configured G41/G42 tool data is invalid, reporting unverified compensation instead of discarding the trace.
- Replaced modal GUI execution-error dialogs with status-bar diagnostics and preserved the existing Plot when a failed refresh produces no usable trace.
- Made Linux release creation stop immediately when lint fails.
- Refactored G-code export by output mode so Full Program, Expanded Execution and Plot Data no longer share incompatible coordinate/arc settings.
- Fixed Full Program and Expanded Execution WCS serialization by converting generated machine-space trace geometry back into the active preserved G54-G59 coordinate system without removing WCS selection.
- Fixed turning WCS arc-center conversion by applying the configured X offset in physical radial-X space.
- Fixed turning Expanded incremental output to use U/W rather than milling-style G91 with X/Z deltas.
- Fixed R arc export so resolved full circles are serialized as two exact R semicircles instead of producing an unrepresentable single R full circle or switching center representation.
- Fixed Expanded source-unit/X-mode serialization and made Plot Data ignore stale incremental settings.
- Increased generated export-geometry precision to six decimal places so inch output combined with nonzero WCS does not shift the reconstructed Plot through three-decimal rounding.
- Disabled Arc Output selection for Lathe Expanded export; generated turning arcs use relative I/K only.

## 1.4.1 - 2026-09-09

- Added a translucent milling-tool preview that follows logical playback, rendering configured flat, bull-nose and ball-nose mills plus drills with 120-degree points, with a persistent Plot color setting.
- Added a persistent five-level playback-speed slider using CNCEditor's 1000/250/100/40/10 ms logical-motion intervals.
- Fixed milling IJK arc handling so rounded real-world arc coordinates are no longer rejected solely because the start and end radii differ slightly.
- Fixed IJK arcs being discarded when Radius source mode is selected but the source block contains IJK coordinates and no R value.
- Removed the unconditional `UNVERIFIED_TOOL_LENGTH_COMPENSATION` warning emitted for every milling `G43` block.
- Changed the default arc source mode from absolute-center coordinates to incremental IJK coordinates.
- Added a true zero-motion playback state: Stop now returns to the program start before the first motion, and the playback slider starts at zero.
- Preserved the current playback position when the toolpath is refreshed or re-executed instead of always jumping to the end.
- Paused playback automatically when stepping forward or backward manually.
- Fixed playback timer handling so unrelated Qt timer events no longer advance CNC playback.
- Made lathe/mill mode switching rebuild the toolpath without showing execution-error dialogs during the automatic refresh.
- Improved milling-tool validation: invalid diameters and lengths, non-finite values, and impossible bull-nose corner radii are now rejected.
- Improved file handling with NC-specific Open/Save filters, automatic `.nc` extension for unnamed NC files, corrected DXF extension handling, and atomic file writes.
- Added protection against overwriting files that were modified externally after being opened.
- Fixed recent-file path normalization on Windows.
- Fixed Find, Replace and Replace All behavior, including empty-search handling, case-insensitive replacement, preserving editor selection/cursor state, and grouping Replace All into a single undo action.
- Changed Export and Block Number dialogs so edited settings are applied only after pressing OK; Cancel now leaves existing application settings unchanged.
- Fixed swapped icons for Remove Empty Lines and Remove Spaces.
- Restricted application file logging to the `app` logger instead of modifying the root Python logger, and made legacy-config migration failures non-fatal.

## 1.4.0 - 2026-09-08

- Added ASCII and binary STL import as a persistent 3D overlay alongside the executed toolpath, with File menu, toolbar and direct `.stl` file-open integration.
- Added solid and feature-edge STL rendering modes with configurable persistent model color and explicit Clear STL support.
- Included imported STL geometry in Fit to View and scene bounds so the camera fits the complete toolpath/model combination instead of the toolpath alone.
- Reworked STL rendering around a persistent OpenGL overlay so camera and view changes reuse the existing mesh instead of rebuilding `MeshData`, face colors and scene items.
- Optimized STL loading and rendering with vectorized binary parsing and normal normalization, cached wireframe feature edges and cached toolpath bounds.
- Added true orthographic projection for Top, Front and Left milling views while retaining perspective projection for the standard 3D view, eliminating depth-precision artifacts caused by the previous near-zero-FOV perspective approximation.
- Added persistent optional gradient plot background and STL appearance controls to Plot options, with improved default grid contrast.
- Corrected OpenGL depth/render ordering for the grid, STL model and coordinate-axis triad so solid geometry occludes hidden surfaces correctly while the axis triad remains visible as a screen-oriented overlay.
- Added DXF export of the resolved motion trace with analytical lines, arcs and circles, separate rapid/cutting layers, Plot-aligned Z/X turning coordinates and 3D milling entities.
- Replaced the oversized statistics message box with a reusable, resizable report window containing a read-only scrollable text view.
- Automatically fit the camera to the complete scene after a newly loaded CNC program finishes building its toolpath.
- Reworked Expanded Execution export around execution-step events so tool changes and repeated subprogram boundaries retain runtime order, sequence numbers include executable events, and the program number precedes the analysis banner.
- Preserved WCS selection, G28/G53, G32/G33 threading, G4 dwell, spindle mode/speed/direction and coolant controls in Expanded Execution output, with WCS-aware coordinates.

## 1.3.0 - 2026-09-08

- Added deterministic execution events for program start/end, subprogram start/end, tool changes and home returns across turning and milling execution.
- Exposed execution events through `ExecutionResult`, per-step execution snapshots and CLI JSON output.
- Reworked full-program exporters to use execution events for program/subprogram boundaries, program termination and home-return preservation instead of re-detecting those structures from source text.
- Corrected milling tool semantics so `T` preselects a tool and `M6` emits the actual tool-change event and activates it; split `T`/`M6` blocks no longer assign the new tool to intervening motions.
- Classified milling `G53` as a home-return event only when the addressed machine-coordinate axes deterministically target configured home, including non-zero active WCS offsets.
- Replaced per-frame toolpath array rebuilding with a persistent VBO-backed `GL_LINES` item inside the existing pyqtgraph `GLViewWidget`; playback now changes only the visible logical draw prefix.
- Replaced the three origin-axis lines with a fixed-screen-size 3D axis triad at CNC coordinate zero, with arrowheads and X/Y/Z labels.
- Preserved execution-step ownership through milling cutter compensation so inserted corner transitions export correctly without stale motion counts or repeated G41/G42 compensation.

## 1.2.7 - 2026-09-07

- Added persistent Auto Update controls, including a configurable sampled-segment limit after which plot refresh requires the manual Update action.
- Added staged progress reporting for manual updates of long files; the status-bar indicator remains hidden during idle and ordinary short updates.
- Kept the editor caret and trajectory slider stable while edited source is waiting for recalculation, and preserved the previous plot until a successful refresh replaces it.
- Synchronized machine-specific GUI capabilities so Turning Tools and Milling Tools follow the active execution profile while arc interpretation and tolerance remain available for both turning and milling.
- Added turning G2/G3 regression coverage for relative I/K, absolute I/K and R arcs in both diameter and radius X programming modes without changing existing kernel normalization.
- Removed the dead downstream `arc_type` API from trace rendering, geometry statistics and export consumers; source arc interpretation now exists only at kernel execution.
- Reworked the export dialog into four logical output types with separate G90/G91 and arc-representation controls for expanded execution output, preserving the existing full-program and plot-data exporters.
- Expanded Tokens regression coverage for Macro B flow, grouped modal words, unverified/unsupported diagnostics, fatal execution and partial turning traces.
- Unified GUI and CLI NC-file decoding through one explicit UTF-8/Windows-1251 loader contract and added a CLI `--encoding` option.
- Required the release version passed to `scripts/ps1/release.ps1` to match `pyproject.toml` before creating a commit or tag.
- Made CI static checks blocking and migrated legacy `config.ini` discovery away from process CWD to the stable application directory.
- Restored the 256×256 logo in the About dialog by adding it to the compiled Qt resources and making resource-manifest validation UTF-8-safe.

## 1.2.6 - 2026-09-06

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
