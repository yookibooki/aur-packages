# gitcrawl-bin

- upstream: https://github.com/openclaw/gitcrawl
- asset pattern: 3 (`version_in_asset=true`, `<name>_<version>_<triple>.tar.gz`,
  tag has `v` prefix)
- last-seen version: 0.11.0 (`_realver`, `pkgver` 0.11.0, `pkgrel` 1)
- last-verified: 2026-09-22 (`verify-package.sh`: live download, sha256 match; 0.11.0 bump verified by the discover run that opened PR #30)
- status: verified 2026-09-22 (checksums + `.SRCINFO`); origin still unrecovered, see below
- halt reason: none
- why this package exists: unknown. Predates the keeper system
  (before 2026-09-15). Recovery path:
  `git log --diff-filter=A -- packages/gitcrawl-bin/` — read the initial
  commit message and any linked issue. Until recovered, presume
  deliberately requested by the human who created this repo; do not remove,
  rename, or drop without a halt.
- re-probed 2026-09-21: upstream latest matches packaged version, no update.
- 2026-09-22: staged .SRCINFO corruption ([STRIPPED...]) reverted to HEAD; checksums re-verified via check-consistency. No version change.
- 2026-09-22: bumped 0.10.0 -> 0.11.0 by scripts/discover.sh
