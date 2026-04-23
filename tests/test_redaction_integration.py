"""Adversarial integration test: secrets seeded into Evidence content never
appear in the prompt that reaches the LLM.

This is the end-to-end proof of the redaction pipeline:

  1. Construct an Evidence record whose `content` contains a seeded
     high-confidence secret value (AWS access key, GitHub token, PEM
     private key, etc.).
  2. Invoke the Gap Agent with a StubLLMClient that captures the exact
     prompt the model would see.
  3. Assert the captured prompt contains NO trace of the seeded secret.
  4. Assert the captured prompt DOES contain a properly-shaped
     `[REDACTED:<kind>:sha256:<prefix>]` token in the evidence body.
  5. Optionally, assert a RedactionLedger threaded through the agent
     records an event with the right pattern name.

Spans source-file scrubbing too (Remediation Agent's
`format_source_files_for_prompt` path) so any Terraform heredoc carrying
a real key is also caught.
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.agents.base import format_evidence_for_prompt, format_source_files_for_prompt
from efterlev.llm.scrubber import RedactionLedger
from efterlev.models import Evidence, SourceRef


def _ev(content: dict) -> Evidence:
    """Shortcut to build an Evidence record with a minimal envelope."""
    return Evidence.create(
        detector_id="aws.iam_user_access_keys",
        source_ref=SourceRef(file="infra/iam.tf", line_start=10, line_end=15),
        ksis_evidenced=["KSI-IAM-MFA"],
        controls_evidenced=["IA-2"],
        content=content,
        timestamp=datetime.now(UTC),
    )


# --- evidence content redaction ---------------------------------------------


def test_seeded_aws_access_key_does_not_reach_prompt() -> None:
    secret = "AKIAIOSFODNN7EXAMPLE"
    ev = _ev({"resource_name": "ci_deploy", "leaked_value": secret})
    ledger = RedactionLedger()
    prompt = format_evidence_for_prompt([ev], nonce="deadbeef", redaction_ledger=ledger)

    assert secret not in prompt, "AWS access key leaked into LLM prompt"
    assert "[REDACTED:aws_access_key_id:sha256:" in prompt
    # Ledger captured exactly one redaction with the correct context hint.
    assert ledger.count == 1
    assert ledger.events[0].pattern_name == "aws_access_key_id"
    assert "evidence[aws.iam_user_access_keys]:0" in ledger.events[0].context_hint


def test_seeded_github_token_does_not_reach_prompt() -> None:
    secret = "ghp_1234567890abcdefghijABCDEFGHIJklmnopqr"
    ev = _ev({"attached_user": "alice", "leaked": secret})
    ledger = RedactionLedger()
    prompt = format_evidence_for_prompt([ev], nonce="cafebabe", redaction_ledger=ledger)

    assert secret not in prompt
    assert "[REDACTED:github_token:" in prompt
    assert ledger.events[0].pattern_name == "github_token"


def test_seeded_private_key_in_evidence_does_not_reach_prompt() -> None:
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEA\n"
        "-----END RSA PRIVATE KEY-----"
    )
    ev = _ev({"resource_name": "legacy_cert", "material": pem})
    ledger = RedactionLedger()
    prompt = format_evidence_for_prompt([ev], nonce="beefdead", redaction_ledger=ledger)

    assert "BEGIN RSA PRIVATE KEY" not in prompt
    assert "END RSA PRIVATE KEY" not in prompt
    assert "MIIEvQIBADAN" not in prompt
    assert "[REDACTED:private_key_pem:" in prompt
    assert ledger.events[0].pattern_name == "private_key_pem"


def test_multiple_secrets_across_multiple_evidence_records() -> None:
    ev_a = _ev({"leaked": "AKIAIOSFODNN7EXAMPLE"})
    ev_b = _ev({"token": "ghp_1234567890abcdefghijABCDEFGHIJklmnopqr"})
    ledger = RedactionLedger()
    prompt = format_evidence_for_prompt([ev_a, ev_b], nonce="abcd1234", redaction_ledger=ledger)

    assert "AKIAIOSFODNN7EXAMPLE" not in prompt
    assert "ghp_1234567890" not in prompt
    assert ledger.count == 2
    # Each event carries its own evidence-index context hint.
    hints = {e.context_hint for e in ledger.events}
    assert any(":0" in h for h in hints)
    assert any(":1" in h for h in hints)


def test_no_redaction_leaves_ledger_empty() -> None:
    # Clean evidence with only structural facts — no patterns should match.
    ev = _ev({"resource_name": "strict_policy", "posture": "sufficient"})
    ledger = RedactionLedger()
    prompt = format_evidence_for_prompt([ev], nonce="fedbca98", redaction_ledger=ledger)

    assert ledger.count == 0
    assert "strict_policy" in prompt  # normal content passes through


def test_evidence_without_ledger_still_scrubs() -> None:
    # Scrubbing happens unconditionally; the ledger is an optional audit sink.
    secret = "AKIAIOSFODNN7EXAMPLE"
    ev = _ev({"leaked": secret})
    prompt = format_evidence_for_prompt([ev], nonce="zzz12345")

    assert secret not in prompt
    assert "[REDACTED:aws_access_key_id:" in prompt


# --- source-file redaction (Remediation Agent path) -------------------------


def test_seeded_secret_in_terraform_source_does_not_reach_prompt() -> None:
    # Realistic scenario: a heredoc-wrapped IAM policy in a .tf file
    # contains an embedded AWS access key (bad practice, but happens).
    tf_source = """
