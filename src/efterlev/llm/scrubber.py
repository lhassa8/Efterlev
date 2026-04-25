"""Secret-redaction pass between Evidence and the LLM prompt.

Lives in `efterlev.llm` because the one thing this module does is protect
what gets transmitted to the LLM provider. Runs as the last step inside
`format_evidence_for_prompt` and `format_source_files_for_prompt` in
`agents.base`, so every prompt that flows through an agent is scrubbed.

## Design

A fixed library of high-confidence regex patterns, each with provenance
(where the pattern came from, what it catches, what it doesn't). Every
match is replaced with a structural token of the form
`[REDACTED:<kind>:sha256:<8hex>]` — kind lets the LLM still reason about
the shape of the field ("this value is a GitHub token") without the
value itself; the short sha256 prefix lets a reviewer cross-reference a
redaction event in the audit log back to a specific match.

Hashes use the full SHA-256 of the matched string and expose only the
first 8 hex characters. 32 bits of entropy is enough to distinguish
redactions within a single scan but not enough to attempt a preimage
recovery. The original secret is never written to disk, logged, or
transmitted past the scrubber.

## Scope

- **Does** catch structural secrets with self-identifying prefixes or
  shapes: AWS access key IDs (`AKIA…`/`ASIA…`), GCP API keys
  (`AIza…`), GitHub tokens (`ghp_…`/`gho_…`/etc.), Slack tokens
  (`xox[bpas]-…`), Stripe keys (`sk_(live|test)_…`), PEM-formatted
  private keys, JWT-shaped three-dot base64 tuples.
- **Does NOT** catch everything. High-entropy strings adjacent to
  secret-ish keys (passwords, generic API secrets without known
  prefixes) require context-aware detection beyond this pass. A
  production compliance pipeline should run `trufflehog` or `gitleaks`
  upstream as the primary secret-scanning defense; this scrubber is
  a defense-in-depth layer for what happens to reach the LLM prompt.
- **Does NOT** redact content values the LLM legitimately needs to
  reason about: resource names, AWS account IDs in ARNs (low-confidence
  secret shape, high false-positive rate on legitimate infra
  references), KMS ARNs, regions, etc.

## Failure mode

If any regex throws (which shouldn't happen with well-formed patterns)
the caller raises — fail-closed. A bug in the scrubber must NEVER
result in unscrubbed content flowing to the LLM.

See `THREAT_MODEL.md` "Secrets handling" for the full trust-posture
discussion and DECISIONS 2026-04-23 "Secret redaction implementation"
for the design record.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from re import Pattern
from typing import Any


@dataclass(frozen=True)
class RedactionEvent:
    """One redaction — audit record. Content hint names the context, never the secret."""

    timestamp: datetime
    pattern_name: str
    sha256_prefix: str  # first 8 hex chars of the matched value
    context_hint: str  # e.g. "evidence[aws.iam_user_access_keys]:0" — NEVER the secret


@dataclass(frozen=True)
class _Pattern:
    """One named pattern with provenance.

    `name` shows up in the redaction token kind ("aws_access_key") and the
    audit log. `regex` is the compiled matcher. `description` names what
    the pattern catches and what it doesn't.
    """

    name: str
    regex: Pattern[str]
    description: str


def _p(name: str, pattern: str, description: str, *, flags: int = 0) -> _Pattern:
    """Compile a named pattern. Keeps PATTERNS table below flat and readable.

    `flags` defaults to zero; pass `re.DOTALL` for multi-line bodies like
    PEM private keys whose body contains newlines.
    """
    return _Pattern(name=name, regex=re.compile(pattern, flags), description=description)


# Pattern library. Ordered most-specific first so a value matching multiple
# rules (rare but possible — e.g. a PEM body containing a base64-looking
# AWS-key-shaped substring) gets classified by the more specific one.
#
# Provenance is in the docstring for each pattern so a reviewer can audit
# why we trust the regex. Every regex here matches self-identifying
# shapes, not general "high-entropy string" heuristics.
PATTERNS: tuple[_Pattern, ...] = (
    # PEM-encoded private keys. Matches the header only; the body is
    # redacted by the surrounding replacement. Covers RSA, DSA, EC,
    # OPENSSH, PGP, and generic "PRIVATE KEY" forms.
    # Provenance: PEM RFC 7468 (2015) defines the -----BEGIN … PRIVATE
    # KEY----- header format.
    _p(
        name="private_key_pem",
        # Match from header through footer (DOTALL so . matches newlines).
        # Non-greedy body so adjacent PEM blocks don't get collapsed.
        pattern=(
            r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY-----"
            r".*?"
            r"-----END (?:RSA |DSA |EC |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY-----"
        ),
        description="PEM-formatted private key (RSA/DSA/EC/OPENSSH/PGP/generic).",
        flags=re.DOTALL,
    ),
    # AWS access key IDs. AKIA = long-lived IAM user keys; ASIA =
    # temporary STS credentials. Format: prefix + 16 uppercase-alphanumeric.
    # Provenance: AWS IAM docs on Access Key ID format.
    _p(
        name="aws_access_key_id",
        pattern=r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
        description="AWS access key ID (IAM user: AKIA*, STS session: ASIA*).",
    ),
    # GCP API keys. Fixed 4-char prefix + 35-char body.
    # Provenance: Google Cloud documentation for API-key format.
    _p(
        name="gcp_api_key",
        pattern=r"\bAIza[0-9A-Za-z_\-]{35}\b",
        description="Google Cloud Platform API key.",
    ),
    # GitHub personal / OAuth / server / user-to-server / refresh tokens.
    # Provenance: GitHub Docs "About authentication with GITHUB_TOKEN",
    # 2024. Five distinct shapes share the `gh[posur]_` prefix; body is
    # 36 alphanumeric for personal, up to ~80 for server tokens.
    _p(
        name="github_token",
        pattern=r"\bgh[posur]_[A-Za-z0-9]{36,255}\b",
        description="GitHub token (personal, OAuth, server, user, or refresh).",
    ),
    # Slack tokens. Bot, user, app-level, and admin all share `xox[bpas]-`.
    # Provenance: Slack API docs on token format. Body is variable-length
    # dash-separated segments of digits/hex.
    _p(
        name="slack_token",
        pattern=r"\bxox[bpas]-[0-9]+-[0-9]+(?:-[A-Za-z0-9]+)+\b",
        description="Slack token (bot/user/app/admin; all share xox[bpas]- prefix).",
    ),
    # Stripe API keys. `sk_live_` for production, `sk_test_` for test.
    # Body is ≥24 base62 characters.
    # Provenance: Stripe API keys documentation.
    _p(
        name="stripe_api_key",
        pattern=r"\bsk_(?:live|test)_[0-9a-zA-Z]{24,}\b",
        description="Stripe secret API key (live or test).",
    ),
    # JWT-shaped three-part base64url tokens. Body lengths >= 10 chars
    # each to avoid matching short accidental dot-triples. This matches
    # ANY JWT-shaped string, not only sensitive ones — but since a JWT
    # embeds claims and a signature, treating them all as redaction-
    # worthy is the conservative default. False positives (e.g. a
    # public-key-like blob that happens to match) are acceptable.
    # Provenance: RFC 7519 JWT format.
    _p(
        name="jwt_token",
        pattern=r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b",
        description="JWT-shaped three-segment base64url token.",
    ),
)


def _sha256_prefix(value: str) -> str:
    """First 8 hex chars of the full SHA-256 of `value`. Uses the full hash
    internally (so partial-hash collisions don't reduce overall hash quality)
    and exposes only the prefix to audit records. 32 bits of entropy —
    enough to distinguish redactions within a scan, not enough to enable
    preimage recovery."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def scrub_llm_prompt(
    text: str,
    *,
    context_hint: str = "prompt",
) -> tuple[str, list[RedactionEvent]]:
    """Replace every pattern match in `text` with a structural REDACTED token.

    Returns the scrubbed text plus a list of `RedactionEvent` records for
    audit. The events carry no secret material: only the pattern name, an
    8-hex-char sha256 prefix, and the caller-supplied `context_hint` that
    identifies WHERE in the prompt the redaction happened (e.g.
    "evidence[aws.iam_user_access_keys]:0", "source_file[main.tf]").

    Fail-closed: any regex error raises.
    """
    events: list[RedactionEvent] = []
    now = datetime.now(UTC)

    def _replace_factory(pattern_name: str):
        def _replace(match: re.Match[str]) -> str:
            value = match.group(0)
            prefix = _sha256_prefix(value)
            events.append(
                RedactionEvent(
                    timestamp=now,
                    pattern_name=pattern_name,
                    sha256_prefix=prefix,
                    context_hint=context_hint,
                )
            )
            return f"[REDACTED:{pattern_name}:sha256:{prefix}]"

        return _replace

    scrubbed = text
    for pattern in PATTERNS:
        scrubbed = pattern.regex.sub(_replace_factory(pattern.name), scrubbed)

    return scrubbed, events


