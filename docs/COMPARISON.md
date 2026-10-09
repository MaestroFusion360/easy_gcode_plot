# CIMCO Edit 8 vs Easy G-Code Plot 1.9.8

Comparison of FANUC milling, FANUC turning and native SINUMERIK 840D milling. [Русская версия](COMPARISON_RU.md).

**Scope:** CIMCO Edit **8 Backplot**, not CIMCO Edit 2022–2026 or the separate CIMCO Machine Simulation product. Easy G-Code Plot describes the 1.9.8 working tree and its regression fixtures. This is a capability comparison, not a measured accuracy or performance ranking.

**Legend:** ✅ supported within the stated scope; ⚠️ partial or restricted; ❌ explicitly unsupported; **?** not established for CIMCO Edit 8. **Unknown does not mean unsupported.** ≈ means comparable only within the stated scope. A command in a filter is not evidence of correct geometry. Statements marked [U] are the author's supplied observations, not vendor certification.

## What's changed in 1.9.8

- FANUC milling adds G74 left tapping, G76 fine boring, G87 back boring and G89 dwell/feed-return boring. G74/G84 Q now produces synchronized tapping pecks. Q shift direction and tapping retract behavior are configurable machine assumptions.
- Native SINUMERIK adds CYCLE85/86/87/89 and extends CYCLE84 to metric right/left and deep tapping, including VARI=1/2, DAM/VRT and balanced final pecks. CYCLE88 remains unsupported.
- Siemens circles can select a block-local plane from two endpoint axes; helical TURN moves retain the modal plane. Pure rapid rotary indexing can retain an active CYCLE800 frame.
- Both supplied Fusion 1001 programs reach M30 on `5ax_table_ac`. Tests cover home Z=0 and 500. This verifies those fixtures, not arbitrary CAM output. Missing tool geometry leaves compensation unverified. Out-of-range DC angles are normalized with warnings for backplot compatibility; that does not validate them for a real controller.
- G92.1 zero-valued axis selectors are treated as coordinate preset without physical motion. The model has no manual/G92 shift to cancel. FANUC G53 machine coordinates and configured G28 reference returns were already supported.
- An invalid arc produces a diagnostic and execution can continue to later blocks. Completion and validity are separate result fields; reaching M30 alone does not establish a valid result.

## 1. FANUC milling

