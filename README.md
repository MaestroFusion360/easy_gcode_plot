# Easy G-Code Plot

Desktop G-code editor, analyzer, backplotter and trace exporter for FANUC-style turning and milling, with native SINUMERIK 840D milling support.

[![Build and release](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/release.yml/badge.svg)](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/release.yml)

**Project site:** [English](docs/index.html) · [Русский](docs/ru/index.html)
See [docs/PUBLISHING.md](docs/PUBLISHING.md) for local preview and GitHub Pages setup.

<!-- markdownlint-disable MD033 -->

<p align="center">
  <img src="docs/assets/img2.gif" alt="Easy G-Code Plot main window">
</p>

<details>
  <summary><strong>More screenshots</strong></summary>

  <p align="center">
    <img src="docs/assets/impeller.gif" alt="STL playback">
  </p>

  <p align="center">
    <img src="docs/assets/img3.png" alt="Milling">
  </p>

  <p align="center">
    <img src="docs/assets/img4.png" alt="Turning">
  </p>

  <p align="center">
    <img src="docs/assets/stock_removal.gif" alt="Lathe stock removal simulation">
  </p>

  <p align="center">
    <img src="docs/assets/4ax_table.gif" alt="Indexed rotary-axis milling">
  </p>
</details>

---

## What it is

Easy G-Code Plot models supported CNC program semantics and toolpath geometry. It is not a complete physical CNC-machine simulator.

The GUI, playback, statistics, stock-removal tools, CLI analysis and exporters all consume the same authoritative execution result produced by the shared CNC kernel:

```text
G-code source
    │
    ▼
Parser / controller semantics
    │
    ▼
CNC execution kernel
    │
    ▼
Resolved execution result
    ├── GUI rendering and playback
    ├── statistics
    ├── batch analysis
    ├── trace export
    └── NC / DXF export
```

Unsupported or ambiguous controller behavior is reported explicitly instead of being converted into guessed geometry.

## Highlights

### FANUC-style turning

- Macro B expressions, conditions and loops.
- `G65` custom-macro calls and `M98/M99` subprograms.
- Turning cycles `G70`–`G76`.
- `G32`, `G33` and `G92` threading.
- Tool-nose compensation.
- Direct A/C/corner-R programming.
- Cutter-aware Stock Removal, including thread profiles.

### FANUC-style milling

- Canned cycles and helical arcs.
- `G15/G16` polar-coordinate programming.
- Cutter-radius compensation.
- `G10`, `G50`, `G51`, `G52`, `G54.1`, `G68` and `G69` coordinate operations.
- Indexed 3+2 milling with `G68.2/G53.1`.
- Continuous five-axis TCP motion with `G43.4` on supported angled AC/BC table profiles.
- Indexed A/B milling and planar X/C contour mapping with selected rotary profiles.
- Fixture coverage for `4ax_table_a`, `4ax_table_b` and `4ax_table_c`.
- Tapered ball-mill preview (`TAPER_BALL_MILL`).

### SINUMERIK 840D

- Native three-axis milling for `.mpf` / `.spf`.
- Native `G0/G1/G2/G3`, `CR=`, work offsets, compensation and common tool/spindle/coolant commands.
- `G290/G291` native / ISO Dialect M switching.
- Modal `MCALL CYCLE81/82/83/84`.
- Native R parameters for the supported numeric subset.
- `TURN=` multi-revolution arc handling.
- Resolved conversion between supported FANUC, SINUMERIK ISO-M and SINUMERIK native milling geometry.

