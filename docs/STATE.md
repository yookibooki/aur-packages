# State

First thing every run reads. If this file disagrees with anything else,
this file wins for status, and you fix the loser in the same change.

- heartbeat: 2026-09-15T08:50Z — keeper docs created, no upstream re-verification this run.
  (Previous heartbeat note, kept for context: STATE.md + per-package notes +
  heartbeat ritual first written this run.)
- last full re-verification: never recorded under this system.
- halted packages: none recorded. (A halt here means: do not touch that
  package on schedule until the reason is resolved. See its note in
  `docs/packages/`.)
- open questions:
  - `gitcrawl-bin` tarball and `mpatch-bin` tarballs sit unpacked in
    `packages/` working dirs alongside `src/` — check whether build
    leftovers are committed and should be cleaned (see `.gitignore`).
  - No per-package note has a confirmed "why"; origins predate this system.
  - `docs/research.md` is reference-only; confirm it stays out of the
    agent reading order or delete it.

## Why the heartbeat exists

GitHub disables scheduled workflows after 60 days of *repository*
inactivity — commits, not runs. A quiet repo reads as dead and the cron
dies silently. So every scheduled run updates the `heartbeat:` line above
and commits, even when nothing changed. One line per run. Ugly,
load-bearing: it is the difference between decades and two months.
