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

- `hold: true` — Repo Assist skips held packages during scheduled runs;
  verification still runs on demand (`workflow_dispatch` with `pkg` set).
- `active: false` — package removed: directory moved to `archive/<pkg>/`,
  discovery and AUR push skip it.

## Scripts do X, Repo Assist does Y

Repo Assist (`.github/workflows/repo-assist.yml`) is the primary automation.
It runs every 12 hours and on-demand via `/repo-assist <instructions>`.
It selects 3 tasks from 10 each run, weighted by repo state.

Scripts (model-free, run as tools called by Repo Assist) do the repeatable work:

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
- `scripts/push-aur.sh` — copies PKGBUILD artifacts, regenerates `.SRCINFO`,
  pushes each changed package to `aur.archlinux.org` over SSH with a pinned
  host key.
- `scripts/probe-upstream.py` — resolves latest release, filters Linux assets,
  matches against 5 patterns. Prints JSON for `issue-apply.py`.

Repo Assist (model-backed, scheduled and on-demand) does the cognitive work:

- Task 1: Labels and triages open issues
- Task 2: Investigates issues, resolves, fixes, seeks clarification, or comments
- Task 3: Investigates fixable issues, creates draft PRs
- Task 4: Engineering investments (dependency updates, CI improvements)
- Task 5: Coding improvements (code clarity, dead code, duplication)
- Task 6: Maintains its own PRs (fix CI, resolve conflicts)
- Task 7: Documentation, ad hoc QA, project basics
- Task 8: Performance improvements
- Task 9: Testing improvements
- Task 10: Proactive forward progress
- Task 11: Monthly activity summary for maintainer visibility

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
- **Hold/unhold**: open a "Hold package" issue, or `/repo-assist hold <pkg>`.
  Applies immediately via `scripts/issue-apply.py hold`.
- **Remove**: open a "Remove package" issue, or `/repo-assist remove <pkg>`.
  Applies immediately via `scripts/issue-apply.py remove`. Sets
  `active: false`, removes the package entirely from this repo (registry,
  package directory, docs). AUR deletion (if wanted) is a separate manual
  request on aur.archlinux.org.

## Secrets

- `AUR_SSH_KEY` — SSH key for `aur.archlinux.org`. Used by
  `scripts/push-aur.sh` when Repo Assist pushes to AUR.
- `AUR_KNOWN_HOSTS` — pinned host key (`ssh-keyscan -t ed25519
  aur.archlinux.org`). `push-aur.sh` hard-fails when unset; no TOFU fallback.
- `NOUS_API_KEY` — model key for Repo Assist's coding backend. Required
  for model-backed tasks. Set as a repo secret.
- `NOUS_BASE_URL` — base URL for the inference API. Defaults to
  `https://inference-api.nousresearch.com/v1`. Change to any OpenAI-compatible
  endpoint (e.g. `https://api.openai.com/v1`) via repo secret.
- `NOUS_MODEL` — model identifier. Defaults to
  `poolside/laguna-s-2.1:free`. Change to any model your provider supports
  via repo secret.