| Area / command | CIMCO Edit 8 | Easy G-Code Plot 1.9.8 | Assessment |
|---|---|---|---|
| G0/G1, modal XYZ | ✅ Backplot [C1] | ✅ execution and motion trace | ≈ |
| G2/G3, IJK, R | ✅ configurable arcs [C1, C2] | ✅ absolute/incremental IJK and R | ≈; variants not compared |
| Full circles | ✅ zero-arc setting [C2] | ✅ | ≈ |
| Helical G2/G3 | ? exact geometry | ✅ analytic arcs and helices | Not established |
| G4 | ✅ [C1] | ✅ dwell signal | ≈ |
| G17/G18/G19 | ✅ [C1] | ✅ | ≈ |
| G20/G21 | ✅ [C1] | ✅ units and mm/inch export | ≈ for input |
| G90/G91 | ✅ [C1] | ✅ | ≈ |
| G28 | ✅ [C1] | ✅ configured home and intermediate point | ≈ in basic use |
| G53 | ? exact nonmodal contract | ✅ machine-coordinate G0/G1 | Not established |
| G30 | ? | ❌ second reference return not modeled | Not established |
| G54–G59 | ✅ [C1] | ✅ WCS offsets | ≈ |
| G54.1 P1–P99 | ? | ⚠️ selection; zero offset without G10 L20 | Not established |
| G10 L2/L20 | ? runtime WCS programming | ✅ runtime WCS updates | Not established |
| G52 | ? | ✅ local shift | Not established |
| G68/G69 | ✅ filter and fixes [C3] | ✅ plane rotation/cancellation | Presence comparable; accuracy untested |
| G50/G51 scaling | ? | ⚠️ restricted scaling model | Not established |
| G15/G16 polar | ? | ⚠️ polar coordinates with arc restrictions | Not established |
| G40/G41/G42 | ✅ compensation settings [C1, C2] | ✅ supported 2D geometry with known tool radius | No paired accuracy test |
| G43 H / G49 | ⚠️ recognized; author observed no H path shift [C3, U] | ⚠️ state retained; H does not shift plotted path [E] | ≈ observed geometry |
| G68.2/G53.1 | ⚠️ G68.2 filter support; G53.1 contract unconfirmed [C3] | ✅ supported indexed AC/BC and two-axis profiles | Not ranked |
| G43.4 TCP | ? V8 interpretation contract | ✅ restricted AC/BC TCP, G0/G1/G2/G3 | Not established |
| G68.2 with G43.4 | ? | ❌ composition unsupported | Not established |
| Indexed 3+1 A/B/C | ✅ configurable 4/5-axis Backplot [C2] | ✅ selected A/B/C table profiles | ≈ supported profiles |
| Indexed 3+2 | ✅ 4/5-axis setup; frame coverage unconfirmed [C2, C3] | ✅ supported G68.2/G53.1 subset | Not ranked |
| Continuous 4-axis X/C | ✅ 4/5-axis class [C2]; X/C semantics unknown | ✅ tested 4ax_table_c subset | Not established |
| Continuous 5-axis AC/BC | ✅ 5-axis Backplot [C2]; TCP scope unknown | ✅ AC/BC TCP and tool orientation | Not ranked |
| Full machine simulation | ? not established for this Backplot | ❌ | No verified equivalence |
| Finished-part STL overlay | ? V8 overlay scope | ✅ STL overlay, no milling subtraction | Not established |
| Volumetric milling stock removal | ✅ Solid Animation [C2] | ❌ | CIMCO for this feature |
| G73 high-speed peck | ? exact semantics | ✅ restricted peck cycle | Not established |
| G74 left tapping | ? | ✅ feed withdrawal; Q pecks | Not established |
| G76 fine boring | ? | ✅ oriented Q clearance shift; configurable XY direction | Not established |
| G80 | ✅ [C1] | ✅ cycle cancellation | ≈ |
| G81 | ✅ [C1] | ✅ | ≈ |
| G82 | ? exact form | ✅ bottom dwell | Not established |
| G83 | ✅ historical fixes [C4] | ✅ pecks with R-plane returns | ≈ cycle class; details unknown |
| G84 + M29 | ✅ G84 [C1]; M29 unverified | ✅ rigid-tapping preparation, feed withdrawal, Q pecks | ≈ for G84 presence |
| G85 | ✅ historical fixes [C4] | ✅ feed-return boring | ≈ cycle class |
| G86 | ? | ✅ spindle-stop boring signal | Not established |
| G87 | ? | ✅ back boring with Q shift; always initial-plane return | Not established |
| G88 | ? | ❌ | Not established |
| G89 | ? | ✅ dwell and feed withdrawal | Not established |
| G98/G99 cycles | ? exact geometry | ✅ initial/R-plane return; G87 always initial | Not established |
| G92.1 | ? | ⚠️ zero-selector preset, no physical motion or modeled manual shift | Not established |
| G93 inverse-time | ? | ✅ restricted rotary/TCP inverse-time feed | Not established |
| G94/G95 | ✅ basic programming; details unverified | ✅ feed/min and feed/rev | ≈ presence |
| M3/M4/M5, M6, M8/M9 | ✅ example [C1] | ✅ states/signals, no machine physics | ≈ |
| Variables and nested `#[...]` | ✅ nested variables in V8 FANUC/Haas filter [C3] | ✅ Macro B read/write and indirect variables | ≈ presence; depth unknown |
| Macro B IF/GOTO, WHILE/DO | ⚠️ V8 fixes; exact forms unconfirmed [C3] | ✅ executable expressions and flow | Not ranked |
| G65 and local variables | ? runtime behavior | ✅ O macros, local stack, L repeats | Not established |
| M98/M99 | ? exact runtime | ✅ subprograms and L; no M99 P | Not established |
| EXPANDED / FANUC↔SINUMERIK | ? equivalent replay contract not found | ✅ semantic export; experimental AC/BC | Different documented contracts |

## 2. FANUC turning

