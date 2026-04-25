# SPEC-06: Container image (multi-arch)

**Status:** Dockerfile + workflow landed 2026-04-24; Docker Hub token + first dry-run are maintainer actions
**Gate:** A2
**Depends on:** SPEC-01 (container registry namespaces), SPEC-05 (release triggers same tag that builds containers)
**Blocks:** SPEC-08 (container images are signed by that pipeline — signing wired inline), SPEC-45 (air-gap tutorial uses the container)
**Size:** M

## Goal

`docker run --rm -v $(pwd):/repo ghcr.io/efterlev/efterlev:latest scan /repo` works on any Docker-capable host — amd64 laptop, arm64 laptop, Linux x86_64 CI runner, Linux arm64 CI runner, and AWS EC2 (both commercial and GovCloud). No secondary install steps.

## Scope

- Multi-arch image: `linux/amd64` and `linux/arm64`
- Published to both `ghcr.io/efterlev/efterlev` (primary) and `docker.io/efterlev/efterlev` (mirror)
- Base image: `python:3.12-slim-bookworm` at v0.1.0; distroless migration tracked as a follow-up spec if the size/security trade-off is worth it
- Entrypoint: `efterlev` (so `docker run ... <args>` passes args directly to the CLI)
- Tags: `v{semver}` per release, `v{major}.{minor}` moving tag, and `latest` pointing at the most recent non-rc release
- Built and pushed on every semver tag via GitHub Actions
- Container signed via SPEC-08 Sigstore pipeline

## Non-goals

