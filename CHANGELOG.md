# Changelog

All notable changes to Efterlev will be tracked here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) loosely; we
group by `docs/v1-readiness-plan.md` priorities for the v1-shaped
release.

## [Unreleased] — v0.1.0 close-out

The work in this section closes Priorities 1, 2, and 3 of
`docs/v1-readiness-plan.md`. 35 PRs landed 2026-04-27 → 2026-04-28
(#36 → #70).

### Priority 1 — Detector breadth (✅ complete)

Coverage moved from 14 → 30 KSIs / 5 → 8 themes / 38 → 43 detectors.
The plan's ≥30 KSI / ≥8 theme floor was reached at PR #51.

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

- 970+ tests passing
- 167 source files
- 24 CLI commands
- 43 detectors (36 KSI-mapped + 7 supplementary 800-53-only)
- 30 KSIs covered across 8 themes
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
