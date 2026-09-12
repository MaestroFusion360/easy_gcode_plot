# Easy G-Code Plot FAQ

This document is the detailed user and developer reference for Easy G-Code Plot. It is also available offline from **Help → FAQ** inside the application.

## Contents

- [Getting started](#getting-started)
- [Interface and playback](#interface-and-playback)
- [Lathe mode](#lathe-mode)
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

To run from source, install Python 3.11+ and [uv](https://docs.astral.sh/uv/), then run:

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

Auto Update has a configurable sampled-segment limit. Large programs are left unchanged until an explicit Refresh so that typing remains responsive. Manual refresh displays staged progress for a large trace.

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

## Turning Stock Removal

### How are initial Stock dimensions selected?

The resolved G1/G2/G3 cutting trace supplies an automatic minimum outside diameter and length. Rapid G0 outliers are ignored, cycle-generated cutting motions are included, and G18 arc extrema are evaluated analytically. The suggested inside diameter is zero.

The normal Lathe plot displays this stock as a lightweight outline when `Show Stock` is enabled. **Settings → Stock** is prefilled from the current suggestion, but persistent settings change only after pressing OK.

### What can I configure in Settings → Stock?

- Enable or disable Stock Removal on Play.
- Outside diameter.
- Existing inside diameter.
- Stock length.
- Front Z stock allowance.
- Accuracy, which selects the axial profile resolution.

### Does Play use the same bounds as the visible outline?

Yes. Refresh and program changes update the automatic suggestion, and both the outline and Stock Timeline use the same effective stock specification. Starting Play no longer falls back to stale saved dimensions.

### Which turning tools remove material?

Supported tool geometries include Face Groove, OD Groove, ID Groove, Drill, OD80, ID80, OD35 and ID35. The Stock simulation and turning-tool preview share one cutter silhouette implementation.

OD80/OD35 P3, ID80/ID35 P2, OD Groove P3/P4 and ID Groove P1/P2 use their configured insert or groove footprint. Unknown or unconfigured tools leave the stock unchanged instead of using an assumed cutter.

### Is Stock Removal a machine simulation?

No. It is a geometric material-removal preview driven by resolved motions and configured cutter geometry. It does not model acceleration, collision, workholding, spindle dynamics or machine safety.

## Mill mode

### Which views are available?

The normal 3D view uses perspective projection. Top, Front and Left are true orthographic views. Starting free orbit from a fixed view returns the scene to perspective.

### Which milling tools can be previewed?

- Flat end mill.
- Bull-nose mill.
- Ball end mill.
- Drill with a 120-degree point.

The translucent preview follows the active motion endpoint and uses the tool configured in **Settings → Milling Tools**.

### How does milling cutter compensation work?

G40/G41/G42 uses the configured tool diameter for supported G17 line, arc and compatible helical contours. Entry, steady contour, corner stitching and exit transitions are resolved against the executed trace. Unsupported cases remain marked `UNVERIFIED` rather than being presented as corrected geometry.

### Is G43 tool-length geometry applied?

G43/G49 and H values are tracked for execution/export context, but H-offset geometry is not currently applied to the trace.

## Units and arc programming

### What does the default unit option do?

The default millimetre/inch option initializes execution only until the program explicitly selects G20 or G21. Explicit program codes always take precedence.

### What does Arc Type control in Mill Mode?

- IJK relative to the arc start.
- IJK absolute center coordinates.
- Prefer R when both center words and a radius are present.

Analytical arc center, radius, sweep, plane and direction are resolved once by the kernel. Rendering only samples the resulting geometry.

### Are full circles supported?

Yes. When exporting an R-format full circle, Expanded Execution emits two exact R semicircles because one R block cannot uniquely represent a full circle.

## Supported G-code

### Common execution

- `G00/G01/G02/G03` motion.
- `G17/G18/G19` planes where applicable.
- `G20/G21` units.
- `G28` configured reference return.
- `G54-G59` work coordinate systems.
- `G90/G91` absolute/incremental programming where applicable.
- Macro B expressions and assignments.
- `IF/GOTO` and `WHILE/END`.
- `M98/M99` subprogram execution.
- `M00/M01/M02/M03/M04/M05/M08/M09/M30` signals and program control.

### FANUC milling

- XYZ motion and helical interpolation.
- G53 machine-coordinate motion.
- G80/G81/G82/G83/G84/G85/G86 canned cycles.
- G98/G99 canned-cycle return modes.
- G94/G95 feed modes.
- Configured milling tools and cutter-radius compensation.

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

### What is the Tokens window for?

**Settings → Tokens** shows parser words, evaluated values, source position, execution status and diagnostics. Suspicious or unsupported rows are highlighted and can be copied or exported as CSV.

### Which export types are available?

- Turning Full Program.
- Milling Full Program.
- Expanded Execution.
- Plot Data.
- DXF trajectory.

Expanded Execution follows actual occurrence order, including subprogram calls and generated cycle motions. It preserves relevant WCS, home returns, threading, dwell, spindle and coolant events.

In Lathe mode, generated arcs use relative I/K and incremental coordinates use U/W. In Mill mode, coordinate and arc output representations are configurable.

DXF uses separate rapid and cutting layers. Turning uses plot-aligned Z/X entities; milling exports 3D line/arc/circle geometry where representable.

## Configuration

### Where is configuration stored?

On Windows:

```text
%LOCALAPPDATA%\easy-gcode-plot\config.ini
```

A legacy `config.ini` beside the launcher may be migrated on first run.

### What is available in Settings → Options?

- UTF-8 or Windows-1251 document encoding.
- Default Text/ISO editor mode and default units.
- Application logging.
- G41/G42 correction and arc tolerance.
- Editor font and visual settings.
- Plot colors, line thickness, axes and grid.
- `Show Stock` immediately after `Show canvas grid`.
- Canvas gradient and STL appearance.
- Playback speed and adaptive/fixed grid spacing.

### Where is the log file?

When logging is enabled:

```text
%LOCALAPPDATA%\easy-gcode-plot\main.log
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

- `app/gcode/kernel/` owns CNC parsing, execution, cycles and analytical geometry.
- `app/gcode/trace_tools.py` owns render sampling and statistics derived from the resolved trace.
- `app/ui/` owns PyQt GUI behavior.
- `app/ui/generated/` contains Qt Designer sources and generated PyQt-compatible modules.
- `app/resources/files_res.qrc` is the resource manifest.
- `tests/` contains kernel, GUI, CLI, export, Stock and code-generation regressions.

CNC semantics belong in the kernel. GUI rendering, statistics and export consume `ExecutionResult` and must not independently reinterpret source commands.

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

Generated Python modules must not be edited manually. PySide6 supplies maintained code-generation tools in the development dependency group; the application runtime remains PyQt6.

### How do I build or release?

```powershell
.\scripts\ps1\build.ps1
.\scripts\ps1\release.ps1 -Version 1.5.0 -Message "Release 1.5.0"
```

## License

MIT License — see [LICENSE.md](LICENSE.md).
