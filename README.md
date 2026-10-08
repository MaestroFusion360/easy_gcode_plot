# Easy G-Code Plot

Desktop G-code editor, analyzer, backplotter and NC/DXF exporter for FANUC turning/milling and SINUMERIK 840D milling (native and ISO-M), including supported native 3+2 and continuous five-axis CAM toolpaths.

Checked CAM examples include programs generated in Autodesk Fusion 360 and Siemens NX 2312 with SINUMERIK 840D and FANUC postprocessors. Coverage follows the supported commands and configured kinematics documented below.

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
    |
    `--> Parser / controller frontend
           |- native Cython parser
           `- per-block Python fallback where required
                |
                v
             Program / AST
                |
                v
          Program tool setup
          (AST operation hints, library lookup, manual overrides)
                |- source comments / dimensions: Cython scanner
                `- Python scanner fallback
                |
                v
          CNC execution kernel
          (flow, cycles, compensation, geometry)
                |
                v
           ExecutionResult
                |
                +--> GUI rendering / playback
                +--> statistics
                +--> batch / CLI trace
                +--> EXPANDED postprocessor
                `--> DXF geometry

G-code source + execution map
                |
                `--> FULL source normalizer
```

The frontend constructs Program/AST once per shared execution. Tool setup consumes that same object before motion execution; the Cython/Python source scanner supplies literal tool candidates, comments and dimensions. Library lookup and manual overrides resolve the tool geometry, and the kernel owns execution semantics. FULL uses the exact source together with the authoritative execution map; EXPANDED and DXF consume resolved execution geometry/state. None of these paths implements a second CNC interpreter. Python fallback is supported in source checkouts, including individual complex blocks. Packaged releases require all three native extensions; missing extensions are explicit runtime errors.

Unsupported or ambiguous controller behavior is reported explicitly instead of being converted into guessed geometry.

## Highlights

### FANUC-style turning

- Macro B expressions, conditions and loops, with bitwise AND/OR/XOR and LN/EXP.
- `G65` custom-macro calls and `M98/M99` subprograms.
- Turning cycles `G70`–`G76`.
- `G32`, `G33` and `G92` threading.
- Tool-nose compensation.
- Direct A/C/corner-R programming.
- Cutter-aware Stock Removal, including thread profiles.
- Stock Removal follows executed motions and physical cutter geometry independently of the OD/ID/Face UI filters.
- Thread-insert previews use a fixed contour with three 60-degree teeth, scaled only by diameter; P8 external tools point down and P6 internal tools point up. The thread-removal profile is calculated separately.

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

- Native milling for `.mpf` / `.spf`, including the configured rotary subset described below.
- Native `G0/G1/G2/G3`, `CR=`, work offsets, compensation and common tool/spindle/coolant commands.
- `G290/G291` native / ISO Dialect M switching.
- Modal `MCALL CYCLE81/82/83/84`.
- Native R parameters for the supported numeric subset.
- GUI/CLI/kernel TRAORI/TRAFOOF TCP on the angled AC/BC table profiles, including G2/G3 with rotary interpolation.
- Native CYCLE800 static frames and TRAORI/TRAFOOF TCP on angled AC/BC tables. Numeric A/B/C, direct R references and incremental IC values are supported for configured axes; DC selects the shortest absolute rotary approach; ambiguous half turns remain rejected.
- `TURN=` multi-revolution arc handling.
- EXPANDED serialization of resolved three-axis geometry plus configured indexed A/B/C, verified `4ax_table_c` simultaneous motion and AC/BC TCP through the bundled multiaxis FANUC/SINUMERIK profiles. Tilted-plane/CYCLE800 reconstruction remains fail-closed.