| Area / command | CIMCO Edit 8 | Easy G-Code Plot 1.9.8 | Assessment |
|---|---|---|---|
| G0/G1 | ✅ turning Backplot [C5] | ✅ X/Z trace | ≈ |
| G2/G3 I/K, R | ✅ turning examples [C5] | ✅ G18, absolute/incremental I/K and R | ≈ basic arcs |
| Diameter/radius programming | ✅ diameter setting [C2] | ✅ physical radius and diameter input mode | ≈ |
| U/W incremental | ✅ relative-axis setup [C2, C5] | ✅ independent of X/Z mode | ≈ |
| FANUC Type A / B | ? filter dialect distinctions | ✅ selectable A/B; no Type C | Not established |
| G20/G21 | ✅ [C5] | ✅ mm/inch | ≈ |
| G53 | ? | ✅ nonmodal G0/G1; arcs rejected | Not established |
| G28/G30 | ? complete semantics | ✅ configured G28; no G30 | Not established |
| G54–G59 | ✅ G54 example [C5] | ✅ WCS | ≈ |
| G54.1 P / G10 L2/L20 | ? | ✅ runtime offsets | Not established |
| G40/G41/G42 nose compensation | ✅ tool setup [C2, C5]; accuracy untested | ✅ supported 2D compensation with tool geometry | Not ranked |
| T0101 tool/offset | ✅ [C5] | ✅ tool/offset state | ≈ |
| G96/G97 CSS/RPM | ✅ [C5] | ✅ | ≈ |
| G50 S spindle clamp | ✅ [C5] | ✅ | ≈ |
| G98/G99 Type A feed | ✅ G99 example [C5] | ✅ feed/min and feed/rev | ≈ |
| G94/G95 Type B feed | ? for Type B | ✅ | Not established |
| G32/G33 single threading | ? geometric execution | ✅ synchronized threading motions | Not established |
| G70 P/Q finishing | ✅ example and Backplot [C5] | ✅ P/Q profile expansion | ≈ |
| G71 longitudinal roughing | ✅ OD/ID example and V8 fixes [C3, C5] | ✅ OD/ID passes; Type II restrictions | ≈ basic function |
| G72 face roughing | ✅ historical V7 fixes [C4] | ✅ restricted complex Type II | ≈ cycle class |
| G73 pattern repetition | ? in V8 | ✅ repeated profile displacement | Not established |
| G74 face peck/grooving | ✅ historical V7 fixes [C4] | ✅ Z direction | ≈ cycle class |
| G75 grooving | ✅ historical V7 fixes [C4] | ✅ X direction | ≈ cycle class |
| G76 multipass threading | ✅ two-line example and V8 fixes [C3, C6] | ✅ two-line passes, supported flank infeed and thread geometry; chamfer interval is axial | ≈ main cycle; not every variant |
| G83 axial peck drilling | ✅ historical mention [C4] | ✅ | ≈ cycle class |
| G84 axial tapping | ✅ historical mention [C4] | ✅ | ≈ cycle class |
| G90/G92/G94 Type A cycles | ? exact V8 geometry | ✅ modal turning/threading/facing | Not established |
| G77/G78/G79 Type B cycles | ? | ✅ modal turning/threading/facing | Not established |
| A contour angle | ? | ✅ restricted endpoint calculation | Not established |
| C chamfer / R fillet | ? | ✅ G1 contour chamfer/fillet | Not established |
| Macro B, IF/WHILE, G65 | ⚠️ V8 fixes; runtime not fully specified [C3] | ✅ shared milling/turning runtime | Not ranked |
| M98/M99 | ? | ✅ O subprograms, L | Not established |
| 2D turning stock removal | ✅ Solid Animation [C2, C5] | ✅ calculated stock and thread profile | ≈ presence; different algorithms |
| C/Y mill-turn | ? for V8; later demos are not V8 evidence | ❌ in fanuc_turn | Not established |
| Full machine simulation | ? not established for this Backplot | ❌ | No verified equivalence |
| Turning → EXPANDED | ? comparable mode not found | ⚠️ geometric export with turning-cycle restrictions | Not established |

## 3. Native SINUMERIK 840D milling

SINUMERIK ISO mode is excluded from this comparison. Native-cycle support applies to documented parameter subsets, not every technology option on a Siemens controller.

