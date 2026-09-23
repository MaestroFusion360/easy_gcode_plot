# Easy G-Code Plot

[![Windows build](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml/badge.svg)](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml)

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

Easy G-Code Plot is a desktop editor, analyzer, simulator and trace exporter for FANUC-style turning and milling programs. Rendering, playback, Stock Removal, statistics, CLI analysis and export consume one resolved trace produced by the shared CNC kernel.

## Highlights

- FANUC turning and milling with Macro B expressions, conditions, loops, `G65` custom-macro calls and `M98/M99` subprograms.
- Turning G70–G76 cycles, G32/G33/G92 threading, tool-nose compensation and direct A/C/corner-R programming.
- Milling canned cycles, helical arcs, `G15/G16` polar-coordinate programming, cutter-radius compensation and G10/G50/G51/G52/G54.1/G68/G69 coordinate operations.
- G-code editor with highlighting, line numbers, search, replace and cleanup tools.
- CNC editing assistants for circular/grid hole patterns, circular/rectangular pockets and reusable persistent snippets.
- Interactive OpenGL toolpath, logical-motion playback and source-line synchronization.
- Toolpath statistics and CIMCO-style UTF-8 Tool List export from the resolved trace and configured tools.
- Cutter-aware turning Stock Removal, including thread profiles.
- ASCII and binary STL overlays with solid and feature-edge modes.
- SQLite-backed turning and milling tool libraries.
- Full Program, Expanded Execution, Plot Data and DXF exports.
- English and Russian UI, Light and Dark themes, UTF-8 and Windows-1251 files.
- Native Cython acceleration with a compatible Python fallback.

Detailed controller behavior, limitations, configuration and troubleshooting are documented in [FAQ.md](FAQ.md), also available through **Help → FAQ**.

## Quick start

### Windows executable

