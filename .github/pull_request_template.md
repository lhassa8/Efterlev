<!--
Thanks for the PR! The checklist below mirrors the gates in CONTRIBUTING.md.
Tick each box as you go; uncheck any that don't apply with a one-line note
explaining why. Maintainer review starts when the checklist is complete.
-->

## Description

What does this PR change, and why?

Linked issue: <!-- e.g., Closes #123, Refs #456, or "no linked issue" -->

## Type of change

- [ ] Bug fix
- [ ] New detector
- [ ] New primitive / agent / output format
- [ ] Documentation
- [ ] Infrastructure (CI, build, release)
- [ ] Refactor / non-functional

## Standards checklist

- [ ] `uv run ruff check . && uv run ruff format --check` clean
- [ ] `uv run mypy src/efterlev` clean
- [ ] `uv run pytest -m "not e2e"` clean
- [ ] DCO sign-off on every commit (`git commit -s`); commit-signing if you have it set up (optional for contributors)
- [ ] CHANGELOG entry added under the appropriate version section, or "no-changelog" justified in description
- [ ] DECISIONS.md entry added if the change is architectural

## For new detectors

- [ ] All five contract files present: `detector.py`, `mapping.yaml`, `evidence.yaml`, `fixtures/`, `README.md`
- [ ] Detector docstring includes a "does NOT prove" section
- [ ] Fixtures cover at least one should-match and one should-not-match case
- [ ] HCL + plan-JSON equivalence fixtures present; equivalence test in `tests/detectors/test_plan_mode_equivalence.py`
- [ ] KSI mapping uses `ksis=[]` when no KSI in FRMR 0.9.43-beta cleanly applies; gap explained in the README

## For docs changes

- [ ] All internal links resolve
- [ ] Quickstart still passes if it was touched
- [ ] No hidden secrets, internal-only URLs, or NDA-era language reintroduced

## Anything else

Notes, caveats, or follow-up issues spawned by this change.
