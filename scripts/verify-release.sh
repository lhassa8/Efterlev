#!/usr/bin/env bash
# verify-release.sh — end-to-end cryptographic verification of an Efterlev release.
#
# Checks:
#   1. PyPI wheel + sdist are signed by the expected GitHub Actions workflow
#      via Sigstore (Trusted Publishing attestations).
#   2. Container images on both registries (ghcr.io and docker.io) are signed
#      by the expected workflow via cosign keyless OIDC.
#   3. SLSA build provenance is attached to each container image.
#
# Usage:
#   scripts/verify-release.sh v0.1.0
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed
#   2 — usage error or missing tools

set -euo pipefail

# ---------- argument parsing ----------

if [ $# -ne 1 ]; then
  echo "Usage: $0 <version>" >&2
  echo "Example: $0 v0.1.0" >&2
  exit 2
fi

VERSION="${1#v}"
TAG="v${VERSION}"
EXPECTED_REPO="efterlev/efterlev"
OIDC_ISSUER="https://token.actions.githubusercontent.com"

# ---------- tool-availability checks ----------

missing=0
need() {
  command -v "$1" >/dev/null 2>&1 || { echo "  missing: $1" >&2; missing=1; }
}
echo "Checking prerequisites..."
need curl
need python3
need cosign
need docker

if ! python3 -c "import sigstore" >/dev/null 2>&1; then
  echo "  missing: sigstore Python package" >&2
  missing=1
fi

if [ "$missing" -ne 0 ]; then
  echo
  echo "Install missing tools:" >&2
  echo "  cosign:   https://docs.sigstore.dev/system_config/installation" >&2
  echo "  sigstore: python3 -m pip install sigstore" >&2
  exit 2
fi
echo "  all tools available"
echo

# ---------- shared state ----------

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

pass=0
fail=0

pass_line() { printf "  \033[32m✓\033[0m %s\n" "$1"; pass=$((pass + 1)); }
fail_line() { printf "  \033[31m✗\033[0m %s\n" "$1"; fail=$((fail + 1)); }
info_line() { printf "    %s\n" "$1"; }

# ---------- check 1: PyPI wheel + sdist ----------

echo "[1/3] PyPI artifacts — Sigstore signatures via Trusted Publishing"

# Query the PyPI JSON API for this version's download URLs.
pypi_json="$WORKDIR/pypi.json"
if ! curl -sfL -o "$pypi_json" "https://pypi.org/pypi/efterlev/${VERSION}/json"; then
  fail_line "PyPI version $VERSION not found"
else
  urls=$(python3 -c "
import json, sys
d = json.load(open('$pypi_json'))
for f in d['urls']:
    print(f['url'])
")
  for url in $urls; do
    name="$(basename "$url")"
    curl -sfL -o "$WORKDIR/$name" "$url"
    # PyPI Trusted Publishing attaches a .sigstore sidecar bundle per artifact.
    # The sidecar URL is derived from the PEP 740 attestation set exposed under
    # the project's /integrity endpoint, but as a pragmatic check, each .whl or
    # .tar.gz on PyPI is accompanied by a Sigstore bundle the JSON API indexes
    # under the same file group. We look for .sigstore next to the artifact.
    sidecar_url="${url}.sigstore"
    if curl -sfL -o "$WORKDIR/$name.sigstore" "$sidecar_url"; then
      if python3 -m sigstore verify identity \
          --bundle "$WORKDIR/$name.sigstore" \
          --cert-identity "https://github.com/${EXPECTED_REPO}/.github/workflows/release-pypi.yml@refs/tags/${TAG}" \
          --cert-oidc-issuer "$OIDC_ISSUER" \
          "$WORKDIR/$name" >/dev/null 2>&1; then
        pass_line "$name: Sigstore signature valid"
      else
        fail_line "$name: signature failed verification"
      fi
    else
      fail_line "$name: no .sigstore sidecar present (release predates Trusted Publishing or signing was disabled)"
    fi
  done
fi
echo

# ---------- check 2: container signatures on both registries ----------

echo "[2/3] Container images — cosign keyless-OIDC signatures"

for registry in ghcr.io/efterlev/efterlev docker.io/efterlev/efterlev; do
  image="${registry}:${TAG}"
  if ! docker manifest inspect "$image" >/dev/null 2>&1; then
    fail_line "$image: image not pullable (not published yet, or registry unreachable)"
    continue
  fi

  # Sign-by-digest is the cosign-recommended pattern. Resolve the digest first.
  digest="$(docker buildx imagetools inspect "$image" --format '{{ .Manifest.Digest }}' 2>/dev/null || true)"
  if [ -z "$digest" ]; then
    fail_line "$image: could not resolve digest"
    continue
  fi
  image_by_digest="${registry}@${digest}"

  if cosign verify "$image_by_digest" \
      --certificate-identity-regexp "^https://github\.com/${EXPECTED_REPO}/" \
      --certificate-oidc-issuer "$OIDC_ISSUER" \
      >/dev/null 2>&1; then
    pass_line "$image: cosign signature valid"
    info_line "digest: $digest"
  else
    fail_line "$image: cosign verification failed"
  fi
done
echo

# ---------- check 3: SLSA provenance on container images ----------

echo "[3/3] SLSA build provenance — OCI attestations"

for registry in ghcr.io/efterlev/efterlev docker.io/efterlev/efterlev; do
  image="${registry}:${TAG}"
  if ! docker manifest inspect "$image" >/dev/null 2>&1; then
    # Already fail-lined above; skip SLSA check quietly.
    continue
  fi

  if cosign verify-attestation --type slsaprovenance \
      "$image" \
      --certificate-identity-regexp "^https://github\.com/${EXPECTED_REPO}/" \
      --certificate-oidc-issuer "$OIDC_ISSUER" \
      >/dev/null 2>&1; then
    pass_line "$image: SLSA build provenance present and valid"
  else
    fail_line "$image: SLSA provenance missing or invalid"
  fi
done
echo

# ---------- summary ----------

echo "---"
echo "Verification summary for efterlev $TAG"
echo "  passed: $pass"
echo "  failed: $fail"

if [ "$fail" -gt 0 ]; then
  echo
  echo "Release $TAG FAILED verification. Do not install."
  exit 1
fi

echo
echo "Release $TAG is cryptographically verified."
exit 0
