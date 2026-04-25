# Provenance

> How every generated artifact traces back to its source.

This page is a placeholder for SPEC-38.4. Substantial content lands in a follow-up batch.

Every detector finding, every AI claim, every remediation suggestion is a node in a local graph (SQLite plus a content-addressed file store under `.efterlev/`). Edges point from derived claims to their sources. The graph is **append-only** — new evidence does not overwrite old, it adds.

`efterlev provenance show <record_id>` walks the chain from any output sentence back to the file and line that produced it.

This is the architecture commitment that lets us tell a 3PAO: "every assertion in this attestation has a traceable provenance back to either a Terraform line your team wrote or a customer-attested manifest entry your team signed."
