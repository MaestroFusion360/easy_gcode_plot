# Changelog

## 1.9.4 - Unreleased

- Reconstruct the verified indexed A/B/C, simultaneous table-C and angled AC/BC TCP subsets through multiaxis posts. Tilted-plane/CYCLE800 reconstruction and indexed export about a displaced WCS remain unsupported.
- Emit supported drilling and tapping operations through the selected post's cycle templates, preserving resolved geometry and machine state. Native SINUMERIK posts retain separate classic 01/2008 and extended 03/2009 cycle interfaces.
- Use the display name `840D Extended cycles` in Options, help and diagnostics. Keep the saved `CNC/SINUMERIK_840D_SL` setting, CLI `--sinumerik-cycles classic|sl` values and JSON cycle-profile identifiers compatible.
- Add direct NC reference comparison to CLI `export` with `--compare-with FILE`: print a deterministic unified diff and return 1 on mismatch, 0 on a match, or 2 on export/read errors. Protect the reference from overwrite.
- Add the supplied `ext_cycles.mpf` and `no_ext_cycles.mpf` programs to the fixture corpus, checking common drilling geometry, supported extended tapping, export replay and explicit rejection of unmodeled operations.
- Audit multiaxis reconstruction with real fixture replay in absolute and incremental output. Preserve physical position on repeated G43.4 and G43 cancellation, distribute ABC over split/linearized TCP arcs without cumulative incremental angle drift, and preserve inverse-time block duration after subdivision.
- Keep rotary feed motion at the table-C origin in the trace, retain table-frame metadata on reference returns independently of head orientation, validate every emitted rotary axis against the post, and invalidate modal motion after explicit rotary control frames.
- Allow already-resolved zero-distance reference returns and source-preserving macro/index normalization. Reject indexed export about a displaced WCS until target frame offsets can be reconstructed; classify unverified compensation/ignored native geometry as export limitations with their concrete diagnostic codes.
- Prototype controller-neutral multiaxis EXPANDED reconstruction. Multiaxis posts can declare target TCP control frames; bundled FANUC and SINUMERIK multiaxis profiles map resolved `G43.4`/`G49` and `TRAORI`/`TRAFOOF` semantics across controllers instead of rejecting all TCP execution.
- Emit verified indexed `A/B/C` changes as dedicated rotary rapid frames instead of folding an index into the next XYZ motion. Reconstruct indexed-table XYZ/arc geometry in the rotary frame before postprocessing so replay does not rotate physical coordinates twice.
- Reconstruct the verified non-TCP `4ax_table_c` continuous rotary subset through FANUC and SINUMERIK multiaxis posts. Indexed A/B/C and simultaneous table-C output now re-execute with matching geometry and final rotary state; other unresolved continuous-rotary semantics remain fail-closed.
- Record TCP controls as real state transitions instead of source-word echoes: inactive `G49`, native `D0` and `TRAFOOF` no longer manufacture `TCP_CONTROL_OFF`, and repeated activation/cancellation does not duplicate semantic edges.
- Allow native SINUMERIK A/B/C positioning on any selected profile that actually configures those axes; ISO-M rotary remains fail-closed and TRAORI still requires the supported angled AC/BC TCP profiles.
- Keep tilted working planes/CYCLE800 fail-closed in EXPANDED until their controller reconstruction contract is implemented.
- Add semantic replay regressions for FANUC↔SINUMERIK TCP conversion, indexed/continuous rotary output, TCP edge events, the shared `export_file` path, and both full FANUC five-axis impeller fixtures.

## 1.9.3 - 2026-10-06

- Consolidate user-facing export into three paths: FULL source-preserving normalization, EXPANDED controller postprocessing from resolved execution, and DXF geometry output. Remove Plot Data and separate cycle-export modes from the current export contract.
- Replace controller-specific conversion code with one EXPANDED JSON-profile engine. Add bundled `fanuc_mill`, `fanuc_lathe_a`, `fanuc_lathe_b`, `sinumerik_iso` and `sinumerik_840d` profiles for motion, comments, arcs, positioning, reference returns, tool/spindle/coolant signals, dwell, units and program wrappers.
- Make controller conversion an EXPANDED-only operation. FULL keeps the source controller/dialect and unfolds only flow/label-dependent constructs that cannot safely survive normalization: evaluated Macro B, IF/GOTO/WHILE, G65/M98/M99 and FANUC turning G70–G76.
- Support four explicit EXPANDED arc outputs (relative IJK, absolute IJK, radius and linearized). Native SINUMERIK profiles emit absolute centers with `AC(...)`, radius with `CR=`, and preserve source comments through `;` formatting.
- Treat Target CNC as a syntax/post-profile selector only: EXPANDED is one universal serializer, so every user output option (coordinates, sequence numbers, delimiter, leading zero, modal feed, decimal precision, force decimal, plus sign, arc output and start/end program text) remains available and is honored across FANUC→FANUC, FANUC→SINUMERIK ISO, FANUC→SINUMERIK native and SINUMERIK→FANUC. Profile values are defaults, not overrides. Remove the `allowProgramStartOverride` user-facing restriction so SINUMERIK keeps the mandatory `G290`/`G291` frame first and emits user start text after it.
- Implement Safety Line in the EXPANDED serializer through a profile-declared `program.safety` block, so no visible export setting is silently ignored. Route serialization cancellation into the FULL/EXPANDED serializers so Cancel stops a heavy export instead of only the final write.
- Reorganize the Export Data dialog into two visually separated columns without group titles, rename `As source (no conversion)` to `Auto (source controller)`, drop the old address-force control, and drive option availability by export mode only. A concrete Target CNC no longer disables ordinary formatting controls.
- Move mandatory frame-word output and word ordering into the post profile: `format.words` now defines `order` and `required` for `motion`, `X`, `Y`, `Z`, `A`, `B`, `C`, `I`, `J`, `K` and `R`, with per-word `decimals`/`sign` in the same object. Address requiredness is a property of the specific post/controller, so it now lives in the profile (`format.words.required`) instead of a separate generic axis setting; `required=true` forces an address when it has a resolved value, `motion.required=false` makes the motion code modal, an axis entry is only valid when declared in `supports.axes`, and `F` is excluded because feed is managed by Modal Feed.
- Add bundled `fanuc_mill_multiaxis` and `sinumerik_840d_multiaxis` post profiles that declare `supports.axes` `X/Y/Z/A/B/C` and emit explicit resolved rotary coordinates. They preserve export ability for programs with explicit rotary axes without weakening the three-axis `fanuc_mill` and `sinumerik_840d` profiles; TCP/tilted-plane/CYCLE800 semantics remain unsupported on both.
- Unify GUI, single-file `export` and `batch-export` on one `ExportRequest`/`write_export` contract. The GUI only fills the shared request from the dialog; all target mapping, option resolution, conversion and atomic writing happen in the shared export service, so CLI and batch output is byte-identical to the GUI for the same settings.
- Add a mandatory batch-export semantic regression gate (`tests/export/test_batch_export_semantics.py`, `tests/export_signatures.py`) that runs the four conversion scenarios and re-executes every successfully exported program, comparing the strict per-motion trajectory signature with the source and reporting a conversion that cannot preserve it.
- Refine the three-axis conversion guard so a selected kinematics profile, G65 arguments and non-rotary turning A/C words do not masquerade as rotary geometry; actual rotary/TWP/TCP use remains fail-closed.
- Correct DXF planar-arc OCS/direction handling, including tilted-plane normals and exact 180-degree arcs, while keeping analytical arcs/circles where representable and sampled polylines for multi-turn/helical geometry.
- Replace the stale batch helper set with four explicit conversion scripts for FANUC mill → SINUMERIK native, FANUC mill → SINUMERIK ISO-M, FANUC lathe Type A → Type B, and SINUMERIK native → FANUC mill; outputs go to `tmp/test_export`.
- Add export-contract regression coverage: the 1.9.2 golden corpus remains a semantic reference, while current FULL/EXPANDED behavior and post profiles are tested as the release contract rather than requiring historical text serialization.

## 1.9.2 - 2026-10-05

- Shorten sandbox test7 playback to a brief Play followed by 10% slider steps and completion; retain complete continuous playback for the flange and turning Stock Removal.
- Seed the sandbox milling library with the user's T60 taper-ball-mill geometry (D4, 6-degree taper, 25 mm flute and 50 mm total length). Select T60/D1 in the impeller fixture itself and remove sandbox source rewriting so GUI and kernel tests execute the same program; leave the user's SQLite unchanged.
- Use the shared configured G28/SUPA reference coordinates for native zero XYZ returns, matching FANUC G53 in the application's coordinate model. Preserve absolute SUPA under G91, nonzero targets and rotary zero; resolve the return through WCS and the current AC/BC frame. Set sandbox impeller return Z to 300 and verify parity with FANUC under nonzero WCS. Correct both FAQ architecture diagrams to place tool setup after the shared Program/AST.
- Prevent world-axis arrows from being cut by camera near/far planes when rotating an empty scene. Keep their screen projection and fixed colors, independently of scene depth clipping; cover several camera orientations with regression tests.
- Rotate test7 STL by +90 degrees around Z through Transform before sectioning; Undo preserves that rotation. Include full flange playback and use a faster sandbox timer with cooperative Qt waits for the complete playback stages.
- Play the complete turning Stock Removal and BC impeller in the visible sandbox without slider jumps; select ISO view after New. Support native D0..D12 edge selection with explicit unverified controller-offset diagnostics and frame-only CYCLE800 ST220000/220001. Bind the DMG frame-only call to the selected BC profile; retain rejection of OEM indexing and incompatible profiles. The supplied impeller now completes all 5469 motions through M30.
- Give the flange benchmark explicit T2 D10 end-mill geometry and T4 selection in O8000 so discovery attributes drilling to the caller's tool and all G41/G42 motions resolve without compensation warnings; leave discovery unchanged.
- Keep STL Objects at least 440 pixels wide so operation fields and buttons remain visible.
- Support SINUMERIK rotary-only and mixed XYZ/ABC rapid SUPA blocks on configured profiles. Machine rotary targets remain absolute under G91; reject missing/incompatible profiles even for unchanged zero targets.
- Persist sandbox ISO G-code highlighting through Options instead of only switching the editor temporarily. Seed all six reference turning tools in the isolated library, including T0505 P2 ID grooving and T0606 P6 internal threading; verify that G76 enlarges the bore without damaging the outside stock contour.
- Correct sandbox setup order to New, mode/profile, WCS, then Open. Set turning G28 Home to displayed X150/Z10 and test6 milling Home to X0/Z100. Enable ISO G-Code highlighting after the first Open and exercise real Play/timer advancement before stage transitions; explicitly report unavailable playback for the rejected impeller program.
- Trigger File → New before every sandbox program and verify that the previous editor, toolpath, STL objects and stock mesh are cleared.
- Center the sandbox window on screen and enable STL edges only for test7 after undoing its section; keep test6 and the section demonstration solid.
- Correct sandbox turning stock to D130, no bore, length 55 mm, front Z=1 mm and accuracy 0.1 mm; verify the applied settings before playback.
- Add PowerShell and Bash sandbox launchers with visible demo defaults, an automated offscreen option and configurable pacing. Restore the caller's environment and preserve pytest's exit status.
- Rework the GUI sandbox into one deterministic four-program scenario, shared by offscreen pytest and paced visual demo mode. Exercise dark-theme/plot persistence, expanded FANUC export/replay, real turning stock playback/rewind and distinct STL Objects workflows (test6: Origin and Z=-100; test7: Section Y and Undo) with the existing fixtures. Keep line width unchanged, demonstrate Statistics with per-tool selection and SVG HTML export, and verify saved-library T0303 P2 geometry in the isolated sandbox. Report a timed visual summary and stdout stage results; verify complete native impeller execution and playback with its documented warnings.
- Preserve the kernel execution result when manual GUI Update fails before its first motion, while clearing the previous plot and playback state.
- Check Windows native-extension locks before build-environment synchronization. Report the blocked .pyd file and visible owning process IDs with instructions to close the application or Python session, instead of compiling all extensions before failing during replacement.
- Reject milling drilling depths above R with `INVALID_DRILLING_DEPTH`, while allowing Z equal to R. Report mixed `IF ... THEN assignment GOTO` blocks as `UNSUPPORTED_MACRO_IF`.
- Remove generated empty blocks from native drilling Full Program conversion while preserving source blank lines, comments, sequence numbering and motion-mode restoration after G80.
- Model FANUC milling G83 rapid reentry at clearance d above the previous peck depth, bounded by R. Add finite, non-negative `milling_g83_clearance` in millimetres (default 1.0 mm as a modeling assumption); update cycle paths and statistics without changing turning or native SINUMERIK pecks.
- Parse each shared execution once: the kernel passes its Program/AST to tool setup before executing motions, and the same resolved tool geometry reaches turning execution and milling compensation. Reuse AST operation hints for FANUC and SINUMERIK instead of reparsing native source during discovery; keep the Cython scanner for literal candidates and comment dimensions. Preserve cancellation/resource diagnostics and UNVERIFIED compensation status.
- Resolve program tool geometry from matching saved-library numbers before applying source/default geometry, while retaining manual Current Program overrides. Read library snapshots for GUI discovery, execution and conversion without writing SQLite. Classify native SINUMERIK CYCLE81/82/83 as DRILL and CYCLE84 as TAP from controller AST facts, including modal MCALL, cancellation and tool changes; comments and MSG text do not activate cycles. Operation type takes priority over conflicting comment type hints; comments still supply fallback dimensions.
- Remove Stock Removal's dependence on the OD/ID/Face checkboxes. These remain UI filters for available tracing orientations. Material removal follows the resolved motion and physical cutter geometry; bounded sweeps preserve separate material rings instead of removing everything on a guessed side of the contour. Fix G71 boring with the P2 tool in `PROFILE ROUGHING2`, including deterministic backward/forward playback.
- Separate radial and face-groove geometry from application filters through the Groove geometry selector; correct its Russian translations and embed the rebuilt translation catalog.
- Replace the thread preview's single wedge with `THREAD_INSERT_OUTLINE`, the supplied 15-edge insert contour with three 60-degree cutting teeth. Tool Library and the Stock Removal overlay share this silhouette and its active tracing point. P8 external tools point down; P6 internal tools point up.
- Scale the complete thread-insert silhouette only by its inscribed-circle diameter: the reference is D12, so D20 uses a factor of 20/12. EX, RC and the thread profile angle do not deform the displayed insert. Keep the radial thread-removal profile separate from the displayed body; hide the profile angle in the editor and replace the library's angle summary with the tracing orientation. Leave existing SQLite tool records unchanged.
- Update test fixtures and corpus references for `tests/fixtures/milling/fanuc` and `tests/fixtures/milling/sinumerik`, including the five-axis CAM and impeller samples. Accept both UTF-8 and Windows-1251 fixture text in corpus checks.
- Add regressions for checkbox-independent stock removal, G71 boring, thread orientation, uniform diameter scaling, fixed preview geometry and recessed insert shoulders in the 3D mesh.

