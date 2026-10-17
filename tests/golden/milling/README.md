# FANUC milling golden trajectories

Native HEIDENHAIN/iTNC additions reuse this CSV mechanism; see
[heidenhain/README.md](heidenhain/README.md) for four accepted scenarios and two
explicit known-failure regressions across the five requested `.h` fixtures.

These 17 CSVs cover the complete ordered `execute()` output of the existing NC
files in `tests/fixtures/milling/fanuc/`. No NC files are copied or rewritten.
The comparison follows `tests/dialects/test_g72_golden.py` (O0339): ASCII CSV,
exact header/count, then each movement in order using
`pytest.approx(reference, abs=1e-8)`. Pytest's existing default relative tolerance
(`1e-6`) is retained. Movement codes, arc planes and direction/full-circle flags
are compared exactly. There is no update option in the pytest test.

## CSV contract and execution inputs

One row is one resolved primitive, without discretization:

```text
move,start_x,start_y,start_z,end_x,end_y,end_z,arc_plane,center_x,center_y,center_z,radius,sweep,clockwise,full_circle
```

XYZ, centers and radii are millimetres; sweeps are positive radians. The eight
arc columns are empty for a straight movement. G0/G1/G2/G3 retain their public
numeric movement codes. `clockwise` follows public `ArcGeometry` conventions,
including the G18 direction convention. Numbers use 12 significant digits.
AST, source indices, cycle internals, runtime state and feeds are not serialized.

`test_fanuc.py` fixes the public API inputs: `language="fanuc_mill"`,
`source_dialect="fanuc"`, incremental IJK (`source_arc_type=1`), no autodetection,
`arc_tolerance=0.01`, and Home XYZ=(0,0,0). No rotary kinematics, GUI settings or
tool discovery are involved. Other options retain public API defaults.

Additional inputs, explicitly recorded in `OPTIONS`:

- `wcs_test`: G54=(0,0,0), G55=(200,0,10), G56=(0,200,20),
  G57=(200,200,30). This produces **74**, rather than the 71 movements of the
  all-zero-WCS scenario: three previously zero-displacement positioning blocks
  now move between distinct origins. WCS selection itself preserves physical Z.
- `correction_fanuc`: T2 flat mill D8, from the fixture's tool comment.
- `macro_boss_milling`, `macro_hole_milling`: T2 flat mill D50, from their comments.
  Compensation is enabled; the center-path radii are 75 and 25 respectively.
- `polar_drilling` omits G98/G99 and G20/G21. Its reference uses the application's
  default millimetres and return-to-R mode. It does not assert the power-on or
  reset defaults of any physical FANUC controller.

## Initial independent review

`generate.py` contains fixture-specific analytic transcriptions, not an NC
interpreter. It does not import kernel arc, compensation, macro or cycle helpers.
Before writing any candidate, it compares **all 692 movements** against those
transcriptions, with absolute error below `1e-8`, checks circle equations at both
endpoints, directions, sweeps and full circles, and computes bounds analytically
using arc extrema. Every execution must be successful, complete, reach M30 and
have **no diagnostics**. No failed or unsupported program is silently accepted.

The initial review found no differences between these analytic references and
the selected execution scenarios. Counts and full-primitive bounds, including the
initial origin and rapids, are:

| Fixture (`.nc`) | Movements | X bounds, mm | Y bounds, mm | Z bounds, mm |
|---|---:|---|---|---|
| wcs_test | 74 | -55.123 … 255.123 | -55.123 … 265.123 | -5.123 … 130 |
| macro_b | 14 | 0 … 42 | -5.773333333 … 69.399858 | -9.906666667 … 30.824704 |
| correction_fanuc | 27 | -94.999846156 … 94.999846156 | -74.4 … 61.999846156 | -24 … 15 |
| subprogram | 172 | -72.39 … 57.15 | -31.75 … 31.75 | -6.35 … 25.4 |
| terraced_ramp | 13 | -20 … 20 | -15 … 15 | -4 … 10 |
| ramped_surface | 12 | -30 … 30 | -20 … 20 | -5 … 15 |
| macro_boss_milling | 208 | -75 … 75 | -75 … 100 | -50 … 100 |
| macro_hole_milling | 57 | -25 … 25 | -25 … 25 | -50 … 100 |
| multiplane_edges | 9 | 0 … 30 | 0 … 30 | -12 … 10 |
| incremental_xyz_raster | 10 | -24 … 24 | -12 … 12 | -5.5 … 10 |
| inch_spiral | 6 | -6.35 … 6.35 | -6.35 … 6.35 | -6.35 … 12.7 |
| mixed_ijk_r_planes | 7 | -20 … 10 | 0 … 20 | -11 … 8 |
| helical_bore | 7 | -8 … 8 | -8 … 8 | -5 … 10 |
| radius_arc_ramp | 7 | -10 … 10 | -10 … 10 | -4 … 8 |
| macro_face_milling | 27 | -100 … 100 | -100 … 100 | 0 … 100 |
| tapping_fanuc | 22 | -20 … 20 | -20 … 20 | 0 … 26 |
| polar_drilling | 20 | -86.602540378 … 86.602540378 | -100 … 50 | -20 … 0 |

