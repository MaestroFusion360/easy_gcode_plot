## Problem

Describe the defect or limitation this PR addresses.

## Change

Describe the implementation change and why this approach is appropriate.

## Semantics / safety impact

For parser, execution, cycles, kinematics, or export changes, state what machining semantics are affected and how equivalence was verified.

If not applicable, write `N/A`.

## Regression coverage

List the tests or fixtures added/updated and what each protects.

## Validation

- [ ] `./scripts/ps1/test.ps1` or `bash scripts/sh/test.sh`
- [ ] `./scripts/ps1/lint.ps1 -CheckResources` or `bash scripts/sh/lint.sh`
- [ ] `git diff --check`
- [ ] Relevant controller/export round-trip checks, when applicable
- [ ] No lint/complexity suppression added only to make checks pass

## Notes

Document intentional fail-closed behavior, environment limitations, controller-specific assumptions, or checks that could not be run.
