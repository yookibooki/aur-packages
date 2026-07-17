# AUR package monorepo

Each subdirectory is an AUR package. `.github/workflows/publish.yml` auto-updates them by checking upstream GitHub releases daily via a scheduled GitHub Actions workflow.

The heavy lifting (downloading tarballs, computing checksums, rewriting PKGBUILD) is delegated to `scripts/update-pkgbuild.sh` — a reusable, tested shell script that reads arch-triple pairs from stdin.

## Adding a package

1. Create `$pkg/PKGBUILD` and `$pkg/.SRCINFO`
2. Add an entry to `.github/packages.json`:

```json
{
  "pkg": "myapp-bin",
  "upstream": "Owner/Repo",
  "asset": "myapp",
  "ext": ".tar.gz",
  "ver_in_url": true,
  "ver_in_path": true,
  "archs": "x86_64 x86_64-unknown-linux-gnu\naarch64 aarch64-unknown-linux-gnu"
}
```

| Field | Description |
|---|---|
| `pkg` | AUR package name (directory name) |
| `upstream` | GitHub `Owner/Repo` |
| `asset` | Tarball/binary name prefix before the arch triple |
| `ext` | File extension — `.tar.gz` for archives, `""` for bare binaries |
| `ver_in_url` | `true` if the download URL has `-v<VERSION>` before the extension |
| `ver_in_path` | `true` (default) if release tags use a `v` prefix (e.g. `v1.2.3`) |
| `archs` | Space-separated `arch triple` pairs, one per line, separated by `\n` |

> **Tip:** Use `"ext": ""` and `"ver_in_url": false` for release assets whose filename
> is just `<asset>-<triple>` with no version or extension (like most Go binaries).

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
