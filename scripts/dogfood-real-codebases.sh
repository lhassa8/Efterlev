#!/usr/bin/env bash
# Dogfood Efterlev against pinned real-world Terraform codebases. Catches
# regressions that synthetic fixtures can't surface — e.g. detector
# registration silently dropping (the 16-of-30 bug found 2026-04-25),
# parser changes breaking real codebases, python-hcl2 dependency bumps
# introducing new parse failures, or a detector going silent on inputs
# it used to fire on.
#
# Each target is pinned at a specific SHA so upstream churn doesn't
# spook this test. SHAs were captured at known-good state on 2026-04-25
# after parse_terraform_tree gained collect-and-continue semantics.
#
# Thresholds are deliberately loose: we assert "at least N" not "exactly
# N" so this test catches catastrophic regressions, not normal upstream
# evolution. Tight thresholds are the wrong call here — they go yellow
# constantly, get ignored, and stop catching real problems.
#
# Exit 0 = every target scanned with the registry intact and the parser
# producing at least the floor expected. Exit 1 = something regressed.

set -euo pipefail

# Targets: one line each, pipe-separated fields.
#   name | repo | sha | min_resources | min_evidence | max_parse_failures
# Plain bash 3.2-compatible config (associative arrays need bash 4+;
# macOS ships 3.2 — refusing to use it here would block local invocation).
TARGETS_TSV='terraform-aws-vpc|terraform-aws-modules/terraform-aws-vpc|3ffbd46fb1c7733e1b34d8666893280454e27436|80|4|0
terraform-aws-rds|terraform-aws-modules/terraform-aws-rds|fa183b6b36204913fac1219d09b4979c1e60443a|15|5|0
terraform-aws-iam|terraform-aws-modules/terraform-aws-iam|981121bcd17618b8ed032223c0d9e647b9277ef9|25|12|0
terraform-aws-eks|terraform-aws-modules/terraform-aws-eks|ed7f4d5f5129999f1723cd2f76a0804a53adf4d3|90|10|5
terraform-aws-s3-bucket|terraform-aws-modules/terraform-aws-s3-bucket|6c5e082b5d2fde77cb59c387a7f553dd2ed5da29|40|10|0
terraform-aws-security-group|terraform-aws-modules/terraform-aws-security-group|3cf4e1a48a4649179e8ea27308daf0b551cb0bfa|25|8|0
terraform-aws-control-tower|aws-ia/terraform-aws-control_tower_account_factory|22f754aca0aa572e8970dc1b81e40a27bc08d6bd|300|80|3'

EXPECTED_DETECTOR_COUNT=40

# Derive REPO_ROOT from the script's own location rather than `git
# rev-parse --show-toplevel` — the latter follows whatever symlink
# resolution the user's shell did, which can land on a symlink target
# that doesn't have `.venv`. The script lives at `scripts/`, so the
# repo root is one level up.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
EFTERLEV="${REPO_ROOT}/.venv/bin/efterlev"
if [ ! -x "$EFTERLEV" ]; then
  echo "error: ${EFTERLEV} not found. Run \`uv sync --extra dev\` first."
  exit 2
fi

WORKDIR="$(mktemp -d -t efterlev-dogfood-XXXXXX)"
trap 'rm -rf "$WORKDIR"' EXIT

# Run one target. Echoes a structured line on success or failure.
# Returns 0 if all thresholds are met, 1 otherwise.
run_target() {
  local name repo sha min_r min_e max_pf
  name="$1"; repo="$2"; sha="$3"; min_r="$4"; min_e="$5"; max_pf="$6"

  echo "===== ${name} (${repo}@${sha:0:8}) ====="

  local target_dir="${WORKDIR}/${name}"
  git clone --filter=blob:none --no-checkout "https://github.com/${repo}.git" "${target_dir}" >/dev/null 2>&1
  (
    cd "${target_dir}"
    git fetch --depth 1 origin "${sha}" >/dev/null 2>&1
    git checkout --detach "${sha}" >/dev/null 2>&1
  )

  (cd "${target_dir}" && "${EFTERLEV}" init >/dev/null 2>&1)
  local scan_output
  if ! scan_output="$(cd "${target_dir}" && "${EFTERLEV}" scan --target . 2>&1)"; then
    echo "  ✗ scan exited non-zero"
    echo "${scan_output}" | sed 's/^/    /'
    return 1
  fi

  local resources_parsed detectors_run evidence_records parse_failures
  resources_parsed="$(echo "${scan_output}" | sed -nE 's/.*resources parsed:[[:space:]]+([0-9]+).*/\1/p' | head -1)"
  detectors_run="$(echo "${scan_output}" | sed -nE 's/.*detectors run:[[:space:]]+([0-9]+).*/\1/p' | head -1)"
  evidence_records="$(echo "${scan_output}" | sed -nE 's/.*evidence records:[[:space:]]+([0-9]+).*/\1/p' | head -1)"
  parse_failures="$(echo "${scan_output}" | sed -nE 's/.*files skipped due to parse error:[[:space:]]+([0-9]+).*/\1/p' | head -1)"
  parse_failures="${parse_failures:-0}"

  echo "  resources_parsed=${resources_parsed} detectors_run=${detectors_run} evidence=${evidence_records} parse_failures=${parse_failures}"

  local fail=0
  if [ "${detectors_run}" != "${EXPECTED_DETECTOR_COUNT}" ]; then
    echo "  ✗ detectors_run=${detectors_run} (expected ${EXPECTED_DETECTOR_COUNT}) — registry regressed?"
    fail=1
  fi
  if [ "${resources_parsed}" -lt "${min_r}" ]; then
    echo "  ✗ resources_parsed=${resources_parsed} < floor ${min_r} — parser regressed?"
    fail=1
  fi
  if [ "${evidence_records}" -lt "${min_e}" ]; then
    echo "  ✗ evidence_records=${evidence_records} < floor ${min_e} — detector(s) went silent?"
    fail=1
  fi
  if [ "${parse_failures}" -gt "${max_pf}" ]; then
    echo "  ✗ parse_failures=${parse_failures} > cap ${max_pf} — new parser-failure mode introduced?"
    fail=1
  fi

  if [ $fail -eq 0 ]; then
    echo "  ✓ within thresholds"
    return 0
  fi
  return 1
}

OVERALL_FAIL=0
# Use a here-string so the loop runs in the parent shell — required for
# OVERALL_FAIL to propagate. (Piping into `while read` runs the loop in
# a subshell on bash 3.2, where assignments don't escape.)
while IFS='|' read -r name repo sha min_r min_e max_pf; do
  [ -z "$name" ] && continue
  case "$name" in \#*) continue ;; esac
  if ! run_target "$name" "$repo" "$sha" "$min_r" "$min_e" "$max_pf"; then
    OVERALL_FAIL=1
  fi
  echo
done <<< "$TARGETS_TSV"

if [ $OVERALL_FAIL -eq 0 ]; then
  echo "RESULT: all dogfood targets within thresholds."
else
  echo "RESULT: at least one threshold violation. Investigate above."
  exit 1
fi
