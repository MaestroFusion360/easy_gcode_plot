# NC fixture inventory after 2.1.0 stabilization

Version 2.5.0 registers the supplied Klartext milling programs as native-input
fixtures. Parser/runtime and GUI regressions are run separately from corpus
registration. All 11 programs in `milling/heidenhain/` must execute completely
and open/plot in the real Qt GUI with configured Home emulation enabled.
`tests/dialects/test_heidenhain_execution.py` and
`tests/gui/test_gui_state_lifecycle.py` enforce this for the entire directory.

The corpus includes CAM contours, drilling/tapping, Cycle 7 datum shifts,
Cycle 10 planar rotation, Cycle 247 preset selection, FN 6/7 trigonometric
assignments and Q/label flow. The actual programs are retained unchanged.
`cycles_itnc530.h` reaches M30 and executes eight holes; the macro drilling
program executes ten holes; `ellipse.h` completes its 40-step ellipse loop.

M140 MB MAX uses Z from Home (G28) in WCS for the vertical three-axis preview.
It requires Home emulation, emits a warning and blocks NC trace export because
physical travel limits are not modeled. Cycle 32 smoothing and F0 warnings
remain visible. Complete execution of this corpus does not imply complete
controller coverage.

All checked-in NC/MPF/PTP files were reviewed against tracked tests, scripts,
documentation and CI. The table records literal filename references separately
from directory consumers: `tests/export/test_batch_export_semantics.py` exports
and replays every NC/MPF file in its three controller directories. Therefore a
missing literal reference does **not** establish that a fixture is unused.
`tests/meta/test_corpus.py` also guards the exact corpus and normalized uniqueness.
No normalized duplicates were found. Controller/CAM is a regression role, not a
claim that undocumented files have verified CAM provenance.

The retained controller/CAM programs, including large impellers, paired controller
exports, macros, cycles and simulation examples, remain unchanged. Small native
HEIDENHAIN AST scenarios live inline in frontend tests.
The four-line CUT3DC warning scenario now lives in a semantic golden test in
`tests/dialects/test_sinumerik_tcp.py`; its file remains a directory batch input.
The test freezes motion coordinates, feed, diagnostic location/severity and TCP
events. Existing CLI `export --compare-with` golden text also now verifies the
reimported motion trace with `motion_traces_match`; its expected text is unchanged.

Small simulation fixtures such as helical_bore, inch_spiral, raster and ramps
remain useful batch inputs. Removing them would reduce the independent directory
export/reimport coverage. STL files used by Sandbox remain untouched as well.