See [SINUMERIK 840D](#sinumerik-840d) for the exact supported subset and current limitations.

### GUI and visualization

- G-code editor with syntax highlighting, line numbers, search, replace and cleanup tools.
- Interactive OpenGL toolpath.
- Logical-motion playback with source-line synchronization.
- The Status Bar shows compact diagnostic counts with source-line details on hover. Long notifications are shortened to fit the available space; their full text remains in the tooltip.
- Play animates supported arcs and helices through intermediate cursor/tool positions while the slider keeps one step per logical motion, including repeated full circles in Macro B loops. The button shows Pause while running; clicking it again pauses playback.
- Toolpath statistics: HTML summary, per-tool selector, metric/imperial display and Export HTML. Exported reports include a static SVG projection (XY milling, XZ turning) below the table. SVG uses Print page fitting and line styles, retaining every motion. CLI: `python -m app analyze program.nc --html statistics.html`.
- HTML exports always use a light theme; the Statistics dialog follows the application theme. GUI report/program exports display their completion status. Playback highlights the current logical motion, including a whole arc, using the configured current-move color.
- CNC editing assistants for hole patterns, pockets and reusable snippets.
- ASCII and binary STL overlays with solid and feature-edge modes.
- STL positioning, transforms, arrays, sections and statistics.
- SQLite-backed turning and milling tool libraries.
- Automatic saved-tool lookup by program T number, preserving manual program overrides. Operation-based fallbacks include native SINUMERIK CYCLE81–83 drills and CYCLE84 taps, classified from the controller AST.
- English and Russian UI.
- Light and Dark themes.
- UTF-8 and Windows-1251 input.

### Export and automation

- Full Program export.
- Expanded Execution export.
- DXF export.
- CLI `parse`, `trace`, `analyze`, `batch`, `export` and `batch-export`.
- JSON and CSV batch reports.
- Native Cython acceleration with compatible Python fallback.

Detailed controller behavior, limits, configuration and troubleshooting are documented in [FAQ.md](FAQ.md), also available through **Help → FAQ**.

The [GUI sandbox](docs/GUI_SANDBOX.md) runs one isolated four-program regression scenario or a paced visual demo, covering Options, Export, Stock Removal and STL Objects with an explicit final result.

---

## Controller support overview

| Area | FANUC-style | SINUMERIK 840D native |
| --- | --- | --- |
| Turning | Yes | No |
| Three-axis milling | Yes | Yes |
| Macro / variable subset | Macro B | R parameters |
| Drilling / tapping cycles | Yes | `MCALL CYCLE81/82/83/84` |
| Indexed rotary milling | Yes | Configured rotary axes; CYCLE800 indexing on angled AC/BC profiles |
| Continuous TCP | `G43.4`, including rotary arcs | GUI/CLI/kernel `TRAORI` / `TRAFOOF`, angled AC/BC subset |
| Tilted working plane | `G68.2/G53.1` | Supported `CYCLE800` static frames and 3+2 indexing (GUI/CLI/kernel) |
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

MPF/SPF documents retain the selected rotary-kinematics profile. Settings and Options expose the enabled profiles; native CYCLE800/TRAORI require a supported angled AC/BC table. The kernel rejects incompatible axes, profiles and ISO-M rotary commands.

**Options > General > 840D Extended cycles** selects the native cycle interface for reading and EXPANDED export: checked uses Siemens 03/2009 (9/9/20/24 arguments for CYCLE81/82/83/84), unchecked uses the classic 01/2008 interface (5/6/17/18 arguments). The setting defaults to checked and is saved. These are explicit cycle-interface profiles, not a claim that every powerline/sl installation uses that interface; verify the installed cycle package. Native JSON posts contain both templates under `cycleProfiles.classic_0108` and `cycleProfiles.sl_0309`. CLI uses `--sinumerik-cycles classic|sl`.

### Native subset

Native support currently includes:

- `G0/G1/G2/G3`
- `CR=`
- plane selection
- absolute / incremental positioning
- metric `G710`
- work offsets
- `G40/G41/G42`
- `D0..D12`
- tool, spindle and coolant commands
- `G0 SUPA`, including configured A/B/C rotary axes (absolute even under G91); zero XYZ addresses use the application's configured G28/SUPA return position, shared with FANUC G53
- `MSG`
- `WORKPIECE`
- `G64`
- semicolon comments

`MSG`, `WORKPIECE`, `G64` and comments do not generate phantom geometry.

CYCLE800 uses Siemens bit-coded axis order, not FANUC Euler ZXZ. Modes 57/54/39/27/30/45, ST200000 (new)/200001 (additive), DIR-1/0/1, quoted TISCH/empty data-set names and numeric/direct R arguments are supported on angled AC/BC tables. DIR selects the principal first-table-joint branch; 0 calculates the frame without indexing. Reset uses `CYCLE800()`, bare `CYCLE800`, or a zero frame with TC="0" (ST200000 or compatibility ST110000). FR0/1/2 are accepted as logical retract requests: OEM machine retract paths are not simulated. FR_I must be empty/zero; DMODE0/1 is supported. Other options and arbitrary OEM data sets reject.

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

Native XYZ geometry and modal cycles are supported; the GUI/CLI/kernel also accepts the bounded TCP subset below.

GUI/CLI/kernel TRAORI/TRAFOOF supports TCP on the angled AC/BC table profiles, including Cartesian G2/G3 arcs with rotary interpolation. Numeric A/B/C assignments and direct R references are supported only for configured axes. CYCLE800 supports the bounded static-frame subset described above. IC(numeric/direct R) is incremental independently of G90/G91. Native extensions such as TRANS/AROT, CUT3DC and FL[] are accepted with unmodeled warnings; their effects are not simulated. GUI profile selection reaches the same kernel and plotting path. Supplied CAM examples reach M30 in regression tests, but unmodeled warnings must be reviewed when interpreting the plotted geometry. Tilted-plane/CYCLE800 reconstruction remains unsupported in EXPANDED export.

`D0` cancels edge selection; `D1` through `D12` select an edge while retaining
nominal tool geometry. Edges above D1 report `UNVERIFIED_SINUMERIK_EDGE_OFFSETS`
because controller offset tables are unavailable. CYCLE800 ST220000/220001
compute a new/additive frame without indexing. The `DMG` frame-only data-set
name is accepted on `5ax_table_bc_angled` with FR0; OEM indexing remains unsupported.

### Native acceleration

Contiguous literal position blocks can use the Cython execution path. The Python capability gate runs before state changes.

Native declarations, `G290/G291` switches and controller operations break an accelerated run; later eligible blocks can resume acceleration. Blocks under active native cycles stay on the Python reference path until the cycle is cancelled.

---

## Export model

The GUI and CLI expose three export families: **FULL**, **EXPANDED** and **DXF**.

**FULL** is a source-preserving NC normalizer. It keeps ordinary source blocks, comments, controller dialect,
modal commands and supported cycles. Constructs whose meaning depends on labels or execution flow are unfolded
from the authoritative execution map before sequence numbers can be changed: FANUC Macro B / evaluated variables,
IF/GOTO/WHILE flow, G65 and M98/M99 calls, and FANUC turning G70–G76. FULL is not a controller-conversion mode.

**EXPANDED** is one universal serializer of the resolved execution. Target CNC selects the target
syntax and post profile; the bundled profiles are `fanuc_mill`, `fanuc_mill_multiaxis`, `fanuc_lathe_a`,
`fanuc_lathe_b`, `sinumerik_iso`, `sinumerik_840d` and `sinumerik_840d_multiaxis`, and a JSON path can be supplied
with `--post-profile`.
`Auto (source controller)` selects the profile matching the source controller and dialect. Profiles
define syntax, mandatory frames, capabilities and defaults, but they do not disable user output
options: coordinates, sequence numbers, delimiter, leading zero, modal feed,
decimal precision, force decimal, plus sign, arc output and start/end program text remain available
and are honored for FANUC→FANUC, FANUC→SINUMERIK ISO, FANUC→SINUMERIK native and SINUMERIK→FANUC. A
profile default is used only when the user did not choose a value.

Expanded arcs can be emitted as relative IJK, absolute IJK, radius or linearized motion. The profile defines the
controller spelling: native SINUMERIK uses `I=AC(...)` / `J=AC(...)` / `K=AC(...)` for absolute centers and `CR=`
for radius output, while FANUC/ISO profiles use their configured IJK/R forms. Source comments are preserved through
the post's comment template. Native SINUMERIK emits its `G290`/`G291` language mode as the physically first program
line, and user start text is emitted after it.

EXPANDED output is modal by default: `Modal Feed` controls whether `F` is restated (`Yes` only when the feed value
or feed mode changes, `No` on every cutting motion). Safety Line emits the profile-declared `program.safety` block
after the user start text. Word order and mandatory output are controlled by the post profile's `format.words`: each
token (`motion`, `X`, `Y`, `Z`, `A`, `B`, `C`, `I`, `J`, `K`, `R`) has an `order` and a `required` flag. `required`
forces an address to be emitted even when unchanged or zero (for example `Y0`); `motion.required=false` makes the
motion code modal. Per-word `decimals`/`sign` live in the same object, and an axis entry is only valid when the axis
is declared in `supports.axes`. `F` is intentionally not part of `format.words` because feed is managed by Modal
Feed. Other profile sections (`format.turnsWord`/`radiusSplitAngle`/`arcSplitAngle`/`fullCircle`, and `supports`
declaring `axes`/`inverseTime`/`multiTurnArcs`/`absoluteArcCenters`) keep working and make unsupported requests fail
closed as `UNSUPPORTED` instead of writing partial NC. Multi-axis geometry (rotary A/B/C, `G68.2`/`G53.1`, `G43.4`,
`CYCLE800`, `TRAORI`/TCP) remains unsupported by the three-axis postprocessor and is reported as a limitation, not an
error.

Cycles, variables and subprogram flow are already executed before EXPANDED serialization. Physical XYZ is emitted
in one zero-offset G54 frame. The three-axis posts reject rotary/TWP/TCP geometry; the bundled multiaxis posts also
reconstruct configured indexed A/B/C, the verified `4ax_table_c` continuous subset and supported AC/BC TCP. Tilted
working planes/CYCLE800 remain fail-closed. Merely having a kinematics profile selected does not make an otherwise
XYZ-only program rotary. Reference returns are emitted through the target profile (`G28`/`G53` or native `SUPA`) and
unresolved position gaps fail closed.

Indexed rotary EXPANDED export about a non-zero WCS origin remains fail-closed as
`UNSUPPORTED_INDEXED_WCS_EXPANDED_EXPORT`: the current post contract does not reconstruct target frame offsets.
Split/linearized TCP arcs distribute rotary angles over their XYZ segments; incremental angle output avoids
cumulative rounding drift. Reference traces retain the table frame separately from tool/head orientation.

**DXF** writes the available resolved motion geometry without NC formatting or controller postprocessing. Rapid and
cutting moves use separate layers. Planar arcs/circles are written analytically where representable; helices and
multi-revolution geometry are sampled as polylines when required. Turning uses the plot-aligned Z/X view.

Examples using the packaged CLI:

```powershell
.\easy_gcode_plot_cli.exe export source.nc --lang fanuc_mill --mode full --sequence-numbers -o normalized.nc
.\easy_gcode_plot_cli.exe export source.nc --lang fanuc_mill --mode expanded --post-profile app\gcode\export\posts\sinumerik_840d.json -o posted.mpf
.\easy_gcode_plot_cli.exe export source.nc --lang fanuc_mill --post-profile sinumerik_840d -o actual.mpf --compare-with expected.mpf
.\easy_gcode_plot_cli.exe export source.nc --lang fanuc_mill --format dxf -o toolpath.dxf
```

For NC export, `--compare-with FILE` compares the generated output with a UTF-8 reference file.
LF and CRLF line endings are treated equally; spaces, comments and the final newline are compared.
Exit codes are `0` for a match, `1` for a mismatch (unified diff on stdout, reference first), and `2`
for export or file errors. The generated NC is retained on mismatch; the reference is never overwritten.

The GUI exposes the same FULL / EXPANDED / DXF split in the Export Data dialog. Target-controller selection belongs
to EXPANDED (including `Auto (source controller)`); FULL keeps the source controller/dialect. The GUI, single-file
`export` and `batch-export` all use the same export contract and conversion code, so CLI and batch output matches the
GUI for the same settings.

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

.\easy_gcode_plot_cli.exe export part.mpf --lang fanuc_mill --mode expanded --post-profile app\gcode\export\posts\fanuc_mill.json -o part.nc

.\easy_gcode_plot_cli.exe export fanuc_part.nc --lang fanuc_mill --mode expanded --post-profile app\gcode\export\posts\sinumerik_840d.json -o part.mpf
```

### Batch analysis

`batch` scans recursively by default.

Without `--lang`, each `.mpf/.spf` file selects milling SINUMERIK; other files keep the turning default. An explicit `--lang` applies to all files.

Use the shared single-file statistics/HTML API for every program:

```powershell
.\easy_gcode_plot_cli.exe batch .\programs --html .\reports\html -o .\reports
```

This writes one HTML report with a tool selector and XY/XZ SVG per input, alongside the JSON/CSV summary. Relative directories and complete input names are preserved (`sub/part.mpf` → `html/sub/part.mpf.html`). Add `--inches` for imperial display. Each source is executed once; failed/partial execution still produces its statistics report. An unreadable input has diagnostics in JSON/CSV. HTML write errors are reported per file without stopping the batch.

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

The same single-file export contract backs `export`, `batch-export` and the GUI, so the same settings produce the same
output. The four preset conversion scripts below are covered by a semantic regression gate
(`tests/export/test_batch_export_semantics.py`) that re-executes successfully exported programs and compares their
trajectory signature with the source.

Files with invalid or incomplete execution are skipped while the remaining inputs continue.

For mixed indexed batches, `--kinematics-map` can assign a profile per relative input path.

### Preset conversion scripts

The development tree contains four EXPANDED batch-export checks. They use the built CLI and explicit JSON post
profiles, writing below `tmp/test_export`.

Windows:

```powershell
.\scripts\ps1\batch\fanuc_mill_to_sinumerik_native.ps1
.\scripts\ps1\batch\fanuc_mill_to_sinumerik_iso.ps1
.\scripts\ps1\batch\fanuc_lathe_a_to_b.ps1
.\scripts\ps1\batch\sinumerik_native_to_fanuc_mill.ps1
```

Linux:

```bash
bash scripts/sh/batch/fanuc_mill_to_sinumerik_native.sh
bash scripts/sh/batch/fanuc_mill_to_sinumerik_iso.sh
bash scripts/sh/batch/fanuc_lathe_a_to_b.sh
bash scripts/sh/batch/sinumerik_native_to_fanuc_mill.sh
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

### Colors

**Options → Colors** separates **Editor** and **Plot** colors. Editor has independent current-line highlight colors for the light and dark themes, defaulting to `#e8e8ff` and `#2a2d2e`. Choose a color with the swatch button or enter `#RRGGBB`, then press **OK** to save it. Changing themes selects the corresponding saved color. **Options → Editor → Highlight current line** controls whether the highlight is visible.

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

Repository working-tree text uses CRLF; Bash scripts use LF. Git attributes and VS Code workspace settings enforce these defaults. Run `.\scripts\ps1\lint.ps1 -Fix -CheckResources` to normalize existing text and regenerated Qt modules; without `-Fix`, the PowerShell linter reports incorrect or mixed endings. Normalization preserves encoding and skips binary assets and ignored build/temporary outputs. Git stores normalized text with LF.

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

See [FAQ.md](FAQ.md#development-and-architecture) for package structure, Qt generation, detailed settings and release notes.

---

## Community and project direction

- [Contributing](CONTRIBUTING.md): development principles, checks and pull requests.
- [Roadmap](ROADMAP.md): implemented release scope and remaining work.
- [Changelog](CHANGELOG.md): changes by version.
- [Code of Conduct](CODE_OF_CONDUCT.md): participation rules and reporting concerns.
- [Security Policy](SECURITY.md): vulnerability reporting and CNC semantics issues.
- [Report a bug or request an improvement](https://github.com/MaestroFusion360/easy_gcode_plot/issues/new/choose).

---

## License

MIT License — see [LICENSE.md](LICENSE.md).

---

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=MaestroFusion360-easy-gcode-plot&label=Project+Views&color=blue" alt="Project Views">
</p>
