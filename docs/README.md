# Docs for agents

Read in this order. Everything here is kept current; if code and docs
disagree, code wins and you must update the doc in the same change.

1. `AGENTS.md` (repo root) — who you are, why this repo exists, what is
    fenced off. Start there.
2. `docs/STATE.md` — live repo status: heartbeat, halts, open questions.
    Read it next, before touching anything else, and update it before you
    leave.
3. `docs/packages/<name>.md` — per-package status, for any package you touch.
4. `docs/registry.md` — `packages/registry.json` schema, every field, the
    asset-pattern flags, `active` semantics.
5. `docs/repo-assist.md` — Repo Assist integration: triggers, tools,
    commands, memory schema, and this repo's conventions for the agent.
6. `docs/workflows.md` — automation architecture: how Repo Assist orchestrates
    the system and how scripts hand off to each other.
7. `docs/scripts.md` — every script, exact usage, what it reads and writes.
8. `docs/packages.md` — asset-pattern table with examples, scripts-vs-agent
    split, issue/command management, secrets.
9. `docs/changelog/` — one file per day, the running changelog. Append to
    today's file every run, even no-ops. Never edit prior days.

Not in the read order: `docs/research.md`. It is background reading on
external agent tools, kept for reference only, and is not part of this
system. Do not act on it.