## 1.9.1 - 2026-10-04

- Diagnose evaluated FANUC turning G/M codes in the kernel; unsupported position-bearing G codes fail closed and cannot produce successful expanded exports. Macro call arguments and unexecuted branches remain outside CNC-code diagnostics.
- Protect CLI JSON/HTML and GUI program/tool-list outputs against source-file collisions, including file aliases; reject colliding JSON/HTML destinations before writing. CLI read/write failures return code 2 with a diagnostic.
- Write CLI reports and GUI DXF through temporary files with atomic replacement. A failed or cancelled DXF write preserves the previous destination.
- Preserve valid legacy snippet imports when another file has invalid UTF-8, logging the skipped file and retaining the original backup. Ignore invalid encoding in legacy ordering metadata.
- Make default batch discovery independent of extension order; clarify milling unknown-position diagnostics and report missing/broken Ruff without a JSON parsing traceback.
- Add a deterministic daily GUI smoke test (`tests/gui/test_daily_workflow_smoke.py`): it opens the plate-setup program and its matching STL, saves a working copy, exports SINUMERIK ISO-M (G291) and re-executes it to confirm the same motions, shifts G54 to X100 to match a model moved to X100, inspects a Y section, hides the STL dock, edits a program tool and exports the Statistics HTML report. It stays fast on the offscreen platform and adds step pauses plus CNC assistant dialogs under `QT_QPA_PLATFORM=windows`; both FAQs document the visible run, `EASY_GCODE_SMOKE_DELAY_MS` and the GUI test limitations.
- List the accepted native CAM setup forms (bounded underscore `DEF REAL` scalars, direct scalar assignments, named tools with M6, SETMS/FNORM/COMPOF/CYCLE832, legacy 15-argument CYCLE800 ST0/R_DATA, four-argument CYCLE81, DC shortest-path with the 180-degree rejection, and unverified G41/G42 for named tools without cutter geometry) in the SINUMERIK tables of both FAQs.

## 1.9.0 - 2026-10-04

- Correct incremental drilling depth relative to R and retain the original G98 return plane across G99 holes. Reject drilling without modal Z/R or a positive feed.
- Execute conditional Macro B THEN assignments, reject unsupported IF bodies without executing embedded NC words, and correct negative FIX/FUP rounding. Preserve preprocessing diagnostics before the execution loop.
- Keep native drilling return-plane changes in FANUC conversion and avoid negative-zero coordinates and redundant mode restoration before returns.
- Include dynamically loaded PyOpenGL platform/array handlers in GUI builds and repair missing contributed PyInstaller hooks in the cached build environment.
- Support bounded three-axis SINUMERIK native → FANUC milling Full Program conversion through the same GUI/CLI/batch API. Preserve operation order, modal feed and supported arc geometry; map numeric tool offsets, D0 cancellation and SUPA positioning, apply comment style and uppercase FANUC comments. Accept empty CYCLE800 frame resets while retaining guards on actual rotary/TWP/TCP conversion.
- Convert native MCALL CYCLE81/82 to G81/G82 with validated drilling and return planes. Expand CYCLE83 locally to preserve Siemens peck degression, feed factors and reentry geometry. Convert supported metric right-hand CYCLE84 to M29/G99 G84 with feed withdrawal, dwell and rapid return to RTP. Re-execute FANUC output to verify motion paths, feeds and machine signals; cover the supplied drilling/tapping fixtures with 31 conversion regressions.
- Document FANUC Mill → SINUMERIK ISO-M/G291 and native SINUMERIK → FANUC Mill in both FAQs and documentation-site languages, distinguishing Full Program from Resolved conversion and explicitly marking SINUMERIK lathe/ISO Dialect T as unsupported.
- Allow native SINUMERIK Full Program formatting in GUI As source/native and CLI `--target-dialect sinumerik_native`: preserve native function arguments, variables, semicolon comments, modal and multi-axis state while applying numbering and address formatting. Keep FANUC-to-native Full Program conversion prohibited.
- Replace the Statistics dialog's continuous text with HTML measurement tables and a tool selector. Export the same aggregate report, including all tool sections and current units, from GUI Export HTML or CLI `analyze --html`. Exported HTML includes static XY/XZ toolpath SVGs; NC source is not embedded. Batch analysis can generate per-file HTML reports through the single-file API.
- Preserve analytical circles when applying roughing allowances. G71 Type I follows the contour to the previous depth boundary and retains G2/G3 arcs instead of replacing them with sampled lines. Pass the configured tool table into cycle expansion and use its nose radius/orientation for roughing; correct the internal diameter-I conversion after compensation. Verify all 16 CAM-expanded roughing arc endpoints, centers and radii within 0.002 mm.
- Calculate turning R corner-fillet tangent points in physical radius X/Z, then convert X back to diameter coordinates. Add quarter-circle, fixture tangency and sampled-radius regressions, plus explicit G2/G3 minor/major arc checks.
- Add the missing R retract after the final G72 allowance-contour pass, before the Z/X return.
- Correct G71 final contour return: retract by R, return along Z, then return X to the saved cycle start. Preserve the radial/diameter retract convention for OD roughing and boring.
- Implement native G93 inverse-time feed (1/F minutes per cutting motion), including rotary TCP timing. Separate G70/G71 length units from G700/G710 length/feed units; retain modal numeric F on unit changes. Native resolved export preserves G93 without feed scaling; other NC targets reject it.
- Accept G505–G599, G601, G641/G642/G645, ORI*, TRANS/AROT, FGROUP/FL/FGREF, SPOS, CUT3D* and listed motion-control words with unverified warnings. Their machine effects are not simulated and resolved NC export rejects unverified geometry. G4 S dwell is warning-only; G4 F retains seconds semantics.
- Parse native DIAMON/DIAMOF/DIAM90 with warnings while retaining DIAMOF coordinate semantics. Parse CHF/CHR/RND/RNDM/FRC/FRCM as warning-only metadata without contour or feed changes; resolved NC export rejects these unmodeled commands.
- Support native X/Y/Z=IC(...) incremental positioning and empty MSG(); add the guide example covering CR radius arcs, modal drilling and SUPA. Native CR syntax requires an MPF/SPF source document.
- Accept native G60 exact-stop metadata and G500 modal work-offset deactivation with coordinate rebasing. G500 defaults to zero; API wcs_offsets[500] supports translation. OEM base-frame rotations/scaling and acceleration dynamics remain outside the model.
- Verified CLI/kernel subset; OEM machine retract trajectories remain unmodeled. Multi-axis controller conversion stays fail-closed.
- Updated both documentation-site SINUMERIK tables with incremental IJK / explicit AC centers, native CAM setup, DC, legacy CYCLE800 and ignored CYCLE832.
- Execute the supplied 5232-block five-axis sample through M30: support bounded DEF REAL variables, named tools, DC rotary targets, legacy CYCLE800 setup and short CYCLE81 calls.
- Preserve TRAORI when D0/D1 selects a cutting edge; allow explicit SUPA machine positioning with rotary axes.
- Ignore CYCLE832 without geometry or display events, as requested.
- Correct native IJK to incremental centers; support explicit AC centers and emit AC syntax for absolute native conversion output.
- Removed the obsolete GUI-wide MPF/SPF rotary lock. Native CYCLE800/TRAORI can use the selected AC/BC profile through Settings or Options; opening documents preserves selection while kernel capability checks remain authoritative.
- Macro B AND/OR now use explicit integer bitwise semantics, consistent with XOR.
- The expression evaluator rejects Pow, nonnumeric constants and Python containers; expression size/depth/node budgets and floating-point constants bound evaluation.
- CLI analysis no longer eagerly imports ezdxf; DXF loading failures are controlled export errors only when the DXF backend is used.
- A shared native gateway caches extension availability and import reasons; frozen releases reject missing extensions. Both build scripts explicitly collect the dynamically loaded parser, discovery and executor extensions.
- CR-only/uncommon line separators and oversized literal words use the Python reference frontend instead of publishing a divergent native Program graph.
- Macro B LN/EXP, with domain/overflow diagnostics; BIN/BCD/ADP remain unsupported.
- Internal context-local parser statistics expose actual total/native/fallback blocks.
- Native CYCLE800 static frames use Siemens axis-order matrices, common TWP solver/rebasing, additive frames and active-frame resets on angled AC/BC tables. FR0/1/2 are recorded as logical retract requests, without OEM trajectories.
- Native IC rotary increments accept numeric/direct R values independently of G90/G91.
- Native SINUMERIK TRAORI/TRAFOOF reuse the common angled AC/BC table TCP state, with numeric configured rotary addresses and direct R references.
- Common TCP G2/G3 motions accept rotary interpolation in FANUC and SINUMERIK while retaining analytical Cartesian geometry and start/end tool orientation metadata.
- Active tilted-frame/TCP state prevents ambiguous G290/G291 transitions.
- Corrected the separate tool-discovery, parser/AST, kernel and ExecutionResult pipeline.
- Documented source/native fallback policy and frozen-release requirements.
- Updated the English/Russian controller tables with the bounded CLI/kernel TCP subset and the remaining fail-closed controller/export limitations.

## 1.8.1 - 2026-10-02

- Redesigned the bilingual landing page with separate language controls, sticky section navigation, visible impeller/STL playback GIFs, expanded feature descriptions, a 1.0.0-to-1.8.0 comparison and a full resource footer.
- Consolidated screenshots and animations under docs/assets/ and moved sample STL models to the root stl/ directory; updated README links and rendering fixture paths.
- Added an English/Russian static project landing page under docs/, with shared CSS, existing screenshots, release/documentation links and explicit SINUMERIK limits. Includes GitHub Pages branch publishing instructions without a framework or custom workflow.
- Added a bounded native SINUMERIK R-parameter subset: finite numeric assignments and R references in F/S/XYZ/IJK, CR, TURN and supported cycle parameters. Siemens state is separate from FANUC Macro B and resets per execution; MCALL parameters are revalidated at each hole. Undefined parameters, arithmetic, arrays, system variables and Siemens control flow fail closed.
- Added native TURN=0..999 as additional complete revolutions on one analytical arc/helix, including all three planes. Rendering, playback and statistics consume the total sweep; DXF preserves multiple passes as a sampled polyline. FANUC/ISO trace exporters subdivide only at serialization, while the native target preserves TURN.
- Added Resolved Program Conversion between fanuc_mill, sinumerik_iso and sinumerik_native through ExecutionResult, exposed in CLI (--mode resolved), batch-export and the GUI's Expanded Execution target selector. Outputs use physical XYZ coordinates in a zero-offset frame, resolved cycles/variables, tool/spindle/coolant controls, dwell and tapping reversal. Native dwell uses standalone G4 F seconds without changing modal feed. Full Program remains source-preserving for the proven FANUC/ISO-M subset; sinumerik840d remains a compatible ISO-M alias.
- Updated the English/Russian references, native target translation and the release version to 1.8.1. Added dialect-matrix replay coverage and R/TURN downstream regressions; milling material-removal simulation remains outside the existing turning stock model.

