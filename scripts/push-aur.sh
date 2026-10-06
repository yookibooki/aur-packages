#!/usr/bin/env bash
# push-aur.sh <workspace> [pkg ...] — ship the committed packages/ tree to the AUR.
#
# Fail closed per package, in order:
#   1. clean tree (ship the commit, not the worktree), no SKIP/empty checksums
#   2. .SRCINFO must reproduce byte for byte from the PKGBUILD via makepkg
#   3. clone ssh://aur@aur.archlinux.org/<pkg>.git, push only on a real diff
# Failures are collected; exit 1 lists them.
#
# Requires: makepkg, git, python3, and SSH write access to aur.archlinux.org.
set -euo pipefail

(($# >= 1)) || { echo "Usage: $0 <workspace> [pkg ...]" >&2; exit 1; }
workspace="$(cd "$1" && pwd)"
shift
command -v makepkg >/dev/null 2>&1 || { echo "ERROR: makepkg is required" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -ne 0 ]] || { echo "ERROR: makepkg refuses root; run unprivileged" >&2; exit 1; }

active_pkgs() {
    python3 - "$workspace/packages/registry.json" <<'EOF'
import json, sys
for e in json.load(open(sys.argv[1])):
    if e.get("active", True) in (True, "true"):
        print(e["pkg"])
EOF
}

candidates=("$@")
if ((${#candidates[@]} == 0)); then
    while IFS= read -r p; do [[ -n "$p" ]] && candidates+=("$p"); done < <(active_pkgs)
fi
((${#candidates[@]})) || { echo "No packages to publish" >&2; exit 0; }

failures=()
publishable=()

for pkg in "${candidates[@]}"; do
    pkgdir="$workspace/packages/$pkg"
    if [[ ! "$pkg" =~ ^[a-z0-9@._+-]+$ ]]; then
        echo "ERROR: invalid package name ${pkg}" >&2; failures+=("$pkg"); continue
    fi
    if [[ ! -f "$pkgdir/PKGBUILD" || ! -f "$pkgdir/.SRCINFO" ]]; then
        echo "ERROR: ${pkg} is missing packages/${pkg}/{PKGBUILD,.SRCINFO}" >&2
        failures+=("$pkg"); continue
    fi
    if [[ -n "$(git -C "$workspace" status --porcelain -- "packages/$pkg")" ]]; then
        echo "ERROR: ${pkg} has uncommitted changes; commit before publishing" >&2
        failures+=("$pkg"); continue
    fi
    if grep -q "'SKIP'" "$pkgdir/PKGBUILD" \
        || grep -Eq "sha256sums_[a-z0-9_]+=\(''\)" "$pkgdir/PKGBUILD"; then
        echo "ERROR: ${pkg} PKGBUILD has SKIP or empty checksums; refusing to publish" >&2
        failures+=("$pkg"); continue
    fi

    # A PKGBUILD that does not reproduce its .SRCINFO must never reach the AUR.
    echo "==> ${pkg}: makepkg --printsrcinfo parity"
    work=$(mktemp -d)
    cp "$pkgdir/PKGBUILD" "$work/"
    if ! new="$(cd "$work" && makepkg --printsrcinfo)" \
        || ! diff -u "$pkgdir/.SRCINFO" <(printf '%s\n' "$new"); then
        echo "ERROR: ${pkg}: committed .SRCINFO does not reproduce from PKGBUILD" >&2
        rm -rf "$work"; failures+=("$pkg"); continue
    fi
    rm -rf "$work"
    publishable+=("$pkg")
done

push_one() {
    local pkg="$1" version tmp clone_err
    version=$(cd "$workspace/packages/$pkg" \
        && bash -c 'set -u; source ./PKGBUILD; printf %s "${pkgver:?pkgver is not set}"')
    tmp=$(mktemp -d)
    if ! clone_err=$(git clone --depth 1 "ssh://aur@aur.archlinux.org/${pkg}.git" "$tmp" 2>&1); then
        if [[ -z "$(ls -A "$tmp")" ]] \
            && [[ "${clone_err,,}" == *"repository not found"* || "${clone_err,,}" == *"does not appear to be a git repository"* ]]; then
            git -C "$tmp" init -b master
            cp "$workspace/packages/$pkg/PKGBUILD" "$workspace/packages/$pkg/.SRCINFO" "$tmp/"
            git -C "$tmp" add -A
            git -C "$tmp" remote add origin "ssh://aur@aur.archlinux.org/${pkg}.git"
            git -C "$tmp" -c user.name="aur-publish" -c user.email="aur-publish@localhost" \
                commit -m "init: ${pkg} v${version}"
            git -C "$tmp" push -u origin master
        else
            echo "ERROR: failed to clone AUR package ${pkg}: ${clone_err}" >&2
            rm -rf "$tmp"; return 1
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
    echo "==> ${pkg}: publishing"
    push_one "$pkg" || failures+=("$pkg")
done

if ((${#failures[@]} > 0)); then
    echo "ERROR: failed to publish: ${failures[*]}" >&2
    exit 1
fi
echo "Publish complete (${#publishable[@]} candidate(s))."
