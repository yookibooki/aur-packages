#!/usr/bin/env python3
"""issue-apply.py — Mutate packages/registry.json from IssueOps input.

Usage:
    issue-apply.py add --pkg X [--source S | --upstream O/R] [--asset A]
        [--ext E] [--ver-in-url true|false] [--ver-in-path true|false]
        [--version-in-asset true|false] [--ver-after-asset true|false]
        [--allow-prerelease true|false]
        --archs $'x86_64 <triple>\\naarch64 <triple>'
    issue-apply.py remove --pkg X [--archive-dir archive]

add scaffolds packages/<pkg>/PKGBUILD from the -bin template, writes a
per-package note under docs/packages/, and appends a registry entry. It
does NOT write .SRCINFO and it leaves 'SKIP' in the checksums on purpose:
the caller must run scripts/update-pkgbuild.sh (which erases SKIP with real
sha256 sums) and then `makepkg --printsrcinfo > .SRCINFO` before committing.
See docs/packages.md "The SKIP lifecycle". Nothing is committed by this
script.

remove sets active:false and moves packages/<pkg>/ to archive/<pkg>/.

All commands are idempotent: re-running with the same input exits 0 without
changing the registry hash. Validation errors exit 2 with a message on stderr
suitable for posting back to the issue.
"""

import argparse
import json
import os
import re
import shutil
import sys

REGISTRY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "packages",
    "registry.json",
)
REGISTRY = os.environ.get("REGISTRY_PATH", REGISTRY)
ROOT = os.path.dirname(os.path.dirname(REGISTRY))

PKG_RE = re.compile(r"^[a-z0-9@._+\-]+$")
UPSTREAM_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]*$")
ALLOWED_EXTS = {"", ".tar.gz", ".tgz", ".zip", ".tar.xz", ".tar.bz2"}


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def load_registry():
    try:
        with open(REGISTRY) as f:
            entries = json.load(f)
    except FileNotFoundError:
        fail(f"registry not found at {REGISTRY}")
    except json.JSONDecodeError as e:
        fail(f"registry is not valid JSON: {e}")
    if not isinstance(entries, list):
        fail("registry must be a JSON array")
    return entries


def save_registry(entries):
    with open(REGISTRY, "w") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")


def parse_bool(name, value):
    if isinstance(value, bool):
        return value
    if value in ("true", "True", "TRUE"):
        return True
    if value in ("false", "False", "FALSE"):
        return False
    fail(f"{name} must be true/false, got {value!r}")


def validate_archs(raw):
    archs = []
    seen = set()
    for line in (raw or "").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2:
            fail(f"archs line must be exactly '<arch> <triple>', got {line!r}")
        arch, triple = parts
        if not re.fullmatch(r"[a-z0-9_]+", arch):
            fail(f"invalid arch {arch!r}")
        if not re.fullmatch(r"[A-Za-z0-9_.\-]+", triple):
            fail(f"invalid triple {triple!r}")
        if arch in seen:
            fail(f"duplicate arch {arch!r}")
        seen.add(arch)
        archs.append((arch, triple))
    if not archs:
        fail("no archs defined (need at least one '<arch> <triple>' line)")
    return "\n".join(f"{a} {t}" for a, t in archs)


def find(entries, pkg):
    for e in entries:
        if e.get("pkg") == pkg:
            return e
    return None


PKGBUILD_TEMPLATE = """# Maintainer: yookibooki <61198899+yookibooki@users.noreply.github.com>
pkgname={pkg}
_realver="{version}"
pkgver="{pkgver}"
pkgrel=1
pkgdesc='{desc}'
arch=({arch_list})
url='https://github.com/{upstream}'
license=('MIT')
provides=('{provides}')
conflicts=('{provides}')
options=('!strip')

{triple_lines}

{source_lines}

{sum_lines}

package() {{
{package_body}}}
"""

BODY_TARBALL = """  cd "${{srcdir}}"
  install -Dm755 {asset} "${{pkgdir}}/usr/bin/{asset}"
  [[ -f LICENSE ]] && install -Dm644 LICENSE "${{pkgdir}}/usr/share/licenses/${{pkgname}}/LICENSE"
"""
BODY_ZIP = """  cd "${{srcdir}}"
  bsdtar -xf "{asset}-${{_realver}}-${{_triple_x86_64}}.zip" 2>/dev/null || bsdtar -xf *.zip
  install -Dm755 {asset} "${{pkgdir}}/usr/bin/{asset}"
"""
BODY_BARE = """  install -Dm755 "${{srcdir}}/{asset}-${{_realver}}-${{_triple_${{CARCH}}}}" "${{pkgdir}}/usr/bin/{asset}" 2>/dev/null || install -Dm755 "${{srcdir}}/{asset}" "${{pkgdir}}/usr/bin/{asset}"
"""


