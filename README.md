# Easy G-Code Plot

[![Windows build](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml/badge.svg)](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml)

Download the current standalone Windows executable from [GitHub Releases](https://github.com/MaestroFusion360/easy_gcode_plot/releases). The packaged application does not require a separate Python installation.

<!-- markdownlint-disable MD033 -->

<details>
  <summary><h2>Screenshot</h2></summary>

<p align="center">
  <div style="text-align: center;">
    <img src="assets/img1.png" alt="Easy G-Code Plot">
  </div>
</p>

</details>

---

- [Easy G-Code Plot](#easy-g-code-plot)
  - [Overview](#overview)
  - [Features](#features)
    - [File Management](#file-management)
    - [Code Editor](#code-editor)
    - [Visualization](#visualization)
    - [Code Manipulation](#code-manipulation)
    - [Export](#export)
    - [Analysis](#analysis)
    - [Tokens Diagnostics](#tokens-diagnostics)
    - [Options](#options)
    - [Tool Configuration](#tool-configuration)
      - [Turning Tools](#turning-tools)
      - [Milling Tools](#milling-tools)
  - [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [Installation Steps](#installation-steps)
  - [Usage](#usage)
    - [Basic Workflow](#basic-workflow)
    - [Main Interface](#main-interface)
      - [Editor Panel](#editor-panel)
      - [Plot Panel](#plot-panel)
      - [Playback Controls](#playback-controls)
      - [Status Bar](#status-bar)
  - [Supported G-code](#supported-g-code)
    - [Common execution](#common-execution)
    - [FANUC milling](#fanuc-milling)
      - [Milling cutter compensation](#milling-cutter-compensation)
      - [Tool length compensation](#tool-length-compensation)
    - [FANUC turning](#fanuc-turning)
  - [Configuration](#configuration)
    - [Options Dialog](#options-dialog)
    - [Plot](#plot)
    - [Editor](#editor)
    - [Export](#export-1)
    - [Geometry](#geometry)
    - [CNC configuration](#cnc-configuration)
  - [Troubleshooting](#troubleshooting)
    - [Plot Not Displaying](#plot-not-displaying)
    - [Cutter Compensation Not Visible](#cutter-compensation-not-visible)
    - [Machining Time Is UNKNOWN](#machining-time-is-unknown)
    - [Export Errors](#export-errors)
    - [Logging](#logging)
  - [Technical Details](#technical-details)
    - [Architecture](#architecture)
    - [Execution Model](#execution-model)
    - [Arc Geometry](#arc-geometry)
    - [Resource Protection](#resource-protection)
    - [Performance](#performance)
    - [File Support](#file-support)
  - [Development](#development)
    - [Building from Source](#building-from-source)
    - [Code Structure](#code-structure)
    - [Development Rules](#development-rules)
  - [License](#license)

---

## Overview

Easy G-Code Plot is a desktop G-code viewer, editor, analyzer, simulator and trace exporter for FANUC-style turning and milling programs.

The application uses a native Python CNC kernel shared by the GUI and CLI. Source code is parsed and executed once into an authoritative `ExecutionResult` containing the resolved logical motion trace, execution occurrences, modal state, diagnostics and machine signals.

Rendering, playback, statistics and export consume this execution result instead of maintaining independent CNC interpretation paths.

The kernel supports both:

- `fanuc_turn`
- `fanuc_mill`

The project intentionally prefers explicit diagnostics over guessing unsupported CNC semantics.

## Features

### File Management

- New, open, save and save-as
- Drag-and-drop file opening
- Recent Files list
- Missing recent-file cleanup
- Unsaved-changes prompt
- Standard `.nc`, `.cnc` and `.txt` input

### Code Editor

- G-code syntax highlighting
- Configurable font, size and style
- Line numbering and margins
- Caret-line highlighting
- Whitespace and EOL display
- Find and Replace
- Undo / Redo
- Cut / Copy / Paste
- Block renumbering
- Empty-line and whitespace cleanup
- Comment removal

### Visualization

- Interactive 3D toolpath view
- Top, Front and Left orthographic views
- Milling and Lathe modes
- Configurable grid
- Zoom controls
- Step-by-step playback
- Fixed-pixel playback cursor
- Separate rapid and cutting motion rendering
- Shift+Click trajectory picking with source-line synchronization
- Analytical circular interpolation sampled only at the rendering boundary

### Code Manipulation

- Add, remove or renumber N-block numbers
- Remove unnecessary spaces
- Remove empty lines
- Remove comments
- Optional-block skipping
- Source-aware expanded program reconstruction

### Export

The exporter works from the executed logical trace rather than running a second CNC interpreter.

Available modes include:

- Standard trace export
- `EXPANDED TURN PROGRAM`
- `EXPANDED MILL PROGRAM`
- Turning cycle expansion
- Absolute or incremental positioning
- Source unit preservation
- Sequence-number generation
- Forced address output
- Leading-zero suppression
- Configurable headers and footers
- Safety lines
- Address delimiters

Expanded program export follows actual execution-step order, including repeated subprogram execution.

### Analysis

- Toolpath length
- Machining time
- X/Y/Z bounds
- Rapid and feed motion statistics
- Physical turning-radius geometry
- Feed-per-minute and feed-per-revolution execution state
- CSS-aware turning time calculation where sufficient runtime data is available

When machining time cannot be resolved reliably, the application reports it as unknown rather than silently guessing.

### Tokens Diagnostics

Open **Settings → Tokens** to inspect the current editor document without modifying it. The dialog refreshes from the live editor and uses the application's existing parser, AST and `ExecutionResult`; it does not maintain a second G-code parser.

The read-only table shows the original line and parsed words together with dedicated address groups for `N`, `O`, `M`, motion, plane, units, correction, cycles, coordinate mode, spindle and control flow. Kernel warnings and errors are attached to their source lines. Valid rows are highlighted in pale green; every suspicious row (warning or error) is highlighted in pale red.

Selected rows can be copied with **Ctrl+C** or the context menu. **Export CSV** writes the current table as UTF-8, semicolon-delimited data, and **Reset Columns** restores the default widths and scroll position.

### Options

**Settings → Options** opens a separate Qt Designer-based settings dialog. Tokens remains an independent diagnostic tool and is not embedded in Options.

Options is organized into General, Editor and Plot pages. Changes are applied with **OK** and persisted in the normal application configuration; **Cancel** discards unapplied edits.

### Tool Configuration

Turning and milling tools are configured independently.

#### Turning Tools

Turning tools are identified using FANUC-style tool numbers such as:

```text
T0101
T0202
```

Configured turning tools can provide:

- tool type
- nose radius
- tip orientation
- additional tool metadata

Turning `G41/G42` tool-nose compensation uses the configured tool geometry.

#### Milling Tools

Milling tools use compact tool identities:

```text
T1
T2
...
T99
```

Leading zeroes are not used for milling tool identities.

Configured milling tools can provide:

- tool type
- diameter
- corner radius
- length
- description

Supported milling tool types include:

- flat end mill
- bull-nose mill
- ball end mill
- drill

For supported G17 contours, configured tool diameter is used by cutter-radius compensation.

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

### Installation Steps

Clone the repository:

```bash
git clone https://github.com/MaestroFusion360/easy_gcode_plot.git
cd easy_gcode_plot
```

Create or update the project environment:

```bash
uv sync --no-dev
```

Run the GUI:

```bash
uv run --no-dev python main.py
```

The same kernel is also available through the CLI:

```bash
uv run --no-dev python -m app parse program.nc --lang fanuc_turn

uv run --no-dev python -m app trace program.nc \
  --lang fanuc_turn \
  -o trace.json

uv run --no-dev python -m app analyze program.nc \
  --lang fanuc_turn

uv run --no-dev python -m app export program.nc \
  --lang fanuc_turn \
  -o expanded.nc

uv run --no-dev python -m app export program.nc \
  --lang fanuc_turn \
  --mode program \
  -o expanded-turn.nc

uv run --no-dev python -m app export program.nc \
  --lang fanuc_mill \
  --mode program \
  -o expanded-mill.nc

uv run --no-dev python -m app export program.nc \
  --lang fanuc_turn \
  --mode cycles \
  -o expanded-cycles.nc
```

## Usage

### Basic Workflow

1. Open a G-code program through **File → Open** or drag and drop it into the application.
2. Select the appropriate machine mode.
3. Configure machine coordinates, WCS and tools if required.
4. View the resolved toolpath.
5. Edit the source program.
6. Refresh the execution result after changes.
7. Inspect playback, diagnostics and statistics.
8. Use **Settings → Tokens** when line-by-line parser and execution diagnostics are needed.
9. Export the resolved or expanded program if required.

### Main Interface

#### Editor Panel

The left side contains the source program editor with:

- syntax highlighting
- line numbers
- editing commands
- search and replace

#### Plot Panel

The right side contains the toolpath visualization with:

- 3D view
- Top / Front / Left views
- grid
- zoom
- trajectory picking
- playback cursor

#### Playback Controls

Playback controls allow stepping through the executed logical motion trace.

The current source block and playback position remain synchronized.

#### Status Bar

The status bar displays application and editor state such as:

- character count
- cursor position
- progress for long operations

## Supported G-code

The kernel currently exposes two execution profiles:

```text
fanuc_mill
fanuc_turn
```

Both share the same parsing, Macro B, control-flow, diagnostics and execution-result foundation.

### Common execution

Supported common semantics include:

- `G00/G01/G02/G03` — rapid, linear and circular interpolation
- `G17/G18/G19` — interpolation planes where applicable
- `G20/G21` — inch / metric units
- `G28` — configured primary reference return
- `G54-G59` — work coordinate systems
- `G90/G91` — absolute / incremental programming where applicable
- Macro B expressions and assignments
- `IF/GOTO`
- `WHILE/END`
- `M98/M99` — subprogram execution
- `M00/M01/M02/M03/M04/M05/M08/M09/M30`

Unsupported controller-dependent semantics are diagnosed explicitly rather than inferred heuristically.

### FANUC milling

Milling execution includes:

- XYZ motion
- absolute and incremental positioning
- `G17/G18/G19`
- IJK and R circular interpolation
- helical interpolation
- `G53` machine-coordinate motion
- `G54-G59` work coordinate systems
- `G80/G81/G82/G83/G84/G85/G86` canned cycles
- `G98/G99` canned-cycle return modes
- `G94/G95` feed modes
- M98/M99 subprogram execution
- machine signals
- configured milling tools
- cutter-radius compensation

#### Milling cutter compensation

`G40/G41/G42` cutter-radius compensation uses configured milling tool diameter.

The compensation pipeline follows the executed contour:

```text
entry transition
    ↓
steady compensated motion
    ↓
line / arc corner stitching
    ↓
exit transition
```

Supported geometry includes G17 line, arc and compatible helical paths.

Unsupported compensation cases are preserved as `UNVERIFIED` instead of silently pretending that compensation was successfully applied.

#### Tool length compensation

`G43/G49` state and `H` values are tracked and preserved for execution/export context.

Tool-length H-offset geometry is not currently applied to the motion trace. Explicit `G43` geometry therefore remains reported as unverified where appropriate.

### FANUC turning

Turning execution includes:

- X/Z programming
- U/W incremental axes
- diameter/radius handling
- I/K/R circular interpolation
- `G32/G33` threading motion
- `G70-G76`
- modal `G90/G92/G94` turning cycles
- turning `G83/G84`
- `G96/G97` spindle modes
- `G98/G99` feed modes
- subprogram execution
- machine signals
- tool-nose compensation

`G40/G41/G42` turning compensation uses configured tool nose radius and tip orientation.

## Configuration

The application stores its configuration outside the installation directory.

On Windows:

```text
%LOCALAPPDATA%\easy-gcode-plot\config.ini
```

On first run, a legacy `config.ini` next to the launcher may be migrated to the per-user configuration location.

The configuration stores settings for:

### Options Dialog

The **Settings → Options** dialog exposes:

- UTF-8 or Windows-1251 file encoding
- default Text / ISO G-code editor mode
- default millimeter or inch preference
- current UI language (displayed read-only until localization switching is ready)
- application logging toggle
- G41/G42 correction preference and arc tolerance
- editor font, size, caret-line, EOL, whitespace and line-number presentation
- rapid, linear, arc, current-segment and canvas colors
- native color pickers and a Restore Defaults action
- plot line thickness, canvas axes and grid visibility
- grid step, where `0` selects adaptive spacing and a positive value records a fixed step

The selected encoding is used when opening and saving editor documents. The default editor mode is restored on the next launch, and the default unit preference initializes CNC execution until an explicit `G20` or `G21` in the program overrides it. Existing WCS, tool, Arc Type and Lathe Mode controls remain separate Settings menu entries.

### Plot

- timer speed
- arc calculation mode
- machine coordinates
- lathe mode
- line colors
- background color
- grid color
- grid size
- grid spacing
- rapid, linear, arc and current-segment color preferences
- line thickness and axes visibility
- adaptive/fixed grid-step preference

### Editor

- font
- font size
- font weight
- italic state
- caret-line display
- whitespace display
- EOL display
- margins
- file encoding (`UTF-8` or `Windows-1251`)

### Export

- language
- export mode
- address forcing
- incremental mode
- program start/end strings
- sequence-number settings
- formatting options

### Geometry

- window position
- window size
- maximized state

### CNC configuration

Persistent CNC configuration includes:

- `G54-G59` XYZ work offsets
- `G28` home coordinates
- turning tool definitions
- milling tool definitions

## Troubleshooting

### Plot Not Displaying

Check:

- that the program contains supported motion commands
- that the selected machine mode matches the program
- execution diagnostics
- arc interpretation settings
- machine/WCS configuration
- whether an unsupported position-changing controller command stopped execution

The kernel deliberately stops before some unknown position-changing semantics rather than inventing geometry.

### Cutter Compensation Not Visible

For milling:

- confirm that the program contains `G41` or `G42`
- confirm that the active tool exists in Milling Tools
- use milling tool IDs `T1` through `T99`
- confirm that the tool has a valid positive diameter
- inspect diagnostics for `UNVERIFIED` compensation geometry
- confirm that the contour is supported by the current compensation solver

For turning:

- confirm that the active turning tool exists
- confirm tool nose radius and orientation
- confirm `G41/G42` is active

### Machining Time Is UNKNOWN

This means the runtime could not establish a trustworthy feed rate for one or more motions.

Typical causes include incomplete spindle/feed information during feed-per-revolution execution.

The application intentionally reports unknown time instead of treating an unresolved feed as feed-per-minute.

### Export Errors

Check:

- selected machine profile
- output mode
- unsupported source semantics
- invalid custom header/footer text
- filesystem permissions

### Logging

When application logging is enabled, the log is written beside the per-user configuration file:

```text
%LOCALAPPDATA%\easy-gcode-plot\main.log
```

It records application startup, file open/save activity, CNC execution summaries, export completion and related errors. Disabling logging closes the application-owned file handler.

## Technical Details

### Architecture

```text
NC source
   ↓
Lexer / parser
   ↓
AST / evaluated words
   ↓
Macro B + control flow
   ↓
FANUC turning / milling semantic execution
   ↓
resolved runtime modal state
   ↓
analytical geometry
   ↓
ExecutionResult
   ├─ TraceMotion
   ├─ ExecutionStep
   ├─ diagnostics
   ├─ machine signals
   └─ program state
        ↓
        ├─ GUI rendering
        ├─ playback
        ├─ statistics
        ├─ CLI
        └─ export
```

The CNC kernel under `app/gcode/kernel/` has no Qt dependency.

The GUI does not maintain a second CNC execution engine.

### Execution Model

Execution is occurrence-based rather than source-order based.

This is important for:

- subprogram calls
- repeated blocks
- Macro B control flow
- canned-cycle expansion
- machine signals
- expanded program export

Runtime state is attached to execution occurrences rather than reconstructed afterward from source text.

The authoritative result is:

```python
ExecutionResult
```

It contains the resolved motion trace and execution metadata consumed by the rest of the application.

### Arc Geometry

Arc interpretation belongs to the kernel.

The kernel resolves analytical:

- center
- radius
- sweep
- plane
- direction
- full-circle state

Consumers do not attempt alternative IJK interpretations or choose a best-fit center after execution.

Rendering tessellates analytical arcs only when pixels/vertices are required.

### Resource Protection

Execution includes limits for potentially unbounded operations such as:

- Macro B loops
- subprogram calls
- cycle iterations
- generated motions
- executed blocks

Resource-limit failures are returned as structured diagnostics.

### Performance

- Automatic scene refresh is enabled for editor contents up to 5,000 lines
- Larger files can be refreshed explicitly
- Arcs remain analytical until rendering/export sampling
- Statistics operate on the logical trace
- Playback operates on the same trace used by export and analysis

### File Support

Input:

```text
.nc
.cnc
.txt
```

Output:

- G-code text
- expanded turning programs
- expanded milling programs
- trace-oriented exports

The default encoding is UTF-8. Document loading and saving can be switched through **Settings → Options**:

```text
UTF-8
Windows-1251
```

## Development

### Building from Source

Install runtime and development dependencies:

```bash
uv sync --group dev
```

Run tests:

```bash
uv run pytest
```

Run Ruff:

```bash
uv run ruff check .
uv run ruff format --check .
```

Or use the project scripts on Windows:

```powershell
scripts\lint.ps1 -Fix
scripts\test.ps1
```

Build the Windows executable:

```powershell
.\scripts\build.ps1
```

Release automation is available through:

```powershell
.\scripts\release.ps1
```

### Code Structure

```text
main.py                              application launcher

app/
├─ __main__.py                       GUI/CLI dispatcher
├─ cli.py                            parse/trace/analyze/export CLI
├─ main_window.py                    main-window composition and Qt signal wiring
│
├─ gcode/
│  ├─ core.py                        formatting and generic UI-side helpers
│  ├─ exporter.py                    trace-based export; no second CNC execution path
│  ├─ trace_tools.py                 rendering sampling and trace statistics
│  │
│  └─ kernel/
│     ├─ api.py                      public execute() facade and ExecutionResult assembly
│     ├─ api_types.py                public execution/trace/diagnostic data models
│     ├─ ast.py                      parsed CNC AST nodes
│     ├─ model.py                    internal runtime and geometry models
│     ├─ program.py                  parsing helpers, word evaluation and coordinate utilities
│     ├─ lang.py                     Macro B expressions and condition evaluation
│     ├─ execution.py                Macro B flow, subprogram dispatch and execution control
│     ├─ interpreter.py              FANUC turning resolver
│     ├─ milling.py                  FANUC milling resolver
│     ├─ cycles.py                   FANUC turning cycle expansion
│     ├─ geometry.py                 analytical arc resolution in physical geometry
│     ├─ runtime.py                  occurrence-based turning cycle expansion
│     ├─ resources.py                execution budgets, limits and cancellation checks
│     ├─ signals.py                  machine signals and program-end handling
│     ├─ profile.py                  turning contour/profile geometry
│     ├─ tool_compensation.py        turning tool-nose compensation
│     └─ milling_compensation.py     milling G41/G42 cutter-radius compensation
│
├─ ui/                               Qt-facing GUI package
│  ├─ main_window_file_ops.py         files, recent files, drag/drop and export
│  ├─ main_window_editor_ops.py       editor/status/search/text transformations
│  ├─ main_window_execution.py        kernel execution, auto-refresh, playback and statistics
│  ├─ main_window_plot.py             OpenGL rendering, views, grids and trajectory picking
│  ├─ plot_grid.py                    adaptive grid geometry
│  ├─ plot_navigation.py              plot event/navigation helpers
│  ├─ window_settings.py              persisted main-window settings
│  ├─ widgets.py                      custom QScintilla/PyQtGraph Designer widgets
│  ├─ dialogs.py                      WCS, tools, export and utility dialogs
│  ├─ options.py                      Options controller and settings binding
│  ├─ tokens.py                       parser/ExecutionResult-backed diagnostics
│  ├─ lexer.py                        editor lexer
│  └─ generated/                      Designer sources and generated PyQt6-compatible modules
│     ├─ main_window.ui               canonical main-window Qt Designer source
│     ├─ main_ui.py                   generated main-window Python module
│     ├─ options.ui / options.py      Options source and generated module
│     ├─ tokens.ui / tokens.py        Tokens source and generated module
│     └─ ...
│
└─ resources/                        application resources
   └─ icons/                         application and toolbar icons

tests/
├─ fixtures/                         regression CNC programs
├─ test_core.py                      core helpers and execution behavior
├─ test_gui.py                       GUI-to-kernel contract tests
├─ test_interfaces.py                CLI/export/public interface tests
├─ test_macro_b.py                   Macro B and control-flow tests
├─ test_milling.py                   FANUC milling tests
├─ test_stabilization.py             regression and architecture stabilization tests
├─ test_qt_codegen.py                isolated Qt generation and atomicity tests
├─ test_tokens_dialog.py             Tokens and Options GUI tests
└─ test_turning.py                   FANUC turning tests

scripts/
├─ build.ps1                         Windows executable build (runtime groups only for PyInstaller)
├─ generate-qt.ps1                   regenerate Qt resources and all Designer Python modules
├─ generate-resources.ps1            generate `files_res.py` with pyside6-rcc, normalize to PyQt6
├─ generate-ui.ps1                   generate Designer modules with pyside6-uic, normalize to PyQt6
├─ lint.ps1                          formatting and static-analysis checks
├─ release.ps1                       release/version/tag automation
└─ test.ps1                          project test runner
```

### Development Rules

CNC semantics belong in the kernel.

Rendering code must not independently reinterpret CNC commands.

In particular:

- source is executed once
- consumers use `ExecutionResult`
- arc semantics are resolved in the kernel
- rendering may sample geometry but must not redefine it
- statistics derive from executed physical geometry and runtime state
- export must preserve execution order
- unsupported semantics must be diagnosed rather than guessed
- resource protection must remain active for loops, cycles and subprogram execution

Qt Designer `.ui` files and the Qt resource collection are committed sources. The generated Python modules are also committed.

PySide6 is installed only in the `dev` dependency group to provide the maintained `pyside6-uic` and `pyside6-rcc` command-line tools. The application runtime remains PyQt6; the generation scripts rewrite generated `PySide6` imports to `PyQt6` before updating committed Python modules. With the locked PySide6 6.11.x toolchain, Qt code generation uses Python 3.11-3.14.

Regenerate everything on Windows:

```powershell
.\scripts\generate-qt.ps1
```

Or regenerate only one side of the Qt sources:

```powershell
.\scripts\generate-ui.ps1
.\scripts\generate-resources.ps1
```

Designer dependency mapping includes:

```text
app/ui/generated/main_window.ui -> app/ui/generated/main_ui.py
app/ui/generated/options.ui     -> app/ui/generated/options.py
app/ui/generated/tokens.ui      -> app/ui/generated/tokens.py
app/ui/generated/<name>.ui      -> app/ui/generated/<name>.py
app/resources/files_res.qrc     -> app/resources/files_res.py
```

The `main_window.ui → main_ui.py` name is the only special-case mapping. Generated Python modules must not be edited manually.

`files_res.qrc` is the canonical, deliberately maintained resource manifest: adding or removing an icon requires updating it. The batch command validates missing and duplicate entries, generates every UI and resource module in a staging directory, and replaces committed outputs only after the entire generation succeeds. It can be launched from any working directory and safely handles project paths containing spaces.

The functional code-generation tests use a minimal isolated one-form fixture and the already installed development toolchain. They do not regenerate every project form or create another virtual environment.

The Windows packaging script explicitly drops the dev dependency group before invoking PyInstaller, so PySide6 is not present in the packaged PyQt6 runtime environment.

## License

MIT License — see [LICENSE](License.md).

---

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=MaestroFusion360-easy-gcode-plot&label=Project+Views&color=blue" alt="Project Views">
</p>
