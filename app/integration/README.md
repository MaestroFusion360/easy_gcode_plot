# MiniCAD simulation integration

This directory owns the MiniCAD simulator exchange contract. Both programs implement it without
importing the other application. Version 1 remains readable in EGP; MiniCAD's
legacy write_bundle call without a tool table retains the v1 interface.

The `simulate` command accepts `--bundle output/simulation.json` alongside the NC path.
The manifest contains program-local tools, stock bounds, coordinates and the
simulation dialect: `fanuc_mill` or `fanuc_turn`. The CLI `--lang` must match it;
legacy v1 bundles use `fanuc_mill`.

MiniCAD can exchange one ordered, multi-tool program containing multiple operations:

| Setup | Operations | Simulation dialect |
| --- | --- | --- |
| Milling | Contour (including chamfer), Pocket, Adaptive, Engrave, Drilling (G81/G82/G83/G84 or explicit G1/G0), Face, Bore, ThreadMill | `fanuc_mill` |
| Turning | Face, Rough, Finish, Groove, Boring, Thread Turn (G32), Lathe Drilling (including pecks) | `fanuc_turn` |
| Cutting | Separate AMADA Laser workflow; EGP simulation is disabled | None |

Operations are exchanged as NC movements and tool changes, not as CAM strategy
records. The manifest tool table covers the entire program, including shared tools.
Milling uses rectangular stock bounds; its optional STL is a visual reference
object, not the stock-removal volume. Turning uses an explicit cylinder with an
optional pilot bore and does not accept an STL.

## Milling manifest v2

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
NC is ASCII Fanuc Mill or Fanuc Turn, G21, with exactly the declared G54..G59 work system.
The unique tools list contains every NC T number exactly once, including tools
shared by multiple operations. Tool numbers are integers 1..9999; H/D are integers
0..9999, independent of physical length and diameter. Name must be nonblank.
The manifest is published after NC/STL in MiniCAD's protected file transaction.
EGP rejects an integrity mismatch before changing program state.

For milling v2, all physical dimensions are explicit finite JSON numbers (not strings/booleans).
Unknown types, missing dimensions, duplicate fields/identities, invalid ranges,
inconsistent lengths and unsupported profiles are errors. No v2 milling reader fills a
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

## Turning manifest v2

Turning uses the same file integrity, WCS and tool-table contract, with
`dialect: "fanuc_turn"`, G18 NC (G17 is rejected), and `turningStock`:

```json
{
  "version": 2, "units": "mm", "dialect": "fanuc_turn", "nc": "program.nc",
  "stock": {"xmin": -25, "xmax": 25, "ymin": -25, "ymax": 25, "zmin": -70, "zmax": 0},
  "turningStock": {"outerDiameter": 50, "innerDiameter": 6, "length": 70, "frontZ": 0},
  "coordinates": {"wcs": "G54", "x": 0, "y": 0, "z": 0},
  "tools": [{"number": 101, "name": "T1 OD insert", "h": 0, "d": 0,
    "type": "diamond_80", "applications": ["od"], "tipOrientation": 3,
    "noseRadius": 0.4, "insertLength": 12}],
  "sha256": {"program.nc": "<64 lowercase hexadecimal characters>"}
}
```

`outerDiameter` and `length` must be positive; `0 <= innerDiameter < outerDiameter`.
All four cylinder values must be finite JSON numbers. Its Cartesian envelope must
match `stock` exactly: X/Y are `[-outerDiameter/2, outerDiameter/2]`, Z is
`[frontZ-length, frontZ]`. EGP also validates the cylinder against its turning
stock resolution/size limit. `stl` is rejected for turning bundles.

Tool identifiers match the complete NC T word: MiniCAD logical T1 becomes
`T0101`, manifest `number: 101`, and EGP key `T0101`; logical T2 becomes `202`.
MiniCAD supports logical turning tool numbers 1..99. The common manifest `h`/`d`
fields remain present (MiniCAD writes zero); turning does not use milling M6/G43.

MiniCAD exports `diamond_80`, `diamond_35`, `groove`, `thread` and axial `drill`
geometry. Inserts carry `applications` (`od`/`id`), `tipOrientation`, `noseRadius`
and `insertLength`. Grooves carry `width` and `noseRadius`, with
`grooveCuttingPlane: "face"` for face grooves. Threads carry `insertLength`,
`threadAngle`, `threadTipWidth` and `threadCornerRadius`. Drills carry `diameter`,
`length` (usable axial length) and `tipAngle`. EGP uses its existing turning-tool
normalizer, whose defaults and supported orientations differ from the strict
milling geometry contract above.

MiniCAD emits G21/G18 Fanuc Turning Type A with diameter X, physical I/K arc
offsets, G0/G1/G2/G3, explicit G32 threading and G0/G1 axial drilling. Roughing
and finishing arrive as resolved moves rather than canned cycles. The bundle
initializes EGP's existing turning stock-removal model, including the pilot bore,
and replaces the active program's turning tools. It does not establish validated
holder/chuck clearance or complete physical removal for every operation.

## Application and simulation

EGP imports tools into the active program, never into the persistent library.
Reloads and document switches retain program-local tools and the bundle identity;
opening the matching NC next to simulation.json reloads its geometry and validates
its integrity. Existing explicit program geometry takes precedence over NC inference.
The active T selects the full geometry, including lengths, head and profile.

Coordinates/stock/STL are millimetres. Nonzero origin offsets are explicitly
rejected by v2 until the full coordinate alignment path supports them. For accepted
zero-origin bundles, EGP executes with zero work offsets local to that document;
shared machine preferences are retained. Milling simulation uses Fanuc Mill
independently of the selected milling Setup post. Turning simulation uses Fanuc
Turn and MiniCAD's Fanuc turning Setup.

Tool profile display is distinct from material removal. EGP's height-field stock
cannot faithfully represent undercuts: v2 stock removal explicitly refuses slot_mill
and thread_mill, while their tool/trajectory previews remain available. This format
does not claim validated physical removal for those profiles.

CLI examples:

```text
easy_gcode_plot_cli.exe simulate output/program.nc --lang fanuc_mill --bundle output/simulation.json
easy_gcode_plot_cli.exe simulate turning/program.nc --lang fanuc_turn --bundle turning/simulation.json
```

Repeated GUI simulation requests are forwarded through a user-local Qt socket
to the running GUI. The active exchange document retains its manifest association
across document switches. Reloading it from disk rereads the manifest stock and
tool parameters before recalculation. Unsaved editor changes still require the
normal Save/Discard/Cancel decision before an incoming simulation replaces them.
