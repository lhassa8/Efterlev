# POA&M markdown reference

Stub for SPEC-38.13. Substantial content lands in a follow-up batch.

The `efterlev poam` CLI emits a Plan of Action & Milestones markdown at `.efterlev/reports/poam-<timestamp>.md` for every KSI the Gap Agent classified as `partial` or `not_implemented`.

Per-item shape:

```markdown
## POA&M-XXXXXX — KSI-X-Y (status, severity)

**Weakness:** [drafted from gap classification narrative]

**Risk to system:** DRAFT — reviewer to fill in.

**Mitigation:** DRAFT — reviewer to fill in.

**Resources required:** DRAFT — reviewer to fill in.

**Scheduled completion date:** DRAFT — reviewer to fill in.

**Milestones:** DRAFT — reviewer to fill in.

**Comments:** DRAFT — reviewer to fill in.

**Source evidence:** content-addressed IDs of the evidence records this POA&M derives from.
```

Severity heuristic:

- `not_implemented` → HIGH
- `partial` → MEDIUM
- (LOW reserved for future use)

POA&M IDs derive from the underlying Claim's `record_id` prefix so the markdown is provenance-linked. OSCAL-shaped POA&M JSON is a v1.5+ deliverable, gated on first OSCAL-Hub-consuming customer.
