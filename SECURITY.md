# Security Policy

Thank you for helping keep Efterlev and its users safe.

## Reporting a vulnerability

**Do not file security issues as public GitHub issues.**

Report vulnerabilities through one of these private channels:

1. **GitHub Security Advisories — preferred.** Click [here](https://github.com/efterlev/efterlev/security/advisories/new) (or repo → Security → Advisories → "Report a vulnerability"). GitHub's private-vulnerability-reporting feature gives us a structured intake plus an embedded discussion thread.
2. **Email.** `security@efterlev.com`. Use this if GitHub Security Advisories is unavailable or you prefer email-only contact. Encrypted reports welcome but not required at v0.1.0; the project's BDFL will publish a PGP key by v0.2.0.

## Response-time commitments

- **Acknowledgment within 3 business days** of receipt.
- **Status update every 7 days** thereafter, even if the only update is "still investigating."
- **Coordinated-disclosure window: 90 days default.**
  - Shorter if the issue is being actively exploited or has a public-disclosure deadline forced by a reporter or another party.
  - Longer if the fix depends on a third-party dependency we can't unilaterally patch — coordination with the upstream sets the cadence.

The window starts from our acknowledgment date.

## What to include

A good report typically includes:

- Description of the vulnerability and its potential impact.
- Reproduction steps — minimal proof-of-concept preferred over an end-to-end attack.
- The version, commit SHA, or configuration where you observed the issue.
- Suggested mitigation, if you have one. (Not required — clear description is enough.)

## Scope

**In scope:**

- The published `efterlev` Python package on PyPI.
- The container images at `ghcr.io/efterlev/efterlev` and `docker.io/efterlev/efterlev`.
- The `efterlev/scan-action` GitHub Action.
- The MCP server exposed by Efterlev.
- The detector library shipped in this repository.
- Provenance store, agent prompts, secret-redaction, retry/fallback, and any other Efterlev-authored runtime surface.

**Out of scope:**

- Third-party dependencies — report those to the upstream project; we'll update our pinned versions once fixes are available, and the [`.github/dependabot.yml`](./.github/dependabot.yml) ecosystem watches for advisories.
- LLM provider issues — report to Anthropic (anthropic-direct backend) or AWS (Bedrock backend).
- Customer-authored detectors, plugins, manifests, or other extensions outside the repository.
- Operational security of any specific deployment running Efterlev.
- DoS or rate-limiting issues against public endpoints — Efterlev is local-first; there are no public endpoints we operate.

## Supported versions

| Version line | Supported |
|---|---|
| `0.1.x` | ✅ active |
| `0.0.x` (pre-launch placeholder) | ❌ — never installable as a real product |
| Pre-`0.1` development snapshots | ❌ — use the latest released version |

We expand to "current and previous minor line" once `0.2.0` ships.

## Security architecture

Read [THREAT_MODEL.md](./THREAT_MODEL.md) before reporting. It may answer questions about intended behavior — for example:

- Secret redaction in LLM prompts is unconditional and runs in the shared formatter; reports framed as "I can put a fake AWS access key in a comment and it appears in the prompt" should first verify whether the redaction matched.
- The provenance store enforces `derived_from` citation integrity at write time (defense in depth on top of per-agent fence validators); reports should distinguish "claim cites a fabricated id and lands" (an Efterlev bug) from "agent emits a fabricated id" (caught by the validators).
- The MCP server is stateless and stdio-only; reports against an HTTP-server attack model don't apply.

If the threat model doesn't already address what you found, that itself is useful information — note it in your report.

## Recognition

Efterlev is pure OSS with no commercial tier; **we do not pay bug bounties.** What we do offer:

- Public credit in `docs/security-review-*.md` and any release notes that ship the fix.
- A `Hall of Fame` entry in this file for reporters who follow the coordinated-disclosure process. (Empty at v0.1.0 — your name could go here.)

Anonymous reporting is welcome. Reporters who prefer not to be credited just say so.

## Hall of Fame

_None yet._

## Formal-process evolution

This policy may be tightened (PGP key publication, dedicated SC-formed enforcement team) once project governance evolves past the BDFL era per [GOVERNANCE.md](./GOVERNANCE.md). The BDFL is the sole enforcement authority during the BDFL era.

---

*Last updated: 2026-04-25 per SPEC-30.1.*
