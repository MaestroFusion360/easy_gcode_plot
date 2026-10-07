# Security Policy

## Supported versions

Security fixes are normally made against the current development/release line. Older releases may not receive backports.

## Reporting a security issue

Do not publish sensitive vulnerability details, exploit steps, malicious files, or credentials in a public issue.

If GitHub private vulnerability reporting is enabled for this repository, use [Security → Report a vulnerability](https://github.com/MaestroFusion360/easy_gcode_plot/security/advisories/new).

If private reporting is not available, [open a minimal public issue requesting private maintainer contact](https://github.com/MaestroFusion360/easy_gcode_plot/issues/new). Do not include exploit details, sensitive files or personal information. Wait for the maintainer to provide a private channel before sharing them.

For non-sensitive defects, use the [issue templates](https://github.com/MaestroFusion360/easy_gcode_plot/issues/new/choose).

## CNC safety issues

Incorrect parsing, execution, coordinate transformation, cycle expansion, or export can be safety-relevant even when it is not a conventional software security vulnerability.

Use the **G-code / export semantics bug** issue template for cases such as:

- generated motion differing from the source semantics;
- incorrect home/reference motion;
- wrong WCS or machine-coordinate transformation;
- incorrect rotary/TCP/TWP state;
- controller conversion that silently changes geometry;
- unsafe output being produced instead of a fail-closed diagnostic.

Do not run unverified generated or converted NC programs on production machinery. Validate output using the controller/machine manufacturer's normal verification procedures.

## Scope

Examples of conventional security issues include:

- arbitrary file access or path traversal;
- command or code execution caused by untrusted input;
- unsafe temporary-file handling;
- malicious project/input files escaping their intended sandbox;
- dependency or packaging issues that permit execution of unintended code.

A report should include the affected version, operating system, reproduction steps, impact, and the smallest practical reproducer.
