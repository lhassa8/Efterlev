# Write your first detector

Stub for SPEC-38.9. Substantial content lands in a follow-up batch.

The detector contract is documented authoritatively in [`CONTRIBUTING.md`](https://github.com/efterlev/efterlev/blob/main/CONTRIBUTING.md). A new detector lives at `src/efterlev/detectors/<cloud>/<capability>/` with five files:

1. `detector.py` — the rule. Uses the `@detector` decorator with `id`, `ksis=[...]`, `controls=[...]`, `source`, `version`.
2. `mapping.yaml` — KSI + 800-53 mapping.
3. `evidence.yaml` — schema for the evidence shape.
4. `fixtures/` — `should_match/*.tf` and `should_not_match/*.tf` (plus `.plan.json` siblings).
5. `README.md` — what it proves, what it does NOT prove, known limitations.

Adding a new detector takes 30 minutes if you've written one before, 2 hours your first time. The most common contributor mistake: claiming a KSI mapping that doesn't exist in FRMR. When in doubt, declare `ksis=[]` and explain in the README — there's an established precedent for this (see `aws.encryption_s3_at_rest`).
