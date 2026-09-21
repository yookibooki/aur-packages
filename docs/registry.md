# Registry reference

File: `packages/registry.json`. JSON array, one object per package. It is the
only place package data lives.

## Fields

| Field | Type | Meaning |
|-------|------|---------|
| `pkg` | string | AUR package name, must match `^[a-z0-9@._+-]+$`, must equal its directory `packages/<pkg>/` |
| `upstream` | string | `owner/repo` on GitHub that publishes releases |
| `asset` | string | Release asset name prefix before the arch triple, e.g. `openhuman-core` |
| `ext` | string | File extension including the dot, or `""` for bare binaries. One of `""`, `.tar.gz`, `.tgz`, `.zip`, `.tar.xz`, `.tar.bz2` |
| `ver_in_url` | bool | Asset embeds `-v<VERSION>` before the extension |
| `ver_in_path` | bool | Whether release tags carry a `v` prefix (`v1.2.3`). `true` = tag is `v<version>`; `false` = tag is the raw version. The name is historical and does not describe the URL path — it describes the tag. |
| `version_in_asset` | bool | Asset is `<name>_<version>_<triple><ext>` (underscore separators) |
| `ver_after_asset` | bool | Asset is `<name>-<version>-<triple><ext>` (dash separators) |
| `allow_prerelease` | bool | Track prereleases as well as stable releases |
| `archs` | string | Newline-separated `<arch> <triple>` lines, at least one, no duplicate archs |
| `active` | bool | `false` means removed; directory lives in `archive/<pkg>/`, discovery and push skip it |

`ver_in_url`, `ver_in_path`, `version_in_asset`, `ver_after_asset`,
`allow_prerelease`, `active` accept real JSON booleans. Missing
`ver_after_asset` reads as `false`.

## Pattern mapping

The four asset flags combine into the patterns in `docs/packages.md`:

- pattern 1: `ver_in_url=true`
- pattern 2: all four false (bare or plain triple)
- pattern 3: `version_in_asset=true`, `ver_in_path=true`
- pattern 4: `version_in_asset=true`, `ver_in_path=false`
- pattern 5: `ver_after_asset=true`

## Rules

- No duplicate `pkg`. No empty `archs`. Triples match
  `[A-Za-z0-9_.-]+`, arch names match `[a-z0-9_]+`.
- `pkgver` in PKGBUILD is the sanitized `_realver` (`-`/`+` become `_`);
  `.SRCINFO` `pkgver` must equal PKGBUILD `pkgver`.
- `source_<arch>` URLs must start with
  `https://github.com/<upstream>/releases/download/`.
- Never `SKIP` checksums in a committed PKGBUILD. `SKIP` exists only inside
  a scaffold between creation and the first checksum resolution in the same
  job. See `docs/packages.md` for the lifecycle.
