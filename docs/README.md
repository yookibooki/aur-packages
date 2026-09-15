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
   asset-pattern flags, `hold`/`active` semantics.
5. `docs/workflows.md` — every workflow, its triggers, what it does, and how
   they hand off to each other.
6. `docs/scripts.md` — every script, exact usage, what it reads and writes.
7. `docs/packages.md` — asset-pattern table with examples, watcher-vs-scripts
   split, issue-only management, secrets.

Not in the read order: `docs/research.md`. It is background reading on
external agent tools, kept for reference only, and is not part of this
system. Do not act on it.
