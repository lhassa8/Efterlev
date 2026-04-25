# Pre-launch security review — 2026-04

**Status:** in progress (template populated 2026-04-25; reviewer sign-off pending)
**Reviewer:** _pending — to be filled in by maintainer at review time_
**Commit SHA:** _pending_
**Repo state:** pre-launch (private), all gate-A trust-surface deliverables landed

This document is the structured walkthrough required by SPEC-30.8 before the repo flips public. It records what the reviewer looked at, what they found, and what didn't make the cut. It is NOT a marketing artifact — failures land here truthfully.

The reviewer template below is filled in by the maintainer (and ideally a second reviewer) before A8 launch rehearsal completes. Until that happens the document carries the "in progress" status.

---

## 1. Threat-model coverage

For each named threat in [`THREAT_MODEL.md`](../THREAT_MODEL.md), record one of:

- **Mitigated** — the threat has a named mitigation in code/config; spot-check evidence cited below.
- **Accepted residual risk** — the threat is acknowledged and accepted; rationale cited below.
- **Open with tracker** — issue filed, not blocking launch, with link.

| Threat | Status | Spot-check evidence |
|---|---|---|
| _Fill in per THREAT_MODEL.md threat list at review time._ | | |

## 2. Dependency review

`pip-audit` output snapshot at review-commit SHA:

```
<paste output here>
```

**Waived findings (if any):**

| CVE | Package | Why waived |
|---|---|---|
| _none yet, hopefully._ | | |

## 3. Secret-handling review

Confirm `scrub_llm_prompt` runs unconditionally on all egress paths. Spot-check at least 3 code paths:

- [ ] `format_evidence_for_prompt` in `src/efterlev/agents/base.py` — calls scrubber unconditionally.
- [ ] `format_source_files_for_prompt` in `src/efterlev/agents/base.py` — calls scrubber unconditionally.
- [ ] `AnthropicBedrockClient.complete` (SPEC-10) — confirm prompt arrives at boto3 already-scrubbed (the scrubber runs upstream in the agents, not in the client; verify by tracing one call).

Note any path that bypasses the scrubber (should be none).

## 4. Provenance integrity review

Confirm `validate_claim_provenance` is wired at `ProvenanceStore.write_record` for `record_type="claim"`:

- [ ] Read `src/efterlev/provenance/store.py` `write_record` — confirms the gate.
- [ ] Read `tests/test_validate_claim_provenance.py` — confirms tests exercise both record-id and evidence-id resolution paths AND insertion-atomicity (rejected claim doesn't mutate the store).
- [ ] Per-agent `_validate_cited_ids` helpers in `src/efterlev/agents/{gap,documentation,remediation}.py` — confirm each agent rejects model-output that cites unfencied IDs.

## 5. Build + release review

Each release pipeline (SPEC-05/06/08/09) uses keyless OIDC auth and Sigstore signing — no long-lived credentials.

- [ ] `.github/workflows/release-pypi.yml` — uses `pypa/gh-action-pypi-publish@release/v1` with trusted publishing.
- [ ] `.github/workflows/release-container.yml` — uses cosign keyless-OIDC; SLSA provenance via buildx.
- [ ] `.github/workflows/release-smoke.yml` — runs the install-verification matrix; gates real-PyPI upload via the `pypi` GitHub environment's manual approval.
- [ ] No long-lived secrets in any release workflow other than `DOCKERHUB_TOKEN` (Docker Hub doesn't yet support keyless OIDC for image push at the time of review).

## 6. Public-repo posture

- [ ] No accidental NDA-era / private-repo-era language remaining (run the pre-flip grep sweep from A8 launch rehearsal).
- [ ] No internal hostnames, SSH keys, or credentials in any committed file.
- [ ] `.dockerignore` and `.gitignore` confirmed correct — `.efterlev/` (per-customer state), `.e2e-results/` (local artifacts), and dev caches are excluded.
- [ ] Branch protection on `main` configured per `.github/BRANCH_PROTECTION.md`; enforce_admins on; required signed commits on (or note the BDFL-era waiver).

## 7. Open items

- _Anything found during review that didn't make the launch cut. Each item gets a tracking issue._

| Issue | Severity | Why not a blocker |
|---|---|---|
| _none yet._ | | |

## Sign-off

| Reviewer | GitHub handle | Commit SHA reviewed | Date | Notes |
|---|---|---|---|---|
| _Pending_ | | | | |

A second reviewer is welcome but not required at v0.1.0 — the BDFL-era process is a self-review with the rigor this template enforces. A second reviewer is recommended for v0.2.0 onward as the contributor pool grows.