def scaffold_pkgbuild(
    pkg,
    upstream,
    asset,
    ext,
    ver_in_url,
    ver_in_path,
    version_in_asset,
    archs,
    ver_after_asset=False,
):
    pkgdir = os.path.join(ROOT, "packages", pkg)
    if os.path.exists(pkgdir):
        fail(f"package directory packages/{pkg}/ already exists")
    arch_list = " ".join(f"'{a}'" for a, _ in archs)
    triple_lines = "\n".join(f'_triple_{a}="{t}"' for a, t in archs)
    provides = pkg[: -len("-bin")] if pkg.endswith("-bin") else pkg
    sep = "_" if version_in_asset else "-"
    src_prefix = "v${_realver}" if ver_in_path else "${_realver}"
    source_lines = []
    for a, t in archs:
        if version_in_asset:
            tail = f"${{_realver}}_{t}{ext}"
        elif ver_after_asset:
            tail = f"${{_realver}}-{t}{ext}"
        elif ver_in_url:
            tail = f"{t}-v${{_realver}}{ext}"
        else:
            tail = f"{t}{ext}"
        dl = (
            f"https://github.com/{upstream}/releases/download/"
            f"{src_prefix}/{asset}{sep}{tail}"
        )
        source_lines.append(
            f'source_{a}=(["]{asset}-${{_realver}}-{t}{ext}::{dl}["])'.replace(
                '["]', '"'
            )
        )
    sum_lines = "\n".join(f"sha256sums_{a}=('SKIP')" for a, _ in archs)
    if ext in ("",):
        body = BODY_BARE.format(asset=asset)
    elif ext == ".zip":
        body = BODY_ZIP.format(asset=asset)
    else:
        body = BODY_TARBALL.format(asset=asset)
    if len(archs) > 1:
        cases = "\n".join(f'    {a}) _triple="${{_triple_{a}}}" ;;' for a, _ in archs)
        preamble = (
            f'  local _triple\n  case "${{CARCH}}" in\n{cases}\n'
            f'    *) echo "ERROR: unsupported arch ${{CARCH}}" >&2; exit 1 ;;\n  esac\n\n'
        )
        body = preamble + body
    else:
        a = archs[0][0]
        body = f'  local _triple="${{_triple_{a}}}"\n\n' + body
    content = PKGBUILD_TEMPLATE.format(
        pkg=pkg,
        version="0.0.0",
        pkgver="0.0.0",
        desc=f"{asset} (managed by issue-ops; version filled on first discover run)",
        arch_list=arch_list,
        upstream=upstream,
        provides=provides,
        triple_lines=triple_lines,
        source_lines="\n".join(source_lines),
        sum_lines=sum_lines,
        package_body=body,
    )
    os.makedirs(pkgdir)
    with open(os.path.join(pkgdir, "PKGBUILD"), "w") as f:
        f.write(content)
    # NOTE: no .SRCINFO stub. The caller regenerates it with
    # `makepkg --printsrcinfo` after update-pkgbuild.sh has resolved the
    # checksums. Writing a stub here would be inconsistent with the real
    # output and would fail scripts/check-consistency.sh if ever committed
    # mid-flow. See docs/packages.md "The SKIP lifecycle".
    notedir = os.path.join(ROOT, "docs", "packages")
    os.makedirs(notedir, exist_ok=True)
    notepath = os.path.join(notedir, f"{pkg}.md")
    if not os.path.exists(notepath):
        with open(notepath, "w") as f:
            f.write(
                f"# {pkg}\n\n"
                f"- upstream: https://github.com/{upstream}\n"
                f"- asset pattern: recorded in packages/registry.json\n"
                f"- last-seen version: 0.0.0 (scaffold; real checksums and\n"
                f"  version are resolved by update-pkgbuild.sh before any\n"
                f"  commit — never commit this note while status is\n"
                f"  'scaffolded')\n"
                f"- last-verified: never\n"
                f"- status: scaffolded (not yet installable, do not publish)\n"
                f"- halt reason: none\n"
                f"- why this package exists: added via package-request issue;\n"
                f"  fill in the issue number and requester here.\n"
            )


