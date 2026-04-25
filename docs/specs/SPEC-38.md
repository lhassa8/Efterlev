# SPEC-38: A6 docs site — omnibus

**Status:** draft
**Gate:** A6
**Depends on:** SPEC-01 (canonical domain `efterlev.com`), SPEC-02 (governance + CoC for footer links), all gate-A artifacts that the docs cite
**Blocks:** Launch (gate A6 exit criterion is "naive reader → ran efterlev scan in 5 minutes")
**Size:** L when measured by content count; the scaffold is M, individual pages range from S to M.

## Why one omnibus spec

A6 has 15 deliverables that all live as pages on the same docs site. Each follows the same MkDocs Material conventions and ships to the same `efterlev.com` deploy. Separating into 15 individual SPEC files would repeat the build/deploy/theme contract 15 times. Same pattern as SPEC-14 (detector breadth) and SPEC-30 (trust surface).

## Goal

A reader arriving at `efterlev.com` from a Hacker News comment, a DevSecOps Slack link, or a 3PAO referral finds in under 5 minutes:

1. What Efterlev is and is not.
2. How to install it.
3. A working scan they can run against a sample repo.
4. The KSIs and Evidence/Claims discipline named clearly enough that a non-compliance engineer gets the model.
5. A path forward — tutorials for their actual use case (CI, GovCloud, contributing a detector, etc.).

Measured by: 3 readers who haven't seen the project before, given the URL and a stopwatch, hit "I ran scan and saw findings" in <5 minutes.

## Shared scope (applies to every page below)

