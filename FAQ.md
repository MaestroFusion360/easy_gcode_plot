# Easy G-Code Plot FAQ

This document is the detailed user and developer reference for Easy G-Code Plot. It reflects the current working tree and explains the GUI, FANUC execution kernel, the supported SINUMERIK native and ISO-M subsets, Macro B runtime, turning and milling cycles, indexed rotary behavior, diagnostics, CLI, batch analysis and export behavior.

The same FAQ can be packaged for offline use in **Help → FAQ**.

<details>
  <summary><h2>Contents</h2></summary>

- [Easy G-Code Plot FAQ](#easy-g-code-plot-faq)
  - [Project scope and execution model](#project-scope-and-execution-model)
    - [What is Easy G-Code Plot?](#what-is-easy-g-code-plot)
    - [What is the authoritative data flow?](#what-is-the-authoritative-data-flow)
    - [Is the OpenGL plot the CNC model?](#is-the-opengl-plot-the-cnc-model)
    - [Is the program a machine simulator?](#is-the-program-a-machine-simulator)
    - [What does deterministic mean in this project?](#what-does-deterministic-mean-in-this-project)
  - [Getting started](#getting-started)
    - [How do I install it?](#how-do-i-install-it)
    - [What is the normal GUI workflow?](#what-is-the-normal-gui-workflow)
    - [Which input encodings are supported?](#which-input-encodings-are-supported)
    - [Are compact FANUC blocks accepted?](#are-compact-fanuc-blocks-accepted)
    - [Which comment forms are understood?](#which-comment-forms-are-understood)
    - [How do optional `/` Block Skip lines work?](#how-do-optional--block-skip-lines-work)
  - [Diagnostics and fail-closed behavior](#diagnostics-and-fail-closed-behavior)
    - [What are `ok` and `complete`?](#what-are-ok-and-complete)
    - [What diagnostic information is stored?](#what-diagnostic-information-is-stored)
    - [What happens after unsupported position-changing semantics?](#what-happens-after-unsupported-position-changing-semantics)
    - [How are unsupported turning G-codes classified?](#how-are-unsupported-turning-g-codes-classified)
    - [What about unsupported M-codes?](#what-about-unsupported-m-codes)
    - [Are conflicting modal codes detected?](#are-conflicting-modal-codes-detected)
    - [Are there execution resource limits?](#are-there-execution-resource-limits)
  - [FANUC Macro B and program flow](#fanuc-macro-b-and-program-flow)
    - [How complete is Macro B support?](#how-complete-is-macro-b-support)
    - [Which variable forms are supported?](#which-variable-forms-are-supported)
    - [What is special about `#0`?](#what-is-special-about-0)
    - [What happens when an undefined variable is used numerically?](#what-happens-when-an-undefined-variable-is-used-numerically)
    - [Which arithmetic and relational operators are supported?](#which-arithmetic-and-relational-operators-are-supported)
    - [Which Macro B functions are implemented?](#which-macro-b-functions-are-implemented)
    - [Are assignments supported on labeled blocks?](#are-assignments-supported-on-labeled-blocks)
    - [Is unconditional `GOTO` supported?](#is-unconditional-goto-supported)
    - [Is `IF [...] GOTO` supported?](#is-if--goto-supported)
    - [Are `WHILE / DO / END` loops supported?](#are-while--do--end-loops-supported)
    - [Are real Macro B milling programs exercised by the tests?](#are-real-macro-b-milling-programs-exercised-by-the-tests)
    - [Is `G65` supported?](#is-g65-supported)
    - [How are G65 Type I arguments mapped?](#how-are-g65-type-i-arguments-mapped)
    - [How are repeated I/J/K G65 arguments handled?](#how-are-repeated-ijk-g65-arguments-handled)
    - [Do G65 argument words also perform machine actions?](#do-g65-argument-words-also-perform-machine-actions)
    - [What happens to `#1..#33` when a G65 macro returns?](#what-happens-to-133-when-a-g65-macro-returns)
    - [What does `G65 ... L...` do?](#what-does-g65--l-do)
    - [How deeply can G65 macros nest?](#how-deeply-can-g65-macros-nest)
    - [How does M98 behave inside a G65 macro?](#how-does-m98-behave-inside-a-g65-macro)
    - [Are M98/M99 subprograms supported outside Macro B?](#are-m98m99-subprograms-supported-outside-macro-b)
    - [Is `M99 P...` supported?](#is-m99-p-supported)
    - [Are Macro B variable values stored per execution step?](#are-macro-b-variable-values-stored-per-execution-step)
    - [Does Expanded Execution export keep Macro B statements?](#does-expanded-execution-export-keep-macro-b-statements)
  - [FANUC turning](#fanuc-turning)
    - [Main differences between Type A and Type B](#main-differences-between-type-a-and-type-b)
    - [What is the turning coordinate model?](#what-is-the-turning-coordinate-model)
    - [How do X/U and Z/W behave?](#how-do-xu-and-zw-behave)
    - [How are G20 and G21 handled?](#how-are-g20-and-g21-handled)
    - [Which turning arc formats are supported?](#which-turning-arc-formats-are-supported)
    - [Why can G2/G3 direction look inverted in an XZ plot?](#why-can-g2g3-direction-look-inverted-in-an-xz-plot)
    - [Is direct A-angle turning programming supported?](#is-direct-a-angle-turning-programming-supported)
    - [Are C chamfers and corner R fillets supported?](#are-c-chamfers-and-corner-r-fillets-supported)
    - [Are G32 and G33 threading motions supported?](#are-g32-and-g33-threading-motions-supported)
    - [What are the turning feed modes?](#what-are-the-turning-feed-modes)
    - [Are G96 and G97 modeled?](#are-g96-and-g97-modeled)
    - [What does G50 S do in turning?](#what-does-g50-s-do-in-turning)
    - [Are spindle start/stop signals tracked?](#are-spindle-startstop-signals-tracked)
    - [Which WCS features work in turning?](#which-wcs-features-work-in-turning)
    - [Is G53 supported in turning?](#is-g53-supported-in-turning)
    - [How does G28 work?](#how-does-g28-work)
    - [Is G30 the same as G28?](#is-g30-the-same-as-g28)
    - [How does tool-nose compensation work?](#how-does-tool-nose-compensation-work)
  - [Turning cycles](#turning-cycles)
    - [Which turning cycles are modeled?](#which-turning-cycles-are-modeled)
    - [Do cycle motions remember where they came from?](#do-cycle-motions-remember-where-they-came-from)
    - [How are cycle profiles selected by P and Q?](#how-are-cycle-profiles-selected-by-p-and-q)
    - [Do G71/G72/G73 profile blocks support lines and arcs?](#do-g71g72g73-profile-blocks-support-lines-and-arcs)
    - [How does G70 work?](#how-does-g70-work)
    - [What form of G71 is supported?](#what-form-of-g71-is-supported)
    - [How is G71 depth interpreted?](#how-is-g71-depth-interpreted)
    - [How are G71 U/W finish allowances handled?](#how-are-g71-uw-finish-allowances-handled)
    - [How does G71 distinguish OD and ID roughing?](#how-does-g71-distinguish-od-and-id-roughing)
    - [What is G71 Type I behavior?](#what-is-g71-type-i-behavior)
    - [Is G71 Type II supported?](#is-g71-type-ii-supported)
    - [How does G72 work?](#how-does-g72-work)
    - [Is G72 Type II fully generic?](#is-g72-type-ii-fully-generic)
    - [How does G73 work?](#how-does-g73-work)
    - [How does G74 work?](#how-does-g74-work)
    - [How does G75 work?](#how-does-g75-work)
    - [How is turning peck motion represented?](#how-is-turning-peck-motion-represented)
    - [How does two-line G76 work?](#how-does-two-line-g76-work)
    - [How are G76 P/Q integer increments interpreted?](#how-are-g76-pq-integer-increments-interpreted)
    - [How is G76 pass depth generated?](#how-is-g76-pass-depth-generated)
    - [What do the packed G76 P digits mean here?](#what-do-the-packed-g76-p-digits-mean-here)
    - [Which G76 tool angles are modeled?](#which-g76-tool-angles-are-modeled)
    - [How is G76 chamfer modeled?](#how-is-g76-chamfer-modeled)
    - [Is G92 a modal threading cycle?](#is-g92-a-modal-threading-cycle)
    - [Is G90 a modal turning cycle?](#is-g90-a-modal-turning-cycle)
    - [Is G94 a modal facing cycle?](#is-g94-a-modal-facing-cycle)
    - [What cancels G90/G92/G94?](#what-cancels-g90g92g94)
    - [Are turning G83 and G84 modal?](#are-turning-g83-and-g84-modal)
    - [How does turning G83 behave?](#how-does-turning-g83-behave)
    - [How does turning G84 behave?](#how-does-turning-g84-behave)
    - [Does P dwell in turning G83/G84 create geometry?](#does-p-dwell-in-turning-g83g84-create-geometry)
    - [What happens if a modal drilling/tapping cycle is left in an invalid state?](#what-happens-if-a-modal-drillingtapping-cycle-is-left-in-an-invalid-state)
  - [FANUC milling](#fanuc-milling)
    - [Which milling G functions are recognized?](#which-milling-g-functions-are-recognized)
    - [Which milling M functions are recognized?](#which-milling-m-functions-are-recognized)
    - [What basic milling motion is modeled?](#what-basic-milling-motion-is-modeled)
    - [How is indexed rotary milling handled?](#how-is-indexed-rotary-milling-handled)
    - [Which rotary profiles have been checked?](#which-rotary-profiles-have-been-checked)
    - [What happens when indexed geometry cannot be resolved?](#what-happens-when-indexed-geometry-cannot-be-resolved)
    - [Which milling canned cycles are modeled?](#which-milling-canned-cycles-are-modeled)
    - [What is the difference between G73 and G83 milling peck cycles?](#what-is-the-difference-between-g73-and-g83-milling-peck-cycles)
    - [How is G82 dwell represented?](#how-is-g82-dwell-represented)
    - [How is milling G84 represented?](#how-is-milling-g84-represented)
    - [How is milling G86 represented?](#how-is-milling-g86-represented)
    - [What do milling G98/G99 mean?](#what-do-milling-g98g99-mean)
    - [What are milling feed modes?](#what-are-milling-feed-modes)
    - [Which work coordinate systems are supported?](#which-work-coordinate-systems-are-supported)
    - [How does G10 behave under G91 in milling?](#how-does-g10-behave-under-g91-in-milling)
    - [How does G52 work?](#how-does-g52-work)
    - [How do G68 and G69 work?](#how-do-g68-and-g69-work)
    - [How does G51/G50 scaling work?](#how-does-g51g50-scaling-work)
    - [Is G53 supported in milling?](#is-g53-supported-in-milling)
    - [Is G28 supported in milling?](#is-g28-supported-in-milling)
    - [Is continuous five-axis TCP (`G43.4`) supported?](#is-continuous-five-axis-tcp-g434-supported)
    - [How are milling arcs programmed?](#how-are-milling-arcs-programmed)
    - [What does Arc Type autodetection do?](#what-does-arc-type-autodetection-do)
    - [Can one program mix R arcs with IJK arcs?](#can-one-program-mix-r-arcs-with-ijk-arcs)
    - [Are full circles supported?](#are-full-circles-supported)
    - [Is helical interpolation supported?](#is-helical-interpolation-supported)
    - [What does G16/G15 polar programming do?](#what-does-g16g15-polar-programming-do)
    - [How does polar G90 work?](#how-does-polar-g90-work)
    - [How does polar G91 work?](#how-does-polar-g91-work)
    - [Do G20/G21 scale the polar angle?](#do-g20g21-scale-the-polar-angle)
    - [Are polar G2/G3 arcs supported?](#are-polar-g2g3-arcs-supported)
    - [Is G12.1/G13.1 polar interpolation supported?](#is-g121g131-polar-interpolation-supported)
    - [How does milling cutter compensation work?](#how-does-milling-cutter-compensation-work)
    - [What does `UNVERIFIED_CUTTER_COMPENSATION` mean?](#what-does-unverified_cutter_compensation-mean)
    - [Is G43 tool-length geometry applied?](#is-g43-tool-length-geometry-applied)
  - [Tool libraries and tool discovery](#tool-libraries-and-tool-discovery)
    - [Where are persistent tools stored?](#where-are-persistent-tools-stored)
    - [What is the difference between Current Program and Saved Library?](#what-is-the-difference-between-current-program-and-saved-library)
    - [Does opening a program write discovered tools to the database?](#does-opening-a-program-write-discovered-tools-to-the-database)
    - [How are turning tool numbers represented?](#how-are-turning-tool-numbers-represented)
    - [Can comments describe tool geometry?](#can-comments-describe-tool-geometry)
    - [What happens when no explicit type hint is present?](#what-happens-when-no-explicit-type-hint-is-present)
    - [Are macro T expressions discovered as literal tools?](#are-macro-t-expressions-discovered-as-literal-tools)
    - [Which turning tool geometries are stored?](#which-turning-tool-geometries-are-stored)
    - [Which milling tools can be previewed?](#which-milling-tools-can-be-previewed)
    - [How are milling tool lengths defined?](#how-are-milling-tool-lengths-defined)
    - [Does CLI execution load the GUI Saved Library?](#does-cli-execution-load-the-gui-saved-library)
  - [Interface, editor and playback](#interface-editor-and-playback)
    - [What are the two main GUI panels?](#what-are-the-two-main-gui-panels)
    - [How does an imported STL affect toolpath visibility?](#how-does-an-imported-stl-affect-toolpath-visibility)
    - [How do I use the STL Objects panel?](#how-do-i-use-the-stl-objects-panel)
      - [How do I import and select STL models?](#how-do-i-import-and-select-stl-models)
      - [What do Undo, Redo, Statistics and Delete do?](#what-do-undo-redo-statistics-and-delete-do)
      - [How do STL base points and bounding-box picks work?](#how-do-stl-base-points-and-bounding-box-picks-work)
      - [How do I position and transform an STL model?](#how-do-i-position-and-transform-an-stl-model)
      - [How do STL arrays work?](#how-do-stl-arrays-work)
      - [How do I make a 3D section through an STL model?](#how-do-i-make-a-3d-section-through-an-stl-model)
      - [What does STL Statistics report, and how do I display inches?](#what-does-stl-statistics-report-and-how-do-i-display-inches)
    - [How do I change letter case or mark optional blocks?](#how-do-i-change-letter-case-or-mark-optional-blocks)
    - [How do I print the plot?](#how-do-i-print-the-plot)
    - [Which fixed views are available?](#which-fixed-views-are-available)
    - [How does playback relate to the kernel?](#how-does-playback-relate-to-the-kernel)
    - [What do Step Backward and Step Forward do?](#what-do-step-backward-and-step-forward-do)
    - [Why can many playback motions map to one source line?](#why-can-many-playback-motions-map-to-one-source-line)
    - [How do I locate a plotted move in the editor?](#how-do-i-locate-a-plotted-move-in-the-editor)
    - [Does automatic refresh move the editor caret?](#does-automatic-refresh-move-the-editor-caret)
    - [What happens when Auto Update is too expensive?](#what-happens-when-auto-update-is-too-expensive)
    - [What does Cancel stop?](#what-does-cancel-stop)
    - [What CNC editing assistants are included?](#what-cnc-editing-assistants-are-included)
    - [What does Hole Calculator generate?](#what-does-hole-calculator-generate)
    - [What does Pocket Calculator generate?](#what-does-pocket-calculator-generate)
    - [Where are snippets stored?](#where-are-snippets-stored)
  - [Options and scene configuration](#options-and-scene-configuration)
    - [How do I change the interface language?](#how-do-i-change-the-interface-language)
    - [How do I change the theme?](#how-do-i-change-the-theme)
    - [Where do I set work coordinate systems and home values?](#where-do-i-set-work-coordinate-systems-and-home-values)
    - [How do I set turning stock dimensions?](#how-do-i-set-turning-stock-dimensions)
    - [Is Stock Removal available for milling?](#is-stock-removal-available-for-milling)
  - [Turning Stock Removal](#turning-stock-removal)
    - [What is Turning Stock Removal?](#what-is-turning-stock-removal)
    - [How is automatic stock estimated?](#how-is-automatic-stock-estimated)
    - [Can stock dimensions be overridden manually?](#can-stock-dimensions-be-overridden-manually)
    - [Which tools remove material?](#which-tools-remove-material)
    - [How are threads represented in Stock Removal?](#how-are-threads-represented-in-stock-removal)
    - [Does Stock Removal detect machine collisions?](#does-stock-removal-detect-machine-collisions)
  - [Statistics and Tokens/Macro Variables](#statistics-and-tokensmacro-variables)
    - [What does Toolpath Statistics contain?](#what-does-toolpath-statistics-contain)
    - [Why can machining time be UNKNOWN?](#why-can-machining-time-be-unknown)
    - [What is the Tokens tab?](#what-is-the-tokens-tab)
    - [What is the Macro Variables tab?](#what-is-the-macro-variables-tab)
    - [Why can Macro Variables be unavailable?](#why-can-macro-variables-be-unavailable)
  - [Export](#export)
    - [Which GUI export families exist?](#which-gui-export-families-exist)
    - [Are exporters separate G-code interpreters?](#are-exporters-separate-g-code-interpreters)
    - [What does Full Program mean?](#what-does-full-program-mean)
    - [What does Expanded Execution mean?](#what-does-expanded-execution-mean)
    - [What is the analysis banner?](#what-is-the-analysis-banner)
    - [What is turning cycle-group export?](#what-is-turning-cycle-group-export)
    - [What is Plot Data export?](#what-is-plot-data-export)
    - [What does DXF contain?](#what-does-dxf-contain)
    - [Does DXF parse the G-code again?](#does-dxf-parse-the-g-code-again)
    - [Which NC formatting options exist?](#which-nc-formatting-options-exist)
    - [Which milling Expanded arc output modes exist?](#which-milling-expanded-arc-output-modes-exist)
    - [What happens when a full circle is exported in R mode?](#what-happens-when-a-full-circle-is-exported-in-r-mode)
    - [Can Expanded NC be converted between millimetres and inches?](#can-expanded-nc-be-converted-between-millimetres-and-inches)
    - [Why can explicit unit conversion be rejected?](#why-can-explicit-unit-conversion-be-rejected)
    - [Can Full Program be forced to mm or inch?](#can-full-program-be-forced-to-mm-or-inch)
    - [What units does DXF use?](#what-units-does-dxf-use)
    - [Can comments be removed from export?](#can-comments-be-removed-from-export)
    - [Are exports written atomically by the CLI service?](#are-exports-written-atomically-by-the-cli-service)
    - [Can CLI export overwrite the source file?](#can-cli-export-overwrite-the-source-file)
  - [SINUMERIK 840D input](#sinumerik-840d-input)
    - [What SINUMERIK support is included?](#what-sinumerik-support-is-included)
    - [How are MPF and SPF files detected?](#how-are-mpf-and-spf-files-detected)
    - [Can FANUC milling programs be converted to SINUMERIK?](#can-fanuc-milling-programs-be-converted-to-sinumerik)
    - [Can SINUMERIK native milling programs be converted to FANUC?](#can-sinumerik-native-milling-programs-be-converted-to-fanuc)
    - [How do Full Program and Resolved conversion differ?](#how-do-full-program-and-resolved-conversion-differ)
    - [Is SINUMERIK lathe supported?](#is-sinumerik-lathe-supported)
  - [CLI](#cli)
    - [Does the CLI use the same kernel as the GUI?](#does-the-cli-use-the-same-kernel-as-the-gui)
    - [Which commands exist?](#which-commands-exist)
    - [What does `parse` do?](#what-does-parse-do)
    - [What does `trace` do?](#what-does-trace-do)
    - [What does `analyze` do?](#what-does-analyze-do)
    - [What does `batch` do?](#what-does-batch-do)
    - [What does `export` do?](#what-does-export-do)
    - [What does `batch-export` do?](#what-does-batch-export-do)
    - [Are single export and batch export different exporters?](#are-single-export-and-batch-export-different-exporters)
    - [Which dialect names are used?](#which-dialect-names-are-used)
    - [What are the exit codes?](#what-are-the-exit-codes)
    - [How do I see every option and default?](#how-do-i-see-every-option-and-default)
  - [Batch analysis](#batch-analysis)
    - [What does batch analysis validate?](#what-does-batch-analysis-validate)
    - [Which batch statuses exist?](#which-batch-statuses-exist)
    - [Which extensions are scanned by default?](#which-extensions-are-scanned-by-default)
    - [Can files without a normal NC extension be discovered?](#can-files-without-a-normal-nc-extension-be-discovered)
    - [Is discovery deterministic?](#is-discovery-deterministic)
    - [Can I restrict extensions?](#can-i-restrict-extensions)
    - [What is aggregated in the batch summary?](#what-is-aggregated-in-the-batch-summary)
    - [What files are written?](#what-files-are-written)
    - [Does a bad input file stop the whole batch?](#does-a-bad-input-file-stop-the-whole-batch)
    - [Are there preset batch scripts?](#are-there-preset-batch-scripts)
  - [Batch export](#batch-export)
    - [What problem does batch export solve?](#what-problem-does-batch-export-solve)
    - [Does batch export modify the input files?](#does-batch-export-modify-the-input-files)
    - [Is the source directory hierarchy preserved?](#is-the-source-directory-hierarchy-preserved)
    - [What happens if two source names map to one output name?](#what-happens-if-two-source-names-map-to-one-output-name)
    - [Does one export error stop every file?](#does-one-export-error-stop-every-file)
    - [What files describe the batch export?](#what-files-describe-the-batch-export)
    - [What are batch-export statuses?](#what-are-batch-export-statuses)
    - [Which export modes are available from the CLI?](#which-export-modes-are-available-from-the-cli)
    - [Which options are intentionally rejected in Full Program mode?](#which-options-are-intentionally-rejected-in-full-program-mode)
    - [Which options are rejected for turning cycle export?](#which-options-are-rejected-for-turning-cycle-export)
    - [Can sequence start/increment be supplied without sequence numbers?](#can-sequence-startincrement-be-supplied-without-sequence-numbers)
    - [Are there preset batch-export scripts?](#are-there-preset-batch-export-scripts)
  - [Configuration](#configuration)
    - [Where is application configuration stored on Windows?](#where-is-application-configuration-stored-on-windows)
    - [What is stored in `config.ini`?](#what-is-stored-in-configini)
    - [Is `tools.db` replaceable by old JSON values in config.ini?](#is-toolsdb-replaceable-by-old-json-values-in-configini)
    - [Where is the log file?](#where-is-the-log-file)
    - [What does DEBUG logging add?](#what-does-debug-logging-add)
  - [Troubleshooting](#troubleshooting)
    - [The plot is empty](#the-plot-is-empty)
    - [Macro B motion is missing](#macro-b-motion-is-missing)
    - [My G65 M/S/T words did not start spindle/coolant/change tool](#my-g65-mst-words-did-not-start-spindlecoolantchange-tool)
    - [Cutter compensation is not visible](#cutter-compensation-is-not-visible)
    - [G43 appears in the source but the plotted Z does not include tool length](#g43-appears-in-the-source-but-the-plotted-z-does-not-include-tool-length)
    - [G71 leaves material on the wrong side](#g71-leaves-material-on-the-wrong-side)
    - [G72 Type II reports an error](#g72-type-ii-reports-an-error)
    - [G76 reports `UNSUPPORTED_G76_TOOL_ANGLE`](#g76-reports-unsupported_g76_tool_angle)
    - [Batch shows `UNSUPPORTED_M_CODE` but the geometry looks correct](#batch-shows-unsupported_m_code-but-the-geometry-looks-correct)
    - [Export unit conversion is refused](#export-unit-conversion-is-refused)
    - [Batch-export says the output directory is invalid](#batch-export-says-the-output-directory-is-invalid)
    - [A large program does not update while typing](#a-large-program-does-not-update-while-typing)
    - [The GUI says the current execution is stale](#the-gui-says-the-current-execution-is-stale)
  - [Development and architecture](#development-and-architecture)
    - [How is the CNC kernel organized?](#how-is-the-cnc-kernel-organized)
    - [What belongs in `frontend/`?](#what-belongs-in-frontend)
    - [What belongs in `runtime/`?](#what-belongs-in-runtime)
    - [Why are turning cycles separate files?](#why-are-turning-cycles-separate-files)
    - [What belongs in `milling/`?](#what-belongs-in-milling)
    - [What belongs in `compensation/`?](#what-belongs-in-compensation)
    - [What belongs in `app/gcode/export/`?](#what-belongs-in-appgcodeexport)
    - [What does `program_execution.py` do?](#what-does-program_executionpy-do)
    - [What does `batch.py` do?](#what-does-batchpy-do)
    - [What does `batch_export.py` do?](#what-does-batch_exportpy-do)
    - [Which native components exist?](#which-native-components-exist)
    - [How are execution results represented publicly?](#how-are-execution-results-represented-publicly)
    - [What is an `ExecutionStep`?](#what-is-an-executionstep)
    - [What is an `ExecutionEvent`?](#what-is-an-executionevent)
    - [How are tests organized?](#how-are-tests-organized)
    - [How do I run the main checks?](#how-do-i-run-the-main-checks)
    - [How do I run the daily GUI smoke test with a visible window?](#how-do-i-run-the-daily-gui-smoke-test-with-a-visible-window)
    - [Are generated Qt Python files edited manually?](#are-generated-qt-python-files-edited-manually)
  - [Build and release](#build-and-release)
    - [How do I build on Windows?](#how-do-i-build-on-windows)
    - [How do I build on Linux?](#how-do-i-build-on-linux)
    - [Does the project use a separate build environment?](#does-the-project-use-a-separate-build-environment)
    - [How are releases validated in CI?](#how-are-releases-validated-in-ci)
    - [Does a Linux executable run as a Windows `.exe`?](#does-a-linux-executable-run-as-a-windows-exe)
  - [License](#license)

</details>

---

## Project scope and execution model

### What is Easy G-Code Plot?

Easy G-Code Plot is a FANUC-style CNC editor, deterministic program executor, analyzer, backplotter and exporter for turning and milling programs.

The project has two user-facing entry points:

- a PyQt6 desktop GUI;
- a standalone CLI executable.

Both use the same CNC kernel and the same resolved `ExecutionResult`. The GUI is not a second interpreter, and the CLI does not contain a simplified parser of its own.

### What is the authoritative data flow?

The core data flow is:

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
                `--> NC / DXF export
```

`ExecutionResult` contains the resolved logical motion trace plus diagnostics, execution steps, signals, structural events, WCS state and execution completeness.

### Is the OpenGL plot the CNC model?

No. Rendering consumes the resolved trace produced by the kernel. The renderer does not independently reinterpret G-code.

This separation is intentional: the same resolved geometry is used by playback, statistics, export and analysis.

### Is the program a machine simulator?

No. Easy G-Code Plot models supported FANUC program semantics and toolpath geometry. It does not model a complete physical CNC machine, servo dynamics, acceleration, spindle inertia, fixtures, machine envelopes or all controller parameters.

A clean result means the modeled program was executed without a known error inside the supported contract. It is not a substitute for machine verification.

### What does deterministic mean in this project?

For supported input, execution is intended to produce the same logical trace and diagnostics from the same source and configuration. The kernel avoids guessing controller-dependent behavior when the required semantics are not known.

Where the program cannot be resolved safely, the preferred behavior is an explicit diagnostic or incomplete result rather than invented geometry.

---

## Getting started

### How do I install it?

Release builds provide separate GUI and CLI executables for Windows and a Linux x64 archive containing both executables. A Python installation is not required for packaged builds.

For a source checkout, the project requires Python 3.13+, `uv` and a compiler for the native extensions.

```bash
git clone https://github.com/MaestroFusion360/easy_gcode_plot.git
cd easy_gcode_plot
uv sync --no-dev
uv run --no-dev python main.py
```

### What is the normal GUI workflow?

1. Open or drag a CNC program into the application.
2. Select **Lathe Mode** for turning or leave it disabled for milling.
3. Configure WCS, home and tools when the program requires them.
4. Refresh the execution result.
5. Inspect the trajectory, playback, diagnostics and statistics.
6. Export the full program, expanded execution, cycle groups, plot data or DXF when required.

### Which input encodings are supported?

The normal document encodings are UTF-8 and Windows-1251. The GUI opens `.ptp` files by default and tries Windows-1251 if UTF-8 decoding fails; saving preserves the detected encoding. The CLI exposes the supported encodings through `--encoding`.

### Are compact FANUC blocks accepted?

Yes. Words do not need spaces. Blocks such as:

```text
G18G21G40G54G80G99
G0X100Z5
```

are parsed as address words rather than relying on whitespace splitting.

### Which comment forms are understood?

Both common forms are recognized:

```text
(COMMENT)
; COMMENT
```

A persistent comment-style option controls generated text exports. Reading source programs is not limited to the selected output style.

### How do optional `/` Block Skip lines work?

A source block beginning with `/` is marked as optional.

With **Ignore Block Skip** enabled, the complete block is excluded from execution, including:

- motion;
- Macro B assignments;
- signals;
- subprogram or macro calls.

With the option disabled, it executes normally.

---

## Diagnostics and fail-closed behavior

### What are `ok` and `complete`?

`ExecutionResult.ok` describes whether execution avoided a fatal modeled error. `ExecutionResult.complete` indicates whether the kernel considers the resulting execution trace complete enough for consumers such as export.

A program can therefore retain trustworthy motions before an unsupported or invalid block while still being marked incomplete.

### What diagnostic information is stored?

A diagnostic can contain:

- a stable code such as `UNSUPPORTED_G_CODE` or `UNDEFINED_MACRO`;
- a human-readable message;
- severity;
- status such as verified, unverified, unsupported, malformed or resource-limited;
- source line;
- offending raw block.

### What happens after unsupported position-changing semantics?

The kernel does not assume that the old position remains trustworthy. For turning, an unsupported position-changing command can create an unknown-axis gap. Trace publication resumes only after later absolute coordinates establish a known position again.

This prevents a misleading connector line from being drawn through an unknown region.

### How are unsupported turning G-codes classified?

An unsupported G-code that can affect geometry is treated more seriously than a non-geometric control code. For example, an unsupported code on a block containing X/Z/U/W can make the block unsupported rather than merely unverified.

Y-axis motion is not modeled in `fanuc_turn` and produces `UNSUPPORTED_AXIS`.

### What about unsupported M-codes?

The core tracks modeled program-control and machine signals. Batch/analyze mode additionally reports literal turning M-codes that are not modeled as `UNSUPPORTED_M_CODE` warnings instead of pretending that their machine effect is known.

### Are conflicting modal codes detected?

Yes. Supported modal groups are checked for conflicts within one block. A conflict such as two mutually exclusive motion, plane, unit, compensation, feed, spindle or transform modes produces `MODAL_GROUP_CONFLICT` and the block is not silently interpreted using source-order luck.

### Are there execution resource limits?

Yes. The default execution budget protects against runaway macros, recursive calls and pathological cycles:

| Resource | GUI default |
| --- | ---: |
| Executed blocks | 500,000 |
| Subprogram/macro calls | 10,000 |
| Generated motions | 2,147,483,647 |
| Auto update max segments | 2,147,483,647 |
| Cycle iterations | 100,000 |
| Macro loop iterations | 100,000 |
| General call depth | 64 |

Cancellation is checked through the same budget mechanism. Resource exhaustion produces a structured `RESOURCE_LIMIT`-style result instead of an unbounded run.

---

## FANUC Macro B and program flow

### How complete is Macro B support?

Macro B is part of the execution runtime, not a text substitution preprocessor. Expressions are evaluated while the program executes, so loops, branches, subprogram calls and variable state affect the real logical motion trace.

The same Macro B runtime is used by turning and milling.

### Which variable forms are supported?

Numeric variables:

```text
#1
#100
#500
#13001
```

Named variables:

```text
#<NAME>
#<TOOL_RADIUS>
```

Indirect references:

```text
#[#1]
#[100+#2]
#[FUP[#[ROUND[#3]]]]
```

Indirect assignment is also supported:

```text
#1=100
#[#1]=5
#[#1+1]=#100+2
```

The indirect destination must resolve to an integer variable number.

### What is special about `#0`?

`#0` is permanently vacant.

It cannot be assigned:

```text
#0=123
```

produces `INVALID_MACRO_ASSIGNMENT`.

Vacant values are distinct from numeric zero for equality tests:

```text
IF[#1 EQ #0] GOTO10
```

is the normal way to detect an omitted/vacant local argument.

In arithmetic, a vacant value behaves as numeric zero. Assigning a vacant value clears the destination variable:

```text
#100=#0
```

After that assignment, `#100` is vacant rather than stored as numeric `0`.

### What happens when an undefined variable is used numerically?

A normal numeric reference to an undefined variable fails closed with `UNDEFINED_MACRO`.

The special null-aware comparison behavior is used where FANUC vacant semantics are required, such as comparisons to `#0`.

### Which arithmetic and relational operators are supported?

The expression evaluator supports ordinary arithmetic and FANUC-style relational/logical tokens used by the project fixtures, including:

```text
+  -  *  /
MOD
EQ  NE  GT  GE  LT  LE
AND  OR  XOR
```

Brackets may be nested:

```text
X[#100+5]
#10=[[#1+#2]*#3]
```

Compact expressions such as `#1LT#3` are accepted. AND/OR/XOR convert operands to integers and apply bitwise arithmetic; they do not use Python truthiness. Comparisons return numeric 0/1.

The evaluator rejects exponentiation (`**`), strings, bytes, containers and boolean constants. Limits are 4,096 source characters, 512 AST nodes and depth 64; expression arithmetic uses finite floating-point constants. LN requires a positive argument; EXP overflow produces an execution diagnostic. BIN/BCD/ADP remain explicitly unsupported because their controller-specific semantics were not verified against local references.

### Which Macro B functions are implemented?

The current evaluator includes:

```text
ABS
SQRT
SIN
COS
TAN
ATAN
FIX
FUP
ROUND
MIN
MAX
LN
EXP
```

Trigonometric arguments and results follow FANUC-style degree semantics.

Two-argument FANUC arctangent syntax is supported:

```text
ATAN[y]/[x]
```

For example:

```text
#119=ATAN[0.75]/[1.625]
```

`ROUND` uses FANUC-style nearest-integer rounding with `.5` away from zero.

### Are assignments supported on labeled blocks?

Yes. An `N` block label may precede a Macro B flow statement or assignment:

```text
N900 #151=7
```

Labels are indexed once for flow execution.

### Is unconditional `GOTO` supported?

Yes:

```text
GOTO100
...
N100 ...
```

A missing target produces `FLOW_TARGET_MISSING`.

### Is `IF [...] GOTO` supported?

Yes:

```text
IF[#1 EQ 2] GOTO900
IF[[#2*#11] GT 360] GOTO16
```

Conditions are evaluated at runtime using the current variable state.

### Are `WHILE / DO / END` loops supported?

Yes:

```text
#1=0
WHILE[#1 LT 3] DO1
#1=#1+1
G1 X#1 F100
END1
```

Nested loop IDs are indexed before execution. Missing `END`, unmatched `END`, runaway loops or an exhausted macro-iteration budget produce diagnostics rather than hanging the application.

### Are real Macro B milling programs exercised by the tests?

Yes. The regression corpus includes Macro B programs that generate:

- repeated boss milling;
- face milling;
- hole milling;
- thread milling;
- nested loops;
- large deterministic arc counts;
- indirect variable access.

These execute through the normal milling kernel rather than a separate test interpreter.

### Is `G65` supported?

Yes. `G65 P...` calls an `O` macro program and creates a proper macro-local scope.

Example:

```text
G65 P7700 X0 Y0 M48 S5. D1 R50. Z-70. Q4. V8. I860. A7.5 B15. H24. K1. E100. F200.
```

The called macro can then use the mapped local variables `#1..#33`.

### How are G65 Type I arguments mapped?

The current Type I mapping is:

| Address | Local variable |
| --- | ---: |
| A | #1 |
| B | #2 |
| C | #3 |
| I | #4 on first occurrence |
| J | #5 on first occurrence |
| K | #6 on first occurrence |
| D | #7 |
| E | #8 |
| F | #9 |
| H | #11 |
| M | #13 |
| Q | #17 |
| R | #18 |
| S | #19 |
| T | #20 |
| U | #21 |
| V | #22 |
| W | #23 |
| X | #24 |
| Y | #25 |
| Z | #26 |

`G`, `L`, `N`, `O` and `P` are control words and are not bound as ordinary local arguments.

### How are repeated I/J/K G65 arguments handled?

Repeated I/J/K words use FANUC Type II-style sequential local slots. Each occurrence advances by three:

```text
I -> #4,  #7,  #10, ...
J -> #5,  #8,  #11, ...
K -> #6,  #9,  #12, ...
```

Up to 10 occurrences of each I/J/K address are accepted in one G65 call.

### Do G65 argument words also perform machine actions?

No. On a G65 call, words such as `M`, `S`, `T`, `X`, `Y`, `Z` and `F` are macro arguments, not simultaneous spindle, tool, motion or feed commands.

For example, `T7` or `M8` inside a G65 argument list does not create a tool-change or coolant signal.

### What happens to `#1..#33` when a G65 macro returns?

Local variables are scoped.

On macro entry, the caller's local variables are saved and replaced by the call arguments. On `M99`, the caller's local values are restored. Common and named variables remain shared.

The Macro Variables inspector reflects the active local scope while playback is inside the macro and shows the restored caller values after return.

### What does `G65 ... L...` do?

`L` repeats the macro call. The accepted range is `1..9999`.

Each repetition starts again with the original G65 local arguments. Changes made by the previous repetition to `#1..#33` do not leak into the next repetition.

### How deeply can G65 macros nest?

The current implementation allows four nested G65 local-variable levels. A deeper macro nesting request produces `CALL_DEPTH_EXCEEDED` rather than silently sharing a damaged local scope.

The wider M98/G65 call-stack budget is separately limited by the general call-depth setting.

### How does M98 behave inside a G65 macro?

An M98 subprogram call inside a G65 macro shares the current macro-local level. It does not create another G65 local scope by itself.

### Are M98/M99 subprograms supported outside Macro B?

Yes.

Typical form:

```text
M98 P2000
M98 P2000 L3
...
O2000
...
M99
```

`P` must identify an existing positive integer O-program number. `L` must be a positive integer. Missing targets and invalid values produce structured subprogram diagnostics.

### Is `M99 P...` supported?

No. `M99 P` is controller-profile dependent and currently produces `UNSUPPORTED_M99_P` rather than guessing its jump semantics.

### Are Macro B variable values stored per execution step?

Yes. `ExecutionStep.variables` contains an immutable snapshot of the variable state for that occurrence of a source block. Unchanged snapshots are internally reused rather than copied for every motion.

This is what allows the GUI Macro Variables inspector to follow logical playback without re-running the CNC program.

### Does Expanded Execution export keep Macro B statements?

Expanded Execution follows the actual executed occurrence order. Macro flow and G65 calls are resolved into their resulting execution rather than exported as a second unevaluated macro program.

Subprogram/macro boundaries are preserved as execution events/comments where appropriate, while generated motion comes from the authoritative trace.

---

## FANUC turning

The turning interpreter supports FANUC Type A (default) and Type B. Select Type B in Options under **Lathe G-code system**, or pass `--lathe-gcode-system B` to a CLI command. Type B uses G90/G91 for absolute/incremental X/Z, G33 for threading, G77/G78/G79 for simple cycles, and G94/G95 for feed per minute/revolution. Type C, G66/G67 modal macro calls and G68.2/G53.1 indexed-plane operations are outside the current turning language.

### Main differences between Type A and Type B

| Operation | Type A | Type B |
| --- | --- | --- |
| Rapid | G00 | G00 |
| Linear | G01 | G01 |
| Arc CW | G02 | G02 |
| Arc CCW | G03 | G03 |
| Dwell | G04 | G04 |
| Thread cutting | G32 | G33 |
| Coordinate system / spindle clamp | G50 | G92 |
| Finish cycle | G70 | G70 |
| Rough turning | G71 | G71 |
| Rough facing | G72 | G72 |
| Pattern repeating | G73 | G73 |
| Face peck drilling | G74 | G74 |
| OD/ID grooving | G75 | G75 |
| Multiple threading | G76 | G76 |
| Turning canned cycle | G90 | G77 |
| Threading canned cycle | G92 | G78 |
| Facing canned cycle | G94 | G79 |
| Feed per minute | G98 | G94 |
| Feed per revolution | G99 | G95 |

Type A uses absolute X/Z and incremental U/W. Type B uses G90/G91 to switch X/Z between absolute and incremental; U/W remain incremental.

### What is the turning coordinate model?

Turning uses X/Z geometry. Internally, physical X geometry is radial, while programmed X can follow diameter or radius programming.

The default turning state is diameter programming.

### How do X/U and Z/W behave?

- `X` and `Z` are absolute-axis words where the active mode requires absolute programming.
- `U` and `W` are incremental turning-axis words.
- X/U conversion respects diameter versus radius mode.

Cycle expansion uses the same conversion helpers rather than treating cycle X values differently from ordinary motion.

### How are G20 and G21 handled?

The kernel normalizes physical geometry to millimetres internally.

- `G20` sets inch input scaling;
- `G21` sets millimetre input scaling.

The selected unit mode is captured per execution step so playback, statistics and export can reconstruct the executed unit context.

### Which turning arc formats are supported?

Turning uses G18 XZ circular interpolation with:

- relative or absolute I/K center coordinates, selected by Arc Type or auto detection;
- R radius programming.

Resolved arcs store analytical center, radius, sweep and direction in physical geometry.

R-programmed profile arcs remain R arcs during G71/G72/G73 roughing and G70 finishing, regardless of the selected I/K interpretation. If an I/K arc in a P/Q profile is invalid in the manually selected mode, the associated cycle emits no partial trajectory and reports the source line.

### Why can G2/G3 direction look inverted in an XZ plot?

The physical G18 orientation and the visual X/Z plot orientation are not the same coordinate view. The kernel resolves the physical arc direction and the plotting layer uses the correct XZ convention rather than treating it as XY geometry.

### Is direct A-angle turning programming supported?

Yes. On ordinary G1 turning blocks, A-angle programming can resolve a missing X or Z endpoint using the previous contour direction and programmed angle.

### Are C chamfers and corner R fillets supported?

Yes. Ordinary G1 contour blocks can include:

- `C` corner chamfers;
- corner `R` fillets.

This is distinct from `G2/G3 R`, where R is the circular interpolation radius.

### Are G32 and G33 threading motions supported?

Yes. G32/G33 are represented as synchronized threading motions in the resolved trace. Threading state is preserved into export and Stock Removal where applicable.

### What are the turning feed modes?

For turning:

```text
G98 -> feed per minute
G99 -> feed per revolution
```

The default turning feed mode is per revolution.

Per-revolution machining time is only known when a trustworthy spindle speed is also available. Otherwise statistics report unknown time rather than inventing a feed rate.

### Are G96 and G97 modeled?

Yes.

```text
G96 -> constant surface speed (CSS)
G97 -> direct RPM mode
```

In CSS mode, the S value is stored as surface speed. In inch mode the source surface-speed value is converted to metres per minute internally.

### What does G50 S do in turning?

`G50 S...` is tracked as the spindle-speed limit used with the turning spindle model. It is not treated as the milling G50 scaling cancel operation.

### Are spindle start/stop signals tracked?

Yes. M3/M4 mark the spindle running and M5 marks it stopped. Machine signals such as spindle, coolant, dwell and program end are also published in `ExecutionResult.signals`.

### Which WCS features work in turning?

The kernel supports:

- `G54-G59`;
- `G54.1 P1-P99` extended offsets;
- `G10 L2` programming of G54-G59;
- `G10 L20` programming of G54.1 offsets.

Runtime G10 changes are returned in the execution result and do not silently write application settings.

### Is G53 supported in turning?

Yes, for non-modal machine-coordinate G0/G1 motion.

A turning `G53 G2/G3` cannot be modeled by the current contract and produces `UNSUPPORTED_G53_MOTION` instead of being executed as a WCS-relative arc.

### How does G28 work?

When configured reference-return emulation is enabled, G28 resolves the intermediate programmed point and then emits the configured machine-home motion. Reference-return events are also recorded structurally.

### Is G30 the same as G28?

No. The project does not silently reuse the configured G28 home as a second reference point for G30. A controller-specific G30 reference must not be invented from G28 configuration.

### How does tool-nose compensation work?

G40/G41/G42 state is tracked in turning. When a valid configured turning tool with usable nose geometry is available, the resolved trace can be compensated deterministically.

The compensation layer works from executed motions and tool geometry rather than rewriting source text.

If the required geometry cannot be established safely, the result is not presented as verified compensated motion.

---

## Turning cycles

### Which turning cycles are modeled?

The current turning cycle layer includes:

| Type A | Type B | Purpose in the kernel |
| --- | --- | --- |
| G70 | G70 | P-Q finishing contour |
| G71 | G71 | Longitudinal roughing |
| G72 | G72 | Facing roughing |
| G73 | G73 | Pattern-repeat roughing |
| G74 | G74 | Z peck / face grooving |
| G75 | G75 | X peck / radial grooving |
| G76 | G76 | Two-line multipass threading |
| G83 | G83 | Axial peck drilling |
| G84 | G84 | Axial tapping |
| G90 | G77 | Modal longitudinal turning cycle |
| G92 | G78 | Modal threading cycle |
| G94 | G79 | Modal facing cycle |

Cycle geometry is expanded into ordinary logical motions. Those motions are then consumed by playback, statistics, Stock Removal and export.

### Do cycle motions remember where they came from?

Yes. Generated motions are marked as cycle-generated and retain source ownership such as the invoking block, source text and playback group where applicable.

This is why one source cycle block can own many logical playback motions without losing editor navigation.

### How are cycle profiles selected by P and Q?

P/Q contour cycles resolve N labels in the parsed program. The resolver handles repeated labels relative to the cycle call site rather than assuming every N label is globally unique.

For finishing, a preceding P-Q profile can be preferred where appropriate.

### Do G71/G72/G73 profile blocks support lines and arcs?

Yes. The P-Q contour is built as profile segments and can include supported linear and circular geometry. Analytical arc data is preserved where possible rather than converting every profile arc into a staircase.

### How does G70 work?

`G70 P... Q...` builds the referenced finish contour and approaches it from the actual G70 call position.

The finish path is based on the nominal P-Q profile, not the roughing-offset profile used by G71/G72/G73.

If tool-nose compensation is active and can be verified, the finishing contour uses the compensated profile.

After the finish group, the cycle returns to the saved call position using the project's deterministic turning return order.

### What form of G71 is supported?

The common two-line FANUC form is modeled:

```text
G71 U... R...
G71 P... Q... U... W... F...
```

The first line captures rough depth and retract. The second line supplies the P-Q profile, finishing allowances and feed.

### How is G71 depth interpreted?

The first-line U depth is treated as a radial depth and converted consistently into programmed diameter motion when diameter programming is active.

An empty P-Q profile or zero first-line depth produces an explicit G71 diagnostic; no partial cycle trajectory is published.

### How are G71 U/W finish allowances handled?

The second-line U and W are applied to the roughing profile before rough passes are generated.

U is signed. This matters for OD versus ID work:

- positive U leaves outside material on an OD contour;
- negative U can leave material toward the bore interior on an ID contour.

The sign is not discarded by taking an unconditional absolute value.

### How does G71 distinguish OD and ID roughing?

The cycle compares the stock-side approach and profile geometry and selects boring versus outside behavior. The same P-Q contour engine is used, but pass direction and retract direction follow the selected material side.

### What is G71 Type I behavior?

Type I is treated as monotonic longitudinal roughing. Each rough pass is parallel to Z and terminates at the P-Q roughing profile.

After the roughing passes, the implementation adds one complete pass along the already allowance-offset roughing profile. It does not incorrectly reuse the nominal finishing contour at this stage.

### Is G71 Type II supported?

A Type II profile is detected when the first P block contains both an X/U component and a Z/W component.

The implementation can follow non-monotonic/pocketed profile geometry using clipped profile segments. Controller-dependent cases are handled conservatively; unsupported geometry is not silently simplified.

### How does G72 work?

G72 uses the same P-Q profile infrastructure as G71 but performs facing roughing in Z planes.

Typical two-line form:

```text
G72 W... R...
G72 P... Q... U... W... F...
```

The first line captures axial depth and retract. The second line references the profile and finishing allowances.

### Is G72 Type II fully generic?

No. Type II is supported where the facing plane resolves to a deterministic profile span. If one facing plane produces multiple disjoint material spans that require controller-specific interpretation, execution fails explicitly with:

```text
UNSUPPORTED_G72_TYPE_II_SPANS
```

instead of choosing an arbitrary span.

An empty profile, zero pass depth, or a lone interior crossing after a closed Type II span also produces an explicit diagnostic. No cuttable Type II facing span is reported as an error rather than an empty expansion.

Repeated intersections at the same endpoint of a closed contour count as one crossing. Distinct, disjoint spans still produce `UNSUPPORTED_G72_TYPE_II_SPANS`.

### How does G73 work?

G73 is implemented as repeated shifted copies of the roughing profile.

The first line captures the total U/W pattern displacement and the R pass count. The second line provides P/Q, finish allowances and feed.

The signs of programmed U/W are preserved. The cycle does not infer displacement direction from where the tool happened to approach the contour.

### How does G74 work?

G74 supports Z-direction peck behavior and face-grooving style repetition.

A first block containing R alone can establish the retract distance. The executing block can use X/U and Z/W plus P/Q/R/F parameters.

If no X target is supplied, G74 can operate as a drilling-style Z peck at the current X.

When X repetition is requested, P controls the X step and Q controls Z peck depth. The cycle returns to its saved start using an explicit Z-first return order.

### How does G75 work?

G75 performs X-direction peck/radial grooving.

P controls the radial peck step. Q can repeat grooves along Z. If Q is omitted, a programmed Z/W selects one groove location rather than being treated as an invalid zero-step repetition.

The R value from the setup block controls retract distance, and the executing-block R value is handled as the bottom allowance where applicable.

### How is turning peck motion represented?

The kernel emits actual feed and rapid primitives for each peck/retract sequence. It does not store G74/G75 as an opaque cycle that the renderer has to understand separately.

### How does two-line G76 work?

The modeled form is FANUC-style two-line G76:

```text
G76 P...... Q... R...
G76 X... Z... P... Q... R... F...
```

The first block stores:

- packed P control digits;
- minimum radial increment Q;
- optional finish allowance R.

The second block supplies:

- final thread X;
- final Z;
- thread height P;
- first cut Q;
- optional taper R;
- lead F.

### How are G76 P/Q integer increments interpreted?

The first-block Q and second-block P/Q are treated as integer least-input increments rather than ordinary floating length words.

For metric turning they are converted in thousandths of a millimetre. Inch mode uses the corresponding 0.0001-inch increment converted to physical millimetres.

### How is G76 pass depth generated?

The thread passes use a decreasing-depth / approximately constant-chip-area progression based on the first-cut depth and square-root pass relationship, while respecting the minimum radial increment and finish allowance.

The final commanded X is authoritative for the final thread diameter.

### What do the packed G76 P digits mean here?

The packed first-line P is decoded as:

```text
P(m)(r)(a)
```

where the fields represent:

- final/spring-pass count;
- chamfer amount in tenths of pitch;
- tool/thread angle.

### Which G76 tool angles are modeled?

The supported set is:

```text
0, 29, 30, 55, 60, 80 degrees
```

Other packed angles fail explicitly with:

```text
UNSUPPORTED_G76_TOOL_ANGLE
```

For supported nonzero angles, pass start/end Z is shifted to model FANUC-style single-edge flank infeed rather than ignoring the angle digits.

### How is G76 chamfer modeled?

The packed chamfer digits are converted into an axial chamfer length based on thread lead. The final part of each thread pass is split when necessary to represent the chamfer section.

### Is G92 a modal threading cycle?

Yes.

Example:

```text
G92 X18 Z-10 F1.5
X17.5
X17.0
```

The initial G92 establishes the thread end and lead. Subsequent X/U-only blocks continue the active G92 cycle with new depths until another explicit motion/cycle mode cancels it.

Each pass expands to approach, synchronized longitudinal cutting, retract and return primitives.

### Is G90 a modal turning cycle?

Yes. G90 establishes a longitudinal rectangular turning cycle. Subsequent X/U-only blocks can continue the active cycle at new diameters until cancellation by another explicit motion/cycle code.

### Is G94 a modal facing cycle?

Yes. G94 establishes a facing rectangular cycle. Subsequent Z/W-only blocks can continue the active cycle at new face positions until cancellation.

### What cancels G90/G92/G94?

A non-motion modal code such as G96/G97 does not cancel the active cycle.

Another explicit motion or cycle code cancels the old modal turning cycle unless that same cycle is explicitly present in the block.

### Are turning G83 and G84 modal?

Yes. G83 and G84 remain active for subsequent eligible coordinate blocks until G80, another cycle state, or a tool change cancels them.

### How does turning G83 behave?

G83 is an axial Z drilling cycle.

- If Q is supplied, Z pecks are generated.
- If Q is absent, the kernel does not invent peck depth; it emits one feed stroke to depth and a rapid return.
- Optional X positioning is handled before the axial stroke and restored afterward.

### How does turning G84 behave?

G84 is an axial tapping cycle. The downstroke and return are synchronized feed motions; the return is not represented as a rapid move.

### Does P dwell in turning G83/G84 create geometry?

No. Dwell is a time/control event, not a spatial segment. The backplot geometry therefore does not invent a motion for the dwell itself.

### What happens if a modal drilling/tapping cycle is left in an invalid state?

The runtime can report an `UNCLOSED_CYCLE`-class execution error rather than silently carrying an impossible modal cycle to program end.

---

## FANUC milling

### Which milling G functions are recognized?

This table lists the G codes recognized by the `fanuc_mill` kernel. Details and limits are explained below.

| G code | Function in the kernel |
| --- | --- |
| G00 | Rapid positioning |
| G01 | Linear interpolation |
| G02 / G03 | Clockwise / counterclockwise circular interpolation |
| G04 | Dwell signal; no spatial motion |
| G10 | Program WCS offsets (`L2`, `L20`) |
| G15 / G16 | Cancel / enable polar coordinate programming |
| G17 / G18 / G19 | Select XY / XZ / YZ plane |
| G20 / G21 | Inch / millimetre input units |
| G28 | Reference return using the configured home |
| G40 / G41 / G42 | Cancel / left / right cutter-radius compensation |
| G43 / G49 | Track / cancel tool-length state; G43 does not apply H geometry to the plotted path |
| G43.4 | TCP G0/G1/G2/G3 motion for the angled AC/BC table profiles, including Cartesian arcs with rotary interpolation; combination with G68.2 is unsupported |
| G50 / G51 | Cancel / enable coordinate scaling |
| G52 | Local coordinate shift |
| G53 | Non-modal machine-coordinate motion |
| G54–G59 | Select work coordinate system |
| G54.1 P1–P99 | Parsed and selected; the GUI has no offset setting, so the offset is zero unless the program sets it with G10 L20 |
| G65 | Call a Macro B program |
| G68 / G69 | Enable / cancel coordinate rotation |
| G68.2 / G53.1 | Tilted working plane / tool-axis orientation (3+2, `fanuc_mill` with two-axis table-table, head-head or head-table kinematics) |
| G73 | High-speed peck drilling cycle |
| G80 | Cancel canned cycle |
| G81 | Drilling cycle |
| G82 | Drilling cycle with dwell |
| G83 | Full-retract peck drilling cycle |
| G84 | Tapping cycle |
| G85 | Boring cycle with feed return |
| G86 | Boring cycle with spindle-stop signal |
| G90 / G91 | Absolute / incremental programming |
| G94 / G95 | Feed per minute / feed per revolution |
| G98 / G99 | Return to initial / R plane in canned cycles |

### Which milling M functions are recognized?

| M code | Function in the kernel |
| --- | --- |
| M00 / M01 | Stop / optional-stop signal |
| M02 / M30 | End program |
| M03 / M04 / M05 | Spindle clockwise / counterclockwise / stop signals |
| M06 | Tool-change event for the selected T number |
| M07 | Recognized; no machine-specific coolant action is modeled |
| M08 / M09 | Coolant on / off signals |
| M19 | Spindle-orientation signal; S on this block is an angle, not spindle RPM |
| M29 | Prepare rigid tapping; S on this block sets spindle RPM for the following G84 |
| M98 / M99 | Call / return from subprogram |

Unknown M codes produce `UNSUPPORTED_M_CODE` warnings. Recognized M codes describe trace signals and program flow; they do not simulate machine hardware.

`M29 S500` followed by `G84` marks rigid tapping in the trace. With `G95`, `F1.5` is 1.5 mm per revolution in metric mode; with `G94`, the equivalent feed at 500 RPM is `F750` mm/min. `G80` clears the rigid-tapping preparation. M29 syntax and whether it is required depend on the machine configuration. The kernel records synchronization semantics but does not simulate an encoder or spindle acceleration.

### What basic milling motion is modeled?

The milling kernel supports XYZ rapid, linear and circular/helical motion in the active G17/G18/G19 plane.

Resolved `TraceMotion` is full 3D geometry even though many CNC constructs are planar.

### How is indexed rotary milling handled?

Select a profile in **Settings → Rotary kinematics** or pass `--kinematics PROFILE_ID` with `--lang fanuc_mill` in the CLI. The GUI selection is stored as `CNC/ROTARY_KINEMATICS`. The profile maps programmed A/B/C addresses to signed rotary axes. G90 assigns an absolute rotary angle; G91 adds an increment. For the checked table profiles, later XYZ motions, resolved arcs and milling cycles are transformed into the fixed WCS display frame, and playback orients the tool preview at the resolved tool-tip point. WCS axes themselves do not rotate.

G28 reference return and non-modal G53 use machine-axis coordinates first, including repeated returns and G91 increments, then map their trace points into the indexed display frame. The active WCS remains selected after G53. An A/B index records an event and changes subsequent geometry; the kernel does not currently generate a sampled tool-tip sweep during the rotary movement. The plot omits a connector across that position change.

For the checked `4ax_table_c` profile, concurrent X/C feed blocks and C-only blocks map their endpoints into the fixed XY plane. Here X is the programmed radius and C is the angle about Z; the source program provides the contour sampling. These blocks record `ROTARY_MOTION` rather than an index event.

### Which rotary profiles have been checked?

The `4ax_table_a` and `4ax_table_b` profiles have been compared with the programs in `tests/fixtures/milling/indexed_table_a.nc` and `tests/fixtures/milling/indexed_table_b.nc`. The `4ax_table_c` profile is checked against `tests/fixtures/milling/indexed_table_c.nc`: its X/C contour overlays the program's first XY contour within 0.05 mm at the sampled endpoints. The fixture files are reference inputs, not definitions of a machine. Automated checks also cover A/B angle signs, G90/G91, and repeated G28/G53 behavior.

The catalog also contains head, mixed head/table and other two-rotary-axis profiles. They remain in JSON with `enabled: false` and are hidden from the GUI. The enabled profiles are `4ax_table_a`, `4ax_table_b`, `4ax_table_c`, `5ax_table_ac_angled` and `5ax_table_bc_angled`; **None** is the default selection. The angled AC/BC tables support indexed 3+2 through G68.2/G53.1. The schema does not specify rotary pivot locations, tool-center-point behavior or controller-specific offsets.

The JSON editor validates a profile and saves it to `rotary_profiles.json` beside the user's `config.ini`. It does not change the installed catalog. A selected profile defines the table/head axis and sign explicitly; the software cannot infer those properties from an A, B or C word. Execution steps retain the selected WCS and the configured rotary angles. G10 L2 and WCS changes preserve the current machine position after a table index.

If the user profile file is damaged or invalid, the GUI and JSON editor open with the installed profiles. Saving a valid edit recovers the override file and preserves its original bytes in a neighboring `rotary_profiles.json.invalid-*.bak` file. Valid edits retain the other valid overrides. Kernel and CLI loads remain strict until the file is repaired.

### What happens when indexed geometry cannot be resolved?

A changed A/B/C address without a selected profile or an address absent from the selected profile stops milling execution with an explicit diagnostic. Simultaneous rotary/XYZ movement and non-rapid rotary interpolation also stop for the indexed A/B profiles; the checked `4ax_table_c` planar X/C feed contour is the exception. This is the current implementation, not a general FANUC restriction. A/B/C with an unsupported position-changing G-code also stops execution. Unknown M-codes and G41/G42 that cannot be verified because of missing tool or unsupported contour data produce warnings and let execution continue. G30 is not modeled as G28: its controller-specific second reference point is not inferred from the configured G28 home.

For `4ax_table_c`, G41/G42 cutter compensation is unsupported. Execution continues, but the X/C plot shows the programmed tool-tip path without cutter-radius offset and reports `UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION`. G40 cancels the modal request. Do not treat this plot as a verified compensated contour.

A selected profile makes the calculation repeatable; it does not by itself prove that the profile matches a physical machine. Inspect diagnostics and the supported contract before using `ok` or `complete` as an export decision.

### Which milling canned cycles are modeled?

The current set includes:

```text
G73
G80
G81
G82
G83
G84
G85
G86
```

The common cycle runtime returns generated geometry, modal updates, signals and final position as one outcome.

### What is the difference between G73 and G83 milling peck cycles?

G73 is high-speed peck drilling with short intermediate retract behavior. G83 returns to R between pecks, then rapidly re-enters at clearance d above the previous depth before continuing at feed. Reentry is limited to the R plane. The kernel option `milling_g83_clearance` sets d in millimetres, including inch programs; it must be finite and non-negative. The default 1.0 mm is a modeling assumption because the controller setting cannot be read from the program. This changes G83 feed distance and cycle-time statistics; turning G83 and native SINUMERIK CYCLE83 keep their separate behavior.

For milling drilling cycles, a depth above R reports `INVALID_DRILLING_DEPTH`. Z equal to R remains valid and produces no drilling feed stroke.

### How is G82 dwell represented?

G82 includes its dwell semantics, but dwell itself does not create spatial geometry.

### How is milling G84 represented?

G84 tapping returns from depth as synchronized feed motion rather than rapid motion.

### How is milling G86 represented?

The cycle models spindle-stop semantics together with its drilling motion/return behavior.

### What do milling G98/G99 mean?

For milling canned cycles, G98/G99 select cycle return behavior. They are not the turning feed-mode meanings of G98/G99.

### What are milling feed modes?

For milling:

```text
G94 -> feed per minute
G95 -> feed per revolution
```

Statistics only compute trustworthy machining time where the required feed/spindle information is known.

### Which work coordinate systems are supported?

The kernel supports:

- `G54-G59`;
- `G54.1 P1-P99`;
- runtime `G10 L2`;
- runtime `G10 L20`.

### How does G10 behave under G91 in milling?

For runtime work-offset programming, incremental mode updates the existing selected offset instead of silently replacing it with the raw incremental value.

### How does G52 work?

`G52 X/Y/Z` sets a local coordinate-system shift for subsequent motion. The G52 control block itself does not move the tool.

### How do G68 and G69 work?

G68 enables coordinate rotation around the programmed center in the active plane. G69 cancels the rotation.

In SINUMERIK ISO-M mode (`G291`), the modeled `G68` subset requires `G90` and has no `I/J/K` vector. `G68` with `G91` angle semantics or with any `I/J/K` 3D rotation vector is recognized but unsupported. `G69` remains supported.

The active transform applies to later endpoints and I/J/K arc vectors. Enabling or cancelling the transform does not itself create a motion segment.

G68.2 X/Y/Z I/J/K defines a 3+2 tilted working plane with Z-X-Z Euler angles. Select a kinematics profile with two distinct rotary axes first; supported topologies include table-table, head-head and head-table. G53.1 must be the next standalone block: it solves the selected profile's rotary angles to align the physical tool axis with functional +Z. An unreachable orientation stops with a diagnostic. G69 cancels the plane while retaining the indexed rotary position. This model applies only to `fanuc_mill`. Explicit A/B/C addresses during the tilted plane and simultaneous G68 rotation are unsupported. G53 and G28 reference motions use machine coordinates. Expanded NC export is unavailable for these programs; Full Program preserves the source.

### How does G51/G50 scaling work?

Milling G51 supports:

- uniform scaling with P, where `P1000` means factor 1.0;
- per-axis factors through I/J/K.

G50 cancels milling scaling.

For SINUMERIK ISO-M, `G51` uses the modeled 0.001 scale-factor weighting (`P2000` means a factor of 2.0). Machine-specific alternative weighting is not modeled.

The scaling center is interpreted as absolute coordinates even under G91, and omitted center axes use the current position.

Axis-specific scaling of an arc can turn a circle into non-circular geometry. The kernel reports that unsupported case instead of approximating it as a circle.

### Is G53 supported in milling?

Yes. G53 is non-modal machine-coordinate motion. It does not overwrite the active WCS for later ordinary work-coordinate blocks. An absolute zero axis target such as `G53 Z0` resolves to the configured machine home on that axis; non-zero absolute and incremental targets retain their machine-coordinate meanings.

### Is G28 supported in milling?

Yes. The configured reference-return path is resolved through the execution kernel rather than handled only by the GUI. For indexed milling, the intermediate and home targets are resolved on machine axes before their trace points are transformed for display. `G91 G28 Z0` returns the Z axis to the configured home Z.

With 4/5-axis table kinematics, G28/G53 use the current table orientation without resetting ABC. For example, with home Z=500 and zero WCS offset, a B-table return targets global Z=500 at B0 and Z=-500 at B180. A Z-only reference segment that crosses the WCS centre plane stops execution with an error; check machine home Z and the WCS offset. This check does not detect collisions with a part model.

After G28/G53 in a 4/5-axis program, the next approach can start a separate trace segment in the new table orientation. No connecting line is drawn between those segments. Ordinary three-axis paths remain continuous, including reference returns.

### Is continuous five-axis TCP (`G43.4`) supported?

For `fanuc_mill`, continuous `G0/G1` tool-center motion with simultaneous linear and rotary axes is supported on the angled AC and BC table profiles. Activating TCP preserves the current physical point in the plotted trace. With TCP off, indexing retains programmed XYZ and changes the displayed table frame. `G2/G3` TCP arcs may interpolate configured rotary axes while programmed XYZ remains the authoritative tool-center path; start/end tool orientations and rotary events are retained. Combining TCP with `G68.2` remains unsupported. This is toolpath interpretation, not a complete machine or collision simulation.

### How are milling arcs programmed?

Milling supports:

- relative IJK center offsets;
- absolute IJK center coordinates;
- R radius programming.

The selected source interpretation is resolved into one analytical arc center/radius/sweep representation.

### What does Arc Type autodetection do?

When enabled, the kernel examines milling or turning IJK arcs in source occurrence order before final geometry resolution. Turning X and I values are converted from diameter coordinates to physical radial coordinates for this comparison.

For each IJK arc it compares relative and absolute-center interpretations using the configured arc tolerance. The first unambiguous candidate fixes the IJK mode for that execution.

R-only arcs are ignored during detection because they do not distinguish IJK conventions.

If every candidate is ambiguous, the selected fallback mode is used. CLI analysis/batch currently use relative IJK as the fallback.

Selecting an Arc Type in the GUI manually overrides auto detection for the current document. The Auto Detect setting remains enabled for the next opened document. In turning, an I/K arc interpreted with the wrong center mode reports `INVALID_TURNING_ARC_CENTER`; selecting Radius mode for an arc without an R word reports `TURNING_ARC_REQUIRES_R`.

### Can one program mix R arcs with IJK arcs?

Yes. Arc-type detection determines the IJK interpretation. An R-only block remains an R arc regardless of that decision.

### Are full circles supported?

Yes. Analytical full circles are represented directly by the kernel.

When Expanded Execution is asked to emit R-format arcs, a full circle is exported as two exact R semicircles because one R block cannot uniquely represent a full circle.

### Is helical interpolation supported?

Yes. Circular interpolation can include motion along the axis normal to the active plane where the supported geometry contract permits it.

### What does G16/G15 polar programming do?

`G16` enables milling polar-coordinate endpoint programming and `G15` returns to ordinary Cartesian programming.

The active G17/G18/G19 plane determines the polar plane:

- first in-plane axis = radius;
- second in-plane axis = angle in degrees.

### How does polar G90 work?

In absolute mode, the active work/local origin is used as the pole. Programmed polar radius and angle are absolute polar values.

### How does polar G91 work?

When entering `G91 G16`, the current position becomes the pole. Later G91 polar words increment modal radius or angle, and omitted components retain their previous polar value.

### Do G20/G21 scale the polar angle?

No. The radius is a length and follows units. The angle remains degrees.

### Are polar G2/G3 arcs supported?

The implemented polar circular contract requires R radius programming. I/J/K center programming while G16 polar mode is active is rejected with an explicit diagnostic rather than guessed.

### Is G12.1/G13.1 polar interpolation supported?

No.

### How does milling cutter compensation work?

G40/G41/G42 uses configured milling tool diameter and works on supported line, arc and compatible helical contours.

For indexed table A/B milling, the offset is calculated in the local programmed working plane before the completed geometry is transformed into the fixed WCS plot. Execution continues when the tool or contour cannot be verified, with `UNVERIFIED_CUTTER_COMPENSATION` reported. The 3D view uses left drag to pan and middle drag to orbit around the cursor, as in CNCEditor; the table B 3D/ISO preset shows +Y vertically upward, +X upward-right and +Z downward-right while table A keeps the vertical mill preset.

For `4ax_table_c`, G41/G42 is not resolved. The trace retains the programmed X/C tool-tip coordinates and emits `UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION`; G40 ends the modal request. This limit is specific to the current C-table implementation.

The compensation engine resolves:

- entry transitions;
- steady offset geometry;
- line/arc and arc/line joins;
- corners;
- G40 exit transitions.

Inserted transition motions preserve execution-step ownership so editor navigation and export remain coherent.

### What does `UNVERIFIED_CUTTER_COMPENSATION` mean?

The source requested G41/G42, but the kernel could not prove a valid compensated path with the available tool/configuration/geometry.

The system marks that state explicitly rather than presenting uncompensated geometry as verified compensation.

### Is G43 tool-length geometry applied?

No. G43/G49 and H values are tracked for execution/export context, but H-offset geometry is not currently applied to the resolved toolpath.

That limitation is intentional and should not be interpreted as a simulated tool-length-compensated machine position.

---

## Tool libraries and tool discovery

### Where are persistent tools stored?

Turning and milling tools are stored in:

```text
%LOCALAPPDATA%\easy-gcode-plot\tools.db
```

This SQLite database is authoritative for Saved Library tools.

### What is the difference between Current Program and Saved Library?

**Current Program** is temporary state for the open CNC program. Literal T selections can be discovered from source and assigned geometry without modifying the persistent library.

The operation identifies the fallback tool type first. A matching T number in the corresponding Saved Library then supplies the actual geometry, including its saved type and dimensions. If no valid matching record exists, discovery uses source comment dimensions and the operation-based default. Milling `T02` matches `T2`; turning `T202` matches `T0202`, while different packed offsets remain distinct. Manual Current Program edits take priority on subsequent recalculations.

**Saved Library** is persistent and is committed to `tools.db` only when the Tool Library window is accepted.

### Does opening a program write discovered tools to the database?

No. Tool discovery is temporary.

### How are turning tool numbers represented?

Turning selections retain the packed tool/offset form such as:

```text
T0909
```

Milling selections use the tool number, for example `T03` becomes tool key `T3`.

### Can comments describe tool geometry?

Yes. Tool discovery recognizes useful inline and nearby comments, for example:

```text
(T3 D=6. CR=0. - FLAT END MILL)
(OD ROUGH R0.8)
(ID ROUGH R0.8)
(GROOVE H4)
(DRILL)
(TAP)
(THREAD)
(BALL)
(FACE MILL)
(CHAMFER)
```

Dimensions are interpreted using the units active at the tool selection.

### What happens when no explicit type hint is present?

Operation context supplies a practical temporary default where possible:

- milling G81-G83 -> drill;
- milling G84 -> tap;
- native SINUMERIK CYCLE81/CYCLE82/CYCLE83 -> drill;
- native SINUMERIK CYCLE84 -> tap;
- turning G32/G33/G76/G92 -> thread tool;
- otherwise standard milling or turning fallback geometry.

Native cycle classification uses the controller AST, including modal MCALL, cancellation and tool changes. Cycle names in comments or MSG text do not classify an operation. An operation's type takes priority over a conflicting comment type hint; an automatically matched saved tool keeps its own geometry. The preliminary scan does not execute macros or infer physical dimensions from a toolpath. CLI/API callers can supply a library snapshot through `execute_program(..., library_tools=...)`; execution does not load a local SQLite library implicitly.

Shared GUI/CLI execution builds Program/AST once, resolves tools from that same object before motion execution, and then calculates the trace. Discovery does not run another frontend pass. The Cython/Python scanner still extracts source comments and literal tool candidates; it does not independently execute controller operations.

Finding a saved tool or assigning a default does not guarantee verified compensation. `UNVERIFIED` describes an unproven compensated path, not merely an unknown tool. G41/G42 can remain unverified with missing geometry, an unsupported tool or an invalid entry/path, including native SINUMERIK named tools without matching numeric geometry. Operation-based defaults existed before automatic library lookup.

### Are macro T expressions discovered as literal tools?

No. Discovery intentionally does not evaluate `T#1` or `T[expr]`. Literal tool discovery and full CNC execution are separate concerns.

### Which turning tool geometries are stored?

The turning library uses nine canonical geometry types:

- Diamond 80;
- Diamond 35;
- Square;
- Round;
- Triangle;
- Groove;
- Thread;
- Drill;
- Tap.

OD, ID and Face are UI filters for available tracing orientations, rather than different geometry classes. They do not choose the material-removal side or change Stock Removal results for the same trace and physical geometry.

### Which milling tools can be previewed?

The milling tool model includes flat, bull-nose, ball, tapered ball, face, slot, chamfer, drill and tap geometry.

### How are milling tool lengths defined?

The milling editor stores two metric lengths:

- `fluteLength`: cutting length measured from the tip; must be greater than zero.
- `bodyLength`: non-cutting length from the end of the cutting portion to the holder; may be zero.

Length to holder is `fluteLength + bodyLength` and is read-only in the editor. The compatibility field `length` is derived from this sum; there is no `shaftLength`. The Inches switch changes display units; SQLite and JSON/CSV exports retain millimetres.

For face and slot mills, `fluteLength` sets the cutting head height; `cuttingHeight` is retained only for legacy records. For tapered ball mills, the taper ends at `fluteLength`, followed by a cylindrical body extending to the holder. Both library and playback previews use this geometry.

The library preview shows the cutting part in gold and the non-cutting body in gray. In 3D, the default cutting color is yellow; the body is near-white in the dark theme and dark gray in the light theme to distinguish it from gray STL models. The tool color option changes only the cutting part. Tools without an explicit length split use one color.

Existing tools with only `length` keep their total and preview without an inferred split. The editor identifies these records as legacy. Editing unrelated fields keeps the unsplit record; entering cutting/body lengths defines the new partition. Loading the library does not rewrite the database.

Tool comments can supply both dimensions, for example `(FLAT END MILL D10 FL25 BL15)`. Comment dimensions follow the units active at tool selection. A comment providing only `L`/`LENGTH` retains an unsplit total. Automatically discovered tools without length dimensions use editable defaults, not measured dimensions.

### Does CLI execution load the GUI Saved Library?

No. CLI runs use the same temporary source-based tool discovery used for a newly opened program. GUI manual Current Program assignments and the Saved Library are not silently loaded into the CLI execution.

This matters for G41/G42 verification: inferred tool dimensions should be reviewed before treating a compensated CLI trace as authoritative.

---

## Interface, editor and playback

### What are the two main GUI panels?

The left side is a QScintilla editor with syntax highlighting, line numbers, search/replace and cleanup functions. The right side is an OpenGL trajectory view with axes, grid, camera controls, trajectory picking and playback.

The milling 3D view uses an orthographic CAD projection. Rotating from Top, Front or Left keeps parallel lines parallel and preserves apparent size across depth.

### How does an imported STL affect toolpath visibility?

In solid mode, the STL surface hides toolpath segments behind it. The feature-edge wireframe has no solid surface to occlude those segments. This changes only visibility in the plot, not the resolved trajectory geometry. Manage imported models in **Settings → STL Objects**; the guide below covers transforms, sections, picking and measurements.

### How do I use the STL Objects panel?

The **Settings → STL Objects** dock edits imported STL scene objects without changing the G-code program. Import a model with **File → Import STL**. The dock lists each imported model; select a row before applying an operation. Choose **Base point**, **Position**, **Transform**, **Circular array**, **Rectangular array** or **Section** from the operation selector. The four compact buttons at the top apply Undo, Redo, Statistics and Delete to the STL scene.

#### How do I import and select STL models?

Use **File → Import STL** to load an ASCII or binary mesh. **File → Recent STL** reopens a recent model. Each import appears as a separate row in the dock; selecting a row makes it the target of the operation controls and statistics. **Delete** removes the selected model. **File → Clear STL** removes all STL models. These commands affect imported scene objects, not the editor contents or G-code trajectory.

#### What do Undo, Redo, Statistics and Delete do?

The STL **Undo** and **Redo** history is separate from text-editor undo. It records scene edits such as adding another model, changing a base point, moving, rotating, mirroring, scaling, creating arrays, applying or clearing a section, and deleting an object. The first imported model establishes the scene baseline, so Undo does not close the panel or remove that first model. **Statistics** opens copyable measurements for the selected object. **Delete** removes only the selected row; use **File → Clear STL** to remove the complete STL scene.

#### How do STL base points and bounding-box picks work?

The **Base point** selector chooses the point used as the pivot for rotation, mirroring and scaling:

- **Center** sets it to the center of the source mesh's bounding box.
- **Bounding-box corner** sets it to the source mesh's minimum X, Y and Z corner and displays the transformed object's axis-aligned bounding box in the Base Point color.
- **Origin** sets the point to model coordinates `(0, 0, 0)`.
- **Custom** enables the X/Y/Z fields; enter coordinates in model space and press **Set base point**.

When the bounding box is displayed, its eight corners are picking points. Hold **Shift** and left-click a corner in the 3D plot to move the base point there. The picked point becomes larger and cyan; the other seven corner markers remain in the Base Point color. Picking changes the base point to a custom point, while keeping the box visible so another corner can be picked. Choosing Center or Origin exits bounding-box picking.

The **Position** page shows the current base point's world position. Enter a target X/Y/Z there and use **Move base point here** to place the pivot at those world coordinates. Moving changes the object's transform while preserving its shape.

#### How do I position and transform an STL model?

On **Transform**, select an axis and angle to rotate around the current base point. **Mirror** reflects the object across the plane whose normal is the selected X, Y or Z axis, passing through the base point. **Scale** applies a uniform factor around that point. These operations preserve the source STL and update the scene object's transform; they do not modify the original file on disk.

#### How do STL arrays work?

**Circular array** creates the requested number of copies around a selected axis and center, spread over the total angle. With **Rotate copies** enabled, each copy rotates with its position. When disabled, each copy keeps its orientation and distributes the current base point around the circle. A full 360-degree array spaces copies evenly without duplicating the first copy at the end.

**Rectangular array** creates copies along X, Y and Z. Set the copy count and step for each axis; the resulting array includes the original object. Array creation is one STL history action and can be undone.

#### How do I make a 3D section through an STL model?

On **Section**, choose X, Y or Z for the cutting plane, enter its coordinate and choose which side to keep. The initial coordinate is the midpoint of the selected model's world-space bounding box along that axis. **Apply section** clips the solid in 3D and closes the cut where the mesh produces a closed contour; the cut model remains visible over the source toolpath. **Clear section** restores the full STL. Applying and clearing a section are undoable STL scene actions.

#### What does STL Statistics report, and how do I display inches?

**Statistics** reports surface area, volume, center of mass, world-space coordinate bounds and per-axis lengths. Bounds are written explicitly as `Xmin`, `Xmax` and `Length` (and likewise for Y and Z). The **Inches** checkbox at the lower left of the dialog converts all reported lengths, coordinates, area and volume while leaving the mesh unchanged. Unchecked values display in millimetres; checked values use inches, square inches and cubic inches.

STL files do not encode a unit system, so these labels are display units and do not determine the source model's real-world scale. Surface area and bounding box are available for open meshes. Volume and center of mass require a closed mesh with consistently oriented faces; otherwise the dialog reports them as undefined.

### How do I change letter case or mark optional blocks?

Use **Edit → Uppercase** (`Ctrl+Shift+U`) or **Edit → Lowercase** (`Ctrl+U`), or their toolbar buttons, to convert selected text. With no selection, they convert the entire editor document. Their shortcuts can be changed in Options.

Select one or more blocks and press **Ctrl+/** to add `/` at the start of each selected nonempty block. Press **Ctrl+Shift+/** to remove one leading `/` from each selected block. Without a selection, these commands do nothing. Both shortcuts are fixed and cannot be assigned to another command. The slash is the FANUC optional block skip marker; whether such blocks execute depends on the Block Skip setting.

### How do I print the plot?

Use **File → Print** (`Ctrl+P`) or the Print button in the File toolbar. The app prints sharp vector lines in the current camera orientation, fitted to a landscape page. Printing ignores the playback slider and does not hide lines behind an imported STL. In **Options → Plot**, you can show or hide rapid moves, render them dashed or solid, and color all moves by tool; Print follows those choices. **FAQ** opens with `F3`, and **Grid** toggles with `F4` by default.

### Which fixed views are available?

Top, Front and Left are orthographic views. The ordinary 3D view is perspective. Starting free orbit from a fixed view returns to perspective.

### How does playback relate to the kernel?

Playback advances through resolved logical motions from the current `ExecutionResult`. It does not re-parse each source line as the slider moves.

### What do Step Backward and Step Forward do?

They move by one logical motion, including generated motions from cycles and Macro B-expanded execution.

### Why can many playback motions map to one source line?

One source block can emit many motions. Examples include:

- turning cycles;
- milling canned cycles;
- Macro B loops that execute the same source line repeatedly;
- compensated transition geometry.

Playback tracks execution occurrence and source ownership separately.

### How do I locate a plotted move in the editor?

Use Shift+Click near the trajectory. The application selects the owning source block and moves the logical-motion slider to the corresponding motion.

### Does automatic refresh move the editor caret?

Normal execution/plot refresh is intended to update the result without using editor caret movement as a side effect. Playback/navigation can intentionally select source locations.

### What happens when Auto Update is too expensive?

Auto Update has a sampled-segment limit. Large edits may be left pending until explicit Refresh so typing remains responsive.

If source changes while a refresh is running, the stale calculation is cancelled/ignored and a new refresh is queued.

### What does Cancel stop?

The execution dialog covers the expensive source-to-result pipeline, including reading, parsing, execution, tool discovery, trace sampling and final plot publication. Cancellation is cooperative and checked throughout the execution budget.

### What CNC editing assistants are included?

The GUI contains:

- Hole Calculator;
- Pocket Calculator;
- Snippets.

Hole and Pocket Calculator are milling-only. Snippets is available in both machine modes.

### What does Hole Calculator generate?

It generates coordinate blocks for circular or rectangular/grid hole patterns. It does not invent the complete surrounding drilling-cycle safety logic.

### What does Pocket Calculator generate?

It can generate circular or rectangular milling fragments with configurable stepover, depths, safe/reference Z, feed, direction, clearing strategy, helical entry and finishing pass.

The generated fragment is a starting point, not a machine-safety certification.

### Where are snippets stored?

On Windows, snippets are normally stored in:

```text
%LOCALAPPDATA%\easy-gcode-plot\snippets.db
```

Older text snippets can be imported once while the original files are retained as backup.

An unreadable or invalid UTF-8 legacy snippet is skipped with a log warning; valid files are still imported. The skipped original remains in the backup directory. Invalid ordering metadata falls back to filename order.

---

## Options and scene configuration

### How do I change the interface language?

Open **Settings → Options → General**. In **Language**, choose **English** or **Russian**, then press **OK**. Restart Easy G-Code Plot to apply the language change; the application displays a restart notice. This setting changes the interface language, not the CNC dialect used to execute a program.

### How do I change the theme?

Open **Settings → Options → General**, select **Light** or **Dark** in **Theme**, and press **OK**. The theme is applied immediately without restarting. Language and theme choices are saved in the application configuration.

### Where do I set work coordinate systems and home values?

Open **Settings → WCS**. This is a separate dialog from Options.

| Setting | How to use it |
| --- | --- |
| G54–G59 | Enter the X/Y/Z work offsets for each system. The program selects the active system with its G54–G59 command; editing a row does not insert that command into the program. |
| Home (G28) | Enter the configured reference-return coordinates and use the home configuration checkbox to indicate whether they are configured. These values are used by the modeled G28 return. |
| Turning X/Z | In turning mode, X fields use diameter values; Y fields are disabled. Z is an axial coordinate. |
| Milling X/Y/Z | In milling mode, all three coordinate fields are available and X is a linear coordinate. |
| Inches | Switch the displayed and entered lengths between millimetres and inches. Existing physical values are converted rather than reinterpreted as another unit. |

Press **OK** to apply the values and recalculate the program. **Cancel** leaves the stored values unchanged. G54.1 extended offsets have no fields in this dialog; they remain zero unless set by supported program commands such as G10 L20.

### How do I set turning stock dimensions?

In turning mode, open **Settings → Stock**. Enter the initial blank dimensions before starting Stock Removal.

| Control | Meaning |
| --- | --- |
| Outside diameter | Initial outside diameter of the blank. |
| Inside diameter | Initial bore diameter; use zero for a solid blank. |
| Length | Axial length of the blank. |
| Stock front Z | Absolute Z coordinate of the front face. The rear face is at `front Z − length`; this field is not just an allowance thickness. |
| Accuracy | Stock-model resolution. Higher accuracy gives a finer model and requires more processing time. |
| Inches | Display and enter dimensions in inches instead of millimetres, preserving their physical size. |
| Run Stock Removal when Play is pressed | Enable material-removal playback when pressing Play. |
| Reset to Auto | Return to dimensions estimated from the current program's cutting trace. |

Press **OK** to apply manual dimensions; **Cancel** discards the dialog edits. Manual dimensions remain active until **Reset to Auto**, **New**, or opening another program restores automatic sizing. Stock Removal requires a calculated, complete turning program and configured tool geometry. See [Turning Stock Removal](#turning-stock-removal) for automatic sizing and supported tools.

### Is Stock Removal available for milling?

No. Material removal is currently implemented for turning only. Milling does not yet have stock-removal simulation.

For milling reference geometry, load an STL model and open **Settings → STL Objects**. The panel provides model positioning, rotation, copying, arrays, sections and statistics. It displays reference models alongside the toolpath; it does not subtract milling tool motions from the STL. See the [Interface, editor and playback](#interface-editor-and-playback) section for the panel workflow.

---

## Turning Stock Removal

### What is Turning Stock Removal?

It is an axisymmetric material-removal preview based on the resolved turning trace and configured cutter geometry.

It is not a machine simulation.

### How is automatic stock estimated?

The resolved G1/G2/G3 cutting trace provides the minimum outside diameter and length. Rapid G0 outliers are ignored, cycle-generated cutting motions are included, and G18 arc extrema are evaluated analytically.

### Can stock dimensions be overridden manually?

Yes. **Settings → Stock** allows explicit outside diameter, inside diameter, stock length, absolute front-face Z and accuracy/resolution. See [How do I set turning stock dimensions?](#how-do-i-set-turning-stock-dimensions) for the fields and playback setting.

Manual values persist until Reset to Auto, New or opening another program returns the stock model to program-derived sizing.

### Which tools remove material?

The supported turning tool geometries include the nine canonical tool-library types. Stock Removal follows the resolved trace, tracing orientation and physical cutter geometry. OD/ID/Face checkboxes only filter the tracing choices in the tool editor; changing these filters does not change removal for the same trace and cutter geometry.

The cutter's bounded swept footprint removes only the material it intersects. Separate remaining material rings are retained, including the outside wall during G71 boring. Stepping backward and replaying the same motions restores the same stock section. For grooves, **Groove geometry** selects radial or face geometry independently of these checkboxes.

### How are threads represented in Stock Removal?

Synchronized G32/G33, modal G92 and G76 cutting motions use a deterministic longitudinal thread-section model rather than sweeping the complete insert body as a generic solid.

The programmed X defines root depth, F defines pitch/lead, and configured thread geometry shapes the section.

The displayed thread insert is a separate fixed silhouette shared by Tool Library and the Stock Removal overlay: a triangular body with three small 60-degree cutting teeth and recessed shoulders. Its active tracing point is anchored to the programmed tool position. In the standard lathe view, the external P8 vertex points down and the internal P6 vertex points up.

Only the insert diameter scales this silhouette. The reference contour is D12; entering D20 scales every coordinate by `20 / 12`, approximately 1.667. EX, RC and the thread profile angle do not deform the displayed body. The angle remains part of the removal calculation but is hidden in the editor; the library summary shows the tracing orientation. These display changes do not rewrite SQLite tool records.

### Does Stock Removal detect machine collisions?

No. It does not model chuck, turret, fixtures, acceleration or full machine geometry.

---

## Statistics and Tokens/Macro Variables

### What does Toolpath Statistics contain?

Statistics are derived from the resolved trace and include:

- logical motion counts;
- length breakdown;
- known and unknown machining time;
- average feed;
- assumed rapid speed;
- XYZ bounds;
- per-tool sections.

The Statistics window displays an HTML summary. Use the tool selector to switch between the whole program and one tool. Export HTML saves the summary and all tool sections with the same selector and the current display units. Only the exported report adds a static SVG projection below the table: XY for milling, XZ for turning. The tool selector also filters the drawing. The GUI export uses the same prepared geometry, page fitting and line styles as Print. Every motion is included. The NC source is not embedded.

The Inches display switch converts displayed values without changing stored physical geometry. CLI equivalent: `python -m app analyze program.nc --html statistics.html` (add `--inches` for imperial display).

### Why can machining time be UNKNOWN?

The kernel avoids fabricating a physical feed rate. A common case is feed-per-revolution motion without a known spindle RPM.

### What is the Tokens tab?

Tokens displays parsed/evaluated words, source position, execution status and diagnostics. Suspicious or unsupported rows are highlighted and can be exported to CSV.

### What is the Macro Variables tab?

Macro Variables shows the variable snapshot at the current logical playback position.

It follows:

- assignments;
- loops;
- G65 local scopes;
- M98 execution inside a macro;
- restored caller locals after M99.

It uses existing execution snapshots and does not re-run the CNC program while the playback slider moves.

### Why can Macro Variables be unavailable?

If no execution result exists, there is no variable history to show. If the source editor has changed since the displayed execution result, the result is stale and the variable inspector waits for Refresh rather than mixing new source with old runtime state.

---

## Export

### Which GUI export families exist?

The project contains exporters for:

- Turning Full Program;
- Milling Full Program;
- Expanded Execution;
- turning cycle groups;
- Plot Data;
- DXF trajectory;
- Tool List text report.

### Are exporters separate G-code interpreters?

No. Exporters consume `ExecutionResult`, resolved motions and execution-step/event metadata.

They do not execute a second independent CNC model.

### What does Full Program mean?

For SINUMERIK native with **As source** or **SINUMERIK native** selected, Full Program instead formats the original program without flattening its geometry. Native functions, expressions, modal commands, CYCLE800 and TRAORI remain intact. The CLI equivalent is `--mode full --target-dialect sinumerik_native`.

Full Program is a flattened executable-style export that preserves controller/context blocks and comments where appropriate while replacing geometry with authoritative executed geometry.

Subprogram calls are flattened in actual execution order rather than copied as an untouched source tree.

The turning and milling Full Program exporters deliberately retain more controller structure than Expanded Execution, but they are still built from the executed result rather than being simple source-file copies.

### What does Expanded Execution mean?

Expanded Execution serializes the resolved logical execution trace.

That means it can flatten:

- subprogram calls;
- Macro B loops and branches;
- generated canned-cycle motions;
- cycle expansions;
- resolved compensation where verified.

It can also emit structural execution events as comments/control records where appropriate.

### What is the analysis banner?

Expanded text output can include:

```text
(EXPANDED FROM LOGICAL MOTION TRACE - ANALYSIS ONLY)
```

The banner exists to distinguish generated resolved execution from original controller source.

### What is turning cycle-group export?

CLI mode `cycles` exports only executed turning-cycle groups. Each generated group is annotated and emitted using the execution-step unit/X-programming state.

It is only available for `fanuc_turn` and is not a generic milling export mode.

### What is Plot Data export?

Plot Data serializes the resolved logical trace as point-to-point output intended for geometry consumption rather than controller-structure preservation.

### What does DXF contain?

DXF is generated from resolved geometry. Rapid and cutting motion use separate layers.

Turning is exported in the plot-aligned Z/X representation. Milling exports 3D line/arc/circle geometry where representable.

### Does DXF parse the G-code again?

No. It consumes resolved trace geometry.

### Which NC formatting options exist?

Shared export options include:

- absolute/incremental coordinates where supported;
- force addresses;
- sequence numbers;
- sequence start and increment;
- sequence-number spacing;
- spaces/no spaces between words;
- leading zeroes (`G01` versus `G1`);
- comments/no comments;
- safety line;
- milling arc representation.

### Which milling Expanded arc output modes exist?

The CLI contract exposes:

```text
auto
ijk-relative
ijk-absolute
radius
linearized
```

`auto` detects the source IJK convention per program and chooses a compatible resolved export representation.

### What happens when a full circle is exported in R mode?

It is emitted as two exact semicircular R arcs.

### Can Expanded NC be converted between millimetres and inches?

Yes, for source programs whose non-motion controller operands can be preserved safely.

The conversion scales resolved geometry at the export boundary, including coordinates, arc geometry, I/J/K, radius and feed values represented in the motion trace.

### Why can explicit unit conversion be rejected?

Some control blocks contain dimensioned operands that are not represented solely by resolved `TraceMotion`. Current export therefore refuses explicit NC unit conversion when execution contains source operands for:

```text
G4
G10
G28
G30
G50
G51
G52
G53
G68
G69
G92
G96
```

This is a conservative safety rule. The exporter does not rewrite such operands by heuristic text scaling.

### Can Full Program be forced to mm or inch?

No. CLI Full Program export currently accepts only `--units auto`.

Semantic unit normalization is an Expanded Execution feature.

### What units does DXF use?

DXF can be emitted in millimetres or inches. `auto` keeps the current default DXF behavior, which is millimetres.

### Can comments be removed from export?

Yes. The shared `include_comments`/`--no-comments` option applies to source comments retained by Full Program and generated comments/annotations in expanded output.

### Are exports written atomically by the CLI service?

Yes. The CLI export service writes to a temporary file in the output directory and then replaces the final output path. A failed write does not intentionally leave a partially written final file.

### Can CLI export overwrite the source file?

No. Source and output must be different paths.

---

## SINUMERIK 840D input

Arc-center interpretation follows the executed controller mode: native and ISO-M (`G291`) use incremental IJK centers; native I=AC/J=AC/K=AC explicitly selects absolute centers. Mixed `G290/G291` input resolves each arc in its active mode; document arc settings and automatic detection do not override these semantics. Configured native rotary axes are supported by the bounded TCP/indexing subset; rotary A/B/C in G291 remains rejected.

Structured execution and CLI/batch reports include `source_dialect` (`fanuc` or `sinumerik`) independently of the shared `fanuc_mill` geometry language. This identifies the source family, not one controller mode for the entire mixed program. Unsupported SINUMERIK G/M diagnostics contribute concrete codes to batch summaries; unsupported syntax and features do not become fabricated G/M entries.

The SINUMERIK scope is **visualization of trajectories using native commands and cycles emitted by CAM postprocessors**. Full support for the complex internal Siemens macro language is outside scope; implementing it is not feasible for a project maintained by one person. Executing subprograms from SDI mode is currently unavailable. Opening an SPF file is supported as a document, but arbitrary Siemens subprogram invocation is not.

MPF/SPF documents preserve the selected rotary profile. Settings and Options remain available. Native CYCLE800/TRAORI supports the angled AC/BC table profiles; incompatible profiles, axes and ISO-M rotary commands produce kernel diagnostics.

### What SINUMERIK support is included?

The application supports a bounded native Siemens milling subset (`G290`, also the initial mode of MPF/SPF files) and ISO Dialect M (`G291`). Both use the shared milling kernel and resolved trace. SINUMERIK ISO Dialect T is not supported.

| Native function | Current behavior |
| --- | --- |
| `G0/G1`, `G2/G3`, `G17/G18/G19` | XYZ positioning, linear moves and arcs in the selected plane; `CR=` radius arcs, including negative radius for a major arc |
| `G90/G91`, `G54`–`G59` | Absolute/incremental coordinates and work offsets |
| `G70/G71` | Inch/metric lengths; feed units remain unchanged |
| `G700/G710` | Inch/metric lengths and feed units; modal numeric F is retained |
| `G93` | Inverse-time feed: each cutting motion takes 1/F minutes, including rotary TCP motion; F must be positive. Reprogram F when switching G93/G94/G95. Cycles and cutter compensation are unsupported in G93 |
| `G40/G41/G42` | Modeled cutter-radius compensation using the configured tool |
| `DIAMON/DIAMOF/DIAM90` | Warning-only; all coordinates are executed with DIAMOF semantics |
| `CHF/CHR/RND/RNDM/FRC/FRCM` | Parsed with warnings; no geometry/feed changes. Chamfers, rounding and corner feed are not simulated. RNDM=0 is recognized without geometric effect; resolved NC export is rejected |
| `G60/G64` | Exact-stop / continuous-path metadata; acceleration, stop time and blending are not simulated |
| `G500` | Modal work-offset deactivation with coordinate rebasing; zero G500/base frame by default, API `wcs_offsets[500]` can supply translation; OEM base-frame rotations, mirroring and scaling are not modeled |
| `DEF REAL`, direct scalar assignments | Bounded underscore-named `DEF REAL` scalars used by CAM setup and direct scalar assignments are accepted |
| `T`, `M6`, `D0..D12`, `S`, basic M codes | Tool change, modeled cutting-edge selection/cancellation, spindle and coolant signals; controller-specific offset tables are not simulated |
| Named tools with `M6` | Named tool changes are accepted; if cutter geometry is unavailable, `G41/G42` remains unverified rather than assuming a radius |
| `G0 SUPA ... D0` | Nonmodal absolute XYZ and configured A/B/C positioning, independent of G91. In the application's reference-coordinate model, zero XYZ addresses use the configured G28/SUPA return coordinates, as FANUC G53 does. WCS and the current rotary frame determine the displayed return. Rotary zero means A/B/C=0; `SUPA G0 B0 C0 D0` requires a compatible BC profile |
| `G64`, `MSG(...)`, `WORKPIECE(...)`, `;` comments | Path-control/display metadata and comments; no blending or stock geometry is generated from these declarations |
| `SETMS(1)`, `FNORM`, `COMPOF`, `CYCLE832` | Accepted CAM setup/control statements; `CYCLE832` is ignored without geometry or display events |
| `MCALL CYCLE81/82/83/84(...)` | Modal Z drilling/tapping in `G17/G40`, triggered by subsequent XY blocks; bare `MCALL` cancels the cycle |
| `CYCLE81/82` | Drilling and rapid return, with modeled seconds-based dwell for `CYCLE82`; safety plane is `RFP + SDIS`, return plane is `RTP`; the four-argument `CYCLE81` form is accepted |
| `CYCLE83` | Modeled first depth, amount degression, minimum peck depth, chip-breaking/full-retract options and reentry clearance |
| `CYCLE84` | Single-pass metric right-hand tapping in `G94`: explicit positive `PIT`, `_PITA=0/1`, `SDAC=3`, Z axis and positive `SST` equal to programmed `S`; equal `SST1` or zero/omitted. Feed = pitch × rpm; feed withdrawal to `RFP+SDIS`, rapid return to `RTP`, optional dwell in seconds |
| `TRAORI` / `TRAFOOF` | GUI/CLI/kernel TCP via the common angled AC/BC table core; G0/G1/G2/G3 with configured numeric A/B/C and R references; incremental IC supported; `DC` selects the shortest absolute rotary approach, while an exactly 180-degree ambiguity is rejected |
| `CYCLE800` | GUI/CLI/kernel static frames: modes 57/54/39/27/30/45, ST200000/200001/220000/220001, DIR-1/0/1; legacy 15-argument ST0/R_DATA calls are accepted; active-frame reset via empty/bare call or TC="0" |

Native CR radius arcs require a SINUMERIK source document: use .mpf/.spf. A .nc or unsaved document uses FANUC syntax and cannot interpret CR= as a native radius address. Native X/Y/Z=IC(...) is incremental independently of G90/G91. MSG() is accepted.

`CYCLE84` accepts the 24-argument CAM call and shortened numeric declarations. Depth uses `DP` or positive relative `DPR` in compatibility mode; explicit absolute-depth `AMODE=2/1001002` requires `DP`. Deep tapping, `MPIT`/thread tables, nonmetric pitch units, spindle orientation/technology options, left-hand tapping and unequal entry/withdrawal speeds are outside this subset and produce diagnostics. Spindle synchronization/reversal is represented by logical signals, without angular spindle simulation. The parameters follow [Siemens section 1.7](https://m3.tuc.gr/EQUIPMENT/CTX310/840D%20G-CODE.pdf); paired fixtures `tapping_sin840d.mpf` / `tapping_fanuc.nc` verify G84 geometry and native trace replay.

Cython accelerates contiguous literal position runs, with per-block capability validation before state changes. Controller-specific declarations and G290/G291 switches interrupt the current run, after which eligible positions resume acceleration. Positions inside an active MCALL cycle stay on the Python reference path until cancellation. Metadata or a native cycle elsewhere in the file does not disable acceleration for the whole program.

Numeric R assignments (`R1=500`) and direct references in `F/S/XYZ/IJK=Rn`, `CR=Rn`, `TURN=Rn` and supported cycle parameters are available. Siemens R state is independent of FANUC `#` variables and is fresh for each execution. Undefined references fail before the block changes state; cycle references are validated at declaration and each hole. Arithmetic such as `R1=R2+10` or `F=R1*0.8`, arrays, system variables, Siemens control flow and arbitrary subprogram calls remain unsupported. SPF recognition does not enable subprogram execution.

Native `TURN=n` adds integer 0..999 complete revolutions to the base `G2/G3` arc (IJK or CR, G40, no active MCALL), according to [Siemens](https://support.industry.siemens.com/cs/attachments/104985512/802Dsl_BPF_1006_en.pdf). The trace keeps one analytical arc/helix with the total sweep. Rendering, playback and statistics retain those turns; DXF uses a sampled polyline, and FANUC/ISO exporters split arcs only during serialization. The existing stock material-removal timeline supports turning; this release does not add milling stock removal. Standalone native `G4 F...` uses seconds and leaves modal feed unchanged; spindle-revolution dwell is not modeled.

The GUI/CLI/kernel also supports a bounded TRAORI/TRAFOOF TCP subset on `5ax_table_ac_angled` and `5ax_table_bc_angled`. Configured numeric A/B/C assignments and direct R references follow G90/G91; rotary TCP arcs retain analytical Cartesian geometry and orientation endpoints. The GUI preserves rotary selection and executes native AC/BC programs through the same kernel. CYCLE800 builds its own Siemens rotation matrix and uses the common TWP solver/rebasing. FR0/1/2 are logical retract requests, with no OEM retract trajectory; FR_I must be zero/blank and DMODE0/1 is supported. DIR chooses the principal first-table-joint branch. IC(numeric/direct R) is incremental independently of G90/G91. ORI*, TRANS/AROT, FGROUP, FL[], FGREF[], SPOS, CUT3DC/CUT3DF/CUT3DFF and path-control extensions are parsed with unverified warnings; their effects are not simulated. Arbitrary Siemens subprogram calls remain fail-closed. Cancel TCP before G290/G291; active TCP transitions are rejected. Native MCALL and G41/G42 cannot be activated under TCP, and active MCALL must be cancelled before rotary positioning. No multi-axis controller conversion is enabled.

Regression fixtures are `tests/fixtures/milling/contur_2d_sin840d.mpf` / `contur_2d.nc` and `cycles_sin840d.mpf` / `cycles_fanuc.nc`. Comparisons account for CAM rounding and actual differences in retract commands and peck parameters. A native `CYCLE83` with a decreasing step is not identical to FANUC `G83 Q1`. Native trace export to FANUC is tested by re-executing the exported geometry. Native SINUMERIK -> FANUC milling **Full Program** now uses the kernel's normalized execution words and re-executes the target to verify geometry, feed mode and machine signals. Supported units G70/G71/G700/G710 and G93 are preserved. Safe metadata warnings remain in source diagnostics; CYCLE81/82/83/84 conversion is described below; unsupported frames, orientation and rotary/TCP semantics block conversion. FANUC -> native Full Program remains unavailable.

Conversion places G291 in the first frame, before all comments and headers. It preserves G43/H and G49. O0001 becomes (O0001); standalone % delimiters are removed. Actual rotary/TCP/TWP programs remain unsupported. Controller H-table offsets are not applied to plotted geometry.

In `G291`, common integer milling G codes, unit selection, coordinate systems, selected canned cycles and `G50/G51` are accepted. Extended work offsets use `G54 P1..P48`; source `G54.1` and other decimal G codes are rejected, though `G54 Pn` is normalized internally to the milling kernel's `G54.1 Pn` form. Ordinary `G91` incremental positioning is supported. G68 is limited to a standalone 2D form with `G90` active, only the center axes of the active plane and `R`, and no `I/J/K`; incremental-angle and 3D-vector forms are rejected. `G69` is supported. Macro B flow and unsupported ISO functions stop with diagnostics. `G51` uses the modeled `P/1000` scale weighting; machine-specific alternative weighting is not modeled.

`G290` selects the native subset above; `G291` selects ISO-M. Switches must occupy standalone blocks. Cancel native cutter compensation and `MCALL` before `G291`; cancel incompatible ISO cycles, transforms and extended offsets before `G290`.

### How are MPF and SPF files detected?

The GUI Open/Save filters include `.mpf` and `.spf`. The CLI and batch scanner include both extensions by default and select SINUMERIK for every `.mpf`/`.spf` file independently of its contents; execution starts in native mode and processes standalone `G290/G291` switches. Use `--lang fanuc_mill` for milling analysis; the language option selects the milling geometry model and does not turn on full Siemens support. Mixed folders can still use `--extensions` to control discovery.

### Can FANUC milling programs be converted to SINUMERIK?

Yes. **Full Program** converts the supported three-axis `fanuc_mill` subset to **SINUMERIK ISO Dialect M (`G291`)**. Choose **MILL FULL PROGRAM → SINUMERIK 840D ISO-M (G291)** in the GUI, or use:

```powershell
.\easy_gcode_plot_cli.exe export fanuc_part.nc --lang fanuc_mill --mode full --target-dialect sinumerik_iso -o iso_part.mpf
```

The converter preserves source blocks, supported ISO milling cycles and tool/spindle/coolant commands, including `G43 H...` and `G49`. It inserts a standalone `G291` before the header, converts the `O` program number to a comment and removes standalone `%` delimiters. The legacy target `sinumerik840d` is an alias for ISO-M in Full Program mode. The reverse **SINUMERIK ISO-M → FANUC Mill** direction removes the standalone `G291` and validates the FANUC result.

Only the verified ISO-M subset is accepted: unsupported commands, Macro B control flow, unverified compensation and actual rotary/TWP/TCP programs block conversion. Selecting a rotary profile alone does not block an XYZ-only program. Full Program does not translate FANUC into native Siemens commands such as `CYCLE800` or `TRAORI`.

### Can SINUMERIK native milling programs be converted to FANUC?

Yes, within the supported **three-axis native milling subset**. MPF/SPF inputs start in native mode; `--lang fanuc_mill` selects the shared milling geometry model. Choose **MILL FULL PROGRAM → FANUC milling** in the GUI, or use:

```powershell
.\easy_gcode_plot_cli.exe export native_part.mpf --lang fanuc_mill --mode full --target-dialect fanuc_mill -o fanuc_part.nc
```

Full Program retains the order of source operations and comments, normalizing supported native syntax from kernel execution. Parameters and expressions become evaluated values at their use sites; it does not translate Siemens macro source into Macro B. Supported units `G70/G71/G700/G710`, inverse-time feed `G93`, ordinary XYZ motion and arc geometry are converted to FANUC words. Numeric tool changes use `T... M6`; native `D1` uses the active tool number for `H`/cutter `D`, and `D0` cancels length compensation with `G49`. The selected comment style is applied, and FANUC comments are uppercased.

| Native drilling operation | Full Program FANUC output |
| --- | --- |
| `MCALL CYCLE81/82(...)` | `G81` without dwell, `G82 P...` with dwell; `P` is milliseconds. Hole positions remain modal where equivalent. |
| `MCALL CYCLE83(...)` | Explicit local `G0/G1` pecks preserving the executed first depth, degression, minimum step, feed factor and return/reentry planes. It is not replaced by a different constant-step `G83 Q...`. |
| Supported `MCALL CYCLE84(...)` | `M29` and `G99 G84`, preserving tapping feed, dwell and synchronized feed withdrawal to the safety plane, then `G80` and rapid return to `RTP`. |
| Bare `MCALL` | Cancels the target canned cycle with `G80` when active and restores the source motion mode. |

Cycle depths, safety plane `RFP + SDIS`, return plane `RTP` and per-hole parameter changes come from the executed source. CYCLE84 remains limited to the kernel's metric, right-hand, single-pass tapping subset. CYCLE83 expansion is confined to the drilling holes; the rest of the Full Program is not flattened into a trace.

An empty/bare `CYCLE800` used to reset a frame does not make a three-axis program multi-axis and is accepted. **Active CYCLE800 3+2, rotary 4-axis, TRAORI/TCP 5-axis and their rotary arcs are not converted.** Execution/plotting support for these features is separate from export support. Named tools, source control flow and unmodeled geometry-changing commands also block Full Program conversion. Safe metadata warnings alone do not block it.

The exported text is executed again in the target dialect before writing. Conversion checks the physical motion path, feed mode/feed and modeled machine signals. Only monotone subdivisions of the same axis-aligned rapid path are normalized for cycle return-plane comparison; changed cutting geometry or feed still fails validation.

### How do Full Program and Resolved conversion differ?

**Full Program** keeps source operation structure within the supported subset. **Resolved / Expanded Execution** serializes executed three-axis geometry, expanding cycles and evaluating variables; source loops, expressions and WCS structure are not retained. Resolved output uses physical XYZ in a single zero-offset G54 frame. Targets are `fanuc_mill`, `sinumerik_iso` and `sinumerik_native`; ISO starts with `G291`, while native uses explicit absolute arc centers `I=AC/J=AC/K=AC`. Resolved conversion also rejects rotary/TCP geometry.

```powershell
.\easy_gcode_plot_cli.exe export native_part.mpf --lang fanuc_mill --mode resolved --target-dialect fanuc_mill -o native_trace.nc
.\easy_gcode_plot_cli.exe batch-export C:\Fanuc --lang fanuc_mill --mode full --target-dialect sinumerik_iso -o C:\SiemensISO
.\easy_gcode_plot_cli.exe batch-export C:\SiemensNative --lang fanuc_mill --mode full --target-dialect fanuc_mill -o C:\FanucOutput
```

GUI, single-file CLI and `batch-export` share the conversion API. Batch export uses `.mpf` for SINUMERIK and `.nc` for FANUC and records per-file failures. Existing native source can also be formatted without dialect conversion: choose **As source / SINUMERIK native** or `--mode full --target-dialect sinumerik_native`. This preserves native expressions, CYCLE800 and TRAORI. It does not enable FANUC → native Full Program conversion; native target serialization is available separately in Resolved mode.

### Is SINUMERIK lathe supported?

**No. SINUMERIK turning/lathe is not supported yet**, in either native mode or ISO Dialect T. Siemens turning execution and conversion to/from FANUC turning are unavailable. SINUMERIK support described here is milling; the supported FANUC turning kernel is a separate mode.

---

## CLI

### Does the CLI use the same kernel as the GUI?

Yes.

The standalone CLI is an interface over the same parser, Macro B runtime, machine execution, cycles, compensation and export modules.

### Which commands exist?

Current commands are:

```text
parse
trace
analyze
batch
export
batch-export
```

### What does `parse` do?

`parse` executes one program through the normal kernel and prints a readable summary of instructions, motions and diagnostics.

Example:

```powershell
.\easy_gcode_plot_cli.exe parse program.nc --lang fanuc_turn
```

### What does `trace` do?

`trace` executes one program and can write detailed JSON including resolved motions.

JSON and HTML destinations must differ from the source program and from each other, including aliases of the same file. Collisions are rejected before writing. Input decoding and read/write failures return exit code 2 with an error message. JSON output is committed atomically. GUI program and Tool List export also reject the open source as a destination; use Save/Save As to save source edits.

```powershell
.\easy_gcode_plot_cli.exe trace program.nc --lang fanuc_turn -o trace.json
```

### What does `analyze` do?

The exported HTML report always uses a light theme. The Statistics dialog follows the application theme. GUI report and program exports display success or failure notifications after writing. Playback tail highlighting follows the current logical motion, including all its sampled arc segments, using the current-move color from Options; it also works while stepping backwards and during Stock Removal playback.

`analyze` executes one program and prints trace statistics plus diagnostics. With `-o`, it writes analysis JSON.

```powershell
.\easy_gcode_plot_cli.exe analyze program.nc --lang fanuc_mill -o analysis.json
```

### What does `batch` do?

`batch` analyzes every discovered NC file under a directory and writes JSON/CSV reports.

Add `--html C:\Reports\html` to save a separate statistics report with a tool selector and static XY/XZ SVG for each input, using the same API as single-file `analyze`. Subdirectories and full filenames are preserved; `--inches` changes report units. Without `--lang`, `.mpf/.spf` select milling SINUMERIK and other files keep the turning default. Explicit `--lang` overrides this for the whole batch.

```powershell
.\easy_gcode_plot_cli.exe batch C:\Programs --lang fanuc_mill -o C:\Reports
```

### What does `export` do?

`export` executes one file and sends it through the shared NC/DXF export service.

```powershell
.\easy_gcode_plot_cli.exe export program.nc --lang fanuc_turn -o expanded.nc
```

### What does `batch-export` do?

`batch-export` discovers a directory tree and calls the same single-file export service for every input program.

For indexed A/B programs, choose a profile with `--kinematics PROFILE_ID` when all files use one machine, or pass `--kinematics-map profiles.json` for different machines. Both `batch` and `batch-export` accept the map. It is a JSON object from input-relative paths to profile IDs, for example `{"a.nc":"4ax_table_a","sub/b.nc":"4ax_table_b"}`. Use `--mode full` to preserve the rotary NC words. Without a profile, affected files fail with `ROTARY_KINEMATICS_REQUIRED`; indexed expanded NC export is also rejected. Full indexed NC is preserved verbatim, so formatting options that would otherwise be ignored are rejected. DXF uses resolved geometry and the selected profile.

```powershell
.\easy_gcode_plot_cli.exe batch-export C:\Programs --lang fanuc_mill -o C:\Normalized
```

### Are single export and batch export different exporters?

No. They use the same `ExportRequest`, validation and `export_file()` pipeline.

Directory export is orchestration around the single-file service.

### Which dialect names are used?

```text
fanuc_turn
fanuc_mill
```

There is no separate `sinumerik` `--lang` value. SINUMERIK MPF/SPF input is detected from its extension independently of its contents, then the milling kernel is selected with `--lang fanuc_mill`.

### What are the exit codes?

Normal successful/acceptable CLI execution returns zero. Failed/incomplete single execution, batch `ERRORS`, batch `NO_FILES` and export failures return a nonzero code (currently 2 for the command-level error states).

### How do I see every option and default?

Use:

```powershell
.\easy_gcode_plot_cli.exe --help
```

or command-specific help, for example:

```powershell
.\easy_gcode_plot_cli.exe batch-export --help
```

Top-level help also prints the subcommand help sections.

---

## Batch analysis

### What does batch analysis validate?

Each discovered file is executed through the same authoritative analysis setup as single `analyze`.

Per-file reports include:

- status;
- `ok` / `complete`;
- file size and line count;
- motion count;
- executed-block count;
- diagnostic counts;
- unsupported G-codes;
- unsupported M-codes;
- full diagnostic records;
- elapsed time.

For rotary milling, JSON reports also include `kinematics_definition` and `kinematics_fingerprint` (SHA-256). They capture the effective profile used by that execution, including normalized table/head axis vectors and their order. CSV reports store the same definition as JSON text. A profile ID alone is not enough to reproduce a calculation when user overrides differ. Reporting does not reload the current catalog after execution.

### Which batch statuses exist?

```text
CLEAN
WARNINGS
ERRORS
NO_FILES
```

`CLEAN` means no diagnostics were emitted.

`WARNINGS` means execution is valid/complete but diagnostics remain.

`ERRORS` means at least one file is invalid/incomplete or contains an error-level diagnostic.

`NO_FILES` means discovery found no matching programs.

### Which extensions are scanned by default?

```text
.nc
.cnc
.ptp
.mpf
.spf
.tap
.txt
```

Scanning is recursive unless `--top-level-only` is supplied.

### Can files without a normal NC extension be discovered?

Yes, when the default extension set is used. The scanner also recognizes likely text CNC programs whose first data contains an O-program header or multiple G/M blocks.

Binary-looking files are not treated as NC text.

### Is discovery deterministic?

Yes. Paths are sorted by normalized relative path so the report order does not depend on filesystem enumeration order.

### Can I restrict extensions?

Yes:

```powershell
--extensions .nc,.tap
```

When a custom extension set is supplied, content-based discovery of arbitrary filenames is intentionally not used.

### What is aggregated in the batch summary?

The report aggregates:

- file status counts;
- total diagnostics;
- error and warning totals;
- diagnostic-code frequencies;
- unsupported G-code occurrence/file counts;
- unsupported M-code occurrence/file counts;
- total elapsed time.

### What files are written?

The default report names are:

```text
batch_report.json
batch_report.csv
```

CSV is UTF-8 with BOM for convenient spreadsheet opening.

### Does a bad input file stop the whole batch?

A read/decode failure becomes a per-file `FILE_PROCESSING_ERROR`, and processing continues.

Unexpected internal analyzer failures are not intentionally swallowed as fake user diagnostics. Programming regressions should remain visible.

### Are there preset batch scripts?

Yes.

Windows:

```powershell
.\scripts\ps1\batch\batch_mill.ps1
.\scripts\ps1\batch\batch_turn.ps1
```

Linux:

```bash
bash scripts/sh/batch/batch_mill.sh
bash scripts/sh/batch/batch_turn.sh
```

They run the already-built CLI executable and write reports below the system temporary directory. They do not build or run the test suite.

---

## Batch export

### What problem does batch export solve?

`batch-export` applies one validated export contract to a complete directory tree.

Typical uses include:

- expanding execution;
- normalizing sequence numbers;
- adding/removing spaces;
- removing comments;
- converting supported resolved programs between mm and inch;
- changing milling arc representation;
- generating a directory of DXF trajectories.

### Does batch export modify the input files?

No. Output must be a separate directory.

The output directory may not be the input directory or a child of it, preventing recursive self-processing.

### Is the source directory hierarchy preserved?

Yes.

Example:

```text
input/
  part1.nc
  machine_a/
    part2.tap
```

NC output becomes:

```text
output/
  part1.nc
  machine_a/
    part2.nc
```

DXF output uses `.dxf`.

### What happens if two source names map to one output name?

The batch is rejected before writing ambiguous outputs. For example, two sibling inputs whose different source extensions would both become the same `.nc` destination are detected as a collision.

### Does one export error stop every file?

Normal per-file read/export/value failures become an `ERRORS` file entry and processing continues.

A successfully executed file with diagnostics is exported and marked `WARNINGS` under the current policy.

An execution that is not `ok` or not `complete` does not produce an output file.

### What files describe the batch export?

The output root contains:

```text
batch_export_report.json
batch_export_report.csv
```

The manifest includes source/output relative paths, status, motion counts, execution counts, diagnostics, effective output units, effective milling arc type and elapsed time.

### What are batch-export statuses?

Per file:

```text
EXPORTED
WARNINGS
ERRORS
```

Overall:

```text
CLEAN
WARNINGS
ERRORS
NO_FILES
```

### Which export modes are available from the CLI?

NC mode:

```text
expanded
full
cycles
```

`cycles` is turning-only.

DXF ignores NC-only mode/formatting controls and rejects them if explicitly supplied.

### Which options are intentionally rejected in Full Program mode?

Full Program does not accept explicit:

- unit conversion other than `auto`;
- arc-type selection;
- coordinate-mode conversion;
- force-addresses;
- safety-line control through the CLI contract.

The goal is to avoid pretending those transformations are semantically equivalent to Expanded Execution.

### Which options are rejected for turning cycle export?

Cycle export is turning-only, accepts `--units auto`, and rejects Expanded-only semantic controls such as arc-type, coordinate-mode conversion and force addresses.

### Can sequence start/increment be supplied without sequence numbers?

No. Explicit sequence start, increment or spacing requires `--sequence-numbers`.

### Are there preset batch-export scripts?

The development tree includes Windows/Linux batch-export presets for milling and turning under the same `scripts/ps1/batch` and `scripts/sh/batch` areas as batch analysis.

They are intended to run the built CLI, not to rebuild the application.

---

## Configuration

### Where is application configuration stored on Windows?

```text
%LOCALAPPDATA%\easy-gcode-plot\config.ini
%LOCALAPPDATA%\easy-gcode-plot\tools.db
```

Snippets use their own SQLite store under Local AppData.

### What is stored in `config.ini`?

Application/UI preferences include items such as:

- language;
- theme;
- document encoding;
- editor settings;
- Auto Update;
- maximum generated motions;
- compensation options;
- arc tolerance and milling arc autodetection;
- Block Skip behavior;
- plot colors and geometry display;
- stock settings;
- playback speed;
- hotkeys;
- comment style.

### Is `tools.db` replaceable by old JSON values in config.ini?

No. `tools.db` is authoritative. Legacy tool JSON in configuration is not used as a fallback write target for a current database.

### Where is the log file?

When logging is enabled:

```text
%LOCALAPPDATA%\easy-gcode-plot\main.log
```

### What does DEBUG logging add?

DEBUG logging includes additional execution, rendering, camera, option and Stock Removal timing information. Slow stock frames are rate-limited so logging does not create an even larger performance problem.

---

## Troubleshooting

### The plot is empty

Check:

- selected machine mode;
- execution diagnostics;
- WCS/home configuration;
- whether the program contains supported motion;
- whether a previous unsupported position-changing block left position unknown.

### Macro B motion is missing

Inspect the first diagnostic. Common causes include:

- undefined variable;
- missing GOTO label;
- missing O-program target;
- unmatched WHILE/END;
- G65 argument error;
- call-depth/resource limit.

Use Tokens/Macro Variables to inspect the execution state at the relevant logical occurrence.

### My G65 M/S/T words did not start spindle/coolant/change tool

That is intentional. On a G65 block those words are macro arguments, not machine side effects.

### Cutter compensation is not visible

Confirm that:

- G41/G42 is active;
- the selected tool was discovered or configured;
- its geometry is valid;
- the contour type is supported.

Inspect diagnostics for an `UNVERIFIED` compensation state.

### G43 appears in the source but the plotted Z does not include tool length

G43/G49 and H are tracked, but tool-length offset geometry is not currently applied to the trace.

### G71 leaves material on the wrong side

Check the sign of the second-line U allowance and whether the contour is OD or ID. The project intentionally preserves signed U semantics.

### G72 Type II reports an error

A facing plane can contain multiple disjoint profile spans whose exact selection is controller-dependent. Such a case is rejected as `UNSUPPORTED_G72_TYPE_II_SPANS` rather than guessed.

### G76 reports `UNSUPPORTED_G76_TOOL_ANGLE`

The packed P angle must currently be one of:

```text
0, 29, 30, 55, 60, 80
```

### Batch shows `UNSUPPORTED_M_CODE` but the geometry looks correct

The M-code is not modeled as a machine effect. Batch keeps the geometric trace while warning that the complete real-machine behavior is not verified.

### Export unit conversion is refused

Expanded NC unit conversion is conservative. If the program contains a source control block with dimensioned operands that cannot be safely reconstructed from the resolved trace, export refuses the conversion instead of scaling source text heuristically.

### Batch-export says the output directory is invalid

The output root must be outside the input directory tree. This prevents exported files from being discovered and exported again during the same run.

### A large program does not update while typing

Use Refresh. Auto Update intentionally avoids continuously rebuilding a trace above the configured automatic sampled-segment threshold.

### The GUI says the current execution is stale

The editor text changed after the displayed `ExecutionResult` was created. Refresh before using execution-dependent information such as Macro Variables or export.

---

## Development and architecture

### How is the CNC kernel organized?

The important packages are:

```text
app/gcode/kernel/api/
app/gcode/kernel/frontend/
app/gcode/kernel/geometry/
app/gcode/kernel/runtime/
app/gcode/kernel/turning/cycles/
app/gcode/kernel/milling/
app/gcode/kernel/milling/cycles/
app/gcode/kernel/compensation/
```

### What belongs in `frontend/`?

The frontend owns:

- comment stripping;
- word lexing;
- Macro B-aware expressions;
- flow-node parsing;
- source blocks;
- AST/model construction;
- native parser acceleration.

The lexer is bracket-aware so Macro B function names and `GOTO` are not misread as CNC address words.

### What belongs in `runtime/`?

Runtime owns shared execution mechanics such as:

- Macro flow;
- G65 local scope;
- M98/M99 dispatch;
- modal-group validation;
- signals and structural events;
- cycle contracts;
- resource limits;
- turning trace construction;
- cycle expansion orchestration.

### Why are turning cycles separate files?

Each major cycle has a focused implementation under `turning/cycles/`, while common dispatch/expansion machinery lives under runtime. This keeps G70-G76 geometry testable without building one monolithic interpreter function.

### What belongs in `milling/`?

Milling state, motion execution, polar programming and canned-cycle execution live under the milling package. Native milling execution accelerates selected motion paths without creating different semantics.

### What belongs in `compensation/`?

Turning tool-nose and milling cutter-radius compensation are deterministic geometry layers applied to resolved source motions.

They do not belong to the OpenGL renderer.

### What belongs in `app/gcode/export/`?

The export package owns:

- shared options;
- formatting;
- turning full export;
- milling full export;
- expanded trace export;
- DXF;
- unit scaling;
- single-file CLI export service.

Export consumes the execution result rather than reinterpreting G-code.

### What does `program_execution.py` do?

It is the shared application setup path used to execute a program with the same tool-discovery and kernel configuration used by GUI/CLI workflows.

### What does `batch.py` do?

It performs deterministic file discovery and repeatedly invokes authoritative execution to construct analysis reports. It does not contain a second G-code analyzer.

### What does `batch_export.py` do?

It is directory orchestration around the same `export_file()` service used by single-file CLI export.

### Which native components exist?

The project builds native extensions for:

- frontend parsing;
- selected milling execution paths;
- tool discovery.

The Python contract remains authoritative. Native and Python paths are regression-tested for parity where applicable. `app.native` caches parser, discovery and executor availability and import reasons. Source checkouts support fallback; frozen releases require all three extensions and fail explicitly if one is absent or its DLL cannot load. No runtime build or dependency installation is performed.

`parser_statistics()` exposes total/native/fallback blocks for the most recent successful parse in the current context, counting actual fallback callbacks. Uncommon source line separators and oversized literal words use the Python reference parser to preserve parity; ordinary LF/CRLF numeric programs keep the native scanner.

CLI parse/trace/analyze/batch do not load ezdxf. The DXF backend is imported only when DXF export is executed; a missing backend produces a controlled export error.

### How are execution results represented publicly?

The kernel imports no Qt bindings: per-user profile paths come from `app.paths`, while GUI settings remain in `app.settings`. Execution and parsing do not change process-global garbage-collection settings; execution budgets remain local to their context.

Parsed `Block` objects are authoritative. A compiled Block-to-AST builder accelerates the same contract as the portable Python builder: AST nodes and first-occurrence N/O label maps are built in one pass. Repeated immutable words share a bounded construction-local cache. The native parser installs its freshly derived canonical AST through a private constructor without rebuilding it; public `Program(blocks, ast)` construction still rejects disagreement. AST nodes and words remain frozen, and label maps remain immutable defensive copies. Parsing never changes process-global GC settings. Relative synthetic performance guards compare compiled and portable AST construction and their complete parsing pipelines; run them with `pytest tests/core/test_ast_acceleration.py -m performance` after building the native extension. Application code imports canonical frontend/API/runtime modules; historical aliases remain available for external compatibility.

The core immutable public types include:

- `Diagnostic`;
- `SemanticInstruction`;
- `TraceMotion`;
- `ArcGeometry`;
- `MachineSignal`;
- `ExecutionEvent`;
- `ExecutionStep`;
- `ExecutionResult`.

### What is an `ExecutionStep`?

It records one executed occurrence of a source block and includes information such as:

- source block index;
- number of emitted motions;
- unit scale;
- diameter/radius mode;
- absolute/incremental state;
- evaluated words;
- signals;
- position;
- active WCS;
- feed/spindle state;
- Macro B variable snapshot;
- execution events.

This occurrence-level model is essential for loops and subprograms where one source line executes multiple times.

### What is an `ExecutionEvent`?

Events describe structural facts that are not ordinary geometry, including program/subprogram boundaries, tool changes and reference returns.

Export can therefore preserve structural execution order without reconstructing it from motion geometry.

### How are tests organized?

Tests are grouped by domain, including:

```text
tests/core/
tests/dialects/
tests/stock/
tests/tooling/
tests/export/
tests/gui/
tests/render/
tests/meta/
```

The fixture corpus contains representative turning, milling, Macro B, cycle, compensation, WCS and export programs.

### How do I run the main checks?

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Project scripts add resource/generated-file and complexity checks around the standard lint commands.

On Windows, run the full test suite and project lint checks from the repository root:

```powershell
.\scripts\ps1\test.ps1
.\scripts\ps1\lint.ps1
```

### How do I run the daily GUI smoke test with a visible window?

The launchers configure the environment automatically: `scripts\ps1\start-sandbox.ps1` on Windows, or `bash scripts/sh/start-sandbox.sh` on Linux/macOS. They run the visible demo by default. Use `-Automated` / `--automated` for offscreen mode and `-DelayMs 1500` / `--delay-ms 1500` to adjust demo pacing. The PowerShell launcher restores previous environment values; the Bash launcher sets overrides only for its child process.

Run the automated sandbox from the repository root in PowerShell:

```powershell
.\scripts\ps1\test.ps1 tests/gui/test_daily_workflow_smoke.py -q -s
```

For a visible, paced demo, enable both the Windows Qt platform and demo mode:

```powershell
$env:QT_QPA_PLATFORM = "windows"
$env:EASY_GCODE_SMOKE_DEMO = "1"
try {
    .\scripts\ps1\test.ps1 tests/gui/test_daily_workflow_smoke.py -q -s
}
finally {
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    Remove-Item Env:EASY_GCODE_SMOKE_DEMO -ErrorAction SilentlyContinue
}
```

Setting only `QT_QPA_PLATFORM=windows` shows the window but does not enable presentation pauses or the final demo summary dialog. The default `EASY_GCODE_SMOKE_DELAY_MS` is 1000 ms: actions pause for 1 second, major stages/dialogs for 2 seconds, and the final summary for 4 seconds. You can adjust the pacing:

```powershell
$env:EASY_GCODE_SMOKE_DELAY_MS = "1500"
```

Both modes execute the same assertions. The scenario opens these existing inputs without moving or changing them:

- FANUC milling: `tests/fixtures/milling/fanuc/flange_plate_benchmark.nc`, without STL; dark theme, grid/colors and settings persistence, Statistics with a per-tool selector and SVG HTML export, expanded FANUC export and kernel replay. Line width stays unchanged.
- FANUC turning: `tests/fixtures/turning/lathe_cycles_example.nc`; G71/G76 and real Stock Removal with deterministic rewind/replay. Saved-library geometry takes priority over automatic discovery.
- SINUMERIK 3+2: `tests/fixtures/milling/sinumerik/5ax_test.mpf` with `stl/test6.stl` and the AC profile. STL Objects: Base Point Origin, Position Z=-100, Move Here.
- SINUMERIK impeller: `tests/fixtures/milling/sinumerik/impeller.mpf` with `stl/test7.stl` and `5ax_table_bc_angled`. STL Objects: Transform rotates Z by +90 degrees, then Section Y at zero, Apply, Undo, and STL edges only. The sandbox editor uses saved T60 taper-ball-mill geometry with D1. Play briefly, then seek in 10% slider steps through completion. Turning Stock Removal and the flange benchmark retain complete continuous playback.

Pytest isolates settings, the tool library and all output files in temporary directories. The sandbox's fixed T0303 P2 record is in that temporary library, not the user's configured SQLite. File pickers receive predetermined paths; application dialogs and actions remain real. Unexpected message boxes fail the stage instead of hanging. Assertions inspect widget/model/scene state, not OpenGL pixels. Both modes print stage results; demo mode also displays a timed final summary and identifies the failed stage if an assertion fails.

See [GUI sandbox](docs/GUI_SANDBOX.md) for the complete stage contracts and platform notes.

### Are generated Qt Python files edited manually?

No. `.ui` and `.qrc` sources are authoritative. Regenerate through the project scripts.

Windows:

```powershell
.\scripts\ps1\generate-qt.ps1
```

Generated modules are build artifacts.

---

## Build and release

### How do I build on Windows?

```powershell
.\scripts\ps1\build.ps1
```

The build produces separate GUI and CLI executables plus SHA-256 checksum files.

### How do I build on Linux?

```bash
bash scripts/sh/build.sh
```

For console-only packaging after tests have already passed:

```bash
bash scripts/sh/build.sh --console --skip-tests
./dist/easy_gcode_plot_cli --help
(cd dist && sha256sum -c easy_gcode_plot_cli.sha256)
```

### Does the project use a separate build environment?

Yes. Native/release tooling uses a persistent `.venv-build` rather than replacing or pruning the developer `.venv`.

The native build checks tracked `.pyx` and dependency state and can reuse the build environment when nothing relevant changed.

### How are releases validated in CI?

The release workflow builds/tests Windows and Linux artifacts before publication. Linux release validation includes starting the packaged CLI and exercising the batch fixture presets before the final release artifact is published.

### Does a Linux executable run as a Windows `.exe`?

No. Windows and Linux artifacts are platform-specific builds even though they share the same Python/kernel implementation and CLI contract.

---

## License

Easy G-Code Plot is distributed under the MIT License. See `LICENSE.md` for the full text.
