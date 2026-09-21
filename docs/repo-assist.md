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

Repo Assist runs on the `pi` gh-aw engine (maintainer's choice at setup,
pinned in `.github/workflows/repo-assist.md`) on the **Nous Research
inference API** (`https://inference-api.nousresearch.com/v1`,
OpenAI-compatible `chat/completions`). Only `:free` models work with
this key; the pinned model is `poolside/laguna-s-2.1:free` (262K
context, function tools verified 2026-09-21).
`inference-api.nousresearch.com` is in `network.allowed`. Threat
detection is forced off: it only runs inside the gh-aw agent sandbox,
which is disabled (maintainer decision, 2026-09-15).

**Routing (resolved 2026-09-21, verified against compiled output and pi
0.84.3 source):** a bare or unknown-prefix model compiles to
`--model github-copilot/<m>`, so activation demands
`COPILOT_GITHUB_TOKEN` — format-checked as a real fine-grained PAT —
and inference would go to GitHub's Copilot endpoint. An earlier note
here (2026-09-15) blamed secret plumbing only; it was doubly broken:
`engine.env` secrets never appear in the compiled agent step env at
all, so `BAI_API_KEY` was a no-op. The working path is the `openai/`
model prefix: gh-aw brokers `OPENAI_API_KEY`/`CODEX_API_KEY` natively
(presence-validated, no format check, injected into the agent step),
and the workflow's "Configure pi custom provider" step names its
models.json provider `openai` with the Nous baseUrl and the exact
catalog model id; pi's provider composer keeps models.json entries when
the extension registers no `models`/`baseUrl`. The engine.model token
`laguna-s-2.1` is a schema-legal alias that pi partial-matches to the
models.json id `poolside/laguna-s-2.1:free` (gh-aw's schema forbids
`/` after the prefix; pi would strip a `:free` suffix as a bogus
thinking level), and the full id goes on the wire. **The repo secret
`OPENAI_API_KEY` holds the Nous API key** (set 2026-09-21 from the
maintainer-provided key). `BAI_API_KEY` is unreferenced and can be
deleted. `upstage/solar-pro4:free` is broken upstream (400 "missing
tags" — it wants `tags.user`, which pi cannot send — then persistent
500s); alternative verified working with function tools:
`inclusionai/ling-3.0-flash-fin:free`.

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

- If `OPENAI_API_KEY` is missing, activation fails at "Validate
  CODEX_API_KEY or OPENAI_API_KEY secret" before the agent starts and
  every run posts an `[aw] Repo Assist failed` issue. The secret holds
  the Nous key (see Provider above).
- If `AUR_SSH_KEY` or `AUR_KNOWN_HOSTS` are missing, `push-aur.sh` fails
  hard. Repo Assist documents this and leaves the PR as draft.
- If `check-consistency.sh` fails, no commit is made. Check the output
  for the specific failure and fix it before retrying.