## 1.8.0 - 2026-10-02

- Added native MCALL CYCLE84 single-pass metric right-hand tapping for the actual CAM 24-parameter call and compatible shortened numeric calls. Derives feed from explicit pitch and spindle rpm, feeds back to RFP+SDIS, then rapids to RTP using shared cycle geometry; emits rigid-tapping, synchronization, reversal and optional dwell signals. Rejects unmodeled deep tapping, thread tables, spindle orientation, unequal/changed speeds and other unsupported modes. Added a paired FANUC G84 fixture and native trace replay coverage.
- Closed SINUMERIK rotary bypass in native and G291 ISO-M execution independently of GUI/profile selection. Resolved native and ISO-M incremental IJK arc centers, with explicit native I=AC/J=AC/K=AC absolute centers per executed motion, including mixed G290/G291 programs and work offsets; retained FANUC arc configuration.
- Added immutable source_dialect execution/report metadata and structured unsupported SINUMERIK G/M diagnostic aggregation. Added canonical native AST facts and declaration nodes, eliminated the discarded first AST during MPF/SPF parsing, and enabled the existing Cython modal-position loop for contiguous literal position runs after per-block Python capability validation. Controller-specific syntax and mode switches stop only the current run; acceleration resumes after reference execution and native cycle cancellation. Added complete accelerated/reference parity tests around metadata, cycles, rejection and mixed G290/G291 arcs, plus large-program SINUMERIK/FANUC speed guards.
- Fixed partially translated Russian About dialog: localized runtime version and description, updated the controller summary, and regenerated the translation catalog and embedded resources.
- Forced Rotary kinematics = None for SINUMERIK MPF/SPF documents and disabled other GUI profiles, restoring the previous selection for FANUC/new documents without overwriting saved preferences. Clarified the CAM toolpath visualization scope, exclusion of the complex Siemens macro language, and current lack of SDI subprogram execution.
- Added a bounded SINUMERIK 840D native three-axis milling interpreter. MPF/SPF starts in native mode, with standalone G290/G291 switching and controller capability checks. Native support includes CR arcs, G710, G64/MSG/WORKPIECE metadata, modeled D0/D1, cutter compensation and SUPA machine-coordinate moves.
- Added modal MCALL CYCLE81/82/83 drilling with numeric parameters, safety/return planes and modeled variable pecks. Bare MCALL cancels drilling; empty CYCLE800() is accepted without an active rotary frame. Native trace export to FANUC is verified by geometry replay; native Full Program conversion remains unsupported.
- Consolidated SINUMERIK contour and cycle regression pairs in the main milling fixture directory. Documented current three-axis kinematics and planned full CYCLE800 and TRAORI/TRAFOOF support in the README and both FAQs.
- Made the GUI arc-center choices mutually exclusive when opening programs.
- Refactored controller policy into a shared runtime capability gate before expression evaluation and dispatch. Preserved native source syntax in parsed blocks and execution facts while sharing the existing geometry emitter; unsupported native operations fail before side effects.
- Corrected native trace serialization for modal rapid moves and SUPA machine-zero positioning. Restricted Full Program conversion to FANUC / SINUMERIK ISO-M (G291); documented that the GUI has no native SINUMERIK export target and that resolved native trace export is available through CLI.
- Updated English and Russian documentation, clarified MPF/SPF container detection, and regenerated embedded FAQ resources. Bumped the release version to 1.8.0 for the expanded controller support and kernel restructuring.
- Split milling tool length into `fluteLength` and `bodyLength`, with a derived read-only length to holder. Updated validation, metric/inch editing, SQLite/JSON/CSV persistence and previews; retained unsplit legacy records without guessing their partition. Face/slot head height uses flute length, and tapered cutters have a cylindrical non-cutting body. Turning tools retain their existing model.
- Distinguished cutting and non-cutting milling parts by material: gold/gray in the library and yellow with a theme-contrasting body in 3D. Migrated standard blue tool colors to gold while preserving custom cutting colors.
- Removed the kernel's Qt settings dependency through shared per-user paths and stopped changing process-global GC state during parsing/execution.
- Captured effective rotary profile definitions and SHA-256 fingerprints in immutable execution results and CLI/batch JSON/CSV reports.
- Made parsed blocks authoritative for equivalent native/Python AST builders, rejected inconsistent ASTs, and froze label-map copies. Accelerated Block-to-AST construction in Cython, built label maps in one pass, bounded immutable word caching, and avoided duplicate AST construction on the trusted parser path. Added relative performance guards without disabling GC.
- Restored editing of damaged rotary profile overrides using built-in profiles, with an exact-byte backup before replacement.
- Fixed SINUMERIK ISO-M conversion to preserve G43/H and allow XYZ-only programs with selected rotary profiles. Actual rotary/TCP/TWP programs remain unsupported. Program numbers become comments and standalone percent delimiters are removed; GUI header formatting precedes conversion.
- Simplified execution and cutter-compensation state machines, tightened complexity ceilings, and moved application imports off historical aliases while retaining external compatibility.

## 1.7.2 - 2026-10-01

- Fixed G53.1 table indexing after G68.2: retain machine XYZ while rotating the displayed tip, then rebase into the tilted plane. The first XY-only approach preserves retracted clearance instead of starting near the WCS centre. Added cube approach and rendered-segment regressions for both angled AC/BC tables.
- Added SINUMERIK 840D MPF/SPF source detection and G290/G291 mode handling. G291 ISO Dialect M runs through the milling kernel with one integer-code whitelist, modeled unit aliases and `G54 P1..P48` work offsets; native Siemens execution, SINUMERIK ISO-T, Macro B flow and unsupported ISO functions stop with diagnostics.
- Added MPF/SPF support to GUI file filters and batch scanning. Content-aware SINUMERIK detection is shared by GUI and CLI; ordinary FANUC code in an MPF/SPF file stays in FANUC mode.
- Allowed ordinary G91 incremental positioning in SINUMERIK ISO-M and applied dialect modal state once in the shared milling kernel. Restricted G68 to its standalone active-plane 2D form without extra words or I/J/K; only G68 while G91 is active is rejected. G69 remains supported.
- Made Full Program conversion preserve source blocks while adding or removing a standalone G291 switch. Conversion validates target motion geometry and machine signals, and rejects unverified cutter compensation for a SINUMERIK target. Expanded Execution is not a dialect-conversion mode. Added CLI and batch full-program conversion.
- Restricted SINUMERIK ISO export to the verified three-axis subset. Rotary 4-axis and 5-axis/TCP/TWP conversions fail before NC is written in core, CLI, batch and GUI paths; removed automatic `G43.4` to `TRAORI` conversion and FANUC-surrogate validation. FANUC multi-axis analysis remains supported; selected 4/5-axis profiles also block SINUMERIK export for XYZ-only source. G28/G53 reference returns use the current rotary frame instead of an implicit ABC=0 frame; preserve ABC and trace continuity with TCP active or after G49. Added rotary-frame retract regressions, including B180 returning toward negative global Z.
- Restored indexed table XYZ retention, including five-axis profiles with TCP off, so approaches after G28/G53 start on the current table side. Reference Z returns crossing the WCS centre plane stop execution. Multi-axis reference returns may end a trace run without a connector to the next indexed approach; three-axis continuity remains required.
- Restricted SINUMERIK dialect conversion to Full Program mode; batch conversion writes target `.mpf` files.

## 1.7.1 - 2026-09-30

- Added a bilingual prompt to reload the open document after another program changes it on disk. Declining keeps editor changes; accepting reloads the file and warns before discarding unsaved edits.
- Added `.ptp` to the GUI Open/Save file filters. When UTF-8 decoding fails on Open, the editor tries Windows-1251 and preserves the detected encoding on Save.
- Added `G68.2` tilted working planes and `G53.1` table-axis indexing for `fanuc_mill` with the enabled angled AC/BC table profiles. The physical tool axis is solved against the selected profile; programs without a supported profile or with an unreachable orientation stop explicitly. Included vertical arcs, DXF geometry, machine-reference bypass, cube golden tests, and guarded NC export.
- Added continuous five-axis `G43.4` TCP motion for the angled AC and BC table profiles. TCP activation and rotary indexing preserve the current physical point; `G53 Z0` and `G91 G28 Z0` return to the configured home Z. Added a corpus-wide FANUC milling trace continuity regression check and the `impeller.ptp` / `impeller2.ptp` fixtures.
- Added the tapered ball mill (`TAPER_BALL_MILL`) to milling tool definitions, dimension validation, discovery and preview geometry.

- Added milling `M19` spindle-orientation and `M29` rigid-tapping preparation signals. An `S` word on an `M19` block is recorded as an orientation angle without replacing spindle RPM; `M29 S...` sets RPM, marks following `G84` cycles as rigid tapping, and `G80` clears that state.
- Added regression checks for `M19` orientation, `M29` with `G84` in `G95` and `G94` feed modes, and cancellation of rigid-tapping preparation by `G80`.
- Expanded both FAQs with complete tables of recognized milling G and M functions, clarified Type A/Type B turning-cycle codes and GUI resource limits, and revised the Russian terminology and export explanations.

## 1.7.0 - 2026-09-29

- Corrected physical milling views for horizontal and vertical spindle profiles, including camera orientation and restoring the selected view after changing kinematics.
- Fixed toolpath segments disappearing during middle-button orbit by refreshing orthographic camera clipping after rotation.
- Show the active 3D/Top/Front/Left view as a checked, mutually exclusive toolbar action; add visible theme-aware hover and pressed states to the main toolbars.
- Enable Save only when the editor has unsaved changes, and restore its disabled state after saving or opening a file.
- Add action icons to STL Objects controls, hide the selected object's pivot marker with the panel, and log load, delete, transform, array and section timings.
- Fixed STL section cap winding for all three axes, including Y-plane handedness; a cut coincident with an outer mesh face now retains that face instead of opening the shell.
- Triangulate section caps with nested contours as polygons with holes, preserving hollow regions in tubes and enclosed cavities.
- Replaced the section-cap Python ear-clipping and manual hole bridging with `mapbox-earcut`; preserve holes and disconnected contours, restore collinear boundary vertices for watertight caps, and keep cap normals aligned with the selected side. On `stl/test4.stl` (14,522 triangles, midplane cuts), `clip_mesh` measured X 345 ms, Y 396 ms and Z 350 ms, down from 2,577/18,906/3,651 ms.
- Keep the active section mesh in the plot after `loadPlot()`, and refresh both the visible cut and hidden source mesh when STL color or wireframe settings change.
- Preserve STL undo history when importing after Clear STL or deleting the final object.
- Reject cumulative STL scales that overflow float32 coordinates, collapse non-degenerate faces, or invalidate an originally closed mesh; report rejected GUI scaling in the status bar.
- Added section-cap regression coverage for convex and concave contours, holes, disconnected outer contours, large polygon-with-hole earcut usage, X/Y/Z orientation, both kept sides and watertight results; retain coverage for face-coincident cuts, repeated scaling, plot reloads, appearance refresh and import/clear history.

## 1.6.9 - 2026-09-29

