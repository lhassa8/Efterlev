# Changelog

All notable changes to Efterlev will be tracked here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) loosely.

## [0.1.2] — 2026-04-30

Patch release closing two real-CI bugs surfaced by the govnotes-demo
deep-dive shakedown — the canonical Evidence Manifest pattern (commit
manifests, gitignore cache) didn't survive a fresh clone, and v0.1.1's
bumped `max_tokens=32768` tripped Anthropic's streaming-required
threshold and prevented the gap agent from running at all.

### Fixed

- **`report run` skipped init when `.efterlev/manifests/` was the only
  thing in the workspace dir.** The detection looked at the dir, not
  the FRMR cache file scan needs. Fresh clones with manifests
  committed but the cache gitignored hit "FRMR cache missing"
  immediately. `report run` now detects the cache (the actual
  artifact) and passes `--force` to its sub-init step when the dir
  exists but the cache is missing — regenerates cache + provenance
  store while preserving customer-authored manifests. Regression
  test added.
- **Gap Agent `max_tokens=32768` raised "streaming required" on real
  workloads.** Anthropic's `messages.create()` (non-streaming) path
  rejects requests whose `max_tokens` could plausibly take >10
  minutes. Reduced to **20480** — enough headroom over the v0.1.0
  truncation site (~16384) for the full 60-KSI baseline with
  substantive rationales, but well below the streaming threshold.
  If real workloads need more, the right move is the streaming
  refactor (`client.messages.stream()`), not chasing the cap.
- **README + CLAUDE.md test count drift** (1019 → 1020 after PR #104
  added a regression test for the half-init pattern).

### Notes

- Streaming refactor of the Anthropic client is queued as a
  v0.2.0-targeted item — the right structural fix when output budget
  needs to grow further. The fake-client surface in
  `tests/test_anthropic_retry_fallback.py` would need rewiring for a
  streaming context manager.

## [0.1.1] — 2026-04-29

Patch release closing three v0.1.0 bugs surfaced in a deep-dive shakedown
test against `terraform-aws-modules/terraform-aws-iam` and a synthetic
ground-truth target.

### Fixed

- **Gap Agent `max_tokens` truncation.** The cap was 16384, which truncated
  mid-JSON on real-world full-baseline runs (60 KSIs each with substantive
  rationales). Bumped to 32768 — Claude Opus 4.7's output ceiling. The
  agent's own error message ("increase the max_tokens argument") is now
  acted on; full-baseline runs complete without truncation.
- **Confusing LLM-invocation transcript record.** `agents.base._invoke_llm`
  used to write a per-run transcript record with `record_type="claim"`,
  payload `{user_message, response_text, parsed}`, and empty `derived_from`.
  It looked like a malformed Claim to anyone listing claim records or
  walking provenance — and triggered tester confusion about whether the
  retry path was corrupting state. Removed; per-claim records (per KSI for
  Gap, per narrative for Documentation, per remediation for Remediation)
  already carry `model`, `prompt_hash`, and properly-populated
  `derived_from`. No information loss.
- **`efterlev --version` reported stale `0.0.1` from the published 0.1.0
  wheel.** `pyproject.toml` had a version literal `"0.1.0"` while
  `src/efterlev/__init__.py` had `__version__ = "0.0.1"` — two sources of
  truth, drifted. Switched to hatch dynamic versioning
  (`[tool.hatch.version] path = "src/efterlev/__init__.py"`) so pyproject
  reads from the source file. Added a CI-time regression test
  (`test_in_source_version_matches_package_metadata`) so future drift is
  caught before release.

### Notes

- Bug #5 from the shakedown report (gap/remediate disagreement on
  KSI-AFR-UCM scope: gap classified `partial` citing FIPS-TLS evidence, but
  remediate refused with "no Terraform surface to remediate") deferred to
  `docs/followups.md`. Root cause is design-level: the Gap Agent has
  freedom to cite any prompt-visible Evidence in its rationale, while
  remediate's CLI gate strictly filters by `Evidence.ksis_evidenced`. The
  fix needs a design call between trusting the Gap Agent's citations vs.
  enforcing detector-level KSI mapping at remediate time. Not a regression;
  present in v0.1.0.
- Prompt-tuning concerns from the shakedown (systematic leniency, rationale
  reuse across thematically-adjacent KSIs) are v0.2.0 work — they want a
  real-customer evidence corpus to tune against rather than synthetic
  dogfood.

## [0.1.0] — 2026-04-29

