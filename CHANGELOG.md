# Changelog

## 1.6.2 - 2026-09-23

- Added a machine-neutral cycle execution contract while preserving machine-specific expansion models. Milling canned cycles now return geometry, signals, modal updates and position updates as one atomic outcome built against temporary state; the existing turning expansion pipeline is connected through an adapter without rewriting G70-G76 semantics. Cycle implementations now live under canonical `turning/cycles` and `milling/cycles` packages, with historical import paths retained as aliases.
- Added FANUC milling `G16/G15` polar-coordinate programming with `G17/G18/G19` plane selection, absolute/incremental radius-angle commands, WCS/local-origin and current-position pole selection, canned-cycle positioning, R-format circular interpolation, coordinate-transform integration and Python/native execution parity. Turning remains unchanged.
- Added FANUC Macro B vacant-variable semantics for `#0` and omitted G65 arguments, indirect `#[expr]` assignment, and shared immutable variable snapshots that avoid duplicating unchanged macro state across execution steps.
- Fixed milling `G10` under `G91` to increment existing L2/L20 work offsets instead of silently replacing them.
- Fixed two-line turning `G76` so the packed tool-angle digits now produce FANUC single-edge flank infeed for the supported 0/29/30/55/60/80-degree set instead of being silently ignored; unsupported angles now fail explicitly.
- Expanded modal conflict validation for milling tool-length compensation, scaling and rotation plus turning spindle modes, and added an explicit `UNSUPPORTED_G72_TYPE_II_SPANS` failure for ambiguous multi-span facing profiles.
- Refactored kernel execution without intentional CNC semantic changes: milling now uses named evaluation/validation/state/flow/motion phases with a single block finalizer, while turning machine-specific operations are grouped behind one execution-semantics contract instead of a growing callback list.
- Added a standalone `Tool List` CNC function that reuses resolved per-tool statistics to produce a CIMCO-style UTF-8 text report with program/file metadata, configured tool geometry and exact per-tool Z minimums.
- Fixed turning `G53` fail-open behavior for arc modes. `G53 G2/G3` now reports `UNSUPPORTED_G53_MOTION` and skips the complete block instead of silently executing a WCS-relative arc.
- Expanded the Tokens diagnostic window into `Tokens/Macro Variables` with a read-only Macro Variables inspector driven by execution-step snapshots. The inspector follows the current logical playback position, shows only variables that actually exist at that point, includes active G65 local-variable scopes and restored caller values after M99, updates during playback/step/slider navigation without re-executing the program, and works consistently for turning and milling Python/native execution paths.
- Added a persistent CNC comment-style selector under `Options -> CNC / Execution`. Parenthesized comments remain the default, while semicolon comments can now be selected consistently for editor lexing, generated statistics and every text export mode; existing source programs using either syntax remain readable.
- Improved export failure reporting with an always-visible, copyable diagnostics field containing severity, diagnostic code, source line, explanation and the offending G-code block, so incomplete or invalid executions no longer require opening Tokens or relying on the temporary status-bar message.
- Fixed `MILL FULL PROGRAM` export so the Delimiter option is also applied to retained controller blocks such as compact `G0G91G28Z0`, producing `G0 G91 G28 Z0` consistently with generated motion blocks.
- Localized the dynamic Recent Files menu, including its empty state and clear-list action, for the Russian interface.
- Fixed the Windows complexity-check script failing in project paths containing Cyrillic characters by decoding Ruff's JSON output explicitly as UTF-8.

## 1.6.1 - 2026-09-22