| Area / command | CIMCO Edit 8 | Easy G-Code Plot 1.9.8 | Assessment |
|---|---|---|---|
| G0/G1, modal XYZ | ✅ [U] | ✅ | ≈ |
| ANG= | ✅ [U] | ❌ unmodeled geometry stops execution | CIMCO in supplied observations |
| CHF/CHR/RND | ✅ geometry [U] | ⚠️ parsed without geometric effect | CIMCO in supplied observations |
| G2/G3, CR=, TURN= | ✅ G2/G3 [U]; extensions unconfirmed | ✅ arcs, CR/TURN, block-local circle plane | Extended-form equivalence untested |
| CIP | ✅ [U] | ✅ spatial arcs through an intermediate point | ≈ |
| G4 F/S | ✅ [U] | ⚠️ G4 F; G4 S warns | CIMCO for G4 S in observations |
| G17/G18/G19 | ✅ [U] | ✅ | ≈ |
| G40/G41/G42 | ✅ [U] | ✅ supported 2D milling compensation | ≈ subset |
| G500 | ✅ [U] | ✅ WCS rebasing | ≈ |
| G54–G59 | ✅ [U] | ✅ | ≈ |
| G70/G71, G700/G710 units | ✅ [U] | ✅ | ≈ |
| G90/G91 | ✅ [U] | ✅ | ≈ |
| G93/G94/G95 | ✅ [U] | ✅ inverse-time with rotary/TCP restrictions | ≈ presence |
| G96/G97, G961/G971 | ✅ [U] | ✅ restricted CSS/RPM model | ≈ subset |
| G937 | ✅ [U] | ❌ | CIMCO in observations |
| TRANS/ATRANS | ✅ [U] | ✅ executable programmed frames | ≈ |
| ROT/AROT/RPL | ✅ [U]; V8 fixes [C3] | ✅ supported spatial rotations and RPL | ≈ supported forms |
| SCALE/ASCALE | ✅ [U] | ❌ unmodeled geometry stops execution | CIMCO in observations |
| MIRROR/AMIRROR | ✅ [U] | ❌ unmodeled geometry stops execution | CIMCO in observations |
| GOTO / IF GOTO | ✅ [U, C3] | ✅ numeric N labels | More CIMCO forms observed |
| WHILE/ENDWHILE | ? exact native V8 flow | ✅ bounded nested loops | Not established |
| RET/GOTOC/GOTOB/GOTOF | ✅ [U] | ❌ native flow stops with diagnostic | CIMCO in observations |
| AC() / IC() | ✅ AC; ⚠️ IC arcs in author test [U] | ✅ IJK AC and XYZABC IC | No general ranking |
| DC() rotary endpoints | ? exact V8 semantics | ⚠️ shortest-path angles; out-of-range values normalized with warning; half-turn ties rejected | Not established |
| R parameters and arithmetic | ✅ [U] | ✅ arithmetic, comparisons, SIN/COS/ABS/SQRT | ≈ subset |
| Named production variables | ✅ [U] | ⚠️ R and restricted _NAME; arbitrary names unsupported | CIMCO in observations |
| Symbolic labels / SPF calls | ✅ [U] | ❌ arbitrary named calls/labels | CIMCO in observations |
| M17, M96/M97/M99 | ✅ [U] | ❌ native flow stops | CIMCO in observations |
| M66/M98 | ✅ [U] | ⚠️ warning; no native subprogram call | CIMCO for calls in observations |
| M3/M4/M5/M6/M8/M9, M19 | ✅ [U] | ✅ logical signals, no machine physics | ≈ signals |
| Named T / D0/D1/D2 | ✅ [U, C3] | ✅ name and D state; no inferred offset tables | ≈ subset |
| SUPA / G0 SUPA | ✅ [U] | ✅ configured reference-return model | ≈ subset |
| CYCLE800 3+2 / reset | ❌ in author's tested setup [U]; other V8 builds untested | ✅ static AC/BC, 14–16 arguments; pure rapid rotary indexing retains frame | Easy in that test only |
| TRAORI / TRAFOOF | ? exact V8 TCP contract | ✅ supported AC/BC TCP subset | Not established |
| 4/5-axis Backplot / rotary | ✅ setup [C2] | ✅ AC/BC profiles and tool orientation | ≈ class; geometry untested |
| Full machine simulation | ? not established for Backplot | ❌ | No verified equivalence |
| CYCLE81 | ✅ [U] | ✅ supported drilling parameters | ≈ subset |
| CYCLE801 | ✅ [U] | ❌ | CIMCO in observations |
| CYCLE82 | ✅ [U] | ✅ dwell drilling | ≈ subset |
| CYCLE83 | ✅ [U] | ✅ peck/chip-breaking subset | ≈ subset |
| CYCLE84 | ✅ [U] | ✅ metric right/left and deep tapping; equal SST/SST1 matching S, G94, explicit PIT | ≈ supported subset |
| CYCLE840 | ✅ [U] | ❌ | CIMCO in observations |
| CYCLE85 | ✅ [U] | ✅ reaming with distinct FFR/RFF feeds | ≈ supported subset |
| CYCLE86 | ✅ [U] | ✅ fine boring, orientation and RPA/RPO/RPAP clearance | ≈ supported subset |
| CYCLE87 | ✅ [U] | ✅ boring with spindle-stop/manual-stop signals and rapid return | ≈ supported subset; no operator simulation |
| CYCLE88 | ✅ [U] | ❌ | CIMCO in observations |
| CYCLE89 | ✅ [U] | ✅ bottom dwell and feed withdrawal | ≈ supported subset |
| CYCLE90 | ✅ [U] | ❌ | CIMCO in observations |
| POCKET1/2/3/4 | ✅ [U] | ❌ native cycle execution; GUI pocket generator is separate | CIMCO for native cycles |
| HOLES1/HOLES2 | ✅ [U] | ❌ native cycle execution; GUI hole generator is separate | CIMCO for native cycles |
| LONGHOLE, SLOT1/SLOT2 | ❌ author's table [U] | ❌ | Unsupported in this comparison |
| CYCLE71/72 | ❌ author's table [U] | ❌ | Unsupported in this comparison |
| CYCLE73/74/75/76/77 | ❌ author's table [U] | ❌ | Unsupported in this comparison |
| CYCLE60 engraving | ❌ author's table [U] | ❌ | Unsupported in this comparison |
| CYCLE899 | ❌ author's table [U] | ❌ | Unsupported in this comparison |
| CYCLE832 | ❌ author's table [U] | ⚠️ recognized, ignored setting | Recognition only |
| MCALL CYCLE81/82/83/84/85/86/87/89 | ✅ [U] | ✅ supported modal drilling/tapping/boring | ≈ subset |
| MCALL custom SPF | ✅ [U] | ❌ | CIMCO in observations |
| HOLES2 with MCALL | ✅ [U] | ❌ native hole-pattern execution | CIMCO in observations |
| STOPRE | ✅ [U] | ❌ unsupported native command | CIMCO in observations |
| EXPANDED / native↔FANUC | ? equivalent replay contract not found | ✅ three axes, experimental AC/BC; unsupported cases rejected | Different documented contracts |

