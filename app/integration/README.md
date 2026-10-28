# MiniCAD simulation bundle

The `simulate` command accepts an optional `--bundle output/simulation.json` alongside the NC path. The manifest is local and contains:

```json
{
  "version": 1,
  "units": "mm",
  "nc": "program.nc",
  "stl": "stock.stl",
  "stock": {"xmin": 0, "xmax": 100, "ymin": 0, "ymax": 60, "zmin": -10, "zmax": 0},
  "tool": {"number": 1, "diameter": 6, "type": "mill_flat"},
  "coordinates": {"wcs": "G54", "x": 0, "y": 0, "z": 0}
}
```

The NC and STL paths must be filenames in the same directory as the manifest. All bounds are WCS millimetres. The coordinate offset is in millimetres. `stock.stl` is loaded as a *visual STL object*, not as the milling stock removal volume. Milling stock removal currently uses the existing rectangular dexel stock configured from the bounds. The existing NC interpreter's WCS offsets are not populated by this manifest: nonzero `coordinates` offsets therefore do not yet guarantee aligned toolpaths. A subsequent integration step must explicitly apply those offsets to the NC execution state before reliable nonzero-offset simulation. Do not treat this as complete MiniCAD simulation integration.

CLI example:

`easy_gcode_plot_cli.exe simulate output/program.nc --lang fanuc_mill --bundle output/simulation.json`
