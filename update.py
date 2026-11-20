#!/usr/bin/env python3

import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PACKAGES = os.path.join(ROOT, "packages")
AUR = "ssh://aur@aur.archlinux.org/{pkg}.git"
RELEASE_URL = re.compile(r"^https://github\.com/[^/]+/[^/]+/releases/download/")


def fail(msg):
    raise RuntimeError(msg)


def run(cmd, **kw):
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def fetch(url, headers):
    last = None
    for attempt in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=600)
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            last = e
            if attempt < 2:
                time.sleep(2 ** attempt)
    fail(f"could not fetch {url}: {last}")


def api(url):
    headers = {"User-Agent": "aur-packages", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with fetch(url, headers) as r:
        return json.load(r)


def newest_release(repo, allow_prerelease):
    for page in range(1, 11):
        rels = api(f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}")
        if not rels:
            break
        for rel in rels:
            if rel.get("draft"):
                continue
            if rel.get("prerelease") and not allow_prerelease:
                continue
            tag = (rel.get("tag_name") or "").strip()
            ver = tag[1:] if tag.startswith("v") else tag
            if re.fullmatch(r"[A-Za-z0-9._+-]+", ver):
                return ver
            print(f"  skipping unusable tag: {tag!r}")
        if len(rels) < 100:
            break
    fail(f"{repo}: no eligible release found")


def download(url):
    print(f"  downloading {url}", flush=True)
    with fetch(url, {"User-Agent": "aur-packages"}) as r:
        digest, size = hashlib.sha256(), 0
        for chunk in iter(lambda: r.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    if not size:
        fail(f"downloaded file is empty: {url}")
    return digest.hexdigest()


def var(text, name):
    m = re.search(rf"^{name}=[\"']?([^\"'\n]+?)[\"']?\s*$", text, re.M)
    if not m:
        fail(f"PKGBUILD has no {name}= line")
    return m.group(1)


def parse_pkgbuild(text):
    url = var(text, "url")
    if not url.startswith("https://github.com/"):
        fail(f"url= is not a github.com repo: {url}")
    repo = url.removeprefix("https://github.com/").rstrip("/")
    repo = repo.removesuffix(".git")
    m = re.search(r"^arch=\(([^)]*)\)", text, re.M)
    if not m:
        fail("PKGBUILD has no arch= line")
    arches = re.findall(r"'([^']+)'", m.group(1))
    if not arches:
        fail("PKGBUILD arch= line has no quoted entries")
    sources = {}
    for arch in arches:
        m = re.search(rf"^source_{arch}=\((.*)\)\s*$", text, re.M)
        if not m:
            fail(f"PKGBUILD has no source_{arch}= line")
        entries = re.findall(r'"([^"]*)"', m.group(1))
        if len(entries) != 1:
            fail(f"expected exactly one source_{arch}= entry, found {len(entries)}")
        sources[arch] = entries[0].rsplit("::", 1)[-1]
    return {
        "realver": var(text, "_realver"),
        "repo": repo,
        "allow_prerelease": bool(re.search(r"^_allow_prerelease=1\s*$", text, re.M)),
        "sources": sources,
    }


def rewrite(text, ver, sums):
    out, n = re.subn(r"^_realver=.*$", f'_realver="{ver}"', text, count=1, flags=re.M)
    if n != 1:
        fail("could not find a single _realver= line")
    out, n = re.subn(r"^pkgrel=.*$", "pkgrel=1", out, count=1, flags=re.M)
    if n != 1:
        fail("could not find a single pkgrel= line")
    for arch, total in sums.items():
        out, n = re.subn(rf"^sha256sums_{arch}=\([^)]*\)$", f"sha256sums_{arch}=('{total}')",
                         out, count=1, flags=re.M)
        if n != 1:
            fail(f"could not find a single sha256sums_{arch}= line")
    return out


def srcinfo(pkgbuild):
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "PKGBUILD"), "w") as f:
            f.write(pkgbuild)
        out = subprocess.run(["makepkg", "--printsrcinfo"], cwd=tmp,
                             stdout=subprocess.PIPE, text=True, check=True).stdout
    if not out.strip():
        fail("makepkg --printsrcinfo produced nothing")
    return out


def publish(pkg, pkgbuild, info, ver):
    with tempfile.TemporaryDirectory() as tmp:
        run(["git", "clone", "--depth=1", AUR.format(pkg=pkg), tmp])
        with open(os.path.join(tmp, "PKGBUILD"), "w") as f:
            f.write(pkgbuild)
        with open(os.path.join(tmp, ".SRCINFO"), "w") as f:
            f.write(info)
        run(["git", "-C", tmp, "add", "PKGBUILD", ".SRCINFO"])
        if subprocess.run(["git", "-C", tmp, "diff", "--cached", "--quiet"]).returncode == 0:
            print(f"{pkg}: AUR already carries {ver}, nothing to push")
            return
        run(["git", "-C", tmp, "-c", "user.name=aur-publish",
             "-c", "user.email=aur-publish@localhost", "commit", "-m", f"{pkg}: {ver}"])
        run(["git", "-C", tmp, "push"])
        print(f"{pkg}: pushed {ver} to the AUR")


def update_one(pkgdir):
    pkg = os.path.basename(pkgdir)
    pkgbuild_path = os.path.join(pkgdir, "PKGBUILD")
    if not os.path.isfile(pkgbuild_path):
        return False
    text = open(pkgbuild_path).read()
    meta = parse_pkgbuild(text)
    if var(text, "pkgname") != pkg:
        fail(f"pkgname= does not match directory name {pkg}")
    have = meta["realver"]
    ver = newest_release(meta["repo"], meta["allow_prerelease"])
    if ver == have:
        print(f"{pkg}: current ({have})")
        return False

    print(f"{pkg}: {have} -> {ver}")
    sums = {}
    for arch, template in meta["sources"].items():
        url = template.replace("${_realver}", ver)
        if not RELEASE_URL.match(url):
            fail(f"refusing to download from {url}")
        sums[arch] = download(url)
        print(f"  {arch}: {sums[arch]}")

    updated = rewrite(text, ver, sums)
    publish(pkg, updated, srcinfo(updated), ver)
    with open(pkgbuild_path, "w") as f:
        f.write(updated)
    return True


def main():
    bumped, failed = [], []
    for pkg in sorted(os.listdir(PACKAGES)):
        try:
            if update_one(os.path.join(PACKAGES, pkg)):
                bumped.append(pkg)
        except Exception as e:
            print(f"ERROR: {pkg}: {type(e).__name__}: {e}", file=sys.stderr)
            failed.append(pkg)

    print(f"updated: {', '.join(bumped)}" if bumped else "nothing to update")
    if failed:
        print(f"left alone: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