- Switched the milling 3D camera to an orthographic CAD projection and kept it orthographic while orbiting from fixed views, so apparent feature size does not change with depth.
- Refined the STL Objects panel with a dark-theme border, copyable statistics, visible base-point coordinates and a plot marker. Mesh measurements now account for float32 STL coordinate precision, and Section displays clipped 3D geometry with section caps and supports Clear/Undo.
- Completed Russian localization of the STL Objects panel, compacted the operation pages, added Apply/Clear section controls, shortened array and positioning actions, renamed the minimum bounding-box base point, and removed the forced panel minimum width. Updated both FAQs and the README guidance.
- Raised the default automatic-refresh segment and generated-motion limits to the QSpinBox upper bound (`2,147,483,647`); automatic refresh no longer applies a separate 20,000-point cap.
- Updated STL section/statistics golden expectations for the current `test4.stl` asset and kept offscreen GUI tests from painting the OpenGL view when they only exercise editor actions or panel widgets.
- Added a persistent Recent STL submenu after Clear STL in the File menu.
- Replaced raster plot snapshots in Print with page-fitted vector toolpath rendering; all motions print regardless of playback position, with distinct rapid and cutting styles.
- Removed the page heading from Print and added Plot settings for rapid visibility, rapid dashes, and colors by tool for both rapid and cutting moves. The settings apply to the 3D view and printed output and have Russian translations.
- Matched on-screen rapid dashes to the short dash spacing used by Print at plot build and explicit view changes. Camera navigation now draws the resident VBO without rebuilding dash geometry on every frame.
- Made Plot options more compact with paired checkboxes, playback speed last, and a shorter Options dialog.
- Kept the milling `PROGRAM_START` event when the first block is eligible for native acceleration, and expanded native/Python trace parity checks across modal transitions.
- A damaged user `rotary_profiles.json` no longer prevents the GUI from opening: menus use the installed profiles while strict kernel calls still report the invalid override.
- Matched recent-file and save-path casing to the host platform, and moved restored windows back onto an available screen.
- Solid STL overlays now write depth before the toolpath is drawn; trajectory segments behind the model are hidden. The plot requests a 24-bit depth buffer.
- G71 now reports empty profiles and zero pass depth instead of producing an empty cycle. G72 Type II accepts repeated endpoint crossings on a closed contour while continuing to reject genuinely disjoint facing spans.
- Consolidated simple Plot, Stock, CNC, Editor, General and Export preferences into shared load/save specifications with defaults, types and applicable bounds. Simplified turning-cycle, execution and tool-library code without changing its supported controller scope.
- Delayed FAQ search while typing, retained immediate navigation, removed unused GUI compatibility wrappers, and labeled the text toolpath duration as estimated motion time.
- Added a full Russian FAQ translation and kept the in-app FAQ content synchronized with the expanded English documentation.

## 1.6.8 - 2026-09-28

- Resolved duplicate hotkeys while loading older settings: Grid keeps its F4 default, and a conflicting legacy Fit to View F4 assignment is cleared before the Options hotkey list opens.
- Brightened the Tool List toolbar icon and simplified the Hole Calculator icon to four blue markers for clearer display at 32×32.
- Stabilized indexed milling profiles and WCS: profile edits now save atomically in the user configuration, G10 L2 after table rotation preserves machine position, and execution steps record configured A/B/C angles. Batch analysis and export accept a per-file `--kinematics-map` and report the selected profile; indexed DXF export works with a profile, while indexed full NC rejects formatting options it cannot apply.
- Added editor Uppercase/Lowercase actions with Ctrl+Shift+U/Ctrl+U shortcuts and fixed Ctrl+/ and Ctrl+Shift+/ shortcuts for adding and removing `/` on selected blocks. Added plot print preview on Ctrl+P with a white print background, FAQ on F3 and Grid on F4. Existing empty FAQ/Grid shortcuts are updated once to these defaults.
- Added FANUC Lathe Type B through a source-code mapping onto the existing turning executor. Type B supports G90/G91 distance modes, its thread and canned-cycle codes, and G94/G95 feed modes. GUI settings and CLI/batch commands now select Type A or Type B; Type A remains the default.
- Consolidated the turning Type A motion and cycle code mapping and the supported-code diagnostics.
- Replaced parallel subprogram and G65 local-scope stacks with a single call-frame stack while preserving repeat and local-variable behavior.
- Split tool handling and canned-cycle dispatch into explicit turning execution stages and reduced the regular-motion call argument list.
- G72 Type II now reports ambiguous interior crossings instead of silently returning no motion. Empty profiles and zero pass depth also produce explicit errors.
- Enabled relative I/K, absolute I/K and R arc selection and auto detection for turning in the GUI and kernel. Auto detection compares turning X/I in physical radial coordinates. Expanded turning export accepts the same arc output modes as milling.
- Fixed P/Q profile motion selection when a block contains both a motion code and G40, such as `G01 G40`; the following G70 no longer fabricates an arc without I/K or R.
- Added golden trace checks for every checked-in turning fixture and regression coverage for the supplied G71 ID arc case.
- Manual Arc Type selection now overrides auto detection for the current document without changing the saved Auto Detect setting. Turning arcs report diagnostics when the selected I/K center does not fit the endpoints or Radius mode has no R word.
- Kept R-programmed P/Q arcs as R arcs through cycle expansion; synthesized internal I/K offsets no longer change with the source Arc Type. A bad I/K arc in a P/Q profile now discards the entire G71/G70 cycle group before publishing any of its motions.

## 1.6.7 - 2026-09-27

- Added deterministic indexed 3+1 milling for the verified `4ax_table_a` (vertical mill) and `4ax_table_b` (horizontal mill) profiles. Programmed G90/G91 A/B indexing transforms subsequent tool-tip trajectories, arcs and milling cycles while WCS axes remain fixed; playback rotates the tool preview.
- Corrected A/B rotation signs and repeated G28/G53 machine-axis returns after indexing. Removed false plot segments joining positions across a rotary index.
- G40/G41/G42 now calculate cutter compensation in the local working plane before the completed geometry is transformed by A/B, including arc centers and normals. Missing tools or unsupported contours produce warnings without stopping execution; unknown M-codes also remain non-blocking warnings.
- Added an `enabled` flag to every rotary profile. Only the verified table A/B/C profiles appear in the GUI; **None** is the default. Other profiles remain in the JSON catalog, disabled pending reference programs. G68.2 and 5-axis behavior are outside the verified 1.6.7 scope.
- Enabled `4ax_table_c` for the checked planar X/C program: concurrent X/C and C-only blocks map tool-tip points into fixed XY WCS. The resulting contour overlays the equivalent XY contour in `indexed_table_c.nc` within 0.05 mm at sampled endpoints.
- Disabled G41/G42 cutter compensation for `4ax_table_c`. Programs continue with the programmed, uncompensated X/C tool-tip path and an explicit warning; G40 still cancels the modal request. The correction approach in `tmp/indexed_table_c_correction.nc` is not treated as verified compensation.
- Matched CAD-style mouse navigation to CNCEditor: left drag pans, middle drag orbits around the cursor. Corrected the table B 3D/ISO camera so +Y points vertically up, +X runs upward-right and +Z downward-right; table A retains the vertical mill view.
- Fixed **New** so an accepted new-document action removes the imported STL model and disables **Clear STL**. Canceling the action preserves the model.
- Refreshed the FAQ and License dialogs with larger, resizable reading windows, clearer heading and paragraph spacing, padded code blocks, and theme-aware syntax colors for fenced examples. Preserved FAQ anchor and License links.
- Refined FAQ/License contrast: muted light-theme links, clearer headings, and continuous code-block backgrounds in both themes with a lighter dark-theme code surface. Added the CNC icon to Rotary kinematics and a blue WCS action icon for visibility in light and dark themes.
- Fixed the embedded FAQ table of contents: Qt cannot parse Markdown links nested inside the source file's HTML `<details>` block, so the dialog displays that block as a regular heading and list while the source FAQ keeps its collapsible form. Restored readable links in both themes and pale blue section headings in the dark theme.
- Refactored only the dark FAQ styling to follow the selected application theme instead of guessing from the native widget palette. Dark headings, links, and code blocks now use explicit contrasting colors, including after a live theme switch; the light FAQ styling stays unchanged.
- Added FAQ search below the document with a result count, icon buttons for Previous/Next, wraparound, Enter for the next match, and Ctrl+F focus. Search remains usable after switching the application theme.
- Updated README and FAQ and added regression checks for the A/B/C fixtures, rotation direction, G90/G91, G28/G53, local-plane compensation, camera behavior and STL cleanup. The reference NC fixtures were not changed.

## 1.6.6 - 2026-09-26

- Refactored single-file CLI export and added `batch-export` around one shared execution, validation and NC/DXF export pipeline.
- Added semantic mm/inch conversion for expanded NC and DXF, milling arc output choices, coordinate and formatting controls, and byte-identical single/batch output.
- Added mirrored directory exports with JSON/CSV manifests, input safety checks, and four Windows/Linux batch-export presets.
- Aligned single-file `analyze` with `batch`: both now use milling arc-type detection and turning unsupported-M-code diagnostics, and report matching per-file statuses and diagnostic counts.

## 1.6.5 - 2026-09-25

- Linux releases now include a versioned x64 archive with GUI and CLI executables plus a SHA-256 checksum. CI builds and smoke-tests both batch presets before publication.
- Replaced terminal JSON dumps with readable execution results for every CLI command. Batch now reports each file as it is processed, followed by final counts and report paths; detailed JSON remains available in output files.
- Added ready-to-run PowerShell and Linux shell batch presets for the bundled milling and turning fixtures. They use UTF-8, write separate reports to the system temporary directory, and run the built CLI without building or running tests. Milling batch analysis now detects Arc Type per program, with relative IJK as the fallback.
- Added recursive CLI batch analysis for turning and milling NC files, with JSON and Excel-friendly CSV reports, diagnostic counts, unsupported G/M-code summaries and selectable file extensions.
- Defined report statuses as `CLEAN`, `WARNINGS`, `ERRORS` and `NO_FILES`, with a nonzero exit code for errors or an empty scan. File read/decode failures remain per-file diagnostics; unexpected analyzer failures surface directly. Bumped the report schema to version 2.
- Unified GUI and CLI program execution through one shared setup path and the authoritative CNC kernel. Temporary tool discovery now supplies G41/G42 geometry to single-file and batch CLI runs, while GUI manual tool assignments retain priority.
- Built a separate console CLI executable alongside the windowed GUI. Windows releases publish both executables and a SHA-256 checksum list; local Windows and Linux builds write `.sha256` files beside their executables. Top-level CLI help now lists every command's arguments and defaults; packaged and source commands are documented.
- Set Python 3.13 as the minimum source runtime and aligned the lint target and lock file with the supported environments.
- Highlighted fenced command examples in the built-in FAQ with a contrasting background and padding.
- Aligned PowerShell and shell helpers: lint resource checks, release lint gates, build checksum output, test arguments and startup arguments. Updated build and release documentation.
- Verified the Ubuntu WSL shell workflow: dependency sync, Qt source generation, lint with resource checks, 933 passing tests, CLI packaging, checksums and both batch presets. Fixed first-run native build state handling and completed the turning preset.
- Made exported project ZIPs portable to Linux by using forward-slash entry paths and LF line endings for shell scripts.

## 1.6.4 - 2026-09-24

- Reworked **Options → Hotkeys** into a table covering named menu commands, including nested commands. A separate assignment dialog offers modifier checkboxes and a searchable key list; shortcuts persist per command, can be cleared or restored to defaults, and conflicting assignments are rejected. Default shortcuts were updated for Refresh and standard views.
- Updated toolbars: moved Refresh to View, placed View after Edit by default, added Statistics and Tool List before the CNC calculators, and added a persistent 1–5 playback-speed slider. The CNC editor mode is now a dropdown with distinct icons for ISO G-Code and Text File. Toolbar icons have configurable 32/24/16-pixel sizes, defaulting to 24 pixels.
- Added the missing Settings menu icons for Stock, Tool Library, WCS, Options and Tokens, refreshed toolbar icons and fixed Qt resource regeneration so changed icon files are embedded by the lint fix workflow.
- Updated Snippets with a smaller monospace content font, editor zoom, and icon-only management buttons. Added 16-pixel icons and concise labels/tooltips to Tool Library actions and preview controls.
- Kept Qt Designer `.ui` sources authoritative, regenerated their Python modules and Russian translations, and extended lint checks for UI formatting and generated UI, translations and resource freshness. Simplified repeated UI handlers without changing CNC behavior.

## 1.6.3 - 2026-09-23

- Fixed milling 3D camera jumps during automatic refresh after pasting or dropping G-code. Ordinary updates preserve the camera center and zoom; a newly inserted path is fitted only when it grows or moves substantially and would otherwise extend beyond the current view. Turning camera behavior is unchanged.
- Added Hole Calculator, Pocket Calculator and Snippets dialogs ported from CNCEditor, including circular/grid hole coordinates, circular/rectangular pocket G-code, helical-entry and compensation options, persistent editable snippets, insertion at the editor caret, and the original CNCEditor toolbar icons. Calculator windows are now compact/resizable with live painter-based XY previews, use a simple Insert action, place pocket-option checkboxes in the first column, and are disabled in Lathe mode; rectangular Spiral generates a real interior clearing path plus the final contour. Snippets uses a SQLite library, imports the former text-file store once without deleting it, protects unsaved edits when selection/closing changes and persists manual Up/Down ordering.

## 1.6.2 - 2026-09-23