First public release. The work in this section closes Priorities 1, 2,
and 3 of `docs/v1-readiness-plan.md` plus the post-launch-prep
walkback / audit / new-detector arc. 51 PRs landed 2026-04-27 →
2026-04-29 (#36 → #96).

### Priority 1 — Detector breadth (✅ complete; lifted post-floor)

Coverage moved from 14 → 31 KSIs / 5 → 8 themes / 38 → 45 detectors.
The plan's ≥30 KSI / ≥8 theme floor was reached at PR #51; post-walkback
work (PRs #88, #89, #92) lifted coverage to 31 / 8 / 45.

- **Added detectors:**
  - `aws.terraform_inventory` — KSI-PIY-GIV (PR #39)
  - `aws.s3_lifecycle_policies` — KSI-SVC-RUD (PR #40)
  - `aws.federated_identity_providers` — KSI-IAM-APM (PR #41)
  - `aws.iam_managed_via_terraform` — KSI-IAM-AAM (PR #42)
  - `aws.cloudfront_viewer_protocol_https` — KSI-SVC-VCM (PR #47)
  - `aws.ec2_imdsv2_required` — KSI-CNA-IBP (PR #48); cross-mapped to KSI-CNA-DFP via CM-2 (PR #51)
  - `aws.backup_restore_testing` — KSI-RPL-TRC (PR #49)
  - `aws.suspicious_activity_response` — KSI-IAM-SUS (PR #50)
  - `aws.vpc_logical_segmentation` — KSI-CNA-ULN (PR #36)
  - `github.ci_validation_gates` — KSI-CMT-VTD (PR #37)
  - `github.supply_chain_monitoring` — KSI-SCR-MON (PR #38)
  - `github.immutable_deploy_patterns` — KSI-CMT-RMV (PR #44)
  - `github.action_pinning` — KSI-SCR-MIT (PR #46)

- **Cross-mappings** (existing detectors gained additional KSI attributions
  via FRMR control overlap, not invented attribution):
  - `aws.cloudtrail_audit_logging` → +KSI-CMT-LMC via AU-2 (PR #43)
  - `aws.iam_admin_policy_usage`, `aws.iam_inline_policies_audit` → +KSI-IAM-JIT via AC-6 (PR #45)
  - `aws.ec2_imdsv2_required` → +KSI-CNA-DFP via CM-2 (PR #51)

### Priority 2 — HTML report overhaul (✅ complete)

All 9 acceptance items closed. 11 PRs (#52 → #62 + #63 doc).

- **JSON sidecars on all 3 reports** — `gap-{ts}.json`, `documentation-{ts}.json`,
  `remediation-{ksi}-{ts}.json`. Schema-versioned; suitable for tool integration.
  PRs #52, #53, #54.
- **Coverage matrix** — single-page heatmap of all 11 themes × 60 KSIs at the
  top of the gap report. KSIs the agent didn't classify render as `unclassified`.
  Click any cell to scroll to the per-KSI classification card. PR #55.
- **Filter by status** — single-click pills above the classification list.
  Inline vanilla JS, no framework. PR #56.
- **Free-text search** — debounced input, live match count, additive with
  the status filter. PR #57.
- **Print stylesheet** — interactive bits hide; cards don't split across
  pages; out-of-boundary `<details>` expand on paper. PR #58.
- **Sort controls** — by KSI / severity / evidence count. PR #59.
- **Drill-down** — per-classification `<details>` listing each cited
  evidence's `source_file:line_range`. JSON sidecar gains
  `cited_evidence_refs[]`. PR #60.
- **Diff view** — `efterlev report diff PRIOR CURRENT` writes both
  `gap-diff-{ts}.html` and `gap-diff-{ts}.json`. CI-gateable: exits 2 on
  regression. PRs #61 (compute), #62 (CLI + HTML).

All Priority-2 features are self-contained (no external CDN, no fonts beyond
system-default, no analytics) and degrade gracefully without JavaScript
(filter/sort show all results in input order).

### Post-launch-prep walkback + audit (✅ complete)

Triggered by AWS's 2026-04-27 FedRAMP 20x deep-dive blog and a
maintainer review pass. 12 PRs landed 2026-04-28 → 2026-04-29
(#80 → #92), plus the dependency unblock #93.

**Detector additions:**
- `aws.nacl_restrictiveness` — KSI-CNA-RNT (PR #88). Per-NACL
  posture summary (restrictive / partially_restrictive / permissive
  / empty); emits Evidence even on clean NACLs so positive evidence
  flows to the Gap Agent.
- `aws.centralized_log_aggregation` — KSI-MLA-OSM (PR #89). Workspace-
  scoped summary of log producers + aggregators; closes the
  "no SIEM aggregation primitives visible" agent narrative gap.

**Detector reclassifications:**
- `aws.iam_user_access_keys` (PR #92): primary mapping
  KSI-IAM-MFA → **KSI-IAM-SNU** (Securing Non-User Authentication);
  KSI-IAM-MFA preserved as cross-mapping. Adds KSI-IAM-SNU to the
  covered set (30 → 31 KSIs).

**Mapping audits + partial-coverage discipline:**
- PR #83: SVC-RUD and SVC-VCM downgraded to partial cross-mappings
  with explicit notes (scheduled-vs-on-request, viewer-edge-vs-S2S).
- PR #91: 6 detectors gained explicit `coverage: partial` notes
  (cloudtrail_log_file_validation, cloudwatch_alarms_critical,
  guardduty_enabled, elb_access_logs, vpc_flow_logs_enabled,
  access_analyzer_enabled).
- PR #90: systematic audit of all 34 remaining KSI-mapped detectors
  (`docs/detector-mapping-audit.md`). 23 direct fits, 9 partial
  cross-mappings, 2 reclassification candidates.

**Real bug fixes:**
- PR #82: FRMR loader now reads `varies_by_level.{level}.statement`
  with fallback to top-level. 5 KSIs (KSI-CNA-EIS, KSI-MLA-ALA,
  KSI-SVC-PRR, KSI-SVC-RUD, KSI-SVC-VCM) were silently statement-
  less; the Gap Agent had been classifying them blind.
- PR #81: report path display uses the user-supplied form (e.g.
  `/tmp/...`) instead of canonical (`/private/tmp/...`); macOS
  symlink paper-cut surfaced by a real local run.

**CSX-SUM / CSX-ORD gap closures:**
- PR #84: `validation_cadence` field added to documentation artifact
  (closes the CSX-SUM cadence-field-gap acknowledged in csx-mapping.md).
- PR #85: `efterlev poam --sort csx-ord` mode (closes the CSX-ORD
  prescribed-sequence-sort gap).

**Init-time UX:**
- PR #86: catalog freshness warning at `efterlev init` (180-day
  staleness + post-CR26-window heuristics).

**Framing walkback:**
- PR #80: walked back overclaims in csx-mapping.md / aws-coexistence.md
  / release-notes-v0.1.0-draft.md / README.md / aws-ksi-blog-analysis.md.
  "shaped to satisfy CSX-SUM" instead of "IS the artifact 3PAOs
  consume" (pending Priority 5 empirical validation).

**Documentation + upstream:**
- PR #87: drafts of two FRMR upstream feedback issues (file post-tag).
- PR #93: pathspec upper bound widened `<1` → `<2` to unblock
  Dependabot resolver.

**Dependabot bulk-merge:**
- 7 minor/major version bumps merged (#3, #4, #5, #6, #7, #9, #10).
  Python 3.14 (#2) and mypy 1.20 (#8) deferred to v0.1.x.

### Priority 3 — UX during install and usage (✅ complete)

All 6 acceptance items closed. 6 PRs (#64 → #69 + #70 doc).

- **`efterlev doctor`** — five pre-flight checks (Python, .efterlev workspace,
  FRMR cache freshness, ANTHROPIC_API_KEY shape, AWS Bedrock credentials)
  with per-check pass/warn/fail and remediation hints. No network calls.
  PR #64.
- **Friendly errors** — all 8 typed `anthropic.APIError` subclasses mapped to
  one-line messages + remediation hints at the agent CLI boundary. PR #65.
- **`efterlev report run`** — one-command pipeline (init → scan → agent gap
  → agent document → poam) with per-stage `--skip-*` flags. PR #66.
- **First-run wizard** — TTY-gated, credential-aware intro at `efterlev init`.
  Auto-skips on non-TTY (CI-safe); never modifies config silently. PR #67.
- **Progress indicators** — Documentation Agent emits
  `[idx/total] KSI-XXX ✓` per narrative to stderr. PR #68.
- **`--watch` mode** — `efterlev report run --watch` polls the target for
  `.tf`/`.tfvars`/`.yml`/`.yaml`/`.json` changes (debounced 2s) and re-runs
  the pipeline. Polling-based, no `watchdog` dependency. PR #69.

### Catalog stats (post-session)

- 1018 tests passing
- 172 source files
- 24 CLI commands
- 45 detectors (38 KSI-mapped + 7 supplementary 800-53-only)
- 31 KSIs covered across 8 themes
- mypy strict / ruff check / ruff format clean

### Documentation

- `docs/v1-readiness-plan.md` updated to mark Priorities 1, 2, 3 complete
  with PR pointers per acceptance item (PRs #51, #63, #70).

### Out of scope this session

- Priority 4 (boundary scoping): already shipped pre-session.
- Priority 5 (real customer dogfood + 3PAO touchpoint): calendar-time
  work outside the code surface — needs maintainer outreach.
- Priority 6 (honesty pass on `ksis=[]` detectors): already done
  pre-session.

The remaining gates to v0.1.0 are: maintainer security-review §8 sign-off,
24-hour fresh-eyes pause, optional GovCloud walkthrough, then `git push
origin v0.1.0`.
