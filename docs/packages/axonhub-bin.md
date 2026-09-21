# axonhub-bin

- upstream: https://github.com/looplj/axonhub
- asset pattern: 3 (`version_in_asset=true`, `<name>_<version>_<triple>.zip`,
  tag has `v` prefix; tracks prereleases)
- last-seen version: 1.0.0-beta10 (`_realver`, `pkgver` 1.0.0_beta10,
  `pkgrel` 1)
- last-verified: 2026-09-22 (`verify-package.sh`: live download, sha256 match)
- status: verified 2026-09-22 (checksums + `.SRCINFO`); origin still unrecovered, see below
- halt reason: none
- why this package exists: unknown. Predates the keeper system
  (before 2026-09-15). Recovery path:
  `git log --diff-filter=A -- packages/axonhub-bin/` — read the initial
  commit message and any linked issue. Until recovered, presume
  deliberately requested by the human who created this repo; do not remove,
  rename, or drop without a halt. Note it tracks prereleases
  (`allow_prerelease`), so version churn is expected.
- re-probed 2026-09-21: upstream latest matches packaged version, no update.
- 2026-09-22: staged .SRCINFO corruption ([STRIPPED...]) reverted to HEAD; checksums re-verified via check-consistency. No version change.
