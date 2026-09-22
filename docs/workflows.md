# Automation architecture

Two workflows own this repository (2026-09-22 token redesign):

- **`discover.yml`** — plain, zero-token, runs every 3 hours:
  `scripts/discover.sh` probes every active registry entry, runs the full
  bump transaction on drift (real checksums → verify → consistency), and
  opens one PR per package. This is where the old scheduled Repo Assist
  update-discovery duty moved. Two load-bearing facts: it needs the repo
  setting `actions/permissions/workflow.can_approve_pull_request_reviews
  = true` (enabled 2026-09-22 with maintainer approval — otherwise `gh
  pr create` fails "GitHub Actions is not permitted to create or
  approve pull requests"; the create failure now surfaces gh's real
  error in the run log), and GitHub's anti-cascade rule means PRs opened
  with the workflow token do NOT trigger `lint.yml` themselves — the
  creating run's in-transaction verification (sha256/printsrcinfo/
  verify-package/check-consistency) is their gate; maintainer merges
  re-trigger CI on `main` normally.
- **Repo Assist** (`.github/workflows/repo-assist.lock.yml`, compiled from
  `repo-assist.md`) — the AI agent, on-demand ONLY: `/repo-assist`
  commands, issue/PR events, manual dispatch. It has NO schedule;
  `max-turns: 12` is compiled in but NOT enforced on the gemini engine
  (only claude_harness reads `GH_AW_MAX_TURNS` — see
  `docs/upstream-gh-aw.md`); budget target: <100k tokens per run,
  <5k system prompt, <20 requests (measured in
  `docs/changelog/2026-09-22.md`). No weighted task selection, no
  threat-detection job, no gh-aw repo-memory (state lives in git docs).

## How Repo Assist works (token redesign, 2026-09-22)

Each run triages the triggering issue/PR or executes one command, makes
small focused fixes through safe-outputs, and comments the result. It
never probes upstreams — that is `discover.yml`'s deterministic job.

## Deterministic tools

Workflows call these scripts directly for all precise operations.
No model ever improvises checksums, version comparison, or registry
mutations.

| Script | What it does |
|--------|-------------|
| `scripts/discover.sh` | Scheduled discovery loop: probe every active registry entry (`probe-upstream.py --latest-tag-only --newer-than`), run the bump transaction on drift, open one PR per package, keep-alive heartbeat when the repo is silent >10d. |
| `scripts/probe-upstream.py` | Infers asset pattern, version, archs from a GitHub upstream's latest release. Outputs JSON for `scripts/issue-apply.py`. `--latest-tag-only [--newer-than V]` is the fast discovery probe (exit 4 = not newer). |
| `scripts/issue-apply.py add` | Scaffolds `packages/<pkg>/PKGBUILD` (checksums SKIP), registry entry, and per-package note. Does NOT write .SRCINFO. |
| `scripts/issue-apply.py remove` | Sets `active:false`, moves `packages/<pkg>/` to `archive/<pkg>/`. |
| `scripts/update-pkgbuild.sh` | Downloads arch assets in parallel, verifies sha256, rewrites `_realver`, `pkgver`, `pkgrel`, `source_*`, `sha256sums_*`. Erases SKIP. |
| `scripts/verify-package.sh` | Fast gate: `bash -n`, shellcheck, SKIP check, `.SRCINFO` diff, `makepkg --verifysource`, namcap. |
| `scripts/check-consistency.sh` | Cross-validates registry schema, PKGBUILD↔.SRCINFO parity, workflow triggers, forbidden strings. Must stay green. |
| `scripts/push-aur.sh` | Copies PKGBUILDs from artifacts, regenerates .SRCINFO, pushes to AUR over SSH with pinned host key. |

## Schedule

| Trigger | Cadence | Action |
|---------|---------|--------|
| `discover.yml` schedule | Every 3h | Zero-token discovery: probe + bump + PR via `scripts/discover.sh` |
| repo-assist `workflow_dispatch` | On-demand | Command mode (`-F command="..."`) or manual trigger |
| Issues opened/edited | Event-driven | Activation only on `/repo-assist`; otherwise no-op |
| Issue comments | Event-driven | Command mode if `/repo-assist`, otherwise no-op |
| Pull requests / discussions | Event-driven | `/repo-assist` in body → command mode |

`check-consistency.sh` enforces the split: `discover.yml` MUST contain a
schedule, `repo-assist.lock.yml` MUST NOT.

## SKIP lifecycle

1. `scripts/issue-apply.py add` scaffolds PKGBUILD with `SKIP` checksums
2. `scripts/update-pkgbuild.sh` resolves real checksums (erases SKIP)
3. `makepkg --printsrcinfo` generates `.SRCINFO`
4. `scripts/check-consistency.sh` validates everything before commit
5. Commit: registry + PKGBUILD + .SRCINFO + per-package note

`SKIP` exists ONLY in scaffolds between creation and first successful
`update-pkgbuild.sh` run in the same job. Never committed.

## Heartbeat

GitHub disables scheduled workflows after 60 days of repository
inactivity, so something must commit regularly. In order of preference:
(1) real activity — maintainer runs and merged PRs; (2) `discover.sh`
commits `docs/heartbeat.log` when the repo has been silent for 10+ days
(keepalive guard, runs under `GITHUB_ACTIONS` only); (3) maintainer-run
heartbeats in `docs/STATE.md`.

## Legacy workflows

The 7 workflows that preceded Repo Assist (issue-manager, discover, verify,
publish, watcher, maintainer, runner) were removed when Repo Assist became
the primary automation. Intentionally not archived — their full history
remains in git if ever needed:
`git log --diff-filter=D -- .github/workflows/`

The `lint.yml` workflow (push/PR gate with namcap + shellcheck) is
kept as-is — it runs deterministically and provides fast feedback
before Repo Assist runs.
