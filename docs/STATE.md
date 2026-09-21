# State

First thing every run reads, after `AGENTS.md`. If this file disagrees with
anything else, this file wins for status, and you fix the loser in the same
change.

This file is capped. When the heartbeat log below exceeds 50 entries, move
the oldest to `docs/archive/STATE-<year>.md` (create it if needed). Old
closed questions: keep at most 5 closed entries in this file; move older
closed ones to the same archive. Open questions are never pruned.

- heartbeat: 2026-09-21T17:00Z — this run: diagnosed the daily schedule
  failures (activation requires COPILOT_GITHUB_TOKEN for pi+bare model;
  never set — see changelog 2026-09-21), rerouted the engine to pi on
  the `openai/` prefix so a third-party OpenAI-compatible key rides
  gh-aw's native OPENAI_API_KEY broker (lock recompiled, v0.88.7),
  pushed the long-unpushed 09-15 sandbox-off work alongside it, removed
  the hold feature (#5), fixed check-consistency expectations (#9, #10 —
  gate green locally), verify.yml docs (#11), stale NOUS secrets docs
  (#12), update-pkgbuild input validation (#13), and the minor batch
  (#14). Getting main's Lint gate green for the first time since cutover
  (run 35624285789) required three latent fixes its early failure had
  masked: shellcheck SC2043 one-element loop (83951b1), unescaped `$p`
  expanded by lint.yml's `set -u` shell (2cd0aea), and verify-package.sh
  PKGBUILD shellcheck severity plus makepkg needing a writable BUILDDIR
  — now run from a temp copy (dc4c963). Maintainer then clarified
  credentials: no OpenAI/Anthropic access, only free models on the Nous
  inference API; b.ai is dead as a provider choice. Smoke-tested the
  Nous key live: `upstage/solar-pro4:free` broken upstream (400 "missing
  tags" → persistent 500s); pinned `poolside/laguna-s-2.1:free`
  (chat + function tools verified, 262K ctx), via a schema-legal
  gh-aw alias + models.json wire id. Set repo secret OPENAI_API_KEY to
  the maintainer-provided Nous key. **Open: prove the first green
  Repo Assist dispatch run, then close the [aw] failure issues;
  `BAI_API_KEY` then deletable.** See `docs/repo-assist.md` "Provider".
- heartbeat: 2026-09-15 — this run: (1) maintainer confirmed the legacy
  workflows were deleted intentionally, no archive wanted; fixed the four
  dangling references to `docs/legacy-workflows/` (AGENTS.md, docs/README.md,
  docs/workflows.md, STATE.md) to point to git history instead. (2) Moved
  the changelog out of AGENTS.md; per maintainer it is now one file per day
  in `docs/changelog/` (entries carry no date prefix; the filename is the
  date; prior days never edited). (3) Added the STATE.md cap rule above:
  heartbeat log rotates at 50 entries, closed questions at 5. Unrelated
  pre-existing breakage left open: check-consistency.sh expects
  `.github/workflows/repo-assist.yml` but the file is
  `repo-assist.lock.yml`, and expects sections absent from
  `.github/workflows/repo-assist.md`. Not falsifiable from here which name
  is intended — needs the Repo Assist config or next run to resolve.
- heartbeat: 2026-09-15T12:30Z — Repo Assist integrated as primary
  automation; old 7 workflows removed, lint.yml kept; notes.json
  initialized; check-consistency and docs updated for the new architecture.
- heartbeat: 2026-09-15T12:24Z — issue #4 removed; approval gate for
  pkg-remove eliminated; run_gh_safe + field extraction fixes in
  probe-upstream.py; issue #3 reached makepkg but failed there (run
  34964107817), awaiting next CI run.
- last full re-verification: never recorded under this system. A full
  re-verification means: fresh clone, clean chroot, every package rebuilt
  from source, every checksum re-derived, every `.SRCINFO` regenerated and
  diffed. Until that has run, every package is `carried-over`.
- halted packages: none recorded. (A halt here means: do not touch that
  package on schedule until the reason is resolved. See its note in
  `docs/packages/`.)

## Open questions

1. **CLOSED 2026-09-21: check-consistency.sh vs the actual Repo Assist
   filenames.** The script was the loser: it was fixed to validate
   `repo-assist.lock.yml` triggers and `repo-assist.md` sections that
   actually exist (issues #9/#10). `repo-assist.yml` was never meant to
   exist; the compiled workflow is `.lock.yml`, per `docs/repo-assist.md`
   and `gh aw compile` behavior (verified v0.88.7).

2. **Origin of every package is unknown.** All four predate the keeper
   system. Per-package notes carry a recovery path
   (`git log --diff-filter=A -- packages/<pkg>/`) and default to "presume
   deliberately requested; do not remove, rename, or drop without a halt."
   Recover what you can on the next run that has spare capacity.

3. **`docs/research.md`** is reference-only. It stays out of the agent
   reading order (see `docs/README.md`). Leave it in place unless it grows
   enough to confuse a cold reader; if so, delete it.

4. **CLOSED 2026-09-15: the add flow closes the SKIP lifecycle in the same
   job** (probe → issue-apply add → update-pkgbuild → printsrcinfo →
   check-consistency, with rollback). This was the failure behind issue #2.

5. **CLOSED 2026-09-15: leftovers are gitignored, not committed.** No
   tarballs or `src/` tracked under `packages/`.

## Why the heartbeat exists

GitHub disables scheduled workflows after 60 days of *repository* inactivity
— commits, not runs. A quiet repo reads as dead and the cron dies silently.
So every scheduled run updates the `heartbeat:` log above and commits, even
when nothing changed. One entry per run. History beyond the cap lives in
`docs/archive/` and in git. Ugly, load-bearing: it is the difference between
decades and two months.
