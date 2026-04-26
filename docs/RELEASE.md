# Release process

Efterlev releases are gate-driven, not date-driven. A release happens when it's ready and the readiness gates in `DECISIONS.md` 2026-04-23 have cleared. There is no scheduled cadence.

This document covers:
1. The release mechanics (what actually happens when a maintainer cuts a tag).
2. The release-notes template (paste, fill in per-release).
3. The verification contract (what users can check about every release).

## Mechanics

### Cutting a release

1. Update `pyproject.toml` to the target version (e.g., `0.1.0` or `0.1.0rc1`).
2. Write or finalize the CHANGELOG.md entry under the new version heading.
3. Commit and merge the version bump via PR.
4. Tag the merge commit:
   - Release-candidate: `git tag -s v0.1.0-rc.1 -m "v0.1.0-rc.1"`
   - Final release: `git tag -s v0.1.0 -m "v0.1.0"`
5. Push the tag: `git push origin v0.1.0-rc.1` (or the final tag).
6. Observe the two release workflows fire in parallel:
   - `release-pypi.yml` (SPEC-05) — builds + uploads to Test PyPI, then to real PyPI (gated on `pypi` environment approval for final tags)
   - `release-container.yml` (SPEC-06) — builds multi-arch container, pushes to ghcr.io, signs via cosign, attaches SLSA provenance. (Docker Hub publish was a parallel target at design time but was dropped at v0.1.0 after Docker Hub eliminated the free organization tier; deferred to post-launch via the Docker-Sponsored Open Source program.)
7. Once the `release-smoke.yml` matrix (SPEC-09) reports green on the same tag, approve the `pypi` environment deployment to proceed with real-PyPI upload.
8. Cut a GitHub Release from the tag, pasting the release-notes template below.

### What the workflows sign and attest

Every release artifact carries two things:
- **Sigstore signature** — keyless, bound to the GitHub Actions workflow identity. Nobody holds a signing key that can be lost or stolen.
- **SLSA build provenance** — cryptographically-verifiable record of *which workflow on which commit built this artifact*. Level 3 because the build runs on GitHub-hosted runners with OIDC.

Both are automatic:
- PyPI wheel + sdist: via `pypa/gh-action-pypi-publish@release/v1` under Trusted Publishing.
- Container images: via `docker/build-push-action@v6` with `provenance: mode=max` plus a `cosign sign` step in the workflow.

No long-lived signing keys exist. Key rotation is not a concern because there are no keys to rotate.

## Verification contract

Every user can verify any release with one command:

```bash
scripts/verify-release.sh v0.1.0
```

The script checks:
1. PyPI wheel + sdist are signed by the expected workflow identity (`release-pypi.yml` on the tag's refs).
2. Container images on ghcr.io are signed by the expected workflow identity.
3. SLSA build provenance is attached to every container image.

Exit 0 means all checks passed. Exit 1 means at least one check failed; do not install the release.

Requires `cosign`, `python3`, the `sigstore` Python package, `curl`, and `docker`. Install instructions are printed by the script if anything is missing.

## Release-notes template

Paste this into the GitHub Release body, replace `<VERSION>` and `<date>`, fill in the sections.

```markdown
# Efterlev <VERSION>

Released <date>.

## Install

```bash
# From PyPI
pipx install efterlev==<VERSION>

# Or pull the container
docker pull ghcr.io/efterlev/efterlev:v<VERSION>
```

## Changelog

*(Paste the matching section from CHANGELOG.md — features, fixes, breaking changes,
deprecations, dependency bumps — preserving the Keep-a-Changelog headers.)*

## Verification

Every artifact in this release is signed via Sigstore and carries SLSA Level 3 build provenance. Verify the full release with one command:

```bash
git clone https://github.com/efterlev/efterlev && cd efterlev
scripts/verify-release.sh v<VERSION>
```

The script checks:
- PyPI wheel + sdist Sigstore signatures (bound to this repo's `release-pypi.yml` workflow).
- Container images on ghcr.io, cosign-signed by `release-container.yml`.
- SLSA build provenance on every container image.

Artifacts:
- PyPI project: https://pypi.org/project/efterlev/<VERSION>/
- Container (GHCR): `ghcr.io/efterlev/efterlev:v<VERSION>`

## What hasn't been independently verified

Efterlev output is drafts, not authorizations. Every LLM-generated artifact (Gap Agent classifications, Documentation Agent narratives, Remediation Agent diffs) carries a `DRAFT — requires human review` marker. No scanning run, verified or otherwise, substitutes for a 3PAO.

See [LIMITATIONS.md](../LIMITATIONS.md) for the full accounting of what Efterlev does not do.

## Contributors

*(Auto-generate from git log, or list by hand for small releases.)*
```

## Release-candidate notes

For `*-rc.*` tags, skip the full template and post a short release note instead:

```markdown
# Efterlev <VERSION> (release candidate)

Released <date>.

Pre-release verification build. Not published to real PyPI; available only on Test PyPI and the staging container tags.

**Do not use in production.** Use for:
- Verifying install paths on your platform (`pipx install -i https://test.pypi.org/simple/ efterlev==<pep440-version>`)
- Smoke-testing CI integration via the scan-action against a `v<VERSION>` tag pin.
- Shaking out release-workflow regressions before the final tag.

Feedback on the release process itself (not on the content of the release) is welcome as a GitHub Discussion.
```

## When something goes wrong

### A workflow fails mid-release

The tag stays. The release is incomplete but not corrupt — consumers never saw it because trusted-publishing gating prevents partial uploads from reaching real PyPI without the full matrix green. Maintainer:
1. Investigate the failure (`gh run view <run-id> --log-failed`).
2. Fix root cause.
3. Force-push the tag only if absolutely necessary (documented in a `DECISIONS.md` entry); otherwise, cut the next patch version.

### A signature verification fails post-release

Emergency-severity. Post a public notice on the project's docs site and in the repo README. Investigate the build environment. If a release artifact was tampered with, yank the PyPI version and revoke the container tag; cut a new release with the yank documented in CHANGELOG.md.

### A signed release is found to contain a vulnerability

Normal vulnerability-disclosure flow per `SECURITY.md`. Signing is about *who produced the artifact*, not *whether the artifact is free of bugs*. A signed release can still have vulnerabilities; the disclosure and patching process is unchanged.

## Deferred and tracked

These are intentionally not in the v0.1.0 release process, named here so they don't get lost:

- **Homebrew formula** — if demand surfaces. Separate spec.
- **Conda-forge publishing** — if demand surfaces. Separate spec.
- **Signed git tags enforcement** — requires BDFL's SSH signing key registration per SPEC-04; process is in place.
- **SBOMs** — buildx emits an SBOM attestation for container images (`sbom: true` in release-container.yml). A separate SBOM for the PyPI wheel is not yet generated; tracked as a follow-up.
- **Release-signing-key rotation drill** — keyless signing via OIDC means there's no key to rotate. If the project ever moves to key-based signing (unlikely), a drill process goes here.
