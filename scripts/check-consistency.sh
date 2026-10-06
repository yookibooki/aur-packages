#!/usr/bin/env bash
# check-consistency.sh — registry, PKGBUILD and .SRCINFO must agree.
set -euo pipefail

cd "$(dirname "$0")/.."

failures=0
fail() { echo "FAIL: $*" >&2; failures=$((failures + 1)); }

for f in scripts/*.sh ./aur; do
    bash -n "$f" || fail "syntax error in $f"
done
for pkgdir in packages/*/; do
    [[ -f "$pkgdir/PKGBUILD" ]] || continue
    bash -n "$pkgdir/PKGBUILD" || fail "syntax error in ${pkgdir}PKGBUILD"
done
python3 -m py_compile scripts/issue-apply.py scripts/probe-upstream.py \
    || fail "syntax error in a python script"
rm -rf scripts/__pycache__

REGISTRY="packages/registry.json"
[[ -f "$REGISTRY" ]] || fail "missing $REGISTRY"
export CHECK_ROOT="$PWD" CHECK_REGISTRY="$REGISTRY"
python3 - <<'EOF'
import json, os, re, sys

root = os.environ["CHECK_ROOT"]
registry_rel = os.environ.get("CHECK_REGISTRY", "packages/registry.json")
errors = []
def fail(msg):
    errors.append(msg)
    print(f"FAIL: {msg}", file=sys.stderr)

try:
    entries = json.load(open(os.path.join(root, registry_rel)))
except Exception as e:
    fail(f"{registry_rel} is not valid JSON: {e}")
    sys.exit(1)

if not isinstance(entries, list) or not entries:
    fail(f"{registry_rel} must be a non-empty array")

seen_pkgs = set()
for e in entries if isinstance(entries, list) else []:
    for key in ("pkg", "upstream", "asset", "archs"):
        if key not in e:
            fail(f"entry {e.get('pkg', '?')}: missing key {key!r}")
    for key in ("ver_in_url", "ver_in_path", "version_in_asset", "ver_after_asset", "allow_prerelease"):
        if key in e and e[key] not in (True, False, "true", "false"):
            fail(f"entry {e.get('pkg', '?')}: {key} must be true/false, got {e[key]!r}")
    if "active" not in e:
        fail(f"entry {e.get('pkg', '?')}: missing key 'active'")
    elif e["active"] not in (True, False, "true", "false"):
        fail(f"entry {e.get('pkg', '?')}: active must be true/false, got {e['active']!r}")
    if "ext" in e and not isinstance(e["ext"], str):
        fail(f"entry {e.get('pkg', '?')}: ext must be a string, got {e['ext']!r}")
    upstream = e.get("upstream", "")
    if not re.fullmatch(r"[^/\s]+/[^/\s]+", upstream or ""):
        fail(f"entry {e.get('pkg', '?')}: invalid upstream {upstream!r} (expected owner/repo)")
    pkg = e.get("pkg", "?")
    if pkg in seen_pkgs:
        fail(f"duplicate pkg entry {pkg!r}")
    seen_pkgs.add(pkg)
    if not re.fullmatch(r"[a-z0-9@._+-]+", pkg or ""):
        fail(f"invalid pkg name {pkg!r}")

    archs = []
    for line in (e.get("archs") or "").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2:
            fail(f"{pkg}: archs line must be exactly '<arch> <triple>', got {line!r}")
            continue
        archs.append(parts[0])
    if len(set(archs)) != len(archs):
        fail(f"{pkg}: duplicate arch in archs")
    if not archs:
        fail(f"{pkg}: no archs defined")

    pkgb = os.path.join(root, "packages", pkg, "PKGBUILD")
    srcinfo = os.path.join(root, "packages", pkg, ".SRCINFO")
    if e.get("active", True) not in (True, "true"):
        if os.path.exists(os.path.join(root, "packages", pkg)):
            fail(f"{pkg}: inactive but packages/{pkg}/ still exists (move to archive/)")
        continue
    if not os.path.isfile(pkgb):
        fail(f"{pkg}: missing PKGBUILD")
        continue
    if not os.path.isfile(srcinfo):
        fail(f"{pkg}: missing .SRCINFO")
        continue
    pb = open(pkgb).read()
    si = open(srcinfo).read()

    m = re.search(r"^pkgver=(.*)$", pb, re.M)
    if not m:
        fail(f"{pkg}: PKGBUILD has no pkgver")
        continue
    pkgver = m.group(1).strip().strip("\"'")
    mr = re.search(r"^_realver=(.*)$", pb, re.M)
    realver = mr.group(1).strip().strip("\"'") if mr else pkgver
    m2 = re.search(r"^\s*pkgver\s*=\s*(\S+)", si, re.M)
    if not m2 or m2.group(1) != pkgver:
        fail(f"{pkg}: .SRCINFO pkgver ({m2.group(1) if m2 else '?'}) != PKGBUILD pkgver ({pkgver})")

    if "options = !strip" not in si:
        fail(f"{pkg}: .SRCINFO missing 'options = !strip'")

    prefix = f"https://github.com/{upstream}/releases/download/"
    for msrc in re.finditer(r"^source_[a-z0-9_]+=\((.*)\)$", pb, re.M):
        for url in re.findall(r"https?://\S+", msrc.group(1)):
            url = url.rstrip("\"')")
            if not url.startswith(prefix):
                fail(f"{pkg}: source URL {url!r} outside {prefix}")

    if "'SKIP'" in pb:
        fail(f"{pkg}: PKGBUILD contains SKIP checksums")

    for arch in archs:
        for var in (f"source_{arch}", f"sha256sums_{arch}"):
            pm = re.search(rf"^{var}=\((.*)\)$", pb, re.M)
            if not pm:
                fail(f"{pkg}: PKGBUILD missing {var}= line")
                continue
            sm = re.search(rf"^\s*{var}\s*=\s*(.*)$", si, re.M)
            if not sm:
                fail(f"{pkg}: .SRCINFO missing {var}")
                continue
            pb_val = pm.group(1).strip().strip("\"'")
            pb_val = pb_val.replace("${_realver}", realver).replace("${pkgver}", pkgver)
            si_val = sm.group(1).strip()
            if pb_val != si_val:
                fail(f"{pkg}: {var} differs between PKGBUILD and .SRCINFO")

sys.exit(1 if errors else 0)
EOF
((failures == 0)) || exit 1
echo "Consistency check passed."