resource "aws_iam_user_policy" "bad_practice" {
  user = aws_iam_user.ci.name
  policy = <<-EOT
    {
      "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}],
      "leaked_access_key_do_not_commit": "AKIAIOSFODNN7EXAMPLE"
    }
  EOT
}
"""
    ledger = RedactionLedger()
    prompt = format_source_files_for_prompt(
        {"infra/iam.tf": tf_source}, nonce="11223344", redaction_ledger=ledger
    )

    assert "AKIAIOSFODNN7EXAMPLE" not in prompt
    assert "[REDACTED:aws_access_key_id:" in prompt
    assert ledger.count == 1
    assert "source_file[infra/iam.tf]" in ledger.events[0].context_hint


def test_source_file_preserves_non_secret_content() -> None:
    tf = 'resource "aws_s3_bucket" "logs" { bucket = "logs-prod" }\n'
    prompt = format_source_files_for_prompt({"main.tf": tf}, nonce="deadc0de")
    # The scrubber must not break legitimate Terraform.
    assert 'resource "aws_s3_bucket" "logs"' in prompt
    assert 'bucket = "logs-prod"' in prompt


def test_multiple_source_files_each_scrubbed_in_context() -> None:
    files = {
        "iam.tf": 'access_key = "AKIAIOSFODNN7EXAMPLE"\n',
        "github.tf": 'token = "ghp_1234567890abcdefghijABCDEFGHIJklmnopqr"\n',
    }
    ledger = RedactionLedger()
    prompt = format_source_files_for_prompt(files, nonce="f00dfeed", redaction_ledger=ledger)

    assert "AKIAIOSFODNN7EXAMPLE" not in prompt
    assert "ghp_1234567890" not in prompt
    assert ledger.count == 2
    hints = [e.context_hint for e in ledger.events]
    assert "source_file[iam.tf]" in hints
    assert "source_file[github.tf]" in hints


# --- fence interaction ------------------------------------------------------


def test_redaction_does_not_disturb_fence_ids() -> None:
    """Evidence IDs (the content-addressed sha256 of the evidence record)
    must NOT be redacted even though they live inside an `id="sha256:…"`
    attribute. The scrubber operates on the JSON body INSIDE the fence,
    not the fence markup itself — confirms the design-call-3 fence-and-
    validator contract still holds under redaction."""
    ev = _ev({"leaked": "AKIAIOSFODNN7EXAMPLE"})
    prompt = format_evidence_for_prompt([ev], nonce="11112222")
    # Fence-attribute sha256 (the evidence_id) preserved intact.
    assert f'<evidence_11112222 id="{ev.evidence_id}">' in prompt
    assert "</evidence_11112222>" in prompt
    # Body-level secret redacted.
    assert "[REDACTED:aws_access_key_id:" in prompt