@dataclass
class RedactionLedger:
    """Append-only collection of redaction events across an agent run.

    The caller (usually the scan or agent CLI wrapper) constructs one
    ledger per run, threads it through `format_*_for_prompt` via the
    `scrub_llm_prompt` helper, and at end-of-run writes it to the audit
    log under `.efterlev/redacted.log` with 0600 permissions.
    """

    events: list[RedactionEvent] = field(default_factory=list)

    def extend(self, new_events: list[RedactionEvent]) -> None:
        self.events.extend(new_events)

    def as_jsonl(self, *, scan_id: str) -> str:
        """Serialize events as newline-delimited JSON for the audit log."""
        lines = []
        for ev in self.events:
            record: dict[str, Any] = {
                "scan_id": scan_id,
                "timestamp": ev.timestamp.isoformat(),
                "pattern_name": ev.pattern_name,
                "sha256_prefix": ev.sha256_prefix,
                "context_hint": ev.context_hint,
            }
            lines.append(json.dumps(record, sort_keys=True))
        return "\n".join(lines) + ("\n" if lines else "")

    @property
    def count(self) -> int:
        return len(self.events)

    def pattern_counts(self) -> dict[str, int]:
        """Return `{pattern_name: n}` summary. Useful for end-of-run logging."""
        counts: dict[str, int] = {}
        for ev in self.events:
            counts[ev.pattern_name] = counts.get(ev.pattern_name, 0) + 1
        return counts


