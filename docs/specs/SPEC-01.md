# SPEC-01: Name squatting and canonical identity

**Status:** mostly implemented 2026-04-23 (GitHub org + both domains + PyPI name held; canonical-domain choice open; repo transfer pending; container namespaces + npm pending)
**Gate:** A1
**Depends on:** none
**Blocks:** SPEC-05 (PyPI name — unblocked), SPEC-06 (container registries — unblocked once ghcr.io/docker.io namespaces claimed), SPEC-07 (GitHub org — unblocked), SPEC-38 (docs site domain — unblocked pending canonical-domain decision)
**Size:** S

## Goal

Secure Efterlev's identity across every platform the launch depends on, before anything public-facing references those names. Establish canonical URLs so every doc, install instruction, and link can point at them without revision later.

## Scope

- GitHub organization: `efterlev/` (**held 2026-04-23**)
- PyPI project: `efterlev` (**held 2026-04-23** — `0.0.0` placeholder uploaded; see DECISIONS 2026-04-23 "PyPI name `efterlev` held via placeholder upload")
- Domains: `efterlev.com` (canonical) AND `efterlev.org` (redirect) both held (**2026-04-23**). Canonical decision recorded in Open Questions below.
- Container registry namespaces: `ghcr.io/efterlev/` (auto-provisioned with the GitHub org; verify at launch) and `docker.io/efterlev/` (pending manual claim)
- npm namespace: `efterlev` (defensive; the project uses no JavaScript, but the name is cheap to hold)

## Non-goals

- Marketing website visuals, logo, branding assets (handled under A6 when docs site is built)
- Trademark registration (explicitly deferred per the pure-OSS posture in `DECISIONS.md` 2026-04-23)
- Fallback-name strategy if primary names are taken (see Risks)
- Social-media handle reservation (Twitter/X, LinkedIn, Mastodon) — not on the critical path; reserve opportunistically

## Interface

Canonical URLs the rest of the project references:

- Repo: `https://github.com/efterlev/efterlev` (org held; repo-transfer from `lhassa8/Efterlev` pending)
- PyPI: `https://pypi.org/project/efterlev/` (live; placeholder 0.0.0)
- Docs: `https://efterlev.com` (canonical). `efterlev.org` 301-redirects to `efterlev.com`.
- Container primary: `ghcr.io/efterlev/efterlev` (provisioned with GitHub org)
- Container mirror: `docker.io/efterlev/efterlev` (manual claim pending)
- CoC mailbox: `conduct@efterlev.com` (referenced by SPEC-03)
- Security mailbox: `security@efterlev.com` (referenced by SPEC-30 — disclosure process)

## Behavior

- All documentation (`README.md`, `docs/`, `CONTRIBUTING.md`, `THREAT_MODEL.md`) points at canonical URLs. Pre-launch, the repo is still at `lhassa8/Efterlev`; the docs reference the canonical future URL with a note that the repo is pre-launch at a different URL.
- When the repo transfers to the `efterlev/` org, GitHub automatically redirects the old URL, preserving issues, PRs, stars, watchers, and releases. No link rot.
- PyPI upload uses the canonical name from the first release.
- `efterlev.com` DNS points at the docs-site hosting (GitHub Pages or equivalent) configured by SPEC-38. `efterlev.org` serves a 301 redirect to the `.com` equivalent URL, preserving path (so `efterlev.org/tutorials/quickstart` → `efterlev.com/tutorials/quickstart`).

## Data / schema

N/A.

## Test plan

- **Verification (manual, one-time):** each canonical URL resolves to the expected surface.
  - GitHub org exists and repo transferred.
  - PyPI project name reserved (upload a `0.0.0` placeholder marked as pre-release if needed to hold the name).
  - Domain resolves.
  - Both container-registry namespaces are writable by the org.
- **Backwards-compat:** after the transfer, the old `github.com/lhassa8/Efterlev` URL redirects to the new repo (GitHub does this automatically; confirm manually).

## Exit criterion

- [x] `efterlev/` GitHub org exists and is owned by the project maintainer. **Done 2026-04-23.** Repo transfer from `lhassa8/Efterlev` to `efterlev/efterlev` is a separate action, performed as part of A8 launch rehearsal when the staging flip is dry-run — not now, since transferring while the repo is still private changes nothing externally but can break in-flight PR-branch URLs.
- [x] `pypi.org/project/efterlev/` returns a page confirming the name is held. **Done 2026-04-23**: inert `efterlev==0.0.0` placeholder uploaded, classifier `Development Status :: 1 - Planning`, raises `RuntimeError` on import. Real `0.1.0` release follows SPEC-05.
- [x] Domain(s) registered and DNS controllable. **Done 2026-04-23**: both `efterlev.com` and `efterlev.org` held. Canonical: `efterlev.com`. `efterlev.org` 301-redirects to `.com` (configured during SPEC-38 docs-site setup).
- [ ] `ghcr.io/efterlev/` namespace accessible to the org (auto-provisioned; verify before SPEC-06 work begins).
- [ ] `docker.io/efterlev/` organization created on Docker Hub.
- [ ] npm `efterlev` namespace claimed defensively.
- [x] Canonical domain chosen and recorded: `efterlev.com` (**2026-04-23**).
- [ ] All project docs (`README.md`, `CONTRIBUTING.md`, `DECISIONS.md` going forward, `docs/**/*.md`) reference canonical URLs. Cascade performed 2026-04-23 for SPEC-03 and THREAT_MODEL.md; remaining doc cascade (canonical URLs in README, CONTRIBUTING, COMPETITIVE_LANDSCAPE) runs as part of SPEC-38 docs-site setup when the canonical URLs will matter to external readers.

## Risks

- ~~**Any canonical name is already taken.**~~ Resolved 2026-04-23 — all primary names held (GitHub org, PyPI, both `.com` and `.org` domains). Container and npm namespaces are formality.
- **GitHub org transfer breaks active links.** GitHub's redirect handles this but the redirect is one-way at the repo level and may not cover embedded images or release download URLs. Mitigation: after transfer, run a link-audit in the repo and fix any that didn't redirect. Performed during A8 launch rehearsal.

## Open questions

- ~~**Canonical domain choice: `.com` or `.org`?**~~ **Resolved 2026-04-23: `.com` canonical.**

  The recommendation at draft time was `.org` on OSS-convention grounds. Maintainer chose `.com` — the more memorable TLD reads cleanly to a first-time visitor who arrives from HN or a DevSecOps Slack link. `efterlev.org` 301-redirects to `.com`, so the OSS-convention-typing audience still lands in the right place; if the project ever donates to a foundation, the canonical can flip at that point without breaking existing links (the foundation would typically own both TLDs post-donation).

  All mailboxes bind to `.com`: `conduct@efterlev.com`, `security@efterlev.com`.

- ~~Should the GitHub org own any related repos at launch?~~ Answer: yes — `efterlev/scan-action` (SPEC-07) and `efterlev/govnotes-demo` (if promoted as the canonical demo per A6 decision) are created under the org. Create these as empty repos at spec-execution time, populated per their dependent specs.