- Fixed milling `G84` tapping so withdrawal from depth is emitted as synchronized feed motion instead of rapid motion.
- Added turning `G53` non-modal machine-coordinate motion while preserving the active WCS for subsequent blocks.
- Added machine-specific modal-group validation for the supported code set. Conflicting codes now produce `MODAL_GROUP_CONFLICT` and the complete block is skipped instead of silently applying the last code.
- Corrected the shared AST so milling `G90/G94` are not classified as turning cycles, and preserved `Y/J/V` plus coordinate-only modal motion blocks with Python/Cython parser parity.
- Added kernel/API support for `G54.1 P1-P99` through `extended_wcs_offsets`, and `G10 L2 P1-P6` / `G10 L20 P1-P99` runtime work-offset programming without requiring UI configuration.
- Modeled milling `G82` dwell, `G84` spindle synchronization/reversal and `G86` spindle-stop signals. The high-speed `G73` retract distance is now configurable through `milling_g73_retract_distance` instead of being hardcoded in cycle expansion.
- Fixed Lathe Mode zoom so perspective zoom no longer stalls at the intentionally near-orthographic `0.01` FOV limit. Turning zoom now changes camera distance while preserving the existing projection, orientation and visual appearance; milling 3D keeps its previous FOV-based zoom behavior.
- Made the WCS dialog vertically compact and resizable instead of enforcing the previous oversized minimum height.
- Fixed missing `QDoubleSpinBox` up/down arrows in the Windows 10 dark-theme fallback. Spin-box buttons now keep native Windows geometry while the dark compatibility style explicitly renders visible arrows; the Windows 11 native dark-style path is unchanged.
- Added regression coverage for Lathe Mode zoom behavior, preserved turning camera FOV/orientation, compact WCS sizing and Windows 10 dark-theme spin-box arrow rendering.

## 1.6.0 - 2026-09-21

- Added FANUC `G65` custom-macro calls for turning and milling: `P` target selection, `L` repetition, Type I/II address-to-`#1..#33` argument binding, four macro-local nesting levels, local-variable restoration on `M99`, and shared execution/export events. `G65` argument words are isolated from normal motion, feed, spindle, M-code and tool-selection side effects; Python/Cython parsing and tool discovery follow the same rule. `G66/G67` remain intentionally out of scope for this release.
- Removed the obsolete installation-directory `config.ini` and its first-run migration; `%APPDATA%/easy-gcode-plot/config.ini` is now the only settings file and clean-profile defaults come exclusively from code.
- Added persistent arc-sampling presets and maximum radius, minimum radius and minimum chord length controls under `Options -> CNC / Execution`; GUI trace generation now applies them per arc to reduce unnecessary render points in large programs without changing CNC execution geometry.

## 1.5.9 - 2026-09-20

- Localized every user-visible Toolpath Statistics report label for the Russian UI while preserving the existing English report text, values, units and statistics calculations.
- Fixed PyInstaller packages failing at startup with `ModuleNotFoundError: app.gcode.export` by explicitly collecting the canonical exporter package referenced through the legacy lazy module aliases.
- Added a persistent **Maximum generated motions** setting to `Options -> General`; it controls the kernel-wide generated-motion resource limit for both turning and milling executions and defaults to 200,000.
- Added a separate Cython tool-discovery scanner that performs line/comment scanning, literal T recognition, G20/G21 unit tracking and operation inference in one native pass while preserving the existing Python `refresh_setup()` orchestration and scanner fallback.
- Made debounced editor Auto Update non-modal so typing remains usable during recalculation; edits made during an active refresh cancel the stale run, queue another refresh and prevent stale results from replacing the current plot.
- Added a Cython native parser that accepts the complete G-code source in one call, scans lines, comments, words, numeric values, labels and flow constructs in compiled code, and produces the existing `Program`, `Block`, token and AST object model without changing CNC semantics.
- Added a Cython native milling executor for contiguous ordinary literal/modal blocks, eliminating per-line Python/native transitions while retaining the existing Python interpreter for Macro B, cycles, transforms and other complex behavior.
- Kept authoritative Python fallbacks for unsupported or complex input and for source environments where native extensions have not been built; cancellation checkpoints remain active in both execution paths.
- Fused ordinary parsing and AST construction, added faster literal-word evaluation and reduced repeated scans and temporary allocations during program indexing and tool discovery.
- Reduced interpreter and post-processing overhead by avoiding unchanged dataclass replacements, empty signal/flow allocations and unnecessary coordinate-transform work, and by rebuilding emitted-motion counts only when they change.
- Added scoped cyclic-GC deferral around construction and execution of the large, predominantly acyclic CNC object graph, restoring the caller's previous GC state on every exit path.
- Added slotted high-volume frontend and execution dataclasses to reduce allocation size and attribute-access overhead without changing equality, immutability or public result types.
- Changed the GUI execution path to omit the optional full instruction list when it is not consumed, while preserving instructions for API and CLI callers that request them.
- Consolidated tool discovery so source parsing results are reused instead of performing redundant full-file passes.
- Improved the 77 MB / 2,577,485-line FANUC milling reference workload from approximately 110.7 seconds to 25.3 seconds at the 200,000-motion limit (about 4.37x overall on the reference machine).
- Verified native/Python parity across every block and AST node in the reference file, label indexes and complete limited execution results, including motions, steps, diagnostics, events, signals and final state.
- Added native-acceleration regression tests comparing the compiled parser and milling loop with their Python fallbacks; unbuilt source checkouts skip only the native-specific tests.
- Added Cython to the PEP 517 build requirements and configured setuptools to compile `_native_parser.pyx` and `_native_executor.pyx` into platform-specific `.pyd`/`.so` modules.
- Kept generated Cython `.c`, `.pyd` and `.so` artifacts out of version control; clean wheel builds start from the tracked `.pyx` sources and include both compiled extensions.
- Added matching `build-native.ps1` and `build-native.sh` helpers that maintain a persistent `.venv-build`, rebuild native extensions when build inputs change, support an explicit refresh and verify both extension imports.
- Made the PowerShell and shell PyInstaller workflows reuse the isolated `.venv-build`, validate native acceleration before packaging and skip dependency synchronization when the locked build inputs are unchanged.
- Documented compiler prerequisites, native build verification, source-tree startup and the behavior of prebuilt Windows releases.

