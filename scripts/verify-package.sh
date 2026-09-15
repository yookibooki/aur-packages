#!/usr/bin/env bash
set -euo pipefail

if (($# != 1)); then
    echo "Usage: $0 <pkgdir>" >&2
    exit 1
fi
pkgdir="$1"
[[ -f "$pkgdir/PKGBUILD" ]] || { echo "ERROR: no PKGBUILD in $pkgdir" >&2; exit 1; }

failures=0
fail() { echo "FAIL: $*" >&2; failures=$((failures + 1)); }

echo "==> bash -n $pkgdir/PKGBUILD"
bash -n "$pkgdir/PKGBUILD" || fail "bash syntax error"

if command -v shellcheck >/dev/null 2>&1; then
    echo "==> shellcheck $pkgdir/PKGBUILD"
    shellcheck --severity=warning "$pkgdir/PKGBUILD" || fail "shellcheck warnings"
else
    echo "SKIP: shellcheck not installed"
fi

if grep -q "'SKIP'" "$pkgdir/PKGBUILD"; then
    fail "PKGBUILD contains SKIP checksums (run update-pkgbuild.sh first)"
fi
if grep -Eq "sha256sums_[a-z0-9_]+\=\(''\)" "$pkgdir/PKGBUILD"; then
    fail "PKGBUILD contains empty checksums"
fi

if command -v makepkg >/dev/null 2>&1; then
    echo "==> makepkg --printsrcinfo diff"
    want="$(cd "$pkgdir" && makepkg --printsrcinfo)"
    if ! diff -u "$pkgdir/.SRCINFO" <(printf '%s\n' "$want"); then
        fail ".SRCINFO is stale (regenerate with makepkg --printsrcinfo)"
    fi
    echo "==> makepkg --verifysource"
    (cd "$pkgdir" && makepkg --verifysource) || fail "--verifysource failed"
else
    echo "SKIP: makepkg not installed (chroot build in verify.yml is authoritative)"
fi

if command -v namcap >/dev/null 2>&1; then
    echo "==> namcap PKGBUILD"
    namcap -e carch "$pkgdir/PKGBUILD" || fail "namcap PKGBUILD warnings"
else
    echo "SKIP: namcap not installed"
fi

if ((failures > 0)); then
    echo "ERROR: $failures verification failure(s) in $pkgdir" >&2
    exit 1
fi
echo "Verified $pkgdir."
