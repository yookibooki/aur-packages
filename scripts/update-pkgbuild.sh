#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat >&2 <<EOF
Usage: echo '<arch triple>...' | $0 <pkgdir> <version> <asset> <ext> <ver_in_url> <upstream> [ver_in_path] [version_in_asset] [ver_after_asset]

Arguments:
  pkgdir           path to the package directory containing PKGBUILD
  version          new upstream version (e.g. "1.2.3")
  asset            tarball/binary prefix (e.g. "mpatch")
  ext              file extension, may be empty (e.g. ".tar.gz" or "")
  ver_in_url       "true" if the URL embeds "-v<VERSION>" before the extension
  upstream         "owner/repo" for GitHub release downloads
  ver_in_path      "true" (default) if release tags use a "v" prefix (e.g. "v1.2.3")
  version_in_asset "true" (default false) if asset is <name>_<version>_<triple><ext>
  ver_after_asset  "true" (default false) if asset is <name>-<version>-<triple><ext>

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

asset_tail() {
    local triple="$1" ver_in_url="$2" version="$3" ext="$4" version_in_asset="$5" ver_after_asset="${6:-false}"
    if [[ "$version_in_asset" == "true" ]]; then
        printf '%s_%s%s' "$version" "$triple" "$ext"
    elif [[ "$ver_after_asset" == "true" ]]; then
        printf '%s-%s%s' "$version" "$triple" "$ext"
    elif [[ "$ver_in_url" == "true" ]]; then
        printf '%s-v%s%s' "$triple" "$version" "$ext"
    else
        printf '%s%s' "$triple" "$ext"
    fi
}

