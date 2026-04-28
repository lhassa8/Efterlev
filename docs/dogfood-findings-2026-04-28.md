# Dogfood findings — 2026-04-28 — Multi-target sweep, post-Priority 1/2/3

**Purpose:** validate that the 43-detector catalog (Priority 1) holds up against
the seven pinned real-world OSS Terraform targets in
`scripts/dogfood-real-codebases.sh`, and verify no regressions from the
substantial Priority 2 + Priority 3 work shipped 2026-04-27 → 2026-04-28.

**Run command:**

```bash
bash scripts/dogfood-real-codebases.sh
```

**Result: all 7 targets within thresholds, every target running the full 43-detector
catalog cleanly.**

---

## Per-target results

| Target | SHA | Resources | Detectors | Evidence | Parse failures |
|---|---|---:|---:|---:|---:|
| terraform-aws-vpc | `3ffbd46f` | 96 | 43 | 29 | 0 |
| terraform-aws-rds | `fa183b6b` | 18 | 43 | 28 | 0 |
| terraform-aws-iam | `981121bc` | 30 | 43 | 40 | 0 |
| terraform-aws-eks | `ed7f4d5f` | 108 | 43 | 42 | 3 |
| terraform-aws-s3-bucket | `6c5e082b` | 51 | 43 | 38 | 0 |
| terraform-aws-security-group | `3cf4e1a4` | 30 | 43 | 31 | 0 |
| terraform-aws-control-tower | `22f754ac` | 359 | 43 | 119 | 1 |
| **Totals** | — | **692** | — | **327** | **4** |

---

## Observations

### The 43-detector catalog fires on real code

Every target produced meaningful evidence (the lowest evidence-to-resources ratio
is `terraform-aws-vpc` at 30%; the highest is `terraform-aws-iam` at 133%). The
new Priority 1.x detectors landing in this session contribute observably:

- `terraform-aws-iam`'s 40 evidence records on 30 resources reflect the new
  `aws.iam_managed_via_terraform`, `aws.federated_identity_providers`, and
  cross-mapped `aws.iam_admin_policy_usage` / `aws.iam_inline_policies_audit`
  → KSI-IAM-JIT firing on the same surfaces.
- `terraform-aws-control-tower`'s 119 evidence on 359 resources is the largest
  absolute haul; the spread across detectors is wide (control-tower-shaped IAM,
  CloudTrail, multi-account boundaries, KMS, S3, CloudWatch).
- `terraform-aws-rds`'s 28 evidence on 18 resources reflects RDS-heavy detectors
  (encryption, public-accessibility, backup-retention).

### No regressions from Priority 2/3 work

The Priority 2 (HTML overhaul) + Priority 3 (UX) shipped substantial code:
new modules (`reports/gap_diff.py`, `cli/doctor.py`, `cli/progress.py`,
`cli/watch.py`, `cli/friendly_errors.py`, `cli/first_run_wizard.py`),
new `report run` and `report diff` commands, new HTML rendering paths
(coverage matrix, filter, search, sort, drill-down). None of it regressed
the deterministic-scan path — every target still runs and produces the
same shape of output.

### Parse failures

4 total parse failures across all 7 targets, all on `terraform-aws-eks` (3) and
`terraform-aws-control-tower` (1). These are within the per-target thresholds
and reflect the documented limits of `python-hcl2` against unusual HCL
constructs (rare `dynamic` blocks, deeply-nested `for_each` expressions). The
parse-failure floor was the same on 2026-04-27 — this work did not introduce
new parse-failure modes.

### Module-expansion gap (still open)

The 2026-04-27 dogfood-findings doc identified module-expansion as a major
gap when scanning real ICP-A codebases. That gap is unchanged here — the
dogfood targets are themselves `terraform-aws-modules/*` repos, so we're
scanning the modules' own `*.tf` files (not module-consumer code).

The Priority 0 work (PRs landed earlier this week — module-call detection +
plan-JSON discoverability + Documentation Agent scan-coverage awareness)
remains the documented path for end-users scanning module-composed codebases.
This dogfood doesn't exercise that path.

---

## What this run validates

1. **The 43-detector catalog runs cleanly against real OSS Terraform** at the
   SHAs pinned in the dogfood script. No regressions from the catalog
   expansion or the cross-mapping work.
2. **The Priority 2/3 surface area additions** (new CLI commands, new HTML
   rendering paths, watcher, doctor) did not destabilize the scan path.
3. **Evidence-to-resource ratios are consistent with the catalog's design.**
   The detectors exist to fire on real code, and they do.

## What this run does NOT validate

- **The agent stages.** This dogfood is scan-only; running the Gap +
  Documentation + Remediation agents requires Anthropic API access and would
  consume budget against real-world targets. The 2026-04-27 dogfood doc
  validated end-to-end agent behavior on a single target.
- **Real customer feedback.** None of these are real customers. Priority 5
  (real-customer dogfood + 3PAO touchpoint) remains open and is the
  highest-leverage next-step that this work cannot replace.
- **The full pipeline UX from a fresh-eyes perspective.** A maintainer running
  `efterlev report run --watch` against an ICP-A-shaped target for the first
  time would catch UX paper-cuts that this multi-target sweep cannot.

---

## Recommendation

The catalog and surface area are at a clean v0.1.0 shape. The remaining work
to reach the public-flip gate is operational:

1. Maintainer runs `efterlev report run` end-to-end against a real ICP-A target
   (one of their own prospects' stacks if accessible, otherwise a real OSS
   deployment shape) — to capture any UX paper-cuts the multi-target sweep
   misses.
2. Priority 5 — at least one design-partner-class customer engagement and one
   3PAO touchpoint, captured per the spec in
   `docs/v1-readiness-plan.md`.
3. Security-review §8 sign-off, 24-hour fresh-eyes pause.
4. `git push origin v0.1.0`.

Nothing in the code surface blocks the v0.1.0 cut.