## 1.5.8 - 2026-09-20

- Added persistent **Autodetect Arc Type** under `Settings -> Options -> CNC / Execution` for milling. Execution inspects the already parsed unresolved motion stream, skips R-only arcs while detecting, compares relative-IJK and absolute-center radius consistency against the configured arc tolerance, fixes one effective IJK mode for the whole run and falls back to the manually selected Arc Type when the program remains ambiguous. Turning and Arc Output export semantics are unchanged.
- Added persistent **Ignore Block Skip** under `Settings -> Options -> CNC / Execution`. When enabled, leading `/` blocks are excluded consistently from turning and milling execution, Macro B side effects and Expanded Execution export without modifying the source file; the existing execute-by-default behavior remains the default.
- Fixed the cancellable CNC execution dialog so it remains visible through actual plot publication instead of closing when only the worker portion finishes. Cancel now uses the same cooperative token during tool discovery, streaming source parsing, AST/index construction, kernel execution, trace sampling and GUI geometry publication.
- Removed whole-file `splitlines()` copies from kernel parsing and tool discovery, added bounded cancellation checkpoints to the previously non-cancellable passes and verified responsive cancellation with a 77 MB / 2.57 million-line milling program.
- Fixed the execution dialog's dark-theme client area and first-frame painting so Windows no longer exposes a blank white interior before the dialog contents are rendered.
- Improved the execution status bar with spacing between fields, explicit `Errors`/`Warnings` labels, diagnostic detail tooltips and compact second-based timing for long executions.
- Made the built-in FAQ a normal resizable/maximizable window, added document-aware heading/paragraph spacing without modifying `FAQ.md`, preserved anchor navigation and made the packaged `LICENSE.md` link open correctly.
- Reduced avoidable Turning Stock Removal overlay work and removed noisy slow-frame warnings when no actionable slowdown is present.
- Refactored `app/gcode/kernel` without adding new G-code functionality or intentionally changing CNC execution semantics; the change consolidates common mechanics left from the historically separate turning and milling implementations.
- Added shared machine/runtime state primitives for unit mode, active WCS/tool, feed mode/feed and spindle state, and removed the duplicate turning cycle-state synchronization path.
- Consolidated common program execution plumbing for Macro B evaluation/control flow, block evaluation/classification, execution guard/program counter, subprogram call stack and M98/M99/M2/M30 flow events.
- Consolidated turning and milling reference-return path generation through a machine-neutral two-stage home-return helper.
- Consolidated WCS rebasing helpers and grouped milling G52/G68/G69/G51/G50 modal transform state behind one `TransformState` while preserving the existing transform semantics.
- Consolidated axial drilling/peck/retract/return mechanics in shared runtime helpers and reused them from milling drilling cycles and turning peck/tapping paths. Existing milling G73/G81-G86 geometry is preserved; this refactor does not add G87-G89 or new dwell/spindle cycle semantics.
- Reduced duplicated turning-cycle expansion code across G71/G72/G73 profile preparation, G74/G75 pecking, G83/G84 drilling/tapping state handling and G90/G92/G94 rectangular-cycle mechanics.
- Reduced duplicated geometry/profile clipping helpers and repeated milling execution-step/event bookkeeping.
- Kept threading, drilling, turning and milling machine-specific semantics in their existing domains while moving only shared mechanics into common runtime helpers, preparing the kernel for later G65 and G66/G67 work.
- Fixed milling G41/G42 compensation for planar full-circle G2/G3 motions so the compensated path remains active through the final circle until the following G40 exit; added a regression using `tests/fixtures/milling/macro_boss_milling.nc`.
- Fixed the Russian Stock dialog unit suffix regression: the `" mm"` source now translates to `" мм"` (without quotes), and the compiled catalog is re-embedded into the Qt resource so the translation is actually applied at runtime.
- `generate-translations.ps1`/`generate-translations.sh` now refresh the generated Qt resource (`files_res.py`) after compiling `.qm` files, so running only the translation step can no longer leave a stale embedded catalog.
- Localized standard `QDialogButtonBox` controls (`OK`, `Cancel`, `Close`, ...) centrally by installing Qt's own `qtbase_<language>.qm` catalog alongside the application translator instead of adding per-dialog `setText()` calls.
- Restored the `Inches` display switch in the Turning and Milling tool editors and added regression coverage that it only changes the displayed units while stored geometry stays metric.
- Fixed dark-theme spin-box controls: the legacy Windows dark fallback now applies a shared `QAbstractSpinBox` stylesheet so the frame and up/down arrows stay readable instead of rendering black on the dark background.