## Sources and verification limits

- **[U]** The author's supplied `sinumerik_cimco_1.9.7(1).md` observations and production MPF files. Historical observations were retained; no new CIMCO binary comparison was performed for 1.9.8.
- **[E]** Current 1.9.8 source: [FAQ](../FAQ.md), [kernel](../app/gcode/kernel/), [export](../app/gcode/export/), [full Fusion regressions](../tests/dialects/test_fusion_benchmark.py), [native cycle regressions](../tests/dialects/test_sinumerik_cam_cycles.py) and [export regressions](../tests/export/test_drilling_operations.py).
- **[C1]** [CIMCO Edit V8: FANUC G/M codes](https://www.cimco.com/documentation/online/cimco_edit/v8/en/ExercisesMillingFanucGMCodes.html).
- **[C2]** [CIMCO Edit V8: Backplot setup](https://www.cimco.com/documentation/online/cimco_edit/v8/en/SetupBackplot.html).
- **[C3]** [CIMCO Edit 8 release notes](https://www.cimco.com/download/releases/?p=edit&v=8.00.30).
- **[C4]** [CIMCO Edit 7 release notes](https://www.cimco.com/download/releases/?p=edit&v=7.55.68). Historical evidence for cycle classes, not proof of every V8 variant.
- **[C5]** [CIMCO Edit V8: FANUC turning exercise 1](https://www.cimco.com/documentation/online/cimco_edit/v8/en/ExercisesTurningFanuc1.html).
- **[C6]** [CIMCO Edit V8: FANUC turning exercise 4](https://www.cimco.com/documentation/online/cimco_edit/v8/en/ExercisesTurningFanuc4.html).

Support means the stated documented or tested behavior. It does not establish equal trajectory accuracy, complete controller emulation, machine collision detection or interchangeability of NC output. Configure tools, WCS and kinematics for the program being reviewed. Experimental five-axis export retains its documented limitations.