| Fixture relative to tests/fixtures | Lines | Role | Directory batch | Sandbox | Direct test/script references |
| --- | ---: | --- | --- | --- | --- |
| `milling/fanuc/bottle.nc` | 3462 | Controller/CAM integration | yes | - | directory/corpus checks only |
| `milling/fanuc/contur_2d.nc` | 96 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py`, `tests/dialects/test_sinumerik_native.py`, `tests/export/test_cli_batch_export.py`, `tests/export/test_multiaxis_audit.py` |
| `milling/fanuc/correction_fanuc.nc` | 50 | Controller/CAM integration | yes | - | directory/corpus checks only |
| `milling/fanuc/cycles_fanuc.nc` | 184 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_cycles.py`, `tests/export/test_drilling_operations.py`, `tests/export/test_multiaxis_audit.py` |
| `milling/fanuc/flange_plate_benchmark.nc` | 291 | Synthetic simulation/regression | yes | yes | `tests/dialects/test_milling_golden.py`, `tests/export/test_cli_batch_export.py`, `tests/export/test_dxf_exporter.py`, `tests/export/test_multiaxis_audit.py`, `tests/gui/test_daily_workflow_smoke.py` |
| `milling/fanuc/fusion_benchmark_1001.nc` | 2063 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py` |
| `milling/fanuc/g68_2_cube.nc` | 123 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py`, `tests/dialects/test_milling_twp.py`, `tests/export/test_multiaxis_audit.py` |
| `milling/fanuc/helical_bore.nc` | 17 | Synthetic simulation/regression | yes | - | directory/corpus checks only |
| `milling/fanuc/impeller.ptp` | 3540 | Controller/CAM integration | - | - | `tests/dialects/test_milling.py`, `tests/dialects/test_milling_reference_frames.py`, `tests/export/test_multiaxis_audit.py`, `tests/export/test_multiaxis_profiles.py` |
| `milling/fanuc/impeller2.ptp` | 3541 | Controller/CAM integration | - | - | `tests/dialects/test_milling.py`, `tests/export/test_multiaxis_audit.py`, `tests/export/test_multiaxis_profiles.py` |
| `milling/fanuc/inch_spiral.nc` | 16 | Synthetic simulation/regression | yes | - | directory/corpus checks only |
| `milling/fanuc/incremental_xyz_raster.nc` | 22 | Synthetic simulation/regression | yes | - | directory/corpus checks only |
| `milling/fanuc/indexed_table_a.nc` | 498 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py`, `tests/dialects/test_milling_golden.py`, `tests/export/test_multiaxis_audit.py` |
| `milling/fanuc/indexed_table_b.nc` | 1161 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py`, `tests/dialects/test_milling_golden.py`, `tests/dialects/test_milling_reference_frames.py`, `tests/export/test_multiaxis_audit.py` |
| `milling/fanuc/indexed_table_c.nc` | 817 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py`, `tests/dialects/test_milling_golden.py`, `tests/export/test_multiaxis_audit.py` |
| `milling/fanuc/Machine_tool_simulation.ptp` | 2083 | Controller/CAM integration | - | - | `tests/dialects/test_milling.py` |
| `milling/fanuc/Machine_tool_simulation_BC.ptp` | 2083 | Controller/CAM integration | - | - | `tests/dialects/test_milling.py` |
| `milling/fanuc/macro_b.nc` | 75 | Controller/CAM integration | yes | - | `tests/dialects/test_macro_b.py`, `tests/render/test_playback_mapping.py` |
| `milling/fanuc/macro_boss_milling.nc` | 28 | Controller/CAM integration | yes | - | `tests/core/test_stabilization.py`, `tests/dialects/test_macro_b.py`, `tests/render/test_gui_plot_runtime.py`, `tests/render/test_playback_mapping.py` |
| `milling/fanuc/macro_face_milling.nc` | 27 | Controller/CAM integration | yes | - | `tests/dialects/test_macro_b.py` |
| `milling/fanuc/macro_hole_milling.nc` | 28 | Controller/CAM integration | yes | - | `tests/dialects/test_macro_b.py` |
| `milling/fanuc/macro_thread_milling.nc` | 135 | Controller/CAM integration | yes | - | `tests/dialects/test_macro_b.py` |
| `milling/fanuc/mixed_ijk_r_planes.nc` | 17 | Synthetic simulation/regression | yes | - | `tests/export/test_multiaxis_audit.py` |
| `milling/fanuc/multiplane_edges.nc` | 19 | Synthetic simulation/regression | yes | - | directory/corpus checks only |
| `milling/fanuc/plate_setup_complete.nc` | 437 | Controller/CAM integration | yes | - | `tests/tooling/test_tool_discovery.py` |
| `milling/fanuc/polar_drilling.nc` | 18 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py`, `tests/export/test_mill_full_program.py` |
| `milling/fanuc/radius_arc_ramp.nc` | 17 | Synthetic simulation/regression | yes | - | directory/corpus checks only |
| `milling/fanuc/ramped_surface.nc` | 22 | Synthetic simulation/regression | yes | - | directory/corpus checks only |
| `milling/fanuc/smpl_sim08_5ax_fanuc_mm.nc` | 669 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py`, `tests/export/test_sim08_conversion.py` |
| `milling/fanuc/subprogram.nc` | 46 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py`, `tests/export/test_mill_full_program.py` |
| `milling/fanuc/tapping_fanuc.nc` | 18 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_cycles.py` |
| `milling/fanuc/terraced_ramp.nc` | 24 | Synthetic simulation/regression | yes | - | directory/corpus checks only |
| `milling/fanuc/test_5ax_ac_fanuc.nc` | 65 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py` |
| `milling/fanuc/test_5ax_bc_fanuc.nc` | 65 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py` |
| `milling/fanuc/toolchange.nc` | 788 | Controller/CAM integration | yes | - | `tests/export/test_drilling_operations.py`, `tests/stock/test_milling_stock_gpu.py`, `tests/stock/test_milling_stock_gui.py`, `tests/tooling/test_tool_discovery.py` |
| `milling/fanuc/wcs_test.nc` | 99 | Controller/CAM integration | yes | - | `tests/dialects/test_milling.py`, `tests/export/test_mill_full_program.py` |
| `milling/heidenhain/1001.h` | 128 | Contours, RL/RR/R0, label calls, Cycle 247 and M140 | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/arcs.h` | 29 | CC/C circular interpolation in coordinate planes | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/bore_itnc530.h` | 47 | Multi-turn helical CP boring, Q feeds and RL | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/contour.h` | 597 | L/CC/C contour and machine-coordinate positioning | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/cycles_itnc530.h` | 98 | Cycles 200/203, eight holes and completion at M30 | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/ellipse.h` | 49 | Cycles 7/10, Q expressions and a 40-step ellipse loop | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/itnc530.h` | 3027 | CAM contours, Cycle 200 drilling, Cycle 207 tapping and M140 | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/itnc530_base_pgm.h` | 18 | Basic contour, tool call, spindle/coolant and M91 | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/itnc530_cycl200macro.h` | 38 | FN 6/7 trigonometry and ten-hole Cycle 200 macro | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/sample.h` | 5605 | Large CAM contour, Cycle 32 and F0 diagnostics | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/heidenhain/sample_cr.h` | 2256 | CR arcs, decimal-comma input and STOP M30 | - | - | `tests/dialects/test_heidenhain_execution.py`, `tests/gui/test_gui_state_lifecycle.py` |
| `milling/sinumerik/5ax_test.mpf` | 5232 | Controller/CAM integration | yes | yes | `tests/dialects/test_sinumerik_cam_setup.py`, `tests/export/test_multiaxis_audit.py`, `tests/gui/test_daily_workflow_smoke.py` |
| `milling/sinumerik/contur_2d_sin840d.mpf` | 99 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_native.py`, `tests/export/test_multiaxis_audit.py` |
| `milling/sinumerik/correction_ijk_sin840d.mpf` | 50 | Controller/CAM integration | yes | - | directory/corpus checks only |
| `milling/sinumerik/correction_sin840d.mpf` | 51 | Controller/CAM integration | yes | - | directory/corpus checks only |
| `milling/sinumerik/cycles_sin840d.mpf` | 188 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_cycles.py`, `tests/export/test_drilling_operations.py`, `tests/export/test_multiaxis_audit.py` |
| `milling/sinumerik/ext_cycles.mpf` | 548 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_cam_cycles.py` |
| `milling/sinumerik/fusion_benchmark_1001.mpf` | 2207 | Controller/CAM integration | yes | - | directory/corpus checks only |
| `milling/sinumerik/impeller.mpf` | 5504 | Controller/CAM integration | yes | yes | `tests/dialects/test_milling_reference_frames.py`, `tests/dialects/test_sinumerik_cam_setup.py`, `tests/dialects/test_sinumerik_frames.py`, `tests/export/test_multiaxis_audit.py`, `tests/gui/test_daily_workflow_smoke.py` |
| `milling/sinumerik/macro_drilling.mpf` | 29 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_macro_flow.py` |
| `milling/sinumerik/no_ext_cycles.mpf` | 548 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_cam_cycles.py` |
| `milling/sinumerik/sinumerik_cam_setup.mpf` | 37 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_cam_setup.py` |
| `milling/sinumerik/sinumerik_cut3dc_unsupported.mpf` | 4 | Compact warning golden; batch input retained | yes | - | directory/corpus checks only |
| `milling/sinumerik/sinumerik_cycle800.mpf` | 10 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_swivel.py`, `tests/export/test_multiaxis_audit.py`, `tests/export/test_native_source_formatting.py` |
| `milling/sinumerik/sinumerik_guide_radius.mpf` | 41 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_diameter_rounding.py` |
| `milling/sinumerik/sinumerik_traori_ac.mpf` | 9 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_tcp.py`, `tests/export/test_multiaxis_audit.py`, `tests/export/test_native_source_formatting.py` |
| `milling/sinumerik/smpl_sim08_5ax_sinumerik_mm.mpf` | 639 | Controller/CAM integration | yes | - | `tests/export/test_sim08_conversion.py`, `tests/gui/test_export_file_safety.py`, `tests/gui/test_gui_files.py` |
| `milling/sinumerik/tapping_sin840d.mpf` | 13 | Controller/CAM integration | yes | - | `tests/dialects/test_sinumerik_cycles.py`, `tests/export/test_multiaxis_audit.py` |
| `milling/sinumerik/test_5ax_ac_sin840d.mpf` | 63 | Controller/CAM integration | yes | - | directory/corpus checks only |
| `milling/sinumerik/test_5ax_bc_sin840d.mpf` | 63 | Controller/CAM integration | yes | - | directory/corpus checks only |
| `milling/sinumerik/text_NX.mpf` | 644 | Controller/CAM integration | yes | - | `tests/dialects/test_m_code_continuation.py` |
| `turning/basic_turning_cycles.NC` | 237 | Controller/CAM integration | yes | - | `tests/core/test_stabilization.py`, `tests/dialects/test_g72_golden.py`, `tests/dialects/test_turning.py`, `tests/dialects/test_turning_arc_geometry.py`, `tests/dialects/test_turning_golden.py`, `tests/export/test_full_normalizer.py`, `tests/tooling/test_tool_discovery.py` |
| `turning/compensation_control_off.nc` | 102 | Controller/CAM integration | yes | - | `tests/dialects/test_turning.py`, `tests/dialects/test_turning_golden.py` |
| `turning/compensation_control_on.nc` | 102 | Controller/CAM integration | yes | - | `tests/dialects/test_turning.py`, `tests/dialects/test_turning_golden.py` |
| `turning/cycle71_ID.nc` | 18 | Controller/CAM integration | yes | - | `tests/dialects/test_turning_golden.py`, `tests/export/test_cli.py` |
| `turning/drill.nc` | 102 | Controller/CAM integration | yes | - | `tests/dialects/test_turning.py`, `tests/dialects/test_turning_golden.py`, `tests/render/test_playback_mapping.py` |
| `turning/face_groove.nc` | 25 | Synthetic simulation/regression | yes | - | `tests/dialects/test_turning_golden.py` |
| `turning/lathe_cnc_macro_test.nc` | 40 | Controller/CAM integration | yes | - | `tests/export/test_full_normalizer.py`, `tests/export/test_turning_post_batch.py` |
| `turning/lathe_cycles_example.nc` | 206 | Controller/CAM integration | yes | yes | `tests/export/test_turning_post_batch.py`, `tests/gui/test_daily_workflow_smoke.py`, `tests/stock/test_turning_stock_tool_footprint.py` |
| `turning/lathe_cycles_example_expanded.nc` | 461 | Controller/CAM integration | yes | - | directory/corpus checks only |
| `turning/od_rough_finish.nc` | 24 | Synthetic simulation/regression | yes | - | `tests/dialects/test_turning_golden.py` |
| `turning/oem_header.nc` | 17 | Synthetic simulation/regression | yes | - | `tests/dialects/test_turning_golden.py` |
| `turning/radius_profile.nc` | 16 | Synthetic simulation/regression | yes | - | `tests/dialects/test_turning_golden.py` |
| `turning/simple_programming.nc` | 32 | Controller/CAM integration | yes | - | directory/corpus checks only |
| `turning/taper_thread.nc` | 21 | Synthetic simulation/regression | yes | - | `tests/dialects/test_turning_golden.py` |
| `turning/thread.nc` | 89 | Controller/CAM integration | yes | - | `tests/dialects/test_turning.py`, `tests/dialects/test_turning_golden.py`, `tests/export/test_full_normalizer.py` |
