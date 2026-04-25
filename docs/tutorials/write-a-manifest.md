# Write an Evidence Manifest

Stub for SPEC-38.10. Substantial content lands in a follow-up batch.

Evidence Manifests are YAML files under `.efterlev/manifests/*.yml` that declare human-signed procedural attestations. They fill the gap between scanner-visible evidence (Terraform-detectable) and the procedural KSIs no scanner can see — things like KSI-AFR-FSI (Federal Security Inbox: a monitored mailbox for federal-incident correspondence).

A reference template lives at [`docs/examples/evidence-manifests/security-inbox.yml`](https://github.com/efterlev/efterlev/blob/main/docs/examples/evidence-manifests/security-inbox.yml).

The shape:

```yaml
ksi: KSI-AFR-FSI
attestations:
  - statement: |
      Our designated security inbox security@example.com is monitored
      24/7 by the security on-call rotation; messages are triaged within
      4 business hours and acknowledged within 1 business day.
    attested_by: jane.doe@example.com
    attested_at: 2026-04-01
    reviewed_at: 2026-04-01
    next_review: 2026-10-01
    supporting_docs:
      - "https://wiki.internal/security-on-call"
      - "https://github.com/example/runbooks/blob/main/security-inbox.md"
```

Each attestation produces one Evidence record at scan time with `detector_id="manifest"`. The Gap Agent reasons about it alongside detector evidence.
