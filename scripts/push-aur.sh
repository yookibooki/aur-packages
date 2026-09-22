#!/usr/bin/env bash
# push-aur.sh — publish the committed packages/ tree to the AUR.
#
# Repo mode is the only mode: packages/<pkg>/{PKGBUILD,.SRCINFO} in the
# workspace is the source of truth (there are no PKGBUILD artifacts to copy
# — discover.sh commits its bump transaction, the maintainer merges it, and
# this script ships exactly that commit).
#
# Per candidate package:
#   1. refuse the package if its tree is dirty (ship the commit, not the
#      worktree) or its PKGBUILD still carries SKIP/empty checksums
#   2. regenerate .SRCINFO inside an Arch container and fail hard when the
#      result differs from the committed one — a PKGBUILD that does not
#      reproduce its .SRCINFO must never reach the AUR
#   3. clone ssh://aur@aur.archlinux.org/<pkg>.git (init when genuinely
#      missing) and push only when the tree differs (idempotent)
# Per-package failures are collected; the script exits non-zero listing them.
#
# Usage: push-aur.sh <workspace> [pkg ...]
#   pkg arguments limit the run; default is every active registry entry.
#
# Requires: docker, git, python3, and SSH access to aur.archlinux.org
# (private key + pinned known_hosts — materialized by
# .github/workflows/publish.yml from the AUR_SSH_KEY / AUR_KNOWN_HOSTS
# secrets; the script reads neither).
#
# Env:
#   AUR_DOCKER_IMAGE   container image for makepkg (default: archlinux:base-devel).
#                      Pin to a digest for reproducibility, e.g.
#                      archlinux:base-devel@sha256:<digest>.
set -euo pipefail

if (($# < 1)); then
    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 1
fi

arg1="$1"
if [[ "$arg1" = /* ]]; then
    workspace="$arg1"
else
    workspace="$PWD/$arg1"
fi
shift
if [[ ! -d "$workspace" ]]; then
    echo "ERROR: workspace \"${arg1}\" does not exist" >&2
    exit 1
fi

image="${AUR_DOCKER_IMAGE:-archlinux:base-devel}"

# Active registry entries, one pkg per line (matches the repo's registry
# schema: entries carry active:true|false and a validated pkg name).
active_pkgs() {
    python3 - "$workspace/packages/registry.json" <<'EOF'
import json, sys
for e in json.load(open(sys.argv[1])):
    if e.get("active", True) in (True, "true"):
        print(e["pkg"])
EOF
}

candidates=()
if (($# > 0)); then
    candidates=("$@")
else
    while IFS= read -r p; do
        [[ -n "$p" ]] && candidates+=("$p")
    done < <(active_pkgs)
fi
if ((${#candidates[@]} == 0)); then
    echo "No packages to publish" >&2
    exit 0
fi

failures=()

for pkg in "${candidates[@]}"; do
    # Fail closed on anything that would make the pushed content ambiguous.
    if [[ ! "$pkg" =~ ^[a-z0-9@._+-]+$ ]]; then
        echo "ERROR: invalid package name ${pkg}" >&2
        failures+=("$pkg")
        continue
    fi
    pkgdir="$workspace/packages/$pkg"
    if [[ ! -f "$pkgdir/PKGBUILD" || ! -f "$pkgdir/.SRCINFO" ]]; then
        echo "ERROR: ${pkg} is missing packages/${pkg}/{PKGBUILD,.SRCINFO}" >&2
        failures+=("$pkg")
        continue
    fi
    if [[ -n "$(git -C "$workspace" status --porcelain -- "packages/$pkg")" ]]; then
        echo "ERROR: ${pkg} has uncommitted changes; commit before publishing" >&2
        failures+=("$pkg")
        continue
    fi
    if grep -q "'SKIP'" "$pkgdir/PKGBUILD" \
        || grep -Eq "sha256sums_[a-z0-9_]+=\(''\)" "$pkgdir/PKGBUILD"; then
        echo "ERROR: ${pkg} PKGBUILD has SKIP or empty checksums; refusing to publish" >&2
        failures+=("$pkg")
        continue
    fi
done

publishable=()
for pkg in "${candidates[@]}"; do
    [[ " ${failures[*]-} " == *" $pkg "* ]] && continue
    publishable+=("$pkg")
done

# Regenerate .SRCINFO in an Arch container (makepkg refuses root in most
# environments; the container runs as the invoking user) and assert it
# reproduces the committed file byte for byte.
for pkg in "${publishable[@]}"; do
    pkgdir="$workspace/packages/$pkg"
    echo "==> ${pkg}: makepkg --printsrcinfo (parity check)"
    if ! new="$(cd "$pkgdir" && docker run --rm --user "$(id -u):$(id -g)" \
        -e HOME=/tmp -v "$pkgdir:/pkg" -w /pkg "$image" \
        makepkg --printsrcinfo)"; then
        echo "ERROR: ${pkg}: could not regenerate .SRCINFO" >&2
        failures+=("$pkg")
        continue
    fi
    if ! diff -u "$pkgdir/.SRCINFO" <(printf '%s\n' "$new"); then
        echo "ERROR: ${pkg}: committed .SRCINFO does not reproduce from PKGBUILD" >&2
        failures+=("$pkg")
    fi
done

push_one() {
    local pkg="$1" version tmp clone_err
    version=$(cd "$workspace/packages/$pkg" \
        && bash -c 'set -u; source ./PKGBUILD; printf %s "${pkgver:?pkgver is not set}"')
    tmp=$(mktemp -d)

    if ! clone_err=$(git clone --depth 1 "ssh://aur@aur.archlinux.org/${pkg}.git" "$tmp" 2>&1); then
        if [[ -z "$(ls -A "$tmp")" ]] &&
            [[ "${clone_err,,}" == *"repository not found"* || "${clone_err,,}" == *"does not appear to be a git repository"* ]]; then
            git -C "$tmp" init -b master
            cp "$workspace/packages/$pkg/PKGBUILD" "$workspace/packages/$pkg/.SRCINFO" "$tmp/"
            git -C "$tmp" add -A
            git -C "$tmp" remote add origin "ssh://aur@aur.archlinux.org/${pkg}.git"
            git -C "$tmp" -c user.name="aur-publish" -c user.email="aur-publish@localhost" \
                commit -m "init: ${pkg} v${version}"
            git -C "$tmp" push -u origin master
        else
            echo "ERROR: failed to clone AUR package ${pkg}:" >&2
            echo "${clone_err}" >&2
            rm -rf "$tmp"
            return 1
        fi
    else
        cp "$workspace/packages/$pkg/PKGBUILD" "$workspace/packages/$pkg/.SRCINFO" "$tmp/"
        git -C "$tmp" add PKGBUILD .SRCINFO
        if git -C "$tmp" diff --cached --quiet; then
            echo "${pkg}: already current on the AUR, nothing to push"
        else
            git -C "$tmp" -c user.name="aur-publish" -c user.email="aur-publish@localhost" \
                commit -m "${pkg}: update to v${version}"
            git -C "$tmp" push
            echo "${pkg}: pushed v${version} to the AUR"
        fi
    fi

    rm -rf "$tmp"
}

for pkg in "${publishable[@]}"; do
    [[ " ${failures[*]-} " == *" $pkg "* ]] && continue
    echo "==> ${pkg}: publishing"
    if ! push_one "$pkg"; then
        failures+=("$pkg")
    fi
done

if ((${#failures[@]} > 0)); then
    echo "ERROR: failed to publish: ${failures[*]}" >&2
    exit 1
fi
echo "Publish complete (${#publishable[@]} candidate(s))."
