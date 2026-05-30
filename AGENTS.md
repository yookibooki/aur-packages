# AUR package monorepo

Each subdirectory is an AUR package. `publish.yml` auto-updates them when upstream GitHub releases are detected via newreleases.io webhook.

## Adding a package

1. Create `$pkg/PKGBUILD` and `$pkg/.SRCINFO`
2. Add a matrix entry to `.github/workflows/publish.yml`:

```yaml
- pkg: $pkg
  upstream: Owner/Repo
  asset: $asset_prefix   # tarball name before the triple
  archs: |
    x86_64 x86_64-unknown-linux-gnu
    aarch64 aarch64-unknown-linux-gnu
```

## Secrets

- `AUR_SSH_KEY` — SSH key for pushing to AUR

## Guardrails

- `set -euo pipefail` and `curl -fsSL` everywhere — don't remove these
- SSH key written via `install -m600 /dev/stdin`, never echoed
- PKGBUILD sourced in isolated subshell: `bash -c 'source PKGBUILD; ...'` — keeps `pkgver()` execution contained and prevents variable leaks
