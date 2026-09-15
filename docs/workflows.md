# Workflow reference

## issue-manager

Triggers: `issues` opened/edited/reopened, `issue_comment` created. Only acts
on issues labeled `pkg-add`, `pkg-remove`, or `pkg-hold`. Parses the form with
`issue-ops/parser`, with fallbacks to the issue title/body when the parser
output is empty or changes shape, so a minimal issue (package name plus
source URL, like #2) is enough. `remove` applies immediately. The add flow
in one job: `scripts/probe-upstream.py` infers the asset pattern from the
upstream's latest release (explicit `asset`/`ext` issue fields override the
probe), `scripts/issue-apply.py add` scaffolds the registry entry and
PKGBUILD, `scripts/update-pkgbuild.sh` resolves the real version and
checksums (erasing `SKIP`), `makepkg --printsrcinfo` regenerates `.SRCINFO`
(native, else one Arch container), the per-package note is stamped with the
issue number and version, and `scripts/check-consistency.sh` gates the
commit. Any failure rolls back (registry restored, scaffold directory and
note removed) and posts the exact error with `needs-info`, leaving the
issue open. Success commits registry + PKGBUILD + `.SRCINFO` + package note,
comments, labels `validated,applied`, and closes. Exposes `status`/`kind`
outputs for the watcher.

## discover

Triggers: schedule `0 */4 * * *`, `workflow_dispatch` (optional `pkg` limit,
optional `nightly-chroot`). Builds a matrix of entries where `active` is true
and `hold` is not true, then per package resolves the latest stable tag
(`allow_prerelease` entries may take prereleases), refuses silent downgrades
via `sort -V`, regenerates the PKGBUILD with `scripts/update-pkgbuild.sh`,
re-checks for re-cut assets under unchanged tags (`pkgrel` bump), and uploads
`pkgbuild-<pkg>` artifacts. Hands off to publish. On failure opens or updates
the rolling `[auto-fix]` issue with the run URL.

## verify

Triggers: `workflow_call` with `pkg` input. Fast gate
(`scripts/verify-package.sh` in an Arch container as non-root) plus full build
(`makepkg -s --noconfirm --noarchive`, nightly `extra-x86_64-build` clean
chroot) plus `namcap` on the PKGBUILD and on the built artifact when one
exists. Red blocks that package only.

## publish

Triggers: `workflow_run` on discover success, `workflow_dispatch`. Downloads
`pkgbuild-*` artifacts, regenerates `.SRCINFO` in one Arch container step,
pushes each changed package to `aur.archlinux.org` over SSH with a pinned host
key (`AUR_KNOWN_HOSTS` missing is a hard fail), then commits
`PKGBUILD`+`.SRCINFO` back to `main`.

## watcher

Triggers: `issues`, `issue_comment`, `pull_request`,
`pull_request_review`, `pull_request_review_comment`, `discussion`,
`discussion_comment`, `workflow_run` completed. No wake word. `sort` labels
new issues to exactly one lane (`pkg-add`, `pkg-hold`, `pkg-remove`, `bug`,
`question`, `invalid`). `act` defers `pkg-*` to issue-manager, answers
`question` once with a 4-hour auto-close timer, and files the rolling
`[auto-fix]` issue on red runs. `review` reviews every PR in plain words and
fixes red checks on the same branch. One branch per issue
(`fix/<issue>-<slug>`), max 2 automated rounds, then `needs-info`.

## runner

Triggers: `workflow_dispatch` with `prompt` and `name` inputs. Single model
call against `https://inference-api.nousresearch.com/v1` model
`meituan/longcat-2.0:free` using the `NOUS_API_KEY` secret. Masks the key,
scrubs GitHub tokens from the worker env, writes the answer to the log.
Dispatched only for new requests and failures; happy-path checks never call it.

## maintainer

Triggers: schedule `17 3 * * *`, `workflow_dispatch`. Syncs labels, refreshes
docs, closes duplicates, closes `auto-fix`/`question` issues quiet for 14
days, merges green bot PRs (squash, delete branch), and dispatches the runner
for conflicting PR branches. Updates the `heartbeat:` line in
`docs/STATE.md` every run — this is the commit that keeps GitHub from
disabling scheduled workflows after 60 days of repo inactivity — then
commits and pushes whatever changed.

## lint

Triggers: push, pull request. One Arch container: installs `namcap` plus
`shellcheck` as root, runs `scripts/check-consistency.sh`, then runs
`namcap -e carch` on every PKGBUILD as the non-root `checker` user.
