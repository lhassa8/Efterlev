# SPEC-08: Sigstore signing + SLSA provenance

**Status:** verification script + release docs landed 2026-04-24; signing pipelines already inline in SPEC-05 (Trusted Publishing Sigstore) and SPEC-06 (cosign + buildx provenance); first-release dry-run is the remaining check
**Gate:** A2
**Depends on:** SPEC-05 (PyPI pipeline signs inside its workflow), SPEC-06 (container pipeline signs inside its workflow)
**Blocks:** SPEC-09 (install-verification matrix verifies signatures), A5 (trust surface)
**Size:** M

## Goal

Every release artifact — wheel, sdist, container images on both registries — is cryptographically signed and carries SLSA Level 3 provenance traceable to the GitHub workflow that produced it, so any consumer can verify what they're installing.

## Scope

- Sigstore/cosign signing via keyless OIDC-based signing (no long-lived signing keys to manage)
- PyPI wheel + sdist: signed via `pypa/gh-action-pypi-publish`'s built-in Sigstore support (Trusted Publishing + attestations)
- Container images (ghcr.io + docker.io): signed via `cosign sign` in the release-container workflow
- SLSA Level 3 provenance via `slsa-framework/slsa-github-generator` for all artifact types
- Verification instructions in every release's GitHub Release notes
- Ship `scripts/verify-release.sh` in the main repo so users can verify a release with one command

## Non-goals

