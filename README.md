# Easy G-Code Plot

[![Windows build](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml/badge.svg)](https://github.com/MaestroFusion360/easy_gcode_plot/actions/workflows/windows-release.yml)

Download the current standalone Windows executable from [GitHub Releases](https://github.com/MaestroFusion360/easy_gcode_plot/releases). The packaged application does not require a separate Python installation.

<!-- markdownlint-disable MD033 -->

<details>
  <summary><h2>Main Screen</h2></summary>

<p align="center">
  <div style="text-align: center;">
    <img src="assets/img1.png" alt="Easy G-Code Plot">
  </div>
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
- Lathe Stock outline and cutter-aware Stock Removal playback.
- Turning G70–G76 cycles, tool-nose compensation and direct A/C/corner-R programming.
- Milling canned cycles, helical arcs and cutter-radius compensation.
- ASCII/binary STL reference overlay with solid and feature-edge modes.
- Tokens diagnostics, toolpath statistics and millimetre/inch display.
- Full-program, Expanded Execution, Plot Data and DXF exports.
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

## Supported areas

| Area | Main support |
| --- | --- |
| Common | G00–G03, G17–G21, G28, G54–G59, G90/G91, Macro B, M98/M99 |
| Turning | X/Z, U/W, I/K/R arcs, A/C/corner-R, G32/G33, G70–G76, G90/G92/G94 cycles, G96/G97, G98/G99 |
| Milling | XYZ, IJK/R and helical arcs, G53, G80–G86, G94/G95, G40/G41/G42 |
| Visualization | 3D/orthographic plot, STL overlay, turning Stock outline and removal, configured tool previews |
| Export | Turning/Milling Full Program, Expanded Execution, Plot Data and DXF |

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

Architecture, Qt generation and release instructions are documented in the [FAQ development section](FAQ.md#development).

## License

MIT License — see [LICENSE.md](LICENSE.md).

---

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=MaestroFusion360-easy-gcode-plot&label=Project+Views&color=blue" alt="Project Views">
</p>