## 1.5.7 - 2026-09-18

- Refactored the CNC core without changing existing execution semantics: the former flat `app/gcode/kernel/` modules are now grouped into `api/`, `frontend/`, `geometry/`, `lathe_cycles/`, `compensation/`, `runtime/` and `milling/` packages.
- Split the largest kernel modules into focused files for cycle expansion, interpreter dispatch/execution, profile geometry, milling state/motion/drilling and compensation geometry.
- Split G-code/DXF export into the `app/gcode/export/` package while keeping export behavior based on the authoritative `ExecutionResult`/resolved trace.
- Added milling `G73` high-speed peck drilling with short intermediate retracts while preserving existing `G83` full-retract behavior.
- Added a reusable milling coordinate-transform layer and FANUC-style `G52` local coordinate-system shifts. `G52` changes transform state without moving the tool.
- Added milling `G68`/`G69` coordinate rotation around a programmed center. The control blocks do not create motion, and the active rotation is applied to subsequent endpoints and I/J/K arc vectors.
- Added milling `G51`/`G50` coordinate scaling. `G51` supports a uniform `P` factor or per-axis `I/J/K` factors around the programmed center, while `G50` cancels scaling; neither control block creates a motion segment.
- Fixed milling `M98`/`M99` execution so a subprogram inherits the caller's current position and complete modal/coordinate-transform state, returns to the caller without synthetic connector motion, and resumes execution with the resulting state.
- Fixed main-program completion when subprogram definitions follow `M30`, allowing the authoritative execution result to remain valid and complete for UI and DXF export.
- Fixed milling `G41`/`G42` contour construction across line/arc junctions, corners and `G40` exit so compensated primitives remain continuously joined without artificial diagonals between source and compensated geometry.
- Added an end-to-end `flange_plate_benchmark.nc` integration test covering subprogram execution, compensated-contour continuity and non-empty DXF generation through the production execution path.
- Fixed lathe Auto Stock so the calculated Z bounds come from the actual toolpath instead of incorrectly exposing the default `2 mm` Z allowance for programs located entirely in positive Z.
- Renamed the turning-only cycle implementation package to `lathe_cycles/`, updated its consumers, and added regression checks for the canonical package layout and representative turning/milling execution paths.
- Remapped the complexity baseline to the new module paths without relaxing the recorded complexity thresholds.

## 1.5.6 - 2026-09-17

