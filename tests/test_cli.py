"""CLI shape tests.

Verifies the CLI registers every v0 subcommand, that `--help` / `--version` work,
and that stub subcommands raise `NotImplementedError`. Does not yet exercise any
real behavior — that lands with each subcommand's implementation phase.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from efterlev import __version__
from efterlev.cli.main import app

runner = CliRunner()


def test_root_help_lists_every_v0_subcommand() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("init", "scan", "agent", "provenance", "mcp"):
        assert cmd in result.output


def test_version_flag_prints_package_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_agent_subtree_lists_three_agents() -> None:
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    for sub in ("gap", "document", "remediate"):
        assert sub in result.output


def test_mcp_serve_command_is_registered() -> None:
    """`efterlev mcp serve` is wired up — behavior lives in tests/test_mcp_server.py."""
    result = runner.invoke(app, ["mcp", "serve", "--help"])
    assert result.exit_code == 0
    assert "MCP stdio server" in result.output


def test_detectors_list_lists_all_thirty_detectors(tmp_path: pytest.TempPathFactory) -> None:
    """`efterlev detectors list` was promised by THREAT_MODEL.md but
    didn't exist before 2026-04-25 (round-2 review finding). Now it
    does — this test locks the contract.
    """
    result = runner.invoke(app, ["detectors", "list"])
    assert result.exit_code == 0
    # 45 detectors per the A4 + Priority 1.x catalog + the 2026-04-29
    # nacl_restrictiveness + centralized_log_aggregation landings (see
    # tests/test_smoke.py: test_every_detector_folder_registers).
    assert "total: 45 detectors" in result.output
    # Priority 6 honesty pass (2026-04-27): summary breaks down KSI-mapped
    # vs supplementary 800-53-only detectors so a reader knows the marketed
    # count isn't all KSI contributions.
    assert "38 KSI-mapped" in result.output
    assert "7 800-53 only" in result.output
    # Spot-check a couple of detector ids appear.
    assert "aws.encryption_s3_at_rest" in result.output
    assert "aws.access_analyzer_enabled" in result.output


def test_detectors_list_tags_supplementary_800_53_only_detectors(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Supplementary detectors (those with ksis=[]) get a visible tag so a
    reader scanning the list knows which detectors contribute to KSI
    roll-ups vs which provide supplementary 800-53 evidence only.
    Priority 6 (2026-04-27 honesty pass)."""
    result = runner.invoke(app, ["detectors", "list"])
    assert result.exit_code == 0
    # The 5 SC-28 detectors are the canonical supplementary cohort.
    for det_id in (
        "aws.encryption_s3_at_rest",
        "aws.encryption_ebs",
        "aws.rds_encryption_at_rest",
        "aws.sns_topic_encryption",
        "aws.sqs_queue_encryption",
    ):
        # Each line for one of these detectors should carry the [800-53 only] tag.
        line_with_tag = next(
            (
                line
                for line in result.output.splitlines()
                if det_id in line and "[800-53 only]" in line
            ),
            None,
        )
        assert line_with_tag is not None, (
            f"expected `{det_id}` line to carry `[800-53 only]` tag; output:\n{result.output}"
        )
    # And kms_key_rotation, rehomed in this same pass, should NOT carry the tag.
    line_with_kms = next(
        (line for line in result.output.splitlines() if "aws.kms_key_rotation" in line),
        None,
    )
    assert line_with_kms is not None
    assert "[800-53 only]" not in line_with_kms


def test_provenance_verify_clean_store_passes(tmp_path: pytest.TempPathFactory) -> None:
    """`efterlev provenance verify` was claimed by THREAT_MODEL.md as
    the tamper-detection path. The earlier reality: the command did
    not exist. Now it does; this test locks the clean-store path.
    """
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0
    # Empty store — no records to verify against, but the command
    # must still exit cleanly.
    result = runner.invoke(app, ["provenance", "verify", "--target", str(tmp_path)])
    assert result.exit_code == 0
    assert "RESULT: clean" in result.output


