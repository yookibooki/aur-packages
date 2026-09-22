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
| Schedule | **None** — the agent is on-demand only; 3h scheduled discovery is `.github/workflows/discover.yml` (zero tokens) |
| workflow_dispatch | Manual trigger, optional `command` input for command mode |
| Issues | Activation only when body starts with `/repo-assist` |
| Issue comments | `/repo-assist <instructions>` runs command mode |
| Pull requests | `/repo-assist` in the PR body runs command mode |

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
| `scripts/push-aur.sh` | Publish the committed PKGBUILDs to the AUR (run by `publish.yml`, which materializes AUR_SSH_KEY / AUR_KNOWN_HOSTS first) |
| `scripts/discover.sh` | The 3h discovery loop behind `discover.yml`: probe → bump → verify → PR (zero tokens) |

## Package lifecycle

Standing duty (every 3h): `scripts/discover.sh`, run by
`.github/workflows/discover.yml`, probes each active registry entry for
upstream updates and bumps outdated packages through the full verify
transaction — zero AI tokens. Repo Assist is not involved unless a human
opens or comments on the PR. The add/remove flows below reuse the same
scripts.

1. **Request**: issue labeled `pkg-add` or `/repo-assist add <pkg> from <source>`
2. **Probe**: `scripts/probe-upstream.py` infers asset pattern
3. **Scaffold**: `scripts/issue-apply.py add` creates PKGBUILD (SKIP) + registry + note
4. **Resolve**: `scripts/update-pkgbuild.sh` downloads assets, writes real checksums
5. **Regenerate**: `makepkg --printsrcinfo > .SRCINFO`
6. **Verify**: `scripts/verify-package.sh` + `scripts/check-consistency.sh`
7. **Commit**: registry + PKGBUILD + .SRCINFO + per-package note
8. **Publish**: `.github/workflows/publish.yml` runs `scripts/push-aur.sh`
   on every merge that touches `packages/**` (and on manual dispatch).
   Repo Assist only needs to publish when asked out-of-band; the standing
   duty belongs to the workflow.

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

Since the 2026-09-22 token redesign gh-aw's `repo-memory` tool is
**disabled** (its prompt file rode on every request; budget target <5k
system tokens). Durable state lives in git instead: `docs/STATE.md`
heartbeats, `docs/changelog/<date>.md`, issue threads, and the
per-package notes in `docs/packages/<pkg>.md`. The old bootstrap seed
`.github/repo-assist/notes.json` was deleted; the remote branch
`memory/repo-assist` is legacy and unmounted (delete it whenever).

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

The current engine is Gemini CLI with model `gemini-3.5-flash-lite` and
the repository secret `GEMINI_API_KEY`. Gemini CLI headless mode also
requires the explicit auth selection `GEMINI_DEFAULT_AUTH_TYPE=gemini-api-key`;
the workflow supplies that value through `engine.env`. Budget controls
(frontmatter): `max-turns: 12` hard cap per run; target totals in
`docs/workflows.md`. gh-proxy keeps the ~45 github MCP tool schemas
(~19k tokens/request) out of context.

The legacy memory branch `memory/repo-assist` is no longer mounted
(repo-memory disabled); `.github/repo-assist/notes.json` was removed.

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
