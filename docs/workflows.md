# Automation architecture

Repo Assist (`.github/workflows/repo-assist.lock.yml`, compiled from `repo-assist.md`) is the primary automation
for this repository. It runs every 3 hours and on-demand via
`/repo-assist` commands. Since the 2026-09-22 lean rebuild it is a
minimal workflow: engine pin + repo memory + safe-outputs, with no
weighted task selection, no threat-detection job, and no monthly
summary issue. It orchestrates all repository maintenance
tasks; deterministic operations are performed by scripts in
`scripts/`.

## How Repo Assist works (lean build, 2026-09-22)

Each run triages open issues/PRs, makes small focused fixes through
safe-outputs, and updates memory (`notes.json`).

## Deterministic tools

Repo Assist calls these scripts directly for all precise operations.
It never improvises checksums, version comparison, or registry mutations.

| Script | What it does |
|--------|-------------|
| `scripts/probe-upstream.py` | Infers asset pattern, version, archs from a GitHub upstream's latest release. Outputs JSON for `scripts/issue-apply.py`. |
| `scripts/issue-apply.py add` | Scaffolds `packages/<pkg>/PKGBUILD` (checksums SKIP), registry entry, and per-package note. Does NOT write .SRCINFO. |
| `scripts/issue-apply.py remove` | Sets `active:false`, moves `packages/<pkg>/` to `archive/<pkg>/`. |
| `scripts/update-pkgbuild.sh` | Downloads arch assets in parallel, verifies sha256, rewrites `_realver`, `pkgver`, `pkgrel`, `source_*`, `sha256sums_*`. Erases SKIP. |
| `scripts/verify-package.sh` | Fast gate: `bash -n`, shellcheck, SKIP check, `.SRCINFO` diff, `makepkg --verifysource`, namcap. |
| `scripts/check-consistency.sh` | Cross-validates registry schema, PKGBUILD↔.SRCINFO parity, workflow triggers, forbidden strings. Must stay green. |
| `scripts/push-aur.sh` | Copies PKGBUILDs from artifacts, regenerates .SRCINFO, pushes to AUR over SSH with pinned host key. |

## Schedule

| Trigger | Cadence | Action |
|---------|---------|--------|
| Schedule | Every 3h | Full Repo Assist run (task selection + execution) |
| workflow_dispatch | On-demand | Command mode (`-F command="..."`) or manual trigger |
| Issues opened/edited | Event-driven | Repo Assist investigates, labels, or escalates |
| Issue comments | Event-driven | Command mode if `/repo-assist`, otherwise triage |
| Pull requests | Event-driven | Review and auto-fix red checks |

## SKIP lifecycle

1. `scripts/issue-apply.py add` scaffolds PKGBUILD with `SKIP` checksums
2. `scripts/update-pkgbuild.sh` resolves real checksums (erases SKIP)
3. `makepkg --printsrcinfo` generates `.SRCINFO`
4. `scripts/check-consistency.sh` validates everything before commit
5. Commit: registry + PKGBUILD + .SRCINFO + per-package note

`SKIP` exists ONLY in scaffolds between creation and first successful
`update-pkgbuild.sh` run in the same job. Never committed.

## Heartbeat

Every scheduled Repo Assist run updates `docs/STATE.md` with a
heartbeat timestamp. This is the commit that prevents GitHub from
disabling scheduled workflows after 60 days of repository inactivity.

## Legacy workflows

The 7 workflows that preceded Repo Assist (issue-manager, discover, verify,
publish, watcher, maintainer, runner) were removed when Repo Assist became
the primary automation. Intentionally not archived — their full history
remains in git if ever needed:
`git log --diff-filter=D -- .github/workflows/`

The `lint.yml` workflow (push/PR gate with namcap + shellcheck) is
kept as-is — it runs deterministically and provides fast feedback
before Repo Assist runs.
