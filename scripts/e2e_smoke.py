"""End-to-end smoke harness — the full Efterlev CLI against a real Claude call.

This closes the one gap the unit-test suite cannot close: every test in
`tests/` uses `StubLLMClient`, so the production Opus prompts have never
been exercised in-development against the real API. That means prompt
quality on a 60-KSI Gap classification, fence-nonce respect under
adversarial-looking content, FRMR JSON shape under real model output, and
narrative grounding in evidence are ALL unmeasured until this script runs.

What it does:

  1. Lays down a synthetic Terraform fixture under a scratch workspace
     that exercises every registered detector (12 as of Phase 6-lite) plus
     one Evidence Manifest attestation for KSI-AFR-FSI (FedRAMP Security
     Inbox).
  2. Runs `efterlev init → scan → agent gap → agent document → agent
     remediate` as subprocess invocations via `uv run efterlev …`, so the
     whole Typer/CLI layer is exercised (not just Python-level primitives).
  3. Evaluates the outputs against a list of checks split into three
     severities: `critical` (fail the harness), `quality` (warn), and
     `info` (timings and counts, no bearing on exit code).
  4. Writes a dated results directory at `.e2e-results/<UTC-ISO-TS>/` with
     per-stage captured outputs, copied artifacts, a machine-readable
     `checks.json`, and a human-readable `summary.md`.

Contract:

  - Two backends supported, selected via `--llm-backend`:
    * `anthropic` (default) — requires `ANTHROPIC_API_KEY` in env.
    * `bedrock` — requires `EFTERLEV_BEDROCK_SMOKE=1` (opt-in gate),
      AWS credentials (`AWS_PROFILE` or `AWS_ACCESS_KEY_ID`), and a
      region (`--llm-region` or `AWS_REGION`). Implements SPEC-13.
  - When the configured backend's prerequisites are missing, the script
    exits with code 2 (skip — distinct from 0 for pass and 1 for critical
    fail) so CI can distinguish "not configured for live test" from "live
    test failed."
  - Exit 0 iff every critical check passed.
  - Never mutates the surrounding repo. The workspace lives entirely
    under `.e2e-results/<timestamp>[-<backend>-<region>]/workspace/`
    and is gitignored.

Pytest wrappers at `tests/test_e2e_smoke.py` (anthropic) and
`tests/test_e2e_smoke_bedrock.py` (bedrock) give `pytest -k e2e` as the
CI-shaped entry point; the script itself remains the primary interface
for interactive use and local debugging.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO_ROOT / ".e2e-results"

Severity = Literal["critical", "quality", "info"]


@dataclass(frozen=True)
class Check:
    stage: str
    name: str
    severity: Severity
    passed: bool
    detail: str


@dataclass
class StageResult:
    stage: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float


FIXTURE: dict[str, str] = {
    # Encrypted S3 bucket — should match encryption_s3_at_rest detector.
    "infra/s3_encrypted.tf": """\
resource "aws_s3_bucket" "reports" {
  bucket = "quarterly-reports"

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}
""",
    # Plain S3 bucket — should NOT match, exercising the negative path.
    "infra/s3_plain.tf": """\
resource "aws_s3_bucket" "public_assets" {
  bucket = "public-assets"
}
""",
    # TLS 1.2+ listener — should match tls_on_lb_listeners AND
    # fips_ssl_policies_on_lb_listeners.
    "infra/lb_tls.tf": """\
resource "aws_lb_listener" "https" {
  load_balancer_arn = "arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/x"
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = "arn:aws:acm:us-east-1:123:certificate/abc-123"

  default_action {
    type             = "forward"
    target_group_arn = "arn:aws:elasticloadbalancing:us-east-1:123:targetgroup/app/x"
  }
}
""",
    # Plain HTTP listener — should NOT match (gives the remediation step
    # something real to propose a diff for).
    "infra/lb_http.tf": """\
resource "aws_lb_listener" "http" {
  load_balancer_arn = "arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/x"
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = "arn:aws:elasticloadbalancing:us-east-1:123:targetgroup/app/x"
  }
}
""",
    # Multi-region CloudTrail with validation enabled — should match.
    "infra/cloudtrail.tf": """\
