# Code of Conduct

## Adoption

Efterlev adopts the [Contributor Covenant, version 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) as its Code of Conduct, in full. The canonical text is hosted by the Contributor Covenant project at the link above; that text is our Code of Conduct as if reproduced here. No local modifications to the Contributor Covenant itself are made; project-specific interpretation appears in its own section below.

Why adoption-by-reference: the Contributor Covenant is a living document maintained by a stewarded community. Linking to the canonical source rather than reproducing ensures we automatically track any errata or official clarifications without a stale copy in this repo, and it is a pattern in use at Kubernetes and many other major OSS projects.

## Enforcement

Instances of behavior in scope of the Contributor Covenant may be reported to the community leaders responsible for enforcement at:

> **conduct@efterlev.com**

During the BDFL era (see [GOVERNANCE.md](./GOVERNANCE.md)), this mailbox is received by the BDFL. After the steering-committee formation trigger fires, the mailbox is received by a dedicated enforcement team named by the steering committee.

## Response-time commitment

Reports are acknowledged within **3 business days**. Resolution timing depends on the complexity of the report but we commit to keeping reporters informed of status every 7 days until resolution.

Resolution follows the Contributor Covenant's four-tier enforcement ladder (Correction, Warning, Temporary Ban, Permanent Ban), calibrated to the severity and pattern of the incident. Enforcement actions are private between the enforcement body, the reporter, and the subject; aggregate statistics may be published once the project is active enough that aggregation preserves reporter anonymity.

## Project-specific interpretation

Three norms follow directly from Efterlev's product discipline and are part of how this Code of Conduct is applied in this project's specific context. They are Efterlev-specific commentary on Contributor Covenant sections "Our Standards" and "Enforcement Responsibilities" — they do not modify the Contributor Covenant text itself.

### 1. No FUD about competitors

Efterlev's `COMPETITIVE_LANDSCAPE.md` is written as honest positioning, not marketing against competitors. Comments in issues, PRs, or community forums that disparage Paramify, compliance.tf, Comp AI, RegScale, Vanta, Drata, or any other tool or practitioner in the compliance space will be asked to be reframed. We compete on honest merits; any weakness in a competitor we genuinely understand is also a weakness we can state respectfully.

This is an "unprofessional" behavior by Contributor Covenant standards in the context of a project whose product discipline explicitly values honest positioning.

### 2. No overclaiming in docs or code

Efterlev's `LIMITATIONS.md` is a first-class product document, not a disclaimer. Contributions — code, docs, or commentary — that blur what the tool proves vs. what it merely evidences are reshaped or declined. Examples of overclaiming that would warrant reframing:

- Detector READMEs that say "this proves SC-28 is implemented" rather than "this evidences the infrastructure layer of SC-28."
- PR descriptions that say "closes compliance gap" rather than "adds evidence for the relevant KSI."
- Comments or marketing text that suggest Efterlev produces authorizations, passes, or compliance guarantees rather than drafts requiring human review.

Overclaiming is harmful not only because it damages the project's credibility — it creates real downstream risk for users whose 3PAOs or authorizing officials may reject artifacts built on inflated claims.

### 3. Compliance jargon is okay; gatekeeping is not

Efterlev's target users include engineers new to the FedRAMP and NIST 800-53 space. Some contributors will be deep-compliance experts; others will be strong engineers learning the domain. Both are welcome.

If a contributor asks a basic compliance question, explain it. If a contributor uses imprecise compliance terminology, correct it gently and with a reference. Condescension, "this is obvious" dismissals, or behavior that suggests the domain is for gatekeepers rather than for the engineers who need to implement it in production — these are unprofessional behaviors under this project's interpretation of the Contributor Covenant.

The compliance domain needs more practitioners, not fewer. Governance upholds that.

## Scope of this Code of Conduct

Per the Contributor Covenant's Scope section, this Code applies within all community spaces associated with Efterlev and also when an individual is representing the project in public. Community spaces include (non-exhaustive):

- This GitHub repository: issues, PRs, discussions, commits, reviews, and wiki (if added).
- Related repositories under the `efterlev/` GitHub organization (e.g., `efterlev/scan-action`).
- The docs site at `efterlev.com` (once live, including its community-comment surface if any).
- Any communication channel officially associated with Efterlev (conduct mailbox, any future chat or mailing list).

## Attribution

The Contributor Covenant is Copyright © 2014–2024 the Contributor Covenant project maintainers and is licensed under the [Creative Commons Attribution 4.0 International license](https://creativecommons.org/licenses/by/4.0/).

The Efterlev project-specific interpretation sections above are © the Efterlev project maintainers and are licensed under the same Apache 2.0 license as the rest of the Efterlev repository.