- Added a Russian user interface. The language is selected in `Settings -> Options -> General` and applied after restarting the application; English technical logging, kernel diagnostics and G-code comments are intentionally unchanged.
- Added a `Light`/`Dark` theme selector next to the language option. The application uses Qt's native color-scheme support with a palette fallback, plus editor and plot colors; standard plot colors follow the active theme while user-customized plot colors are preserved.
- Light and Dark use the native platform `QStyle` where it supports the requested scheme. Windows 11 keeps Qt's native Windows 11 style; Windows 10 falls back from the legacy `windowsvista` style to the palette-aware `windows` style in Dark mode because the native Vista theme engine can otherwise leave menus, toolbars and input controls light. QScintilla and plot colors remain theme-aware, and switching between Text and ISO G-code still reapplies the editor chrome.
- Added Qt translation generation (`pyside6-lupdate`/`pyside6-lrelease`) to the Qt codegen pipeline: `translations/app_ru.ts` is the tracked source and the compiled `app_ru.qm` is embedded in the Qt resources as a generated artifact.
- Recolored the `Fit to View` toolbar icon so it stays visible on the dark theme.
- Restored fast NC file opening by removing the 1.5.4 forced synchronous Auto Update from `Open`; the previous plot is cleared immediately, normal Auto Update settings are respected, and long calculations use delayed execution feedback while short calculations avoid a modal flash.
- Moved tool discovery plus trace sampling into the worker path so slow calculations are covered by the delayed cancellable execution dialog without reintroducing a status-bar progress bar.
- Added an `inches` display switch to Stock and WCS and to both Turning and Milling Tool Library add/edit forms; stored geometry and WCS values remain millimetres.
- Avoided unnecessary re-execution before Export when the current trace is already valid, moved export generation/writing through the delayed cancellable execution dialog, and kept total export timing in the status bar.
- Fixed Expanded Execution formatting so Delimiter always inserts a space after sequence numbers, and fixed G91 export so I/J/K are emitted incrementally even when Absolute IJK is selected.
- Reorganized the `tests/` tree into domain subpackages (`core`, `dialects`, `stock`, `tooling`, `export`, `gui`, `render`, `meta`) and split the oversized stock-removal and CLI/exporter suites into focused modules; shared fixtures and helper imports now resolve from the `tests` root.
- Grouped the Qt Designer sources and their generated modules under `app/ui/generated/main`, `app/ui/generated/dialogs` and `app/ui/generated/editors`, and updated the Windows and shell generation scripts to recurse and mirror the category directories.
- Updated locked dependencies: numpy 2.5.3, fonttools 4.65.0, platformdirs 4.11.9, pyinstaller 6.22.3 and ruff 0.16.8.
- Split `app/ui/` into `dialogs/`, `plot/`, `windows/` and `support/` packages, rewrote all application and test imports plus the Designer custom-widget headers, and remapped the complexity baseline to the new module paths.
- Made the Tokens window a standard resizable window with minimize and maximize controls and removed its in-content Close button.
- Fixed the FAQ table of contents in the Help window by resolving `#section` links to the matching document headings.

## 1.5.4 - 2026-09-16

- Unified turning and milling tool management under one `Tool Library` window with separate Milling/Turning tabs and explicit `Current Program` versus persistent `Saved Library` areas.
- Kept discovered T selections temporary per open program; inferred geometry from inline, named-tool and nearby operation comments, preserved descriptions, and used standard geometry when no type was recognized. New/Open resets temporary program assignments without modifying `tools.db`.
- Added explicit assignment/copy operations between Current Program and Saved Library while preserving the NC program's T number.
- Changed Tool Library export to write the complete Saved Library of the active machine kind as JSON or CSV instead of exporting only the selected tool.
- Moved code-built dialogs and tool editors to Qt Designer `.ui` sources and removed the obsolete separate turning/milling tool forms and collection classes. Generated Python UI/resource modules remain build artifacts produced by the existing generation scripts.
- Normalized Designer sources to Qt 6 scoped enum names and hardened UI generation against PySide6-to-PyQt6 enum alias mismatches.
- Used standard tool geometry for unknown selections in Stock Removal and playback instead of silently leaving stock unchanged or hiding the tool.
- Staged Saved Library Add/Edit/Duplicate/Remove operations in the Tool Library window; OK commits the final state to `tools.db`, while Cancel discards the staged changes and Current Program remains temporary.
- Improved Tool Library layout and preview behavior with compact resizable defaults, borderless sections, larger table space and viewport-aware automatic Fit for selected Current Program and Saved Library tools.
- Inferred temporary Current Program fallback geometry from the active tool's operation: D10 Drill for G81-G83, D10 Tap for G84 and OD Thread for turning G32/G33/G76/G92, while retaining D10 Flat Mill and Diamond 80 OD as the general defaults and preserving explicit comment hints.
- Made Tool Library OK commit Milling and Turning changes in a single SQLite transaction, eliminating partial cross-tab saves and compensating rollback.
- Reported tool-library read failures explicitly at startup and disabled Tool Library editing instead of presenting an unreadable `tools.db` as an empty library.
- Made Linux and Windows CI regenerate Qt sources and fail on any modified or untracked generated output before tests or packaging.
- Removed the redundant status-bar progress indicator; long CNC execution now uses only the cancellable execution dialog.
- Restarted ordinary playback from the beginning when Play is pressed at the completed end of a trajectory.
- Refreshed the plot immediately when opening a new NC program, regardless of the Auto Update setting, so geometry from the previously opened file is never left on screen.
- Made Playback controls authoritative over editor-line synchronization: Play, Step Forward, Step Backward and manual trackbar movement now advance correctly through expanded Macro B execution even when multiple execution steps originate from the same source line.
- Fixed lathe Auto Stock for programs located in positive Z coordinates and separated absolute stock front position from front allowance, so opening or confirming the Stock dialog no longer shifts automatically detected stock back into negative Z.
- Fixed G70 finishing so the cycle first approaches the profile start from the actual G70 call position instead of beginning the finish contour with a discontinuous jump.
- Renamed the automatic refresh threshold to `Auto update max points`, removed the hidden point ceiling from manual Update, and reused an already computed kernel result when an oversized automatic render is completed manually.
- Delayed the cancellable execution dialog until a calculation has run for two seconds, while keeping execution immediate; fast runs no longer flash a modal window, and the worker shutdown path no longer relies on a nested `QDialog.exec()` lifecycle that could crash Qt on Windows.
- Split the oversized GUI and dialog regression suites into focused test modules covering actions, execution, files, plotting, settings, views, export, options and turning-tool editing.