if (($# < 6)); then usage; fi

pkgdir="$1"
version="$2"
asset="$3"
ext="$4"
ver_in_url="${5:-false}"
upstream="$6"
ver_in_path="${7:-true}"
version_in_asset="${8:-false}"
ver_after_asset="${9:-false}"

if [[ -n "$ext" && "$ext" != .* ]]; then
    echo "ERROR: ext must be empty or start with a dot, got \"${ext}\"" >&2
    exit 1
fi
validate_bool ver_in_url "$ver_in_url"
validate_bool ver_in_path "$ver_in_path"
validate_bool version_in_asset "$version_in_asset"
validate_bool ver_after_asset "$ver_after_asset"

if [[ ! "$version" =~ ^[A-Za-z0-9][A-Za-z0-9._+-]*$ ]]; then
    echo "ERROR: version \"${version}\" contains characters unsafe for PKGBUILDs/URLs" >&2
    exit 1
fi

# These values are interpolated into `sed` replacement text delimited by
# `|`. Restricting them to this character set (the same one
# scripts/issue-apply.py writes into the registry) makes `|`, `&` and `\`
# impossible, so no sed replacement injection is reachable from
# registry-fed input.
if [[ ! "$asset" =~ ^[A-Za-z0-9._+-]+$ ]]; then
    echo "ERROR: asset must match ^[A-Za-z0-9._+-]+$, got \"${asset}\"" >&2
    exit 1
fi
if [[ -n "$ext" && ! "$ext" =~ ^\.[A-Za-z0-9._-]+$ ]]; then
    echo "ERROR: ext must be empty or match ^\\.[A-Za-z0-9._-]+$, got \"${ext}\"" >&2
    exit 1
fi
if [[ ! "$upstream" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
    echo "ERROR: upstream must be \"owner/repo\" with safe characters, got \"${upstream}\"" >&2
    exit 1
fi
if [[ ! -d "$pkgdir" ]]; then
    echo "ERROR: pkgdir \"${pkgdir}\" does not exist or is not a directory" >&2
    exit 1
fi
if [[ ! -f "$pkgdir/PKGBUILD" ]]; then
    echo "ERROR: no PKGBUILD in \"${pkgdir}\"" >&2
    exit 1
fi

expected_prefix="https://github.com/${upstream}/releases/download/"
if grep -E '^source_[a-z0-9_]+=' "$pkgdir/PKGBUILD" | grep -vqF "$expected_prefix"; then
    echo "ERROR: existing source_* URL does not start with ${expected_prefix}" >&2
    exit 1
fi

entries=()
declare -A seen=()
while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    read -ra fields <<< "$line"
    if ((${#fields[@]} != 2)); then
        echo "ERROR: invalid arch/triple line \"${line}\" (expected exactly '<arch> <triple>')" >&2
        exit 1
    fi
    arch="${fields[0]}"
    triple="${fields[1]}"
    if [[ ! "$arch" =~ ^[a-z0-9_]+$ ]]; then
        echo "ERROR: invalid arch \"${arch}\" (must match ^[a-z0-9_]+$)" >&2
        exit 1
    fi
    if [[ ! "$triple" =~ ^[A-Za-z0-9_.-]+$ ]]; then
        echo "ERROR: invalid triple \"${triple}\" (must match ^[A-Za-z0-9_.-]+$)" >&2
        exit 1
    fi
    if [[ -n "${seen[$arch]:-}" ]]; then
        echo "ERROR: duplicate arch \"${arch}\" on stdin" >&2
        exit 1
    fi
    seen[$arch]=1
    entries+=("${arch}|${triple}")
done
if ((${#entries[@]} == 0)); then
    echo "ERROR: no arch/triple entries provided on stdin" >&2
    exit 1
fi

cd "$pkgdir"

for entry in "${entries[@]}"; do
    arch="${entry%%|*}"
    if ! grep -q "^source_${arch}=" PKGBUILD || ! grep -q "^sha256sums_${arch}=" PKGBUILD; then
        echo "ERROR: PKGBUILD has no source_${arch}/sha256sums_${arch} line; add it manually" >&2
        exit 1
    fi
done

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

if [[ "$ver_in_path" == "true" ]]; then
    version_prefix="v${version}"
    src_prefix='v${_realver}'
else
    version_prefix="$version"
    src_prefix='${_realver}'
fi
[[ "$version_in_asset" == "true" ]] && sep="_" || sep="-"

pids=()
for entry in "${entries[@]}"; do
    arch="${entry%%|*}"
    triple="${entry#*|}"
    url="https://github.com/${upstream}/releases/download/${version_prefix}/${asset}${sep}$(asset_tail "$triple" "$ver_in_url" "$version" "$ext" "$version_in_asset" "$ver_after_asset")"
    echo "Downloading ${arch}: ${url}"
    curl -fsSL --retry 3 --retry-all-errors --connect-timeout 10 --max-time 600 \
        "$url" -o "${tmp_dir}/${asset}-${arch}${ext}" &
    pids+=($!)
done

failed=0
for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
        failed=1
    fi
done
if ((failed)); then
    echo "ERROR: one or more downloads failed (see above)" >&2
    exit 1
fi

declare -A sums=()
for entry in "${entries[@]}"; do
    arch="${entry%%|*}"
    f="${tmp_dir}/${asset}-${arch}${ext}"
    if [[ ! -s "$f" ]]; then
        echo "ERROR: downloaded file for ${arch} is missing or empty: ${f}" >&2
        exit 1
    fi
    sums[$arch]="$(sha256sum "$f" | cut -d' ' -f1)"
    if [[ ! "${sums[$arch]}" =~ ^[0-9a-f]{64}$ ]]; then
        echo "ERROR: bad sha256 for ${arch}: ${sums[$arch]}" >&2
        exit 1
    fi
done

current_realver="$(bash -c 'set -u; source ./PKGBUILD; printf %s "${_realver:-$pkgver}"' 2>/dev/null || true)"
current_pkgrel="$(bash -c 'source ./PKGBUILD; printf %s "${pkgrel:-1}"' 2>/dev/null || true)"
[[ "$current_pkgrel" =~ ^[0-9]+$ ]] || current_pkgrel=1
if [[ "$version" == "$current_realver" ]]; then
    new_pkgrel=$((current_pkgrel + 1))
else
    new_pkgrel=1
fi
if [[ "$version" == "$current_realver" ]]; then
    unchanged=true
    for entry in "${entries[@]}"; do
        arch="${entry%%|*}"
        old="$(grep "^sha256sums_${arch}=" PKGBUILD | grep -o '[0-9a-f]\{64\}' || true)"
        if [[ "$old" != "${sums[$arch]}" ]]; then unchanged=false; break; fi
    done
    if [[ "$unchanged" == true ]]; then
        echo "PKGBUILD already up to date at ${version}"
        exit 0
    fi
fi
sanitized_version="${version//[-+]/_}"
if grep -q '^_realver=' PKGBUILD; then
    sed -i "s/^_realver=.*/_realver=\"${version}\"/" PKGBUILD
else
    sed -i "/^pkgver=/i _realver=\"${version}\"" PKGBUILD
fi
sed -i "s/^pkgver=.*/pkgver=\"${sanitized_version}\"/; s/^pkgrel=.*/pkgrel=${new_pkgrel}/" PKGBUILD

for entry in "${entries[@]}"; do
    arch="${entry%%|*}"
    triple="${entry#*|}"
    src_tail="$(asset_tail "$triple" "$ver_in_url" '${_realver}' "$ext" "$version_in_asset" "$ver_after_asset")"
    sed -i "s|^source_${arch}=.*|source_${arch}=(\"${asset}-\${_realver}-${triple}${ext}::https://github.com/${upstream}/releases/download/${src_prefix}/${asset}${sep}${src_tail}\")|" PKGBUILD
    sed -i "s|^sha256sums_${arch}=.*|sha256sums_${arch}=('${sums[$arch]}')|" PKGBUILD
done

bash -n PKGBUILD
echo "Updated PKGBUILD to ${version} (pkgver=${sanitized_version})"
