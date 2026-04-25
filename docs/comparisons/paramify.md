# Efterlev vs Paramify

Paramify is the category-defining FedRAMP 20x specialist — the first GRC tool authorized through the 20x Phase 2 Moderate pilot, marketed as "FedRAMP authorization in 30 days" with case-study backing. Pricing is publicly disclosed at ~$145–180K initial + $235–360K annual.

## Where they overlap with Efterlev

- Both target first-time FedRAMP 20x Moderate SaaS users.
- Both produce FRMR-compatible authorization-package artifacts.
- Both accelerate the path from first engagement to 3PAO submission.

## Where they don't overlap

| | Paramify | Efterlev |
|---|---|---|
| Distribution | SaaS, account-bound | Pure OSS, Apache 2.0 |
| Pricing | $145–180K/year | Free |
| Locus of work | GRC dashboard | Engineer's repo + CLI |
| Terraform scanning | Not directly | Yes, 30 detectors |
| Code-level remediation diffs | Not directly | Yes, via the Remediation Agent |
| Evidence-vs-Claims discipline | Standard GRC framing | Architectural — type-level |

## Who picks which

A SaaS company willing to spend ~$180K to compress their first-FedRAMP timeline, with a dedicated compliance person or appetite to hire one, **picks Paramify**.

A SaaS company that wants to own the work, keep costs near-zero, and use the same tool to maintain compliance post-authorization **picks Efterlev**.

Different buyer, different budget authority, different time horizon. These markets coexist.

## What's honestly true about Paramify

- **They got there first.** Authorization through Phase 2 Moderate is a meaningful proof point we don't have at v0.1.0.
- **Their managed service is doing real work.** When customers buy Paramify, they're buying tooling + advisory + 3PAO coordination as a package. Efterlev is just the tooling.
- **The pricing matches the depth of integration.** A package that gets you to authorization in 30 days is reasonably priced at $180K/year.

## What we do that they don't

- **Run inside your repo, not as a SaaS.** No vendor lock-in. Your Terraform never leaves your machine; your evidence store lives in `.efterlev/`.
- **Code-level remediation diffs.** When Efterlev finds a gap, the Remediation Agent proposes a Terraform change. PR-ready.
- **Open source.** Apache 2.0 forever. If you outgrow Efterlev, you fork it; you're never dependent on a vendor's roadmap.

If your finance team is reviewing both: Paramify is a service, Efterlev is a tool. The right answer depends on whether you want to outsource the FedRAMP push or own it in-house.