## 1.5.3 - 2026-09-14

- Replaced direction-bearing turning type identifiers with nine canonical geometry types: Diamond 80, Diamond 35, Square, Round, Triangle, Groove, Thread, Drill and Tap.
- Persisted OD, ID and Face as independent `applications` flags and routed preview, orientation, compensation and Stock Removal through canonical geometry plus application context.
- Added idempotent `tools.db` migration on load; historical records retain application meaning and geometry fields and are immediately rewritten using canonical types without duplication.
- Added a Qt-free SQLite tool library in `tools.db` as the authoritative store for turning and milling tool definitions.
- Initialized new SQLite libraries directly with the current tool schema; no intermediate legacy tool import is used.
- Added a generator for the complete auto-mode turning catalogue and made turning and milling tool-set replacement atomic.
- Added regression coverage for deterministic catalogue generation, deletion persistence, duplicate-key protection and the settings bridge.
- Added live previews, first-free-number duplication and JSON/CSV export to both tool-library dialogs.
- Added Face Mill, Slot Mill, Chamfer Mill and Tap cutters plus square, round and triangular turning inserts.
- Added a directional threading tool with Length/Diameter, E, EX and RC geometry for preview and trace playback.
- Added Diamond 80 with OD applicability and D10 Flat Mill fallback geometry when a program does not select a configured tool.
- Added Prev/Next Toolchange navigation and exposed the Edit and CNC Functions actions in the editor context menu.
- Corrected the application-specific auto tracing-point catalogue, including P1/P2/P6/P7 for Diamond 35 ID and P3/P4/P7/P8 for Diamond 35 OD.
- Corrected turning-tool geometry consistency: Triangle Insert now uses a real three-sided footprint, Round Insert uses its physical insert radius for trace-point placement, and Drill/Tap library preview reuses the shared cutter geometry used by playback and Stock Removal.
- Added pitch- and insert-driven Stock Removal profiles for synchronized G32/G33, modal G92 and G76 cutting moves; repeated OD/ID passes deepen one phase-aligned profile, radial infeed/retract moves do not create false angled faces, and G94 remains a facing cycle.
- Changed Stock sizing to preserve user-entered manual dimensions across Refresh and turning-tool edits; Reset to Auto, New and Open return Stock to program-derived automatic sizing.
- Added startup Fit to View for persisted Lathe Mode after the main window is shown, so the automatic stock outline is visible immediately.
- Consolidated tool validation under `app/tools/validation.py`, split turning/milling library dialogs out of the generic dialog module, and kept compatibility re-exports for existing callers/tests.
- Kept `tools.db` as the single authoritative turning/milling library; legacy `CNC/TOOLS_JSON` and `CNC/MILLING_TOOLS_JSON` values are not imported or written.

