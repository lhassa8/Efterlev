# SPEC-09: Install-verification CI smoke tests

**Status:** workflow + fixture + assert.py landed 2026-04-24; first-release dry-run is the final check
**Gate:** A2
**Depends on:** SPEC-05 (Test PyPI upload produces an installable artifact), SPEC-06 (container images to pull), SPEC-08 (signatures to verify)
**Blocks:** real-PyPI upload of `v*.*.*` (non-rc) tags — the smoke matrix is the gate (via maintainer approval on the `pypi` environment)
**Size:** M

## Goal

Every release candidate is smoke-tested on every supported platform and install method before the real-PyPI upload is allowed to proceed, so "it works on my machine" is a property of the release pipeline, not an act of faith.

## Scope

- GitHub Actions matrix that runs on every tag push (rc or final)
- Platform matrix: macOS arm64, macOS x86_64 (if available on GitHub runners), Ubuntu 22.04 x86_64, Ubuntu 22.04 arm64, Windows 2022
- Install-method matrix: pipx from Test PyPI, Docker from ghcr.io, Docker from docker.io
- Per matrix cell: install → run `efterlev --version` → run `efterlev scan` against a known-finding fixture → verify exit code and a minimal expected-output check
- On `v*.*.*-rc.*` tags: matrix runs; results reported; no real-PyPI upload regardless
- On `v*.*.*` final tags: matrix runs; real-PyPI upload (SPEC-05) is blocked until matrix all-green
- Signature-verification step runs inside the matrix (using SPEC-08 artifacts)

## Non-goals

