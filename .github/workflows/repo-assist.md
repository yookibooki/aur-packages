---
engine:
  id: gemini
  model: gemini-3.5-flash-lite
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
    # gh-proxy: GitHub reads go through the pre-authenticated gh CLI in
    # bash — no github MCP server, so its ~45 tool schemas (each with
    # full JSONSchema + two base64 icon blobs, ~19k tokens/request)
    # never enter the model context. This is what makes the prompt fit
    # Gemma's 16k free-tier TPM. Agent already uses gh CLI for probing.
    mode: gh-proxy
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
Engine gemini id:gemini model:gemini-3.5-flash-lite (1M context; -lite IDs pass the CLI's flash remap unmapped, unlike *-flash which rebinds to 3.5-flash with its 20 req/day cap). Auth via GEMINI_API_KEY read directly (agent sandbox OFF — the firewall path starves the CLI of the key and gateway auth fails CLI validation, exit 41). Prompt diet (2026-09-22): github MCP server replaced with gh-proxy (reads via gh CLI in bash) — the ~45 MCP tool definitions with inline base64 icons cost ~19k input tokens/request against Gemma's 16k free-tier TPM, every request over budget. Only safeoutputs schemas remain in context. MCP gateway on. No threat-detection job in this lean build. Lock compiled with gh-aw v0.88.7.
