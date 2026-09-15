# State

First thing every run reads, after `AGENTS.md`. If this file disagrees with
anything else, this file wins for status, and you fix the loser in the same
change.

- heartbeat: 2026-09-15T15:00Z — fixed the pkg-add flow end-to-end
  after live CI replay on issue #3 (was stuck since #2): root
  cause was dual — (1) probe-upstream.py exited 2 on any single
  gh API failure (no retry, no fallback for 90MB downloads),
  (2) issue-manager field extraction read ISSUE_BODY as env
  var that was empty in some CI event contexts while parser
  output shape varied across issue-ops/parser versions, so both
  parser and regex paths missed the source URL → status=invalid
  "Give a source" loop kept #2 and #3 stuck. Now body-first
  extraction in bash+jq, and probe uses soft-fallback gh calls.
  All 4 registry rows reproduced exactly. Pushed d2bed0b.
  Open questions 2–5 closed; live commit of a new package still
  needs a CI run (sandbox downloads too slow).
- last full re-verification: never recorded under this system. A full
  re-verification means: fresh clone, clean chroot, every package rebuilt
  from source, every checksum re-derived, every `.SRCINFO` regenerated and
  diffed. Until that has run, every package is `carried-over`.
- halted packages: none recorded. (A halt here means: do not touch that
  package on schedule until the reason is resolved. See its note in
  `docs/packages/`.)

## Open questions

1. **Origin of every package is unknown.** All four predate the keeper
   system. Per-package notes now carry a recovery path
   (`git log --diff-filter=A -- packages/<pkg>/`) and default to "presume
   deliberately requested; do not remove, rename, or drop without a halt."
   Recover what you can on the next run that has spare capacity.

2. **CLOSED 2026-09-15: workflows are committed.** `.github/workflows/`
  holds discover, issue-manager, lint, maintainer, publish, runner, verify,
  watcher (eight; the "six" count in the old question was wrong).

3. **CLOSED 2026-09-15: `.SRCINFO` files exist and are current.**
  `git ls-files` shows all four tracked and `check-consistency.sh` passes.

4. **CLOSED 2026-09-15: the add flow now closes the SKIP lifecycle in the
  same job.** `issue-manager.yml` runs probe → `issue-apply.py add` →
  `update-pkgbuild.sh` (erases SKIP) → `makepkg --printsrcinfo` →
  `check-consistency.sh`, with rollback on any failure. This was the exact
  failure behind issue #2 (`needs-info`, stuck open): scaffold-then-check
  could never pass. Docs (`workflows.md`, `scripts.md`, `packages.md`)
  updated to describe the real flow.

5. **CLOSED 2026-09-15: leftovers are gitignored, not committed.**
  `git ls-files` shows no tarballs or `src/` under `packages/`; `.gitignore`
  covers `*.tar.gz`, `src/`, `pkg/`. Working-tree only — leave for the
  builder, never commit.

6. **`docs/research.md`** is reference-only. It stays out of the agent
   reading order (see `docs/README.md`). Leave it in place unless it grows
   enough to confuse a cold reader; if so, delete it.

## Why the heartbeat exists

GitHub disables scheduled workflows after 60 days of *repository* inactivity
— commits, not runs. A quiet repo reads as dead and the cron dies silently.
So every scheduled run updates the `heartbeat:` line above and commits, even
when nothing changed. One line per run. Ugly, load-bearing: it is the
difference between decades and two months.
