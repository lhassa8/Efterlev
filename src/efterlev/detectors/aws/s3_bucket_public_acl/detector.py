"""S3 public-ACL detector.

Flags `aws_s3_bucket_acl` resources with public canned ACLs
(`public-read`, `public-read-write`) and `aws_s3_bucket_policy`
resources granting `Principal = "*"` or `{"AWS": "*"}`. Complements
the existing `aws.s3_public_access_block` detector by catching the
ACL/policy path that PAB doesn't directly cover when PAB is absent.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-CNA-RNT (Restricting Network Traffic) — sc-7.5.
  - KSI-CNA-MAT (Minimizing Attack Surface) — broader sc-7 family.

Policy parsing is best-effort: heredoc-style literal JSON is parsed;
`jsonencode(...)` and `data.aws_iam_policy_document.X.json` references
render as `${...}` placeholders and emit unparseable evidence variants.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_PUBLIC_CANNED_ACLS = frozenset({"public-read", "public-read-write"})


@detector(
    id="aws.s3_bucket_public_acl",
    ksis=["KSI-CNA-RNT", "KSI-CNA-MAT"],
    controls=["AC-3", "SC-7"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each S3 ACL or bucket-policy that exposes the bucket publicly.

    Evidences (800-53):  AC-3 (Access Enforcement), SC-7 (Boundary Protection).
    Evidences (KSI):     KSI-CNA-RNT, KSI-CNA-MAT.
    Does NOT prove:      that the bucket actually contains anything sensitive;
                         that an `aws_s3_bucket_public_access_block` doesn't
                         override the ACL (PAB does override, but the
                         declared intent is still worth surfacing); the
                         intricacies of cross-account access patterns.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type == "aws_s3_bucket_acl":
            ev = _classify_acl(r, now)
            if ev is not None:
                out.append(ev)
        elif r.type == "aws_s3_bucket_policy":
            ev = _classify_bucket_policy(r, now)
            if ev is not None:
                out.append(ev)

    return out


def _classify_acl(r: TerraformResource, now: datetime) -> Evidence | None:
    acl = r.body.get("acl")
    if not isinstance(acl, str):
        return None
    if acl in _PUBLIC_CANNED_ACLS:
        return Evidence.create(
            detector_id="aws.s3_bucket_public_acl",
            ksis_evidenced=["KSI-CNA-RNT", "KSI-CNA-MAT"],
            controls_evidenced=["AC-3", "SC-7"],
            source_ref=r.source_ref,
            content={
                "resource_type": "aws_s3_bucket_acl",
                "resource_name": r.name,
                "exposure_state": "public_acl",
                "acl": acl,
                "gap": f"bucket ACL is {acl!r}, exposing the bucket to anonymous access",
            },
            timestamp=now,
        )
    return None


def _classify_bucket_policy(r: TerraformResource, now: datetime) -> Evidence | None:
    policy = r.body.get("policy")
    if policy is None:
        return None

    # Unparseable cases: jsonencode(...) and data references render as
    # ${...}. Surface as unparseable rather than silently passing.
    if isinstance(policy, str) and policy.strip().startswith("${"):
        return Evidence.create(
            detector_id="aws.s3_bucket_public_acl",
            ksis_evidenced=["KSI-CNA-RNT", "KSI-CNA-MAT"],
            controls_evidenced=["AC-3", "SC-7"],
            source_ref=r.source_ref,
            content={
                "resource_type": "aws_s3_bucket_policy",
                "resource_name": r.name,
                "exposure_state": "unparseable",
                "reason": (
                    "policy built via jsonencode or data reference; not a literal JSON string"
                ),
            },
            timestamp=now,
        )

    parsed = _try_parse_json(policy)
    if parsed is None:
        return None

    statements = parsed.get("Statement")
    if not isinstance(statements, list):
        return None

    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        if stmt.get("Effect") != "Allow":
            continue
        principal = stmt.get("Principal")
        if _is_anonymous_principal(principal):
            return Evidence.create(
                detector_id="aws.s3_bucket_public_acl",
                ksis_evidenced=["KSI-CNA-RNT", "KSI-CNA-MAT"],
                controls_evidenced=["AC-3", "SC-7"],
                source_ref=r.source_ref,
                content={
                    "resource_type": "aws_s3_bucket_policy",
                    "resource_name": r.name,
                    "exposure_state": "anonymous_allow",
                    "gap": "bucket policy grants Allow to Principal=* (anonymous access)",
                },
                timestamp=now,
            )
    return None


def _try_parse_json(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else None
        except (ValueError, TypeError):
            return None
    return None


def _is_anonymous_principal(principal: Any) -> bool:
    """True iff Principal indicates anonymous access (`*` or `{"AWS": "*"}`)."""
    if principal == "*":
        return True
    if isinstance(principal, dict):
        for value in principal.values():
            if value == "*":
                return True
            if isinstance(value, list) and "*" in value:
                return True
    return False
