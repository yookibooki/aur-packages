# Supported asset patterns

`packages/registry.json` is the single source of truth. Each entry combines
boolean flags to describe how the upstream release looks. The workflows never
contain package data, only logic.

## Patterns

| # | Flags | Meaning | Example |
|---|-------|---------|---------|
| 1 | `ver_in_url=true` | Asset embeds `-v<VERSION>`; tag has `v` prefix | `mpatch-bin` ← `Romelium/mpatch`: `mpatch-x86_64-unknown-linux-gnu-v1.6.4.tar.gz` under tag `v1.6.4` |
| 2 | all false, `ext=""` | Plain `<asset>-<triple>` bare binary; tag has `v` prefix | `umadev-bin` ← `umacloud/umadev`: `umadev-x86_64-unknown-linux-gnu` under tag `v1.1.1` |
| 3 | `version_in_asset=true` | Asset uses `<name>_<version>_<triple><ext>`; tag has `v` prefix | `axonhub-bin` ← `looplj/axonhub`: `axonhub_1.0.0-beta10_linux_amd64.zip` under tag `v1.0.0-beta10` |
| 4 | `version_in_asset=true`, `ver_in_path=false` | Same as 3 but the tag has NO `v` prefix (`latest` = raw tag) | hypothetical `foo-bin`: `foo_2.0_linux_amd64.tar.gz` under tag `2.0` |
| 5 | `ver_after_asset=true` | Asset uses `<name>-<version>-<triple><ext>`; tag has `v` prefix | `openhuman-bin` ← `tinyhumansai/openhuman`: `openhuman-core-0.63.12-x86_64-unknown-linux-gnu.tar.gz` under tag `v0.63.12` |

## Operational flags

- `hold: true` — discover.yml logs and skips the package; verification still
  runs on demand (`workflow_dispatch` with `pkg` set).
- `active: false` — package removed: directory moved to `archive/<pkg>/`,
  discovery and AUR push skip it.

## Scripts do X, watcher does Y

Scripts (model-free, run on every schedule) do the repeatable work:

- `scripts/issue-apply.py` — validates and mutates `packages/registry.json`
  (add scaffolds `packages/<pkg>/PKGBUILD`, hold toggles `hold`, remove sets
  `active:false` and moves `packages/<pkg>/` to `archive/<pkg>/`).
- `scripts/update-pkgbuild.sh` — downloads upstream assets, writes real
  sha256 sums, bumps `pkgrel` on asset re-cuts.
- `scripts/verify-package.sh` — fast local gate (`bash -n`, `.SRCINFO` diff
  vs `makepkg --printsrcinfo`, `makepkg --verifysource`).
- `scripts/check-consistency.sh` — registry/PKGBUILD/`.SRCINFO` cross-check
  plus workflow trigger checks. Must stay green; red blocks that package
  only (`fail-fast: false`), never the whole run.

The watcher (`.github/workflows/watcher.yml`, model-backed via
`.github/workflows/runner.yml`) does only what scripts cannot:

- Sorts new issues into `bug`, `question`, `pkg-add`, `pkg-hold`,
  `pkg-remove`, `invalid`.
- Answers `question` issues once (ending "react 👎 to keep open"); no reply
  in 4 hours → auto-closes as completed; a follow-up comment reopens.
- Opens/updates the one rolling `[auto-fix]` issue with the failed run URL
  when discover/verify turns red; fixes naming patterns, updates the asset
  table above, re-runs tests. Max 2 automated rounds per issue on one branch
  (`fix/<issue>-<slug>`); still stuck → posts the exact bad line and sets
  `needs-info`.
- Reviews every PR in plain words (bugs, security, style); pushes fixes to
  the same branch. No push on red: `publish.yml` runs only after green
  discover + verify. Every change is a branch + issue comment + pull request,
  so everything is visible and undoable (revert closes or reverts the change).

## Managing packages (issues only)

- **Add**: open an "Add package" issue with package name plus source
  (owner/repo, link, or download page). The automation probes the upstream's
  latest release to infer the asset prefix, extension, pattern flags, and
  arches, then scaffolds `packages/<pkg>/PKGBUILD` plus the registry entry
  and resolves real checksums and `.SRCINFO` before committing. Optional
  `asset`/`ext` fields override the probe when upstream names are unusual.
- **Hold/unhold**: open a "Hold package" issue. Applies immediately.
- **Remove**: open a "Remove package" issue. A maintainer must comment
  `.approve` before it applies (destructive). Sets `active: false`, archives
  the directory. AUR deletion (if wanted) is a separate manual request on
  aur.archlinux.org.

## Secrets

- `AUR_SSH_KEY` — SSH key for `aur.archlinux.org`.
- `AUR_KNOWN_HOSTS` — pinned host key (`ssh-keyscan -t ed25519
  aur.archlinux.org`). publish.yml hard-fails when unset; no TOFU fallback.
- `NOUS_API_KEY` — model key for the runner. Base
  `https://inference-api.nousresearch.com/v1`, model
  `meituan/longcat-2.0:free`. Missing key posts an "add a key" comment,
  never skips silently.
