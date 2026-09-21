# mpatch-bin

- upstream: https://github.com/Romelium/mpatch
- asset pattern: 1 (`ver_in_url=true`, tag has `v` prefix)
- last-seen version: 1.6.4 (`_realver`, `pkgver` 1.6.4, `pkgrel` 1)
- last-verified: never recorded under this system
- status: carried-over (present with real checksums and `.SRCINFO`, not
  re-verified since keeper docs began)
- halt reason: none
- why this package exists: unknown. Predates the keeper system
  (before 2026-09-15). Recovery path:
  `git log --diff-filter=A -- packages/mpatch-bin/` — read the initial
  commit message and any linked issue. Until recovered, presume
  deliberately requested by the human who created this repo; do not remove,
  rename, or drop without a halt.
- re-probed 2026-09-21: upstream latest matches packaged version, no update.
- 2026-09-22: staged .SRCINFO corruption ([STRIPPED...]) reverted to HEAD; checksums re-verified via check-consistency. No version change.