# Context-var plumbing so CLI wrappers can set an active ledger and agents
# pick it up automatically — same pattern as `efterlev.provenance.context.active_store`.
# `format_*_for_prompt` consults this when no explicit `redaction_ledger` is
# passed, keeping the agent code agnostic of how audit-logging is wired.
_active_redaction_ledger: contextvars.ContextVar[RedactionLedger | None] = contextvars.ContextVar(
    "efterlev_active_redaction_ledger", default=None
)


def get_active_redaction_ledger() -> RedactionLedger | None:
    """Return the currently-activated RedactionLedger, or None."""
    return _active_redaction_ledger.get()


@contextmanager
def active_redaction_ledger(ledger: RedactionLedger) -> Iterator[RedactionLedger]:
    """Scope-bind `ledger` so format_*_for_prompt helpers record into it automatically.

    Example:
        ledger = RedactionLedger()
        with active_redaction_ledger(ledger):
            agent.run(input)
        # `ledger.events` now holds every redaction that happened during
        # the agent's prompt assembly, even though the agent never knew
        # a ledger was involved.
    """
    token = _active_redaction_ledger.set(ledger)
    try:
        yield ledger
    finally:
        _active_redaction_ledger.reset(token)


def write_redaction_log(
    ledger: RedactionLedger,
    log_path: Any,  # Path — typed as Any to avoid an import cycle in the scrubber module
    *,
    scan_id: str,
) -> int:
    """Append the ledger's events to `log_path` as JSONL with 0600 perms.

    Creates the parent directory if needed. File mode 0o600 (user read/write
    only) is set on create AND reaffirmed on append — a previous scan that
    created the file with different perms still ends up 0600 after we append.

    Returns the number of events written. Appending an empty ledger is a
    no-op (the file isn't touched if there's nothing to write).
    """
    from pathlib import Path

    path = Path(log_path) if not isinstance(log_path, Path) else log_path
    if ledger.count == 0:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    content = ledger.as_jsonl(scan_id=scan_id)

    # Create-if-missing with restrictive perms; append to existing.
    if not path.exists():
        # Create with 0600 in one shot via os.open + O_CREAT, then wrap.
        import os

        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, content.encode("utf-8"))
        finally:
            os.close(fd)
    else:
        # Existing file: append and reaffirm mode (defense against a prior
        # umask-permissive create).
        with path.open("a", encoding="utf-8") as f:
            f.write(content)
        import os

        os.chmod(path, 0o600)

    return ledger.count
