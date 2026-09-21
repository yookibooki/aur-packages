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

Repo Assist runs a lean custom workflow (cut from the stock
`githubnext/agentics` template on 2026-09-22: `engine: id gemini /
model gemma-4-26b-a4b-it`, schedule every 3h, repo memory +
safe-outputs, no task-selection pre-step, no threat-detection job —
see `.github/workflows/repo-assist.md`). `lint.yml` is the
deterministic push/PR gate (containerized archlinux:base-devel).

## Last curated design (superseded by #19, see git history at 91412c5)

Repo Assist ran on the `gemini` gh-aw engine (maintainer decision,
2026-09-21, replacing pi), pinned model `gemma-4-26b-a4b-it` against
`generativelanguage.googleapis.com`, authenticated by the `GEMINI_API_KEY`
repo secret (set 2026-09-21 from the maintainer's environment).
`gemma-4-31b-it` was the documented manual fallback — gh-aw has no
automatic model failover, so recovery was an edit + recompile. The AWF
sandbox was re-enabled with the gemini switch (the pi-era reason to
disable it — third-party key plumbing — was void); `model-fallback:
false` and `token-steering: false` kept the gemma slugs verbatim through
the proxy, and threat detection was re-enabled with the sandbox.

Verified 2026-09-21: both gemma models returned correct functionCalls
via raw REST, and headless `gemini@0.55.1 -m gemma-4-26b-a4b-it` with
`GEMINI_API_KEY` answered (with `--skip-trust`, which gh-aw passes).
No CI run completed on this config: the same day the maintainer purged
the agent setup for a manual rebuild.

**Superseded pi routing (2026-09-21, same day):** pi needed the Nous
Research inference API with an `openai/` model prefix, a bare-model alias
because gh-aw's `engine.model` schema forbids `/` after the provider
prefix, and a hand-written "Configure pi custom provider" `models.json`
step to redirect the OpenAI provider at Nous. A bare or unknown-prefix
model instead compiled to `--model github-copilot/<m>`, which demanded a
format-checked `COPILOT_GITHUB_TOKEN` fine-grained PAT. All of that is
gone; the workflow no longer defines a custom-provider step. If pi is ever
revisited, start from git history rather than this file.

**Quota risk (open).** `tools.bash: true`, the default `max-turns` of 500,
and a slash command anyone can file on a public issue mean one run can
issue many Google requests. The AIC guardrail counts gh-aw credits, not
Google quota, so it does not bound this key. Watch for 429s; if they
appear, lower `max-turns` before touching the engine again.

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

- If `GEMINI_API_KEY` is missing, activation fails at "Validate
  GEMINI_API_KEY secret" before the agent starts and every run posts
  an `[aw] Repo Assist failed` issue.
- If `AUR_SSH_KEY` or `AUR_KNOWN_HOSTS` are missing, `push-aur.sh` fails
  hard. Repo Assist documents this and leaves the PR as draft.
- If `check-consistency.sh` fails, no commit is made. Check the output
  for the specific failure and fix it before retrying.
