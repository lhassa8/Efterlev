# Deployment modes

Where Efterlev runs, with verification status per mode. Maintained per [SPEC-53](specs/SPEC-53.md).

A mode is one of three states:

- **🟢 CI-verified.** Covered by [`release-smoke.yml`](https://github.com/efterlev/efterlev/blob/main/.github/workflows/release-smoke.yml) on every tag. The matrix cell ran on the most recent release; failures gate real-PyPI publication.
- **🟡 Manually verified.** A human walked through the mode end-to-end. Records the commit SHA and date.
- **⚪ Documented but unverified.** A runbook or tutorial describes the mode, but no end-to-end verification has been recorded. Honest state for v0.1.0; entries graduate as customers and maintainers walk them.

## Matrix

| Mode | Verification | Latest | Notes |
|---|---|---|---|
| **macOS arm64 — pipx (Test PyPI / PyPI)** | 🟢 CI-verified | release-smoke matrix cell `macos-14 / pipx` | Apple Silicon; `actions/setup-python@v5` Python 3.12. |
| **macOS x86_64 — pipx** | 🟢 CI-verified | release-smoke matrix cell `macos-13 / pipx` | Intel-Mac runners may eventually deprecate from GitHub-hosted runners; the cell switches to GitHub-supplied alternative when that happens. |
| **Ubuntu 22.04 x86_64 — pipx** | 🟢 CI-verified | release-smoke matrix cell `ubuntu-22.04 / pipx` | Reference Linux distribution. |
| **Ubuntu 24.04 arm64 — pipx** | 🟢 CI-verified | release-smoke matrix cell `ubuntu-24.04-arm / pipx` | GitHub's hosted ARM Linux runners. |
| **Windows 2022 x86_64 — pipx** | 🟢 CI-verified | release-smoke matrix cell `windows-2022 / pipx` | Git Bash compatibility verified by `tests/smoke/assert.py` (Python; runs identically across platforms). |
| **Ubuntu 22.04 x86_64 — Docker (ghcr.io)** | 🟢 CI-verified | release-smoke matrix cell `ubuntu-22.04 / docker-ghcr` | `ghcr.io/efterlev/efterlev:latest`. |
| **Ubuntu 22.04 x86_64 — Docker (Docker Hub)** | 🟢 CI-verified | release-smoke matrix cell `ubuntu-22.04 / docker-dockerhub` | `docker.io/efterlev/efterlev:latest`. |
| **Ubuntu 24.04 arm64 — Docker (ghcr.io)** | 🟢 CI-verified | release-smoke matrix cell `ubuntu-24.04-arm / docker-ghcr` | Multi-arch image built via QEMU during release. |
| **Ubuntu 24.04 arm64 — Docker (Docker Hub)** | 🟢 CI-verified | release-smoke matrix cell `ubuntu-24.04-arm / docker-dockerhub` | Multi-arch image. |
| **GitLab CI (any host)** | ⚪ Documented but unverified | runbook: [`tutorials/ci-gitlab.md`](tutorials/ci-gitlab.md) | Pattern is `image: ghcr.io/efterlev/efterlev:latest`. Verification graduates to 🟡 when a customer or maintainer reports a successful pipeline. |
| **CircleCI** | ⚪ Documented but unverified | runbook: [`tutorials/ci-circleci.md`](tutorials/ci-circleci.md) | Same pattern as GitLab — container-based job. |
| **Jenkins** | ⚪ Documented but unverified | runbook: [`tutorials/ci-jenkins.md`](tutorials/ci-jenkins.md) | Container-based pipeline-stage skeleton. |
| **AWS EC2 commercial region + Bedrock** | ⚪ Documented but unverified | runbook: [`tutorials/deploy-govcloud-ec2.md`](tutorials/deploy-govcloud-ec2.md) (substitute commercial region) | The GovCloud tutorial is the canonical setup; commercial-region differs only in IAM partition (`aws` vs `aws-us-gov`) and Bedrock model availability. |
| **AWS GovCloud EC2 + Bedrock GovCloud** | ⚪ Documented but unverified | runbook: [`tutorials/deploy-govcloud-ec2.md`](tutorials/deploy-govcloud-ec2.md); automated smoke: SPEC-13 e2e harness Bedrock path | The "runs anywhere customer wants it to run" load-bearing claim. Graduates to 🟡 when a maintainer (or design-partner) walks the runbook on a real GovCloud account. |
| **Air-gap container (no internet egress)** | ⚪ Documented but unverified | runbook: [`tutorials/deploy-air-gap.md`](tutorials/deploy-air-gap.md) | True air-gap (no AWS-API egress either) needs a local LLM backend; v1.5+. The "boundary-isolated" variant (egress only to AWS Bedrock VPC endpoint) is achievable on v0.1.0 but not yet walked end-to-end. |

## How a mode graduates

`Documented but unverified ⚪ → Manually verified 🟡`:

1. Walk the runbook end-to-end on a real instance of the target environment.
2. Confirm the pass criteria from `docs/manual-verification-runbook.md`.
3. Open a PR that updates this matrix:
   - Status icon changes to 🟡.
   - "Latest" column gets `<commit-sha> @ <YYYY-MM-DD> (reviewed by @handle)`.
   - "Notes" column gets any new gotchas the walkthrough surfaced.
4. PR merges. The mode is verified at that commit until the next walkthrough or a major release shifts the env.

`Manually verified 🟡 → Stale`:

A 🟡 entry whose commit SHA is more than 6 months behind `main` is informally treated as stale. We're not currently auto-flagging this in CI; that's a follow-up if matrix maintenance starts to lag.

## What's not on the matrix

- **Kubernetes / Helm.** Out of scope at v0.1.0; container image is what runs in K8s if you orchestrate it yourself. K8s-native deployment is post-launch C3 territory.
- **Self-hosted GitHub Actions runners.** Should work identically to GitHub-hosted runners; not separately matrixed.
- **Per-distribution Linux variants.** Debian 12, RHEL 9, Fedora, Arch, etc. — the container image abstracts the distro. Bare-metal pipx installs on non-Ubuntu distros work in practice but aren't matrixed.

If you're running Efterlev in a mode not listed here and it works (or doesn't), [open a Discussion](https://github.com/efterlev/efterlev/discussions) — your data point graduates the matrix.
