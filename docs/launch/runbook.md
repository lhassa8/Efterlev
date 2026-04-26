# Launch runbook

Hour-by-hour sequence for flipping Efterlev public. Tick each checkbox as you go. Skipping is then visible.

## Pre-launch (the day before)

- [ ] Run `bash scripts/launch-grep-scrub.sh` — must exit 0.
- [ ] Run `uv run pytest -m "not e2e" -q` — must pass.
- [ ] Run `uv run mkdocs build --strict` — must build clean.
- [ ] Repo transfer from `lhassa8/Efterlev` → `efterlev/efterlev` complete (see SPEC-01.62 maintainer-action). The destination repo exists and is **still private**.
- [ ] `gh repo view efterlev/efterlev` — confirm visibility is `private`; you haven't flipped accidentally.
- [ ] **GitHub Pages enable: timing depends on plan.** On GitHub Pro/Team/Enterprise, enable now while private (Settings → Pages → Source: "GitHub Actions"). On GitHub Free, Pages-on-private isn't available — Pages can only be enabled AFTER the visibility flip; that step is in the hour-0 sequence below. Not a launch blocker either way; just a sequencing detail that depends on the plan.
- [ ] All other A1-A7 maintainer-action queues worked through (Docker Hub org, npm namespace, branch protection apply, DCO app install, security review §8 sign-off, GovCloud walkthrough if maintainer has access).
- [ ] Sleep on it. The 24-hour pause is a feature; surprises tend to surface when fresh-eyes look at the same thing.

## Launch hour 0 — The flip

- [ ] Tag and build artifacts:
  ```bash
  # Bump version if needed
  # git tag v0.1.0 && git push origin v0.1.0  # this fires release-pypi.yml + release-container.yml + release-smoke.yml
  ```
- [ ] Confirm release workflows are running: `gh run list --limit 5 --repo efterlev/efterlev`
- [ ] Wait for release-smoke.yml matrix to complete green.
- [ ] Approve the `pypi` GitHub-environment deployment (manual gate per SPEC-05) once smoke is green.
- [ ] Confirm artifacts: `pip index versions efterlev`, `docker manifest inspect ghcr.io/efterlev/efterlev:v0.1.0`.
- [ ] **Flip repo visibility:** `efterlev/efterlev` → GitHub → Settings → Danger Zone → Change visibility → Public.
- [ ] **Enable GitHub Pages (if not already done in pre-launch).** Settings → Pages → Source: "GitHub Actions". On free-plan accounts this option is only available once the repo is public; do it now, immediately after the visibility flip, before triggering docs-deploy. Save.
- [ ] Trigger the docs deploy: `gh workflow run docs-deploy.yml --ref main --repo efterlev/efterlev`. (A visibility flip is a settings change, not a push, so it does NOT auto-fire `docs-deploy.yml`. The workflow has a `workflow_dispatch` trigger for exactly this case.)
- [ ] Watch the run: `gh run watch --repo efterlev/efterlev`. Build + deploy must succeed.
- [ ] Confirm `efterlev.com` resolves to the docs site (DNS-propagation can lag — give it up to 10 min).
- [ ] Enable GitHub Security Advisories on the now-public repo (Settings → Security → Code security and analysis).

## Launch hour 1 — Hacker News post

- [ ] Post to Hacker News. Title: `Show HN: Efterlev — open-source FedRAMP 20x scanner you can run locally`.
- [ ] Body: copy from `docs/launch/announcement-copy.md` § HN. Edit timing-sensitive phrases (Phase 2 authorization counts, etc.) with current numbers.
- [ ] Stay close to the post for the first 2 hours. Reply to substantive technical comments; ignore the inevitable "ha ha LLMs" comments.

## Launch hour 4 — Reddit + LinkedIn + dev.to

- [ ] Cross-post to r/devops, r/govcloud, r/fednews, r/cybersecurity. **Separate posts** — subreddits hate cross-posts. Use the per-subreddit framing in `announcement-copy.md`.
- [ ] LinkedIn post linking to the docs site.
- [ ] dev.to / Medium cross-post (longer narrative, "Why we built Efterlev").

## Launch hour 8 — DevSecOps Slack communities

- [ ] Post in OWASP Slack `#announcements` (or the equivalent appropriate channel).
- [ ] Post in CNCF Slack `#security` if relevant to the conversation.
- [ ] Kubernetes Slack `#security`. Tone: "I just shipped this; might be useful to people doing FedRAMP-adjacent work."

Slack posts are different from HN/Reddit — they're seen by communities of practitioners who'll evaluate quietly. Don't post the marketing copy; post a short note linking to docs and inviting questions.

## Day 1 — Blog post

- [ ] Publish "Why we built Efterlev" on dev.to and Medium (use the long-form draft from `docs/launch/announcement-copy.md` § dev.to/Medium).
- [ ] Link both cross-posts from a pinned GitHub Discussion on the repo. (mkdocs-material's blog plugin is a v0.2.0 follow-up — a pinned Discussion is the v0.1.0 substitute and keeps the docs-site nav uncluttered for now.)

## Day 2 — Design-partner outreach

- [ ] Send the five outreach emails from `docs/launch/design-partner-outreach.md`. Customize each with a current-news hook ("just saw your CEO's interview about the federal pipeline...").
- [ ] Track replies in a private spreadsheet. Don't follow up sooner than 5 business days.

## Day 3 — Open `good first issue` tickets

- [ ] Open 10 GitHub issues labeled `good first issue`. Each must have:
  - Clear scope (a sentence describing what's needed).
  - Pointer to the relevant area of the codebase (file path).
  - Expected effort (S/M/L).
  - "Maintainer-approved" label so contributors know it's actually wanted.
- [ ] Mix of types: 3 new detectors, 2 doc improvements, 2 small bugs, 2 test additions, 1 stretch goal (tutorial deepening).

## Day 7 — Public retrospective

- [ ] Open a GitHub Discussion: "Week 1 retrospective." Honest report on:
  - What landed (artifacts published, stars, PRs, issues).
  - What surprised us (good and bad).
  - What's next.
- [ ] Pin the discussion.

## 30-day success gates

Per the launch plan in `DECISIONS.md` 2026-04-23:

- **Green:** ≥500 stars, ≥3 external PRs merged, ≥1 "I ran this on real infra" story (issue, PR, or blog post), ≥1 design-partner conversation active.
- **Yellow:** 100–500 stars, 1–2 external PRs, no clear user story.
- **Red:** <100 stars, no external PRs, silence.

Green → continue Phase C as planned. Yellow → pause, reassess messaging, do a second-wave announcement with a case study. Red → treat as a positioning failure; return to planning before building more product.

## When the runbook is interrupted

If something goes wrong mid-runbook (the flip succeeds but a release workflow fails; the HN post is killed by a flag wave; etc.) — pause, consult [`failure-response.md`](failure-response.md), and resume only after the issue is addressed.

The runbook is a guideline, not a religion. The discipline is: every step you skip, you write down why.
