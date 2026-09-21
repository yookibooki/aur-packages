#!/usr/bin/env python3
"""probe-upstream.py — Infer registry fields from a GitHub upstream's releases.

Usage:
    probe-upstream.py --upstream owner/repo --pkg mypkg-bin [--tag v1.2.3]
    probe-upstream.py --upstream owner/repo --pkg mypkg-bin --assets-json assets.json [--tag v1.2.3]

Resolves the latest stable release (unless --tag is given), lists its assets
via `gh`, filters to Linux runtime assets, and matches them against the five
asset patterns in docs/packages.md. Prints a JSON object on stdout:

    {"upstream": ..., "tag": ..., "version": ..., "asset": ...,
     "ext": ..., "ver_in_url": ..., "ver_in_path": ...,
     "version_in_asset": ..., "ver_after_asset": ...,
     "allow_prerelease": false, "archs": "x86_64 <triple>\\naarch64 <triple>"}

Exit 0 on success. Exit 2 with an ERROR on stderr when nothing matches
(suitable for posting back to the issue). Stdlib only.

--assets-json bypasses `gh` (tests / offline): a JSON array of asset names,
or an object with an "assets" key holding names or {"name": ...} objects.
"""

import argparse
import json
import re
import subprocess
import sys

KNOWN_TRIPLES = [
    "x86_64-unknown-linux-gnu",
    "aarch64-unknown-linux-gnu",
    "armv7-unknown-linux-gnueabihf",
    "armv7l-unknown-linux-gnueabihf",
    "x86_64-unknown-linux-musl",
    "aarch64-unknown-linux-musl",
    "x86_64-linux-gnu",
    "aarch64-linux-gnu",
    "linux_amd64",
    "linux_arm64",
    "linux-amd64",
    "linux-arm64",
    "amd64-linux",
    "arm64-linux",
]

TRIPLE_TO_ARCH = {
    "x86_64-unknown-linux-gnu": "x86_64",
    "aarch64-unknown-linux-gnu": "aarch64",
    "armv7-unknown-linux-gnueabihf": "armv7h",
    "armv7l-unknown-linux-gnueabihf": "armv7h",
    "x86_64-unknown-linux-musl": "x86_64",
    "aarch64-unknown-linux-musl": "aarch64",
    "x86_64-linux-gnu": "x86_64",
    "aarch64-linux-gnu": "aarch64",
    "linux_amd64": "x86_64",
    "linux_arm64": "aarch64",
    "linux-amd64": "x86_64",
    "linux-arm64": "aarch64",
    "amd64-linux": "x86_64",
    "arm64-linux": "aarch64",
}

SKIP_SUFFIXES = (".sig", ".sha256", ".md5", ".asc", ".pem", ".json", ".txt")
SKIP_DESKTOP = (".deb", ".rpm", ".AppImage", ".dmg", ".exe", ".msi")
ALLOWED_EXTS = ("", ".tar.gz", ".tgz", ".zip", ".tar.xz", ".tar.bz2")


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def run_gh(*args):
    try:
        out = subprocess.run(
            ["gh"] + list(args), capture_output=True, text=True, timeout=60
        )
    except FileNotFoundError:
        fail("`gh` CLI is not installed")
    except subprocess.TimeoutExpired:
        fail("`gh` timed out")
    if out.returncode != 0:
        fail(f"`gh {' '.join(args)}` failed: {out.stderr.strip()[:500]}")
    return out.stdout.strip()


def version_key(tag):
    """Sort key approximating `sort -V` for release tags."""
    s = tag[1:] if tag.startswith("v") else tag
    parts = re.split(r"[._+\-]+", s)
    key = []
    for p in parts:
        key.append((0, int(p)) if p.isdigit() else (1, p))
    return key