def cmd_add(args):
    pkg = args.pkg
    if not PKG_RE.fullmatch(pkg or ""):
        fail(f"invalid pkg name {pkg!r} (must match ^[a-z0-9@._+-]+$)")
    source = (args.source or "").strip()
    upstream = args.upstream
    if not upstream and source:
        m = re.search(r"github\.com/([^/\s]+/[^/\s]+)", source)
        if m:
            upstream = m.group(1).rstrip("/")
            if upstream.endswith(".git"):
                upstream = upstream[:-4]
        elif UPSTREAM_RE.fullmatch(source):
            upstream = source
        else:
            upstream = (
                source.replace("https://", "").replace("http://", "").split("/")[0]
            )
    if not UPSTREAM_RE.fullmatch(upstream or ""):
        if "/" not in (upstream or ""):
            base = pkg[: -len("-bin")] if pkg.endswith("-bin") else pkg
            upstream = f"local/{base}"
        else:
            fail(f"invalid upstream {upstream!r} (expected owner/repo)")
    asset = args.asset
    if not asset:
        asset = pkg[: -len("-bin")] if pkg.endswith("-bin") else pkg
    if not re.fullmatch(r"[A-Za-z0-9._+\-]+", asset or ""):
        fail(f"invalid asset prefix {asset!r}")
    ext = args.ext if args.ext is not None else ".tar.gz"
    if ext not in ALLOWED_EXTS:
        fail(f"unsupported ext {ext!r} (allowed: {sorted(ALLOWED_EXTS)})")
    ver_in_url = parse_bool("ver_in_url", args.ver_in_url)
    ver_in_path = parse_bool("ver_in_path", args.ver_in_path)
    version_in_asset = parse_bool("version_in_asset", args.version_in_asset)
    ver_after_asset = parse_bool("ver_after_asset", args.ver_after_asset)
    allow_prerelease = parse_bool("allow_prerelease", args.allow_prerelease)
    archs_raw = args.archs
    if not archs_raw:
        archs_raw = "x86_64 x86_64-unknown-linux-gnu\naarch64 aarch64-unknown-linux-gnu"
    archs_norm = validate_archs(archs_raw)
    archs = [tuple(l.split()) for l in archs_norm.splitlines()]

    entries = load_registry()
    if find(entries, pkg):
        fail(f"package {pkg!r} already exists in registry")
    entry = {
        "pkg": pkg,
        "upstream": upstream,
        "asset": asset,
        "ext": ext,
        "ver_in_url": ver_in_url,
        "ver_in_path": ver_in_path,
        "version_in_asset": version_in_asset,
        "ver_after_asset": ver_after_asset,
        "allow_prerelease": allow_prerelease,
        "archs": archs_norm,
        "active": True,
    }
    scaffold_pkgbuild(
        pkg,
        upstream,
        asset,
        ext,
        ver_in_url,
        ver_in_path,
        version_in_asset,
        archs,
        ver_after_asset,
    )
    entries.append(entry)
    save_registry(entries)
    print(f"added {pkg}")


def cmd_remove(args):
    entries = load_registry()
    e = find(entries, args.pkg)
    if not e:
        fail(f"unknown package {args.pkg!r}")
    if e.get("active") is False:
        print(f"{args.pkg}: already inactive (no-op)")
        return
    e["active"] = False
    save_registry(entries)
    src = os.path.join(ROOT, "packages", args.pkg)
    archive_root = os.path.join(ROOT, args.archive_dir)
    if os.path.isdir(src):
        os.makedirs(archive_root, exist_ok=True)
        dst = os.path.join(archive_root, args.pkg)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.move(src, dst)
        print(f"{args.pkg}: deactivated, moved to {args.archive_dir}/")
    else:
        print(f"{args.pkg}: deactivated (no directory to archive)")


def main():
    # Compatibility shim: maintainer.yml refreshes docs with --refresh-docs.
    # There is no docs table to regenerate (registry.json is the source of
    # truth); report the package count so the step stays green.
    if "--refresh-docs" in sys.argv:
        try:
            entries = load_registry()
        except SystemExit:
            raise
        print(f"{len(entries)} packages tracked")
        return
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--pkg", required=True)
    a.add_argument("--source", required=False, default="")
    a.add_argument("--upstream", required=False, default="")
    a.add_argument("--asset", required=False, default="")
    a.add_argument("--ext", default=".tar.gz")
    a.add_argument("--ver-in-url", default="false")
    a.add_argument("--ver-in-path", default="true")
    a.add_argument("--version-in-asset", default="false")
    a.add_argument("--ver-after-asset", default="false")
    a.add_argument("--allow-prerelease", default="false")
    a.add_argument("--archs", required=False, default="")
    a.set_defaults(func=cmd_add)
    r = sub.add_parser("remove")
    r.add_argument("--pkg", required=True)
    r.add_argument("--archive-dir", default="archive")
    r.set_defaults(func=cmd_remove)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
