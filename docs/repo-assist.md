# Repo Assist — aur-packages integration

This document describes how Repo Assist operates in this
specific repository. The general Repo Assist documentation is in
`docs/workflows.md`. This file covers the aur-packages-specific
details that Repo Assist needs to know.

## What this repo is

This repository maintains Arch Linux AUR packages. Each package
is a binary tool distributed as a release asset from a GitHub
upstream. The registry (`packages/registry.json`) describes
how to find, download, and package each one.

## Repo Assist triggers

| Trigger | How |
|---------|-----|
| Schedule | Every 3 hours (per workflow frontmatter) |
| workflow_dispatch | Manual trigger, optional `command` input for command mode |
| Issues | Repo Assist investigates, labels, and triages |
| Issue comments | `/repo-assist <instructions>` runs command mode |
| Pull requests | Repo Assist reviews and can fix red checks |

## Repo Assist tools

Repo Assist calls these scripts directly for all operations.
Each is deterministic and tested — Repo Assist never improvises.

| Script | What Repo Assist uses it for |
|--------|------------------------------|
| `scripts/probe-upstream.py` | Before adding a package: infer asset pattern, version, archs from the upstream's latest release |
| `scripts/issue-apply.py add` | Scaffold PKGBUILD + registry entry after probing (checksums SKIP) |
| `scripts/issue-apply.py remove` | Remove a package based on issue or command |
| `scripts/update-pkgbuild.sh` | Update a PKGBUILD to a new version: download assets, compute sha256, rewrite version fields |
| `scripts/verify-package.sh` | Verify a PKGBUILD: syntax, checksums, .SRCINFO parity, makepkg, namcap |
| `scripts/check-consistency.sh` | Full cross-validation before any commit |
| `scripts/push-aur.sh` | Push updated PKGBUILDs to AUR (requires AUR_SSH_KEY, AUR_KNOWN_HOSTS) |

## Package lifecycle

1. **Request**: issue labeled `pkg-add` or `/repo-assist add <pkg> from <source>`
2. **Probe**: `scripts/probe-upstream.py` infers asset pattern
3. **Scaffold**: `scripts/issue-apply.py add` creates PKGBUILD (SKIP) + registry + note
4. **Resolve**: `scripts/update-pkgbuild.sh` downloads assets, writes real checksums
5. **Regenerate**: `makepkg --printsrcinfo > .SRCINFO`
6. **Verify**: `scripts/verify-package.sh` + `scripts/check-consistency.sh`
7. **Commit**: registry + PKGBUILD + .SRCINFO + per-package note
8. **Publish**: `scripts/push-aur.sh` pushes to AUR (can be deferred)

## Remove flow

- **Remove**: `scripts/issue-apply.py remove --pkg X` → sets `active: false`, moves `packages/X/` to `archive/X/`. Discover and push skip.

## Verification layers

Repo Assist runs these before creating any PR:

1. `bash -n` on all shell scripts
2. `shellcheck` on scripts and PKGBUILDs (when available)
3. `scripts/check-consistency.sh` — full cross-validation
4. `scripts/verify-package.sh` — per-package verification
5. `makepkg -s --noconfirm --noarchive` — full build (when available)
6. `namcap` on PKGBUILDs and artifacts (when available)

If any check fails due to Repo Assist's changes, the PR is not created.
Infrastructure failures are documented in the PR's Test Status section.

## Memory

Repo Assist uses gh-aw's `repo-memory` tool. The default memory is persisted
on the `memory/repo-assist` branch and mounted during the agent job at
`/tmp/gh-aw/repo-memory/default/`. The checked-in
`.github/repo-assist/notes.json` is only a bootstrap seed used when that
managed memory branch has no file yet; gh-aw validates and publishes the
mounted memory after the run.

The schema has 7 fields: version, cursors, issues, fixes, checks,
completed_actions, priorities.

## Guidelines specific to this repo

- **Read AGENTS.md first** — it defines the caretaker philosophy
  and trust model. Every PKGBUILD affects strangers who cannot audit it.
- **Never commit SKIP** — SKIP exists only in scaffolds before the
  first `update-pkgbuild.sh` run in the same job.
- **Halt when unsure** — if you cannot verify something, stop and
  leave evidence. Do not guess.
- **The registry is truth** — `packages/registry.json` is the single
  source of truth for package data. Workflows contain no package data.
- **`docs/research.md` is reference only** — it lists external agent
  tools and is not part of the agent reading order.

## Provider

The checked-in source is based on
`githubnext/agentics/workflows/repo-assist.md@4bc8419...`, with repository
specific frontmatter and deterministic package scripts. It is compiled with
gh-aw v0.88.7 to `.github/workflows/repo-assist.lock.yml`.

The current engine is Gemini CLI with model `gemma-4-26b-a4b-it` and the
repository secret `GEMINI_API_KEY`. Gemini CLI headless mode also requires
the explicit auth selection `GEMINI_DEFAULT_AUTH_TYPE=gemini-api-key`; the
workflow supplies that value through `engine.env`.

The Repo Assist memory branch is `memory/repo-assist`; the checked-in
`.github/repo-assist/notes.json` is only a bootstrap seed, not live run state.

## Run Repo Assist immediately
```bash
gh aw run repo-assist
```

Command mode (focus on specific task):
```bash
gh aw run repo-assist -F command="Run Task 9"
```

On-demand via any issue or PR:
```
/repo-assist <instructions>
```

## Troubleshooting

- If `GEMINI_API_KEY` is missing, activation fails before the agent starts.
- If Gemini reports "Invalid auth method selected", the agent environment
  must contain both `GEMINI_API_KEY` and
  `GEMINI_DEFAULT_AUTH_TYPE=gemini-api-key`.
- If the runner has no usable SSH access to `aur.archlinux.org`,
  `push-aur.sh` fails hard. Repo Assist documents this and leaves the PR as draft.
- If `check-consistency.sh` fails, no commit is made. Check the output
  for the specific failure and fix it before retrying.
