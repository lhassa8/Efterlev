# `github.action_pinning`

Inspects every `.github/workflows/*.yml` workflow and reports whether each `uses:` step references its action by an immutable commit SHA (pinned) or by a mutable tag/branch (vulnerable to a compromised-tag attack).

## What this detector evidences

- **KSI-SCR-MIT** (Mitigating Supply Chain Risk).
- **800-53 controls:** SR-5 (Acquisition Strategies, Tools, and Methods), SI-7(1) (Integrity Checks).

## What it proves

For each workflow file, the detector walks every job's steps. Each `uses: owner/repo@ref` is classified:

- **Pinned:** `@ref` is exactly 40 hex characters (a Git commit SHA).
- **Mutable:** `@ref` is anything else — `@v4`, `@main`, `@latest`, or no `@` at all.
- **Out of scope:** local refs (`./.github/...`) and Docker refs (`docker://...`) are skipped; they have different supply-chain semantics.

One Evidence is emitted per workflow with a `pin_state` of `all_pinned`, `mixed`, `none_pinned`, or `no_external_actions`, plus the full list of mutable refs for follow-up.

## Why this matters

A tag like `@v4` resolves at runtime to whatever commit currently holds the tag. An attacker who compromises an action repository (or a maintainer account) can retag a malicious commit as `v4` and every workflow using `@v4` will execute the malicious code on its next run. This is the attack vector behind tj-actions/changed-files (CVE-2025-30066) and the broader pattern OpenSSF, CISA, and GSA all flag as the FedRAMP-relevant supply-chain hygiene baseline.

A 40-char commit SHA is content-addressed. The workflow run will fail if the upstream object doesn't match the pin.

## What it does NOT prove

- That the SHA-pinned commits are non-malicious — a pin freezes whatever code was at that SHA.
- That pins are kept current — stale pins miss security fixes. Pin-by-SHA combined with a renovate/dependabot update flow is the full pattern.
- That local actions (`uses: ./.github/local-action`) are safe — those are in-tree code; `aws.terraform_inventory` and code review cover that surface.
- That third-party Docker images referenced via `docker://image:tag` are pinned by digest — that's a related but separate concern.

## Detection signal

One Evidence record per workflow file. The `gap` field populates only on `pin_state ∈ {none_pinned, mixed}` — `all_pinned` and `no_external_actions` are good shapes.

## Known limitations

- Reusable-workflow refs (`uses: owner/repo/.github/workflows/foo.yml@ref`) are classified the same way as action refs. That's the right semantics — a reusable workflow at a mutable ref has the same risk shape as an action at a mutable ref.
- The detector doesn't look at `.github/dependabot.yml` to verify the pins are kept current. That's a future detector against a future `parse_dependabot_config` parser.
