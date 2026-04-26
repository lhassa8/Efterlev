# Release-pipeline dry-run runbook

**Why this exists:** the three release workflows (`release-pypi.yml`, `release-container.yml`, `release-smoke.yml`) have never actually run. The first time they run will be at launch hour unless we deliberately exercise them earlier. A broken workflow at launch hour is a panic-troubleshoot situation; a broken workflow on a dry-run is a calm-fix situation. This runbook drives the latter.

**When to run:** after all A1–A8 work is locally green, before flipping the repo public. Per the launch posture, this is gate-driven, not date-driven — when the maintainer is ready to validate the pipeline. The dry-run does NOT publish to real PyPI (the `-rc` tag skips that job by design).

**What it costs:** ~10 minutes of human attention plus ~30 minutes of CI runtime. No money — Trusted Publishing means no credentials to provision; ghcr.io uses the per-job `GITHUB_TOKEN`; only Docker Hub needs a long-lived secret (already configured if A2 is closed).

**What you'll learn:** whether the workflows actually run, whether all preconditions (Trusted Publishing config, GitHub environments, secrets, dependency versions) are correct, and which cells of the smoke matrix pass on which platforms.

---

## Pre-flight checklist

Run these checks BEFORE pushing the tag. Each one is an "if this isn't true, fix it before continuing" gate.

### 1. Git state is clean and at the SHA you want to release

```bash
git status                           # working tree clean
git log --oneline -5                 # confirm HEAD is the SHA to release
git rev-parse HEAD                   # capture the SHA for later reference
```

### 2. Local verification suite is green at HEAD

```bash
uv run --extra dev pytest -m "not e2e" -q
uv run --extra dev ruff check
uv run --extra dev mypy
uv run --extra docs mkdocs build --strict
bash scripts/launch-grep-scrub.sh
uv run python scripts/check-docs.py
bash scripts/dogfood-real-codebases.sh   # optional but high signal
```

All must exit 0. If any fail, do NOT push the tag.

### 3. PyPI Trusted Publishing is configured for TestPyPI

Without this the `publish-test-pypi` job will 403. The configuration lives in your TestPyPI account, not in this repo.

- Go to <https://test.pypi.org/manage/account/publishing/>
- Add a pending publisher with these exact values (matching the workflow):
  - Project name: `efterlev`
  - Owner: the GitHub org/user that will own the tag-pushing repo at dry-run time. **Currently this is `lhassa8`** since the repo hasn't been transferred yet. After transfer it will be `efterlev`. Configure for whichever owns the repo NOW.
  - Repository name: `Efterlev` (case matters — match the repo)
  - Workflow filename: `release-pypi.yml`
  - Environment name: `test-pypi`

If you've already configured this for `efterlev/efterlev` (post-transfer) and you're dry-running before the transfer, you'll need to add a second pending publisher for the current owner OR perform the dry-run after the transfer. The dry-run is most informative AFTER the transfer because it validates the post-transfer config.

### 4. GitHub environments exist on the repo

The workflow references two environments: `test-pypi` and `pypi`. They must exist (Settings → Environments) or the workflow's `environment:` blocks will fail.

- `test-pypi`: no required reviewers; the publish runs automatically.
- `pypi`: at least one required reviewer (you). This is the manual gate that prevents accidental real-PyPI publish. **For an `-rc.N` dry-run this gate is never hit** because the publish-pypi job is `if: is-rc == 'false'`. But the environment must still exist for the job-level `environment:` to validate.

### 5. `DOCKERHUB_TOKEN` secret is set on the repo

Settings → Secrets and variables → Actions. The container workflow needs it for the Docker Hub push (line 70 of release-container.yml). If unset, the Docker Hub push step fails informatively but the rest of the workflow continues. ghcr.io uses `GITHUB_TOKEN` which is automatic — no setup required.

If you don't have a Docker Hub org claimed yet, you have two options:
- **(a)** Skip Docker Hub publish for the dry-run (comment out the Docker Hub steps in release-container.yml temporarily, dry-run, then revert).
- **(b)** Push the dry-run anyway and accept that Docker Hub steps will fail; the ghcr.io path is still validated.

### 6. GitHub Pages is NOT relevant to the pipeline dry-run

Pages is for `docs-deploy.yml`, which doesn't fire on tag pushes. Ignore Pages for this dry-run.

