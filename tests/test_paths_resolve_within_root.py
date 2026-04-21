"""Tests for `paths.resolve_within_root` — the path-traversal defense.

Used by the Remediation CLI + MCP tool when reading `.tf` files
referenced by `Evidence.source_ref.file`. The hardening property:
evidence records cannot exfiltrate files outside the target repo.
"""

from __future__ import annotations

import os
from pathlib import Path

from efterlev.paths import resolve_within_root


def test_accepts_valid_relative_path(tmp_path: Path) -> None:
    (tmp_path / "main.tf").write_text("resource {}")
    resolved = resolve_within_root(Path("main.tf"), tmp_path)
    assert resolved is not None
    assert resolved == (tmp_path / "main.tf").resolve()


def test_accepts_nested_relative_path(tmp_path: Path) -> None:
    nested = tmp_path / "modules" / "app"
    nested.mkdir(parents=True)
    (nested / "main.tf").write_text("resource {}")
    resolved = resolve_within_root(Path("modules/app/main.tf"), tmp_path)
    assert resolved is not None
    assert resolved == (nested / "main.tf").resolve()


def test_rejects_absolute_path_outside_root(tmp_path: Path) -> None:
    # An absolute path that is NOT under root is still rejected — containment
    # is the safety check. `/etc/passwd` obviously doesn't live in tmp_path.
    assert resolve_within_root(Path("/etc/passwd"), tmp_path) is None


def test_accepts_absolute_path_inside_root(tmp_path: Path) -> None:
    # Absolute paths that resolve INSIDE root are accepted. Real CI case:
    # the Terraform parser captures source_ref.file paths exactly as walked,
    # which under GitHub Actions comes out as absolute (e.g.
    # /home/runner/work/repo/infra/terraform/main.tf). Rejecting those
    # outright broke the remediation flow; containment is the real check.
    (tmp_path / "main.tf").write_text("resource {}")
    abs_path = (tmp_path / "main.tf").resolve()
    resolved = resolve_within_root(abs_path, tmp_path)
    assert resolved is not None
    assert resolved == abs_path


def test_rejects_parent_traversal(tmp_path: Path) -> None:
    # The classic attack: `../../../etc/passwd`. A detector that emits this
    # as source_ref.file could otherwise cause the remediation agent to
    # read /etc/passwd and ship it to the LLM fenced as a source_file.
    outer = tmp_path / "outside.tf"
    outer.write_text("should not be readable through the agent")
    inner_root = tmp_path / "repo"
    inner_root.mkdir()
    assert resolve_within_root(Path("../outside.tf"), inner_root) is None


def test_rejects_deep_traversal(tmp_path: Path) -> None:
    # Even if we descend first, `..` segments that ultimately climb out
    # must be rejected.
    deep_root = tmp_path / "a" / "b"
    deep_root.mkdir(parents=True)
    (tmp_path / "leak.tf").write_text("secret")
    assert resolve_within_root(Path("../../leak.tf"), deep_root) is None


def test_returns_none_on_nonexistent_but_contained_path(tmp_path: Path) -> None:
    # Containment check is independent of existence — callers do the
    # is_file() gate separately. A non-existent repo-relative path
    # resolves inside root, so we return the path (caller rejects later).
    resolved = resolve_within_root(Path("nonexistent.tf"), tmp_path)
    assert resolved is not None
    assert resolved == (tmp_path / "nonexistent.tf").resolve()


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    # A symlink inside the repo pointing outside the repo is the subtle
    # case: naive `(root / candidate).resolve()` follows the symlink, so
    # the returned path escapes root. `relative_to` catches it.
    outside = tmp_path / "outside_secrets"
    outside.mkdir()
    (outside / "secret.tf").write_text("very secret")

    repo = tmp_path / "repo"
    repo.mkdir()
    # Create a symlink `repo/escape` → `../outside_secrets`.
    link = repo / "escape"
    os.symlink(outside, link)

    # `escape/secret.tf` syntactically sits under repo, but the symlink
    # makes the resolved path live outside it.
    result = resolve_within_root(Path("escape/secret.tf"), repo)
    assert result is None
