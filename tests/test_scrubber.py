"""Tests for the LLM-prompt secret redaction pass (`efterlev.llm.scrubber`).

Every pattern in `PATTERNS` gets at least one should-redact test and one
false-positive test (something that LOOKS like the secret but isn't).
The false-positive tests are as important as the positive ones — an
over-aggressive regex that redacts legitimate infrastructure references
(ARNs, resource names) cripples the LLM's ability to reason about the
evidence.

See DECISIONS 2026-04-23 "Secret redaction implementation" for the full
design.
"""

from __future__ import annotations

import json

from efterlev.llm.scrubber import (
    PATTERNS,
    RedactionLedger,
    scrub_llm_prompt,
)

# --- pattern-by-pattern coverage --------------------------------------------


def test_aws_access_key_id_iam_akia_redacted() -> None:
    text = 'the key is AKIAIOSFODNN7EXAMPLE and should go away'
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "[REDACTED:aws_access_key_id:sha256:" in scrubbed
    assert len(events) == 1
    assert events[0].pattern_name == "aws_access_key_id"


def test_aws_access_key_id_sts_asia_redacted() -> None:
    text = "ASIAY34FZKBOKMUTVV7A"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert "ASIAY34FZKBOKMUTVV7A" not in scrubbed
    assert len(events) == 1


def test_aws_arn_account_id_not_a_false_positive() -> None:
    # ARNs embed 12-digit account IDs but do NOT start with AKIA/ASIA.
    # An over-aggressive regex would match the account-id digits; ours
    # does not.
    text = "arn:aws:iam::123456789012:role/app_task"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert scrubbed == text
    assert events == []


def test_gcp_api_key_redacted() -> None:
    # AIza prefix (4) + body exactly 35 chars = 39 total.
    key = "AIzaSyDEXAMPLEKEYEXAMPLE12345abcdefghij"
    assert len(key) == 39
    text = f"GCP key: {key} in config"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert key not in scrubbed
    assert len(events) == 1
    assert events[0].pattern_name == "gcp_api_key"


def test_github_token_personal_redacted() -> None:
    # ghp_ prefix + 36-char body
    text = "token = ghp_1234567890abcdefghijABCDEFGHIJklmnopqr"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert "ghp_1234567890abcdefghijABCDEFGHIJklmnopqr" not in scrubbed
    assert len(events) == 1
    assert events[0].pattern_name == "github_token"


def test_github_token_server_to_server_redacted() -> None:
    # ghs_ is the server-token prefix; body can be longer than 36.
    text = "ghs_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert events and events[0].pattern_name == "github_token"
    assert "ghs_" not in scrubbed or "[REDACTED" in scrubbed


def test_slack_bot_token_redacted() -> None:
    text = "slack xoxb-12345678901-1234567890123-abcd1234EFGH5678ijkl9012"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert "xoxb-12345678901" not in scrubbed
    assert events and events[0].pattern_name == "slack_token"


def test_stripe_live_key_redacted() -> None:
    text = "stripe = sk_live_abcdefghijklmnopqrstuvwx"  # 24-char body
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert "sk_live_abcdefghijklmnopqrstuvwx" not in scrubbed
    assert events and events[0].pattern_name == "stripe_api_key"


def test_stripe_test_key_redacted() -> None:
    text = "sk_test_ABC1234567890XYZ1234567890"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert "sk_test_ABC1234567890XYZ1234567890" not in scrubbed
    assert events and events[0].pattern_name == "stripe_api_key"


def test_private_key_pem_redacted() -> None:
    pem = (
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ...truncated...\n"
        "-----END PRIVATE KEY-----"
    )
    text = f"key content:\n{pem}\nend of key"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    # Header/footer gone; replacement token present once (single block).
    assert "BEGIN PRIVATE KEY" not in scrubbed
    assert "END PRIVATE KEY" not in scrubbed
    assert "[REDACTED:private_key_pem:sha256:" in scrubbed
    assert len(events) == 1


def test_multiple_pem_blocks_each_redacted_separately() -> None:
    # Two distinct PEM bodies — the regex's non-greedy body match should
    # NOT collapse them into one redaction.
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "ABCDEF\n"
        "-----END RSA PRIVATE KEY-----\n"
        "some text between\n"
        "-----BEGIN EC PRIVATE KEY-----\n"
        "GHIJKL\n"
        "-----END EC PRIVATE KEY-----"
    )
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert "some text between" in scrubbed  # non-secret context preserved
    assert len(events) == 2


