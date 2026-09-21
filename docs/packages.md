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
| 5 | `ver_after_asset=true` | Asset uses `<name>-<version>-<triple><ext>`; tag has `v` prefix | no tracked package uses this yet; e.g. `foo-core-0.63.12-x86_64-unknown-linux-gnu.tar.gz` under tag `v0.63.12` |

## Operational flags

- `active: false` — package removed: directory moved to `archive/<pkg>/`,
  discovery and AUR push skip it.

## Scripts do X, Repo Assist does Y

Repo Assist (`.github/workflows/repo-assist.lock.yml`, compiled from
`repo-assist.md`) is the primary automation.
It runs every 3 hours and on-demand via `/repo-assist <instructions>`.

Scripts (model-free, run as tools called by Repo Assist) do the repeatable work:

- `scripts/issue-apply.py` — validates and mutates `packages/registry.json`
  (add scaffolds `packages/<pkg>/PKGBUILD`, remove sets
  `active:false` and moves `packages/<pkg>/` to `archive/<pkg>/`).
- `scripts/update-pkgbuild.sh` — downloads upstream assets, writes real
  sha256 sums, bumps `pkgrel` on asset re-cuts.
- `scripts/verify-package.sh` — fast local gate (`bash -n`, `.SRCINFO` diff
  vs `makepkg --printsrcinfo`, `makepkg --verifysource`).
- `scripts/check-consistency.sh` — registry/PKGBUILD/`.SRCINFO` cross-check
  plus workflow trigger checks. Must stay green; red blocks that package
  only (`fail-fast: false`), never the whole run.
- `scripts/push-aur.sh` — copies PKGBUILD artifacts, regenerates `.SRCINFO`,
  pushes each changed package to `aur.archlinux.org` over SSH with a pinned
  host key.
- `scripts/probe-upstream.py` — resolves latest release, filters Linux assets,
  matches against 5 patterns. Prints JSON for `issue-apply.py`.

Repo Assist (model-backed, scheduled and on-demand) does the cognitive work:
triage, investigation, fixes via safe-outputs, and memory updates.
The full architecture is in `docs/workflows.md`.
The Repo Assist integration guide is in `docs/repo-assist.md`.

## Managing packages (issues and /repo-assist)

Repo Assist handles package management through both issue labels
and `/repo-assist` commands:

- **Add**: open an "Add package" issue with package name plus source
  (owner/repo, link, or download page). Repo Assist probes the upstream's
  latest release via `scripts/probe-upstream.py` to infer the asset prefix,
  extension, pattern flags, and arches, then scaffolds `packages/<pkg>/PKGBUILD`
  plus the registry entry and resolves real checksums and `.SRCINFO` before
  committing. Optional `asset`/`ext` fields override the probe when upstream
  names are unusual. Also triggered via `/repo-assist add <pkg> from <source>`.
- **Remove**: open a "Remove package" issue, or `/repo-assist remove <pkg>`.
  Applies immediately via `scripts/issue-apply.py remove`: sets
  `active: false`, moves `packages/<pkg>/` to `archive/<pkg>/`.
  AUR deletion (if wanted) is a separate manual request on aur.archlinux.org.

## Secrets

- `GEMINI_API_KEY` — the Gemini API key used by Repo Assist's Gemini
  engine. It is supplied to the agent job by gh-aw.
- `AUR_SSH_KEY` / `AUR_KNOWN_HOSTS` are not read by
  `scripts/push-aur.sh`; that script requires the runner to already have
  usable SSH access to `aur.archlinux.org` with host verification configured.