resource "aws_cloudtrail" "main" {
  name                          = "main-trail"
  s3_bucket_name                = "audit-logs-bucket"
  is_multi_region_trail         = true
  include_global_service_events = true
  enable_log_file_validation    = true

  event_selector {
    read_write_type           = "All"
    include_management_events = true
  }
}
""",
    # RDS with backup retention AND storage encryption — should match
    # backup_retention_configured and rds_encryption_at_rest.
    "infra/rds.tf": """\
resource "aws_db_instance" "primary" {
  identifier              = "app-primary"
  engine                  = "postgres"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  backup_retention_period = 14
  skip_final_snapshot     = false
  storage_encrypted       = true
  kms_key_id              = "arn:aws:kms:us-east-1:123:key/abc-123"
}
""",
    # IAM policy WITH MFA gate — heredoc-style literal JSON, per the
    # existing fixture convention. `jsonencode(...)` wrapping becomes
    # unparseable by python-hcl2's follow-through; a heredoc with literal
    # JSON is what the mfa_required_on_iam_policies detector expects.
    "infra/iam_mfa.tf": """\
resource "aws_iam_policy" "admin_with_mfa" {
  name = "admin-with-mfa"
  policy = <<-EOT
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": "*",
          "Resource": "*",
          "Condition": {
            "Bool": {"aws:MultiFactorAuthPresent": "true"}
          }
        }
      ]
    }
  EOT
}
""",
    # IAM policy WITHOUT MFA gate — also heredoc-style literal JSON.
    "infra/iam_no_mfa.tf": """\
resource "aws_iam_policy" "admin_no_mfa" {
  name = "admin-no-mfa"
  policy = <<-EOT
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": "*",
          "Resource": "*"
        }
      ]
    }
  EOT
}
""",
    # S3 public-access-block covering reports bucket — all four flags true.
    # Exercises aws.s3_public_access_block.
    "infra/s3_pab.tf": """\
resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}
""",
    # Symmetric KMS CMK with rotation enabled. Exercises aws.kms_key_rotation.
    "infra/kms.tf": """\
resource "aws_kms_key" "app_data" {
  description             = "Application-data encryption key"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}
""",
    # VPC flow log capturing ALL traffic to S3. Exercises
    # aws.vpc_flow_logs_enabled.
    "infra/flow_log.tf": """\
resource "aws_flow_log" "main" {
  vpc_id               = "vpc-0abc123"
  traffic_type         = "ALL"
  log_destination_type = "s3"
  log_destination      = "arn:aws:s3:::flow-logs-bucket"
}
""",
    # Account-level IAM password policy meeting the FedRAMP Moderate
    # baseline. Exercises aws.iam_password_policy.
    "infra/password_policy.tf": """\
resource "aws_iam_account_password_policy" "strict" {
  minimum_password_length      = 14
  require_uppercase_characters = true
  require_lowercase_characters = true
  require_numbers              = true
  require_symbols              = true
  max_password_age             = 60
  password_reuse_prevention    = 24
}
""",
    # Evidence Manifest for KSI-AFR-FSI (FedRAMP Security Inbox) — a
    # KSI with no Terraform-detectable surface, covered purely by a
    # human-signed procedural attestation. next_review is set well in
    # the future relative to today (2026-04-22) so the "staleness" axis
    # does not interfere with the quality checks.
    ".efterlev/manifests/security-inbox.yml": """\
ksi: KSI-AFR-FSI
name: FedRAMP Security Inbox
evidence:
  - type: attestation
    statement: >
      security@example.com is monitored by the SOC team 24/7. The inbox is
      configured in Google Workspace with a 15-minute acknowledgment SLA
      documented in runbooks/security-inbox.md, and auto-forwards
      high-severity reports to the on-call PagerDuty rotation. Incoming
      messages are triaged into our incident management system within the
      SLA window, and a weekly audit of acknowledgment timings is reviewed
      by the security lead.
    attested_by: vp-security@example.com
    attested_at: 2026-04-15
    reviewed_at: 2026-04-15
    next_review: 2026-10-15
    supporting_docs:
      - ./policies/security-inbox-sop.pdf
      - https://wiki.example.com/soc/security-inbox
