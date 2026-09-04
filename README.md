# Easy G-Code Plot

[![Windows build](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml/badge.svg)](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml)

Download the current standalone Windows executable from [GitHub Releases](https://github.com/MaestroFusion360/easy_gcode_plot/releases). The packaged application does not require a separate Python installation.

<!-- markdownlint-disable MD033 -->
<details>
  <summary><h2>Screenshot</h2></summary>

<p align="center">
  <div style="text-align: center;">
    <img src="assets/img1.png" alt="Image 1">
  </div>
</p>

</details>

---

- [Easy G-Code Plot](#easy-g-code-plot)
  - [Overview](#overview)
  - [Features](#features)
    - [📁 File Management](#-file-management)
    - [✍️ Code Editor](#️-code-editor)
    - [📊 Visualization](#-visualization)
    - [🔧 Code Manipulation](#-code-manipulation)
    - [📤 Export Options](#-export-options)
    - [📈 Analysis Tools](#-analysis-tools)
  - [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [Installation Steps](#installation-steps)
  - [Usage](#usage)
    - [Basic Workflow](#basic-workflow)
    - [Key Interface Elements](#key-interface-elements)
      - [1. Editor Panel](#1-editor-panel)
      - [2. 3D Plot Panel](#2-3d-plot-panel)
      - [3. Control Panel](#3-control-panel)
      - [4. Status Bar](#4-status-bar)
    - [Export Configuration](#export-configuration)
  - [Supported G-code Commands](#supported-g-code-commands)
    - [Motion Commands](#motion-commands)
    - [Plane Selection](#plane-selection)
    - [Coordinate Systems](#coordinate-systems)
    - [Canned Cycles](#canned-cycles)
    - [Tool Compensation](#tool-compensation)
    - [Miscellaneous](#miscellaneous)
  - [Configuration](#configuration)
    - [Settings File](#settings-file)
      - [Plot Settings](#plot-settings)
      - [Editor Settings](#editor-settings)
      - [Export Settings](#export-settings)
      - [Geometry Settings](#geometry-settings)
  - [Troubleshooting](#troubleshooting)
    - [Common Issues](#common-issues)
    - [Logging](#logging)
  - [Technical Details](#technical-details)
    - [Architecture](#architecture)
    - [Performance](#performance)
    - [File Support](#file-support)
  - [Development](#development)
    - [Building from Source](#building-from-source)
    - [Code Structure](#code-structure)
    - [Adding Features](#adding-features)
  - [License](#license)

---

## Overview

Easy G-Code Plot is a desktop G-code viewer, editor, analyzer and trace exporter. Version 1.2.0 introduces a native Python CNC kernel shared by the GUI and CLI: source is parsed into AST/semantic instructions and executed into one authoritative logical Motion Trace before rendering, statistics or export.

## Features

### 📁 File Management

- **New/Open/Save**: Create, open, and save G-code files
- **Drag & Drop**: Open files by dragging them onto the application
- **Recent Files**: Track recently opened files
- **Auto-save Prompt**: Warns about unsaved changes before closing

### ✍️ Code Editor

- **Syntax Highlighting**: Color-coded G-code commands (rapid moves, linear moves, circular moves)
- **Customizable Editor**:
  - Adjustable font family, size, and style
  - Configurable margins and line numbers
  - Caret line highlighting
  - Whitespace visibility control
- **Advanced Editing**:
  - Find and Replace with options (case-sensitive, whole word, wrap-around)
  - Undo/Redo operations
  - Copy/Cut/Paste functionality
  - Line numbering with customizable spacing

### 📊 Visualization

- **3D Plotting**: Real-time visualization of toolpaths
- **Multiple Views**: 3D, Top, Front, and Left view modes
- **Zoom Controls**: In/out zoom functionality
- **Grid Display**: Configurable grid with adjustable size and spacing
- **Lathe Mode**: Specialized view for lathe operations
- **Toolpath Animation**: Step-by-step simulation with playback controls

### 🔧 Code Manipulation

- **Renumber Blocks**: Add, remove, or renumber N-line sequences
- **Cleanup Tools**:
  - Remove unnecessary spaces
  - Delete empty lines
  - Eliminate comments
- **Block Skipping**: Skip commented lines with leading "/"

### 📤 Export Options

- **Multiple Output Languages**: Support for different G-code dialects
- **Export Modes**:
  - Trace export from the authoritative logical Motion Trace
  - `EXPANDED TURN PROGRAM` in Lathe Mode
  - `EXPANDED MILL PROGRAM` in Milling Mode
  - Absolute or incremental positioning for standard trace export
  - Force address output
  - Leading zero suppression
- **Program Headers/Footers**: Customizable start and end program blocks
- **Safety Lines**: Option to add standard safety commands
- **Delimiter Control**: Space or no-space between commands

### 📈 Analysis Tools

- **Statistics**: Calculate toolpath length and machining time
- **Coordinate Limits**: Determine min/max X, Y, Z values
- **Feed Rate Analysis**: Identify rapid vs. feed moves

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

### Installation Steps

1. Clone the repository:

   ```bash
   git clone https://github.com/MaestroFusion360/easy_gcode_plot.git
   cd easy_gcode_plot
   ```

2. Create/update the project environment from `pyproject.toml` and `uv.lock`:

   ```bash
   uv sync
   ```

3. Run the application:

   ```bash
   uv run python main.py
   ```

The same kernel is available without Qt through the CLI:

```bash
uv run python -m app parse program.nc --lang fanuc_turn
uv run python -m app trace program.nc --lang fanuc_turn -o trace.json
uv run python -m app analyze program.nc --lang fanuc_turn
uv run python -m app export program.nc --lang fanuc_turn -o expanded.nc
uv run python -m app export program.nc --lang fanuc_turn --mode program -o expanded-turn.nc
uv run python -m app export program.nc --lang fanuc_mill --mode program -o expanded-mill.nc
uv run python -m app export program.nc --lang fanuc_turn --mode cycles -o expanded-cycles.nc
```

## Usage

### Basic Workflow

1. Open a G-code file using **File → Open** or by dragging and dropping it.
2. Select **ISO G-code** for syntax highlighting, then press **Refresh** to apply.
3. View the toolpath in the **3D plot window**.
4. Edit the code in the **syntax-highlighted editor**.
5. Simulate the program using the **playback controls**.
6. Export the modified G-code with the desired settings.

### Key Interface Elements

#### 1. Editor Panel

- Left side of the application
- Syntax-highlighted G-code display
- Line numbers and margin area
- Context menu for editing operations

#### 2. 3D Plot Panel

- Right side of the application
- Interactive 3D visualization
- View control buttons (3D, Top, Front, Left)
- Grid toggle option

#### 3. Control Panel

- **Slider**: Navigate through toolpath steps
- **Coordinate Display**: Current X, Y, Z, I, J, K, Feed values
- **Playback Controls**: Play, stop, forward, backward buttons

#### 4. Status Bar

- Character count
- Cursor position
- Progress bar for long operations

### Export Configuration

Access via File → Export Options:

1. **Language Selection**: Choose G-code dialect or export mode
2. **Expanded program modes**:
   - `EXPANDED TURN PROGRAM` is available only in Lathe Mode.
   - `EXPANDED MILL PROGRAM` is available only in Milling Mode.
   - CLI `--mode program` is available for both `fanuc_turn` and `fanuc_mill`; `--mode cycles` is turning-only.
3. **Output Mode**: Absolute/Incremental for standard trace export
4. **Address Forcing**: Always output G/M codes
5. **Program Start/End**: Custom program headers/footers
6. **Sequence Numbers**: Configure N-line numbering
7. **Formatting**: Delimiters and zero suppression

## Supported G-code Commands

The native kernel currently exposes two execution profiles: `fanuc_mill` and `fanuc_turn`. Both use the same AST, Macro B/control-flow foundation, diagnostics and logical Motion Trace.

### Common motion and execution

- `G00/G01/G02/G03`: rapid, linear and circular interpolation
- `G17/G18/G19`: interpolation planes where applicable
- `G20/G21`: units
- `G28`: configured primary reference return; otherwise handled fail-closed
- `G30`: secondary reference return is position-changing and remains fail-closed unless its reference is known
- `G54-G59`: work coordinate systems
- Macro B expressions and assignments, `IF/GOTO`, `WHILE/END`
- `M98/M99`: subprogram execution
- `M00/M01/M02/M03/M04/M05/M08/M09/M30`: machine signals/program control

### FANUC milling

- XYZ absolute/incremental motion (`G90/G91`)
- IJK/R arcs and helical interpolation
- `G80/G81/G82/G83/G84` canned cycles
- `G40/G41/G42` cutter-compensation modal state is tracked, but cutter-radius geometry is not applied; explicit G41/G42 blocks are reported as `UNVERIFIED`
- `G43/G49` tool-length compensation state is tracked and preserved for export, but H-offset geometry is not applied; explicit G43 blocks are reported as `UNVERIFIED`
- `G98/G99` canned-cycle return mode

### FANUC turning

- X/Z and U/W programming, diameter/radius handling, I/K/R arcs
- `G32/G33` threading motion
- `G70-G76` finish/roughing/grooving/threading cycles
- modal `G90/G92/G94` turning cycles
- turning `G83/G84`
- `G40/G41/G42` tool-nose compensation with tool-tip orientation support
- controller-dependent or unknown position-changing semantics are reported as `UNVERIFIED`/fail-closed rather than guessed

## Configuration

### Settings File

The application saves configuration to `config.ini` **outside the program
directory**, in the per-user config location (on Windows:
`%LOCALAPPDATA%\easy-gcode-plot\config.ini`). On the first run a legacy
`config.ini` found next to the launcher is copied there once. The file stores
the following sections:

#### Plot Settings

- Timer speed
- Arc calculation type
- Machine coordinates
- Lathe mode
- Line/background/grid colors
- Grid size and spacing

#### Editor Settings

- Font family, size, weight, italic
- Caret line color and visibility
- Whitespace and EOL visibility
- Margin settings

#### Export Settings

- Language selection
- Address forcing
- Incremental mode
- Program start/end strings
- Sequence number configuration

#### Geometry Settings

- Window position and size
- Maximized state

## Troubleshooting

### Common Issues

1. **Plot Not Displaying**
   - Ensure the G-code contains valid motion commands
   - Check for syntax errors in the code
   - Verify machine coordinates are set correctly

2. **Export Errors**
   - Confirm output language compatibility
   - Check for invalid characters in custom headers/footers
   - Ensure sufficient disk space

3. **Performance Issues**
   - Reduce plot complexity for very large files
   - Close unnecessary applications
   - Update graphics drivers

### Logging

The application creates a `main.log` file for debugging:

- Log level: DEBUG
- Location: Application directory
- Contains: Conversion errors, export issues, general exceptions

## Technical Details

### Architecture

```text
NC source
   ↓
Lexer / AST
   ↓
Semantic instructions
   ↓
FANUC resolver / modal execution
   ↓
ExecutionResult + logical TraceMotion + diagnostics/signals
   ├─ CLI
   ├─ statistics
   ├─ trace-based exporter
   └─ renderer sampling → PyQtGraph/OpenGL GUI
```

The CNC kernel under `app/gcode/kernel/` has no Qt, C#, `pythonnet` or subprocess bridge dependency. Arcs remain logical arcs in the kernel and are sampled only by the visualization/export adapters. The GUI no longer owns a second `lst*` execution model.

### Performance

- Automatic scene refresh is enabled for editor contents up to 5,000 lines; larger files require an explicit **Refresh**
- Arcs remain logical in the kernel and are sampled only by rendering/export adapters
- GUI playback and statistics consume the same authoritative logical Motion Trace

### File Support

- **Input**: Standard G-code (.nc, .cnc, .txt)
- **Output**: Customizable G-code formats
- **Encoding**: UTF-8

## Development

### Building from Source

```bash
# Install runtime and default development dependencies
uv sync

# Run tests and code-quality checks
uv run pytest
uv run ruff check .
uv run ruff format --check .

# Create the release-compatible Windows executable
./scripts/build.ps1
```

### Code Structure

```text
main.py
app/
├─ __main__.py                 GUI/CLI dispatcher
├─ cli.py                      parse/trace/analyze/export CLI
├─ main_window.py              PyQt6/QScintilla/PyQtGraph consumer of ExecutionResult
├─ gcode/
│  ├─ core.py                  formatting and generic UI-side helpers
│  ├─ exporter.py              trace-based export; no source re-parsing
│  ├─ trace_tools.py           logical arc geometry, sampling and statistics
│  └─ kernel/
│     ├─ api.py                public execute() facade
│     ├─ ast.py / model.py     source and execution models
│     ├─ execution.py          Macro B/control flow/subprogram execution
│     ├─ interpreter.py        FANUC turning resolver
│     ├─ milling.py            FANUC milling resolver
│     ├─ cycles.py             turning cycles
│     ├─ tool_compensation.py  turning tool-nose compensation
│     └─ signals.py            machine signals/program end
├─ ui/                         Qt dialogs, lexer and generated Designer files
└─ resources/                  icons/resources
tests/                         unit, regression, CLI and GUI-kernel contract tests
```

Run the application from the project root with either `uv run python main.py` or
`uv run python -m app`.

To regenerate the Designer output after editing a `.ui` file, use the `pyuic6`
tool shipped with PyQt6:

```bash
uv run pyuic6 app/ui/generated/export.ui -o app/ui/generated/export.py
```

> Note: PyQt6 wheels no longer bundle `pyrcc6`. `app/resources/files_res.py` is
> committed pre-generated; edit it only together with `files_res.qrc`.

### Adding Features

- Add or extend CNC semantics in `app/gcode/kernel/` and cover them with logical-trace regression tests.
- Keep rendering in `app/gcode/trace_tools.py`/GUI consumers; do not tessellate arcs in the kernel.
- Extend export through `ExecutionResult`/`TraceMotion`; do not add a second parser or modal execution path.

## License

MIT License - See [LICENSE](License.md) for details

---

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=MaestroFusion360-easy-gcode-plot&label=Project+Views&color=blue" alt="Project Views" />
</p>