- GPG / long-lived-key signing (Sigstore's keyless OIDC is simpler and has better provenance guarantees)
- Signed commits (separate — SPEC-04)
- In-toto attestations beyond SLSA (out of scope for v0.1.0; SLSA is the industry baseline)
- Key management infrastructure (none required — OIDC identity is the signer)
- Transparent-log exclusivity checks (cosign's default Rekor log lookup is sufficient)

## Interface

- Sigstore signatures alongside each artifact:
  - `efterlev-0.1.0-py3-none-any.whl.sigstore` (bundle file) on PyPI
  - `efterlev-0.1.0.tar.gz.sigstore` on PyPI
  - Container signatures via `cosign`'s signature-in-registry pattern (signatures stored as OCI objects in the same registry)
- SLSA provenance:
  - `efterlev-0.1.0-py3-none-any.whl.intoto.jsonl` attached to the GitHub Release
  - Same for sdist
  - Container provenance attested via cosign, verifiable via `slsa-verifier verify-image`
- Release notes template includes a "Verify this release" section with concrete commands
- `scripts/verify-release.sh v0.1.0` in the main repo: pulls all artifacts for version, verifies every signature, exits 0 only on full success

## Behavior

- **On every `v*.*.*` tag push:** release pipelines (SPEC-05, SPEC-06) produce artifacts → sign via Sigstore → generate SLSA provenance → publish all three (artifact, signature, provenance) together.
- **Verification command (wheel):**
  ```bash
  python -m sigstore verify identity \
    --cert-identity https://github.com/efterlev/efterlev/.github/workflows/release-pypi.yml@refs/tags/v0.1.0 \
    --cert-oidc-issuer https://token.actions.githubusercontent.com \
    efterlev-0.1.0-py3-none-any.whl
  ```
- **Verification command (container):**
  ```bash
  cosign verify ghcr.io/efterlev/efterlev:v0.1.0 \
    --certificate-identity-regexp '^https://github.com/efterlev/efterlev/' \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com
  ```
- **SLSA verification:**
  ```bash
  slsa-verifier verify-artifact efterlev-0.1.0-py3-none-any.whl \
    --provenance-path efterlev-0.1.0-py3-none-any.whl.intoto.jsonl \
    --source-uri github.com/efterlev/efterlev \
    --source-tag v0.1.0
  ```
- Signatures traceable to the workflow file, the tag, and the OIDC identity (GitHub Actions' OIDC provider).
- Unsigned artifacts never appear in published releases — the release pipeline fails before publishing if signing fails.
- `scripts/verify-release.sh` wraps all three verifications plus a checksum check; one command, one exit code.

## Data / schema

- Sigstore bundle format (v0.3+) — standard, versioned.
- SLSA provenance format v1.0 — standard.
- No project-specific schema.

## Test plan

- **Dry-run on release candidate:** `v0.1.0-rc.1` runs the full signing + attestation pipeline; verify every artifact signs successfully and its signature is valid.
- **Verification round-trip:** on a fresh machine without OIDC credentials, `scripts/verify-release.sh v0.1.0-rc.1` against the Test PyPI + staging ghcr.io images succeeds.
- **Tamper detection:** manually corrupt a byte in a downloaded wheel; `sigstore verify` must fail with a clear error.
- **Identity mismatch:** verify a staging artifact using a verify command pointing at a wrong tag; must fail.
- **Provenance attestation:** inspect `.intoto.jsonl` by hand and confirm it names the expected GitHub repo, workflow, and commit SHA.
- **Documentation verification:** the verify-this-release snippet in a release's GitHub Release notes, copy-pasted into a clean shell, verifies the release successfully.

## Exit criterion

### Landed 2026-04-24

- [x] PyPI wheel + sdist Sigstore signing is inline in SPEC-05's `release-pypi.yml` (via `pypa/gh-action-pypi-publish@release/v1` under Trusted Publishing). No separate signing workflow needed.
- [x] Container cosign keyless-OIDC signing + `provenance: mode=max` + `sbom: true` inline in SPEC-06's `release-container.yml`. Inline verification step proves the signature round-trips in every release run.
- [x] `scripts/verify-release.sh` — one-command end-to-end verification. Takes a version tag argument. Checks (a) PyPI wheel + sdist Sigstore signatures bound to the expected workflow identity, (b) container-image cosign signatures on both registries, (c) SLSA build-provenance attestations on both images. Exit 0 only on full pass. Prints clear install instructions when cosign / sigstore-python / docker are missing. Bash syntax checked; smoke-tested with missing-tools and usage-error paths.
- [x] `docs/RELEASE.md` — release mechanics, release-notes template (fill-in-the-blanks for each release), release-candidate template, troubleshooting playbook, and deferred follow-ups. Cross-linked from README's Documentation section.

### Maintainer action — pending

- [ ] First release dry-run (`v0.1.0-rc.0` or similar): confirm that `scripts/verify-release.sh v0.1.0-rc.0` against the first Test PyPI + staging ghcr.io artifacts exits 0. This is the only way to exercise the full verification path end-to-end. Happens alongside SPEC-05 and SPEC-06 first dry-runs.

## Risks

- **Sigstore service outage at release time.** Accept: launch is gate-driven; retry when healthy. Sigstore has high uptime in practice.
- **Cosign / sigstore-python version drift breaks verification commands.** Mitigation: pin tool versions in the release-notes verification snippet; update the snippet when we update the tools. The snippet is a small file; keep it current.
- **User tries to verify from a non-English locale or under Docker-desktop quirks.** Mitigation: `scripts/verify-release.sh` prefers tools already in the user's PATH; falls back to printing manual-verification instructions if verification tools are missing.
- **Keyless signing binds to a specific workflow file path.** Accept: moving or renaming `release-pypi.yml` or `release-container.yml` invalidates old-release verification commands. Migration is a coordinated change (update workflow, update verify instructions, update `verify-release.sh`) and is called out in the spec for any future renames.

## Open questions

- Do we submit signatures to a private transparency log in addition to the public Rekor log? Answer: no. Public Rekor is the default; privacy doesn't apply because release artifacts are public.
- Do we sign the GitHub Release tarball auto-created by GitHub? Answer: no. Users are directed to the curated wheel/sdist/container artifacts, not the GitHub auto-tarball. Documented in release notes.
