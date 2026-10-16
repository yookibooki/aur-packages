#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

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


def api(url):
    headers = {"User-Agent": "aur-packages", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in (1, 2, 3):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=60
            ) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            fail(f"GitHub API {url} -> HTTP {e.code} {e.reason}")
        except Exception as e:
            err = e
    fail(f"GitHub API {url} failed: {err}")


def _chunks(token):
    out = []
    for run in re.findall(r"\d+|\D+", token):
        out.append((0, int(run)) if run.isdigit() else (1, run))
    return out


def version_key(tag):
    s = tag[1:] if tag.startswith("v") else tag
    return [c for part in re.split(r"[._+\-]+", s) for c in _chunks(part)]


def is_newer(candidate, base):
    ka, kb = version_key(candidate), version_key(base)
    for x, y in zip(ka, kb):
        if x != y:
            return x > y
    if len(ka) == len(kb):
        return False
    ka_longer = len(ka) > len(kb)
    extra = ka[len(kb):] if ka_longer else kb[len(ka):]
    if extra[0][0] == 1:
        return not ka_longer
    if not ka_longer:
        return False
    return any(t[0] == 0 and t[1] > 0 for t in extra)


def latest_release(upstream, allow_prerelease):
    if not allow_prerelease:
        rel = api(f"https://api.github.com/repos/{upstream}/releases/latest")
        if not rel.get("tag_name"):
            fail(f"could not determine latest release for {upstream}")
        return rel
    releases = api(f"https://api.github.com/repos/{upstream}/releases?per_page=30")
    cands = [
        r for r in releases
        if not r.get("draft") and r.get("tag_name")
    ]
    if not cands:
        fail(f"could not determine latest release for {upstream}")
    return max(cands, key=lambda r: version_key(r["tag_name"]))


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
            f"({len(names)} assets total). This tool packages Linux "
            "x86_64/aarch64 binaries; report the exact asset file names."
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
            if m_underscore.group("ver") == version:
                flags = {"version_in_asset": True, "ver_after_asset": False,
                         "ver_in_url": False}
                asset = m_underscore.group("asset")
        if flags is None and m_dash and m_dash.group("triple") == triple:
            if m_dash.group("ver") == version:
                flags = {"version_in_asset": False, "ver_after_asset": True,
                         "ver_in_url": False}
                asset = m_dash.group("asset")
        if flags is None and m_vurl and m_vurl.group("triple") == triple:
            if m_vurl.group("ver") == version:
                flags = {"version_in_asset": False, "ver_after_asset": False,
                         "ver_in_url": True}
                asset = m_vurl.group("asset")
        if flags is None:
            plain = None
            if stem.endswith("-" + triple) or stem.endswith("_" + triple):
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
            f"Saw: {sample}."
        )
    groups = {}
    for asset, ext, triple, flags, _full in votes:
        key = (asset, ext, flags["version_in_asset"],
               flags["ver_after_asset"], flags["ver_in_url"])
        groups.setdefault(key, set()).add(triple)
    key = sorted(groups, key=lambda k: (-len(groups[k]), k[0]))[0]
    asset, ext, vin_asset, vafter, vurl = key
    arch_lines = []
    seen_arch = set()
    for triple in sorted(groups[key]):
        arch = TRIPLE_TO_ARCH.get(triple)
        if not arch or arch in seen_arch:
            continue
        seen_arch.add(arch)
        arch_lines.append(f"{arch} {triple}")
    if not arch_lines:
        fail(f"matched triples {sorted(groups[key])} map to no known Arch names")
    return {
        "asset": asset,
        "ext": ext,
        "ver_in_url": vurl,
        "ver_in_path": None,
        "version_in_asset": vin_asset,
        "ver_after_asset": vafter,
        "archs": "\n".join(arch_lines),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True)
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--allow-prerelease", default="false")
    ap.add_argument("--latest-tag-only", action="store_true")
    ap.add_argument("--newer-than", default="", metavar="VERSION",
                    help="with --latest-tag-only: exit 4 (still printing the tag) "
                         "when the latest version is not strictly newer than VERSION")
    args = ap.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", args.upstream):
        fail(f"invalid upstream {args.upstream!r} (expected owner/repo)")
    if args.allow_prerelease not in ("true", "True", "TRUE", "false", "False", "FALSE"):
        fail(f"invalid --allow-prerelease {args.allow_prerelease!r} (expected true/false)")
    allow_pre = args.allow_prerelease in ("true", "True", "TRUE")

    release = latest_release(args.upstream, allow_pre)
    tag = release["tag_name"]

    if args.latest_tag_only:
        print(tag)
        if args.newer_than:
            version = tag[1:] if tag.startswith("v") else tag
            if not is_newer(version, args.newer_than):
                sys.exit(4)
        return

    names = [a.get("name", "") for a in release.get("assets", []) if a.get("name")]
    ver_in_path = tag.startswith("v")
    version = tag[1:] if ver_in_path else tag
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]*", version or ""):
        fail(f"release tag {tag!r} yields an unsafe version {version!r}")
    inferred = infer(names, version, args.pkg)
    inferred["ver_in_path"] = ver_in_path
    print(json.dumps({
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
    }, indent=2))


if __name__ == "__main__":
    main()