- Added a machine-neutral cycle execution contract while preserving machine-specific expansion models. Milling canned cycles now return geometry, signals, modal updates and position updates as one atomic outcome built against temporary state; the existing turning expansion pipeline is connected through an adapter without rewriting G70-G76 semantics. Cycle implementations now live under canonical `turning/cycles` and `milling/cycles` packages, with historical import paths retained as aliases.
- Added FANUC milling `G16/G15` polar-coordinate programming with `G17/G18/G19` plane selection, absolute/incremental radius-angle commands, WCS/local-origin and current-position pole selection, canned-cycle positioning, R-format circular interpolation, coordinate-transform integration and Python/native execution parity. Turning remains unchanged.
- Added FANUC Macro B vacant-variable semantics for `#0` and omitted G65 arguments, indirect `#[expr]` assignment, and shared immutable variable snapshots that avoid duplicating unchanged macro state across execution steps.
- Fixed milling `G10` under `G91` to increment existing L2/L20 work offsets instead of silently replacing them.
- Fixed two-line turning `G76` so the packed tool-angle digits now produce FANUC single-edge flank infeed for the supported 0/29/30/55/60/80-degree set instead of being silently ignored; unsupported angles now fail explicitly.
- Expanded modal conflict validation for milling tool-length compensation, scaling and rotation plus turning spindle modes, and added an explicit `UNSUPPORTED_G72_TYPE_II_SPANS` failure for ambiguous multi-span facing profiles.
- Refactored kernel execution without intentional CNC semantic changes: milling now uses named evaluation/validation/state/flow/motion phases with a single block finalizer, while turning machine-specific operations are grouped behind one execution-semantics contract instead of a growing callback list.
- Added a standalone `Tool List` CNC function that reuses resolved per-tool statistics to produce a CIMCO-style UTF-8 text report with program/file metadata, configured tool geometry and exact per-tool Z minimums.
- Fixed turning `G53` fail-open behavior for arc modes. `G53 G2/G3` now reports `UNSUPPORTED_G53_MOTION` and skips the complete block instead of silently executing a WCS-relative arc.
- Expanded the Tokens diagnostic window into `Tokens/Macro Variables` with a read-only Macro Variables inspector driven by execution-step snapshots. The inspector follows the current logical playback position, shows only variables that actually exist at that point, includes active G65 local-variable scopes and restored caller values after M99, updates during playback/step/slider navigation without re-executing the program, and works consistently for turning and milling Python/native execution paths.
- Added a persistent CNC comment-style selector under `Options -> CNC / Execution`. Parenthesized comments remain the default, while semicolon comments can now be selected consistently for editor lexing, generated statistics and every text export mode; existing source programs using either syntax remain readable.
- Improved export failure reporting with an always-visible, copyable diagnostics field containing severity, diagnostic code, source line, explanation and the offending G-code block, so incomplete or invalid executions no longer require opening Tokens or relying on the temporary status-bar message.
- Fixed `MILL FULL PROGRAM` export so the Delimiter option is also applied to retained controller blocks such as compact `G0G91G28Z0`, producing `G0 G91 G28 Z0` consistently with generated motion blocks.
- Localized the dynamic Recent Files menu, including its empty state and clear-list action, for the Russian interface.
- Fixed the Windows complexity-check script failing in project paths containing Cyrillic characters by decoding Ruff's JSON output explicitly as UTF-8.

## 1.6.1 - 2026-09-22

- Fixed milling `G84` tapping so withdrawal from depth is emitted as synchronized feed motion instead of rapid motion.
- Added turning `G53` non-modal machine-coordinate motion while preserving the active WCS for subsequent blocks.
- Added machine-specific modal-group validation for the supported code set. Conflicting codes now produce `MODAL_GROUP_CONFLICT` and the complete block is skipped instead of silently applying the last code.
- Corrected the shared AST so milling `G90/G94` are not classified as turning cycles, and preserved `Y/J/V` plus coordinate-only modal motion blocks with Python/Cython parser parity.
- Added kernel/API support for `G54.1 P1-P99` through `extended_wcs_offsets`, and `G10 L2 P1-P6` / `G10 L20 P1-P99` runtime work-offset programming without requiring UI configuration.
- Modeled milling `G82` dwell, `G84` spindle synchronization/reversal and `G86` spindle-stop signals. The high-speed `G73` retract distance is now configurable through `milling_g73_retract_distance` instead of being hardcoded in cycle expansion.
- Fixed Lathe Mode zoom so perspective zoom no longer stalls at the intentionally near-orthographic `0.01` FOV limit. Turning zoom now changes camera distance while preserving the existing projection, orientation and visual appearance; milling 3D keeps its previous FOV-based zoom behavior.
- Made the WCS dialog vertically compact and resizable instead of enforcing the previous oversized minimum height.
- Fixed missing `QDoubleSpinBox` up/down arrows in the Windows 10 dark-theme fallback. Spin-box buttons now keep native Windows geometry while the dark compatibility style explicitly renders visible arrows; the Windows 11 native dark-style path is unchanged.
- Added regression coverage for Lathe Mode zoom behavior, preserved turning camera FOV/orientation, compact WCS sizing and Windows 10 dark-theme spin-box arrow rendering.

## 1.6.0 - 2026-09-21

- Added FANUC `G65` custom-macro calls for turning and milling: `P` target selection, `L` repetition, Type I/II address-to-`#1..#33` argument binding, four macro-local nesting levels, local-variable restoration on `M99`, and shared execution/export events. `G65` argument words are isolated from normal motion, feed, spindle, M-code and tool-selection side effects; Python/Cython parsing and tool discovery follow the same rule. `G66/G67` remain intentionally out of scope for this release.
- Removed the obsolete installation-directory `config.ini` and its first-run migration; `%APPDATA%/easy-gcode-plot/config.ini` is now the only settings file and clean-profile defaults come exclusively from code.
- Added persistent arc-sampling presets and maximum radius, minimum radius and minimum chord length controls under `Options -> CNC / Execution`; GUI trace generation now applies them per arc to reduce unnecessary render points in large programs without changing CNC execution geometry.

## 1.5.9 - 2026-09-20

- Localized every user-visible Toolpath Statistics report label for the Russian UI while preserving the existing English report text, values, units and statistics calculations.
- Fixed PyInstaller packages failing at startup with `ModuleNotFoundError: app.gcode.export` by explicitly collecting the canonical exporter package referenced through the legacy lazy module aliases.
- Added a persistent **Maximum generated motions** setting to `Options -> General`; it controls the kernel-wide generated-motion resource limit for both turning and milling executions and defaults to 200,000.
- Added a separate Cython tool-discovery scanner that performs line/comment scanning, literal T recognition, G20/G21 unit tracking and operation inference in one native pass while preserving the existing Python `refresh_setup()` orchestration and scanner fallback.
- Made debounced editor Auto Update non-modal so typing remains usable during recalculation; edits made during an active refresh cancel the stale run, queue another refresh and prevent stale results from replacing the current plot.
- Added a Cython native parser that accepts the complete G-code source in one call, scans lines, comments, words, numeric values, labels and flow constructs in compiled code, and produces the existing `Program`, `Block`, token and AST object model without changing CNC semantics.
- Added a Cython native milling executor for contiguous ordinary literal/modal blocks, eliminating per-line Python/native transitions while retaining the existing Python interpreter for Macro B, cycles, transforms and other complex behavior.
- Kept authoritative Python fallbacks for unsupported or complex input and for source environments where native extensions have not been built; cancellation checkpoints remain active in both execution paths.
- Fused ordinary parsing and AST construction, added faster literal-word evaluation and reduced repeated scans and temporary allocations during program indexing and tool discovery.
- Reduced interpreter and post-processing overhead by avoiding unchanged dataclass replacements, empty signal/flow allocations and unnecessary coordinate-transform work, and by rebuilding emitted-motion counts only when they change.
- Added scoped cyclic-GC deferral around construction and execution of the large, predominantly acyclic CNC object graph, restoring the caller's previous GC state on every exit path.
- Added slotted high-volume frontend and execution dataclasses to reduce allocation size and attribute-access overhead without changing equality, immutability or public result types.
- Changed the GUI execution path to omit the optional full instruction list when it is not consumed, while preserving instructions for API and CLI callers that request them.
- Consolidated tool discovery so source parsing results are reused instead of performing redundant full-file passes.
- Improved the 77 MB / 2,577,485-line FANUC milling reference workload from approximately 110.7 seconds to 25.3 seconds at the 200,000-motion limit (about 4.37x overall on the reference machine).
- Verified native/Python parity across every block and AST node in the reference file, label indexes and complete limited execution results, including motions, steps, diagnostics, events, signals and final state.
- Added native-acceleration regression tests comparing the compiled parser and milling loop with their Python fallbacks; unbuilt source checkouts skip only the native-specific tests.
- Added Cython to the PEP 517 build requirements and configured setuptools to compile `_native_parser.pyx` and `_native_executor.pyx` into platform-specific `.pyd`/`.so` modules.
- Kept generated Cython `.c`, `.pyd` and `.so` artifacts out of version control; clean wheel builds start from the tracked `.pyx` sources and include both compiled extensions.
- Added matching `build-native.ps1` and `build-native.sh` helpers that maintain a persistent `.venv-build`, rebuild native extensions when build inputs change, support an explicit refresh and verify both extension imports.
- Made the PowerShell and shell PyInstaller workflows reuse the isolated `.venv-build`, validate native acceleration before packaging and skip dependency synchronization when the locked build inputs are unchanged.
- Documented compiler prerequisites, native build verification, source-tree startup and the behavior of prebuilt Windows releases.

## 1.5.8 - 2026-09-20

- Added persistent **Autodetect Arc Type** under `Settings -> Options -> CNC / Execution` for milling. Execution inspects the already parsed unresolved motion stream, skips R-only arcs while detecting, compares relative-IJK and absolute-center radius consistency against the configured arc tolerance, fixes one effective IJK mode for the whole run and falls back to the manually selected Arc Type when the program remains ambiguous. Turning and Arc Output export semantics are unchanged.
- Added persistent **Ignore Block Skip** under `Settings -> Options -> CNC / Execution`. When enabled, leading `/` blocks are excluded consistently from turning and milling execution, Macro B side effects and Expanded Execution export without modifying the source file; the existing execute-by-default behavior remains the default.
- Fixed the cancellable CNC execution dialog so it remains visible through actual plot publication instead of closing when only the worker portion finishes. Cancel now uses the same cooperative token during tool discovery, streaming source parsing, AST/index construction, kernel execution, trace sampling and GUI geometry publication.
- Removed whole-file `splitlines()` copies from kernel parsing and tool discovery, added bounded cancellation checkpoints to the previously non-cancellable passes and verified responsive cancellation with a 77 MB / 2.57 million-line milling program.
- Fixed the execution dialog's dark-theme client area and first-frame painting so Windows no longer exposes a blank white interior before the dialog contents are rendered.
- Improved the execution status bar with spacing between fields, explicit `Errors`/`Warnings` labels, diagnostic detail tooltips and compact second-based timing for long executions.
- Made the built-in FAQ a normal resizable/maximizable window, added document-aware heading/paragraph spacing without modifying `FAQ.md`, preserved anchor navigation and made the packaged `LICENSE.md` link open correctly.
- Reduced avoidable Turning Stock Removal overlay work and removed noisy slow-frame warnings when no actionable slowdown is present.
- Refactored `app/gcode/kernel` without adding new G-code functionality or intentionally changing CNC execution semantics; the change consolidates common mechanics left from the historically separate turning and milling implementations.
- Added shared machine/runtime state primitives for unit mode, active WCS/tool, feed mode/feed and spindle state, and removed the duplicate turning cycle-state synchronization path.
- Consolidated common program execution plumbing for Macro B evaluation/control flow, block evaluation/classification, execution guard/program counter, subprogram call stack and M98/M99/M2/M30 flow events.
- Consolidated turning and milling reference-return path generation through a machine-neutral two-stage home-return helper.
- Consolidated WCS rebasing helpers and grouped milling G52/G68/G69/G51/G50 modal transform state behind one `TransformState` while preserving the existing transform semantics.
- Consolidated axial drilling/peck/retract/return mechanics in shared runtime helpers and reused them from milling drilling cycles and turning peck/tapping paths. Existing milling G73/G81-G86 geometry is preserved; this refactor does not add G87-G89 or new dwell/spindle cycle semantics.
- Reduced duplicated turning-cycle expansion code across G71/G72/G73 profile preparation, G74/G75 pecking, G83/G84 drilling/tapping state handling and G90/G92/G94 rectangular-cycle mechanics.
- Reduced duplicated geometry/profile clipping helpers and repeated milling execution-step/event bookkeeping.
- Kept threading, drilling, turning and milling machine-specific semantics in their existing domains while moving only shared mechanics into common runtime helpers, preparing the kernel for later G65 and G66/G67 work.
- Fixed milling G41/G42 compensation for planar full-circle G2/G3 motions so the compensated path remains active through the final circle until the following G40 exit; added a regression using `tests/fixtures/milling/macro_boss_milling.nc`.
- Fixed the Russian Stock dialog unit suffix regression: the `" mm"` source now translates to `" мм"` (without quotes), and the compiled catalog is re-embedded into the Qt resource so the translation is actually applied at runtime.
- `generate-translations.ps1`/`generate-translations.sh` now refresh the generated Qt resource (`files_res.py`) after compiling `.qm` files, so running only the translation step can no longer leave a stale embedded catalog.
- Localized standard `QDialogButtonBox` controls (`OK`, `Cancel`, `Close`, ...) centrally by installing Qt's own `qtbase_<language>.qm` catalog alongside the application translator instead of adding per-dialog `setText()` calls.
- Restored the `Inches` display switch in the Turning and Milling tool editors and added regression coverage that it only changes the displayed units while stored geometry stays metric.
- Fixed dark-theme spin-box controls: the legacy Windows dark fallback now applies a shared `QAbstractSpinBox` stylesheet so the frame and up/down arrows stay readable instead of rendering black on the dark background.

