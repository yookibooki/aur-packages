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
| Schedule | Every 12 hours (default) |
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
| `scripts/issue-apply.py hold` | Hold/unhold a package based on issue or command |
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

## Hold/remove flows

- **Hold**: `scripts/issue-apply.py hold --pkg X` → sets `hold: true` in registry. Discover skips; verify on demand.
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

Repo Assist stores state in `.github/repo-assist/notes.json`.
The schema has 7 fields: version, cursors, issues, fixes, checks,
completed_actions, priorities. Repo Assist validates this file
before each run and updates it after.

## Monthly Activity Summary (Task 11)

Every non-command run that performs work updates the monthly
activity issue. Command-mode and no-op runs do not.

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

Repo Assist calls an OpenAI-compatible chat completions endpoint
(`/chat/completions`). Default provider is NOUS Research
(`https://inference-api.nousresearch.com/v1` with model `poolside/laguna-s-2.1:free`).

Any OpenAI-compatible provider works. Configure via repo secrets:

| Secret | Default | Purpose |
|--------|---------|---------|
| `NOUS_API_KEY` | *(required)* | API key for the inference provider |
| `NOUS_BASE_URL` | `https://inference-api.nousresearch.com/v1` | Base URL of the chat completions endpoint |
| `NOUS_MODEL` | `poolside/laguna-s-2.1:free` | Model identifier |

Run Repo Assist immediately:
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

- If `NOUS_API_KEY` is missing, Repo Assist posts a comment requesting it
  and skips model-backed tasks. Deterministic tasks still run.
- If `AUR_SSH_KEY` or `AUR_KNOWN_HOSTS` are missing, `push-aur.sh` fails
  hard. Repo Assist documents this and leaves the PR as draft.
- If `check-consistency.sh` fails, no commit is made. Check the output
  for the specific failure and fix it before retrying.
