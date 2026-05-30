# AUR package monorepo

Automatically updates Arch Linux AUR packages when upstream GitHub releases are published.

## Structure

```
mpatch-bin/          # AUR package directory (one per package)
├── PKGBUILD         # Arch package build recipe
└── .SRCINFO         # Package metadata (generated, don't hand-edit)
.github/workflows/
└── publish.yml      # Auto-update pipeline
```

## How it works

1. **newreleases.io** detects a new GitHub release on `Romelium/mpatch` and POSTs a `repository_dispatch` event to this repo's GitHub API.
2. The workflow in `publish.yml` wakes up on `repository_dispatch` (type `new_release`) or manual `workflow_dispatch`.
3. For each package in the matrix, it checks if the latest upstream version differs from `pkgver` in `PKGBUILD`.
4. If newer: downloads tarballs for all architectures in parallel, updates checksums, generates `.SRCINFO` via `makepkg --printsrcinfo` in a one-shot Arch container, pushes to AUR, and commits the update back to the monorepo.

## Adding a new package

Add a matrix entry to `.github/workflows/publish.yml`:

```yaml
matrix:
  include:
    - pkg: mpatch-bin
      upstream: Romelium/mpatch
      asset: mpatch           # tarball name prefix (e.g., mpatch-x86_64-...tar.gz)
      archs: |
        x86_64 x86_64-unknown-linux-gnu
        aarch64 aarch64-unknown-linux-gnu
        armv7h armv7-unknown-linux-gnueabihf
```

Then create `pkg-name/PKGBUILD` and `pkg-name/.SRCINFO`.

## Architecture triple format

Each line in `archs` is `<arch_name> <upstream_triple>`. The arch name maps to PKGBUILD variables (`source_x86_64=`, `sha256sums_x86_64=`), and the triple is used in the download URL.

Secrets stored on GitHub (repo-level):
- `AUR_SSH_KEY` — SSH private key for `aur@aur.archlinux.org` pushes

## Common tasks

**Bump version manually:** Edit `pkgver` in PKGBUILD, run `updpkgsums`, then `makepkg --printsrcinfo > .SRCINFO`.

**Test workflow locally:** `act -j update` (requires Docker and `act` installed).

**Debug a run:** Check Actions tab on GitHub — every step logs its commands with `set -euo pipefail`.

## Security notes

- SSH key is written with `install -m600 /dev/stdin`, never echoed.
- Host key verified via `ssh-keyscan` before connections.
- PKGBUILD is sourced in an isolated subshell (`bash -c 'source PKGBUILD; ...'`).
- `curl -fsSL` fails on HTTP errors — no silent 404 → bad checksum attacks.
