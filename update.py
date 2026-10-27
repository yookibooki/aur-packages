#!/usr/bin/env python3

import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(ROOT, "packages.json")
AUR = "ssh://aur@aur.archlinux.org/{pkg}.git"


class Failed(Exception):
    pass


def fail(msg):
    raise Failed(msg)


def run(cmd, **kw):
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def api(url):
    headers = {"User-Agent": "aur-packages", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
            last = e
            if attempt < 2:
                time.sleep(2 ** attempt)
    fail(f"could not read {url}: {last}")


def newest_release(repo, allow_prerelease):
    for rel in api(f"https://api.github.com/repos/{repo}/releases?per_page=100"):
        if rel.get("draft"):
            continue
        if rel.get("prerelease") and not allow_prerelease:
            continue
        tag = (rel.get("tag_name") or "").strip()
        if tag:
            return tag[1:] if tag.startswith("v") else tag
    fail(f"{repo}: no eligible release found")


def download(url):
    print(f"  downloading {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "aur-packages"})
    for attempt in range(3):
        try:
            digest, size = hashlib.sha256(), 0
            with urllib.request.urlopen(req, timeout=600) as r:
                for chunk in iter(lambda: r.read(1 << 20), b""):
                    digest.update(chunk)
                    size += len(chunk)
            if not size:
                fail(f"downloaded file is empty: {url}")
            return digest.hexdigest()
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            if attempt == 2:
                fail(f"download failed: {url}: {e}")
            time.sleep(2 ** attempt)


def read(path):
    with open(path) as f:
        return f.read()


def write(path, text):
    with open(path + ".tmp", "w") as f:
        f.write(text)
    os.replace(path + ".tmp", path)


def current_version(pkgbuild):
    m = re.search(r'^_realver="([^"]+)"', pkgbuild, re.M)
    if not m:
        fail("PKGBUILD has no _realver line")
    return m.group(1)


def rewrite(pkgbuild, entry, ver, sums):
    pkg = entry["pkg"]
    if not re.search(r"^pkgver=", pkgbuild, re.M) or not re.search(r"^pkgrel=", pkgbuild, re.M):
        fail(f"{pkg}: PKGBUILD needs pkgver= and pkgrel= lines")
    out = re.sub(r"^_realver=.*$", f'_realver="{ver}"', pkgbuild, count=1, flags=re.M)
    out = re.sub(r"^pkgver=.*$", f'pkgver="{ver.replace("-", "_").replace("+", "_")}"', out, count=1, flags=re.M)
    out = re.sub(r"^pkgrel=.*$", "pkgrel=1", out, count=1, flags=re.M)
    for arch, triple in entry["triples"].items():
        url = entry["url"].replace("{ver}", "${_realver}").replace("{triple}", triple)
        out, hits = re.subn(
            rf'^source_{arch}=\(("[^"]*::)https://\S+("\))$',
            lambda m: f"source_{arch}=({m.group(1)}{url}{m.group(2)}",
            out, count=1, flags=re.M)
        if hits != 1:
            fail(f"{pkg}: could not find a single source_{arch}= line")
        out, hits = re.subn(
            rf"^sha256sums_{arch}=\([^)]*\)$",
            f"sha256sums_{arch}=('{sums[arch]}')",
            out, count=1, flags=re.M)
        if hits != 1:
            fail(f"{pkg}: could not find a single sha256sums_{arch}= line")
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


def publish(pkg, pkgdir, ver):
    with tempfile.TemporaryDirectory() as tmp:
        run(["git", "clone", "--depth=1", AUR.format(pkg=pkg), tmp])
        for name in ("PKGBUILD", ".SRCINFO"):
            shutil.copy(os.path.join(pkgdir, name), tmp)
        run(["git", "-C", tmp, "add", "PKGBUILD", ".SRCINFO"])
        if subprocess.run(["git", "-C", tmp, "diff", "--cached", "--quiet"]).returncode == 0:
            print(f"{pkg}: AUR already carries {ver}, nothing to push")
            return
        run(["git", "-C", tmp, "-c", "user.name=aur-publish",
             "-c", "user.email=aur-publish@localhost", "commit", "-m", f"{pkg}: {ver}"])
        run(["git", "-C", tmp, "push"])
        print(f"{pkg}: pushed {ver} to the AUR")


def update_one(entry):
    pkg = entry["pkg"]
    pkgdir = os.path.join(ROOT, "packages", pkg)
    pkgbuild_path = os.path.join(pkgdir, "PKGBUILD")
    srcinfo_path = os.path.join(pkgdir, ".SRCINFO")
    for path in (pkgbuild_path, srcinfo_path):
        if not os.path.isfile(path):
            fail(f"missing {path}")

    before = {path: read(path) for path in (pkgbuild_path, srcinfo_path)}
    try:
        pkgbuild = before[pkgbuild_path]
        have = current_version(pkgbuild)
        ver = newest_release(entry["repo"], entry.get("allow_prerelease", False))
        if ver == have:
            print(f"{pkg}: current ({have})")
            return False

        print(f"{pkg}: {have} -> {ver}")
        sums = {}
        for arch, triple in entry["triples"].items():
            url = entry["url"].replace("{ver}", ver).replace("{triple}", triple)
            if not url.startswith(f'https://github.com/{entry["repo"]}/releases/download/'):
                fail(f"refusing to download from {url}")
            sums[arch] = download(url)
            print(f"  {arch}: {sums[arch]}")

        updated = rewrite(pkgbuild, entry, ver, sums)
        write(srcinfo_path, srcinfo(updated))
        write(pkgbuild_path, updated)
        publish(pkg, pkgdir, ver)
        return True
    except BaseException:
        for path, text in before.items():
            write(path, text)
        raise


def main():
    bumped, failed = [], []
    for entry in json.load(open(CONFIG)):
        try:
            if update_one(entry):
                bumped.append(entry["pkg"])
        except Exception as e:
            print(f"ERROR: {entry['pkg']}: {type(e).__name__}: {e}", file=sys.stderr)
            failed.append(entry["pkg"])

    print(f"updated: {', '.join(bumped)}" if bumped else "nothing to update")
    if failed:
        print(f"left alone: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()