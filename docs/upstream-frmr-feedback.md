# Upstream FRMR feedback (drafts ready to file)

Issues we've found vendoring and consuming the
[FedRAMP/docs FRMR catalog](https://github.com/FedRAMP/docs) that are worth
raising upstream. Each is drafted as a ready-to-paste issue body.

The maintainer files these against `FedRAMP/docs` directly with their own
attribution; this doc is the working draft, not the filed issue.

---

## Draft #1 — Inconsistent placement of `statement` field across KSIs in 0.9.43-beta

**Suggested title:** Some KSI `statement` fields live at top level; others at `varies_by_level.{level}.statement` — consumers need consistent placement

**Suggested labels:** `documentation`, `consumer-feedback`, `consistency`

**Body:**

> Hi FedRAMP team — thanks for the FRMR catalog and the v0.9.x progression.
> One observation while building a tooling integration:
>
> In `FRMR.documentation.json` v0.9.43-beta, the per-KSI `statement` field is
> placed inconsistently across the 60 thematic KSIs:
>
> - **55 KSIs** carry a top-level `statement` field on the indicator object.
> - **5 KSIs** carry no top-level `statement` and instead nest the
>   level-specific text under `varies_by_level.{low,moderate,high}.statement`.
>   The 5 are: `KSI-CNA-EIS`, `KSI-MLA-ALA`, `KSI-SVC-PRR`, `KSI-SVC-RUD`,
>   `KSI-SVC-VCM`.
>
> The catalog's `updated` log notes that the v0.9.0 standardization moved
> impact-specific statements down a level for some KSIs, but the migration
> appears partial — most KSIs retained their original top-level statements
> while these 5 moved entirely.
>
> **Why it matters for downstream consumers:** A naive loader that reads
> `statement` from the top-level indicator object silently drops the
> statement for those 5 KSIs. The downstream tool then either misclassifies
> ("this KSI has no outcome to evidence") or has to special-case the 5.
>
> **Suggested resolutions** (any one would work; no preference from our side):
>
> 1. **Standardize on `varies_by_level`** — move all 60 KSI statements to
>    `varies_by_level.{level}.statement`. This is the more expressive form
>    (different impact levels can carry different text) and the v0.9.0 note
>    suggests that was the intent.
>
> 2. **Standardize on top-level `statement`** — move the 5 outliers' moderate
>    statement back up. Less expressive but consistent.
>
> 3. **Document the dual placement** — update the FRMR schema to make the
>    invariant explicit: "A KSI has a statement either at top level OR in
>    `varies_by_level.{level}.statement`, never both." Make the schema reject
>    KSIs that have neither.
>
> The 5 KSIs in question all have substantive moderate-level statements
> (visible at `varies_by_level.moderate.statement`); this isn't a content
> gap, just a placement inconsistency.
>
> Happy to send a PR if a specific resolution is desired.

**Reference:** `catalogs/frmr/FRMR.documentation.json @ 0.9.43-beta` as
vendored at <https://github.com/FedRAMP/docs/blob/main/FRMR.documentation.json>
on 2026-04-08.

---

## Draft #2 — KSI-CSX-ORD prescribed sequence uses "(RSC)" abbreviation but the matching KSI ID has `SCG` suffix

**Suggested title:** `KSI-CSX-ORD.following_information` says "Secure Configuration Guide (RSC)" but the corresponding KSI ID is `KSI-AFR-SCG`

**Suggested labels:** `documentation`, `consistency`

**Body:**

> Small one: the `following_information` array under
> `FRR.KSI.data.20x.CSX.KSI-CSX-ORD` lists the prescribed initial-authorization
> sequence as 10 phrases of the form `"<Full Name> (<3-letter code>)"`. For
> the seventh entry, the catalog says:
>
> ```
> "Secure Configuration Guide (RSC)"
> ```
>
> But the corresponding KSI in the AFR theme has ID `KSI-AFR-SCG`, not
> `KSI-AFR-RSC`. Every other entry's parenthetical 3-letter code matches the
> corresponding KSI ID's 3-letter suffix:
>
> | Phrase | KSI ID |
> |---|---|
> | Minimum Assessment Scope (MAS) | KSI-AFR-MAS |
> | Authorization Data Sharing (ADS) | KSI-AFR-ADS |
> | Using Cryptographic Modules (UCM) | KSI-AFR-UCM |
> | Vulnerability Detection and Response (VDR) | KSI-AFR-VDR |
> | Significant Change Notifications (SCN) | KSI-AFR-SCN |
> | Persistent Validation and Assessment (PVA) | KSI-AFR-PVA |
> | **Secure Configuration Guide (RSC)** | **KSI-AFR-SCG** |
> | Collaborative Continuous Monitoring (CCM) | KSI-AFR-CCM |
> | FedRAMP Security Inbox (FSI) | KSI-AFR-FSI |
> | Incident Communications Procedures (ICP) | KSI-AFR-ICP |
>
> **Suggested fix:** change the seventh entry from
> `"Secure Configuration Guide (RSC)"` to `"Secure Configuration Guide (SCG)"`
> so a consumer mapping the prescribed sequence to KSI IDs by 3-letter code
> finds a clean match.
>
> (We worked around this by matching on the long-form name, which is robust
> to the abbreviation typo, but the fix would simplify other consumers'
> implementations.)

---

## Filing checklist (for the maintainer)

When ready to file:

- [ ] Open <https://github.com/FedRAMP/docs/issues>
- [ ] Search for prior art — these may already be filed by other consumers.
- [ ] Paste the appropriate draft.
- [ ] Add a one-line context: "Filing on behalf of Efterlev
  (https://github.com/efterlev/efterlev), an OSS FedRAMP 20x compliance
  scanner that consumes `FRMR.documentation.json` directly."
- [ ] Link to the specific Efterlev PRs that worked around each issue:
  - For draft #1: PR #82 (loader fix for `varies_by_level`)
  - For draft #2: PR #85 (POA&M `--csx-ord-sort` mode using name-matching)
- [ ] After filing: link the upstream issue number from this doc as
  evidence that the feedback flowed.

---

## Why we file these (and why we wait until after v0.1.0)

Open feedback to upstream is a healthy posture; FedRAMP has an open
contribution model on the docs repo. We hold these drafts until v0.1.0
ships so the filed issue can reference an actual project, with actual
users, rather than a pre-launch demo. Once v0.1.0 publishes, the issues
become "consumer feedback from a working FedRAMP 20x toolchain" rather
than a hypothetical observation — that's a meaningful difference for
how the FedRAMP team prioritizes catalog consistency work.
