# SPEC-05: PyPI release pipeline

**Status:** workflow landed 2026-04-24; trusted-publishing registration + first dry-run are maintainer actions
**Gate:** A2
**Depends on:** SPEC-01 (PyPI name held — done), SPEC-04 (release tags signed — policy documented, maintainer config pending)
**Blocks:** SPEC-08 (signing runs inside this pipeline), SPEC-09 (install verification pulls from Test PyPI before this pipeline publishes to real PyPI)
**Size:** M

## Goal

A tagged-commit on `main` produces a PyPI release via GitHub Actions with zero long-lived credentials, so `pipx install efterlev` works the moment the gate passes and every subsequent release is a one-commit operation.

## Scope

- GitHub Actions workflow triggered on semver-shaped tag push (`v*.*.*` or `v*.*.*-rc.*`)
- Builds both wheel and sdist via `uv build`
- Uploads via PyPI trusted publishing (OIDC, no long-lived token)
- First public release: `v0.1.0`
- Pre-release candidates (`v*.*.*-rc.*`) upload to Test PyPI only
- Final releases (`v*.*.*`) upload to real PyPI
- Version in `pyproject.toml` must match the tag; mismatch aborts the release
- Pre-launch: workflow lives in the repo but only triggers on Test PyPI targets until SPEC-09 matrix passes and the repo flips public

## Non-goals

- Automatic version bumping (manual, deliberate — release is an explicit act)
- Conda-forge publishing (separate spec if demanded; not a launch blocker)
- Homebrew formula (separate spec if demanded)
- Auto-generated release notes (changelog discipline is per-PR; release notes are the collected changelog section for the release, curated manually at tag time)
- Binary wheels for native extensions (Efterlev is pure Python; no native code)

## Interface

- Workflow: `.github/workflows/release-pypi.yml`
- Triggers: `push` with `tags: ['v*.*.*', 'v*.*.*-rc.*']`
- Uses `pypa/gh-action-pypi-publish` with OIDC trusted-publisher configuration
- PyPI project settings: configured to trust the `efterlev/efterlev` repo's `release-pypi.yml` workflow file + `release-pypi` environment (for deployment-environment scoping)
- Test PyPI project settings: same configuration on test.pypi.org
- Job graph:
  1. `build` — `uv build` → produces `dist/*.whl` + `dist/*.tar.gz`
  2. `verify-version` — `pyproject.toml` version matches tag (strip leading `v`)
  3. `upload-test-pypi` — runs on any tag; uploads to Test PyPI via OIDC
  4. `upload-pypi` — runs only on `v*.*.*` (no `-rc.*` suffix); uploads to real PyPI via OIDC; blocked on SPEC-09 smoke matrix green

## Behavior

- **`v0.1.0-rc.1` tag pushed:** workflow runs `build` → `verify-version` → `upload-test-pypi`. Real PyPI upload skipped. Release-candidate installable via `pip install -i https://test.pypi.org/simple/ efterlev==0.1.0rc1`.
- **`v0.1.0` tag pushed:** workflow runs `build` → `verify-version` → `upload-test-pypi` (still) → wait for SPEC-09 matrix on the same commit → if all green, `upload-pypi` uploads to real PyPI.
- **Tag-version mismatch:** `verify-version` fails; workflow aborts before any upload. Maintainer fixes `pyproject.toml` version, re-tags.
- **Upload failure (PyPI rate limit, outage, name conflict):** workflow marks release as failed; maintainer can re-run the workflow from the UI after investigation. The tag remains; no partial release.
- **Version format:** strict semver, `v{major}.{minor}.{patch}` with optional `-rc.N` suffix. No `-dev`, no `-alpha`, no `-beta` initially.

## Data / schema

- Tag format: `v{major}.{minor}.{patch}` or `v{major}.{minor}.{patch}-rc.{N}`
- `pyproject.toml` `[project]` table: `version = "{major}.{minor}.{patch}"` or `"{major}.{minor}.{patch}rc{N}"` (PEP 440 form; trusted-publishing action normalizes)
- Artifacts in `dist/`: `efterlev-{version}-py3-none-any.whl` and `efterlev-{version}.tar.gz`

## Test plan