---

## The dry-run

### Step 1: bump `pyproject.toml` version to match the planned tag

The release-pypi workflow's `verify` step will fail if `pyproject.toml`'s version doesn't match the tag (after PEP 440 normalization). For tag `v0.0.1-rc.1`, `pyproject.toml` must say `0.0.1rc1`.

```bash
# Edit pyproject.toml, change:   version = "0.0.1"
# to:                            version = "0.0.1rc1"
git add pyproject.toml
git commit -s -m "Bump pyproject.toml to 0.0.1rc1 for pipeline dry-run

Pre-launch dry-run of the release pipeline. The release-pypi
workflow's verify step requires pyproject.toml to match the tag
after PEP 440 normalization (v0.0.1-rc.1 → 0.0.1rc1). Will be
reverted to 0.0.1 (or bumped to 0.1.0 for the real launch tag)
after the dry-run completes."
```

### Step 2: push the tag

```bash
git tag v0.0.1-rc.1
git push origin main           # push the bump commit first
git push origin v0.0.1-rc.1    # then the tag — fires all three workflows
```

### Step 3: watch the workflows

```bash
gh run list --limit 5 --branch main
gh run watch --exit-status       # follow whichever's running
```

Or in the browser: Actions tab on the repo.

### Step 4: per-workflow verification

For each workflow, observe the outcome and record it. Expected behavior:

#### `release-pypi`

- ✅ `build` job: must pass. Verifies version match, builds wheel + sdist, uploads as `dist` artifact.
- ✅ `publish-test-pypi` job: should pass IF Trusted Publishing is configured per pre-flight #3. If it fails with a 403, the publisher config is missing or mismatched. If it fails with "version exists" — TestPyPI doesn't allow re-uploads of the same version. Bump to `-rc.2` and re-tag.
- ⏭️ `publish-pypi` job: should NOT run (skipped by `if: is-rc == 'false'`). Confirm in the run summary that it shows as "Skipped."

#### `release-container`

- ✅ `build-and-push` job: builds multi-arch image, pushes to ghcr.io (using `GITHUB_TOKEN` — should always work) and to Docker Hub (needs `DOCKERHUB_TOKEN`).
- ✅ `cosign sign --yes` step: signs the pushed image by digest.
- ✅ `cosign verify` step: confirms the signature on what's actually in the registry. **This is the critical end-to-end check** — if it passes, sigstore is fully wired.

After it completes, manually verify the image is real:

```bash
docker pull ghcr.io/<owner>/efterlev:v0.0.1-rc.1
docker run --rm ghcr.io/<owner>/efterlev:v0.0.1-rc.1 efterlev --help
```

#### `release-smoke`

- 9-cell matrix: 5 pipx cells (Linux, Linux-arm, macOS x86, macOS arm, Windows) + 2 docker-ghcr cells + 2 docker-dockerhub cells.
- Each cell polls the relevant registry until the artifact appears (TestPyPI for pipx; ghcr.io for docker-ghcr; Docker Hub for docker-dockerhub), then installs + runs `efterlev scan` against an embedded fixture.
- Fail-fast is OFF, so all cells run to completion regardless of others.
- **What to look for:** how many cells pass. 9/9 = pipeline is fully validated. <9/9 = note which platforms fail and why; not all need to pass v0.1.0 (the deployment-mode matrix calls out which are CI-required vs documented-but-unverified).

### Step 5: revert the version bump (optional)

If the dry-run found issues you want to fix before another attempt, revert the version bump and iterate. If everything was green and you're going straight to the real v0.1.0 tag soon, leave the version at `0.0.1rc1` until the next bump.

```bash
# Option A: revert to 0.0.1 (back to pre-dry-run state)
git revert <bump-commit-sha> --no-edit

# Option B: leap to 0.1.0 in preparation for the real launch tag
# (edit pyproject.toml: version = "0.1.0", commit, then push v0.1.0 tag at launch hour)
```

### Step 6: clean up dry-run artifacts

