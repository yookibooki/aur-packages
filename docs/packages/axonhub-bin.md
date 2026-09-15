# axonhub-bin

- upstream: https://github.com/looplj/axonhub
- asset pattern: 3 (`version_in_asset=true`, `<name>_<version>_<triple>.zip`,
  tag has `v` prefix; tracks prereleases)
- last-seen version: 1.0.0-beta10 (`_realver`, `pkgver` 1.0.0_beta10,
  `pkgrel` 1)
- last-verified: never recorded under this system
- status: carried-over (present with real checksums and `.SRCINFO`, not
  re-verified since keeper docs began)
- halt reason: none
- why this package exists: unknown. Predates the keeper system
  (before 2026-09-15). Recovery path:
  `git log --diff-filter=A -- packages/axonhub-bin/` — read the initial
  commit message and any linked issue. Until recovered, presume
  deliberately requested by the human who created this repo; do not remove,
  rename, or drop without a halt. Note it tracks prereleases
  (`allow_prerelease`), so version churn is expected.
