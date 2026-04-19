# catalogs/

FedRAMP and NIST OSCAL source materials vendored into the repo for determinism and air-gap
friendliness. `efterlev init` references these files in place rather than downloading at
runtime. An `efterlev catalog update` command is planned for v1 for users who want the latest;
v0 ships with a known-good pinned set.

## Contents (to be populated pre-hackathon)

Target files:

- `fedramp-moderate.json` — FedRAMP Moderate profile (OSCAL), from
  [`GSA/fedramp-automation`](https://github.com/GSA/fedramp-automation)
- `NIST_SP-800-53_rev5_catalog.json` — NIST SP 800-53 Rev 5 catalog, from
  [`usnistgov/OSCAL`](https://github.com/usnistgov/OSCAL)

## Provenance record

As each file lands here, append a row documenting its source repository, commit SHA, download
date, and file SHA-256. This lets any contributor reproduce the vendored state and gives us an
audit trail if the upstream content changes.

| File | Source repo | Commit SHA | Downloaded | SHA-256 |
| ---- | ----------- | ---------- | ---------- | ------- |
| _(none yet)_ | | | | |
