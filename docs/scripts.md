# Script reference

## scripts/issue-apply.py

Mutates `packages/registry.json` from validated input. Stdlib only, exits 2
with a stderr message on validation errors.

- `add --pkg X --source S [--upstream O/R] [--asset A] [--ext E] [--ver-in-url b] [--ver-in-path b] [--version-in-asset b] [--ver-after-asset b] [--allow-prerelease b] [--archs $'a t\n...']` — infers `upstream` from a `github.com` URL or bare `owner/repo`, defaults `asset` to the pkg basename, defaults `archs` to x86_64 plus aarch64 gnu triples, scaffolds `packages/<pkg>/PKGBUILD` (checksums `SKIP`) and `docs/packages/<pkg>.md` (status `scaffolded`, why-to-fill-in), appends the registry entry. **Does not write `.SRCINFO`** — that comes from `makepkg --printsrcinfo` later in the same job. See the `SKIP` lifecycle in `docs/workflows.md` for the full transaction. Re-adding an identical package is a no-op; conflicting existing registry data or an existing package directory without a registry match fails closed.
- `remove --pkg X [--archive-dir archive]` — sets `active:false`, moves `packages/<pkg>/` to `archive/<pkg>/`. No-op when already inactive; refuses an occupied archive destination or an archive path outside the repository, and rolls the move back if the registry write fails.
- `--refresh-docs` — compatibility shim; prints the tracked package count
  and exits 0 (the registry is the source of truth, there is no
  generated table).

Override the registry path with `REGISTRY_PATH` (tests use a temp copy; the
package directory then resolves under that temp root, keeping the repo clean).

## scripts/probe-upstream.py

Usage: `probe-upstream.py --upstream owner/repo --pkg foo-bin [--tag v1.2.3]
[--allow-prerelease false] [--assets-json assets.json]`. Resolves the latest
release the same way Repo Assist does (`gh release view` first, version-
sorted `gh release list` fallback), filters the release to Linux runtime
assets, and matches them against the five patterns in `docs/packages.md`.
Prints JSON (`upstream`, `tag`, `version`, `asset`, `ext`, the four pattern
flags, `archs`) for `scripts/issue-apply.py` to feed into `issue-apply.py` and
`update-pkgbuild.sh`. Verified against all four tracked packages: it
reproduces their registry rows exactly. Exits 2 with an actionable stderr
message (exact asset names needed) when nothing matches. `--assets-json`
bypasses `gh` for tests. Stdlib only.

## scripts/update-pkgbuild.sh

Usage: `printf '<arch triple>\n' | update-pkgbuild.sh <pkgdir> <version> <asset> <ext> <ver_in_url> <upstream> [ver_in_path] [version_in_asset] [ver_after_asset]`. Downloads every arch asset in parallel with retry (600s cap for large assets), verifies non-empty plus 64-hex sha256, then rewrites `_realver`, `pkgver` (sanitized), `pkgrel` (1 on upgrade, +1 on re-cut), `source_<arch>`, `sha256sums_<arch>`. Nothing touches the PKGBUILD until all downloads succeed. Exits 0 untouched when version and checksums are identical. This is the step that erases `SKIP` from a scaffold.

## scripts/verify-package.sh

Usage: `verify-package.sh <pkgdir>`. Fail-closed gate: `bash -n`,
`shellcheck --severity=error` on the PKGBUILD (warning-level findings are
inherent to makepkg-set variables), rejects `SKIP`/empty checksums,
diffs `.SRCINFO` against `makepkg --printsrcinfo` when makepkg exists
(runs from a temp copy, never writes into the checkout), runs
`makepkg --verifysource`, runs `namcap -e carch` on the PKGBUILD when
namcap exists. The authoritative
Arch build gate is `lint.yml`, which runs this script inside
`archlinux:base-devel`.

## scripts/check-consistency.sh

Cross-validates registry, PKGBUILDs, `.SRCINFO` files, and the Repo Assist
workflow files on plain Ubuntu (`bash` + `python3`). Checks shell syntax, `shellcheck` on
scripts plus `severity=error` on PKGBUILDs when installed, registry schema
and duplicate/pattern rules, per-arch `source_`/`sha256sums_` parity between
PKGBUILD and `.SRCINFO` after `${_realver}` expansion, `repo-assist.lock.yml`
triggers and `repo-assist.md` sections, and forbidden artifacts
(`.agent/`, `Docs/sepo-setup.md`, bot-mention strings). Must stay green.

## scripts/push-aur.sh

Usage: `push-aur.sh <workspace>`. Copies `pkgbuild-*/PKGBUILD` artifacts into
package dirs, regenerates `.SRCINFO` for each in one Arch container as the
invoking user, then clones each `ssh://aur@aur.archlinux.org/<pkg>.git` (init
when genuinely missing) and pushes when the tree differs. Collects per-package
failures and exits non-zero listing them.
