#!/usr/bin/env python3
"""Doc-vs-code drift checker.

Catches the class of bug the round-2 reviewer flagged: numeric claims
in prose ("344 passing", "60 indicators", "14 detectors") and command
references ("`efterlev detectors list`") that diverge from runtime
truth. The honesty-pass model is unsustainable — by the time the
maintainer notices a number went stale, the next one already has.
This script makes the check enforceable.

What's checked at this revision:
  1. Test count claims in prose match `pytest -q --collect-only -m "not e2e"`.
  2. Detector count claims match the runtime registry (the 16-of-30
     bug fixed 2026-04-25 is exactly this class).
  3. FRMR indicator count claims match the structural count of the
     vendored catalog.
  4. Source-file count claims match `find src -name "*.py" | wc -l`.
  5. Every `efterlev <verb>` reference in user-facing prose resolves
     to an actual CLI command.

Out of scope deliberately:
  - PyPI install honesty: README + LIMITATIONS already explicitly call
    out that pipx install is gated on launch. The grep-scrub script
    catches the inverse drift (post-launch references slipping in pre-
    launch). This script trusts that.
  - Internal-doc test counts (DECISIONS.md historical entries are
    snapshots-in-time and DO NOT need to match current).

Exit 0 = clean. Exit 1 = at least one drift; details on stdout.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# User-facing docs that should agree with runtime. Internal docs
# (CLAUDE.md, DECISIONS.md) deliberately carry dated "end state at
# <date>" snapshots — those are journal entries by design and should
# not be auto-updated. The reviewer's specific concern was the
# user-facing surface (README, LIMITATIONS, THREAT_MODEL, etc.); this
# checker scopes itself there.
USER_FACING_DOCS = [
    "README.md",
    "LIMITATIONS.md",
    "THREAT_MODEL.md",
    "CONTRIBUTING.md",
    "docs/architecture.md",
    "docs/quickstart.md",
    "docs/index.md",
    "docs/concepts/ksis-for-engineers.md",
    "docs/concepts/evidence-vs-claims.md",
    "docs/concepts/provenance.md",
    "docs/concepts/what-efterlev-is-not.md",
    "docs/reference/cli.md",
    "docs/reference/detectors.md",
    "docs/reference/primitives.md",
    "catalogs/README.md",
]

# Dated retrospectives, if any are reintroduced, are point-in-time and excluded.
EXCLUDE = re.compile(r"^docs/dogfood-\d{4}-\d{2}-\d{2}\.md$")

# A CLI reference that lives in a context where the prose explicitly
# names it as not-yet-implemented or planned doesn't count as a drift
# claim. These markers must appear in the SAME paragraph as the
# command reference (within ±200 chars of the match) for the
# exemption to apply.
ASPIRATIONAL_MARKERS = re.compile(
    r"(not yet implemented|not implemented|"
    r"planned for v|v1 command|v1\+|v1\.5\+|"
    r"tracked as follow-up|follow-up|"
    r"deferred|aspirational|"
    r"\bTODO\b|\bFIXME\b)",
    re.IGNORECASE,
)


def runtime_test_count() -> int:
    """How many tests `pytest -m "not e2e"` collects right now.

    Counts `path::test_name` lines from `pytest --collect-only -q`. The
    summary-line approach is unreliable across pytest versions; the
    `path::test_name` shape is stable.
    """
    out = subprocess.check_output(
        ["uv", "run", "--extra", "dev", "pytest", "-m", "not e2e", "--collect-only", "-q"],
        cwd=REPO_ROOT,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return sum(1 for line in out.splitlines() if "::" in line and line.startswith("tests/"))


def runtime_detector_count() -> int:
    """How many detectors register on `import efterlev.detectors`."""
    out = subprocess.check_output(
        [
            "uv",
            "run",
            "python",
            "-c",
            "import efterlev.detectors; "
            "from efterlev.detectors.base import get_registry; "
            "print(len(get_registry()))",
        ],
        cwd=REPO_ROOT,
        text=True,
    )
    return int(out.strip())


def runtime_indicator_count() -> int:
    """How many KSIs the FRMR catalog declares structurally."""
    catalog = json.loads((REPO_ROOT / "catalogs" / "frmr" / "FRMR.documentation.json").read_text())
    return sum(len(theme.get("indicators", {})) for theme in catalog.get("KSI", {}).values())


def runtime_source_file_count() -> int:
    """Source-file count under `src/efterlev`. Used by README's lint stanza."""
    return sum(1 for _ in (REPO_ROOT / "src" / "efterlev").rglob("*.py"))


def runtime_cli_commands() -> set[str]:
    """Every command/verb the CLI exposes. Used to validate prose references.

    Captures top-level commands AND subcommand verbs (`agent gap`,
    `detectors list`, `provenance show`, etc.). Returned as the
    "<top> <sub>" or "<top>" string a doc would write.
    """
    out = subprocess.check_output(
        [
            "uv",
            "run",
            "python",
            "-c",
            "from efterlev.cli.main import app\n"
            "import typer\n"
            "from typer.main import get_command\n"
            "click_app = get_command(app)\n"
            "names = set()\n"
            "def walk(cmd, prefix=()):\n"
            "    for n, sub in getattr(cmd, 'commands', {}).items():\n"
            "        names.add(' '.join(prefix + (n,)))\n"
            "        walk(sub, prefix + (n,))\n"
            "walk(click_app)\n"
            "print('\\n'.join(sorted(names)))",
        ],
        cwd=REPO_ROOT,
        text=True,
    )
    return set(out.strip().splitlines())