## 1.5.7 - 2026-09-18

- Refactored the CNC core without changing existing execution semantics: the former flat `app/gcode/kernel/` modules are now grouped into `api/`, `frontend/`, `geometry/`, `lathe_cycles/`, `compensation/`, `runtime/` and `milling/` packages.
- Split the largest kernel modules into focused files for cycle expansion, interpreter dispatch/execution, profile geometry, milling state/motion/drilling and compensation geometry.
- Split G-code/DXF export into the `app/gcode/export/` package while keeping export behavior based on the authoritative `ExecutionResult`/resolved trace.
- Added milling `G73` high-speed peck drilling with short intermediate retracts while preserving existing `G83` full-retract behavior.
- Added a reusable milling coordinate-transform layer and FANUC-style `G52` local coordinate-system shifts. `G52` changes transform state without moving the tool.
- Added milling `G68`/`G69` coordinate rotation around a programmed center. The control blocks do not create motion, and the active rotation is applied to subsequent endpoints and I/J/K arc vectors.
- Added milling `G51`/`G50` coordinate scaling. `G51` supports a uniform `P` factor or per-axis `I/J/K` factors around the programmed center, while `G50` cancels scaling; neither control block creates a motion segment.
- Fixed milling `M98`/`M99` execution so a subprogram inherits the caller's current position and complete modal/coordinate-transform state, returns to the caller without synthetic connector motion, and resumes execution with the resulting state.
- Fixed main-program completion when subprogram definitions follow `M30`, allowing the authoritative execution result to remain valid and complete for UI and DXF export.
- Fixed milling `G41`/`G42` contour construction across line/arc junctions, corners and `G40` exit so compensated primitives remain continuously joined without artificial diagonals between source and compensated geometry.
- Added an end-to-end `flange_plate_benchmark.nc` integration test covering subprogram execution, compensated-contour continuity and non-empty DXF generation through the production execution path.
- Fixed lathe Auto Stock so the calculated Z bounds come from the actual toolpath instead of incorrectly exposing the default `2 mm` Z allowance for programs located entirely in positive Z.
- Renamed the turning-only cycle implementation package to `lathe_cycles/`, updated its consumers, and added regression checks for the canonical package layout and representative turning/milling execution paths.
- Remapped the complexity baseline to the new module paths without relaxing the recorded complexity thresholds.

## 1.5.6 - 2026-09-17

- Added a Russian user interface. The language is selected in `Settings -> Options -> General` and applied after restarting the application; English technical logging, kernel diagnostics and G-code comments are intentionally unchanged.
- Added a `Light`/`Dark` theme selector next to the language option. The application uses Qt's native color-scheme support with a palette fallback, plus editor and plot colors; standard plot colors follow the active theme while user-customized plot colors are preserved.
- Light and Dark use the native platform `QStyle` where it supports the requested scheme. Windows 11 keeps Qt's native Windows 11 style; Windows 10 falls back from the legacy `windowsvista` style to the palette-aware `windows` style in Dark mode because the native Vista theme engine can otherwise leave menus, toolbars and input controls light. QScintilla and plot colors remain theme-aware, and switching between Text and ISO G-code still reapplies the editor chrome.
- Added Qt translation generation (`pyside6-lupdate`/`pyside6-lrelease`) to the Qt codegen pipeline: `translations/app_ru.ts` is the tracked source and the compiled `app_ru.qm` is embedded in the Qt resources as a generated artifact.
- Recolored the `Fit to View` toolbar icon so it stays visible on the dark theme.
- Restored fast NC file opening by removing the 1.5.4 forced synchronous Auto Update from `Open`; the previous plot is cleared immediately, normal Auto Update settings are respected, and long calculations use delayed execution feedback while short calculations avoid a modal flash.
- Moved tool discovery plus trace sampling into the worker path so slow calculations are covered by the delayed cancellable execution dialog without reintroducing a status-bar progress bar.
- Added an `inches` display switch to Stock and WCS and to both Turning and Milling Tool Library add/edit forms; stored geometry and WCS values remain millimetres.
- Avoided unnecessary re-execution before Export when the current trace is already valid, moved export generation/writing through the delayed cancellable execution dialog, and kept total export timing in the status bar.
- Fixed Expanded Execution formatting so Delimiter always inserts a space after sequence numbers, and fixed G91 export so I/J/K are emitted incrementally even when Absolute IJK is selected.
- Reorganized the `tests/` tree into domain subpackages (`core`, `dialects`, `stock`, `tooling`, `export`, `gui`, `render`, `meta`) and split the oversized stock-removal and CLI/exporter suites into focused modules; shared fixtures and helper imports now resolve from the `tests` root.
- Grouped the Qt Designer sources and their generated modules under `app/ui/generated/main`, `app/ui/generated/dialogs` and `app/ui/generated/editors`, and updated the Windows and shell generation scripts to recurse and mirror the category directories.
- Updated locked dependencies: numpy 2.5.3, fonttools 4.65.0, platformdirs 4.11.9, pyinstaller 6.22.3 and ruff 0.16.8.
- Split `app/ui/` into `dialogs/`, `plot/`, `windows/` and `support/` packages, rewrote all application and test imports plus the Designer custom-widget headers, and remapped the complexity baseline to the new module paths.
- Made the Tokens window a standard resizable window with minimize and maximize controls and removed its in-content Close button.
- Fixed the FAQ table of contents in the Help window by resolving `#section` links to the matching document headings.

## 1.5.4 - 2026-09-16

- Unified turning and milling tool management under one `Tool Library` window with separate Milling/Turning tabs and explicit `Current Program` versus persistent `Saved Library` areas.
- Kept discovered T selections temporary per open program; inferred geometry from inline, named-tool and nearby operation comments, preserved descriptions, and used standard geometry when no type was recognized. New/Open resets temporary program assignments without modifying `tools.db`.
- Added explicit assignment/copy operations between Current Program and Saved Library while preserving the NC program's T number.
- Changed Tool Library export to write the complete Saved Library of the active machine kind as JSON or CSV instead of exporting only the selected tool.
- Moved code-built dialogs and tool editors to Qt Designer `.ui` sources and removed the obsolete separate turning/milling tool forms and collection classes. Generated Python UI/resource modules remain build artifacts produced by the existing generation scripts.
- Normalized Designer sources to Qt 6 scoped enum names and hardened UI generation against PySide6-to-PyQt6 enum alias mismatches.
- Used standard tool geometry for unknown selections in Stock Removal and playback instead of silently leaving stock unchanged or hiding the tool.
- Staged Saved Library Add/Edit/Duplicate/Remove operations in the Tool Library window; OK commits the final state to `tools.db`, while Cancel discards the staged changes and Current Program remains temporary.
- Improved Tool Library layout and preview behavior with compact resizable defaults, borderless sections, larger table space and viewport-aware automatic Fit for selected Current Program and Saved Library tools.
- Inferred temporary Current Program fallback geometry from the active tool's operation: D10 Drill for G81-G83, D10 Tap for G84 and OD Thread for turning G32/G33/G76/G92, while retaining D10 Flat Mill and Diamond 80 OD as the general defaults and preserving explicit comment hints.
- Made Tool Library OK commit Milling and Turning changes in a single SQLite transaction, eliminating partial cross-tab saves and compensating rollback.
- Reported tool-library read failures explicitly at startup and disabled Tool Library editing instead of presenting an unreadable `tools.db` as an empty library.
- Made Linux and Windows CI regenerate Qt sources and fail on any modified or untracked generated output before tests or packaging.
- Removed the redundant status-bar progress indicator; long CNC execution now uses only the cancellable execution dialog.
- Restarted ordinary playback from the beginning when Play is pressed at the completed end of a trajectory.
- Refreshed the plot immediately when opening a new NC program, regardless of the Auto Update setting, so geometry from the previously opened file is never left on screen.
- Made Playback controls authoritative over editor-line synchronization: Play, Step Forward, Step Backward and manual trackbar movement now advance correctly through expanded Macro B execution even when multiple execution steps originate from the same source line.
- Fixed lathe Auto Stock for programs located in positive Z coordinates and separated absolute stock front position from front allowance, so opening or confirming the Stock dialog no longer shifts automatically detected stock back into negative Z.
- Fixed G70 finishing so the cycle first approaches the profile start from the actual G70 call position instead of beginning the finish contour with a discontinuous jump.
- Renamed the automatic refresh threshold to `Auto update max points`, removed the hidden point ceiling from manual Update, and reused an already computed kernel result when an oversized automatic render is completed manually.
- Delayed the cancellable execution dialog until a calculation has run for two seconds, while keeping execution immediate; fast runs no longer flash a modal window, and the worker shutdown path no longer relies on a nested `QDialog.exec()` lifecycle that could crash Qt on Windows.
- Split the oversized GUI and dialog regression suites into focused test modules covering actions, execution, files, plotting, settings, views, export, options and turning-tool editing.

## 1.5.3 - 2026-09-14

- Replaced direction-bearing turning type identifiers with nine canonical geometry types: Diamond 80, Diamond 35, Square, Round, Triangle, Groove, Thread, Drill and Tap.
- Persisted OD, ID and Face as independent `applications` flags and routed preview, orientation, compensation and Stock Removal through canonical geometry plus application context.
- Added idempotent `tools.db` migration on load; historical records retain application meaning and geometry fields and are immediately rewritten using canonical types without duplication.
- Added a Qt-free SQLite tool library in `tools.db` as the authoritative store for turning and milling tool definitions.
- Initialized new SQLite libraries directly with the current tool schema; no intermediate legacy tool import is used.
- Added a generator for the complete auto-mode turning catalogue and made turning and milling tool-set replacement atomic.
- Added regression coverage for deterministic catalogue generation, deletion persistence, duplicate-key protection and the settings bridge.
- Added live previews, first-free-number duplication and JSON/CSV export to both tool-library dialogs.
- Added Face Mill, Slot Mill, Chamfer Mill and Tap cutters plus square, round and triangular turning inserts.
- Added a directional threading tool with Length/Diameter, E, EX and RC geometry for preview and trace playback.
- Added Diamond 80 with OD applicability and D10 Flat Mill fallback geometry when a program does not select a configured tool.
- Added Prev/Next Toolchange navigation and exposed the Edit and CNC Functions actions in the editor context menu.
- Corrected the application-specific auto tracing-point catalogue, including P1/P2/P6/P7 for Diamond 35 ID and P3/P4/P7/P8 for Diamond 35 OD.
- Corrected turning-tool geometry consistency: Triangle Insert now uses a real three-sided footprint, Round Insert uses its physical insert radius for trace-point placement, and Drill/Tap library preview reuses the shared cutter geometry used by playback and Stock Removal.
- Added pitch- and insert-driven Stock Removal profiles for synchronized G32/G33, modal G92 and G76 cutting moves; repeated OD/ID passes deepen one phase-aligned profile, radial infeed/retract moves do not create false angled faces, and G94 remains a facing cycle.
- Changed Stock sizing to preserve user-entered manual dimensions across Refresh and turning-tool edits; Reset to Auto, New and Open return Stock to program-derived automatic sizing.
- Added startup Fit to View for persisted Lathe Mode after the main window is shown, so the automatic stock outline is visible immediately.
- Consolidated tool validation under `app/tools/validation.py`, split turning/milling library dialogs out of the generic dialog module, and kept compatibility re-exports for existing callers/tests.
- Kept `tools.db` as the single authoritative turning/milling library; legacy `CNC/TOOLS_JSON` and `CNC/MILLING_TOOLS_JSON` values are not imported or written.

## 1.5.2 - 2026-09-12

- Fixed Linux shell workflow orchestration so nested `.sh` scripts are invoked through `bash` and do not depend on executable file mode in CI.
- Installed the EGL and OpenGL runtime libraries required for PyQt6 imports on clean Ubuntu CI runners.
- Made recent-file deduplication consistently case-insensitive across Windows and Linux, including migrated Windows-style paths.

## 1.5.1 - 2026-09-12

