# CSX KSI mapping — how Efterlev satisfies the cross-cutting KSIs

The FedRAMP 20x FRMR catalog (v0.9.43-beta) defines **60 thematic KSIs** across 11 themes
(AFR, CED, CMT, CNA, IAM, INR, MLA, PIY, RPL, SCR, SVC) plus **3 cross-cutting "CSX" KSIs**
(`KSI-CSX-SUM`, `KSI-CSX-MAS`, `KSI-CSX-ORD`) defined in the catalog's `FRR.KSI.data.20x.CSX`
section. AWS's 2026-04-27 deep-dive blog post counts the CSX KSIs alongside the thematic
ones and arrives at **63 KSIs / 12 themes**; Efterlev's catalog count of 60 / 11 reflects
only the thematic KSIs. Both are defensible accountings of the same catalog data.

This document maps each CSX KSI to the Efterlev artifacts **shaped to satisfy** it.
The CSX KSIs are about how providers organize their KSI evidence, and Efterlev's
existing pipeline produces artifacts that line up with those organization requirements.
Two important honesty notes up front:

1. **Empirical 3PAO acceptance** of the CSX-SUM-shaped artifact is a post-launch
   validation milestone (real-customer dogfood + 3PAO touchpoint). Until that
   closes, "shaped to satisfy" is the correct phrasing — not "satisfies."
2. **CSX-ORD alignment is partial.** Efterlev's POA&M severity ordering implements
   *criticality-based triage*, which is what the CSX-ORD spirit is about; it does
   not yet emit the catalog's prescribed initial-authorization KSI sequence
   (MAS, ADS, UCM…) directly. A `--csx-ord-sort` mode that emits the prescribed
   sequence is on the v0.1.x backlog.

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

### How Efterlev's output is shaped for CSX-SUM

The Documentation Agent's `documentation-{ts}.json` JSON sidecar
(see [PR #53](https://github.com/efterlev/efterlev/pull/53)) emits a per-KSI structured
record that maps to most CSX-SUM information requirements:

| CSX-SUM field | Efterlev artifact field | Status |
|---|---|---|
| Goals + pass/fail criteria | `attestations[].draft.indicator.statement` (KSI statement from FRMR catalog) | ✅ in artifact |
| Consolidated information resources | `attestations[].draft.citations[].source_file:line_range` + `evidence_id` | ✅ in artifact |
| Machine-based validation processes | `attestations[].draft.citations[]` where `detector_id != "manifest"` (deterministic detector evidence) + `detector_id` names the specific machine process | ✅ in artifact |
| Non-machine-based processes | `attestations[].draft.citations[]` where `detector_id == "manifest"` (Evidence Manifests carry the procedural attestations) | ✅ in artifact |
| Persistent cycle | **Not in the artifact today.** Cadence is supplied by the customer's CI integration (`.github/workflows/pr-compliance-scan.yml` runs on every PR; `efterlev report run --watch` runs on every save during dev). | ⚠️ adjacent, not inline |
| Current implementation status | `attestations[].draft.status` ∈ {implemented, partial, not_implemented, evidence_layer_inapplicable, not_applicable} | ✅ in artifact |
| Clarifications | `attestations[].draft.narrative` (the Documentation Agent's prose explaining what the scanner saw + did not see) | ✅ in artifact |

**Cadence-field gap.** CSX-SUM lists the persistent-validation cycle as a required
field per KSI summary. The artifact today does not carry a `validation_cadence` /
`persistent_cycle` field inline; cadence is supplied by the customer's CI integration
and visible in the receipt log + workflow history. A 3PAO consuming the JSON today
would need to look at the workflow YAML alongside the artifact. Adding the field
inline is small (~30 LoC + schema version bump); on the v0.1.x backlog.

**To produce a CSX-SUM-shaped summary today:**

```bash
efterlev report run                                      # runs scan + Gap + Documentation
cat .efterlev/reports/documentation-*.json | jq .         # the CSX-SUM-shaped JSON sidecar
```

The output is schema-versioned (`schema_version: "1.0"`) and machine-readable per
the FedRAMP 20x Phase 2 dual-format requirement. The accompanying
`documentation-{ts}.html` is the human-readable companion. **Empirical 3PAO
acceptance of the artifact** is the next validation milestone (real-customer
dogfood + 3PAO touchpoint).

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

### Where Efterlev's output aligns — and where it doesn't

CSX-ORD prescribes a **specific KSI sequence** for initial authorization: MAS first,
then ADS, then UCM, and so on. It is a *prescribed catalog ordering*, not a
severity sort.

Efterlev today implements **criticality-based triage**, which is the spirit of
CSX-ORD but not the prescribed sequence:

#### POA&M severity ordering (criticality-based triage)

`efterlev poam` emits a Plan of Action & Milestones markdown that orders entries by
severity:

- `not_implemented` → **HIGH** severity (top of the POA&M)
- `partial` → **MEDIUM** severity
- `implemented`, `not_applicable`, `evidence_layer_inapplicable` → not in the POA&M
  (no remediation needed)

Within each severity tier, KSIs are ordered alphabetically by KSI ID for stability.
A reviewer using the POA&M is naturally led to tackle the highest-criticality gaps
first — which lines up with the CSX-ORD intent of "tackle the most important first,"
but is **not** the catalog-prescribed MAS → ADS → UCM sequence.

#### Gap report status-filter pills

The HTML gap report
(see [PR #56](https://github.com/efterlev/efterlev/pull/56)) ships filter pills above the
classification list:

`[ All ] [ Implemented ] [ Partial ] [ Not implemented ] [ Evidence-layer inapplicable ] [ Not applicable ]`

A reviewer can click **"Not implemented"** to focus on highest-priority gaps. Same
caveat: this is criticality triage, not the prescribed catalog sequence.

#### What's not yet implemented

A `--csx-ord-sort` mode that emits the catalog's prescribed initial-authorization
KSI sequence (MAS, ADS, UCM, …) directly is on the v0.1.x backlog. This is the
work that would let Efterlev claim "satisfies CSX-ORD" rather than "aligns with
CSX-ORD's intent." Today the prescribed sequence is data the customer or 3PAO
extracts from the FRMR catalog directly.

#### Honest summary

> **Efterlev's POA&M is a criticality-triaged remediation list.** A 3PAO using
> CSX-ORD's catalog-prescribed sequence to drive their assessment workflow gets
> partial value from Efterlev's POA&M today. The prescribed-sequence sort is on
> the backlog; until then, customers should pair Efterlev's output with the
> FRMR catalog's own ordering for the strict CSX-ORD case.

---

## Summary

The 3 CSX KSIs are procedural meta-requirements about how to organize KSI evidence.
Each CSX KSI has a corresponding Efterlev pipeline output:

| CSX KSI | Efterlev artifact | Status |
|---|---|---|
| KSI-CSX-SUM | `documentation-{ts}.json` JSON sidecar | Shaped to satisfy; cadence-field gap noted; empirical 3PAO acceptance gated on Priority 5 |
| KSI-CSX-MAS | `boundary_state` field on every Evidence/Claim | Implemented (Priority 4 work) |
| KSI-CSX-ORD | POA&M severity-ordered markdown + gap report filter pills | Aligns with intent (criticality triage); catalog-prescribed sequence (MAS, ADS, UCM…) on backlog |

A CSP using Efterlev's full pipeline produces output **shaped to** organize KSI
evidence per the CSX requirements. Closing the remaining gaps (cadence field on
CSX-SUM, prescribed-sequence sort on CSX-ORD, 3PAO empirical acceptance) is
v0.1.x work tracked alongside Priority 5.
