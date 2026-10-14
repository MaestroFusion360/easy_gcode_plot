# GUI Sandbox

Updated for 2.4.0. Run automated checks without showing test windows; use the
visible demonstration only when you explicitly want to watch the simulation.

The existing pytest scenario `tests/gui/test_daily_workflow_smoke.py` drives
MainWindow through four unchanged representative programs. QSettings, the tool
library, logs, HTML and NC exports use pytest temporary storage. No fixture is
rewritten and the user library is never opened or changed.

```powershell
# Offscreen regression, without GPU rendering claims
.\scripts\ps1\start-sandbox.ps1 -Automated
# Optional visible simulation demonstration
.\scripts\ps1\start-sandbox.ps1
```

```bash
bash scripts/sh/start-sandbox.sh --automated
# Optional visible demonstration
bash scripts/sh/start-sandbox.sh
```

Use `-DelayMs 1500` or `--delay-ms 1500` to change presentation pauses. The
launchers preserve pytest exit status; PowerShell restores its environment and
Bash confines overrides to the child process. Visible mode requires a visible Qt
platform; automated mode selects offscreen and disables presentation pauses.

## Presentation and regression

Both modes run the same configuration, export, statistics, tool-library and STL
assertions. Visible mode keeps setup dialogs off the screen and removes pauses
between individual configuration checks. Time is spent on tool motion, playback,
stock changes and completed scenes. Configuration widgets are still real widgets;
`WA_DontShowOnScreen` suppresses their presentation, not their behavior.

| Stage | Input | Demonstration and assertions |
| --- | --- | --- |
| FANUC milling | `milling/fanuc/flange_plate_benchmark.nc` | Complete M30 execution, installed T2/T4 geometry, render scene and full logical playback. Options persistence, HTML statistics and expanded export/reimport remain regression checks. |
| 3-axis GPU Stock Removal | Same flange | Only with an actual visible OpenGL 4.3+ widget. Real GPU playback and readback must show a lower remaining material height, allocated GPU buffers and complete replay. The machined stock remains visible before the next stage. |
| FANUC turning | `turning/lathe_cycles_example.nc` | Saved T0101-T0606 specifications, G71/G76 execution and full Stock Removal playback. The bore grows during internal threading while the outside stock contour stays intact. Rewind/replay restores identical final material intervals. |
| SINUMERIK 3+2 | `milling/sinumerik/5ax_test.mpf`, `stl/test6.stl` | Angled AC table, changing tool orientations, toolpath/playback and positioned STL. Origin/translation assertions remain. |
| SINUMERIK impeller | `milling/sinumerik/impeller.mpf`, `stl/test7.stl` | Angled BC table, saved T60 taper-ball geometry, playback in 10% sections and final scene. Rotation/section/undo assertions remain; TRANS warnings are reported. |

All NC paths above are relative to `tests/fixtures`. Large multi-axis examples
use brief real playback and slider sections to keep the demonstration bounded.
The flange and turning stock visit every logical motion. Visible full playback
uses an 8 ms precise timer; regression mode uses a zero timer interval. Waits
process Qt events and have explicit deadlines. Visible mode keeps its final
summary on screen for at least three seconds. Automated mode writes the summary
to stdout without showing windows. Unexpected warnings or modal dialogs fail
the stage.

## GPU availability

The GPU stage checks the **actual graphics widget** context and its OpenGL version
before enabling removal. Offscreen/minimal platforms, missing/invalid contexts
and OpenGL versions below 4.3 produce an explicit `SKIPPED (...)` stage in stdout
and the summary. The rest of Sandbox continues. An offscreen PASS confirms model
and workflow assertions only; it does not validate visible GPU rendering.
Once an adequate context is available, a rendering/removal failure fails the test
instead of being converted into a skip. There is no CPU material-removal fallback.

## Isolated setup

File → New creates a fresh active MDI document with an empty editor, toolpath,
STL scene and stock state before every input. Previous documents remain in the
isolated session; New does not clear their buffers or scenes. G54-G59
offsets are zero. Configured Home is X=150, Y=0, Z=10 for turning (diameter display),
X=0, Y=0, Z=100 for flange/test6, and X=0, Y=0, Z=300 for the impeller. Milling GPU
stock uses automatic bounds, 2 mm resolution and accuracy preset 1.

Turning stock is diameter 130 mm, no initial bore, length 55 mm, front Z=1 mm,
resolution 0.1 mm. The isolated saved boring tool T0303 uses tip orientation 2;
T0505 is the ID groove and T0606 the internal thread tool. The impeller library
snapshot is T60/D1: diameter 4 mm, taper 6 degrees, flute/body 25 mm each and total
length 50 mm. Exact library resolution and unchanged fixture source are asserted.

STL checks preserve test6 origin and Z=-100 placement; test7 rotates Z by 90 degrees,
sections at Y=0 and undoes only the section, then displays edges. Both temporary
export files and HTML reports are re-read and checked before the scenario ends.
