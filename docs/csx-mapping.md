# CSX KSI mapping — how Efterlev satisfies the cross-cutting KSIs

The FedRAMP 20x FRMR catalog (v0.9.43-beta) defines **60 thematic KSIs** across 11 themes
(AFR, CED, CMT, CNA, IAM, INR, MLA, PIY, RPL, SCR, SVC) plus **3 cross-cutting "CSX" KSIs**
(`KSI-CSX-SUM`, `KSI-CSX-MAS`, `KSI-CSX-ORD`) defined in the catalog's `FRR.KSI.data.20x.CSX`
section. AWS's 2026-04-27 deep-dive blog post counts the CSX KSIs alongside the thematic
ones and arrives at **63 KSIs / 12 themes**; Efterlev's catalog count of 60 / 11 reflects
only the thematic KSIs. Both are defensible accountings of the same catalog data.

This document maps each CSX KSI to the Efterlev artifacts that already satisfy it. **No new
code is required.** The CSX KSIs are about how providers organize their KSI evidence,
and Efterlev's existing pipeline produces the artifacts that organization needs.

For the full strategic analysis of the AWS blog and the catalog accounting question, see
[`docs/aws-ksi-blog-analysis-2026-04-28.md`](https://github.com/efterlev/efterlev/blob/main/docs/aws-ksi-blog-analysis-2026-04-28.md)
in the repository.

---

## KSI-CSX-SUM — Implementation Summaries

**FRMR statement** (paraphrased from `FRR.KSI.data.20x.CSX.KSI-CSX-SUM`):

> Providers MUST maintain simple high-level summaries of at least the following for each
> Key Security Indicator:
>
> - Goals for how it will be implemented and validated, including clear pass/fail criteria
>   and traceability
> - The consolidated information resources that will be validated
> - The machine-based processes for validation and the persistent cycle on which they will
>   be performed (or an explanation of why this doesn't apply)
> - The non-machine-based processes for validation and the persistent cycle on which they
>   will be performed (or an explanation of why this doesn't apply)
> - Current implementation status
> - Any clarifications or responses to the assessment summary

### How Efterlev satisfies CSX-SUM

The Documentation Agent's `documentation-{ts}.json` JSON sidecar
(see [PR #53](https://github.com/efterlev/efterlev/pull/53)) emits a per-KSI structured
record that maps directly to the CSX-SUM information requirements:

| CSX-SUM field | Efterlev artifact field |
|---|---|
| Goals + pass/fail criteria | `attestations[].draft.indicator.statement` (KSI statement from FRMR catalog) |
| Consolidated information resources | `attestations[].draft.citations[].source_file:line_range` + `evidence_id` |
| Machine-based validation processes | `attestations[].draft.citations[]` where `detector_id != "manifest"` (deterministic detector evidence) + `detector_id` names the specific machine process |
| Non-machine-based processes | `attestations[].draft.citations[]` where `detector_id == "manifest"` (Evidence Manifests carry the procedural attestations) |
| Persistent cycle | The CI integration cadence (`.github/workflows/pr-compliance-scan.yml` runs on every PR; `efterlev report run --watch` runs on every save during dev) |
| Current implementation status | `attestations[].draft.status` ∈ {implemented, partial, not_implemented, evidence_layer_inapplicable, not_applicable} |
| Clarifications | `attestations[].draft.narrative` (the Documentation Agent's prose explaining what the scanner saw + did not see) |

**To produce a CSX-SUM-compliant summary today:**

```bash
efterlev report run                                      # runs scan + Gap + Documentation
cat .efterlev/reports/documentation-*.json | jq .         # the CSX-SUM-shaped JSON sidecar
```

The output is already schema-versioned (`schema_version: "1.0"`) and machine-readable per
the FedRAMP 20x Phase 2 dual-format requirement. The accompanying
`documentation-{ts}.html` is the human-readable companion.

---

## KSI-CSX-MAS — Application within the Minimum Assessment Scope

**FRMR statement** (from `FRR.KSI.data.20x.CSX.KSI-CSX-MAS`):

> Providers SHOULD apply ALL Key Security Indicators to ALL aspects of their cloud service
> offering that are within the FedRAMP Minimum Assessment Scope.

### How Efterlev satisfies CSX-MAS

The boundary-scoping primitives shipped in **Priority 4** (pre-session work; see
[`src/efterlev/boundary.py`](https://github.com/efterlev/efterlev/blob/main/src/efterlev/boundary.py))
implement MAS scoping at the repo-relative file-path layer. The flow:

1. **Customer declares the MAS:**
   ```bash
   efterlev boundary set --include 'boundary/**' 'modules/in-scope-*/**'
   ```
   The patterns persist to `.efterlev/config.toml` as a list of gitignore-style globs.

2. **Every Evidence record carries a `boundary_state`** field with values
   `in_boundary`, `out_of_boundary`, or `boundary_undeclared`. Detectors populate
   it based on the source file's match against the boundary patterns.

3. **Every Claim inherits boundary state** from its cited evidence — a Claim citing
   only `out_of_boundary` evidence is itself flagged.

4. **The HTML gap report color-codes by boundary state.** `out_of_boundary` cards
   collapse under `<details>` so reviewers focus on in-scope findings; a
   `boundary_undeclared` workspace shows a banner explaining the customer should
   declare their MAS for an honest posture statement.

5. **POA&M output respects the boundary** — only `in_boundary` and
   `boundary_undeclared` evidence becomes POA&M items.

**Verifying a path's boundary state:**

```bash
efterlev boundary show           # list current rules
efterlev boundary check modules/in-scope-vpc/main.tf   # is this in/out of scope?
```

The `boundary_state` propagates through the JSON sidecars
(`workspace_boundary_state` at the top, plus per-classification `boundary_state`),
so a 3PAO ingesting the JSON has machine-readable evidence that the CSP
applied the KSIs across their declared MAS.

---

## KSI-CSX-ORD — Order of Criticality

**FRMR statement** (from `FRR.KSI.data.20x.CSX.KSI-CSX-ORD`):

> Providers MAY use the following order of criticality for approaching Authorization by
> FedRAMP Key Security Indicators for an initial authorization package: Minimum Assessment
> Scope (MAS), Authorization Data Sharing (ADS), Using Cryptographic Modules (UCM)...

### How Efterlev satisfies CSX-ORD

Two pieces of the existing pipeline implement criticality ordering:

#### POA&M severity ordering

`efterlev poam` emits a Plan of Action & Milestones markdown that orders entries by
severity:

- `not_implemented` → **HIGH** severity (top of the POA&M)
- `partial` → **MEDIUM** severity
- `implemented`, `not_applicable`, `evidence_layer_inapplicable` → not in the POA&M
  (no remediation needed)

Within each severity tier, KSIs are ordered alphabetically by KSI ID for stability.
This matches the CSX-ORD prescription that providers tackle the highest-criticality
gaps first.

#### Gap report status-filter pills

The HTML gap report
(see [PR #56](https://github.com/efterlev/efterlev/pull/56)) ships filter pills above the
classification list:

`[ All ] [ Implemented ] [ Partial ] [ Not implemented ] [ Evidence-layer inapplicable ] [ Not applicable ]`

A reviewer following CSX-ORD's criticality discipline clicks **"Not implemented"** to focus
on the highest-priority gaps, then **"Partial"** for the work-in-progress items, etc.
The sort dropdown's "By severity" option produces the same ordering directly in the
classification list:

```
not_implemented (rank 0) → partial (1) → implemented (2)
                        → evidence_layer_inapplicable (3) → not_applicable (4)
```

#### Combined: pre-export to a 3PAO

A typical CSX-ORD-aligned export workflow:

```bash
efterlev report run             # full pipeline produces gap + documentation + POA&M
efterlev poam                   # POA&M markdown ordered by severity
# Output: .efterlev/reports/poam-{ts}.md
```

The POA&M markdown is the artifact that demonstrates CSX-ORD compliance — the
ordered list directly answers the "which KSI is most critical to fix first" question
the FRMR statement asks providers to address.

---

## Summary

The 3 CSX KSIs are procedural meta-requirements about how to organize KSI evidence.
Every CSX KSI maps to existing Efterlev pipeline output:

| CSX KSI | Efterlev artifact | When it's produced |
|---|---|---|
| KSI-CSX-SUM | `documentation-{ts}.json` JSON sidecar | `efterlev agent document` |
| KSI-CSX-MAS | `boundary_state` field on every Evidence/Claim | `efterlev boundary set` declares; every Evidence gets the state |
| KSI-CSX-ORD | POA&M severity-ordered markdown + gap report filter pills | `efterlev poam` + the HTML gap report |

No new detector code is required. A CSP using Efterlev's full pipeline is already producing
CSX-compliant output; the artifacts just need to be presented to a 3PAO with the CSX
mapping made explicit. This document is that explicit mapping.
