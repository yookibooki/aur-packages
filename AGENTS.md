Keeps every package in `packages.json` current on the AUR. Nothing else belongs
here.

Adding a package is a data change, never a code change:

1. `packages/<pkg>/PKGBUILD` with `_realver` (the upstream version verbatim),
   `pkgver` (its Arch form — `-` and `+` become `_`), `pkgrel`, and one
   `source_<arch>` / `sha256sums_<arch>` pair per architecture.
2. `packages/<pkg>/.SRCINFO` from `makepkg --printsrcinfo`.
3. One `packages.json` entry: `repo`, a `url` template using `{ver}` and
   `{triple}`, and the arch to triple map. Add `"allow_prerelease": true` only
   to track prereleases.

- Checksums come only from downloads. Never `SKIP`, never typed.
- `.SRCINFO` comes only from `makepkg --printsrcinfo`, never hand-edited.
- No comments, no docstrings: the maintainer never reads the source, agents read
  this file.
- Keep it this small — no second script, no second workflow, no PR bot, no merge
  step, no alerting.
- Nothing runs on the maintainer's machine. Prove a change with a run on a
  branch, not locally.
- Secrets: `AUR_SSH_KEY` and `AUR_KNOWN_HOSTS` (`ssh-keyscan -t ed25519
  aur.archlinux.org`, checked against the fingerprint Arch publishes).