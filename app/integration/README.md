# MiniCAD simulation integration

This directory owns the MiniCAD simulator exchange contract. Both programs implement it without
importing the other application. Version 1 remains readable in EGP; MiniCAD's
legacy write_bundle call without a tool table retains the v1 interface.

The `simulate` command accepts `--bundle output/simulation.json` alongside the NC path.
The manifest contains program-local tools, stock bounds and coordinates.
The optional STL is a visual reference object; stock removal uses the rectangular
stock bounds, not the imported STL volume.

The UTF-8 simulation.json manifest contains:

```json
{
  "version": 2, "units": "mm", "dialect": "fanuc_mill", "nc": "program.nc",
  "stock": {"xmin": -20, "xmax": 20, "ymin": -20, "ymax": 20, "zmin": -10, "zmax": 0},
  "coordinates": {"wcs": "G54", "x": 0, "y": 0, "z": 0},
  "tools": [{"number": 1, "name": "End mill", "h": 1, "d": 1,
    "type": "mill_flat", "diameter": 10, "length": 50, "fluteLength": 30,
    "bodyLength": 20, "shankDiameter": 10, "cornerRadius": 0}],
  "sha256": {"program.nc": "<64 lowercase hexadecimal characters>"}
}
```

An optional stl field names stock.stl; its SHA-256 digest is also required.
Names identify existing sibling files, never paths outside the bundle directory.
NC is ASCII Fanuc Mill, G21, with exactly the declared G54..G59 work system.
The unique tools list contains every NC T number exactly once, including tools
shared by multiple operations. Tool numbers are integers 1..9999; H/D are integers
0..9999, independent of physical length and diameter. Name must be nonblank.
The manifest is published after NC/STL in MiniCAD's protected file transaction.
EGP rejects an integrity mismatch before changing program state.

All physical dimensions are explicit finite JSON numbers (not strings/booleans).
Unknown types, missing dimensions, duplicate fields/identities, invalid ranges,
inconsistent lengths and unsupported profiles are errors. No v2 reader fills a
missing value, clips a dimension, or substitutes DEFAULT_MILLING_TOOL.

Common geometry fields: type, diameter, length, fluteLength, bodyLength,
shankDiameter, cornerRadius. diameter/length/fluteLength/shankDiameter > 0;
bodyLength >= 0; length = fluteLength + bodyLength (absolute tolerance 1e-9 mm).
fluteLength measures the cutting portion from the programmed end plane z=0;
bodyLength extends from its upper end to the holder. The body radius is explicitly
shankDiameter/2; an abrupt shoulder is retained in both preview profiles.

| Type | Additional geometry and constraints |
| --- | --- |
| mill_flat | cornerRadius = 0 |
| mill_bull | 0 <= cornerRadius <= diameter/2; fluteLength >= cornerRadius |
| mill_ball | cornerRadius = diameter/2; fluteLength >= diameter/2 |
| taper_ball_mill | taperAngle: 1..89 degrees; diameter describes the spherical tip, as in EGP |
| face_mill | shankDiameter < diameter; fluteLength is the existing EGP cutting-head height |
| slot_mill | shankDiameter < diameter; fluteLength is the cutting-head height |
| chamfer_mill | tipDiameter >= 0 and < diameter; chamferAngle: 1..179 degrees, included angle |
| drill | tipAngle: 1..179 degrees, included point angle |
| tap | cylindrical envelope, cornerRadius = 0 |
| thread_mill | threadProfile = single_form; threadRootDiameter, threadAngle, threadTipWidth |

cornerRadius is zero outside bull/ball. Chamfer and drill cones must fit the
cutting length. For thread_mill, 0 < root diameter < diameter, 1 <= included angle
< 180, crest width > 0. This supports one axisymmetric annular V tooth only.
Define R=diameter/2, r=threadRootDiameter/2, a=(R-r)*tan(threadAngle/2), w=threadTipWidth.
Its cutting profile (z,radius) is (0,r), (a,R), (a+w,R), (2a+w,r), (fluteLength,r).
Require 2a+w <= fluteLength. The body starts at fluteLength, with the explicit
shank diameter. The programmed point stays at the physical end z=0; renderers do
not shift the tip or modify CAM motions. Multiple teeth, reliefs and asymmetric
teeth are outside this profile. Turning thread geometry is separate and unchanged.
MiniCAD currently accepts only 60-degree thread teeth whose height fits the
selected pitch. Unsupported shapes are rejected by the selected 2D CAM strategy.

EGP imports tools into the active program, never into the persistent library.
Reloads and document switches retain program-local tools and the bundle identity;
opening the matching NC next to simulation.json reloads its geometry and validates
its integrity. Existing explicit program geometry takes precedence over NC inference.
The active T selects the full geometry, including lengths, head and profile.

Coordinates/stock/STL are millimetres. Nonzero origin offsets are explicitly
rejected by v2 until the full coordinate alignment path supports them. For accepted
zero-origin bundles, EGP executes with zero work offsets local to that document;
shared machine preferences are retained. A different Setup post in MiniCAD does
not affect simulation: the existing simulation export always uses Fanuc Mill.

Tool profile display is distinct from material removal. EGP's height-field stock
cannot faithfully represent undercuts: v2 stock removal explicitly refuses slot_mill
and thread_mill, while their tool/trajectory previews remain available. This format
does not claim validated physical removal for those profiles.

CLI example:

`easy_gcode_plot_cli.exe simulate output/program.nc --lang fanuc_mill --bundle output/simulation.json`

Repeated GUI simulation requests are forwarded through a user-local Qt socket
to the running GUI. The active exchange document retains its manifest association
across document switches. Reloading it from disk rereads the manifest stock and
tool parameters before recalculation. Unsaved editor changes still require the
normal Save/Discard/Cancel decision before an incoming simulation replaces them.
