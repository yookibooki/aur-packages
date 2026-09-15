#!/usr/bin/env bash
set -euo pipefail

if (($# != 1)); then
    cat >&2 <<EOF
Usage: $0 <workspace>

Copies PKGBUILD files from <workspace>/pkgbuild-*/ into the package
directories, regenerates .SRCINFO for each in one Arch container, and pushes
each changed package to AUR (cloning existing repos, initializing new ones).

Requires: docker, git, and SSH access to aur.archlinux.org.

Env:
  AUR_DOCKER_IMAGE   container image for makepkg (default: archlinux:base-devel).
                     Pin to a digest for reproducibility, e.g.
                     archlinux:base-devel@sha256:<digest>.
EOF
    exit 1
fi

if [[ "$1" = /* ]]; then
    workspace="$1"
else
    workspace="$PWD/$1"
fi
if [[ ! -d "$workspace" ]]; then
    echo "ERROR: workspace \"${1}\" does not exist" >&2
    exit 1
fi

image="${AUR_DOCKER_IMAGE:-archlinux:base-devel}"

changed=()
for dir in "$workspace"/pkgbuild-*/; do
    [ -d "$dir" ] || continue
    pkg="${dir#"$workspace"/pkgbuild-}"
    pkg="${pkg%/}"
    if [[ ! -d "$workspace/packages/$pkg" ]]; then
        echo "ERROR: artifact ${dir} has no matching package dir packages/${pkg}/; skipping" >&2
        continue
    fi
    cp "$dir/PKGBUILD" "$workspace/packages/$pkg/PKGBUILD"
    changed+=("$pkg")
done

if ((${#changed[@]} == 0)); then
    echo "No updated PKGBUILDs to push" >&2
    exit 0
fi

docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$workspace:/w" "$image" bash -c '
    set -euo pipefail
    for dir in /w/pkgbuild-*/; do
        [ -d "$dir" ] || continue
        pkg="${dir#/w/pkgbuild-}"
        pkg="${pkg%/}"
        cd "/w/packages/$pkg"
        makepkg --printsrcinfo > .SRCINFO
    done
'

failures=()

push_one() {
    local pkg="$1" version tmp clone_err
    version=$(cd "$workspace/packages/$pkg" && bash -c 'set -u; source ./PKGBUILD; printf %s "${pkgver:?pkgver is not set}"')
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
            echo "${pkg}: no AUR changes, skipping push"
        else
            git -C "$tmp" -c user.name="aur-publish" -c user.email="aur-publish@localhost" \
                commit -m "${pkg}: update to v${version}"
            git -C "$tmp" push
        fi
    fi

    rm -rf "$tmp"
}

for pkg in "${changed[@]}"; do
    if ! push_one "$pkg"; then
        failures+=("$pkg")
    fi
done

if ((${#failures[@]} > 0)); then
    echo "ERROR: failed to push: ${failures[*]}" >&2
    exit 1
fi