def test_provenance_verify_detects_tampered_blob(tmp_path: Path) -> None:
    """A modified blob must surface as a mismatch finding.

    Walks the storage path: write a record, mutate its blob on disk,
    rerun verify, assert the mismatch is reported and exit code is 1.
    """
    from efterlev.provenance import ProvenanceStore

    with ProvenanceStore(tmp_path) as store:
        record = store.write_record(
            payload={"detector_id": "aws.test", "content": {"x": 1}},
            record_type="evidence",
            primitive="scan_terraform@0.1.0",
        )
        blob_path = store.blob_dir / record.content_ref

    # Tamper: rewrite the blob with different content.
    blob_path.write_text('{"detector_id": "aws.test", "content": {"x": 2}}')

    result = runner.invoke(app, ["provenance", "verify", "--target", str(tmp_path)])
    assert result.exit_code == 1
    assert "MISMATCHES" in result.output
    assert record.record_id in result.output


def test_agent_gap_missing_efterlev_dir_prints_error(tmp_path: pytest.TempPathFactory) -> None:
    result = runner.invoke(app, ["agent", "gap", "--target", str(tmp_path)])
    assert result.exit_code == 1
    assert "no `.efterlev/` directory" in result.output


def test_agent_document_missing_efterlev_dir_prints_error(
    tmp_path: pytest.TempPathFactory,
) -> None:
    result = runner.invoke(app, ["agent", "document", "--target", str(tmp_path)])
    assert result.exit_code == 1
    assert "no `.efterlev/` directory" in result.output