""",
}

# KSI picked for `agent remediate` — one whose v0 detector can see a gap
# (the HTTP listener) so the agent has a real Terraform surface to
# propose a diff for. KSI-SVC-SNT (Securing Network Traffic) maps to the
# `tls_on_lb_listeners` detector.
REMEDIATE_KSI = "KSI-SVC-SNT"


# ----- helpers ----------------------------------------------------------


def _log(msg: str) -> None:
    """Print a progress line to stderr so stdout stays clean for piping."""
    print(f"[e2e-smoke] {msg}", file=sys.stderr, flush=True)


def _utc_timestamp() -> str:
    """`20260422T173012Z` — filesystem-safe UTC ISO-like timestamp."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _write_terraform_fixture(workspace: Path) -> None:
    """Lay down the Terraform fixture files under `workspace/`.

    Writes everything EXCEPT the manifest YAML. The manifest lives under
    `.efterlev/manifests/` which `efterlev init` refuses to overwrite, so
    the manifest is laid down *after* init via `_write_manifest_fixture`.
    This mirrors the real usage pattern: init scaffolds the workspace;
    the user then drops manifests into the carved-out directory.
    """
    for rel, content in FIXTURE.items():
        if rel.startswith(".efterlev/"):
            continue
        dest = workspace / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def _write_manifest_fixture(workspace: Path) -> None:
    """Lay down the Evidence Manifest YAML under `.efterlev/manifests/` post-init."""
    for rel, content in FIXTURE.items():
        if not rel.startswith(".efterlev/"):
            continue
        dest = workspace / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def _run_stage(
    stage: str,
    command: list[str],
    workspace: Path,
    outputs_dir: Path,
) -> StageResult:
    """Run one CLI invocation, capture stdio, persist, return the result."""
    _log(f"running {stage}: {' '.join(command)}")
    started = time.monotonic()
    # `command` is a list[str] constructed from in-script literals at the
    # call sites above (init_cmd + the static argv lists). No shell is
    # invoked (subprocess.run with a list argv does not use shell=True),
    # and no external/user/network input flows in. The semgrep audit rule
    # `python.lang.security.audit.dangerous-subprocess-use-audit` is
    # conservative; verified safe by construction here. Bare `# nosemgrep`
    # suppresses all rules on this line — registry-resolved rule_ids don't
    # match against short-form annotations, so naming the specific rule
    # in the suppression doesn't work in practice.
    proc = subprocess.run(  # nosemgrep
        command,
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    duration = time.monotonic() - started
    result = StageResult(
        stage=stage,
        command=command,
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_s=duration,
    )
    _persist_stage(result, outputs_dir)
    _log(f"  exit={proc.returncode} duration={duration:.1f}s")
    return result


def _persist_stage(result: StageResult, outputs_dir: Path) -> None:
    """Write captured stdio + exit metadata to outputs/<stage>.txt."""
    path = outputs_dir / f"{result.stage}.txt"
    body = (
        f"COMMAND: {' '.join(result.command)}\n"
        f"EXIT: {result.exit_code}\n"
        f"DURATION: {result.duration_s:.3f}s\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}\n"
    )
    path.write_text(body, encoding="utf-8")


# ----- checks -----------------------------------------------------------


def _check(
    stage: str,
    name: str,
    severity: Severity,
    passed: bool,
    detail: str,
) -> Check:
    return Check(stage=stage, name=name, severity=severity, passed=passed, detail=detail)


def _evaluate(
    stages: dict[str, StageResult],
    workspace: Path,
    artifacts_dir: Path,
) -> list[Check]:
    """Run every critical + quality + info check over the collected stage state."""
    checks: list[Check] = []

    # --- Exit codes (critical) -----------------------------------------
    exit_stages = (
        "01-init",
        "02-scan",
        "03-agent-gap",
        "04-agent-document",
        "05-agent-remediate",
    )
    for stage_key in exit_stages:
        result = stages[stage_key]
        checks.append(
            _check(
                stage=stage_key,
                name="exit_zero",
                severity="critical",
                passed=result.exit_code == 0,
                detail=f"exit code {result.exit_code}",
            )
        )

    # --- Scan produced both detector and manifest evidence (critical) --
    evidence_records = _load_evidence_from_store(workspace)
    detector_count = sum(1 for ev in evidence_records if ev["detector_id"] != "manifest")
    manifest_count = sum(1 for ev in evidence_records if ev["detector_id"] == "manifest")
    checks.append(
        _check(
            stage="02-scan",
            name="has_detector_evidence",
            severity="critical",
            passed=detector_count >= 1,
            detail=f"{detector_count} detector evidence record(s)",
        )
    )
    checks.append(
        _check(
            stage="02-scan",
            name="has_manifest_evidence",
            severity="critical",
            passed=manifest_count >= 1,
            detail=f"{manifest_count} manifest evidence record(s)",
        )
    )

    # --- Gap agent classifications (critical + quality) ----------------
    classifications = _load_classifications_from_store(workspace)
    checks.append(
        _check(
            stage="03-agent-gap",
            name="classifications_near_full",
            severity="critical",
            passed=len(classifications) >= 50,
            detail=f"{len(classifications)} classifications (expected ≥50 of 60)",
        )
    )

    known_evidence_ids = {ev["evidence_id"] for ev in evidence_records}
    fabricated: list[str] = []
    for clf in classifications:
        for eid in clf.get("evidence_ids", []):
            if eid not in known_evidence_ids:
                fabricated.append(eid)
    checks.append(
        _check(
            stage="03-agent-gap",
            name="no_fabricated_citations",
            severity="critical",
            passed=not fabricated,
            detail=(
                "every cited evidence_id resolves to a store record"
                if not fabricated
                else f"{len(fabricated)} fabricated citation(s), first: {fabricated[0]}"
            ),
        )
    )

    # "Differentiates" = the model is making distinctions between KSIs, not
    # classifying every one identically. We do NOT require `implemented` to
    # appear — from infra-only Terraform evidence, a cautious model correctly
    # refuses to call anything fully `implemented` (procedural / operational
    # layers remain unverified). That cautious posture is principle 1
    # "Evidence before claims" in CLAUDE.md, so penalizing it here would
    # pressure the model in exactly the direction the product commits NOT to
    # go. Two distinct statuses is the honest floor.
    statuses: set[str] = {str(clf["status"]) for clf in classifications if clf.get("status")}
    checks.append(
        _check(
            stage="03-agent-gap",
            name="differentiates",
            severity="critical",
            passed=len(statuses) >= 2,
            detail=f"observed {len(statuses)} distinct status(es): {sorted(statuses)}",
        )
    )

    # Quality: average rationale length.
    rationales = [clf.get("rationale", "") for clf in classifications]
    mean_len = sum(len(r) for r in rationales) / len(rationales) if rationales else 0.0
    checks.append(
        _check(
            stage="03-agent-gap",
            name="rationales_nontrivial",
            severity="quality",
            passed=mean_len > 80,
            detail=f"mean rationale length {mean_len:.0f} chars (threshold 80)",
        )
    )

    # --- Documentation attestation artifact (critical + quality) ------
    artifact_path = _find_attestation_json(workspace)
    artifact_json_text: str | None = None
    artifact_parsed: dict | None = None
    if artifact_path is None:
        checks.append(
            _check(
                stage="04-agent-document",
                name="artifact_valid",
                severity="critical",
                passed=False,
                detail="no attestation-*.json file produced under .efterlev/reports/",
            )
        )
        checks.append(
            _check(
                stage="04-agent-document",
                name="requires_review_true",
                severity="critical",
                passed=False,
                detail="no artifact to inspect",
            )
        )
        checks.append(
            _check(
                stage="04-agent-document",
                name="no_absolute_paths",
                severity="critical",
                passed=False,
                detail="no artifact to inspect",
            )
        )
    else:
        artifact_json_text = artifact_path.read_text(encoding="utf-8")
        try:
            from efterlev.models.attestation_artifact import AttestationArtifact

            artifact = AttestationArtifact.model_validate_json(artifact_json_text)
            artifact_parsed = artifact.model_dump(mode="json")
            checks.append(
                _check(
                    stage="04-agent-document",
                    name="artifact_valid",
                    severity="critical",
                    passed=True,
                    detail=f"{artifact.indicator_count} indicator(s) in artifact",
                )
            )
            checks.append(
                _check(
                    stage="04-agent-document",
                    name="requires_review_true",
                    severity="critical",
                    passed=artifact.provenance.requires_review is True,
                    detail=f"provenance.requires_review = {artifact.provenance.requires_review}",
                )
            )
        except Exception as exc:
            checks.append(
                _check(
                    stage="04-agent-document",
                    name="artifact_valid",
                    severity="critical",
                    passed=False,
                    detail=f"AttestationArtifact validation failed: {exc!s}",
                )
            )
            checks.append(
                _check(
                    stage="04-agent-document",
                    name="requires_review_true",
                    severity="critical",
                    passed=False,
                    detail="artifact could not be parsed",
                )
            )

        # Absolute-path leak check — repo-relative paths are the contract
        # after post-review fixup D (DECISIONS 2026-04-22). Grep the raw
        # JSON text for the workspace absolute path; it MUST NOT appear.
        workspace_abs = str(workspace.resolve())
        checks.append(
            _check(
                stage="04-agent-document",
                name="no_absolute_paths",
                severity="critical",
                passed=workspace_abs not in artifact_json_text,
                detail=(
                    "workspace absolute path absent from artifact"
                    if workspace_abs not in artifact_json_text
                    else f"workspace prefix {workspace_abs!r} appears in artifact JSON"
                ),
            )
        )

    # Quality: for implemented/partial classifications, narrative length
    # should be substantial on average (not placeholder).
    narratives: list[str] = []
    manifest_ksis = {ev["ksi"] for ev in evidence_records if ev["detector_id"] == "manifest"}
    manifest_ksi_narratives: list[str] = []
    if artifact_parsed is not None:
        for _theme_key, theme in (artifact_parsed.get("KSI") or {}).items():
            for ksi_id, indicator in (theme.get("indicators") or {}).items():
                if indicator.get("status") in ("implemented", "partial"):
                    nar = indicator.get("narrative") or ""
                    narratives.append(nar)
                if ksi_id in manifest_ksis:
                    manifest_ksi_narratives.append(indicator.get("narrative") or "")
    if narratives:
        substantial = sum(1 for n in narratives if len(n) > 200)
        frac = substantial / len(narratives)
    else:
        frac = 0.0
    checks.append(
        _check(
            stage="04-agent-document",
            name="narratives_substantial",
            severity="quality",
            passed=frac >= 0.5 if narratives else False,
            detail=(
                f"{frac * 100:.0f}% of {len(narratives)} impl/partial narratives >200 chars"
                if narratives
                else "no implemented/partial narratives produced"
            ),
        )
    )

    # Quality: for manifest-cited KSIs, narratives should mention the
    # attestor / SOC / role — grounding in the attestation content.
    attestor_keywords = ("vp-security@example.com", "SOC", "security lead")
    if manifest_ksi_narratives:
        grounded = sum(1 for n in manifest_ksi_narratives if any(k in n for k in attestor_keywords))
        manifest_grounded = grounded >= 1
        detail = (
            f"{grounded}/{len(manifest_ksi_narratives)} manifest-KSI narratives "
            f"mention attestor keyword(s)"
        )
    else:
        manifest_grounded = False
        detail = "no manifest-KSI narratives in artifact"
    checks.append(
        _check(
            stage="04-agent-document",
            name="manifest_attestation_mentions_attestor",
            severity="quality",
            passed=manifest_grounded,
            detail=detail,
        )
    )

    # Quality: documentation HTML renders the "attestation" badge when a
    # manifest-sourced citation is present.
    doc_html = _find_documentation_html(workspace)
    if doc_html is not None:
        html_text = doc_html.read_text(encoding="utf-8")
        has_badge = "source-manifest" in html_text and ">attestation<" in html_text
        checks.append(
            _check(
                stage="04-agent-document",
                name="html_has_attestation_badge",
                severity="quality",
                passed=has_badge,
                detail=(
                    "attestation badge present in documentation HTML"
                    if has_badge
                    else "attestation badge missing from documentation HTML"
                ),
            )
        )
    else:
        checks.append(
            _check(
                stage="04-agent-document",
                name="html_has_attestation_badge",
                severity="quality",
                passed=False,
                detail="no documentation-*.html file found",
            )
        )

    # --- Remediation (quality) -----------------------------------------
    remediate_stdout = stages["05-agent-remediate"].stdout
    short_circuited = (
        "No remediation needed" in remediate_stdout
        or "no Terraform surface to remediate" in remediate_stdout
    )
    diff_match = re.search(r"^[-+@]{2,3}", remediate_stdout, flags=re.MULTILINE)
    if short_circuited:
        detail = "short-circuited (implemented / NA / manifest-only) — diff shape N/A"
        passed = True
    else:
        passed = diff_match is not None
        detail = (
            "unified-diff marker present in stdout"
            if passed
            else "no unified-diff markers (---/+++/@@) in stdout"
        )
    checks.append(
        _check(
            stage="05-agent-remediate",
            name="diff_shape",
            severity="quality",
            passed=passed,
            detail=detail,
        )
    )

    # --- Info -----------------------------------------------------------
    for stage_key, result in stages.items():
        checks.append(
            _check(
                stage=stage_key,
                name="duration",
                severity="info",
                passed=True,
                detail=f"{result.duration_s:.2f}s",
            )
        )
    if artifact_parsed is not None:
        total_inds = sum(
            len(theme.get("indicators") or {})
            for theme in (artifact_parsed.get("KSI") or {}).values()
        )
        checks.append(
            _check(
                stage="04-agent-document",
                name="artifact_indicator_count",
                severity="info",
                passed=True,
                detail=f"{total_inds} indicator(s) in attestation artifact",
            )
        )

    # Copy artifacts into the results directory for convenience.
    _copy_artifacts(workspace, artifacts_dir)
    return checks


# ----- store-reading helpers ------------------------------------------


def _load_evidence_from_store(workspace: Path) -> list[dict]:
    """Read every Evidence record from the provenance store as plain dicts.

    Using the production `ProvenanceStore` reader rather than reaching
    into SQLite directly — the iteration API is the public surface and
    this script exercises it the same way the CLI does.
    """
    from efterlev.models import Evidence
    from efterlev.provenance import ProvenanceStore

    records: list[dict] = []
    with ProvenanceStore(workspace.resolve()) as store:
        for _rid, payload in store.iter_evidence():
            ev = Evidence.model_validate(payload)
            ksi = ev.ksis_evidenced[0] if ev.ksis_evidenced else None
            records.append(
                {
                    "evidence_id": ev.evidence_id,
                    "detector_id": ev.detector_id,
                    "ksi": ksi,
                    "ksis_evidenced": list(ev.ksis_evidenced),
                }
            )
    return records


def _load_classifications_from_store(workspace: Path) -> list[dict]:
    """Read every `ksi_classification` Claim from the provenance store."""
    from efterlev.agents import reconstruct_classifications_from_store
    from efterlev.provenance import ProvenanceStore

    with ProvenanceStore(workspace.resolve()) as store:
        rows = store.iter_claims_by_metadata_kind("ksi_classification")
        reconstructed = reconstruct_classifications_from_store(rows)
    return [
        {
            "ksi_id": clf.ksi_id,
            "status": clf.status,
            "rationale": clf.rationale,
            "evidence_ids": list(clf.evidence_ids),
        }
        for clf in reconstructed
    ]


def _find_attestation_json(workspace: Path) -> Path | None:
    reports = sorted((workspace / ".efterlev" / "reports").glob("attestation-*.json"))
    return reports[-1] if reports else None


def _find_documentation_html(workspace: Path) -> Path | None:
    reports = sorted((workspace / ".efterlev" / "reports").glob("documentation-*.html"))
    return reports[-1] if reports else None


def _copy_artifacts(workspace: Path, artifacts_dir: Path) -> None:
    """Mirror generated .html and .json reports into results/artifacts/."""
    reports = workspace / ".efterlev" / "reports"
    if not reports.is_dir():
        return
    for src in reports.iterdir():
        if src.is_file():
            shutil.copy2(src, artifacts_dir / src.name)


# ----- summary --------------------------------------------------------


def _write_reports(
    results_dir: Path,
    workspace: Path,
    checks: list[Check],
    stages: dict[str, StageResult],
) -> tuple[int, int]:
    """Write checks.json + summary.md. Return (critical_failed, quality_failed)."""
    critical = [c for c in checks if c.severity == "critical"]
    quality = [c for c in checks if c.severity == "quality"]
    info = [c for c in checks if c.severity == "info"]

    critical_passed = sum(1 for c in critical if c.passed)
    critical_failed = sum(1 for c in critical if not c.passed)
    quality_passed = sum(1 for c in quality if c.passed)
    quality_failed = sum(1 for c in quality if not c.passed)

    checks_payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "workspace": str(workspace.resolve()),
        "critical_passed": critical_passed,
        "critical_failed": critical_failed,
        "quality_passed": quality_passed,
        "quality_failed": quality_failed,
        "stages": {
            k: {"exit_code": v.exit_code, "duration_s": round(v.duration_s, 3)}
            for k, v in stages.items()
        },
        "checks": [asdict(c) for c in checks],
    }
    (results_dir / "checks.json").write_text(
        json.dumps(checks_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    overall = "PASS" if critical_failed == 0 else "FAIL"
    lines: list[str] = []
    lines.append(f"# Efterlev E2E smoke — {overall}")
    lines.append("")
    lines.append(f"- workspace: `{workspace.resolve()}`")
    lines.append(f"- timestamp: {datetime.now(UTC).isoformat()}")
    lines.append(f"- critical: {critical_passed}/{len(critical)} passed")
    lines.append(f"- quality:  {quality_passed}/{len(quality)} passed")
    lines.append("")
    lines.append("## Critical checks")
    lines.append("")
    for c in critical:
        mark = "PASS" if c.passed else "FAIL"
        lines.append(f"- **[{mark}]** `{c.stage}` / `{c.name}` — {c.detail}")
    lines.append("")
    lines.append("## Quality checks")
    lines.append("")
    for c in quality:
        mark = "PASS" if c.passed else "WARN"
        lines.append(f"- **[{mark}]** `{c.stage}` / `{c.name}` — {c.detail}")
    lines.append("")
    lines.append("## Info")
    lines.append("")
    for c in info:
        lines.append(f"- `{c.stage}` / `{c.name}` — {c.detail}")
    lines.append("")
    (results_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    return critical_failed, quality_failed


# ----- main -----------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args. Defaults preserve v0 anthropic-direct behavior."""
    parser = argparse.ArgumentParser(
        description="End-to-end Efterlev smoke harness against a real LLM backend."
    )
    parser.add_argument(
        "--llm-backend",
        choices=["anthropic", "bedrock"],
        default="anthropic",
        help="LLM backend (default: anthropic).",
    )
    parser.add_argument(
        "--llm-region",
        default=None,
        help=(
            "AWS region for the bedrock backend (e.g. 'us-gov-west-1'). "
            "Falls back to AWS_REGION env if unset. Required when --llm-backend=bedrock."
        ),
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help=(
            "LLM model ID. Defaults to 'claude-opus-4-7' (anthropic) or "
            "'us.anthropic.claude-opus-4-7-v1:0' (bedrock)."
        ),
    )
    return parser.parse_args(argv)


def _check_backend_env(backend: str, region: str | None) -> tuple[bool, int, str]:
    """Return (is-configured, exit-code-on-skip, skip-message).

    Each backend has a distinct "not configured for live test" condition.
    Skip semantics return exit 2 to distinguish "not configured" from
    "configured but failed" (exit 1).
    """
    if backend == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return (
                False,
                2,
                (
                    "ANTHROPIC_API_KEY is not set. This harness calls the real "
                    "Anthropic API end-to-end; skipping.\n"
                    "Set the key and re-run: `ANTHROPIC_API_KEY=sk-... uv run python "
                    "scripts/e2e_smoke.py`"
                ),
            )
        return True, 0, ""

    # backend == "bedrock"
    if os.environ.get("EFTERLEV_BEDROCK_SMOKE") != "1":
        return (
            False,
            2,
            (
                "EFTERLEV_BEDROCK_SMOKE is not set to '1'. This is the explicit "
                "opt-in for live AWS Bedrock smoke runs; skipping.\n"
                "Set EFTERLEV_BEDROCK_SMOKE=1 + AWS_PROFILE (or AWS_ACCESS_KEY_ID) "
                "and re-run."
            ),
        )
    has_creds = bool(os.environ.get("AWS_PROFILE") or os.environ.get("AWS_ACCESS_KEY_ID"))
    if not has_creds:
        return (
            False,
            2,
            (
                "EFTERLEV_BEDROCK_SMOKE=1 set but no AWS credentials available "
                "(neither AWS_PROFILE nor AWS_ACCESS_KEY_ID is set); skipping."
            ),
        )
    if not region and not os.environ.get("AWS_REGION"):
        return (
            False,
            2,
            ("Bedrock smoke needs a region — pass --llm-region or set AWS_REGION; skipping."),
        )
    return True, 0, ""


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    is_configured, skip_code, skip_msg = _check_backend_env(args.llm_backend, args.llm_region)
    if not is_configured:
        print(skip_msg, file=sys.stderr)
        return skip_code

    region = args.llm_region or os.environ.get("AWS_REGION")
    default_model = (
        "us.anthropic.claude-opus-4-7-v1:0" if args.llm_backend == "bedrock" else "claude-opus-4-7"
    )
    model = args.llm_model or default_model

    timestamp = _utc_timestamp()
    # Suffix non-anthropic runs so multiple backends can land artifacts
    # without overwriting each other when run in quick succession.
    suffix = "" if args.llm_backend == "anthropic" else f"-{args.llm_backend}"
    if args.llm_backend == "bedrock" and region:
        suffix = f"{suffix}-{region}"
    results_dir = RESULTS_ROOT / f"{timestamp}{suffix}"
    workspace = results_dir / "workspace"
    outputs_dir = results_dir / "outputs"
    artifacts_dir = results_dir / "artifacts"
    for d in (workspace, outputs_dir, artifacts_dir):
        d.mkdir(parents=True, exist_ok=True)

    _log(f"results directory: {results_dir}")
    _log(f"backend: {args.llm_backend}, region: {region or '(n/a)'}, model: {model}")
    _log("laying down Terraform fixture")
    _write_terraform_fixture(workspace)

    # Build the init command with the right backend wiring. All
    # subsequent agent stages read the resulting `.efterlev/config.toml`
    # via the LLM factory's workspace-walking dispatch (SPEC-10), so the
    # agents themselves don't need backend-specific flags.
    init_cmd = [
        "uv",
        "run",
        "efterlev",
        "init",
        "--target",
        ".",
        "--baseline",
        "fedramp-20x-moderate",
        "--llm-backend",
        args.llm_backend,
        "--llm-model",
        model,
    ]
    if args.llm_backend == "bedrock":
        assert region is not None  # _check_backend_env guarantees this
        init_cmd.extend(["--llm-region", region])

    # Each stage shells out to `uv run efterlev …` so we exercise the
    # exact CLI an operator would invoke. cwd = workspace so Typer's
    # `--target .` resolves correctly.
    stages: dict[str, StageResult] = {}
    stages["01-init"] = _run_stage("01-init", init_cmd, workspace, outputs_dir)
    if stages["01-init"].exit_code != 0:
        _log("init failed; evaluating remaining stages as not-run and reporting")

    # Manifests live under `.efterlev/manifests/` which `init` refuses to
    # clobber — so we write them AFTER init, mirroring the real usage
    # pattern (init scaffolds the workspace; the user then drops manifests
    # into the carved-out directory).
    _log("laying down Evidence Manifest fixture")
    _write_manifest_fixture(workspace)

    stages["02-scan"] = _run_stage(
        "02-scan",
        ["uv", "run", "efterlev", "scan", "--target", "."],
        workspace,
        outputs_dir,
    )
    stages["03-agent-gap"] = _run_stage(
        "03-agent-gap",
        ["uv", "run", "efterlev", "agent", "gap", "--target", "."],
        workspace,
        outputs_dir,
    )
    stages["04-agent-document"] = _run_stage(
        "04-agent-document",
        ["uv", "run", "efterlev", "agent", "document", "--target", "."],
        workspace,
        outputs_dir,
    )
    stages["05-agent-remediate"] = _run_stage(
        "05-agent-remediate",
        [
            "uv",
            "run",
            "efterlev",
            "agent",
            "remediate",
            "--ksi",
            REMEDIATE_KSI,
            "--target",
            ".",
        ],
        workspace,
        outputs_dir,
    )

    _log("evaluating checks")
    checks = _evaluate(stages, workspace, artifacts_dir)
    critical_failed, quality_failed = _write_reports(results_dir, workspace, checks, stages)

    _log(f"done: critical_failed={critical_failed} quality_failed={quality_failed} → {results_dir}")
    return 0 if critical_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