def test_jwt_redacted() -> None:
    # Three base64url segments separated by dots; each segment >= 10 chars.
    jwt = (
        "eyJhbGciOiJIUzI1NiJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    scrubbed, events = scrub_llm_prompt(f"authorization: {jwt}", context_hint="test")
    assert jwt not in scrubbed
    assert events and events[0].pattern_name == "jwt_token"


# --- false-positive guards --------------------------------------------------


def test_ordinary_base64_not_misclassified_as_aws_key() -> None:
    # 20-char base64-alphabet strings are common (short hashes, IDs)
    # and don't start with AKIA/ASIA.
    text = "fingerprint: abc123def456ghi789jk"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert scrubbed == text
    assert events == []


def test_short_dot_tuple_not_misclassified_as_jwt() -> None:
    # Three dot-separated identifiers but each segment < 10 chars.
    text = "route: a.b.c"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert scrubbed == text
    assert events == []


def test_kms_arn_not_misclassified() -> None:
    # KMS ARNs are long and contain base62-looking segments; the
    # scrubber must not redact them or the model loses its ability to
    # reason about key references.
    text = "arn:aws:kms:us-east-1:123456789012:key/abc-123-def-456"
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert scrubbed == text
    assert events == []


# --- multi-pattern within the same string -----------------------------------


def test_multiple_distinct_secrets_each_redacted() -> None:
    text = (
        "AWS key AKIAIOSFODNN7EXAMPLE and "
        "GitHub token ghp_1234567890abcdefghijABCDEFGHIJklmnopqr "
        "should both go"
    )
    scrubbed, events = scrub_llm_prompt(text, context_hint="test")
    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "ghp_1234567890" not in scrubbed
    assert len(events) == 2
    names = {e.pattern_name for e in events}
    assert names == {"aws_access_key_id", "github_token"}


def test_redaction_token_preserves_kind_for_model_reasoning() -> None:
    # The model sees `[REDACTED:aws_access_key_id:sha256:…]` not
    # `[REDACTED]` — preserves structural information so downstream
    # reasoning can still identify the type of value.
    text = "AKIAIOSFODNN7EXAMPLE"
    scrubbed, _ = scrub_llm_prompt(text, context_hint="test")
    assert scrubbed.startswith("[REDACTED:aws_access_key_id:sha256:")
    assert scrubbed.endswith("]")


def test_sha256_prefix_is_deterministic_per_value() -> None:
    # Same secret twice → same 8-char prefix. Different secrets → different
    # prefixes. Property matters for the audit log ("this value was seen
    # twice" vs "these are two different secrets").
    a, ev_a = scrub_llm_prompt("AKIAIOSFODNN7EXAMPLE", context_hint="x")
    b, ev_b = scrub_llm_prompt("AKIAIOSFODNN7EXAMPLE", context_hint="x")
    assert a == b
    assert ev_a[0].sha256_prefix == ev_b[0].sha256_prefix

    _, ev_c = scrub_llm_prompt("AKIA0000000000000000", context_hint="x")
    assert ev_c[0].sha256_prefix != ev_a[0].sha256_prefix


# --- RedactionLedger --------------------------------------------------------


def test_redaction_ledger_serializes_as_jsonl() -> None:
    ledger = RedactionLedger()
    _, events = scrub_llm_prompt("AKIAIOSFODNN7EXAMPLE", context_hint="evidence[X]:0")
    ledger.extend(events)
    jsonl = ledger.as_jsonl(scan_id="scan-20260423-abc")
    lines = [line for line in jsonl.splitlines() if line]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["scan_id"] == "scan-20260423-abc"
    assert record["pattern_name"] == "aws_access_key_id"
    assert record["context_hint"] == "evidence[X]:0"
    assert "timestamp" in record
    # Most importantly, the record contains ONLY the 8-char prefix,
    # never the original secret.
    assert "AKIA" not in jsonl


def test_redaction_ledger_counts_by_pattern() -> None:
    ledger = RedactionLedger()
    for text in (
        "AKIAIOSFODNN7EXAMPLE",
        "AKIAI44QH8DHBEXAMPLE",
        "ghp_1234567890abcdefghijABCDEFGHIJklmnopqr",
    ):
        _, events = scrub_llm_prompt(text, context_hint="x")
        ledger.extend(events)
    assert ledger.pattern_counts() == {
        "aws_access_key_id": 2,
        "github_token": 1,
    }
    assert ledger.count == 3


def test_redaction_ledger_empty_as_jsonl_is_empty_string() -> None:
    ledger = RedactionLedger()
    assert ledger.as_jsonl(scan_id="empty") == ""


# --- PATTERNS integrity -----------------------------------------------------


def test_pattern_names_unique() -> None:
    # Duplicate names would produce ambiguous audit records.
    names = [p.name for p in PATTERNS]
    assert len(names) == len(set(names))


def test_pattern_names_are_lowercase_underscore_shape() -> None:
    # Convention check: names appear in the redaction token and should
    # be readable. Avoid spaces, dashes, uppercase.
    import re as _re

    for p in PATTERNS:
        assert _re.match(r"^[a-z][a-z0-9_]*$", p.name), f"bad pattern name: {p.name!r}"