Review details:

- `macro_b`: all 14 endpoints were evaluated with ordinary arithmetic and
  degree-based trigonometry, including two-argument ATAN, rounding, nested
  indirection (#149=42), two loop iterations and the GOTO result #151=7.
- `subprogram`: ten O10 calls contribute 150 ordered primitives; three O11 calls
  contribute 15. O10 returns in **G91/G0**. The caller's `G00 Z.1` is therefore
  incremental and its `G01 Z0`/`G00 X0 Y0` emit nothing. O11 reaches -5.715 mm;
  the earlier O10 calls reach -6.35 mm. Both R signs in O11 describe semicircles
  because chord length equals diameter. This modal behavior was checked before
  accepting the 172-row reference.
- Boss/hole loops: 200 descents of 0.25 mm plus one cleanup circle, and 50 descents
  of 1 mm plus one cleanup circle. Every helix retains its complete circle and
  changing Z; no arc is replaced with sampled line segments.
- Face milling: six depths 10.3, 8.3, 6.3, 4.3, 2.3, 0.3; each pass contains the
  plunge, straight approach, R100 clockwise full circle, and straight return.
- The simple ramps and raster are complete hand-transcribed endpoint sequences.
  Multiplane programs have explicit quarter-circle centers in G17/G18/G19.
  Inch coordinates and helix pitch are multiplied by exactly 25.4.
- G84 visits four corners, feeds from R15 to Z1 and **feeds** back to R15; G99
  persists across G80. Polar drilling visits R100 at 30°,150°,270° twice, once
  from absolute angles and once from two incremental 120° additions. Initial
  positioning, R-plane approach, depth, retract and final G28 are all included.

### `correction_fanuc` precision limitation

The nominal R10 and R16 CAM transitions are rounded to three decimals in the NC
source. The reference explicitly retains the existing tolerant-circle convention:
mean endpoint radius, then R±4 offset; radial endpoints; and intersections with
adjacent straight lines. `generate.py` independently constructs these points with
closed-form circle equations. For example:

```text
inner = (10 + hypot(3.846, 9.231))/2 - 4
outer = hypot(6.154, 14.769) + 4
tangent displacement = sqrt(inner² - 6²)
```

Four joins have a gap of approximately **0.000168575 mm**, below the configured
0.01 mm geometry tolerance. This is recorded, not smoothed out in the CSV. Exact
continuity and the physical controller's treatment of these rounded transitions
have **not** been independently established. The reference confirms the stated
geometric tolerance model, not a vendor-certified compensated trajectory. No
other fixture required a partial, skipped or expected-failure reference.

## Running and deliberately updating

Ordinary comparison (read-only):

```powershell
.venv\Scripts\python.exe -m pytest tests/golden/milling -q
```

Generate candidates separately, after reviewing the source and the analytic
transcription when either changes:

```powershell
.venv\Scripts\python.exe tests/golden/milling/generate.py --out tmp/milling-golden-candidates
```

The generator refuses the accepted golden directory as its output. Inspect the
candidate CSV diff, movement counts, bounds, diagnostics and analytic review
before explicitly copying the reviewed CSVs into this directory. Do not refresh
references merely because a refactor makes pytest fail. No generator runs during
pytest collection or comparison, and CSVs are never rewritten by tests.

Initial validation: **17 passed** for this directory; **128 passed** together
with the unchanged O0339/G72, turning golden, existing milling golden, Macro B
and `test_legacy_192_reference.py` regressions. The CSVs are compatible with the
existing pytest/csv mechanism; no new dependencies or shared golden framework
were added.