def run_gh_safe(*args):
    """Run gh, return stdout (empty on failure). Never exits."""
    try:
        out = subprocess.run(
            ["gh"] + list(args), capture_output=True, text=True, timeout=60
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if out.returncode != 0:
        return ""
    return out.stdout.strip()


def latest_tag(upstream, allow_prerelease):
    # Prefer an explicit non-draft, non-prerelease listing.
    # `gh release view` (GitHub's "latest") first, `gh release list`
    # only as a fallback. The list endpoint returns creation order,
    # not version order, so sort the fallback by version.
    if allow_prerelease:
        raw = run_gh_safe("release", "view", "-R", upstream,
                          "--json", "tagName", "--jq", ".tagName")
        if raw and raw != "null":
            return raw
    else:
        raw = run_gh_safe("release", "view", "-R", upstream,
                          "--json", "tagName,isPrerelease",
                          "--jq", "select(.isPrerelease == false) | .tagName")
        if raw and raw != "null":
            return raw
    args = ["release", "list", "-R", upstream, "--exclude-drafts"]
    if not allow_prerelease:
        args.append("--exclude-pre-releases")
    args += ["--limit", "10", "--json", "tagName"]
    raw = run_gh(*args)
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError as e:
        fail(f"could not parse release list for {upstream}: {e}")
    tags = [i.get("tagName", "") for i in items if i.get("tagName")]
    if not tags:
        fail(f"could not determine latest release for {upstream}")
    tags.sort(key=version_key)
    return tags[-1]


def asset_names_for(upstream, tag):
    raw = run_gh_safe("release", "view", tag, "-R", upstream, "--json", "assets")
    if not raw:
        return []
    try:
        assets = json.loads(raw).get("assets", [])
    except json.JSONDecodeError:
        return []
    return [a.get("name", "") for a in assets if a.get("name")]


def load_assets_json(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        fail(f"could not read --assets-json {path}: {e}")
    if isinstance(data, dict):
        data = data.get("assets", [])
    if not isinstance(data, list):
        fail(f"--assets-json {path} must contain a JSON array or an object with an 'assets' array")
    names = []
    for item in data:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("name"):
            names.append(item["name"])
    return names


def split_ext(name):
    low = name.lower()
    for ext in (".tar.gz", ".tar.xz", ".tar.bz2", ".tgz", ".zip"):
        if low.endswith(ext):
            return name[: -len(ext)], name[-len(ext):]
    return name, ""


def find_triple(name):
    for triple in KNOWN_TRIPLES:
        if triple in name:
            return triple
    return None


def candidate_linux_assets(names):
    kept = []
    for n in names:
        low = n.lower()
        if low.endswith(SKIP_SUFFIXES) or low.endswith(SKIP_DESKTOP):
            continue
        if "linux" in low or "amd64" in low or "arm64" in low:
            kept.append(n)
    return kept


def infer(names, version, pkg):
    cands = candidate_linux_assets(names)
    if not cands:
        fail(
            "no Linux runtime assets found in this release "
            f"({len(names)} assets total). "
            "This tool only packages Linux x86_64/aarch64 binaries; "
            "if the upstream ships Linux builds under other names, "
            "tell us the exact asset file names."
        )
    votes = []
    for full in cands:
        stem, ext = split_ext(full)
        if ext not in ALLOWED_EXTS:
            continue
        triple = find_triple(full)
        if not triple:
            continue
        m_underscore = re.fullmatch(
            r"(?P<asset>.+?)_(?P<ver>\d[\w._+\-]*?)_(?P<triple>.+)", stem
        )
        m_dash = re.fullmatch(
            r"(?P<asset>.+?)-(?P<ver>\d[\w._+\-]*?)-(?P<triple>.+)", stem
        )
        m_vurl = re.fullmatch(
            r"(?P<asset>.+?)-(?P<triple>.+?)-v(?P<ver>\d[\w._+\-]*?)", stem
        )
        flags = None
        asset = None
        if m_underscore and m_underscore.group("triple") == triple:
            ver = m_underscore.group("ver")
            if ver == version:
                flags = {"version_in_asset": True, "ver_after_asset": False,
                         "ver_in_url": False}
                asset = m_underscore.group("asset")
        if flags is None and m_dash and m_dash.group("triple") == triple:
            ver = m_dash.group("ver")
            if ver == version:
                flags = {"version_in_asset": False, "ver_after_asset": True,
                         "ver_in_url": False}
                asset = m_dash.group("asset")
        if flags is None and m_vurl and m_vurl.group("triple") == triple:
            ver = m_vurl.group("ver")
            if ver == version:
                flags = {"version_in_asset": False, "ver_after_asset": False,
                         "ver_in_url": True}
                asset = m_vurl.group("asset")
        if flags is None:
            # Plain <asset>-<triple> (or <asset>_<triple>), no version in name.
            plain = None
            if stem.endswith("-" + triple):
                plain = stem[: -(len(triple) + 1)]
            elif stem.endswith("_" + triple):
                plain = stem[: -(len(triple) + 1)]
            elif stem == triple:
                plain = pkg[: -len("-bin")] if pkg.endswith("-bin") else pkg
            if plain is not None and plain:
                flags = {"version_in_asset": False, "ver_after_asset": False,
                         "ver_in_url": False}
                asset = plain
        if flags is None or not asset:
            continue
        votes.append((asset, ext, triple, flags, full))
    if not votes:
        sample = ", ".join(cands[:6])
        fail(
            "Linux assets do not match any known pattern "
            "(<name>-<version>-<triple>, <name>_<version>_<triple>, "
            "<name>-<triple>-v<version>, <name>-<triple>). "
            f"Saw: {sample}. "
            "If the upstream names its files differently, paste the exact "
            "Linux file names into the issue."
        )
    # Majority vote on (asset, ext, flags); triples union for archs.
    groups = {}
    for asset, ext, triple, flags, _full in votes:
        key = (asset, ext, flags["version_in_asset"],
               flags["ver_after_asset"], flags["ver_in_url"])
        groups.setdefault(key, set()).add(triple)
    key = sorted(groups, key=lambda k: (-len(groups[k]), k[0]))[0]
    asset, ext, vin_asset, vafter, vurl = key
    triples = sorted(groups[key])
    arch_lines = []
    seen_arch = set()
    for triple in triples:
        arch = TRIPLE_TO_ARCH.get(triple)
        if not arch or arch in seen_arch:
            continue
        seen_arch.add(arch)
        arch_lines.append(f"{arch} {triple}")
    if not arch_lines:
        fail(f"matched triples {triples} map to no known Arch names")
    return {
        "asset": asset,
        "ext": ext,
        "ver_in_url": vurl,
        "ver_in_path": None,  # filled by caller from tag
        "version_in_asset": vin_asset,
        "ver_after_asset": vafter,
        "archs": "\n".join(arch_lines),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True)
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--assets-json", default="")
    ap.add_argument("--allow-prerelease", default="false")
    args = ap.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", args.upstream):
        fail(f"invalid upstream {args.upstream!r} (expected owner/repo)")
    if args.allow_prerelease not in ("true", "True", "TRUE", "false", "False", "FALSE"):
        fail(f"invalid --allow-prerelease {args.allow_prerelease!r} (expected true/false)")
    allow_pre = args.allow_prerelease in ("true", "True", "TRUE")
    tag = args.tag
    if args.assets_json:
        names = load_assets_json(args.assets_json)
        if not tag:
            fail("--assets-json requires --tag (no live release to read it from)")
    else:
        if not tag:
            tag = latest_tag(args.upstream, allow_pre)
        names = asset_names_for(args.upstream, tag)
    ver_in_path = tag.startswith("v")
    version = tag[1:] if ver_in_path else tag
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]*", version or ""):
        fail(f"release tag {tag!r} yields an unsafe version {version!r}")
    inferred = infer(names, version, args.pkg)
    inferred["ver_in_path"] = ver_in_path
    out = {
        "upstream": args.upstream,
        "tag": tag,
        "version": version,
        "asset": inferred["asset"],
        "ext": inferred["ext"],
        "ver_in_url": inferred["ver_in_url"],
        "ver_in_path": inferred["ver_in_path"],
        "version_in_asset": inferred["version_in_asset"],
        "ver_after_asset": inferred["ver_after_asset"],
        "allow_prerelease": allow_pre,
        "archs": inferred["archs"],
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