- **Dry-run on Test PyPI:** push `v0.1.0-rc.1` tag; verify wheel + sdist land on test.pypi.org; verify `pip install -i https://test.pypi.org/simple/ efterlev==0.1.0rc1` works in a throwaway venv.
- **Version-matches-tag failure:** push a tag `v0.9.9` when `pyproject.toml` says `0.1.0`; workflow must fail at the `verify-version` step before any upload.
- **Trusted-publishing misconfiguration:** intentionally remove the PyPI-side OIDC trust entry; workflow must fail at the upload step with a clear error; re-adding the trust allows a workflow re-run to succeed.
- **Post-upload smoke (part of SPEC-09):** `pipx install efterlev=={version}` succeeds in the install-verification matrix before real-PyPI upload is allowed.

## Exit criterion

### Workflow landed 2026-04-24

- [x] `.github/workflows/release-pypi.yml` exists on `main` with three jobs: `build`, `publish-test-pypi`, `publish-pypi`. YAML syntax validated.
- [x] Version-verification step in `build` compares `pyproject.toml` version against tag, normalizing semver rc suffix to PEP 440 (`v0.1.0-rc.1` → `0.1.0rc1`).
- [x] `build` step runs `uv build` for wheel + sdist; `twine check` on artifacts; uploads as workflow artifact.
- [x] `publish-test-pypi` always runs (every semver tag including rc).
- [x] `publish-pypi` gated on `is-rc == 'false'` — never publishes rc tags to real PyPI.
- [x] Both publish jobs use `pypa/gh-action-pypi-publish@release/v1` with trusted-publishing OIDC (no long-lived tokens).
- [x] Sigstore signing enabled by default under trusted publishing (SPEC-08 ties in here).
- [x] One-time maintainer setup documented as a comment block at the top of the workflow file.

### Maintainer actions — pending

- [ ] Configure Test PyPI trusted-publishing at test.pypi.org → Publishing → Add a pending publisher: project `efterlev`, owner `efterlev`, repo `efterlev`, workflow `release-pypi.yml`, environment `test-pypi`. (Requires repo transfer to `efterlev/efterlev` first per SPEC-01.)
- [ ] Configure real PyPI trusted-publishing at pypi.org with the same pattern, environment `pypi`.
- [ ] Configure the `pypi` GitHub environment in repo settings to require maintainer approval as the human gate that confirms SPEC-09 `release-smoke.yml` passed on the same tag.
- [ ] Bump `pyproject.toml` version to `0.1.0rc0` (or similar) and cut `v0.1.0-rc.0` tag as the first dry-run; verify end-to-end Test PyPI publication.
- [ ] Verify throwaway-venv `pip install -i https://test.pypi.org/simple/ efterlev==0.1.0rc0` produces a working install.
- [ ] At A8 launch rehearsal or later: bump `pyproject.toml` to `0.1.0`, cut `v0.1.0` tag, observe real-PyPI publication (after approving the environment gate).

## Risks

- **PyPI trusted-publishing misconfiguration is silent until first release.** Mitigation: the Test PyPI dry-run is the integration test for this; do it early in A2, not late.
- **PyPI outage at real-launch time.** Accept: launch is gate-driven; if PyPI is down, we retry when it's up. No pressure to release on a specific day.
- **Name squatter uploads `efterlev` to PyPI before we do.** Addressed in SPEC-01 (name reservation). If it happens anyway, PyPI has a namespace-dispute process; fallback is `efterlev-compliance`.
- **Malicious dependency introduced during release.** Mitigation: dependency lockfile committed; builds reproducible; SLSA provenance (SPEC-08) ties each wheel to its build workflow.

## Open questions

- Should pre-release tags (`-rc.*`) ever publish to real PyPI? Answer: no. Real PyPI only for final semver releases. Keeps consumer surface clean. If someone specifically needs a pre-release via real PyPI, a spec amendment revisits this.
- Environment protection: do we gate the `upload-pypi` job on manual approval in the first release? Answer: yes, for `v0.1.0` specifically — `release-pypi` GitHub environment requires a maintainer approval click before the real-PyPI upload step. Subsequent releases can drop the manual gate after the workflow has proven itself over 3+ releases.
