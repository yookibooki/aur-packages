#!/usr/bin/env bash
# update-pkgbuild.sh — Update an AUR PKGBUILD with a new upstream release.
set -euo pipefail

usage() {
    cat >&2 <<EOF
Usage: echo '<arch triple>...' | $0 <pkgdir> <version> <asset> <ext> <ver_in_url> <upstream> [ver_in_path]

Arguments:
  pkgdir      path to the package directory containing PKGBUILD
  version     new upstream version (e.g. "1.2.3")
  asset       tarball/binary prefix (e.g. "mpatch")
  ext         file extension, may be empty (e.g. ".tar.gz" or "")
  ver_in_url  "true" if the URL embeds "-v<VERSION>" before the extension
  upstream    "owner/repo" for GitHub release downloads
  ver_in_path "true" (default) if release tags use a "v" prefix (e.g. "v1.2.3")

Stdin: arch-triple pairs, one per line: "arch triple"
EOF
    exit 1
}

validate_bool() {
    local name="$1" value="$2"
    if [[ "$value" != "true" && "$value" != "false" ]]; then
        echo "ERROR: ${name} must be \"true\" or \"false\", got \"${value}\"" >&2
        exit 1
    fi
}

download_url_suffix() {
    local triple="$1" ver_in_url="$2" version="$3" ext="$4"
    if [[ "$ver_in_url" == "true" ]]; then
        printf '%s-v%s%s' "$triple" "$version" "$ext"
    else
        printf '%s%s' "$triple" "$ext"
    fi
}

source_url_suffix() {
    local triple="$1" ver_in_url="$2" ext="$3"
    # Uses \${pkgver} so the variable reference stays literal in PKGBUILD
    if [[ "$ver_in_url" == "true" ]]; then
        printf '%s-v${pkgver}%s' "$triple" "$ext"
    else
        printf '%s%s' "$triple" "$ext"
    fi
}

url_version_prefix() {
    local ver_in_path="$1"
    if [[ "$ver_in_path" == "true" ]]; then
        printf 'v%s' "$2"
    else
        printf '%s' "$2"
    fi
}

main() {
    local pkgdir="$1" version="$2" asset="$3" ext="$4" ver_in_url="$5" upstream="$6"
    local ver_in_path="${7:-true}"

    # Input validation
    validate_bool "ver_in_url" "$ver_in_url"
    validate_bool "ver_in_path" "$ver_in_path"
    if [[ -n "$ext" && "$ext" != .* ]]; then
        echo "ERROR: ext must be empty or start with a dot, got \"${ext}\"" >&2
        exit 1
    fi

    cd "$pkgdir"

    # Buffer entries for two passes (download, then checksum+sed)
    local entries=()
    local arch triple
    while read -r arch triple; do
        [[ -z "$arch" ]] && continue
        entries+=("${arch}|${triple}")
    done

    sed -i "s/^pkgver=.*/pkgver=${version}/; s/^pkgrel=.*/pkgrel=1/" PKGBUILD

    _AUR_UPDATE_TMP=$(mktemp -d)
    trap 'rm -rf "$_AUR_UPDATE_TMP"' EXIT

    local pids=()
    local entry suffix url version_prefix
    version_prefix="$(url_version_prefix "$ver_in_path" "$version")"
    for entry in "${entries[@]}"; do
        arch="${entry%%|*}"
        triple="${entry#*|}"
        suffix="$(download_url_suffix "$triple" "$ver_in_url" "$version" "$ext")"
        url="https://github.com/${upstream}/releases/download/${version_prefix}/${asset}-${suffix}"
        curl -fsSL "$url" -o "${_AUR_UPDATE_TMP}/${asset}-${arch}${ext}" &
        pids+=($!)
    done
    for pid in "${pids[@]}"; do
        wait "$pid" || { echo "ERROR: download failed (pid $pid)" >&2; exit 1; }
    done

    local sum src_suffix pkgver_version_prefix
    pkgver_version_prefix="$(url_version_prefix "$ver_in_path" '${pkgver}')"
    for entry in "${entries[@]}"; do
        arch="${entry%%|*}"
        triple="${entry#*|}"
        sum=$(sha256sum "${_AUR_UPDATE_TMP}/${asset}-${arch}${ext}" | cut -d' ' -f1)
        src_suffix="$(source_url_suffix "$triple" "$ver_in_url" "$ext")"
        sed -i "s|^source_${arch}=.*|source_${arch}=(\"${asset}-\${pkgver}-${triple}${ext}::https://github.com/${upstream}/releases/download/${pkgver_version_prefix}/${asset}-${src_suffix}\")|" PKGBUILD
        sed -i "s|^sha256sums_${arch}=.*|sha256sums_${arch}=('${sum}')|" PKGBUILD
    done
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if (($# < 6)); then usage; fi
    main "$@"
fi