- MkDocs Material is the framework. It has the navigation, search, dark mode, and code-block features we need; alternatives (Hugo, Docusaurus) bring extra config burden for no marginal value.
- Every code block is copy-pasteable. Tutorials never say "now do X" without showing the literal command.
- Every page has a "When this is wrong, file an issue" footer pattern (template-injected via the docs-site theme).
- Per-page top-of-doc one-line summary so search-result snippets read cleanly.
- No emoji unless the user-facing copy explicitly demands one (per the project's no-marketing-decoration discipline).
- Internal links use the docs-site routing, not absolute github.com URLs (so they survive a future repo rename).

## Shared exit criteria

A6 closes when:

- All 15 sub-deliverables are checked-off.
- `efterlev.com` resolves to the published site (DNS + GitHub Pages or equivalent live).
- Three readers test the home → quickstart → first-scan flow and report timing under 5 minutes; the longest path is documented and improved.
- The docs build runs in CI; broken-link checking catches dead links before merge.

## Sub-specs

### SPEC-38.1 — MkDocs Material scaffold + theme + deploy ⬜

- `mkdocs.yml` at repo root with Material theme, plugins (search, autorefs, broken-link-check, mkdocstrings for auto-gen reference), and full nav tree.
- `[docs]` extra in `pyproject.toml` adding mkdocs-material + plugins.
- `.github/workflows/docs-deploy.yml` builds on every PR (broken-link-check) and publishes on push-to-main (GitHub Pages or Cloudflare Pages — pick at implementation; GitHub Pages cheapest, Cloudflare faster).
- `efterlev.com` DNS record pointing at the publish target; CNAME file in the docs root if GitHub Pages.

### SPEC-38.2 — Home page ⬜

- `docs/index.md`: 60-second value prop; three primary CTAs (install / docs / GitHub); compact "what this is and is not" diptych.
- One short demo gif or video placeholder (not blocking; a follow-up content task).

### SPEC-38.3 — Quickstart ⬜

- `docs/quickstart.md`: install → init → scan → see-findings in 5 minutes against a sample repo (govnotes-demo or a miniature inline fixture).
- E2E-tested in CI: a quickstart.sh script extracted from the page is run by `.github/workflows/docs-quickstart-test.yml` against a fresh container.

### SPEC-38.4 — Concept pages ⬜

Four pages under `docs/concepts/`:

- `ksis-for-engineers.md` — the FedRAMP 20x KSI model explained for non-compliance readers.
- `evidence-vs-claims.md` — why Efterlev distinguishes scanner output from LLM output.
- `provenance.md` — how the chain works and why it's defensible.
- `what-efterlev-is-not.md` — limitations restated positively (cross-link to LIMITATIONS.md).

### SPEC-38.5 — Install tutorial ⬜

- `docs/tutorials/install.md`: per-platform install paths (macOS arm64/x86_64, Linux x86_64/arm64, Windows). Includes uv, pipx, and container variants.

### SPEC-38.6 — CI integration tutorial ⬜

- `docs/tutorials/ci-github-actions.md`: 3-line YAML using `efterlev/scan-action@v1`.
- `docs/tutorials/ci-gitlab.md`: equivalent for GitLab CI.
- `docs/tutorials/ci-circleci.md`: equivalent for CircleCI.
- `docs/tutorials/ci-jenkins.md`: equivalent for Jenkins.

### SPEC-38.7 — GovCloud deploy tutorial ⬜

- `docs/tutorials/deploy-govcloud-ec2.md`: refines the existing `docs/deploy-govcloud-ec2.md` (SPEC-12) into a polished docs-site page; same content, MkDocs-friendly headings + code-fence styling.

### SPEC-38.8 — Air-gap deploy tutorial ⬜

- `docs/tutorials/deploy-air-gap.md`: scenario where the customer mirrors the container image into a private registry, runs Bedrock via VPC endpoint, and confirms zero internet egress. Builds on SPEC-12 / SPEC-44.

### SPEC-38.9 — Write-your-first-detector tutorial ⬜

- `docs/tutorials/write-a-detector.md`: walks a contributor through scaffolding a new detector folder, writing the rule, fixtures, mapping, README, and test. References `CONTRIBUTING.md`'s detector contract.

### SPEC-38.10 — Write-your-first-manifest tutorial ⬜

- `docs/tutorials/write-a-manifest.md`: walks a customer through authoring `.efterlev/manifests/*.yml` for a procedural KSI (e.g., KSI-AFR-FSI Security Inbox).

### SPEC-38.11 — Customize-an-agent-prompt tutorial ⬜

- `docs/tutorials/customize-agent-prompt.md`: how to fork an agent's `*_prompt.md`, what discipline to keep (fence-citation rules, DRAFT marker), and how to test changes against the e2e harness.

### SPEC-38.12 — Comparison pages ⬜

Five pages under `docs/comparisons/` — content lifts from `COMPETITIVE_LANDSCAPE.md`, refined for docs-site framing:

- `paramify.md`
- `compliance-tf.md`
- `comp-ai.md`
- `vanta-drata.md`
- `consultant.md`

Each follows the same template: who they're for, who we're for, what we do that they don't, what they do that we don't, honest recommendation when we're wrong for the user.

### SPEC-38.13 — Auto-generated reference ⬜

`docs/reference/`:

- `cli.md` — auto-generated from Typer command help via `mkdocs-typer` or equivalent.
- `primitives.md` — auto-generated from the `@primitive` decorator's introspection (custom docs hook).
- `detectors.md` — auto-generated from the detector library (one section per detector pulling its README.md).
- `models.md` — auto-generated from Pydantic models via `mkdocstrings`.
- `frmr-attestation-schema.md` — auto-generated from `AttestationArtifact` Pydantic model.
- `poam-markdown-shape.md` — hand-written reference for the POA&M markdown structure.

### SPEC-38.14 — Architecture overview page ⬜

- `docs/architecture.md`: keep the existing technical doc; add a docs-site-friendly summary section at the top with a static diagram (SVG via Mermaid). Cross-link to the deeper technical content.

### SPEC-38.15 — FAQ ⬜

- `docs/faq.md`: hard questions named explicitly. "Why another compliance tool?" "Will this ever go closed-source?" "Why FRMR-first instead of OSCAL?" "Can I use Efterlev for SOC 2?" "What happens if my 3PAO rejects an Efterlev-drafted attestation?"

## Roll-up exit criterion (gate A6)

- [ ] All 15 sub-deliverables checked-off.
- [ ] `efterlev.com` resolves to the published site.
- [ ] CI builds the site on every PR; broken-link check passes; quickstart.sh extracted from the quickstart page passes in CI.
- [ ] Three external readers walk home → quickstart → first-scan and complete in under 5 minutes; the slowest reader's path is the post-launch optimization queue.
- [ ] Comparison pages reviewed for accuracy against the latest competitor positioning (refresh trigger documented in `COMPETITIVE_LANDSCAPE.md`).

## Risks

- **Doc rot.** A static docs site can lie about behavior the code has since changed. Mitigation: every code block in tutorials is testable; CI extracts and runs them on every commit. Comparison pages have a date stamp + refresh-trigger documented.
- **Time investment exceeds value.** 15 substantive content pages is real writing time. Mitigation: ship the foundational pages (home, quickstart, FAQ, KSIs-for-engineers) first; tutorials land as the corresponding workflow stabilizes; comparison pages can be one-paragraph-per-competitor at v0.1.0 and deepen as feedback comes in.
- **MkDocs build complexity.** mkdocstrings + custom auto-gen reference plugins are the heaviest config. Mitigation: ship without auto-gen reference at v0.1.0 if it's not stable; reference pages stay hand-written until the auto-gen is solid.

## Open questions

- GitHub Pages vs Cloudflare Pages for hosting? Answer: GitHub Pages at v0.1.0 (zero infrastructure to manage); Cloudflare Pages if traffic warrants the speed bump or DDoS resilience matters.
- Custom analytics? Answer: no. Pure-OSS posture means no telemetry, including for the docs site. If we ever need readership signal, GitHub Pages provides server-log analytics privately to the maintainer; that's enough.
