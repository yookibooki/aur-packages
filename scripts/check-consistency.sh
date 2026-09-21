#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

failures=0
fail() { echo "FAIL: $*" >&2; failures=$((failures + 1)); }

for f in scripts/*.sh; do
    bash -n "$f" || fail "syntax error in $f"
done
for pkgdir in packages/*/; do
    [[ -f "$pkgdir/PKGBUILD" ]] || continue
    bash -n "$pkgdir/PKGBUILD" || fail "syntax error in ${pkgdir}PKGBUILD"
done
if command -v python3 >/dev/null 2>&1; then
    python3 -m py_compile scripts/issue-apply.py || fail "syntax error in scripts/issue-apply.py"
fi

if command -v shellcheck >/dev/null 2>&1; then
    shellcheck --severity=warning scripts/*.sh || fail "shellcheck warnings"
    for pkgdir in packages/*/; do
        [[ -f "$pkgdir/PKGBUILD" ]] || continue
        shellcheck --severity=error --shell=bash "$pkgdir/PKGBUILD" || fail "shellcheck errors in ${pkgdir}PKGBUILD"
    done
else
    echo "SKIP: shellcheck not installed" >&2
fi

REGISTRY="packages/registry.json"
if [[ ! -f "$REGISTRY" ]]; then
    if [[ -f ".github/packages.json" ]]; then
        echo "WARN: $REGISTRY missing, falling back to .github/packages.json" >&2
        REGISTRY=".github/packages.json"
    else
        fail "missing $REGISTRY"
    fi
fi
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
    for key in ("active",):
        if key not in e:
            fail(f"entry {e.get('pkg', '?')}: missing key {key!r}")
        elif e[key] not in (True, False, "true", "false"):
            fail(f"entry {e.get('pkg', '?')}: {key} must be true/false, got {e[key]!r}")
    for key in ("ext",):
        if key in e and not isinstance(e[key], str):
            fail(f"entry {e.get('pkg', '?')}: {key} must be a string, got {e[key]!r}")
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
    active = e.get("active", True)
    is_active = active in (True, "true")
    if not is_active:
        if os.path.exists(os.path.join(root, "packages", pkg)):
            fail(f"{pkg}: inactive but packages/{pkg}/ still exists (move to archive/)")
        continue
    if not os.path.isfile(pkgb):
        fail(f"{pkg}: missing PKGBUILD")
        continue
    if not os.path.isfile(srcinfo):
        fail(f"{pkg}: missing .SRCINFO")
        continue
    with open(pkgb) as f:
        pb = f.read()
    with open(srcinfo) as f:
        si = f.read()

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
REPO_ASSIST=".github/workflows/repo-assist.lock.yml"
if [[ ! -f "$REPO_ASSIST" ]]; then
    fail "missing $REPO_ASSIST (primary automation)"
else
    grep -q 'schedule:' "$REPO_ASSIST" || fail "$REPO_ASSIST must trigger on schedule"
    grep -q 'workflow_dispatch:' "$REPO_ASSIST" || fail "$REPO_ASSIST must trigger on workflow_dispatch"
    grep -q 'repo-assist' "$REPO_ASSIST" || fail "$REPO_ASSIST must reference repo-assist"
    for trigger in 'issues:' 'issue_comment:'; do
        grep -q "$trigger" "$REPO_ASSIST" || fail "$REPO_ASSIST missing trigger $trigger"
    done
fi

[[ -f ".github/workflows/lint.yml" ]] || fail "missing .github/workflows/lint.yml"

# Check the Repo Assist workflow source exists and has its key sections.
# The source is the .md; the .lock.yml above is generated from it by
# `gh aw compile`. Section names below match the actual document.
if [[ -f ".github/workflows/repo-assist.md" ]]; then
    grep -q '## Non-Command Mode' .github/workflows/repo-assist.md || fail "repo-assist.md missing ## Non-Command Mode"
    grep -q '## Memory' .github/workflows/repo-assist.md || fail "repo-assist.md missing ## Memory"
else
    fail "missing .github/workflows/repo-assist.md (source)"
fi

[[ -e ".agent" ]] && fail "forbidden path .agent/ exists"
[[ -e "docs/sepo-setup.md" ]] && fail "forbidden file docs/sepo-setup.md exists"
[[ -e "Docs/sepo-setup.md" ]] && fail "forbidden file Docs/sepo-setup.md exists"
if grep -rEi '@(claude|codex|copilot|cursor|gemini|chatgpt)' .github/workflows/ docs/ scripts/ 2>/dev/null; then
    fail "forbidden bot mention string found"
fi

[[ -f "docs/STATE.md" ]] || fail "missing docs/STATE.md (repo status, heartbeat)"
if [[ -f "docs/STATE.md" ]]; then
    grep -qE '^- heartbeat: [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}Z' docs/STATE.md \
        || fail "docs/STATE.md has no heartbeat timestamp line ('- heartbeat: YYYY-MM-DDTHH:MMZ')"
fi
if [[ -f "packages/registry.json" ]]; then
    while IFS= read -r pkg; do
        [[ -n "$pkg" ]] || continue
        [[ -f "docs/packages/$pkg.md" ]] || fail "missing docs/packages/$pkg.md (per-package status note)"
    done < <(python3 -c "import json; [print(e['pkg']) for e in json.load(open('packages/registry.json')) if e.get('active', True) in (True, 'true')]")
fi

((failures == 0)) || exit 1

echo "Consistency check passed."