# --- claim extractors ----------------------------------------------------------

# Patterns deliberately conservative — match must be unambiguous to
# count as a claim. Loose matches generate noise that desensitizes
# the maintainer to the real findings.

TEST_COUNT_RE = re.compile(r"\b(\d{2,4})\s+(?:tests?\s+(?:passing|pass)|passing)\b")
DETECTOR_COUNT_RE = re.compile(r"\b(\d{1,3})\s+detectors?\s+(?:register|registered|run|loaded)\b")
INDICATOR_COUNT_RE = re.compile(
    r"\b(\d{1,3})\s+(?:KSIs?|indicators?)\s+(?:in\s+FRMR|across\s+\d+\s+themes|in\s+the\s+baseline)"
)
SOURCE_FILES_RE = re.compile(r"\b(\d{1,4})\s+source\s+files?\b")
CLI_REFERENCE_RE = re.compile(r"`efterlev\s+([a-z][a-z\- ]*?[a-z])(?:\s+[<\-]|\s*`)")


def check_doc(path: Path, expected: dict[str, int], cli_commands: set[str]) -> list[str]:
    """Return a list of finding strings (empty list = clean)."""
    findings: list[str] = []
    text = path.read_text()
    rel = path.relative_to(REPO_ROOT)

    # Numeric claims.
    for m in TEST_COUNT_RE.finditer(text):
        claimed = int(m.group(1))
        if claimed != expected["tests"]:
            line_no = text[: m.start()].count("\n") + 1
            findings.append(
                f"{rel}:{line_no}: claims '{claimed} passing' but actual is {expected['tests']}"
            )
    for m in DETECTOR_COUNT_RE.finditer(text):
        claimed = int(m.group(1))
        if claimed != expected["detectors"]:
            line_no = text[: m.start()].count("\n") + 1
            findings.append(
                f"{rel}:{line_no}: claims '{claimed} detectors' but registry has "
                f"{expected['detectors']}"
            )
    for m in INDICATOR_COUNT_RE.finditer(text):
        claimed = int(m.group(1))
        if claimed != expected["indicators"]:
            line_no = text[: m.start()].count("\n") + 1
            findings.append(
                f"{rel}:{line_no}: claims '{claimed} indicators' but FRMR catalog has "
                f"{expected['indicators']}"
            )
    for m in SOURCE_FILES_RE.finditer(text):
        claimed = int(m.group(1))
        if claimed != expected["source_files"]:
            line_no = text[: m.start()].count("\n") + 1
            findings.append(
                f"{rel}:{line_no}: claims '{claimed} source files' but actual is "
                f"{expected['source_files']}"
            )

    # CLI references. Keep the verb conservative — the regex picks up
    # only the form `efterlev <verb> [<verb>]` followed by a flag, an
    # arg placeholder, or backtick-close.
    for m in CLI_REFERENCE_RE.finditer(text):
        verb = m.group(1).strip()
        # Strip option-shaped suffixes that aren't real subcommands.
        verb = re.sub(r"\s+--?\w+.*$", "", verb)
        if not verb or verb in cli_commands:
            continue
        # Tolerate prefix matches: `agent` is a group; `agent gap` is the
        # actual command. A doc that says `efterlev agent` (with no sub)
        # is referring to the group root, which is legitimate.
        if any(c.startswith(verb + " ") for c in cli_commands):
            continue
        # Tolerate aspirational references: prose that names a not-yet-
        # implemented command in the same paragraph as a "planned for v1"
        # / "not yet implemented" marker is honest disclosure, not drift.
        nearby = text[max(0, m.start() - 200) : m.start() + 200]
        if ASPIRATIONAL_MARKERS.search(nearby):
            continue
        line_no = text[: m.start()].count("\n") + 1
        findings.append(
            f"{rel}:{line_no}: references `efterlev {verb}` but CLI has no such command"
        )

    return findings


def main() -> int:
    expected = {
        "tests": runtime_test_count(),
        "detectors": runtime_detector_count(),
        "indicators": runtime_indicator_count(),
        "source_files": runtime_source_file_count(),
    }
    cli_commands = runtime_cli_commands()

    print(
        f"runtime: {expected['tests']} tests, "
        f"{expected['detectors']} detectors, "
        f"{expected['indicators']} indicators, "
        f"{expected['source_files']} source files, "
        f"{len(cli_commands)} CLI commands"
    )

    all_findings: list[str] = []
    for rel in USER_FACING_DOCS:
        if EXCLUDE.match(rel):
            continue
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        all_findings.extend(check_doc(path, expected, cli_commands))

    if not all_findings:
        print("RESULT: clean. No doc-vs-code drift.")
        return 0

    print(f"\nRESULT: {len(all_findings)} drift finding(s):")
    for f in all_findings:
        print(f"  {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