- Testing against all Python minor versions (3.12+ is the only supported version at v0.1.0; separate spec if we expand the support matrix)
- Testing on every Linux distribution beyond Ubuntu 22.04 as the reference (Debian, Fedora, CentOS compatibility is covered by "runs in Docker" — the container image is the multi-distro answer)
- Windows ARM64 (wait for GitHub Actions runner availability)
- Performance benchmarking (separate spec)
- Functional agent testing with real LLM calls (e2e harness handles that; smoke doesn't need it)
- Testing with production-grade Terraform fixtures (the fixture is minimal on purpose — we're testing install, not compliance logic)

## Interface

- Workflow: `.github/workflows/release-smoke.yml`
- Triggers: `push` with `tags: ['v*.*.*', 'v*.*.*-rc.*']`
- Job matrix:
  ```
  platform: [macos-14, ubuntu-22.04, ubuntu-22.04-arm, windows-2022]
  install-method: [pipx-test-pypi, docker-ghcr, docker-dockerhub]
  exclude:
    # Windows container path tracked separately; skip docker cells on Windows
    - platform: windows-2022
      install-method: docker-ghcr
    - platform: windows-2022
      install-method: docker-dockerhub
  ```
- Per-cell steps:
  1. Check out fixture (either committed in the repo or synthesized inline)
  2. Install Efterlev via the cell's install-method
  3. Run `efterlev --version` → assert exit 0 and expected version string
  4. Run `efterlev init --baseline fedramp-20x-moderate` against the fixture → assert exit 0
  5. Run `efterlev scan` → assert exit 0 and at least one detector finding present
  6. Verify Sigstore signature of whichever artifact the cell installed (SPEC-08)
- Matrix success gates the `upload-pypi` job in `release-pypi.yml` (SPEC-05) via `needs:` dependency
- Matrix failure: tag stays, real-PyPI upload does not run, maintainer notified via workflow failure

## Behavior

- **On `v0.1.0-rc.1` tag:** Test PyPI upload runs → matrix runs against Test PyPI + staging containers → results reported. No real-PyPI upload (always skipped for rc tags).
- **On `v0.1.0` final tag:** Test PyPI upload runs first (same as rc) → matrix runs → if all green, real-PyPI upload runs → post-real-PyPI smoke verifies from the real-PyPI artifact as well.
- **Matrix failure on any single cell:** workflow fails overall; real-PyPI upload never triggers.
- **Flaky cell (intermittent failure):** workflow's built-in re-run support handles it; if a cell fails twice in a row, investigate.
- **Known-fixture finding assertion:** the fixture is a minimal Terraform file with one known detector-visible pattern (e.g., `aws_s3_bucket` without `server_side_encryption_configuration`). The smoke assertion is "at least one finding produced," not a specific finding count — avoids coupling to detector-count changes.

## Data / schema

- Fixture: `tests/smoke/fixture.tf` in the main repo. Minimal — 10–20 lines of Terraform. Committed with a tests/smoke/README.md explaining what it intentionally fails.
- Assertion script: `tests/smoke/assert.sh` — checks exit codes and stdout/stderr patterns.

## Test plan

- **Meta-test:** intentionally break a release-candidate build (e.g., remove a required classifier from `pyproject.toml`) and push a test-only rc tag; the smoke matrix must fail as expected.
- **Platform coverage verification:** on each platform in the matrix, at least one successful release-candidate run proves the cell works end-to-end. Windows is historically the most fragile and deserves explicit verification by a human in the loop for the first few releases.
- **Matrix-blocks-upload verification:** force a failure in one matrix cell on a final-release tag; verify the `upload-pypi` job does not execute.
- **Test PyPI round-trip:** successfully install `efterlev==0.1.0rc1` from Test PyPI on every platform in the matrix.

## Exit criterion

### Landed 2026-04-24

- [x] `.github/workflows/release-smoke.yml` merged on `main`. Three jobs: `resolve-version`, `smoke` (9-cell matrix), `signature-verify`. YAML syntax validated.
- [x] 9-cell matrix: pipx install on ubuntu-22.04 / ubuntu-24.04-arm / macos-14 / macos-13 / windows-2022 (5 cells); Docker from ghcr.io on Linux x86_64 + arm64 (2 cells); Docker from Docker Hub on Linux x86_64 + arm64 (2 cells). Windows+Docker and macOS+Docker excluded per SPEC-06 non-goals.
- [x] Retry-and-wait loops on each install step (20 × 30s = 10 min ceiling) absorb tag-push-to-registry-indexing lag.
- [x] Version-check step compares `efterlev --version` against the tag.
- [x] Scan step runs `init + scan` against `tests/smoke/fixture.tf`; assertion step runs `tests/smoke/assert.py`.
- [x] `signature-verify` job runs `scripts/verify-release.sh` (SPEC-08) after the matrix — end-to-end cryptographic verification is an automated check, not a manual user-side step.
- [x] `tests/smoke/fixture.tf` — minimal Terraform with two deliberate gaps.
- [x] `tests/smoke/assert.py` — post-scan state checker; exits 1 on any missing state component with itemized diagnostics. Tested on the missing-dir case.
- [x] `tests/smoke/README.md` — fixture contract and don't-copy-this warning.

### Revision 2026-04-24: `assert.sh` → `assert.py` for Windows portability

SPEC-09 draft said `tests/smoke/assert.sh`. Implemented as `assert.py` instead. On Windows runners, GitHub Actions' bash support goes through Git Bash, which works for simple one-liners but creates path-handling friction for anything that queries SQLite or walks directories. Python is available on every matrix cell (via `actions/setup-python` on pipx cells, bundled in the container for Docker cells). A Python assertion script is portable across all 9 cells without per-cell tweaks.

### Maintainer action — pending

- [ ] First real-tag dry-run: push `v0.1.0-rc.0`, observe release-pypi.yml / release-container.yml / release-smoke.yml all fire in parallel, confirm smoke matrix completes green, confirm `signature-verify` passes on the freshly-signed artifacts.
- [ ] Reconfirm the `pypi` environment approval flow: approve only after release-smoke.yml's matrix is green on the same tag. Coordination documented in `docs/RELEASE.md` and release-pypi.yml's header.
- [ ] After first dry-run completes: update `.github/BRANCH_PROTECTION.md` to add the smoke matrix job names to required status checks on `main` (they only exist as check names once the workflow has run at least once).

## Risks

- **Flaky Windows CI.** Accept and re-run; do not disable the Windows matrix — Windows is the most likely to break for non-Linux-native users, so we need the signal.
- **Test PyPI rate limits.** Unlikely at our volume (a handful of releases per month, not per day). Mitigate by not running the full smoke on every PR, only on release-candidate and final tags.
- **GitHub-runner availability changes.** macOS arm64 runners became generally available in 2024; if GitHub deprecates or renames a runner image, the matrix config needs an update. Tracked through dependabot-style updates on the workflow file.
- **Matrix runtime bloat.** 12 cells × ~3 minutes per cell = ~36 minutes max parallel wall time. Acceptable for a release event.
- **Signature verification failures masking real install issues.** Mitigation: separate steps in the matrix — install step first, signature-verify step second. An install failure is distinguishable from a signature failure in the workflow logs.

## Open questions

- Do we run the smoke matrix on every PR merge to main, or only on tag push? Answer: only on tag push. PR-level CI already runs unit + integration tests; smoke is the release-gate signal, not a PR gate.
- Do we include a "pip install from Test PyPI" cell in addition to pipx? Answer: pipx is the primary recommended install path; pip-install coverage is implicit in pipx's underlying behavior. Keep the matrix small.
- How do we handle a matrix failure that the maintainer judges to be unrelated to the release (e.g., a GitHub-runner outage)? Answer: the maintainer can force-rerun the matrix; if a cell continues to fail for a clearly-external reason, document in the release notes and proceed — but only after the maintainer has explicitly made that call, not silently.
