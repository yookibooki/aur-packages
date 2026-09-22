---
engine:
  id: gemini
  model: gemini-3.5-flash-lite
max-turns: 12
on:
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
  # agent container and points the CLI at a proxy it cannot use (gemini-cli
  # ignores GEMINI_API_BASE_URL; gateway auth fails CLI-side validation,
  # exit 41). Unsandboxed, the CLI reads GEMINI_API_KEY directly.
  agent: false
network:
  allowed: [defaults, github]
tools:
  bash: true
  github:
    # gh-proxy: GitHub reads go through the pre-authenticated gh CLI in
    # bash — no github MCP server, so its ~45 tool schemas (JSONSchema +
    # base64 icons, ~19k tokens/request) never enter model context.
    mode: gh-proxy
---

# Repo Assist — aur-packages

On-demand only: `/repo-assist` commands, issue/PR events, manual dispatch.
NO schedule — scheduled update discovery is the zero-token script
workflow `.github/workflows/discover.yml` (`scripts/discover.sh`). Never
probe upstreams for updates unless explicitly asked. Recent state lives
in `docs/STATE.md` and `docs/changelog/`.

## Non-Command Mode

Triage the triggering issue/PR, make small focused fixes via
safe-outputs, comment the result. Token discipline: short commands,
`head`/`grep` instead of file dumps, no exploration beyond the trigger.

## Command Mode

Execute the `/repo-assist <instructions>` (or `command` input) exactly,
via the deterministic scripts (`docs/repo-assist.md` has the table):
`probe-upstream.py`, `issue-apply.py add|remove`, `update-pkgbuild.sh`,
`verify-package.sh`, `check-consistency.sh`, `push-aur.sh`.
Never improvise checksums or registry edits. Never commit SKIP.
Halt when unsure; leave evidence in a comment instead of guessing.

## Memory

No gh-aw repo-memory (disabled for token budget). Durable state lives
in git: `docs/STATE.md` heartbeats, `docs/changelog/<date>.md`, issues.
Record anything durable in a few lines via safe-outputs.

## Budget

Hard cap `max-turns: 12`; target <100k tokens per run and <5k system
prompt. Prefer one decisive command over surveys; do not re-read files
already shown to you.