- Windows container support (separate spec if demanded; our ICP overwhelmingly uses Linux CI runners)
- Alpine-based image (musl-libc compatibility risk with python-hcl2 and compliance-trestle transitive deps is not worth the ~50MB saving)
- Non-root user at v0.1.0 (scan-tool use case makes root-in-container acceptable; hardening is tracked for a follow-up spec)
- Custom base image (building from scratch or a Wolfi base adds maintenance burden we don't need at v0.1.0)
- Bundling an LLM model (the container is an Efterlev install, not a self-contained inference stack)

## Interface

- `Dockerfile` at repo root
- `.github/workflows/release-container.yml` triggered on `push` to `tags: ['v*.*.*']`
- Build uses `docker/build-push-action` with `platforms: linux/amd64,linux/arm64`
- QEMU multi-arch emulation via `docker/setup-qemu-action`
- Images published to both registries in a single workflow run
- Registry authentication: GitHub OIDC for ghcr.io, Docker Hub access-token stored in repo secret `DOCKERHUB_TOKEN`

Usage contract:
```bash
# Default: scan current directory (repo mounted at /repo)
docker run --rm -v $(pwd):/repo ghcr.io/efterlev/efterlev:v0.1.0 scan /repo

# Version check
docker run --rm ghcr.io/efterlev/efterlev:latest --version

# Persist .efterlev/ across runs
docker run --rm -v $(pwd):/repo -v efterlev-store:/repo/.efterlev \
  ghcr.io/efterlev/efterlev:latest scan /repo
```

Environment variables honored inside the container:
- `ANTHROPIC_API_KEY` — forwarded to agent commands
- `AWS_REGION`, `AWS_PROFILE`, `AWS_ACCESS_KEY_ID`, etc. — for Bedrock backend (SPEC-10)
- `EFTERLEV_DIR` — override `.efterlev/` location

## Behavior

- `docker run --rm -v $(pwd):/repo ghcr.io/efterlev/efterlev:latest scan /repo` produces the same output as `efterlev scan .` on the host would, with `.efterlev/` materialized inside the mounted volume at `/repo/.efterlev/`.
- `docker run --rm ghcr.io/efterlev/efterlev:latest --version` prints the same version the `pipx install`-equivalent would.
- Image size target: under 200 MB compressed. python:3.12-slim is roughly 50 MB; adding Efterlev + dependencies should land well under the cap.
- Image signed via Sigstore (SPEC-08); signature verifiable via `cosign verify`.
- `latest` tag updated only on final-release tags (`v{major}.{minor}.{patch}` with no `-rc.*` suffix).
- `v0.1` (major.minor moving tag) updated on every patch release within that minor line; allows `:v0.1` as a stable-within-minor pin.
- ENTRYPOINT is `["efterlev"]` (not `/bin/sh -c ...`) so CMD args pass through cleanly.

## Data / schema

- Mount convention: host working directory → `/repo` inside container.
- Inside the container, `/repo/.efterlev/` is the Efterlev state directory. Writable; inherits host volume's permissions.
- No container-internal state beyond the `.efterlev/` directory; image is otherwise read-only.

## Test plan

- **Unit (build):** `docker/build-push-action` CI run produces both arch variants on every tag. Release-container workflow reports success.
- **Integration (smoke):** per SPEC-09 install-verification matrix, pull each arch from each registry and run:
  - `docker run --rm $IMAGE --version` → matches expected version string
  - `docker run --rm -v $demo:/repo $IMAGE scan /repo` against a known fixture → exit 0 and expected findings
- **Arch coverage:** the arm64 smoke test runs on a real arm64 CI runner (GitHub provides these), not via QEMU emulation at test time.
- **Registry coverage:** smoke test runs against both ghcr.io and Docker Hub variants of the same version.
- **Signature verification:** `cosign verify ghcr.io/efterlev/efterlev:v0.1.0-rc.1 --certificate-identity-regexp '^https://github.com/efterlev/efterlev/'` succeeds (part of SPEC-08).

## Exit criterion

### Landed 2026-04-24

- [x] `Dockerfile` at repo root — two-stage (builder → runtime), `python:3.12-slim-bookworm` base, builds wheel via `uv build --wheel` (catalogs force-included per pyproject.toml), installs wheel into runtime layer, `ENTRYPOINT ["efterlev"]`, `WORKDIR /repo`, full OCI labels.
- [x] `.dockerignore` excludes VCS, dev artifacts, tests, scripts, docs (except README.md), `.efterlev/`, `.e2e-results/`.
- [x] `.github/workflows/release-container.yml` — multi-arch buildx (amd64 + arm64 via QEMU), pushes to both `ghcr.io/efterlev/efterlev` and `docker.io/efterlev/efterlev`, tag strategy (`vX.Y.Z` always; `vX.Y` + `latest` only on non-rc), cosign keyless-OIDC signing by digest with inline verification, SBOM + provenance attestation via buildx.
- [x] One-time maintainer setup documented as a header comment in the workflow.

### Maintainer actions — pending

- [ ] Docker Hub: create the `efterlev` org and generate an access token. Add as repo secret `DOCKERHUB_TOKEN`.
- [ ] Repo transfer to `efterlev/efterlev` (SPEC-01 remaining) so the `ghcr.io/efterlev/` namespace is writable by this repo's `GITHUB_TOKEN`.
- [ ] First dry-run: cut `v0.1.0-rc.0` tag (after SPEC-05 dry-run), observe container builds and pushes to both registries.
- [ ] Verify pullability of `ghcr.io/efterlev/efterlev:v0.1.0-rc.0` and the Docker Hub equivalent on both amd64 and arm64 hosts.
- [ ] Verify cosign signatures against both registries from a clean shell.
- [ ] Confirm image size under the 200 MB target; if over, open a follow-up spec to move to distroless or prune further.

## Risks

- **QEMU multi-arch build is slow.** Accept: adds ~5 minutes per arch; release workflow runs only on tag push, not on every PR. Not on the critical path for contributor velocity.
- **Docker Hub rate-limits anonymous pulls.** Accept: users hitting rate limits can pull from ghcr.io instead; docs mention both registries.
- **python-hcl2 or another transitive dep doesn't build wheels for arm64.** Mitigation: verified at first build; if encountered, either pin a working version or build the dep from source in the Dockerfile. We'd know during the A2 dry-run, not at launch.
- **Container-internal secret leakage via `.efterlev/` on a shared volume.** Mitigation: docs warn not to mount volumes that other containers share; the secret-redaction work already scrubs prompts before they leave the tool.
- **Non-root-user migration later is a breaking change for users who've configured volume permissions.** Accept: documented clearly when the non-root hardening spec ships; the change carries a major or minor version bump, not a patch.

## Open questions

- Do we publish a `:sha-{short}` tag for every main-branch commit, in addition to release tags? Answer: no at v0.1.0. Only release tags. If demand surfaces (e.g., CI users wanting "latest-tested commit"), add in a follow-up spec.
- Do we publish to quay.io as a third registry? Answer: no at v0.1.0. Two registries is enough; third adds maintenance without clear ICP pull.
