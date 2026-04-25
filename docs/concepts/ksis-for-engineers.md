# KSIs for engineers

> The FedRAMP 20x model, explained for people who write code instead of compliance documents.

If you've heard "FedRAMP" and "KSI" and the next sentence sounds like Charlie Brown's teacher, this page is for you. By the end you'll know what a KSI is, why FedRAMP 20x leans on them instead of the older Rev 5 control set, and what it means for the Terraform you're about to scan.

## What FedRAMP is, in two paragraphs

The U.S. federal government buys software through an authorization regime called FedRAMP (Federal Risk and Authorization Management Program). Before a federal agency can use your SaaS, the product has to be assessed at one of three impact levels — Low, Moderate, or High — based on the sensitivity of the data it'll handle. Most SaaS targets Moderate.

Historically, getting authorized meant: hire a $250K+ specialist consultant, spend 12–18 months producing a thousand-plus-page document called a System Security Plan (SSP), get assessed by a Third-Party Assessment Organization (3PAO), and submit the package to the FedRAMP Program Management Office for review. The paperwork output was narrative-heavy: "we have a process for X" with prose explaining how. Whether the prose was true depended on the assessor's diligence.

## What FedRAMP 20x changes

In 2025–2026 FedRAMP launched **20x**, an authorization track that replaces narrative-heavy SSPs with measurable outcomes called **Key Security Indicators (KSIs)**. Instead of "describe in 50 pages how you encrypt data at rest," 20x asks "show evidence that you encrypt data at rest." The evidence is machine-readable, formatted as **FRMR** (FedRAMP Machine-Readable). New SaaS authorizations starting in 2026 are heading into the 20x track.

A KSI is a discrete outcome statement — typically two to five sentences — backed by a list of underlying NIST 800-53 Rev 5 controls. Examples from FRMR 0.9.43-beta:

- **KSI-SVC-SNT — Securing Network Traffic.** "Use cryptographic protections for network communications." Underlying controls: SC-8.
- **KSI-IAM-MFA — Enforcing Phishing-Resistant MFA.** "Require phishing-resistant MFA for all human users." Underlying controls: IA-2.
- **KSI-MLA-LET — Logging Event Types.** "Generate audit records for the event types policy and regulation require." Underlying controls: AU-2, AU-12.
- **KSI-RPL-ABO — Aligning Backups with Objectives.** "Establish backups that meet recovery time and recovery point objectives." Underlying controls: CP-9.

There are 60 KSIs in FRMR 0.9.43-beta, organized into 11 themes (SVC, IAM, MLA, RPL, CMT, AFR, INR, KSO, PIY, SCR, CNA — yes, the acronyms compound).

## Why this matters for the Terraform you scan

Most KSIs map naturally onto things a static analyzer can see in IaC:

- **KSI-SVC-VRI** (Validating Resource Integrity) — controls SC-13. Detector: does the load-balancer listener use a FIPS-validated TLS policy?
- **KSI-CNA-RNT** (Restricting Network Traffic) — controls SC-7.5. Detector: does any security group allow `0.0.0.0/0` ingress on a non-public-web port?
- **KSI-IAM-MFA** — controls IA-2. Detector: do IAM policies condition `aws:MultiFactorAuthPresent` on sensitive actions?
- **KSI-MLA-LET** — controls AU-2, AU-12. Detector: are CloudTrail and VPC flow logs enabled?

Some KSIs are procedural — they need a human attesting that an organizational practice exists. Examples: KSI-AFR-FSI (Federal Security Inbox: a monitored mailbox for federal-incident-coordination correspondence), KSI-INR-RIR (Reviewing Incident Response Procedures). Efterlev calls these out and uses **Evidence Manifests** — customer-authored YAML files where someone with authority states "yes, we do this, here's who reviews it" — to fill the procedural gap.

The combination — scanner-derived evidence for the IaC-visible part, human-attested evidence for the procedural part — gets you to roughly 80% coverage of FedRAMP Moderate's KSI set. The remaining 20% needs assessor-side work that no IaC scanner can short-circuit.

## How Efterlev models KSIs

Each detector declares which KSIs it evidences in its `@detector` decorator:

```python
@detector(
    id="aws.tls_on_lb_listeners",
    ksis=["KSI-SVC-SNT"],
    controls=["SC-8"],
    source="terraform",
    version="0.1.0",
)
def detect(resources): ...
```

When the detector emits an `Evidence` record, it carries `ksis_evidenced=["KSI-SVC-SNT"]` and `controls_evidenced=["SC-8"]`. Downstream, the Gap Agent reads these records, classifies each KSI's posture (`implemented` / `partial` / `not_implemented`), and produces a per-KSI HTML report. The Documentation Agent turns the classifications into FRMR-compatible attestation JSON.

## When the mapping isn't clean

Sometimes the underlying 800-53 control isn't listed in any KSI's `controls` array in FRMR 0.9.43-beta. **SC-28 (Protection of Information at Rest)** is the canonical example — it's a real, important control, but no KSI in 0.9.43-beta references it. Efterlev's discipline:

- We do not invent a KSI mapping that doesn't exist.
- The detector declares `ksis=[]` and explains the FRMR mapping gap in its README.
- The Gap Agent renders such findings under "Unmapped findings" — honest about the current FRMR state.

We expect this to resolve as FRMR moves from beta toward GA. Until then, the project's bias is toward telling the truth about coverage gaps rather than pretending coverage exists.

## What FedRAMP 20x means for your timeline

If you're a SaaS company beginning your first FedRAMP Moderate authorization in 2026:

- **You're in the 20x track**, almost certainly. The legacy Rev 5 path still exists for Rev5-transition submissions, but new authorizations from 2026 forward target 20x.
- **You'll produce FRMR-compatible attestation JSON**, not 1000-page SSPs. The format is documented and validated against the FedRAMP-published JSON schema.
- **Your 3PAO will look at evidence**, not prose. Every assertion in your attestation traces back to a measurable artifact: a Terraform resource, an Evidence Manifest entry, or a controlled deviation noted in your POA&M.
- **Authorization timeline shrinks substantially**. The first 20x Phase 2 Moderate pilot participants achieved authorization in roughly 30–60 days — not the legacy 12–18 months. This depends heavily on having clean evidence, which is exactly what Efterlev produces.

## Further reading

- The vendored FRMR document at [`catalogs/frmr/FRMR.documentation.json`](https://github.com/efterlev/efterlev/blob/main/catalogs/frmr/FRMR.documentation.json) — every KSI, its statement, and its underlying controls.
- The FedRAMP 20x program page at [fedramp.gov/20x/](https://www.fedramp.gov/20x/).
- The [Evidence vs Claims](evidence-vs-claims.md) concept page — why Efterlev distinguishes scanner output from LLM output.
- The [Provenance](provenance.md) concept page — how every generated artifact traces back to its source.
