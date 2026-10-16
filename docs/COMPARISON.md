# CIMCO Edit 8 vs Easy G-Code Plot 2.7.0

Comparison of document editing, text comparison, FANUC milling, FANUC turning, native SINUMERIK 840D milling/limited XZ turning and native HEIDENHAIN iTNC 530 Klartext. [Русская версия](COMPARISON_RU.md).

**Scope:** CIMCO Edit **8 editor and Backplot**, not CIMCO Edit 2022–2026 or the separate CIMCO Machine Simulation product. Easy G-Code Plot describes the 2.7.0 working tree and its regression fixtures. The MDI/Compare update concerns the editor; controller-command rows retain their previously stated evidence. This is a capability comparison, not a measured accuracy or performance ranking.

**Legend:** ✅ supported within the stated scope; ⚠️ partial or restricted; ❌ explicitly unsupported; **?** not established for CIMCO Edit 8. **Unknown does not mean unsupported.** ≈ means comparable only within the stated scope. A command in a filter is not evidence of correct geometry. Statements marked [N] are historical comparison notes, not vendor certification.

## What's new in 2.7.0: native iTNC rotary execution

- Bounded native SINUMERIK XZ turning and ISO-T input, including the implemented CYCLE93/95/97 subsets. CYCLE95 nominal-contour execution and its unverified nose-compensation warning do not establish controller-equivalent geometry. DXF observations from another backplotter are comparison evidence, not a normative Siemens reference. See [turning coverage and limits](../FAQ.md#is-sinumerik-lathe-supported); no new CIMCO support or accuracy rating is inferred here.
- Native `PLANE SPATIAL/RESET` with STAY/TURN, SEQ branch selection, A/B/C indexing and AC/BC table `M128/M129` or the supported FUNCTION TCPM form. Continuous rotary motion requires L blocks and active TCP.
- The supplied three-post CAM project reaches M30 on all three dialects with `5ax_table_ac` and Home Z=100. Tests compare 1182 normalized cutting segments, arcs, feeds, tools and start/end tool axes within 0.002 mm positional tolerance. This verifies the reference project, not arbitrary posts or full machine simulation.

## What's new in 2.6.0: view rotation

- **Rotate view** rotates Top/Front/Left around model X/Y/Z without CNC recalculation, retaining scale and per-document camera state. Available in View, plot context menus, toolbar customization and Hotkeys; disabled in ISO/3D and turning. Grid and ruler follow coordinate planes and are disabled at oblique angles.

## Document and controller features retained from earlier releases

- MDI and Compare were introduced in 2.4.0; native HEIDENHAIN input and three-axis execution in 2.5.0; RND/CHF contour geometry in 2.6.0.
- MDI keeps multiple NC programs in one workspace. The application starts with one empty milling document. Use **+ / File → New**, the document-list arrow and **× / Ctrl+W** to create, select and close documents. Opening an already open file selects its existing buffer; opening a different file preserves nonempty documents and their unsaved edits. Close All and application exit check each modified document for Save, Discard or Cancel.
- Each document retains its text and undo history, cursor/selection, encoding, machine mode, source overrides, current-program tools, cached execution, view direction and playback position. Stock settings, STL objects and STL edit history also belong to the document. Shared Options, saved libraries, WCS/Home and rotary selection remain application preferences; changed shared CNC inputs make an inactive cached trace stale on selection. Finish or cancel pending editing dialogs before switching documents.
- **CNC Functions → Compare** opens two read-only text panes with file selectors, a resizable splitter and synchronized vertical/horizontal scrolling. Sources can be open MDI buffers, including unsaved text, or independently selected disk files decoded through the existing UTF-8/legacy mechanism. Yellow marks changed lines, green added lines and red removed lines; display padding aligns corresponding rows. Refresh reloads selected disk files and rereads MDI buffers without replacing unsaved documents. Copying and both application themes are supported. The command participates in Hotkeys and Customize Toolbars.
- Easy Compare is an ordinary line diff: spacing, block numbers and comments remain significant; CRLF/LF line endings are normalized. It does not merge/edit sources, save/print diff reports or compare CNC semantics, geometry or toolpaths. These limits distinguish it from CIMCO's configurable File Compare; they do not change the execution kernel or export capabilities.
- Menu groups follow the document workflow. **View → STL Objects** opens the scene panel; **CNC Functions → Tokens/Variables** opens the inspector. **Settings → Options** contains editor, plot, hotkey, postprocessor and rotary-profile preferences. Customize Toolbars restores compact default groups while leaving saved button selections intact until an explicit reset; printing, clipboard/formatting buttons and calculators are optional.
- **iTNC-code** provides highlighting for native Klartext input. `.h`/`.H` opens with a native immutable AST and three-axis execution for `L/CC/C/CR/CT/LP/CP`, `APPR/DEP`, tools, feeds, spindle, `M91`, Q parameters, label flow and drilling/boring/tapping cycles; Cycle 32 retains smoothing metadata. `RND`/`CHF` construct programmed-contour geometry before existing RL/RR/R0 compensation. Configured rotary indexing, PLANE SPATIAL/RESET and AC/BC table M128/TCPM execution are available in 2.7.0. Tool offsets DL/DR/DR2, auxiliary axes and `M120` remain unsupported. See [the iTNC input coverage in the FAQ](../FAQ.md#heidenhain-itnc-530-input) and section 4 below. The existing Heidenhain export post has separate coverage.

## Editor and document workflow

| Feature | CIMCO Edit 8 | Easy G-Code Plot 2.7.0 | Assessment |
| --- | --- | --- | --- |
| Multiple open programs / MDI | ✅ multiple file windows [C7] | ✅ independent buffers and document scenes; compact controls without visible tabs [E] | Both support multiple programs; window organization differs |
| Side-by-side text comparison | ✅ two-pane comparison with colored differences [C7] | ✅ read-only aligned line diff; changed/added/removed colors and synchronized scrolling [E] | ≈ feature present; comparison options differ |
| Compare unsaved open buffers and disk files | ? exact unsaved-buffer contract not established here | ✅ current MDI text or independent disk snapshots; no document replacement [E] | Easy behavior is covered by regression tests |
| Ignore formatting or selected text categories | ✅ optional ignoring of block numbers, spaces, comments, case and numeric formatting [C9] | ❌ no such filters; ordinary text diff with normalized line endings [E] | CIMCO offers additional comparison filters |
| Editing / synchronizing differences | ✅ editing modes and difference synchronization documented [C9] | ❌ read-only; no merge or synchronization of source text [E] | Different scope; synchronized scrolling is not merging |
| Print a comparison report | ✅ side-by-side/differences printing [C8, C9] | ❌ no diff-report printing or saving [E] | Separate from Easy's existing CNC export and plot printing |
| Token/diagnostic filters | ? equivalent V8 workflow not established here | ✅ All/Warnings/Errors, shown/total count and case-insensitive text search; copying and CSV respect filters. Opening/refreshing reuses the current execution result [E] | [Tokens workflow](../FAQ.md#what-is-the-tokens-tab); filtering does not recalculate; missing/stale results require analysis |
| Missing/incompatible rotary profile | ? equivalent notification not established here | ✅ persistent plot notice with detected axes and source line; direct profile selection and editor navigation, including zero-angle addresses [E] | [Rotary workflow](../FAQ.md#how-is-indexed-rotary-milling-handled); machine geometry is not inferred from axis letters |
| Controller variable inspector | ? equivalent snapshot coverage not established here | ✅ Variables: FANUC numbered/named, SINUMERIK R/named and HEIDENHAIN Q/QL/QR snapshots; dialect, source line and occurrence context, numeric ordering and CSV [E] | [Recorded variable state](../FAQ.md#what-is-the-variables-tab); playback reads existing execution snapshots |

Implementation and regressions: [MDI](../app/ui/windows/main_window_documents.py), [MDI tests](../tests/gui/test_documents.py), [Compare](../app/ui/dialogs/compare.py), [Designer dialog](../app/ui/generated/dialogs/compare.ui), [Compare tests](../tests/gui/test_compare.py), [Hotkeys](../app/ui/support/hotkeys.py), [toolbar customization](../app/ui/support/toolbar_settings.py).

## Backplot capabilities in the current version

- G0 stock contact is visualized in both machining modes. Milling GPU removal retains a rapid-damage marker in the height field; turning marks the intersection with remaining material without removing it on G0, restores marks on rewind and clips them as later cuts remove the affected material. Neither model checks holders, fixtures or machine components.
- Settings → Options → Rotary Kinematics contains 24 read-only built-in configurations, named user copies, table/head ownership, signed direction vectors, joint order and visibility. Optional paired Min/Max angular limits on user copies produce nonblocking source-line warnings; they do not alter geometry, wrap angles or select another inverse solution.
- Milling 3D picking selects sampled lines and arcs by camera depth and synchronizes the editor and playback occurrence. Shift+left-click remains the default. Settings → Options → General → Cimco Like Picking enables left-click selection and right-button panning, with a context menu on a right-click without dragging.
- Measure provides two-point coordinates and distances in fixed XY/XZ/YZ and turning views. It has priority over trajectory picking while active; turning displays diameter coordinates separately from physical distances. Measure in a free 3D view remains outside its scope.
- The 2.0 release adds 3D Stock Removal for three-axis FANUC and native SINUMERIK milling, alongside existing 2D turning stock removal; 2.5.0 extends it to native HEIDENHAIN iTNC three-axis Klartext. The current comparison includes the 2.7.0 native rotary execution updates.
- Milling removal runs on the GPU using configured cutter geometry and a sampled height field. It supports box stock, vertical cutters, playback/rewind, five Accuracy levels and STL export of the current machining stage. OpenGL 4.3 is required; rotary/TCP removal, undercuts and subtraction from imported STL solids are outside this model.
- Milling and turning use the same Stock Removal button and Stock dialog, with settings for the active machining mode. Imported STL models remain visual references.
- Previously checked FANUC/SINUMERIK comparison rows retain their recorded evidence; they have not undergone a new paired CIMCO review. This does not imply unchanged language support: native HEIDENHAIN execution was added in 2.5.0 and RND/CHF geometry in 2.6.0. Stock removal is distinct from full machine collision simulation.

## Language updates retained from 1.9.8

- FANUC milling adds G74 left tapping, G76 fine boring, G87 back boring and G89 dwell/feed-return boring. G74/G84 Q now produces synchronized tapping pecks. Q shift direction and tapping retract behavior are configurable machine assumptions.
- Native SINUMERIK adds CYCLE85/86/87/89 and extends CYCLE84 to metric right/left and deep tapping, including VARI=1/2, DAM/VRT and balanced final pecks. CYCLE88 remains unsupported.
- Siemens circles can select a block-local plane from two endpoint axes; helical TURN moves retain the modal plane. Pure rapid rotary indexing can retain an active CYCLE800 frame.
- Both Fusion 1001 regression programs reach M30 on **5Ax Table AC**. Tests cover home Z=0 and 500. This verifies those fixtures, not arbitrary CAM output. Missing tool geometry leaves compensation unverified. Out-of-range DC angles are normalized with warnings for backplot compatibility; that does not validate them for a real controller.
- G92.1 zero-valued axis selectors are treated as coordinate preset without physical motion. The model has no manual/G92 shift to cancel. FANUC G53 machine coordinates and configured G28 reference returns were already supported.
- An invalid arc produces a diagnostic and execution can continue to later blocks. Completion and validity are separate result fields; reaching M30 alone does not establish a valid result.

## Visualization and configuration

| Feature | CIMCO Edit 8 | Easy G-Code Plot 2.7.0 | Assessment |
| --- | --- | --- | --- |
| Stock contact on G0 | ? exact remaining-stock/damage contract | ✅ milling rapid-damage markers and turning remaining-stock intersections | Present in both Easy modes; no paired accuracy test |
| Rotary profile editor and limits | ✅ 4/5-axis setup [C2]; exact limit contract unconfirmed | ✅ Options tab, named copies, optional angular warning limits | Settings do not establish physical machine equivalence |
| Milling 3D toolpath picking | ? exact selection/control contract | ✅ depth-aware line/arc selection; source and playback synchronization | No new CIMCO binary comparison |
| Optional mouse controls | ? exact binding contract | ✅ default Shift+left-click or Cimco Like Picking; click/drag separation | Easy offers two control modes |
| Two-point measurement | ? V8 contract not established here | ✅ fixed milling views and turning; editable coordinates and mm/inch | Free 3D Measure is not supported |

Implementation and regressions: [navigation](../app/ui/plot/plot_navigation.py), [3D picking](../app/ui/plot/trace_picking.py), [Measure](../app/ui/plot/ruler.py), [rotary limits](../tests/core/test_rotary_limits.py), [turning collisions](../tests/stock/test_turning_stock_collisions.py), [milling rapid damage](../tests/stock/test_milling_stock_gpu.py).

## 1. FANUC milling

| Area / command | CIMCO Edit 8 | Easy G-Code Plot 2.7.0 | Assessment |
| --- | --- | --- | --- |
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
| Continuous 4-axis X/C | ✅ 4/5-axis class [C2]; X/C semantics unknown | ✅ tested 4Ax Table C subset | Not established |
| Continuous 5-axis AC/BC | ✅ 5-axis Backplot [C2]; TCP scope unknown | ✅ AC/BC TCP and tool orientation | Not ranked |
| Full machine simulation | ? not established for this Backplot | ❌ | No verified equivalence |
| Finished-part STL overlay | ? V8 overlay scope | ✅ visual STL overlay; removal uses separate box stock | Not established |
| 3D milling stock removal | ✅ Solid Animation [C2] | ✅ GPU three-axis box stock; height-field model, OpenGL 4.3 [E] | ≈ feature present; scope and accuracy not compared |
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

| Area / command | CIMCO Edit 8 | Easy G-Code Plot 2.7.0 | Assessment |
| --- | --- | --- | --- |
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

| Area / command | CIMCO Edit 8 | Easy G-Code Plot 2.7.0 | Assessment |
| --- | --- | --- | --- |
| G0/G1, modal XYZ | ✅ [N] | ✅ | ≈ |
| ANG= | ✅ [N] | ❌ unmodeled geometry stops execution | CIMCO in historical comparison notes |
| CHF/CHR/RND | ✅ geometry [N] | ⚠️ parsed without geometric effect | CIMCO in historical comparison notes |
| G2/G3, CR=, TURN= | ✅ G2/G3 [N]; extensions unconfirmed | ✅ arcs, CR/TURN, block-local circle plane | Extended-form equivalence untested |
| CIP | ✅ [N] | ✅ spatial arcs through an intermediate point | ≈ |
| G4 F/S | ✅ [N] | ⚠️ G4 F; G4 S warns | CIMCO for G4 S in observations |
| G17/G18/G19 | ✅ [N] | ✅ | ≈ |
| G40/G41/G42 | ✅ [N] | ✅ supported 2D milling compensation | ≈ subset |
| G500 | ✅ [N] | ✅ WCS rebasing | ≈ |
| G54–G59 | ✅ [N] | ✅ | ≈ |
| G70/G71, G700/G710 units | ✅ [N] | ✅ | ≈ |
| G90/G91 | ✅ [N] | ✅ | ≈ |
| G93/G94/G95 | ✅ [N] | ✅ inverse-time with rotary/TCP restrictions | ≈ presence |
| G96/G97, G961/G971 | ✅ [N] | ✅ restricted CSS/RPM model | ≈ subset |
| G937 | ✅ [N] | ❌ | CIMCO in observations |
| TRANS/ATRANS | ✅ [N] | ✅ executable programmed frames | ≈ |
| ROT/AROT/RPL | ✅ [N]; V8 fixes [C3] | ✅ supported spatial rotations and RPL | ≈ supported forms |
| SCALE/ASCALE | ✅ [N] | ❌ unmodeled geometry stops execution | CIMCO in observations |
| MIRROR/AMIRROR | ✅ [N] | ❌ unmodeled geometry stops execution | CIMCO in observations |
| GOTO / IF GOTO | ✅ [U, C3] | ✅ numeric N labels | More CIMCO forms observed |
| WHILE/ENDWHILE | ? exact native V8 flow | ✅ bounded nested loops | Not established |
| RET/GOTOC/GOTOB/GOTOF | ✅ [N] | ❌ native flow stops with diagnostic | CIMCO in observations |
| AC() / IC() | ✅ AC; ⚠️ IC arcs in author test [N] | ✅ IJK AC and XYZABC IC | No general ranking |
| DC() rotary endpoints | ? exact V8 semantics | ⚠️ shortest-path angles; out-of-range values normalized with warning; half-turn ties rejected | Not established |
| R parameters and arithmetic | ✅ [N] | ✅ arithmetic, comparisons, SIN/COS/ABS/SQRT | ≈ subset |
| Named production variables | ✅ [N] | ⚠️ R and restricted _NAME; arbitrary names unsupported | CIMCO in observations |
| Symbolic labels / SPF calls | ✅ [N] | ❌ arbitrary named calls/labels | CIMCO in observations |
| M17, M96/M97/M99 | ✅ [N] | ❌ native flow stops | CIMCO in observations |
| M66/M98 | ✅ [N] | ⚠️ warning; no native subprogram call | CIMCO for calls in observations |
| M3/M4/M5/M6/M8/M9, M19 | ✅ [N] | ✅ logical signals, no machine physics | ≈ signals |
| Named T / D0/D1/D2 | ✅ [U, C3] | ✅ name and D state; no inferred offset tables | ≈ subset |
| SUPA / G0 SUPA | ✅ [N] | ✅ configured reference-return model | ≈ subset |
| CYCLE800 3+2 / reset | ❌ in author's tested setup [N]; other V8 builds untested | ✅ static AC/BC, 14–16 arguments; pure rapid rotary indexing retains frame | Easy in that test only |
| TRAORI / TRAFOOF | ? exact V8 TCP contract | ✅ supported AC/BC TCP subset | Not established |
| 4/5-axis Backplot / rotary | ✅ setup [C2] | ✅ AC/BC profiles and tool orientation | ≈ class; geometry untested |
| 3D milling stock removal | ✅ Solid Animation [C2]; native SINUMERIK scope unverified | ✅ three-axis native milling, GPU box stock and STL export [E] | ≈ feature present; dialect scope not compared |
| Full machine simulation | ? not established for Backplot | ❌ | No verified equivalence |
| CYCLE81 | ✅ [N] | ✅ supported drilling parameters | ≈ subset |
| CYCLE801 | ✅ [N] | ❌ | CIMCO in observations |
| CYCLE82 | ✅ [N] | ✅ dwell drilling | ≈ subset |
| CYCLE83 | ✅ [N] | ✅ peck/chip-breaking subset | ≈ subset |
| CYCLE84 | ✅ [N] | ✅ metric right/left and deep tapping; equal SST/SST1 matching S, G94, explicit PIT | ≈ supported subset |
| CYCLE840 | ✅ [N] | ❌ | CIMCO in observations |
| CYCLE85 | ✅ [N] | ✅ reaming with distinct FFR/RFF feeds | ≈ supported subset |
| CYCLE86 | ✅ [N] | ✅ fine boring, orientation and RPA/RPO/RPAP clearance | ≈ supported subset |
| CYCLE87 | ✅ [N] | ✅ boring with spindle-stop/manual-stop signals and rapid return | ≈ supported subset; no operator simulation |
| CYCLE88 | ✅ [N] | ❌ | CIMCO in observations |
| CYCLE89 | ✅ [N] | ✅ bottom dwell and feed withdrawal | ≈ supported subset |
| CYCLE90 | ✅ [N] | ❌ | CIMCO in observations |
| POCKET1/2/3/4 | ✅ [N] | ❌ native cycle execution; GUI pocket generator is separate | CIMCO for native cycles |
| HOLES1/HOLES2 | ✅ [N] | ❌ native cycle execution; GUI hole generator is separate | CIMCO for native cycles |
| LONGHOLE, SLOT1/SLOT2 | ❌ comparison notes [N] | ❌ | Unsupported in this comparison |
| CYCLE71/72 | ❌ comparison notes [N] | ❌ | Unsupported in this comparison |
| CYCLE73/74/75/76/77 | ❌ comparison notes [N] | ❌ | Unsupported in this comparison |
| CYCLE60 engraving | ❌ comparison notes [N] | ❌ | Unsupported in this comparison |
| CYCLE899 | ❌ comparison notes [N] | ❌ | Unsupported in this comparison |
| CYCLE832 | ❌ comparison notes [N] | ⚠️ recognized, ignored setting | Recognition only |
| MCALL CYCLE81/82/83/84/85/86/87/89 | ✅ [N] | ✅ supported modal drilling/tapping/boring | ≈ subset |
| MCALL custom SPF | ✅ [N] | ❌ | CIMCO in observations |
| HOLES2 with MCALL | ✅ [N] | ❌ native hole-pattern execution | CIMCO in observations |
| STOPRE | ✅ [N] | ❌ unsupported native command | CIMCO in observations |
| EXPANDED / native↔FANUC | ? equivalent replay contract not found | ✅ three axes, experimental AC/BC; unsupported cases rejected | Different documented contracts |

## 4. Native HEIDENHAIN iTNC 530 milling

HEIDENHAIN is a separate input dialect, not a FANUC/SINUMERIK variant. Easy G-Code Plot parses and executes a documented Klartext subset with three-axis, indexed 3+2 and AC/BC table TCP execution and stops at unsupported semantics; the comparison below does not rank Klartext backplot accuracy.

| Area / command | CIMCO Edit 8 | Easy G-Code Plot 2.7.0 | Assessment |
| --- | --- | --- | --- |
| Source detection and highlighting | ? Klartext support in V8 not established here | ✅ `.h`/`.H`, `BEGIN PGM` detection and iTNC-code highlighting [E] | Not established |
| `BEGIN/END PGM`, `MM/INCH`, BLK FORM | ? | ✅ program/unit metadata and stock bounds; metric conversion | Not established |
| Native source/AST fidelity | ? no equivalent internal contract assessed | ✅ immutable Klartext AST; original lines, `/` skip, numeric prefixes, source line/column and cycle Q continuations preserved | Easy implementation guarantee, not a backplot ranking |
| `L`, omitted-L, `IX/IY/IZ` | ? | ✅ three-axis straight motion with incremental addresses | Not established |
| `CC`/`C`/`CR`/`CT` | ? | ✅ center, direction, radius and tangent arcs | Not established |
| `LP`/`CP` polar and helix | ? | ✅ polar positioning and polar/helical arcs | Not established |
| `APPR`/`DEP` LT/LN/CT/LCT | ? | ✅ approach/departure lines and tangent arcs | Not established |
| `TOOL CALL`/`TOOL DEF`, S/F | ? | ✅ numeric/named/Q tools and spindle axis; `DL/DR/DR2` stop execution | Not established |
| `R0`/`RL`/`RR` | ? | ✅ modal compensation state passed to the shared geometry resolver | Not established |
| `M0/M1/M3/M4/M5/M6/M8/M9/M13/M14/M30`, `M99` | ? | ✅ logical signals, spindle state, program end and cycle call | Not established |
| `M91` machine coordinates | ? | ✅ nonmodal absolute XYZ using the configured WCS | Not established |
| Cycle 247 datum selection | ? | ✅ application mapping `Q339=1..6` to configured G54..G59; machine position preserved | Controller preset tables are not imported |
| Cycles 7/10 | ? | ✅ axis-address datum shifts and XY planar rotation, including circle-center transforms and cancellation | No tilted-plane or datum-table variant |
| `M140 MB distance` / `MB MAX` | ? | ✅ physical machine +Z retraction mapped through table orientation; MAX uses enabled Home Z with a warning and NC trace export guard | Physical travel limits are not modeled |
| `LBL`, `CALL LBL`, `REP`, `FN 9–12` | ? | ✅ label flow with call stack, repeats and conditional GOTO | Not established |
| Q/QL/QR, `FN 0–4/6/7`, expressions | ? | ✅ bounded arithmetic, comparisons and function trees without `eval` | Not established |
| Q ranges and parse diagnostics | ? | ✅ `Q0–Q1999`, `QL/QR0–499`; errors keep source line, column and diagnostic code | No matched CIMCO test |
| `F0` and repeated feeds | ? | ⚠️ geometry retained, zero-feed timing warned; final repeated feed applies | No matched CIMCO test |
| `CYCL DEF`/`CYCL CALL` 1/2, 200–209, 240/241 | ? | ✅ expanded drilling/boring/tapping geometry | Not established |
| Cycle 32 smoothing | ? | ⚠️ metadata only; controller smoothing not simulated | Not established |
| Optional `/` block skip and `LBL 0` | ? | ✅ skip and source block numbers preserved; separate named/numeric label maps and return handling | Not established |
| Klartext editor calculators and renumber | ? | ✅ native `L`/`CR`, `CC`/`CP` fragments; numeric prefixes without `N`, optional `/` retained | Editor tools, not CNC execution equivalence |
| `RND R… [F…]` / `CHF … [F…]` | ? | ✅ tangent line/arc rounding and straight-line chamfers; neighbor trimming, block-local feed and existing RL/RR/R0 compensation. ⚠️ unique planar local corners with residual neighboring lengths | [References and limits](../FAQ.md#how-is-the-itnc-implementation-verified); no matched CIMCO run |
| A/B/C indexing, IA/IB/IC | ? | ✅ matching configured kinematics required, including zero angles | No matched CIMCO run |
| PLANE SPATIAL/RESET | ? | ✅ STAY/TURN and SEQ branch selection with two rotary joints; MOVE and TABLE COORD unsupported | No matched CIMCO run |
| M128/M129, FUNCTION TCPM | ? | ✅ logical tool-tip control on AC/BC tables with PLANE reset; continuous L motion and start/end tool orientations | OEM pivot lengths are not modeled |
| M126/M127, M94 | ? | ✅ shortest-path rotary positioning and displayed-angle reduction | No matched CIMCO run |
| M120, U/V/W, DL/DR/DR2 | ? | ❌ unsupported execution stops at the source block | Not established |
| 3D milling stock removal | ✅ Solid Animation [C2]; Klartext scope unverified | ✅ three-axis native Klartext, GPU box stock and STL export [E] | ≈ feature present; dialect scope not compared |
| EXPANDED iTNC output | ? | ✅ `heidenhain_itnc530` resolved post (`L/FMAX`, `CC`+`C/CP`, `CR`, `CYCL DEF 200/201/202/203/207`); FULL rejected | Different documented contracts |
| Full machine simulation | ? not established for this Backplot | ❌ | No verified equivalence |

Input implementation and regression evidence: [HEIDENHAIN FAQ](../FAQ.md#heidenhain-itnc-530-input), [native parser](../app/gcode/kernel/frontend/heidenhain.py), [AST tests](../tests/dialects/test_heidenhain_frontend.py), [execution tests](../tests/dialects/test_heidenhain_execution.py), [rotary and three-post geometry tests](../tests/dialects/test_heidenhain_rotary.py), [GUI lexer tests](../tests/gui/test_heidenhain_lexer.py) and [export tests](../tests/export/test_heidenhain.py). The real `sample.h` fixture reaches `M30`, but neither that test nor output-post support proves complete controller coverage.

## Sources and verification limits

- **[N]** Historical comparison notes on CIMCO Edit 8 behavior. These are not an exhaustive vendor reference; no new paired CIMCO binary comparison was performed for 2.7.0.
- **[E]** Current 2.7.0 source: [FAQ](../FAQ.md), [kernel](../app/gcode/kernel/), [export](../app/gcode/export/), [GPU stock removal](../app/ui/plot/milling_stock_gpu.py), [stock replay and STL export](../app/gcode/stock/milling_stock.py), [GPU stock regressions](../tests/stock/test_milling_stock_gpu.py), [full Fusion regressions](../tests/dialects/test_fusion_benchmark.py), [native cycle regressions](../tests/dialects/test_sinumerik_cam_cycles.py) and [export regressions](../tests/export/test_drilling_operations.py).
- **[C1]** [CIMCO Edit V8: FANUC G/M codes](https://www.cimco.com/documentation/online/cimco_edit/v8/en/ExercisesMillingFanucGMCodes.html).
- **[C2]** [CIMCO Edit V8: Backplot setup](https://www.cimco.com/documentation/online/cimco_edit/v8/en/SetupBackplot.html).
- **[C3]** [CIMCO Edit 8 release notes](https://www.cimco.com/download/releases/?p=edit&v=8.00.30).
- **[C4]** [CIMCO Edit 7 release notes](https://www.cimco.com/download/releases/?p=edit&v=7.55.68). Historical evidence for cycle classes, not proof of every V8 variant.
- **[C5]** [CIMCO Edit V8: FANUC turning exercise 1](https://www.cimco.com/documentation/online/cimco_edit/v8/en/ExercisesTurningFanuc1.html).
- **[C6]** [CIMCO Edit V8: FANUC turning exercise 4](https://www.cimco.com/documentation/online/cimco_edit/v8/en/ExercisesTurningFanuc4.html).
- **[C7]** [CIMCO Edit V8: Overview](https://www.cimco.com/documentation/online/cimco_edit/v8/en/Overview.html) — multiple file windows and two-pane text comparison.
- **[C8]** [CIMCO Edit V8: Introduction](https://www.cimco.com/documentation/online/cimco_edit/v8/en/Introduction.html) — File Compare and side-by-side printing.
- **[C9]** [CIMCO Edit V8: File Compare setup](https://www.cimco.com/documentation/online/cimco_edit/v8/en/SetupFileCompare.html) — ignore filters, editing/read-only modes, difference synchronization and print settings.

Support means the stated documented or tested behavior. It does not establish equal trajectory accuracy, complete controller emulation, machine collision detection or interchangeability of NC output. Configure tools, WCS and kinematics for the program being reviewed. Experimental five-axis export retains its documented limitations.