- Fixed Groove + Face Stock Removal so axial feed moves subtract only the swept cutter footprint and preserve material on both radial sides; rapid moves remain non-cutting and the generalized interval profile stays reversible during playback.
- Added P2/P3 Groove + Face orientations and used the same orientation-aware cutter polygon for the tool preview, 3D playback and Stock Removal.
- Added configurable corner radius for Groove tools in OD, ID and Face applications, with `R0` compatibility and real rounded cutter footprints for preview and material removal.
- Restored a clearly visible yellow/gold turning insert material without changing global scene lighting or the rendering of stock, STL, grid and toolpaths.
- Added groove regressions covering the supplied G74 face-grooving cycle, local material removal, rapid/feed behavior, multiple X passes, P2/P3, rounded OD/ID/Face footprints and reversible stock playback.
- Fixed disconnected stock-ring meshing so topology changes do not create overlapping faces and exact radial Groove profile breaks remain effective alongside Groove + Face cuts.
- Kept long kernel executions responsive to Qt events and made Stop, repeated Refresh and window close request cooperative cancellation.
- Removed machine-specific window geometry from the bundled legacy configuration, constrained runtime dependency ranges and added Linux CI coverage for the shell workflow.

## 1.5.0 - 2026-09-12

- Reworked playback around an indexed logical-movement map: one trackbar position now represents one actual CNC movement while retaining the complete detailed `TraceMotion`/render range for OpenGL and Stock Removal. Arc tessellation and G71 offset-profile chords no longer inflate the slider, while real cycle and Macro B expansions remain individually playable.
- Split the legacy toolbar into independent File, Edit, CNC, View and Playback toolbars backed by the same `QAction` instances as the menus; added File Type, Fit to View and View 3D controls, standardized Paste on `Ctrl+V`, centralized icon sizing, and renamed the misleading `langCombo` to `fileTypeCombo`.
- Added persistent movable-toolbar layout using `QMainWindow.saveState()`/`restoreState()`, placed all toolbars in one row by default, and added `Reset to Default` to the toolbar context menu.
- Replaced the editor-centric Length status bar with execution-aware READY/UPDATING/OK/WARNING/ERROR/STALE state, machine mode, resolved units, source position, step/motion counts, diagnostic totals, execution time and transient progress/playback position. Cursor movement no longer reads the complete document.
- Reorganized Options into Designer-owned General, Editor, CNC / Execution, Plot and Colors tabs, with clickable color swatches plus validated hex fields, bounded numeric controls, safe handling of invalid persisted values, and correct OK/Cancel/Restore Defaults semantics without runtime layout construction.
- Made the X/Y/Z axis triad use fixed unlit colors so scene lighting and camera orientation cannot turn its arrows black, without changing STL, toolpath, Stock Removal or grid rendering.
- Added `Lathe Mode` to the view toolbar immediately before Refresh, added the resource-backed STL action beside Export Data before Undo, and placed File → Import STL directly above Clear STL.
- Added the `Show Stock` checkbox to Settings → Options → Plot immediately after Show canvas grid, with live preview/cancel handling and persistent visibility state; no separate Stock toolbar action is used.
- Added Lathe UI boundary handling for diameter-based X/I and WCS X values, disabled inapplicable WCS Y controls, and made X/Y/Z/I/J/K/F indicators follow the active G20/G21 units of each executed motion.
- Added relative I/K indication derived from resolved G18 arc centers for turning R arcs and generated contour motions, fixed Lathe source I/K semantics to relative offsets, and disabled the milling-only Settings → Arc Type menu in Lathe Mode.
- Added a bottom-left Inches switch to Toolpath Statistics that converts every displayed length, speed and XYZ bound without changing physical trace data or timing.
- Fixed G71 Type I roughing to finish with a complete contour-following pass along the signed U/W allowance profile before returning to the cycle start; OD positive U and ID negative U now leave material on the correct roughing side without duplicating the nominal finish contour.
- Fixed Stock outline settings and automatically inferred bounds being refreshed after program changes and Refresh, instead of updating only after accepting the Stock dialog.
- Fixed Lathe Play to build Stock Removal from the same current effective bounds as the visible outline, and changed Stop after Stock playback to restore the fully visible trajectory with the slider at 100%.
- Expanded application diagnostics for option changes, machine/view/playback transitions, execution and plot timing, and sampled Stock Removal performance; slow Stock frames report timeline/mesh timing, profile and mesh sizes without logging every frame.
- Added a shared Qt-free X/Z turning-tool geometry layer so preview and Stock Removal use the same Diamond 80, Diamond 35 and Groove silhouettes across OD/ID applications.
- Changed Diamond 80/Diamond 35 Stock Removal for OD P3 and ID P2 from the previous nose/width approximation to sampled polygon-footprint removal along the resolved `TraceMotion`, so plate angle, main-edge angle and nose radius affect the machined profile.
- Added Groove edge-reference selection for OD P3/P4 and ID P1/P2, with application-aware defaults and valid orientation choices.
- Changed unknown or unconfigured turning tools to leave stock unchanged instead of falling back to an implicit Diamond 80 cutter; Stock Removal remains a geometric simulation and does not require spindle-running state.
- Added automatic turning-stock sizing from resolved G1/G2/G3 cutting motions, including cycle-generated motions and exact G18 arc extrema, while ignoring G0 positioning; the suggested bore remains zero by default.
- Added a lightweight stock outline to the normal Lathe Plot, included configured stock in Fit View bounds, hid the outline in milling and isolated Stock Removal playback, and restored it when returning to the normal lathe plot.
- Added Stock-dialog prefill from the current automatic stock suggestion without mutating persisted settings until OK is pressed, and refresh the suggestion after program or mode recalculation so stale dimensions are not reused.
- Added ordinary FANUC turning source-trace support for simplified `A`, `C` and corner-`R` programming, including compact blocks without spaces: `A` resolves the missing X/Z coordinate and `C`/`R` insert chamfer/fillet transitions through the same profile helper already used by cycle contours.
- Preserved G2/G3 `R` as arc-radius programming, applied source-unit scaling to direct-programming `C`/`R`, allowed a chamfer/fillet to consume an adjacent segment exactly, and rebuilt execution-step motion counts after inserted source transitions so playback and editor ownership remain aligned.
- Expanded regression coverage for OD/ID insert footprints, groove P orientations, reversible playback, unknown tools, automatic stock bounds/outline refresh, cycle-generated stock sizing, and ordinary source-trace A/C/R execution.
- Split the detailed user/developer reference from README into `FAQ.md`, added an offline Help → FAQ window below About, and embedded the FAQ in application resources for packaged builds.

## 1.4.2 - 2026-09-10

- Added turning Stock Removal playback driven by the resolved execution trace, with reversible OD/ID profiles, drilling, grooving, persistent stock dimensions and geometry-specific 3D tools for Groove, Drill, Diamond 80 (5-degree edge) and Diamond 35 (3-degree edge) across application contexts.
- Reset playback to the complete recalculated trajectory after source, mode or semantic setting changes so stale slider positions cannot hide updated geometry.
- Changed turning and milling execution to preserve trustworthy partial traces and continue after recoverable G-code, Macro B and unsupported position-changing blocks once absolute coordinates re-establish the affected axes.
- Changed invalid arc handling to skip only the unresolved motion while retaining later resolved motions.
- Separated execution traversal completeness from diagnostic success and exposed `complete` in CLI JSON output; resource limits and internal kernel failures remain terminal while preserving prior motions.
- Fixed turning G83 without Q so a new cycle does not invent or inherit peck depth, and modeled G84 tapping as a single feed stroke with return motions.
- Preserved nominal turning geometry when configured G41/G42 tool data is invalid, reporting unverified compensation instead of discarding the trace.
- Replaced modal GUI execution-error dialogs with status-bar diagnostics and preserved the existing Plot when a failed refresh produces no usable trace.
- Made Linux release creation stop immediately when lint fails.
- Refactored G-code export by output mode so Full Program, Expanded Execution and Plot Data no longer share incompatible coordinate/arc settings.
- Fixed Full Program and Expanded Execution WCS serialization by converting generated machine-space trace geometry back into the active preserved G54-G59 coordinate system without removing WCS selection.
- Fixed turning WCS arc-center conversion by applying the configured X offset in physical radial-X space.
- Fixed turning Expanded incremental output to use U/W rather than milling-style G91 with X/Z deltas.
- Fixed R arc export so resolved full circles are serialized as two exact R semicircles instead of producing an unrepresentable single R full circle or switching center representation.
- Fixed Expanded source-unit/X-mode serialization and made Plot Data ignore stale incremental settings.
- Increased generated export-geometry precision to six decimal places so inch output combined with nonzero WCS does not shift the reconstructed Plot through three-decimal rounding.
- Disabled Arc Output selection for Lathe Expanded export; generated turning arcs use relative I/K only.

## 1.4.1 - 2026-09-09

- Added a translucent milling-tool preview that follows logical playback, rendering configured flat, bull-nose and ball-nose mills plus drills with 120-degree points, with a persistent Plot color setting.
- Added a persistent five-level playback-speed slider using CNCEditor's 1000/250/100/40/10 ms logical-motion intervals.
- Fixed milling IJK arc handling so rounded real-world arc coordinates are no longer rejected solely because the start and end radii differ slightly.
- Fixed IJK arcs being discarded when Radius source mode is selected but the source block contains IJK coordinates and no R value.
- Removed the unconditional `UNVERIFIED_TOOL_LENGTH_COMPENSATION` warning emitted for every milling `G43` block.
- Changed the default arc source mode from absolute-center coordinates to incremental IJK coordinates.
- Added a true zero-motion playback state: Stop now returns to the program start before the first motion, and the playback slider starts at zero.
- Preserved the current playback position when the toolpath is refreshed or re-executed instead of always jumping to the end.
- Paused playback automatically when stepping forward or backward manually.
- Fixed playback timer handling so unrelated Qt timer events no longer advance CNC playback.
- Made lathe/mill mode switching rebuild the toolpath without showing execution-error dialogs during the automatic refresh.
- Improved milling-tool validation: invalid diameters and lengths, non-finite values, and impossible bull-nose corner radii are now rejected.
- Improved file handling with NC-specific Open/Save filters, automatic `.nc` extension for unnamed NC files, corrected DXF extension handling, and atomic file writes.
- Added protection against overwriting files that were modified externally after being opened.
- Fixed recent-file path normalization on Windows.
- Fixed Find, Replace and Replace All behavior, including empty-search handling, case-insensitive replacement, preserving editor selection/cursor state, and grouping Replace All into a single undo action.
- Changed Export and Block Number dialogs so edited settings are applied only after pressing OK; Cancel now leaves existing application settings unchanged.
- Fixed swapped icons for Remove Empty Lines and Remove Spaces.
- Restricted application file logging to the `app` logger instead of modifying the root Python logger, and made legacy-config migration failures non-fatal.

## 1.4.0 - 2026-09-08

- Added ASCII and binary STL import as a persistent 3D overlay alongside the executed toolpath, with File menu, toolbar and direct `.stl` file-open integration.
- Added solid and feature-edge STL rendering modes with configurable persistent model color and explicit Clear STL support.
- Included imported STL geometry in Fit to View and scene bounds so the camera fits the complete toolpath/model combination instead of the toolpath alone.
- Reworked STL rendering around a persistent OpenGL overlay so camera and view changes reuse the existing mesh instead of rebuilding `MeshData`, face colors and scene items.
- Optimized STL loading and rendering with vectorized binary parsing and normal normalization, cached wireframe feature edges and cached toolpath bounds.
- Added true orthographic projection for Top, Front and Left milling views while retaining perspective projection for the standard 3D view, eliminating depth-precision artifacts caused by the previous near-zero-FOV perspective approximation.
- Added persistent optional gradient plot background and STL appearance controls to Plot options, with improved default grid contrast.
- Corrected OpenGL depth/render ordering for the grid, STL model and coordinate-axis triad so solid geometry occludes hidden surfaces correctly while the axis triad remains visible as a screen-oriented overlay.
- Added DXF export of the resolved motion trace with analytical lines, arcs and circles, separate rapid/cutting layers, Plot-aligned Z/X turning coordinates and 3D milling entities.
- Replaced the oversized statistics message box with a reusable, resizable report window containing a read-only scrollable text view.
- Automatically fit the camera to the complete scene after a newly loaded CNC program finishes building its toolpath.
- Reworked Expanded Execution export around execution-step events so tool changes and repeated subprogram boundaries retain runtime order, sequence numbers include executable events, and the program number precedes the analysis banner.
- Preserved WCS selection, G28/G53, G32/G33 threading, G4 dwell, spindle mode/speed/direction and coolant controls in Expanded Execution output, with WCS-aware coordinates.

## 1.3.0 - 2026-09-08

