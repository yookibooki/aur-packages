---
engine:
  id: gemini
  model: gemma-4-26b-a4b-it
on:
  schedule:
    - cron: "17 */3 * * *"
  workflow_dispatch:
    inputs:
      command:
        description: "Optional command-mode instruction"
        required: false
        type: string
        default: ""
  slash_command:
    name: repo-assist
  reaction: "eyes"
source: githubnext/agentics/workflows/repo-assist.md@4bc8419fad05e6b032741cbfd189986700bcf71c
permissions: read-all
# Strict mode OFF: required to allow sandbox.agent=false below (the AWF
# firewall path cannot authenticate the gemini engine — see sandbox note).
# Blast radius stays small: read-all permissions, writes via safe-outputs.
strict: false
features:
  dangerously-disable-sandbox-agent: true
sandbox:
  # Agent sandbox (AWF) OFF: the firewall strips GEMINI_API_KEY from the
  # agent container and points the CLI at a proxy it cannot use
  # (gemini-cli ignores GEMINI_API_BASE_URL; gateway auth fails CLI-side
  # validation with exit 41). Unsandboxed, the CLI reads GEMINI_API_KEY
  # directly. MCP gateway stays on. Revisit if gh-aw/CLI fix gateway auth.
  agent: false
network:
  allowed: [defaults, github]
tools:
  bash: true
  github:
    toolsets: [all]
  repo-memory: true
---

# Repo Assist — aur-packages

Lean custom workflow (cut from the stock agentics template 2026-09-22):
engine pin kept, task-selection pre-step and threat-detection job
dropped. Smaller lock, less quota per run.

## Non-Command Mode
Runs every 3h plus /repo-assist commands. Triages open issues/PRs,
makes small focused fixes via safe-outputs, updates notes.json.

## Update discovery (every scheduled run)
There is no separate discover workflow — this is how packages stay
current. Each scheduled run MUST probe every `active: true` entry in
`packages/registry.json` for upstream updates:

1. Resolve the latest release for `<upstream>` (`gh release list -R`,
   honoring `allow_prerelease`; or `scripts/probe-upstream.py
   --upstream <upstream> --pkg <pkg>`).
2. Compare to the packaged `_realver` in `packages/<pkg>/PKGBUILD`.
3. If upstream is newer: run `scripts/update-pkgbuild.sh` (real
   checksums from real artifacts, never SKIP), regenerate `.SRCINFO`
   via `makepkg --printsrcinfo`, verify (`verify-package.sh`,
   `check-consistency.sh`), update `docs/packages/<pkg>.md`, and open
   a PR via safe-outputs. One PR per package.
4. Record the probe outcome (versions seen, updated or current) in
   memory and in the `docs/STATE.md` heartbeat.

## Memory
Schema version 1, 7 fields: version, cursors, issues, fixes, checks, completed_actions, priorities. Stored in.github/repo-assist/notes.json.

## Provider
Engine gemini id:gemini model:gemma-4-26b-a4b-it, fallback gemma-4-31b-it (manual edit + gh aw compile). Auth via GEMINI_API_KEY read directly (agent sandbox OFF — see frontmatter; the firewall path starves the CLI of the key and gateway auth fails CLI validation, exit 41). MCP gateway on. No threat-detection job in this lean build. Lock compiled with gh-aw v0.88.7.