def test_agent_remediate_missing_efterlev_dir_prints_error(
    tmp_path: pytest.TempPathFactory,
) -> None:
    result = runner.invoke(
        app, ["agent", "remediate", "--ksi", "KSI-SVC-VRI", "--target", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "no `.efterlev/` directory" in result.output


def test_agent_remediate_unknown_ksi_prints_error(tmp_path: pytest.TempPathFactory) -> None:
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    result = runner.invoke(
        app,
        ["agent", "remediate", "--ksi", "KSI-DOES-NOT-EXIST", "--target", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "not in the loaded baseline" in result.output


def test_agent_remediate_without_classification_prints_error(
    tmp_path: pytest.TempPathFactory,
) -> None:
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    # Pick any real KSI from the loaded FRMR; no `agent gap` has run yet.
    result = runner.invoke(
        app, ["agent", "remediate", "--ksi", "KSI-SVC-SNT", "--target", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "no Gap Agent classification" in result.output


def test_agent_remediate_short_circuits_on_manifest_only_evidence(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """A KSI whose Evidence is exclusively manifest-sourced has no Terraform
    surface to remediate — the CLI must exit cleanly before invoking the LLM
    rather than feeding the YAML manifest to the Remediation Agent as if it
    were Terraform source. This locks in the filter from Phase 1 polish C.
    """
    import json

    from efterlev.models import Claim
    from efterlev.provenance import ProvenanceStore

    root = Path(str(tmp_path))

    # 1. Init the workspace so FRMR cache + provenance store exist.
    init_result = runner.invoke(app, ["init", "--target", str(root)])
    assert init_result.exit_code == 0, init_result.output

    # 2. Drop a manifest attesting to KSI-AFR-FSI (FedRAMP Security Inbox).
    manifests_dir = root / ".efterlev" / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    (manifests_dir / "security-inbox.yml").write_text(
        "ksi: KSI-AFR-FSI\n"
        "name: FedRAMP Security Inbox\n"
        "evidence:\n"
        "  - type: attestation\n"
        "    statement: security@example.com monitored 24/7 by SOC team.\n"
        "    attested_by: vp-security@example.com\n"
        "    attested_at: 2026-04-15\n",
        encoding="utf-8",
    )

    # 3. Scan to produce the manifest-sourced Evidence record. No `.tf` files
    #    are present, so no Terraform Evidence lands — only manifest Evidence.
    scan_result = runner.invoke(app, ["scan", "--target", str(root)])
    assert scan_result.exit_code == 0, scan_result.output

    # 4. Persist a `partial` classification for KSI-AFR-FSI directly. We
    #    don't run the Gap Agent (it needs an API key); we just write the
    #    Claim in the shape the reconstruction helper expects, cited by
    #    the manifest Evidence id.
    with ProvenanceStore(root) as store:
        manifest_evidence = [
            p for _rid, p in store.iter_evidence() if p["detector_id"] == "manifest"
        ]
        assert manifest_evidence, "scan should have produced one manifest Evidence record"
        ev_id = manifest_evidence[0]["evidence_id"]
        clf = Claim.create(
            claim_type="classification",
            content={
                "ksi_id": "KSI-AFR-FSI",
                "status": "partial",
                "rationale": "Procedural attestation present; infra layer n/a.",
            },
            confidence="medium",
            derived_from=[ev_id],
            model="stub",
            prompt_hash="stub",
        )
        store.write_record(
            payload=json.loads(clf.model_dump_json()),
            record_type="claim",
            derived_from=[ev_id],
            agent="stub",
            model="stub",
            prompt_hash="stub",
            metadata={"kind": "ksi_classification", "ksi_id": "KSI-AFR-FSI"},
        )

    # 5. Invoke remediate. The CLI must short-circuit with a clean message
    #    before calling any LLM — if it reached the agent, the test would
    #    fail with a missing-API-key error.
    result = runner.invoke(
        app, ["agent", "remediate", "--ksi", "KSI-AFR-FSI", "--target", str(root)]
    )
    assert result.exit_code == 0, result.output
    assert "no Terraform surface to remediate" in result.output
    assert ".efterlev/manifests/" in result.output


def test_agent_document_without_classifications_prints_error(
    tmp_path: pytest.TempPathFactory,
) -> None:
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    # Init ran but no `agent gap` yet — no classifications in the store,
    # so the CLI should say so rather than calling the LLM.
    result = runner.invoke(app, ["agent", "document", "--target", str(tmp_path)])
    assert result.exit_code == 1
    assert "0 Gap Agent classifications" in result.output


def test_agent_gap_without_evidence_prints_error(tmp_path: pytest.TempPathFactory) -> None:
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    # init writes a load-receipt evidence record (primitive-invocation shape),
    # but no detector-emitted Evidence until `scan` runs. The CLI should
    # detect the empty evidence set and say so.
    result = runner.invoke(app, ["agent", "gap", "--target", str(tmp_path)])
    assert result.exit_code == 1
    assert "0 evidence records" in result.output


def test_scan_missing_efterlev_dir_prints_error(tmp_path: pytest.TempPathFactory) -> None:
    result = runner.invoke(app, ["scan", "--target", str(tmp_path)])
    assert result.exit_code == 1
    assert "no `.efterlev/` directory" in result.output


def test_scan_after_init_produces_evidence(tmp_path: pytest.TempPathFactory) -> None:
    # Write an encrypted bucket then init + scan end-to-end.
    Path(str(tmp_path) + "/main.tf").write_text(
        'resource "aws_s3_bucket" "logs" {\n'
        '  bucket = "logs"\n'
        "  server_side_encryption_configuration {\n"
        "    rule {\n"
        "      apply_server_side_encryption_by_default {\n"
        '        sse_algorithm = "AES256"\n'
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    # `--verbose` so the per-detector record-ID dump appears in stdout —
    # without it, v0.1.4's quieter default just prints a 1-line summary
    # ("N record(s) written to .efterlev/store.db; pass --verbose...").
    scan_result = runner.invoke(app, ["scan", "--target", str(tmp_path), "--verbose"])
    assert scan_result.exit_code == 0, scan_result.output
    assert "Scanned" in scan_result.output
    assert "resources parsed:" in scan_result.output
    assert "aws.encryption_s3_at_rest" in scan_result.output
    # Manifest loading is now part of `scan`; the record-IDs section is
    # labeled "Detector record IDs" to distinguish from manifest-sourced
    # Evidence (Phase 1, Evidence Manifest landing). Verbose-only as of v0.1.4.
    assert "Detector record IDs" in scan_result.output
    assert "manifest files:" in scan_result.output
    # No `module calls:` line when there are no module declarations — the
    # summary stays terse for the common resource-only case.
    assert "module calls:" not in scan_result.output
    # No plan-JSON warning either.
    assert "module calls detected" not in scan_result.output


def test_scan_warns_about_module_density_when_module_heavy(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """When a codebase is module-composed (the dominant ICP-A pattern),
    `efterlev scan` (HCL mode) must surface a structured warning recommending
    plan-JSON expansion."""
    Path(str(tmp_path) + "/main.tf").write_text(
        'module "vpc" {\n  source = "terraform-aws-modules/vpc/aws"\n}\n'
        'module "eks" {\n  source = "terraform-aws-modules/eks/aws"\n}\n'
        'module "iam" {\n  source = "terraform-aws-modules/iam/aws"\n}\n'
    )
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    scan_result = runner.invoke(app, ["scan", "--target", str(tmp_path)])
    assert scan_result.exit_code == 0, scan_result.output
    # Module-call count is surfaced in the summary block.
    assert "module calls:        3" in scan_result.output
    # Warning fires.
    assert "3 module calls detected" in scan_result.output
    assert "detector coverage is limited in HCL mode" in scan_result.output
    # Remediation is the copy-pasteable plan-JSON command.
    assert "efterlev scan --plan plan.json" in scan_result.output


def test_init_succeeds_and_prints_summary(tmp_path: pytest.TempPathFactory) -> None:
    result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Initialized" in result.output
    assert "FRMR:" in result.output
    assert "NIST SP 800-53 Rev 5:" in result.output


def test_init_refuses_existing_workspace(tmp_path: pytest.TempPathFactory) -> None:
    first = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert first.exit_code == 0
    second = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert second.exit_code == 1
    assert "already exists" in second.output


def test_provenance_show_missing_efterlev_dir_prints_error(
    tmp_path: pytest.TempPathFactory,
) -> None:
    # tmp_path has no `.efterlev/` — the CLI should error cleanly, not explode.
    result = runner.invoke(app, ["provenance", "show", "sha256:abc", "--target", str(tmp_path)])
    assert result.exit_code == 1
    assert "no `.efterlev/` directory" in result.output


def test_remediate_requires_ksi_option() -> None:
    result = runner.invoke(app, ["agent", "remediate"])
    # Missing required --ksi should fail at Typer's argument parser (exit 2),
    # not reach the stub body.
    assert result.exit_code == 2
    assert result.exception is None or not isinstance(result.exception, NotImplementedError)


# --- boundary CLI verbs (Priority 4.2, 2026-04-27) ------------------------


def test_boundary_show_on_undeclared_workspace(tmp_path: Path) -> None:
    """Fresh workspace has no boundary; `boundary show` says so + suggests next step."""
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    show = runner.invoke(app, ["boundary", "show", "--target", str(tmp_path)])
    assert show.exit_code == 0, show.output
    assert "No boundary declared" in show.output
    assert "boundary_undeclared" in show.output
    assert "boundary set --include" in show.output


def test_boundary_set_then_show_round_trips(tmp_path: Path) -> None:
    """`set` writes patterns; `show` reads them back including counts."""
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0

    set_result = runner.invoke(
        app,
        [
            "boundary",
            "set",
            "--target",
            str(tmp_path),
            "--include",
            "boundary/**",
            "--include",
            "infra/prod/**",
            "--exclude",
            "**/test/**",
        ],
    )
    assert set_result.exit_code == 0, set_result.output
    assert "include (2)" in set_result.output
    assert "exclude (1)" in set_result.output

    show = runner.invoke(app, ["boundary", "show", "--target", str(tmp_path)])
    assert show.exit_code == 0
    assert "boundary/**" in show.output
    assert "infra/prod/**" in show.output
    assert "**/test/**" in show.output
    assert "exclude wins over include" in show.output


def test_boundary_set_appends_by_default(tmp_path: Path) -> None:
    """Calling `set` twice appends — typical 'add another pattern' workflow."""
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0
    runner.invoke(app, ["boundary", "set", "--target", str(tmp_path), "--include", "a/**"])
    runner.invoke(app, ["boundary", "set", "--target", str(tmp_path), "--include", "b/**"])

    show = runner.invoke(app, ["boundary", "show", "--target", str(tmp_path)])
    assert "a/**" in show.output
    assert "b/**" in show.output
    assert "include (2)" in show.output


def test_boundary_set_replace_overwrites_existing(tmp_path: Path) -> None:
    """`--replace` swaps the pattern set rather than appending."""
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0
    runner.invoke(app, ["boundary", "set", "--target", str(tmp_path), "--include", "old/**"])
    runner.invoke(
        app,
        [
            "boundary",
            "set",
            "--target",
            str(tmp_path),
            "--replace",
            "--include",
            "new/**",
        ],
    )

    show = runner.invoke(app, ["boundary", "show", "--target", str(tmp_path)])
    assert "new/**" in show.output
    assert "old/**" not in show.output


def test_boundary_set_with_no_patterns_errors(tmp_path: Path) -> None:
    """`boundary set` with no --include/--exclude is a usage error.

    Typer can't catch this (both options are list-typed and default to []),
    so the command checks at runtime and exits with code 2."""
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0
    result = runner.invoke(app, ["boundary", "set", "--target", str(tmp_path)])
    assert result.exit_code == 2
    assert "at least one --include or --exclude" in result.output


def test_boundary_check_classifies_path(tmp_path: Path) -> None:
    """`boundary check <path>` echoes the resolved state."""
    init_result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert init_result.exit_code == 0
    runner.invoke(
        app,
        [
            "boundary",
            "set",
            "--target",
            str(tmp_path),
            "--include",
            "boundary/**",
            "--exclude",
            "**/test/**",
        ],
    )

    in_check = runner.invoke(
        app, ["boundary", "check", "--target", str(tmp_path), "boundary/main.tf"]
    )
    assert in_check.exit_code == 0
    assert "in_boundary" in in_check.output

    out_check = runner.invoke(
        app, ["boundary", "check", "--target", str(tmp_path), "commercial/eks.tf"]
    )
    assert out_check.exit_code == 0
    assert "out_of_boundary" in out_check.output

    excluded_check = runner.invoke(
        app, ["boundary", "check", "--target", str(tmp_path), "boundary/test/iam.tf"]
    )
    assert excluded_check.exit_code == 0
    assert "out_of_boundary" in excluded_check.output


def test_boundary_set_missing_workspace_errors(tmp_path: Path) -> None:
    """Without a workspace at the target, `boundary set` exits cleanly."""
    result = runner.invoke(
        app,
        ["boundary", "set", "--target", str(tmp_path), "--include", "boundary/**"],
    )
    assert result.exit_code == 1
    assert "config not found" in result.output


def test_display_path_keeps_user_target_form_for_symlinked_dirs(tmp_path: Path) -> None:
    # On macOS /tmp is a symlink to /private/tmp; the same paper-cut shows
    # up anywhere a user passes a path under a symlinked directory. Verify
    # the helper reconstructs the path under the un-resolved target form.
    from efterlev.cli.main import _display_path

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / ".efterlev" / "reports").mkdir(parents=True)
    report = real_dir / ".efterlev" / "reports" / "gap-1.html"
    report.write_text("<html/>", encoding="utf-8")

    symlink_target = tmp_path / "link"
    symlink_target.symlink_to(real_dir)

    # User passed `tmp/link/...`; canonical form lives under `tmp/real/...`.
    # Display should re-stitch the path under the user-supplied form.
    displayed = _display_path(report, symlink_target)
    assert str(symlink_target) in displayed
    assert str(real_dir) not in displayed

    # Sanity: a path not under target.resolve() falls back to its own str().
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("", encoding="utf-8")
    assert _display_path(outside, symlink_target) == str(outside)
