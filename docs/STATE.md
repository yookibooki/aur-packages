# State

First thing every run reads, after `AGENTS.md`. If this file disagrees with
anything else, this file wins for status, and you fix the loser in the same
change.

- heartbeat: 2026-09-15T12:00Z — constitution rewritten (Trust and What you
  can do added; machinery vs. release path fenced); STATE refreshed; four
  per-package notes given a recovery path for "why". No upstream
  re-verification this run.
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

2. **`.github/workflows/` is not visible in the source tree**, but
   `docs/workflows.md` describes six workflows in detail (issue-manager,
   discover, verify, publish, watcher, runner, maintainer, lint — that is
   eight, the doc is the authority). Verify the workflows are committed.
   If they are not, `docs/workflows.md` describes a system that does not
   exist and must be corrected before it is trusted.

3. **`.SRCINFO` files are not visible in the source tree** for any of the
   four packages. `scripts/check-consistency.sh` requires them. Verify they
   exist and are current. If missing, this is a real red and must be fixed
   before any push.

4. **`scripts/issue-apply.py` no longer writes a stub `.SRCINFO`.** As of
   this rewrite, the scaffolder writes only the PKGBUILD and the per-package
   note; `.SRCINFO` is regenerated downstream by makepkg. The
   `issue-manager` workflow must be verified to run
   `scripts/update-pkgbuild.sh` and `makepkg --printsrcinfo` between
   `issue-apply.py add` and any commit. If it does not, the add flow will
   commit a package with placeholder checksums and no `.SRCINFO` — which
   `check-consistency.sh` will correctly reject, so nothing lands on `main`,
   but the issue will look stuck. Fix the workflow, not the checker.

5. **Unpacked tarballs in `packages/` working directories.** `gitcrawl-bin`
   and `mpatch-bin` have tarball and `src/` leftovers alongside the
   PKGBUILD. Confirm they are gitignored or delete them. Do not commit
   build leftovers.

6. **`docs/research.md`** is reference-only. It stays out of the agent
   reading order (see `docs/README.md`). Leave it in place unless it grows
   enough to confuse a cold reader; if so, delete it.

## Why the heartbeat exists

GitHub disables scheduled workflows after 60 days of *repository* inactivity
— commits, not runs. A quiet repo reads as dead and the cron dies silently.
So every scheduled run updates the `heartbeat:` line above and commits, even
when nothing changed. One line per run. Ugly, load-bearing: it is the
difference between decades and two months.
