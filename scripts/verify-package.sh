#!/usr/bin/env bash
set -euo pipefail

(($# == 1)) || { echo "Usage: $0 <pkgdir>" >&2; exit 1; }
pkgdir="$1"
[[ -f "$pkgdir/PKGBUILD" ]] || { echo "ERROR: no PKGBUILD in $pkgdir" >&2; exit 1; }
command -v makepkg >/dev/null 2>&1 || { echo "ERROR: makepkg is required" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -ne 0 ]] || { echo "ERROR: makepkg refuses root; run unprivileged" >&2; exit 1; }

failures=0
fail() { echo "FAIL: $*" >&2; failures=$((failures + 1)); }

echo "==> bash -n"
bash -n "$pkgdir/PKGBUILD" || fail "bash syntax error"

if grep -q "'SKIP'" "$pkgdir/PKGBUILD"; then
    fail "SKIP checksums (run ./aur bump <pkg> first)"
fi
if grep -Eq "sha256sums_[a-z0-9_]+=\(''\)" "$pkgdir/PKGBUILD"; then
    fail "empty checksums"
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp "$pkgdir/PKGBUILD" "$work/"

echo "==> makepkg --printsrcinfo diff"
if ! diff -u "$pkgdir/.SRCINFO" <(cd "$work" && makepkg --printsrcinfo); then
    fail ".SRCINFO is stale (regenerate: cd $pkgdir && makepkg --printsrcinfo > .SRCINFO)"
fi

echo "==> makepkg --verifysource"
(cd "$work" && makepkg --verifysource) || fail "--verifysource (download or sha256 mismatch)"

if ((failures > 0)); then
    echo "ERROR: $failures failure(s) in $pkgdir" >&2
    exit 1
fi
echo "OK: $pkgdir"
