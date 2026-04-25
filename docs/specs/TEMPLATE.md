# SPEC-NN: <one-line title>

**Status:** draft
**Gate:** <A1 / A2 / A3 / A4 / A5 / A6 / A7 / A8 / C1 / ...>
**Depends on:** SPEC-XX, SPEC-YY  (or "none")
**Blocks:** SPEC-ZZ  (or "none at this time")
**Size:** S (≤1 day) / M (2–5 days) / L (≥1 week; consider splitting)

## Goal

One sentence. What does this item do for the user or the system?

## Scope

Bulleted list of what's in.

## Non-goals

Bulleted list of what's deliberately out. Prevents scope creep and makes review decisions easy.

## Interface

CLI flags, function signatures, file shapes, config fields — whatever surface this spec introduces or changes. Concrete, with examples.

## Behavior

Happy path, edge cases, error paths. "Given X, the system does Y." One bullet per observable behavior.

## Data / schema

Pydantic models, YAML shapes, DB migrations, on-disk file formats. Name `extra="forbid"` invariants and `Literal[True]` invariants explicitly where applicable.

## Test plan

- **Unit tests:** what's covered
- **Integration tests:** what's covered
- **E2E tests:** what's covered (if any)
- **Failure-mode tests:** what failures we prove we handle

## Exit criterion

Checkable sentence(s). "Running `efterlev X` against the demo repo produces Y; test file Z passes." If you can't write this, the spec isn't done.

## Risks

What could go wrong. What we'll do if it does.

## Open questions

Anything unresolved. Ideally zero before status → `accepted`.