See [SINUMERIK 840D](#sinumerik-840d) for the exact supported subset and current limitations.

### GUI and visualization

- G-code editor with syntax highlighting, line numbers, search, replace and cleanup tools.
- Interactive OpenGL toolpath.
- Logical-motion playback with source-line synchronization.
- Toolpath statistics.
- CNC editing assistants for hole patterns, pockets and reusable snippets.
- ASCII and binary STL overlays with solid and feature-edge modes.
- STL positioning, transforms, arrays, sections and statistics.
- SQLite-backed turning and milling tool libraries.
- English and Russian UI.
- Light and Dark themes.
- UTF-8 and Windows-1251 input.

### Export and automation

- Full Program export.
- Expanded Execution export.
- Plot Data export.
- DXF export.
- CLI `parse`, `trace`, `analyze`, `batch`, `export` and `batch-export`.
- JSON and CSV batch reports.
- Native Cython acceleration with compatible Python fallback.

Detailed controller behavior, limits, configuration and troubleshooting are documented in [FAQ.md](FAQ.md), also available through **Help → FAQ**.

---

## Controller support overview

| Area | FANUC-style | SINUMERIK 840D native |
| --- | --- | --- |
| Turning | Yes | No |
| Three-axis milling | Yes | Yes |
| Macro / variable subset | Macro B | R parameters |
| Drilling / tapping cycles | Yes | `MCALL CYCLE81/82/83/84` |
| Indexed rotary milling | Yes | Not yet |
| Continuous TCP | `G43.4` | Not yet |
| Tilted working plane | `G68.2/G53.1` | `CYCLE800` not yet |
| Native controller conversion | FANUC / ISO-M | Resolved native output |
| Batch analysis | Yes | Yes |

`CLEAN` CLI status means that the supported execution model produced no diagnostics. It is not machine validation.

---

## SINUMERIK 840D

### Input modes

Every `.mpf` / `.spf` file is treated as a SINUMERIK container.

- Native mode is the default.
- Standalone `G290` selects native Siemens syntax.
- Standalone `G291` selects ISO Dialect M.
- CLI commands still use `--lang fanuc_mill` for the common milling geometry model.

For recognized MPF/SPF documents, the GUI disables rotary-kinematics profiles and uses **Rotary kinematics = None**. Opening a FANUC document or creating a new document restores the previous saved profile.

### Native subset

Native support currently includes:

- `G0/G1/G2/G3`
- `CR=`
- plane selection
- absolute / incremental positioning
- metric `G710`
- work offsets
- `G40/G41/G42`
- `D0/D1`
- tool, spindle and coolant commands
- machine-coordinate `G0 SUPA`
- `MSG`
- `WORKPIECE`
- `G64`
- semicolon comments

`MSG`, `WORKPIECE`, `G64` and comments do not generate phantom geometry.

Empty `CYCLE800()` is accepted only when no rotary frame is active.

### R parameters

The supported native subset accepts numeric assignments such as:

```text
R1=500
R2=6000
```

and references in supported addresses and cycles, including:

```text
F=R1
S=R2
X=R1
CR=R1
TURN=R1
```

R state is separate from FANUC `#` variables and resets for each execution.

Undefined references, arithmetic/control flow, arrays and Siemens system variables are outside the current subset.

### MCALL cycles

Modal `MCALL CYCLE81/82/83/84` expands supported numeric parameters into resolved motions. Bare `MCALL` cancels the active cycle.

`CYCLE84` implements the supported CAM-oriented single-pass metric right-hand tapping subset. It models trajectory and logical spindle signals, not spindle-angle simulation.

See [FAQ.md](FAQ.md#sinumerik-840d-input) and [FAQ_RU.md](FAQ_RU.md#sinumerik-840d) for exact parameter constraints.

### TURN=

`TURN=n` supports integer values from `0` to `999` for supported `G2/G3` arcs using IJK or `CR=`.

The kernel keeps a single resolved arc with the complete sweep. Rendering, playback and statistics preserve all revolutions. DXF uses sampled polylines when required.

### Current kinematic limit

Native SINUMERIK execution currently supports three-axis XYZ trajectories only.

Parameterized tilted planes, rotary motion and TCP transformations are intentionally rejected with diagnostics. Full `CYCLE800` and `TRAORI/TRAFOOF` support is planned for future kernel development.

### Native acceleration

Contiguous literal position blocks can use the Cython execution path. The Python capability gate runs before state changes.

Native declarations, `G290/G291` switches and controller operations break an accelerated run; later eligible blocks can resume acceleration. Blocks under active native cycles stay on the Python reference path until the cycle is cancelled.

---

## Export model

Exporters consume the resolved kernel result instead of interpreting G-code independently.

This is intentional: controller execution is resolved once, then downstream consumers serialize or visualize the same geometry.

### Resolved conversion

Resolved Program Conversion supports:

- `fanuc_mill`
- `sinumerik_iso`
- `sinumerik_native`

for supported three-axis milling input.

Example:

```powershell
.\easy_gcode_plot_cli.exe export fanuc_part.nc --lang fanuc_mill --mode resolved --target-dialect sinumerik_native -o native_part.mpf

.\easy_gcode_plot_cli.exe export native_part.mpf --lang fanuc_mill --mode resolved --target-dialect fanuc_mill -o resolved_part.nc
```

Cycles and variables are evaluated before serialization. Resolved output is written in a zero-offset frame.

SINUMERIK native output uses absolute IJK and can preserve `TURN=`.

### Full Program conversion

Source-preserving `--mode full` is limited to the verified FANUC ↔ SINUMERIK ISO-M subset.

Native SINUMERIK Full Program conversion is not implemented.

Programs containing unsupported rotary/TCP/tilted-plane semantics are rejected before NC output is written. The exporter does not invent `TRAORI`, `TRAFOOF`, `CYCLE800` or controller-switching sequences.

### GUI export

The GUI provides the verified SINUMERIK 840D ISO-M (`G291`) target.

Native SINUMERIK resolved conversion is currently a CLI capability.

---

## Quick start

### Windows release

Download the GUI executable and `easy_gcode_plot_cli.exe` from [GitHub Releases](https://github.com/MaestroFusion360/easy_gcode_plot/releases/latest).

Python and Visual Studio are not required for packaged applications.

```powershell
.\easy_gcode_plot_cli.exe --help
.\easy_gcode_plot_cli.exe analyze program.nc --lang fanuc_turn
.\easy_gcode_plot_cli.exe batch C:\Programs --lang fanuc_mill -o C:\Reports
```

### Linux release

Download the Linux x64 archive and matching `.sha256` file.

```bash
sha256sum -c Easy-G-Code-Plot-*-Linux-x64.tar.gz.sha256
tar -xzf Easy-G-Code-Plot-*-Linux-x64.tar.gz

./easy_gcode_plot
./easy_gcode_plot_cli --help
```

### Run from source

Requirements:

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- C compiler:
  - Visual Studio Build Tools with **Desktop development with C++** on Windows
  - platform compiler and Python development headers on Linux

```bash
git clone https://github.com/MaestroFusion360/easy_gcode_plot.git
cd easy_gcode_plot

uv sync --no-dev
uv run --no-dev python main.py
```

`uv sync` builds the tracked Cython `.pyx` sources. Generated `.c`, `.pyd` and `.so` files are not stored in Git.

If native extensions cannot be loaded, the application remains functional through the slower Python fallback.

---

## GUI workflow

1. Open or drag a `.nc`, `.cnc`, `.ptp`, `.mpf`, `.spf` or `.txt` program into the application.
2. Enable **Lathe Mode** for turning, or leave it disabled for milling.
3. Configure WCS, machine home and tools when required.
4. For indexed FANUC milling, select the matching **Settings → Rotary kinematics** profile.
5. Refresh and inspect the resolved toolpath.
6. Use playback, Tokens/Macro Variables and Statistics to inspect execution.
7. Optionally import an STL reference model.
8. Export the required program or trajectory representation.

**File → Print** (`Ctrl+P`) produces a page-fitted vector drawing in the current camera orientation.

---

## CNC editing assistants

The **CNC Functions** menu and toolbar provide:

- **Hole Calculator** — circular or serpentine rectangular hole patterns with live XY preview.
- **Pocket Calculator** — circular or rectangular milling fragments with multiple depths, stock, conventional/spiral clearing, helical entry and optional finish pass.
- **Snippets** — reusable persistent G-code fragments stored in the per-user SQLite database.

Hole and Pocket calculators are milling-only assistants.

The calculators insert code into the editor; they do not execute or export it automatically. Refresh the toolpath after reviewing the generated block.

---

## STL overlays

ASCII and binary STL models can be used as visual references.

The **Settings → STL Objects** panel supports:

- independent undo/redo
- base-point and bounding-box picking
- positioning and transforms
- circular and rectangular arrays
- 3D sections
- copyable statistics
- millimetre / inch display

Solid STL mode can hide toolpath segments that are behind the model surface.

---

## Tool Library

**Settings → Tool Library** manages separate milling and turning tool sets.

- **Current Program** contains temporary T-slot assignments discovered or configured for the open program.
- **Saved Library** contains persistent tools stored in the per-user `tools.db`.

Literal T selections, comments and operation context can infer tool descriptions and geometry. Program discovery never modifies the saved library automatically.

The turning library supports:

- Diamond 80
- Diamond 35
- Square
- Round
- Triangle
- Groove
- Thread
- Drill
- Tap

OD, ID and Face are separate application flags.

JSON and CSV export write the complete working library for the active machine type.

---

## CLI

The CLI uses the same CNC kernel as the GUI.

### Common commands

```powershell
.\easy_gcode_plot_cli.exe parse program.nc --lang fanuc_turn

.\easy_gcode_plot_cli.exe trace program.nc --lang fanuc_turn -o trace.json

.\easy_gcode_plot_cli.exe analyze program.nc --lang fanuc_turn

.\easy_gcode_plot_cli.exe batch .\programs --lang fanuc_mill -o batch-report

.\easy_gcode_plot_cli.exe export program.nc --lang fanuc_turn -o expanded.nc

.\easy_gcode_plot_cli.exe batch-export .\programs --lang fanuc_mill --mode expanded -o normalized
```

Indexed example:

```powershell
.\easy_gcode_plot_cli.exe analyze indexed.nc --lang fanuc_mill --kinematics 4ax_table_b
```

SINUMERIK examples:

```powershell
.\easy_gcode_plot_cli.exe analyze part.mpf --lang fanuc_mill

.\easy_gcode_plot_cli.exe export part.mpf --lang fanuc_mill --mode resolved --target-dialect fanuc_mill -o part.nc

.\easy_gcode_plot_cli.exe export fanuc_part.nc --lang fanuc_mill --mode resolved --target-dialect sinumerik_native -o part.mpf
```

### Batch analysis

`batch` scans recursively by default.

Default recognized extensions:

```text
.nc .cnc .ptp .mpf .spf .tap .txt
```

FANUC programs without a conventional NC extension can also be discovered from their first blocks when default discovery is used.

Reports:

```text
batch_report.json
batch_report.csv
```

Per-file status:

- `CLEAN`
- `WARNINGS`
- `ERRORS`

An empty scan produces `NO_FILES`.

Reports include diagnostics, motion/executed-block counts and unknown or unsupported G/M codes.

Use:

```text
--extensions .nc,.mpf
```

to restrict file types, or:

```text
--top-level-only
```

to disable recursive scanning.

### Batch export

`batch-export` writes a mirrored output tree plus:

```text
batch_export_report.json
batch_export_report.csv
```

Source files are never modified.

Files with invalid or incomplete execution are skipped while the remaining inputs continue.

For mixed indexed batches, `--kinematics-map` can assign a profile per relative input path.

### Preset scripts

Windows:

```powershell
.\scripts\ps1\batch\batch_mill.ps1
.\scripts\ps1\batch\batch_turn.ps1
.\scripts\ps1\batch\batch_export_mill.ps1
.\scripts\ps1\batch\batch_export_turn.ps1
```

Linux:

```bash
bash scripts/sh/batch/batch_mill.sh
bash scripts/sh/batch/batch_turn.sh
bash scripts/sh/batch/batch_export_mill.sh
bash scripts/sh/batch/batch_export_turn.sh
```

Run:

```powershell
.\easy_gcode_plot_cli.exe --help
```

or:

```powershell
.\easy_gcode_plot_cli.exe batch --help
```

for the complete command-line reference.

---

## Settings

The main execution settings are under **Settings → Options**.

### General

- Language
- Theme
- Auto Update
- Auto update max segments
- Maximum generated motions
- Toolbar icon size

### CNC / Execution

- Autodetect Arc Type
- Ignore Block Skip
- G41/G42 correction
- Arc tolerance
- Arc sampling preset
- Maximum / minimum circular radius
- Minimum chord length

Sampling controls affect GUI trace representation without changing the resolved CNC execution geometry.

Explicit Refresh operations are cancellable.

---

## Development

Install development dependencies and run the standard checks:

```bash
uv sync --group dev

uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Build helpers are available for both platforms:

| Task | Windows PowerShell | Linux shell |
| --- | --- | --- |
| Tests | `.\scripts\ps1\test.ps1` | `bash scripts/sh/test.sh` |
| Lint | `.\scripts\ps1\lint.ps1` | `bash scripts/sh/lint.sh` |
| Native extensions | `.\scripts\ps1\build-native.ps1` | `bash scripts/sh/build-native.sh` |
| PyInstaller package | `.\scripts\ps1\build.ps1` | `bash scripts/sh/build.sh` |

Linux CLI build:

```bash
bash scripts/sh/build.sh --console --skip-tests
./dist/easy_gcode_plot_cli --help
```

Native and release builds use the separate `.venv-build` environment and rebuild when tracked Cython sources change.

The CNC kernel lives under:

```text
app/gcode/kernel/
```

Exporters consume the kernel's authoritative execution result instead of interpreting G-code again.

New CNC semantics belong in the kernel and should be covered by deterministic regression tests.

See [FAQ.md](FAQ.md#development) for package structure, Qt generation, detailed settings and release notes.

---

## License

MIT License — see [LICENSE.md](LICENSE.md).

---

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=MaestroFusion360-easy-gcode-plot&label=Project+Views&color=blue" alt="Project Views">
</p>