## 1.5.2 - 2026-09-12

- Fixed Linux shell workflow orchestration so nested `.sh` scripts are invoked through `bash` and do not depend on executable file mode in CI.
- Installed the EGL and OpenGL runtime libraries required for PyQt6 imports on clean Ubuntu CI runners.
- Made recent-file deduplication consistently case-insensitive across Windows and Linux, including migrated Windows-style paths.

## 1.5.1 - 2026-09-12

- Fixed Groove + Face Stock Removal so axial feed moves subtract only the swept cutter footprint and preserve material on both radial sides; rapid moves remain non-cutting and the generalized interval profile stays reversible during playback.
- Added P2/P3 Groove + Face orientations and used the same orientation-aware cutter polygon for the tool preview, 3D playback and Stock Removal.
- Added configurable corner radius for Groove tools in OD, ID and Face applications, with `R0` compatibility and real rounded cutter footprints for preview and material removal.
- Restored a clearly visible yellow/gold turning insert material without changing global scene lighting or the rendering of stock, STL, grid and toolpaths.
- Added groove regressions covering the supplied G74 face-grooving cycle, local material removal, rapid/feed behavior, multiple X passes, P2/P3, rounded OD/ID/Face footprints and reversible stock playback.
- Fixed disconnected stock-ring meshing so topology changes do not create overlapping faces and exact radial Groove profile breaks remain effective alongside Groove + Face cuts.
- Kept long kernel executions responsive to Qt events and made Stop, repeated Refresh and window close request cooperative cancellation.
- Removed machine-specific window geometry from the bundled legacy configuration, constrained runtime dependency ranges and added Linux CI coverage for the shell workflow.

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
- Added a shared Qt-free X/Z turning-tool geometry layer so preview and Stock Removal use the same Diamond 80, Diamond 35 and Groove silhouettes across OD/ID applications.
- Changed Diamond 80/Diamond 35 Stock Removal for OD P3 and ID P2 from the previous nose/width approximation to sampled polygon-footprint removal along the resolved `TraceMotion`, so plate angle, main-edge angle and nose radius affect the machined profile.
- Added Groove edge-reference selection for OD P3/P4 and ID P1/P2, with application-aware defaults and valid orientation choices.
- Changed unknown or unconfigured turning tools to leave stock unchanged instead of falling back to an implicit Diamond 80 cutter; Stock Removal remains a geometric simulation and does not require spindle-running state.
- Added automatic turning-stock sizing from resolved G1/G2/G3 cutting motions, including cycle-generated motions and exact G18 arc extrema, while ignoring G0 positioning; the suggested bore remains zero by default.
- Added a lightweight stock outline to the normal Lathe Plot, included configured stock in Fit View bounds, hid the outline in milling and isolated Stock Removal playback, and restored it when returning to the normal lathe plot.
- Added Stock-dialog prefill from the current automatic stock suggestion without mutating persisted settings until OK is pressed, and refresh the suggestion after program or mode recalculation so stale dimensions are not reused.
- Added ordinary FANUC turning source-trace support for simplified `A`, `C` and corner-`R` programming, including compact blocks without spaces: `A` resolves the missing X/Z coordinate and `C`/`R` insert chamfer/fillet transitions through the same profile helper already used by cycle contours.
- Preserved G2/G3 `R` as arc-radius programming, applied source-unit scaling to direct-programming `C`/`R`, allowed a chamfer/fillet to consume an adjacent segment exactly, and rebuilt execution-step motion counts after inserted source transitions so playback and editor ownership remain aligned.
- Expanded regression coverage for OD/ID insert footprints, groove P orientations, reversible playback, unknown tools, automatic stock bounds/outline refresh, cycle-generated stock sizing, and ordinary source-trace A/C/R execution.
- Split the detailed user/developer reference from README into `FAQ.md`, added an offline Help → FAQ window below About, and embedded the FAQ in application resources for packaged builds.

## 1.4.2 - 2026-09-10

- Added turning Stock Removal playback driven by the resolved execution trace, with reversible OD/ID profiles, drilling, grooving, persistent stock dimensions and geometry-specific 3D tools for Groove, Drill, Diamond 80 (5-degree edge) and Diamond 35 (3-degree edge) across application contexts.
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
