"""Parse Terraform / OpenTofu `.tf` files into typed `TerraformResource` objects.

Strategy: run the file through `python-hcl2` to get the parsed body dict, then
regex-scan the original source text for `resource "TYPE" "NAME"` declarations
so we can attach accurate `(line_start, line_end)` source refs to each
resource. python-hcl2 does not expose line info through its public API, so
the regex pass is how we recover it.

v0 scope: `resource` blocks only. `data`, `module`, `locals`, `variable`,
`output`, `provider`, `terraform` blocks are ignored; v1 can add parsers for
whichever detectors need them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hcl2

from efterlev.errors import DetectorError
from efterlev.models import SourceRef, TerraformResource

_RESOURCE_HEADER_RE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"')
# Module-call counting (Priority 0, 2026-04-27): not used for evidence
# extraction — `v0 scope: resource blocks only` per the module docstring.
# Counted alongside resources so the scan layer can warn when a codebase
# is module-heavy and would benefit from plan-JSON expansion. See
# `docs/v1-readiness-plan.md` Priority 0.
_MODULE_HEADER_RE = re.compile(r'^\s*module\s+"([^"]+)"')


@dataclass(frozen=True)
class ParseFailure:
    """One file the tree-walker couldn't parse, captured for partial-success reporting."""

    file: Path
    """Repo-relative path (matches `SourceRef.file` for successful resources)."""
    reason: str
    """Short error message — typically the python-hcl2 / lark exception class + str(e)."""


@dataclass(frozen=True)
class TerraformParseResult:
    """What `parse_terraform_tree` returns: successful resources + per-file failures.

    Real-world Terraform codebases often contain at least one file the
    python-hcl2 library can't parse (the parser lags upstream Terraform
    syntax — see `LIMITATIONS.md`). A scan that aborts on the first failure
    is unusable on production codebases (e.g. `cloudposse/terraform-aws-components`
    has 1801 .tf files; one parse failure on file 1 blocked the entire scan
    pre-2026-04-25). The collect-and-continue contract surfaces failures
    structurally instead of crashing.
    """

    resources: list[TerraformResource]
    parse_failures: list[ParseFailure]
    # Count of `module "<name>" {}` declarations across all parsed .tf files.
    # Detectors do not currently follow into upstream modules — they look for
    # `resource "aws_*"` declarations at the root. Module-composed codebases
    # (the dominant ICP-A pattern) require plan-JSON expansion to surface
    # the resources inside those modules. The scan layer uses this count to
    # warn the user when plan-JSON would meaningfully change the result.
    # See `docs/v1-readiness-plan.md` Priority 0.
    module_call_count: int = 0

    @property
    def files_failed(self) -> int:
        return len(self.parse_failures)


def parse_terraform_tree(target_dir: Path) -> TerraformParseResult:
    """Walk `target_dir` recursively and parse every `.tf` file.

    Collect-and-continue: a file that python-hcl2 can't parse is recorded as
    a `ParseFailure` and the walk continues. Callers (the scan primitive,
    the CLI) inspect `parse_failures` to surface structured warnings.
    Aborting only happens for catastrophic conditions (target directory
    doesn't exist) — never for "one weird file."

    Each resource's `source_ref.file` is recorded as a path relative to
    `target_dir` — keeps the provenance store, HTML reports, and FRMR
    attestation JSON free of the user's absolute filesystem layout. The
    Remediation Agent and other readers recover the absolute path via
    `paths.resolve_within_root(file, root)` at read time. `ParseFailure.file`
    uses the same relative path for the same reason.
    """
    if not target_dir.is_dir():
        raise DetectorError(f"target is not a directory: {target_dir}")
    resources: list[TerraformResource] = []
    parse_failures: list[ParseFailure] = []
    module_call_count = 0
    for tf_file in sorted(target_dir.rglob("*.tf")):
        relative = tf_file.relative_to(target_dir)
        # Count `module "<name>" {}` declarations independently of the HCL
        # parse so a python-hcl2 failure on a sibling block doesn't drop the
        # module-density signal. The regex is tolerant of slight formatting
        # variation (whitespace, trailing brace presence). Module-call
        # counting drives the plan-JSON-recommended warning at the scan
        # layer (Priority 0).
        try:
            text = tf_file.read_text(encoding="utf-8")
            for raw in text.splitlines():
                if _MODULE_HEADER_RE.search(raw):
                    module_call_count += 1
        except OSError:
            # Unreadable files surface as ParseFailures via parse_terraform_file
            # below; no need to double-report here.
            pass
        try:
            resources.extend(parse_terraform_file(tf_file, record_as=relative))
        except DetectorError as e:
            # Strip the absolute-path prefix from the error message to keep
            # the failure record relative-path-clean, matching `file`.
            reason = str(e).replace(f"failed to parse {tf_file}: ", "")
            parse_failures.append(ParseFailure(file=relative, reason=reason))
    return TerraformParseResult(
        resources=resources,
        parse_failures=parse_failures,
        module_call_count=module_call_count,
    )


def parse_terraform_file(
    path: Path,
    *,
    record_as: Path | None = None,
) -> list[TerraformResource]:
    """Parse one `.tf` file; return every `resource` block as a typed record.

    `path` is the filesystem path used for I/O. `record_as`, when provided,
    is the path recorded in `SourceRef.file` — typically the repo-relative
    path produced by `parse_terraform_tree`. When None, `path` is recorded
    verbatim (for direct single-file callers with no repo-root context,
    e.g. unit tests).
    """
    recorded = record_as if record_as is not None else path
    text = path.read_text(encoding="utf-8")
    try:
        with path.open(encoding="utf-8") as f:
            parsed: dict[str, Any] = hcl2.load(f)
    except Exception as e:
        # hcl2 raises lark.exceptions.UnexpectedInput, ValueError,
        # and occasional TypeError on malformed HCL — all map to the
        # same "this .tf file can't be parsed" user-facing story.
        raise DetectorError(f"failed to parse {path}: {e}") from e

    # Build (type, name) -> line_start map by text-scanning the source.
    header_lines: dict[tuple[str, str], int] = {}
    raw_lines = text.splitlines()
    for lineno, raw in enumerate(raw_lines, start=1):
        match = _RESOURCE_HEADER_RE.search(raw)
        if match:
            header_lines.setdefault((match.group(1), match.group(2)), lineno)

    out: list[TerraformResource] = []
    for resource_block in parsed.get("resource", []):
        for rtype, named in resource_block.items():
            for rname, body in named.items():
                actual_body = _unwrap_single_list(body)
                line_start = header_lines.get((rtype, rname))
                line_end = _estimate_block_end(raw_lines, line_start) if line_start else None
                out.append(
                    TerraformResource(
                        type=rtype,
                        name=rname,
                        body=actual_body if isinstance(actual_body, dict) else {},
                        source_ref=SourceRef(
                            file=recorded,
                            line_start=line_start,
                            line_end=line_end,
                        ),
                    )
                )
    return out


def _unwrap_single_list(value: Any) -> Any:
    """python-hcl2 wraps single attribute values in one-element lists; unwrap them."""
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _estimate_block_end(lines: list[str], start: int) -> int:
    """Find the closing `}` for a block that opens on `start` (1-indexed).

    Naive brace-balance — good enough for real-world Terraform because heredoc
    strings are rare and we only need a line range, not an AST. Falls back to
    the last line if no balanced close is found.
    """
    depth = 0
    for offset, line in enumerate(lines[start - 1 :], start=start):
        depth += line.count("{") - line.count("}")
        if depth <= 0 and offset > start:
            return offset
    return len(lines)
