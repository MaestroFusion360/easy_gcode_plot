# Contributing to Easy GCode Plot

Contributions are welcome, especially bug fixes, regression tests, controller dialect improvements, and corrections to machining semantics.

Easy GCode Plot is not only a text editor or G-code formatter. Its core responsibility is to parse, execute, visualize, analyze, and export CNC programs while preserving their machining semantics.

Before making changes, read:

- [README](README.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)

The roadmap separates implemented release scope from planned work. The README and FAQs describe current capabilities and limitations. Follow the [Code of Conduct](CODE_OF_CONDUCT.md); use the [Security Policy](SECURITY.md) for sensitive reports.

## Development principles

### Preserve machining semantics

A change is not correct merely because generated G-code looks plausible.

For parser, executor, kinematics, cycle, multiaxis, or export changes, verify the resulting execution semantics where applicable:

- positions and trajectories;
- modal state;
- coordinate systems;
- feeds and motion modes;
- tool state;
- rotary-axis state;
- TCP and tilted-working-plane state;
- cycle expansion;
- relevant execution events.

For controller conversion, semantic equivalence is more important than textual equivalence.

### Keep controller syntax separate from execution semantics

Controller-specific syntax such as FANUC or SINUMERIK commands should be translated into controller-neutral execution state wherever practical.

The execution kernel should not depend unnecessarily on how a controller spells a particular operation. Export and post-processing should serialize an already resolved execution model rather than reinterpret the original program.

### Fail closed when semantics cannot be reconstructed safely

Do not generate plausible-looking NC code when Easy GCode Plot does not have enough information to reconstruct the operation correctly.

Unsupported TCP, tilted-working-plane, rotary, cycle, or controller-specific semantics should produce an explicit diagnostic rather than silently changing program meaning.

Do not remove an export limitation unless the resulting geometry and machine state can be verified.

## Scope

Useful contributions include:

- parser and dialect fixes;
- FANUC and SINUMERIK support;
- turning and milling execution fixes;
- canned-cycle support;
- TCP, rotary, multiaxis, and kinematics corrections;
- visualization fixes;
- export and postprocessor fixes;
- deterministic analysis and diagnostics;
- regression tests;
- documentation corrections.

Avoid unrelated framework changes, large architectural rewrites, or features outside the current `ROADMAP.md` without prior discussion.

## Tests

Every behavior change should include a regression test when practical.

For G-code execution and export changes, prefer tests that verify semantics, not only output strings. Useful checks include:

- execution result validity;
- motion count and geometry;
- start and end coordinates;
- trajectory signatures;
- rotary positions;
- TCP/TWP state transitions;
- round-trip execution after export;
- explicit diagnostics for unsupported cases.

Small synthetic programs are useful for isolated edge cases, but significant changes should also be checked against existing real-world fixtures.

For deterministic NC text regressions, CLI `export --compare-with expected.nc -o actual.nc` compares the generated file directly with a UTF-8 reference and prints a unified diff. Exit codes are 0 for a match, 1 for a mismatch and 2 for an error; LF/CRLF differences are ignored, while spaces, comments and the final newline are compared. This complements the execution/replay checks for machining-semantic changes. See the [CLI comparison example](FAQ.md#can-cli-export-be-compared-directly-with-an-expected-nc-file).

Do not modify expected test results merely to make the suite pass unless the previous expectation is demonstrably incorrect.

## Export changes

Export is safety-sensitive. When modifying `app/gcode/export`, post profiles, or related execution code, check where applicable:

- source-preserving export;
- expanded execution export;
- FANUC output;
- SINUMERIK output;
- 3-axis milling;
- rotary and indexed motion;
- supported multiaxis motion;
- TCP enable and disable;
- home and reference moves;
- coordinate-mode restoration;
- cycles;
- round-trip execution.

A generated program must never silently replace unsupported controller semantics with ordinary motion just because the resulting coordinates appear similar.

## Development checks

On Windows:

```powershell
.\scripts\ps1\test.ps1
.\scripts\ps1\lint.ps1 -CheckResources
```

On POSIX systems:

```bash
bash scripts/sh/test.sh
bash scripts/sh/lint.sh
```

The expected result is:

- tests pass;
- Ruff/lint checks pass;
- generated Qt/resources are up to date;
- complexity checks pass;
- `git diff --check` is clean.

Do not suppress lint or complexity warnings merely to make checks green.

## Pull requests

A pull request should explain:

1. What was wrong.
2. Why it was wrong.
3. What was changed.
4. What regression tests were added.
5. Which checks were run.

For machining-semantic changes, include a minimal reproducer when useful. Keep pull requests focused on one problem or a closely related group of problems.

## Controller documentation

Controller behavior can differ by model, option package, software version, machine kinematics, and machine-tool builder configuration.

When implementing controller-specific behavior, cite the relevant controller documentation or provide a reproducible program/fixture whenever possible.

Do not generalize machine-specific behavior into universal FANUC or SINUMERIK semantics without evidence.

## Safety

Easy GCode Plot is a visualization, analysis, and development tool. Generated or transformed NC programs must still be reviewed and validated before use on a real machine.

A passing test suite does not constitute machine-tool safety validation.