The dry-run produces real artifacts in:
- TestPyPI: `efterlev==0.0.1rc1` will live there forever (TestPyPI doesn't allow deletion). This is fine — it's the validation evidence.
- ghcr.io: `ghcr.io/<owner>/efterlev:v0.0.1-rc.1` and the `:0.0.1rc1` tag. Can be deleted via the Packages UI on the repo if desired; not required.
- Docker Hub: same. Optional cleanup.

The git tag `v0.0.1-rc.1` should stay — it's the audit trail of when the dry-run happened.

---

## Failure-response playbook

### `release-pypi.build` fails on version mismatch

You forgot Step 1 (the version bump), or the bump is wrong. Read the error message — it prints both the tag-derived version and the pyproject.toml version. Fix pyproject.toml, push the fix, re-tag (`-rc.2`).

### `release-pypi.publish-test-pypi` fails with 403

Trusted Publishing isn't configured for the (owner, repo, workflow, environment) tuple. Check pre-flight #3 against what's actually in TestPyPI's pending-publisher config. Common gotcha: case-sensitive owner/repo names.

### `release-pypi.publish-test-pypi` fails with "version exists"

Someone (probably you, on a previous dry-run) already uploaded this version. Bump to `-rc.2` and re-tag. TestPyPI does not allow overwriting versions — this is by design.

### `release-container` fails on the cosign sign step

`id-token: write` permission is set in the workflow but may be blocked at the org level. Check Settings → Actions → General → Workflow permissions = "Read and write" + "Allow GitHub Actions to create and approve pull requests."

### `release-container` Docker Hub push fails with auth error

`DOCKERHUB_TOKEN` secret is missing or revoked. Set it (Settings → Secrets and variables → Actions). The token needs Read+Write+Delete scope on the `efterlev` namespace.

### `release-smoke` cells time out

Each cell polls registries with a 10-minute deadline (line 13-17 of `release-smoke.yml`). If the container or PyPI artifact takes longer than 10 minutes to propagate, the smoke job times out. Re-running the workflow after the artifact has appeared usually works.

### Multiple cells fail consistently on one platform

Investigate the platform-specific install path. The matrix is intentionally diverse — Windows ARM, macOS Intel, etc. — so platform-specific install bugs surface here, not at customer install time. Document the failing platform in the deployment-mode matrix.

---

## What the dry-run does NOT validate

Be honest about scope:

- **Real-PyPI publish:** intentionally skipped by `-rc` tags. The first time real-PyPI runs is the real launch.
- **PyPI manual approval gate:** intentionally skipped (the `pypi` env's required-reviewer flow doesn't fire on `-rc`). The first time the gate runs is the real launch.
- **Public-repo behavior:** the workflows run on a private repo for the dry-run. Public-flip changes some defaults (e.g., GitHub Discussions auto-enable). Re-confirm after flip.
- **`docs-deploy.yml`:** this workflow doesn't fire on tag pushes (paths-filter on docs/ + push to main). Tested separately by the `workflow_dispatch` step in the launch runbook.

---

## Decision tree after the dry-run

- **All workflows green, all smoke cells pass:** the pipeline is launch-ready. Next step is the maintainer-action queue (repo transfer, branch protection, Pages enable, security-review §8 sign-off, GovCloud walkthrough, fresh-eyes runbook rehearsal). Then `git tag v0.1.0` for the real launch.

- **One or two smoke cells fail (Windows, ARM-something) but the publish + container + sign all pass:** the pipeline core is sound. Decide platform-by-platform whether to block launch on those cells. Document failures in `docs/deployment-modes.md`. Most v0.1.0 launches don't block on every platform.

- **Trusted Publishing or DOCKERHUB_TOKEN auth fails:** prerequisite gap, not a code bug. Fix the config, re-tag (`-rc.2`), re-run.

- **A cosign or sigstore step fails:** treat this as a real bug. Sigstore is the trust foundation for the launch. Investigate before the next attempt.

- **Workflow doesn't fire at all:** check Settings → Actions → General. Workflows may be disabled at the repo level.

---

## Cross-references

- `.github/workflows/release-pypi.yml` — the PyPI publish workflow
- `.github/workflows/release-container.yml` — the container build + sign workflow
- `.github/workflows/release-smoke.yml` — the install-verification matrix
- `docs/RELEASE.md` — release-notes template and verification guidance for users
- `docs/launch/runbook.md` — the broader hour-by-hour launch sequence (this dry-run is its pre-launch step)
- `scripts/verify-release.sh` — the user-side verification script run against released artifacts
