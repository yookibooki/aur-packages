# State

First thing every run reads, after `AGENTS.md`. If this file disagrees with
anything else, this file wins for status, and you fix the loser in the same
change.

- heartbeat: 2026-09-15T12:22Z — issue #4 (pkg-remove openhuman-bin) applied by keeper run; package archived (duplicate in AUR as openhuman-core-bin). registry now 4 packages. last
  state update (d2bed0b → 0030636): (1) run_gh_safe in probe-upstream.py
  prevents exit-2 cascade from single gh API failure, (2) field extraction
  rewritten body-first in bash+jq with nested-parser unwrapping, (3) replaced
  inline Python inside \$(...) that was poisoned by ) and ] characters (bash
  treated them as closing the command substitution, garbling --upstream arg),
  (4) fixed Python heredoc EOF at 14 spaces not recognized by bash after
  YAML strip, (5) added --as root to makepkg in Docker (runner lacks makepkg,
  container runs as root, makepkg refuses). Issue #3 progressed to makepkg
  stage in run 34964107817 but failed there. Awaiting next CI run to verify
  full pipeline completes and openhuman-bin lands in registry.
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
