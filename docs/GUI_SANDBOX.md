# GUI sandbox

One pytest scenario drives the existing MainWindow through four programs. It
uses isolated QSettings and tool-library storage from `tests/conftest.py`;
exports go to pytest's temporary directory. Existing CNC and STL fixtures are
read in place. No network or user configuration is required.

Automated run, from the repository root:

```powershell
scripts\ps1\start-sandbox.ps1 -Automated
```

Visual run on Windows, with the same assertions:

```powershell
scripts\ps1\start-sandbox.ps1
```

On Linux/macOS:

```bash
bash scripts/sh/start-sandbox.sh
# Offscreen regression run:
bash scripts/sh/start-sandbox.sh --automated
```

The Bash launcher selects `xcb` on Linux or `cocoa` on macOS when no visible
Qt platform is configured; an existing visible platform such as `wayland` is
retained. Both launchers enable demo mode by default and preserve pytest's exit
status. PowerShell restores the original environment; Bash applies overrides
only to the child process.

Use `-DelayMs 1500` (PowerShell) or `--delay-ms 1500` (Bash) to adjust pacing.
The default is 1000 ms: major stages/dialogs pause for twice that interval;
the final summary remains visible for at least 3 seconds (4 seconds by default).
Pauses are for presentation; execution/import waits use Qt events and bounded
state conditions. Automated mode forces offscreen and disables presentation
pauses. Demo mode rejects offscreen/minimal platforms.

| Stage | Existing inputs | Assertions |
| --- | --- | --- |
| FANUC milling | `tests/fixtures/milling/fanuc/flange_plate_benchmark.nc` | Successful complete execution through M30 without diagnostics, motions/render points/scene item, no STL. Explicit T2 end-mill geometry and T4 drilling selection resolve cutter compensation. |
| Options / Export | Same milling program | Real Options dialog switches to dark, grid step 20 and cyan/orange toolpath colors. Line width stays unchanged; a fresh MainWindow restores settings. Export dialog writes expanded FANUC; kernel replay completes without diagnostics and preserves motion count. |
| FANUC turning / Stock Removal | `tests/fixtures/turning/lathe_cycles_example.nc` | Complete execution, generated G71/G76 motions; T0303 uses the saved P2 boring tool from the isolated test library. Real Stock dialog and Play action build a timeline and mesh. Material changes; rewind/replay returns to the same final material intervals. |
| SINUMERIK 3+2 | `tests/fixtures/milling/sinumerik/5ax_test.mpf`, `stl/test6.stl` | AC angled-table profile selected through Options; complete execution, varying resolved tool orientations, STL scene item and rotary playback. |
| SINUMERIK impeller | `tests/fixtures/milling/sinumerik/impeller.mpf`, `stl/test7.stl` | BC angled-table profile; complete execution through M30. Show a brief Play, then slider positions in 10% steps through completion. The fixture selects T60/D1 using a fixed saved-library geometry snapshot in the sandbox. TRANS metadata warnings remain explicit. |

The turning Stock dialog uses an outside diameter of 130 mm, no bore,
length 55 mm, front Z=1 mm and accuracy 0.1 mm. The scenario checks these
applied values before playback.

Before opening each program, the scenario triggers **File → New** and checks
that the editor, toolpath, STL objects and stock mesh are cleared.
Select 3D/ISO view immediately after New.
Only then does it select turning/milling mode, the rotary profile and WCS Home
before opening the next fixture. G54–G59 offsets are zero. Configured G28 Home
is X=150, Y=0, Z=10 for turning (X is the displayed diameter), X=0, Y=0, Z=100
for the first milling program and test6, and X=0, Y=0, Z=300 for test7.

After opening the first program, set **Options → Default file type → ISO G-code**.
Check that highlighting remains enabled after later Options dialogs and Open.
Start real Play for milling, turning Stock Removal and test6, verify that the
timer advances a motion, then show intermediate positions and completion.
The flange and turning Stock Removal play every logical motion
to the end without slider jumps. Speed 5 is selected; the sandbox uses a 2 ms
precise timer for faster visible playback and a zero interval in offscreen tests.
The wait yields to Qt between updates. Test6 retains the short playback/seek demonstration.
Test7 plays briefly (two seconds at default demo pacing), pauses, then visits
10%, 20%, through 90% on the slider and resumes the final motion to reach 100%.

The STL stages demonstrate different operations through the existing STL
Objects panel. For test6 select Base Point **Origin**, then Position **Z=-100**
(X/Y=0) and **Move Here**; check the pivot and translated Z bounds. For test7
first use **Transform → Rotate Z +90°**, then select **Section Y**, apply at Y=0,
then **Undo**; check that Undo removes only the section and preserves the rotation and that
the object placement is unchanged. Only after Undo, enable **STL edges only**
through Options; test6 and the test7 section demonstration use solid STL.
The sandbox window opens centered in the screen's available area.
They do not repeat the same transformations
or compare screenshots.

The milling stage also opens Statistics, shows the complete report and a
single-tool selection, then exports HTML with its tool selector and SVG
trajectory to the temporary directory.

The isolated test library contains fixed T0101–T0606 geometry matching the
reference turning setup, including the T0303 P2 boring insert, T0505 P2 ID groove
and T0606 P6 internal threading insert. After the turning fixture opens,
assertions require all six saved specifications in Current Program and verify
that execution did not modify the saved boring record. Threading must enlarge
the bore without changing the outside stock contour. Production
selection already gives matching library numbers priority over discovered
geometry; explicit Current Program overrides retain their established priority.
The demo never loads or writes the user's configured SQLite library.

The impeller uses the selected BC profile for the DMG frame-only CYCLE800 call.
The impeller fixture selects T60 with D1. Its isolated library contains the user's
taper-ball-mill snapshot: diameter 4 mm, taper angle 6 degrees, flute/body length
25 mm each and overall length 50 mm. The sandbox opens the fixture without source
rewrites and verifies library resolution. The user's SQLite is unchanged.

File pickers receive predetermined fixture/output paths. Options, Export,
Stock and STL controls remain actual application widgets. Unexpected warning,
critical or modal message boxes are recorded and rejected so they cannot hang
the run; the stage fails. Demo mode ends with a timed summary message box.
Both modes print a stage summary to stdout; failures include the stage and
re-raise the original exception for pytest.

The sandbox exposed and fixes one GUI issue: manual Update discarded the
kernel result when an error occurred before the first motion. It now retains
that result while clearing stale plot/playback state. Kernel regressions also
cover the supported native impeller header; the flange fixture contains explicit
tool information so its compensation resolves without warnings.
