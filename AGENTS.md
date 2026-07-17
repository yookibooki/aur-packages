# AUR package monorepo

Each subdirectory is an AUR package. `.github/workflows/publish.yml` auto-updates them when upstream GitHub releases are detected via newreleases.io webhook.

The heavy lifting (downloading tarballs, computing checksums, rewriting PKGBUILD) is delegated to `scripts/update-pkgbuild.sh` — a reusable, tested shell script that reads arch-triple pairs from stdin.

## Adding a package

1. Create `$pkg/PKGBUILD` and `$pkg/.SRCINFO`
2. Add a matrix entry to `.github/workflows/publish.yml`:

```yaml
- pkg: $pkg
  upstream: Owner/Repo
  asset: $asset_prefix   # tarball name before the triple
  ext: .tar.gz           # file extension ("" for bare binaries)
  ver_in_url: true       # true if URL has "-v<VERSION>" before ext
  ver_in_path: true      # true (default) if release tags use "v" prefix (e.g. "v1.2.3")
  archs: |
    x86_64 x86_64-unknown-linux-gnu
    aarch64 aarch64-unknown-linux-gnu
```

## Scripts

| Script | Purpose |
|---|---|
| `scripts/update-pkgbuild.sh` | Downloads per-arch assets, computes sha256sums, rewrites PKGBUILD `source_*` / `sha256sums_*` + bumps `pkgver`/`pkgrel`. Reads arch-triple pairs from stdin. |

## Secrets

- `AUR_SSH_KEY` — SSH key for pushing to AUR

## Guardrails

- `set -euo pipefail` and `curl -fsSL` everywhere — don't remove these
- SSH key written via `install -m600 /dev/stdin`, never echoed
- PKGBUILD sourced in isolated subshell: `bash -c 'source PKGBUILD; ...'` — keeps `pkgver()` execution contained and prevents variable leaks