- Added deterministic execution events for program start/end, subprogram start/end, tool changes and home returns across turning and milling execution.
- Exposed execution events through `ExecutionResult`, per-step execution snapshots and CLI JSON output.
- Reworked full-program exporters to use execution events for program/subprogram boundaries, program termination and home-return preservation instead of re-detecting those structures from source text.
- Corrected milling tool semantics so `T` preselects a tool and `M6` emits the actual tool-change event and activates it; split `T`/`M6` blocks no longer assign the new tool to intervening motions.
- Classified milling `G53` as a home-return event only when the addressed machine-coordinate axes deterministically target configured home, including non-zero active WCS offsets.
- Replaced per-frame toolpath array rebuilding with a persistent VBO-backed `GL_LINES` item inside the existing pyqtgraph `GLViewWidget`; playback now changes only the visible logical draw prefix.
- Replaced the three origin-axis lines with a fixed-screen-size 3D axis triad at CNC coordinate zero, with arrowheads and X/Y/Z labels.
- Preserved execution-step ownership through milling cutter compensation so inserted corner transitions export correctly without stale motion counts or repeated G41/G42 compensation.

## 1.2.7 - 2026-09-07

- Added persistent Auto Update controls, including a configurable sampled-segment limit after which plot refresh requires the manual Update action.
- Added staged progress reporting for manual updates of long files; the status-bar indicator remains hidden during idle and ordinary short updates.
- Kept the editor caret and trajectory slider stable while edited source is waiting for recalculation, and preserved the previous plot until a successful refresh replaces it.
- Synchronized machine-specific GUI capabilities so Turning Tools and Milling Tools follow the active execution profile while arc interpretation and tolerance remain available for both turning and milling.
- Added turning G2/G3 regression coverage for relative I/K, absolute I/K and R arcs in both diameter and radius X programming modes without changing existing kernel normalization.
- Removed the dead downstream `arc_type` API from trace rendering, geometry statistics and export consumers; source arc interpretation now exists only at kernel execution.
- Reworked the export dialog into four logical output types with separate G90/G91 and arc-representation controls for expanded execution output, preserving the existing full-program and plot-data exporters.
- Expanded Tokens regression coverage for Macro B flow, grouped modal words, unverified/unsupported diagnostics, fatal execution and partial turning traces.
- Unified GUI and CLI NC-file decoding through one explicit UTF-8/Windows-1251 loader contract and added a CLI `--encoding` option.
- Required the release version passed to `scripts/ps1/release.ps1` to match `pyproject.toml` before creating a commit or tag.
- Made CI static checks blocking and migrated legacy `config.ini` discovery away from process CWD to the stable application directory.
- Restored the 256×256 logo in the About dialog by adding it to the compiled Qt resources and making resource-manifest validation UTF-8-safe.

## 1.2.6 - 2026-09-06

- Run PyInstaller in a disposable `uv --isolated` environment so release packaging cannot mutate the developer `.venv` or leave a second project venv, while test, lint and sync scripts honor an explicitly activated environment.
- Reorganized the main-window GUI layer: `app/main_window.py` now composes focused file, editor, execution/playback and plot mixins under `app/ui/`, and the existing settings/grid/navigation helpers were moved into the same UI package.
- Replaced the stale `app/ui/untitled.ui` Designer source with the canonical `app/ui/generated/main_window.ui`, synchronized with the current editor, plot view, settings actions and two-toolbar layout.
- Fixed drag-and-drop to accept local files only and open the first dropped local file deterministically instead of silently using the last URL.
- Fixed stale toolpath display after edits by invalidating the previous execution/render state before the debounced auto-refresh; oversized, invalid or render-limited edits no longer leave an old trajectory visible.
- Fixed whitespace cleanup so multiple parenthesized comments on one line are preserved independently instead of being concatenated/duplicated.
- Hardened GUI export by aborting when execution fails and reporting output-file errors through the GUI.
- Added PySide6 6.11 as a development-only Qt code-generation toolchain plus PowerShell scripts for regenerating `.ui` and `.qrc` Python modules and converting generated imports back to PyQt6.
- Made Qt generation atomic and deterministic, with automatic `.ui` discovery, resource-manifest validation, path-independent execution, PyQt6 enum normalization and functional regression tests for changed or broken inputs.
- Kept PySide6 out of packaged builds by synchronizing the PyInstaller stage without the dev dependency group.
- Added separate Qt Designer-based `Tokens` and `Options` dialogs to the Settings menu instead of folding either feature into the main-window controller.
- Added a read-only Tokens diagnostic table backed by the existing parser AST and execution diagnostics, with detailed FANUC address groups, status coloring, live refresh, multi-row clipboard copy, CSV export and column reset.
- Added persistent General, Editor and Plot options for file encoding, default file type and units, logging, G41/G42 correction, arc tolerance, editor presentation, plot colors, line width, axes, and fixed/adaptive grid selection, with native color pickers and restore-defaults support.
- Exposed the current UI language in Options as a disabled selector pending complete runtime localization support.
- Simplified Settings menu labels, assigned F2 to Options, and added compact FANUC P1-P9 tip-orientation icons to the turning-tool editor and table without changing control or row heights.
- Matched Tokens validation colors to the Tkinter view: pale green for parsed rows and pale red for every suspicious row.
- Added a resource-backed Fit to View command to the plot context menu, centering the complete toolpath in turning mode and fitting milling bounds from all eight view-rotated corners with CNCEditor-compatible 0.9 padding.
- Added UTF-8 and Windows-1251 document loading and saving through the selected file encoding.
- Fixed the new Options integration so default editor mode persists, default units initialize execution until explicit G20/G21, editor font changes are reapplied to the active lexer, and correction/unit/arc-tolerance changes refresh the current execution instead of leaving a stale trace.
- Made the logging toggle functional with a per-user `main.log` and project-owned file handler instead of disabling the process-wide root logger.
- Fixed Tokens support classification to follow kernel diagnostics, include supported modal/cycle codes, and keep fractional G words distinct instead of coercing them through `int(float(...))`.
- Preserved pre-existing turning diagnostics when execution later fails, and removed duplicate cycle-budget checkpoints from G71/G72/G76 iteration paths.
- Added a Windows codegen regression that verifies committed Qt generated modules exactly match the current `.ui` and `.qrc` sources.
- Updated imports, tests and README for the new UI module layout and generation workflow.

## 1.2.5 - 2026-09-06

- Stopped coercing fractional G/M words to the nearest integer code; unsupported fractional controller codes are now preserved as distinct values and reported diagnostically instead of being executed as another command.
- Fixed relative-center export for turning G18 arcs with non-zero X starts by keeping diameter-space motion coordinates and physical/radius-space arc centers consistent.
- Added bounded trace rendering so point limits are enforced during arc/helix tessellation instead of only after the full sampled trajectory has already been created.
- Fixed `M98 ... L<n>` resource accounting so each repeated subprogram execution consumes the `subprogram_calls` budget.
- Fixed editor font persistence by using the same `EDITOR/FONT_*` settings keys for saving and loading.
- Reduced `main_window.py` by extracting existing settings persistence and plot viewport/navigation responsibilities without changing the current GUI behavior.
- Added regression coverage for fractional G/M handling, turning arc export, bounded rendering, repeated subprogram accounting and editor settings persistence.

## 1.2.4 - Unreleased

- Updated README and project documentation to reflect the current execution architecture, milling cutter compensation and tool configuration.

## 1.2.3 - 2026-09-05

- Stabilized the execution pipeline around one runtime `ExecutionResult` with resolved modal state, machine signals and execution occurrences; removed duplicate turning execution/scanning paths.
- Moved analytical arc resolution into the kernel, removed consumer-side I/2I best-fit heuristics, and fixed resolved-arc export across unit/coordinate conversions.
- Hardened runtime semantics for subprogram state, unsupported position-changing G-codes and cycle/resource limits with explicit structured diagnostics.
- Updated statistics to use physical turning geometry and executed feed/spindle state, reporting unresolved machining time as unknown instead of guessing.
- Restored milling cutter-compensation visualization for configured G17 line/arc/helix paths and standardized milling tool identities to compact `T1`-`T99`.

## 1.2.2 - Unreleased

- Fixed FANUC milling `G53` handling. `G53` is now executed as a non-modal move in machine coordinates instead of being treated as an unsupported G-code.
- Preserved the currently active `G54-G59` work coordinate system across `G53`; subsequent milling moves return to the active WCS normally.
- Fixed milling diagnostics so unsupported or currently unmodeled G-codes no longer discard an otherwise valid Motion Trace.
- Changed unknown milling G-codes to informational `UNVERIFIED` warnings instead of fatal execution errors where safe to continue.
- Made unknown `M00-M199` codes non-fatal for visualization and trace execution; unsupported M-codes are reported without breaking the remaining program plot.
- Preserved all successfully resolved motions before and after unsupported controller words instead of returning an empty trace.
- Added regression coverage for `G53` machine-coordinate motion and tolerant handling of unknown G/M codes.

## 1.2.1 - 2026-09-04

- Updated application icons `app/resources/icons/logo.png` and `logo.ico`.
- Refactored the About dialog into a dedicated Qt Designer form and generated PyQt6 UI module.
- Updated the About dialog layout, application description, MIT license text and copyright information.
- Added persistent WCS configuration for `G54-G59` with full `X/Y/Z` offsets and configurable `G28` home coordinates.
- Extended WCS handling so milling uses full XYZ offsets while turning continues to use the relevant X/Z components.
- Fixed the public milling execution path so configured `wcs_offsets` are passed into the milling kernel.
- Split the previous generic Tools dialog into separate `Turning Tools` and `Milling Tools` dialogs.
- Moved `WCS`, `Turning Tools` and `Milling Tools` from `CNC Functions` to the `Settings` menu.
- Added persistent milling tool definitions with tool type, diameter, corner radius, length and description.
- Added milling tool presets for flat end mills, bull-nose mills, ball end mills and drills.
- Kept milling tool configuration informational only; it does not modify Motion Trace or milling geometry.
- Retained turning tool settings for the existing tool-nose compensation workflow.
- Regenerated Qt resource bindings so updated application artwork is used by the packaged UI.

## 1.2.0 — 2026-09-04

- Added source-aware expanded program export for both machine modes: `EXPANDED TURN PROGRAM` in Lathe Mode and `EXPANDED MILL PROGRAM` in Milling Mode; CLI `--mode program` supports both languages while `--mode cycles` remains turning-only.
- Rebuilt turning program export around actual execution-step order instead of `TraceMotion.source_block`, so G72/G73 profile provenance and repeated subprogram execution do not corrupt ordering.
- Preserved `M2`/`M02`/`M30` exactly, kept short and packed T words unchanged, and preserved source controller words such as G50/G96/G97/G98/G99 in expanded turning output; preservation is pass-through and does not imply complete execution semantics for those controls.
- Preserved source unit mode by scaling normalized trace geometry back to the active G20/G21 units at each executed block.
- Added one logical cycle group per executed cycle invocation, including G72/G73 and finish cycles.
- Added Shift+Click trajectory picking in turning and milling orthographic 2D views with source-line/playback synchronization.
- Rendered G0 rapid motions separately in red while preserving the configured cutting-path color.
- Added persistent File -> Recent Files MRU handling with missing-file cleanup and Clear Recent.
- Made the playback cursor a small fixed-pixel marker so its apparent size no longer changes with zoom.
- Replaced the GUI-owned parallel `lst*` CNC execution model with a shared native Python `ExecutionResult`/logical Motion Trace.
- Added a staged lexer/AST/semantic execution kernel and standalone CLI for `fanuc_turn` and `fanuc_mill`.
- Integrated FANUC turning cycles G70–G76, modal turning cycles, G83/G84, Macro B/control flow, M98/M99, WCS/reference handling and tool-nose compensation.
- Added native XYZ milling trace execution with G17/G18/G19 arcs/helixes and drilling cycles.
- Added source-aware expanded milling-program reconstruction in actual execution-step order, including canned-cycle expansion, repeated M98/M99 execution, comments, T/M6, S/M, WCS, G43/H controls and exact M2/M02/M30 preservation.
- Made unmodeled milling G41/G42 cutter-radius and G43 tool-length geometry explicit: their modal state is tracked and the resolver emits `UNVERIFIED` warnings instead of silently treating the geometry as fully modeled.
- Added fail-closed handling for undefined macros and unknown/reference-changing coordinate semantics; G30 no longer reuses the primary G28 reference implicitly.
- Preserved repeated address words/modal G codes in source parsing.
- Kept arcs logical until rendering/export sampling and moved statistics to the authoritative trace.
- Reworked GUI playback/source synchronization around logical motions and indexed source mapping.
- Replaced the legacy exporter with a trace-based exporter while retaining GUI arc-format, incremental, sequence, header/footer and safety-line options.
- Added machine signals/program-end data to execution results.
- Removed the legacy `app/gcode/processing.py` execution engine and duplicate kernel export/statistics paths.
- Expanded regression coverage against donor FANUC turning/milling programs.
