# Easy G-Code Plot

[![Windows build](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml/badge.svg)](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml)

Download the current standalone Windows executable from [GitHub Releases](https://github.com/MaestroFusion360/easy_gcode_plot/releases). The packaged application does not require a separate Python installation.

<!-- markdownlint-disable MD033 -->

<details>
  <summary><h2>Main Screen</h2></summary>
  <p align="center">
    <img src="assets/img1.png" alt="Main Screen">
  </p>
</details>

<details>
  <summary><h2>STL Playback</h2></summary>
  <p align="center">
    <img src="assets/img2.gif" alt="STL Playback">
  </p>
</details>

---

Easy G-Code Plot is a desktop G-code viewer, editor, analyzer, simulator and trace exporter for FANUC-style turning and milling programs.

The application parses and executes source once through a shared CNC kernel. Rendering, playback, Stock Removal, statistics, CLI analysis and export all consume the same resolved logical trace.

## Highlights

- FANUC turning and milling execution profiles.
- Macro B expressions, conditions, loops and subprograms.
- G-code editor with highlighting, line numbers, search/replace and cleanup tools.
- Interactive OpenGL plot with perspective and orthographic views.
- Logical-motion playback with source-line synchronization.
- Lathe Stock outline and cutter-aware Stock Removal playback, including pitch- and insert-driven thread profiles.
- Turning G70–G76 cycles, G32/G33/G92 threading, tool-nose compensation and direct A/C/corner-R programming.
- Milling canned cycles, helical arcs, cutter-radius compensation and G50/G51/G52/G68/G69 coordinate transforms.
- Milling IJK arc-mode autodetection with manual Relative/Absolute fallback for ambiguous programs.
- Persistent optional-block execution control for leading `/` blocks without editing the NC source.
- ASCII/binary STL reference overlay with solid and feature-edge modes.
- Tokens diagnostics, toolpath statistics and millimetre/inch display.
- English and Russian user interface; the language is selected in `Settings → Options → General` and applied after restarting the application.
- Light and Dark themes; the dark theme adapts the window chrome, the editor, the plot canvas and the toolpath colors.
- Full-program, Expanded Execution, Plot Data and DXF exports.
- SQLite-backed turning and milling tool libraries with live geometry preview and JSON/CSV tool export.
- UTF-8 and Windows-1251 document support.

Detailed behavior, supported commands, configuration, troubleshooting and development notes are in the [FAQ](FAQ.md). The same document is packaged with the application and opens from **Help → FAQ**.

## Quick start

### Windows executable

Download and extract the latest archive from [Releases](https://github.com/MaestroFusion360/easy_gcode_plot/releases), then run the executable.

### Run from source

Requirements:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/MaestroFusion360/easy_gcode_plot.git
cd easy_gcode_plot
uv sync --no-dev
uv run --no-dev python main.py
```

## Basic workflow

1. Open or drag a `.nc`, `.cnc` or `.txt` program into the application.
2. Enable `Lathe Mode` for turning or leave it disabled for milling.
3. Configure WCS, machine home and tools when required.
4. Refresh and inspect the resolved toolpath.
5. Use playback, Tokens and Statistics to inspect execution.
6. Optionally import an STL reference model.
7. Export the required program or trajectory representation.

The application reports unsupported or ambiguous controller behavior explicitly instead of guessing geometry.

## Appearance and language

`Settings → Options → General` provides two application-level preferences:

- **Language** — switch between **English** and **Russian**. The change is applied after restarting the application; kernel diagnostics, log messages and G-code comments intentionally stay in English.
- **Theme** — switch between the native **Light** look and a **Dark** theme that also adapts the editor, the plot canvas and the standard toolpath colors. Plot colors customized on the **Colors** tab are preserved when the theme changes.

## CNC execution options

`Settings → Options → CNC / Execution` contains execution settings shared by Refresh, playback analysis and export:

- **Autodetect Arc Type** applies to milling IJK arcs. It selects relative-to-start or absolute-center interpretation when only one satisfies Arc tolerance; ambiguous programs use the manually selected Arc Type. Turning keeps FANUC relative I/K semantics.
- **Ignore Block Skip** excludes source blocks beginning with `/` from execution without changing the open file. Leave it disabled to execute those blocks normally. Expanded Execution uses the same resolved result and therefore excludes the same blocks.
- **Correction (G41/G42)** and **Arc tolerance** retain their existing geometry behavior.

Long Refresh operations use one cancellable execution dialog for tool discovery, parsing, execution, sampling and plot publication. Cancel cooperatively stops the active stage instead of waiting for the whole source to finish.

## Tool Library

`Settings → Tool Library` is the single tool-management window for both Milling and Turning. Each tab separates **Current Program** T-slot assignments from the persistent **Saved Library** and provides an automatically fitted preview of the selected tool. Current Program tools are temporary: literal T selections are discovered from the open NC program, comments are used to infer descriptions/type/dimensions when possible, and operation context selects D10 Drill for G81-G83, D10 Tap for G84 and OD Thread for turning G32/G33/G76/G92. Otherwise discovery uses D10 Flat Mill or Diamond 80 OD. New/Open resets these temporary assignments.

Saved Library tools are stored in the per-user SQLite database `tools.db`; `config.ini` stores application preferences and does not mirror tool definitions. Assigning a saved tool copies its geometry into the selected Current Program T slot without changing that program T number. Add/Edit/Duplicate/Remove and Save to Library change a working copy inside the dialog: **OK** commits its final state to `tools.db`, while **Cancel** discards it. Discovery and Current Program edits never write program tools automatically. Export writes the complete current working copy for the active machine kind as JSON or CSV, not only the selected row.

The turning library uses nine geometry types: Diamond 80, Diamond 35, Square, Round, Triangle, Groove, Thread, Drill and Tap. OD, ID and Face are stored separately as application flags and drive preview, trace orientation and Stock Removal without changing the geometry type.

## Supported areas

| Area          | Main support                                                                                                           |
| ------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Common        | G00–G03, G17–G21, G28, G54–G59, G90/G91, Macro B, M98/M99                                                              |
| Turning       | X/Z, U/W, I/K/R arcs, A/C/corner-R, G32/G33, G70–G76, G90/G92/G94 cycles, G96/G97, G98/G99                             |
| Milling       | XYZ, IJK/R and helical arcs, G50/G51/G52/G68/G69, G53, G80–G86, G94/G95, G40/G41/G42                                   |
| Visualization | 3D/orthographic plot, STL overlay, turning Stock outline/removal (including thread profiles), configured tool previews |
| Export        | Turning/Milling Full Program, Expanded Execution, Plot Data and DXF                                                    |

See [FAQ.md](FAQ.md) for limitations and exact semantics.

## CLI

The CLI uses the same execution kernel as the GUI:

```bash
uv run --no-dev python -m app parse program.nc --lang fanuc_turn
uv run --no-dev python -m app trace program.nc --lang fanuc_turn -o trace.json
uv run --no-dev python -m app analyze program.nc --lang fanuc_turn
uv run --no-dev python -m app export program.nc --lang fanuc_turn -o expanded.nc
```

Use `--lang fanuc_mill` for milling and `--encoding cp1251` for Windows-1251 source files.

## Development

Install development dependencies and run the checks:

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Windows PowerShell helpers are under `scripts/ps1/`; matching shell scripts are under `scripts/sh/`.

```powershell
.\scripts\ps1\test.ps1
.\scripts\ps1\lint.ps1
.\scripts\ps1\build.ps1
```

The CNC core is intentionally independent from the GUI. `app/gcode/kernel/` is organized by responsibility (`api`, `frontend`, `geometry`, `lathe_cycles`, `compensation`, `runtime`, `milling`), while `app/gcode/export/` consumes the resolved kernel result instead of reinterpreting source G-code. New CNC semantics belong in the core first and should be covered by deterministic regression tests before any UI integration.

The detailed package map, compatibility rules, Qt generation and release instructions are documented in the [FAQ development section](FAQ.md#development).

## License

MIT License — see [LICENSE.md](LICENSE.md).

---

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=MaestroFusion360-easy-gcode-plot&label=Project+Views&color=blue" alt="Project Views">
</p>
