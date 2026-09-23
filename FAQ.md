# Easy G-Code Plot FAQ

This document is the detailed user and developer reference for Easy G-Code Plot. It is also available offline from **Help → FAQ** inside the application.

## Contents

- [Getting started](#getting-started)
- [Interface and playback](#interface-and-playback)
- [Lathe mode](#lathe-mode)
- [Tool libraries](#tool-libraries)
- [Turning Stock Removal](#turning-stock-removal)
- [Mill mode](#mill-mode)
- [Units and arc programming](#units-and-arc-programming)
- [Supported G-code](#supported-g-code)
- [STL reference overlay](#stl-reference-overlay)
- [Statistics, diagnostics and export](#statistics-diagnostics-and-export)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [CLI](#cli)
- [Development](#development)

## Getting started

### What is Easy G-Code Plot?

Easy G-Code Plot is a desktop editor, analyzer, simulator and trace exporter for FANUC-style turning and milling programs. The GUI and CLI use the same CNC kernel and the same resolved `ExecutionResult`.

### How do I install it?

The simplest Windows installation is the standalone executable from [GitHub Releases](https://github.com/MaestroFusion360/easy_gcode_plot/releases). It does not require a separate Python installation.

To run from source, install Python 3.11+, [uv](https://docs.astral.sh/uv/) and a C compiler (Visual Studio Build Tools with **Desktop development with C++** on Windows, or the platform compiler and Python development headers on Linux/macOS), then run:

```bash
git clone https://github.com/MaestroFusion360/easy_gcode_plot.git
cd easy_gcode_plot
uv sync --no-dev
uv run --no-dev python main.py
```

### What is the normal workflow?

1. Open or drag a G-code file into the application.
2. Select `Lathe Mode` for turning or leave it disabled for milling.
3. Configure WCS, machine home and tools when the program requires them.
4. Press `Refresh` after editing if Auto Update is disabled or deferred.
5. Inspect the plot, playback, Tokens diagnostics and Statistics.
6. Export the source structure, expanded execution, plot data or DXF when required.

## Interface and playback

### What is shown in the two main panels?

The left panel is a QScintilla editor with syntax highlighting, line numbers, search/replace and cleanup commands. The right panel is the OpenGL toolpath view with grid, axes, zoom, fixed views, trajectory picking and playback.

### What do the playback controls do?

- `Step Backward` and `Step Forward` move by one resolved logical motion.
- `Play` advances through the same trace used by rendering, statistics and export.
- `Stop` returns ordinary playback to the zero-motion state.
- When Lathe Stock Removal playback is active, `Stop` completes the preview, restores the normal plot and leaves the slider at 100%.

Playback speed levels 1–5 correspond to 1000, 250, 100, 40 and 10 ms per logical motion.

### How do I locate a plotted move in the editor?

Use Shift+Click near the trajectory. The application selects the owning source block and moves the logical-motion slider to that move. A canned-cycle source block can own multiple generated motions.

### Why does Auto Update sometimes ask me to press Refresh?

Auto Update has a configurable sampled-segment limit. Normal edit-triggered Auto Update is non-modal. If the source changes while a refresh is running, the stale run is cancelled, another refresh is queued and the stale result is not published. Large programs are left unchanged until an explicit Refresh so that typing remains responsive. Manual refresh displays staged progress for a large trace.

### What does Cancel stop during Refresh?

The execution dialog covers tool discovery, source parsing, CNC execution, trace sampling and final plot publication. **Cancel** remains active until the complete operation ends and cooperatively stops whichever stage is running. Very large sources are read incrementally so cancellation does not wait for a complete `splitlines()` copy or a full parser pass.

### Can the built-in FAQ be resized?

Yes. **Help → FAQ** opens a normal resizable window with Minimize, Maximize and Close controls. Contents links navigate within the document; the License link opens the packaged `LICENSE.md` document.

## Lathe mode

### Where are the Lathe controls?

`Lathe Mode` is on the view toolbar immediately before `Refresh`. `Show Stock` is not a toolbar button; it is a checkbox in **Settings → Options → Plot**, immediately after `Show canvas grid`.

### How is X displayed in Lathe Mode?

Programmed X and I values are shown using turning diameter conventions. The OpenGL scene and analytical geometry retain their physical radial representation internally.

The WCS dialog follows the same boundary: Lathe X is entered and displayed as a diameter, while the internal physical offset remains radial. Y controls are disabled in Lathe Mode.

### Does the indicator follow G20 and G21?

Yes. X, Y, Z, I, J, K and F are displayed in the active units of the selected executed block:

- `G20` displays inches and inch-based feed values;
- `G21` displays millimetres and millimetre-based feed values.

The kernel continues to normalize physical geometry to millimetres; conversion occurs only at the UI boundary.

### Why do I/K appear for an arc programmed with R?

For resolved G18 turning arcs, the UI derives relative I/K from the analytical center. This also covers generated arcs from cycles and simplified contour programming. Turning always uses FANUC-style I/K offsets relative to the arc start.

### Why is Settings → Arc Type disabled in Lathe Mode?

Arc Type controls milling source interpretation. Turning I/K semantics are fixed to relative offsets, while R remains radius programming. Disabling the milling-only choice avoids presenting a setting that does not apply to Lathe execution.

### What simplified turning programming is supported?

Ordinary G1 source blocks support:

- `A` angle programming with one missing X or Z coordinate;
- `C` corner chamfers;
- corner `R` fillets.

Compact blocks without spaces are accepted. `G2/G3 R` remains circular radius programming and is not treated as a corner fillet.

### How are G71 finishing allowances handled?

The second G71 block uses signed X allowance U and axial allowance W. For outside turning, positive U leaves outside material. For inside boring, negative U leaves material toward the bore interior. The sign and contour direction distinguish OD from ID behavior.

Type I roughing ends with one full pass along the roughing profile that already includes U/W allowance. It does not reuse the nominal finishing contour, so the roughing pass does not overlap the later finish-tool path.

## Tool libraries

### Where are tools stored?

Turning and milling tool definitions are stored in the per-user SQLite database:

```text
%APPDATA%\easy-gcode-plot\tools.db
```

`tools.db` is authoritative. `config.ini` stores UI, editor, plot, WCS, Stock and other application preferences; legacy `CNC/TOOLS_JSON` and `CNC/MILLING_TOOLS_JSON` values are not imported into a current database and are not used as a fallback write target.

### What can Tool Library do?

`Settings → Tool Library` is one resizable window with Milling and Turning tabs. Each tab shows **Current Program** and **Saved Library** side by side with a viewport-fitted live preview. Current Program supports editing geometry, assigning geometry from a saved tool and staging a program tool for the library. Saved Library supports staged Add/Edit/Remove, first-free-number Duplicate and complete-library JSON/CSV export for the active tab. **OK** commits the final working copy to `tools.db`; **Cancel** discards all Saved Library changes made since the window opened. Export never includes temporary Current Program assignments. Turning tools use category-oriented editing and persist canonical geometry types independently from the OD, ID and Face application checkboxes.

### How are tools from the current program added?

Before execution and when Tool Library is opened, Update/Auto Update discover literal T selections into the temporary Current Program setup. They do **not** write discovered tools into `tools.db`. Turning keys retain the packed tool/offset number (`T0909`); milling keys use the tool number (`T03` becomes `T3`). New/Open starts a fresh temporary setup while Saved Library remains unchanged.

Inline tool comments, named headers such as `(T3 D=6. CR=0. - FLAT END MILL)`, and nearby preceding operation comments supply descriptions and recognized geometry. Examples include `OD ROUGH R0.8`, `ID ROUGH R0.8`, `GROOVE H4`, `DRILL`, `TAP`, `THREAD`, `BALL`, `FACE MILL`, and `CHAMFER`. Recognized dimensions follow the units active at the T selection. When no explicit type hint is present, operation context selects D10 Drill for G81-G83, D10 Tap for G84 and OD Thread for turning G32/G33/G76/G92; other selections use Diamond 80 OD or D10 Flat Mill. Explicit comment hints take priority, and retained Current Program geometry can be edited or staged for Saved Library.

Comment-only T references do not create tools. Macro expressions such as `T#1` are not evaluated by discovery. Current Program changes remain temporary. Persistent Saved Library changes happen only when Tool Library is accepted with **OK**.

### Which turning tool geometries are available?

The library supports exactly nine canonical types: Diamond 80, Diamond 35, Square, Round, Triangle, Groove, Thread, Drill and Tap. OD, ID and Face are application flags rather than tool types. Triangle uses a true three-sided footprint; Round uses `Length/Diameter` as its physical diameter.

## Turning Stock Removal

### How are initial Stock dimensions selected?

The resolved G1/G2/G3 cutting trace supplies an automatic minimum outside diameter and length. Rapid G0 outliers are ignored, cycle-generated cutting motions are included, and G18 arc extrema are evaluated analytically. The suggested inside diameter is zero.

The normal Lathe plot displays this stock as a lightweight outline when `Show Stock` is enabled. **Settings → Stock** is prefilled from the current suggestion, but persistent settings change only after pressing OK. If Lathe Mode is already active when the application starts, Fit to View is scheduled after the window is shown so the inferred stock is visible immediately.

### What can I configure in Settings → Stock?

- Enable or disable Stock Removal on Play.
- Outside diameter.
- Existing inside diameter.
- Stock length.
- Front Z stock allowance.
- Accuracy, which selects the axial profile resolution.

### Does Play use the same bounds as the visible outline?

Yes. In Auto mode, Refresh and program changes update the suggestion, and both the outline and Stock Timeline use the same effective stock specification. After the user accepts explicit Stock dimensions, those values become a manual override and survive Refresh and tool-library edits. **Reset to Auto**, **New** and opening another program return Stock to program-derived sizing.

### Which turning tools remove material?

Supported geometry includes Diamond 80, Diamond 35, Square, Round, Triangle, Groove, Thread, Drill and Tap. OD, ID and Face applicability selects the machining context. Preview and Stock Removal share the turning cutter geometry where the operation is footprint-based.

Threading is a deliberate Stock Removal exception: synchronized G32/G33, modal G92 and G76 cutting moves generate a deterministic longitudinal thread section. Programmed X sets the root depth, F sets the pitch, and the configured thread angle and RC shape the flanks and rounded root. Repeated passes deepen the same phase-aligned profile, while radial infeed/retract moves do not sweep the full insert body into false angled end faces. The axisymmetric stock model renders this section rather than a 3D helix. G94 remains a facing cycle.

Missing tool selections use the standard Diamond 80 OD geometry for Stock Removal and its preview. Literal T selections are normally added to the temporary Current Program setup before execution, so their recognized or edited geometry is already available for playback without writing to Saved Library.

### Is Stock Removal a machine simulation?

No. It is a geometric material-removal preview driven by resolved motions and configured cutter geometry. It does not model acceleration, collision, workholding, spindle dynamics or machine safety.

## Mill mode

### Which views are available?

The normal 3D view uses perspective projection. Top, Front and Left are true orthographic views. Starting free orbit from a fixed view returns the scene to perspective.

### Which milling tools can be previewed?

- Flat, bull-nose and ball end mills.
- Face, slot and chamfer mills.
- Drill and tap.

The translucent preview follows the active motion endpoint and uses the tool configured in **Settings → Tool Library → Milling**.

### How does milling cutter compensation work?

G40/G41/G42 uses the configured tool diameter for supported G17 line, arc and compatible helical contours. Entry, steady contour, corner stitching and exit transitions are resolved against the executed trace. Unsupported cases remain marked `UNVERIFIED` rather than being presented as corrected geometry.

### Is G43 tool-length geometry applied?

G43/G49 and H values are tracked for execution/export context, but H-offset geometry is not currently applied to the trace.

### How do milling coordinate transforms work?

- `G52 X/Y/Z` sets a local coordinate-system shift for subsequent motion. The block itself does not move the tool.
- `G68 X/Y R` enables coordinate rotation around the programmed center in the active plane. `G69` cancels it. The rotation applies to subsequent endpoints and I/J/K arc vectors; neither control block creates a motion segment.
- `G51 X/Y/Z P` enables uniform scaling around the programmed center, with `P1000` equal to a factor of `1.0`. `G51 X/Y/Z I/J/K` selects per-axis factors. Center coordinates are interpreted as absolute coordinates even in `G91`; omitted center axes use the current position.
- `G50` cancels `G51` scaling without moving the tool. Enabling or cancelling a transform preserves the current physical tool position.

Axis-specific scaling of a circular arc would require non-circular/spiral interpolation and is currently reported as unsupported instead of being approximated. A `G51` block without `P` or `I/J/K` also produces a diagnostic because no controller parameter supplies a default factor.

### How do extended work offsets and G10 work?

The kernel supports `G54.1 P1` through `G54.1 P99` for both milling and turning. API callers supply these offsets through the `extended_wcs_offsets` mapping, keyed by the P number. The WCS dialog continues to configure only `G54-G59`; extended offsets intentionally have no UI dependency.

`G10 L2 P1-P6` programs `G54-G59`, and `G10 L20 P1-P99` programs extended `G54.1` offsets for the current execution. X/Y/Z values follow the active G20/G21 units. A G10 block never creates motion, and changing the active offset preserves the physical tool position. Runtime G10 changes are returned in `ExecutionResult.wcs_offsets` and `ExecutionResult.extended_wcs_offsets` but are not written to application settings.

## Units and arc programming

### What does the default unit option do?

The default millimetre/inch option initializes execution only until the program explicitly selects G20 or G21. Explicit program codes always take precedence.

### What does Arc Type control in Mill Mode?

- IJK relative to the arc start.
- IJK absolute center coordinates.
- Prefer R when both center words and a radius are present.

Analytical arc center, radius, sweep, plane and direction are resolved once by the kernel. Rendering only samples the resulting geometry.

When **Autodetect Arc Type** is enabled under **Settings → Options → CNC / Execution**, the milling executor examines IJK arcs in occurrence order before geometry resolution. R-only arcs are ignored for detection. Relative and absolute-center interpretations are compared using Arc tolerance; the first unambiguous IJK arc fixes the mode for the whole execution. If all candidate arcs are ambiguous, the manually selected Arc Type is used as the fallback. Mixed R and IJK programs remain valid because each R block is still resolved from R. Turning is unaffected and always uses relative I/K.

### How do leading slash blocks work?

A source block beginning with `/` is an optional Block Skip block. With **Ignore Block Skip** enabled under **Settings → Options → CNC / Execution**, the complete block is excluded, including motion, Macro B assignments, signals and subprogram calls. With the option disabled, it executes normally. The setting applies to turning and milling, persists between launches and is also reflected in Expanded Execution export without rewriting the source file.

### Are full circles supported?

Yes. When exporting an R-format full circle, Expanded Execution emits two exact R semicircles because one R block cannot uniquely represent a full circle.

## Supported G-code

### Common execution

- `G00/G01/G02/G03` motion.
- `G17/G18/G19` planes where applicable.
- `G20/G21` units.
- `G28` configured reference return.
- `G53` non-modal machine-coordinate motion.
- `G54-G59` and `G54.1 P1-P99` work coordinate systems.
- `G10 L2/L20` runtime work-offset programming.
- `G90/G91` absolute/incremental programming where applicable.
- Macro B expressions and assignments.
- `IF/GOTO` and `WHILE/END`.
- `M98/M99` subprogram execution.
- `M00/M01/M02/M03/M04/M05/M08/M09/M30` signals and program control.

### FANUC milling

- XYZ motion and helical interpolation.
- G80/G81/G82/G83/G84/G85/G86 canned cycles.
- G82 dwell, G84 feed-return/spindle synchronization and G86 spindle-stop semantics.
- G98/G99 canned-cycle return modes.
- G94/G95 feed modes.
- Configured milling tools and cutter-radius compensation.
- G52 local coordinate shifts, G68/G69 coordinate rotation and G51/G50 coordinate scaling.

### How does FANUC milling polar-coordinate programming work?

`G16` enables radius/angle endpoint programming and `G15` returns to ordinary Cartesian coordinates. `G17`, `G18` and `G19` select the polar plane; its first axis is the radius and its second axis is the angle in degrees. `G90` uses the active work/local origin as the pole and absolute radius/angle values, while `G91 G16` captures the current position as the pole and later `G91` words increment the modal radius or angle. Omitted polar components retain their previous values.

Polar programming is milling-only. Polar `G2/G3` follows the supported FANUC contract and requires an `R` arc radius; I/J/K center programming in `G16` mode is rejected instead of guessed. `G12.1/G13.1` polar interpolation is not implemented.

### FANUC turning

- X/Z and U/W motion with diameter/radius handling.
- I/K/R circular interpolation.
- Direct A/C/corner-R programming.
- G32/G33 threading motion.
- G70–G76 cycles.
- Modal G90/G92/G94 turning cycles.
- Turning G83/G84.
- G96/G97 spindle modes and G98/G99 feed modes.
- Configured tool-nose compensation.

Controller-dependent semantics that cannot be resolved safely produce diagnostics instead of guessed geometry.

## STL reference overlay

### How do I load or clear an STL?

Use **File → Import STL** or the STL toolbar action next to Export Data. In the File menu, Import STL is directly above Clear STL. Opening an `.stl` file directly also replaces the active reference overlay.

### Does STL affect G-code execution?

No. ASCII and binary STL are parsed through a visualization-only path. The model is not part of `ExecutionResult`, does not change CNC interpretation and is not included in G-code exports.

### What display options are available?

Plot options provide STL color and solid or feature-edge rendering. Fit to View includes both toolpath and STL bounds. The imported mesh remains a persistent OpenGL item across camera changes.

## Statistics, diagnostics and export

### What does Toolpath Statistics contain?

The resizable Statistics window shows logical motion counts, length breakdown, known/unknown time, average feed, assumed rapid speed, XYZ bounds and per-tool sections.

Select `Inches` at the bottom-left of the window to convert every displayed length, speed and bound from millimetres to inches. Timing and counts are unchanged.

### Why is machining time UNKNOWN?

One or more motions lack a trustworthy physical feed rate. A common cause is feed-per-revolution execution without a known spindle RPM. The application reports unknown time instead of treating that feed as millimetres per minute.

### What is the Tokens/Macro Variables window for?

**Settings → Tokens/Macro Variables** has two read-only diagnostic tabs. **Tokens** shows parser words, evaluated values, source position, execution status and diagnostics. Suspicious or unsupported rows are highlighted and can be copied or exported as CSV.

**Macro Variables** shows the Macro B variable state captured at the current logical playback position. Only variables that exist at that execution point are shown. G65 local variables follow the active macro-call scope and are restored after M99. Moving Play, Step or the slider updates the inspector from the existing execution snapshots without re-executing the CNC program. If the current source is stale relative to the displayed execution result, Macro Variables are not shown until the toolpath is updated.

Macro variable `#0` is permanently vacant and cannot be assigned. Omitted G65 local arguments are also vacant, so standard tests such as `IF[#1 EQ #0]` work. Assigning `#0` to another variable clears that variable, while indirect assignment such as `#[#1]=5` resolves the destination variable number at runtime.

### Which export types are available?

- Turning Full Program.
- Milling Full Program.
- Expanded Execution.
- Plot Data.
- DXF trajectory.
- Tool List text report from **CNC Functions → Tool List**.

Expanded Execution follows actual occurrence order, including subprogram calls and generated cycle motions. It preserves relevant WCS, home returns, threading, dwell, spindle and coolant events.

When **Ignore Block Skip** is enabled, Expanded Execution consumes the already filtered execution result, so skipped `/` blocks are not emitted and the source is not executed a second time for export.

In Lathe mode, generated arcs use relative I/K and incremental coordinates use U/W. In Mill mode, coordinate and arc output representations are configurable.

DXF uses separate rapid and cutting layers. Turning uses plot-aligned Z/X entities; milling exports 3D line/arc/circle geometry where representable.

## Configuration

### Where is configuration stored?

On Windows:

```text
%APPDATA%\easy-gcode-plot\config.ini
%APPDATA%\easy-gcode-plot\tools.db
```

`config.ini` contains application preferences; `tools.db` contains the authoritative turning/milling tool library. Files beside the launcher are not used as configuration sources.

### What is available in Settings → Options?

- UTF-8 or Windows-1251 document encoding.
- Default Text/ISO editor mode and default units.
- Application logging.
- Auto Update, its sampled-segment limit and the kernel-wide Maximum generated motions limit.
- G41/G42 correction, arc tolerance and milling Arc Type autodetection.
- Arc-sampling presets plus maximum radius, minimum radius and minimum chord length controls for GUI trace generation.
- Persistent optional-block control through `Ignore Block Skip`.
- Editor font and visual settings.
- Plot colors, line thickness, axes and grid.
- `Show Stock` immediately after `Show canvas grid`.
- Canvas gradient and STL appearance.
- Playback speed and adaptive/fixed grid spacing.

### Where is the log file?

When logging is enabled:

```text
%APPDATA%\easy-gcode-plot\main.log
```

The application logger records startup, file operations, execution summaries, export completion and related errors.

With DEBUG logging enabled it also records applied/cancelled Options changes, machine and camera-view switches, playback state, execution/render/geometry-pack timing, Stock Timeline dimensions and sampled Stock Removal frame performance. A `stock_frame` entry separates `timeline_ms` from `mesh_ms` and includes profile-point, vertex and face counts. Frames taking at least 100 ms are logged as warnings, rate-limited to avoid making an existing slowdown worse.

## Troubleshooting

### The plot is empty

Check the selected machine mode, execution diagnostics, WCS/home values and whether the program contains supported motion. Unsupported position-changing commands can create an unknown-axis gap; the trace resumes only after absolute coordinates re-establish the affected axes.

### Cutter compensation is not visible

Verify that G41/G42 is active, the selected tool is configured and its geometry is valid. Inspect Tokens for `UNVERIFIED` compensation. Milling compensation requires a supported contour; turning compensation requires a valid nose radius and orientation.

### Stock outline changes after Refresh but Play shows old stock

Current versions rebuild Stock Timeline from the same effective auto/configured bounds used by the outline. If this still occurs, confirm that the editor was refreshed successfully and that Stock Removal is enabled.

### Export fails

Check the selected machine profile and output mode, execution diagnostics, custom header/footer content and filesystem permissions. Export intentionally refuses to invent missing geometry.

### A large program does not update while typing

Press Refresh. The automatic sampled-segment limit is intended to prevent expensive continuous rebuilding while editing.

## CLI

The GUI and CLI share the same kernel:

```bash
uv run --no-dev python -m app parse program.nc --lang fanuc_turn
uv run --no-dev python -m app trace program.nc --lang fanuc_turn -o trace.json
uv run --no-dev python -m app analyze program.nc --lang fanuc_turn
uv run --no-dev python -m app export program.nc --lang fanuc_turn -o expanded.nc
```

Use `--encoding cp1251` for Windows-1251 input. Export modes include `program` and `cycles`; use `--lang fanuc_mill` for milling.

## Development

### How is the project organized?

- `app/gcode/kernel/` owns deterministic CNC parsing and execution. Its implementation is split into `api/` (public execution facade and result types), `frontend/` (lexing, parsing, AST/model and NC input), `geometry/` (analytical/profile geometry and coordinate systems), `turning/cycles/` and `milling/cycles/` (machine-specific cycle implementations behind the shared runtime cycle contract), `compensation/` (turning and milling compensation), `runtime/` (control flow, cycle contracts/expansion, interpreter, events/signals and trace construction) and `milling/` (milling state and motion execution). Historical `lathe_cycles` and `milling.drilling` import paths remain compatibility aliases.
- `app/gcode/export/` owns Full Program, Expanded Execution, Plot Data and DXF serialization. Exporters consume the authoritative kernel result/resolved trace and do not implement a second G-code interpreter.
- `app/gcode/trace_tools.py` owns render sampling and statistics derived from the resolved trace.
- `app/ui/` owns PyQt GUI behavior, grouped into `dialogs/` (dialogs and tool editors), `plot/` (OpenGL items, STL, overlays and playback), `windows/` (main-window mixins and the execution worker) and `support/` (editor lexer, units, numeric input and shared widgets).
- `app/tools/` owns tool definitions, SQLite persistence and validation/normalization.
- `app/ui/generated/` contains Qt Designer sources and generated PyQt-compatible modules, grouped into `main/` (main window), `dialogs/` and `editors/`.
- `app/resources/files_res.qrc` is the resource manifest.
- `tests/` mirrors the domains under `core/`, `dialects/`, `stock/`, `tooling/`, `export/`, `gui/`, `render/` and `meta/`, with shared fixtures in `conftest.py` and compact program samples in `gcode_samples.py`.

The primary data flow is:

```text
source NC
  -> frontend parser / AST
  -> runtime + cycle/compensation/geometry logic
  -> ExecutionResult / resolved logical trace
  -> CLI, export, statistics, rendering and playback
```

CNC semantics belong in the kernel. GUI rendering, statistics and export must not independently reinterpret source commands. During the current core-hardening phase, new execution/analysis capabilities should be implemented and regression-tested in the core/CLI first; UI changes should remain bug fixes until the core contract is stable.

Historical module-level imports that existed before the package split are intentionally re-exported/aliased where required so the structural refactor does not change the public Python surface. New code should import from the canonical subject packages.

### How do I run checks?

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

PowerShell entry points are available under `scripts/ps1/`, and matching shell scripts are under `scripts/sh/`.

### How are Qt files regenerated?

Edit canonical `.ui` and `.qrc` sources, then regenerate once:

```powershell
.\scripts\ps1\generate-qt.ps1
```

Generated Python modules must not be edited manually. PySide6 supplies maintained code-generation tools in the development dependency group; the application runtime remains PyQt6. The generation scripts recurse through `app/ui/generated/` and mirror its category subdirectories.

### How do I build or release?

```powershell
.\scripts\ps1\build.ps1
$version = "X.Y.Z"
.\scripts\ps1\release.ps1 -Version $version -Message "Release $version"
```

Native/release tooling uses a separate persistent `.venv-build`; it does not
replace or prune the developer `.venv`. `build-native.ps1`/`build-native.sh`
synchronize locked build dependencies when `pyproject.toml` or `uv.lock`
changes, rebuild the project when the tracked `.pyx` sources change, verify both
native extension imports and otherwise reuse the existing build environment.
Use `-Refresh`/`--refresh` for an explicit native-build refresh, or
`-RefreshBuildEnvironment`/`--refresh-build-environment` with the full build.
PyInstaller is invoked from that build environment rather than through the
developer environment.

## License

MIT License — see [LICENSE.md](LICENSE.md).
