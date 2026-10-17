# HEIDENHAIN / iTNC 530 golden trajectories

Uses the existing milling CSV header, `coordinates()` and O0339-style
`assert_same_geometry()` from `test_fanuc.py`: exact movement/plane/direction
flags and row order, with `pytest.approx(abs=1e-8)` for numeric fields. Tests only
read accepted CSVs. Source NC files and accepted CSVs remain unchanged.

## Reviewed references

| Source `.h` | Movements | Scenario | X bounds | Y bounds | Z bounds |
|---|---:|---|---|---|---|
| bore_itnc530 | 18 | Nominal, compensation explicitly disabled | -10 … 10 | -10 … 10 | -11 … 15 |
| itnc530_base_pgm | 12 | Nominal; source does not specify cutter diameter | -72 … 40 | -72 … 30 | -10 … 200 |
| 6bas154 | 20 | RL, configured T4 flat mill D6 | -30 … 93 | 0 … 93 | -5 … 100 |
| manual_chf | 18 | RL, configured T1 flat mill D6 | -10 … 98 | -10 … 98 | -5 … 250 |
| cycles_itnc530 | 268 | **Full CSV withheld: full geometry review still required** | — | — | — |

The four accepted CSVs contain **68 primitives**. Every row was checked against
an independent analytic transcription in `generate_heidenhain.py`, with absolute
error below `1e-8`. The review also checks bounds including arc extrema, circle
equations, full circles, complete multi-turn sweeps, directions and diagnostics.
It uses no kernel geometry, cycle, expression or sampling helpers.

Public execution settings are explicit in `test_itnc_golden.py`: native
`source_dialect="heidenhain"`, mill language, Home XYZ=(0,0,0), arc tolerance
0.01 mm, no ISO arc autodetection. The selected D6 cutters for the manual examples
are test inputs, as in the existing corner tests; these files contain no TOOL DEF.
No GUI/tool-discovery state is required.

- `bore_itnc530` preserves the full CP angles **5400, 2699.969, 360, 2834.989,
  2834.989, 360 degrees**. Endpoints are derived from accumulated angles using
  sine/cosine; sweeps are degrees × π/180. The two nominal radii are 7 and 10.
  CP360 remains a full circle; CP5400 remains fifteen revolutions, with its full
  Z descent. Smoothing cycle 32 produces the explicitly expected
  `HEIDENHAIN_SMOOTHING_NOT_SIMULATED` warning at physical source line 19.
- `itnc530_base_pgm` transcribes all 12 linear/rapid endpoints, including M91 Z0.
  It completes at END PGM without an M2/M30, so `program_end=None` is intentional.
  `milling_correction_enabled=False` defines a nominal reference; compensated
  behavior with an unspecified cutter is not claimed verified.
- `6bas154` checks all six RND corners using `trim=R*tan(theta/2)`. Clockwise
  corners with RL/R3 keep their centers and have radius R+3. The R3 APPR/DEP
  curves collapse under the selected R3 cutter; their remaining linear parts
  and the final M30 retract are retained.
- `manual_chf` checks CHF10/CHF20 along adjacent elements, diagonal offset
  components 3/√2, all five inserted R3 transition arcs, APPR/DEP and final M2.
  No warnings are expected for this or `6bas154`.

## Regressions fixed in stage 3

The two semantic tests initially used strict xfail. Both now pass as ordinary
regression tests after the focused kernel fixes. Accepted CSVs were not updated;
fixing these assertions does not automatically accept new full-trajectory goldens.

### `bore_itnc530` with compensation

With T1 D6 and compensation enabled, center-path radii become 4 and 7. Previously
four CP sweeps lost their full revolutions: IPA5400 returned 2π instead of 30π,
changing the helix pitch. The compensation projection now retains the executed
motion's additional turns. All six source angles and Z descents are preserved.
The nominal CSV still explicitly disables compensation; there is **no accepted
compensated bore CSV**. Separate analytical tests cover RL/RR, both directions,
all three planes, complete/partial revolutions and planar/helical travel.

The independent angle interpretation follows HEIDENHAIN's
[iTNC 530 manual, “Programming a helix”](https://content.heidenhain.de/doku/tnc_guide/pdf_files/iTNC530/340490-xx/en/bhb.pdf):
IPA is the total angular traverse, with values through 5400° (15 revolutions).
The regression test compares the six public arc sweeps with these source angles,
without consulting runtime turn counters.

### `cycles_itnc530`: cycle 200 inherits cycle 203 parameters

The complete, unchanged file is executed with the existing public
`home_z=100, emulate_g28_home=True` settings. It reaches M30 and emits 268
movements. Expected warnings are `HEIDENHAIN_M140_HOME_EMULATION` at line 8 and
`HEIDENHAIN_SMOOTHING_NOT_SIMULATED` at line 21. The first warning documents a
Home-based emulation of M140 MB MAX, not verification of the machine travel limit.

The final CYCL DEF 200 specifies Q202=1, surface Q203=-1 and depth Q201=-16.262.
Its first hole should therefore have 17 feed endpoints: -2,-3,…,-17,-17.262.
Previously it had **30**, beginning -2,-2.9,-3.7,-4.4,-5,-5.5,…: the common
peck routine incorrectly consumed Q212/Q205 from the preceding cycle 203.
Cycle 200 now ignores foreign decrement, minimum and Q258 re-entry parameters;
the global Q variables remain available to later program expressions.
`test_cycles_last_200_keeps_its_programmed_one_mm_pecks` verifies all 17 depths.
No full trajectory CSV was accepted for this fixture.

HEIDENHAIN's [iTNC 530 cycle manual, section 3.3, Cycle 200](https://content.heidenhain.de/doku/tnc_guide/pdf_files/iTNC530/34049x-07/zyklen/670_388-22.pdf)
defines Q202 as infeed per cut. Q212 decrement belongs to the universal drilling
cycle 203; it is not part of the cycle 200 definition. This test checks the
source's cutting-depth sequence; it does not invent a reference for the remaining
unverified full-cycle geometry.

## Commands and acceptance process

```powershell
.venv\Scripts\python.exe -m pytest tests/golden/milling -q
.venv\Scripts\python.exe tests/golden/milling/generate_heidenhain.py --out tmp/itnc-golden-candidates
```

The generator only produces the four independently reviewed scenarios. It refuses
the accepted golden directory and reports that full-cycle review is pending. Review
candidate diffs, parameters, diagnostics and analytic checks before explicitly
copying CSVs here. It never executes during pytest collection or comparison.

To run the four CSV comparisons and two semantic regressions:

```powershell
.venv\Scripts\python.exe -m pytest tests/golden/milling/test_itnc_golden.py -q
```

Current result: **6 passed** for the iTNC module; **23 passed** together with the
existing 17 FANUC CSV tests. The initial result was 4 passed / 2 xfailed for iTNC.
The full cycles CSV and compensated bore CSV remain unaccepted until their
complete geometry is independently reviewed.

The initial combined regression run including native HEIDENHAIN execution/frontend/corners/
rotary, O0339/G72, turning goldens and legacy export references: **418 passed,
2 xfailed**. Ruff, formatting and repository line endings pass. Existing FANUC
candidate generation remains byte-identical to its 17 accepted CSVs; normal
pytest leaves all 21 accepted CSV files unchanged.