Download the latest standalone `.exe` from [GitHub Releases](https://github.com/MaestroFusion360/easy_gcode_plot/releases) and run it. Python and Visual Studio are not required for the packaged application.

### Run from source

Requirements:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- A C compiler: Visual Studio Build Tools with **Desktop development with C++** on Windows, or the platform compiler and Python development headers on Linux/macOS.

```bash
git clone https://github.com/MaestroFusion360/easy_gcode_plot.git
cd easy_gcode_plot
uv sync --no-dev
uv run --no-dev python main.py
```

`uv sync` compiles the tracked Cython `.pyx` sources. Generated `.c`, `.pyd` and `.so` files are not stored in Git. If native extensions cannot be loaded, the application remains functional through the slower Python fallback.

## Basic workflow

1. Open or drag a `.nc`, `.cnc` or `.txt` program into the application.
2. Enable `Lathe Mode` for turning or leave it disabled for milling.
3. Configure WCS, machine home and tools when required.
4. Refresh and inspect the resolved toolpath.
5. Use playback, Tokens/Macro Variables and Statistics to inspect execution. The Macro Variables tab shows the actual Macro B state captured at the current logical playback step.
6. Use **CNC Functions → Hole Calculator**, **Pocket Calculator** or **Snippets** to generate and insert frequently used code at the editor caret.
7. Optionally import an STL reference model.
8. Export the required program or trajectory representation.

## CNC editing assistants

The **CNC Functions** menu and toolbar provide three editor tools:

- **Hole Calculator** inserts coordinates for holes distributed around a circle or over a serpentine rectangular grid and shows a live XY preview.
- **Pocket Calculator** generates a milling fragment for circular or rectangular pockets. It supports clockwise/counterclockwise cutting, multiple Z depths, XY/Z stock, conventional or spiral clearing, helical entry and an optional finish pass along the calculated tool-center contour. Its compact resizable layout includes a live XY preview; rectangular Spiral generates interior clearing before the final contour.
- Hole and Pocket calculators are milling-only assistants: their actions and Insert buttons are disabled in Lathe mode. Because calculation is already reflected by the live preview, the final action is simply **Insert**.
- **Snippets** manages reusable G-code fragments. Snippets can be added, edited, renamed, reordered, deleted and inserted at the current editor caret. They are stored in the per-user SQLite database `snippets.db`; legacy UTF-8 files from the adjacent `snippets` directory are imported once and retained as a backup. Unsaved edits are protected by a Save/Discard/Cancel prompt when selection or dialog state would otherwise replace them, and manual ordering is persisted.

The calculators insert code into the editor; they do not execute or export it automatically. Refresh the toolpath after reviewing the generated block.

Unsupported or ambiguous controller behavior is reported explicitly instead of being converted into guessed geometry.

## Settings

### General

`Settings → Options → General` contains:

- **Language** — English or Russian; applied after restart.
- **Theme** — Light or Dark; custom colors from the **Colors** tab are preserved.
- **Auto Update** and **Auto update max segments** — control non-modal plot refresh while editing. The segment limit applies only to automatic rendering.
- **Maximum generated motions** — limits the total motions produced by one kernel execution and protects against runaway expansion.

### CNC / Execution

`Settings → Options → CNC / Execution` contains:

- **Autodetect Arc Type** — selects relative or absolute-center milling IJK interpretation when only one satisfies Arc tolerance.
- **Ignore Block Skip** — excludes blocks beginning with `/` without modifying the source.
- **Correction (G41/G42)** and **Arc tolerance** — control compensation and arc validation.
- **Arc sampling preset**, **Maximum circular radius**, **Minimum circular radius** and **Minimum chord length** — control GUI trace sampling without changing CNC execution geometry.

Explicit Refresh operations use a cancellable dialog covering tool discovery, parsing, execution, sampling and plot publication.

## Tool Library

`Settings → Tool Library` manages Milling and Turning tools:

- **Current Program** contains temporary T-slot assignments discovered or configured for the open program.
- **Saved Library** contains persistent tools stored in the per-user `tools.db` database.

Literal T selections, comments and operation context can infer tool descriptions and geometry. Assigning a saved tool copies its geometry without changing the program's T number. **OK** commits Saved Library changes; **Cancel** discards them. Program discovery never modifies the saved library automatically.

The turning library supports Diamond 80, Diamond 35, Square, Round, Triangle, Groove, Thread, Drill and Tap geometry. OD, ID and Face are separate application flags. JSON and CSV export writes the complete working library for the active machine type.

## CLI

The CLI uses the same execution kernel as the GUI:

```bash
uv run --no-dev python -m app parse program.nc --lang fanuc_turn
uv run --no-dev python -m app trace program.nc --lang fanuc_turn -o trace.json
uv run --no-dev python -m app analyze program.nc --lang fanuc_turn
uv run --no-dev python -m app export program.nc --lang fanuc_turn -o expanded.nc
```

Use `--lang fanuc_mill` for milling and `--encoding cp1251` for Windows-1251 input.

## Development

Install dependencies and run the checks:

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Build helpers have matching PowerShell and shell variants:

| Task | Windows PowerShell | Linux/macOS shell |
| --- | --- | --- |
| Tests | `.\scripts\ps1\test.ps1` | `bash scripts/sh/test.sh` |
| Lint | `.\scripts\ps1\lint.ps1` | `bash scripts/sh/lint.sh` |
| Native extensions | `.\scripts\ps1\build-native.ps1` | `bash scripts/sh/build-native.sh` |
| PyInstaller package | `.\scripts\ps1\build.ps1` | `bash scripts/sh/build.sh` |

Native and release builds reuse the separate `.venv-build` environment and rebuild when tracked Cython sources change. Use `-Refresh`/`--refresh` for a forced native-environment refresh; the full-build equivalents are `-RefreshBuildEnvironment`/`--refresh-build-environment`. PyInstaller validates and packages the native parser, executor and tool-discovery extensions.

The CNC kernel lives under `app/gcode/kernel/`; exporters consume its authoritative execution result instead of interpreting G-code again. New CNC semantics should be implemented in the kernel and covered by deterministic regression tests. See the [FAQ development section](FAQ.md#development) for package structure, Qt generation and release details.

## License

MIT License — see [LICENSE.md](LICENSE.md).

---

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=MaestroFusion360-easy-gcode-plot&label=Project+Views&color=blue" alt="Project Views">
</p>
