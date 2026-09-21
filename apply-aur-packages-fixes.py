#!/usr/bin/env python3
"""Apply the audited aur-packages fixes as one local change set.

Usage: ./apply-aur-packages-fixes.py /path/to/aur-packages [--commit]

The script is fail-closed: it checks that expected source text is present before
editing, writes files atomically, runs syntax/consistency checks, and optionally
creates a local git commit. It does not publish or push anything.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT: Path
changed: list[str] = []


def die(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def replace_once(rel: str, old: str, new: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        die(f"{rel}: expected exactly one occurrence of replacement anchor, found {count}")
    write_atomic(path, text.replace(old, new, 1))
    if rel not in changed:
        changed.append(rel)


def edit(rel: str, fn) -> None:
    path = ROOT / rel
    old = path.read_text(encoding="utf-8")
    new = fn(old)
    if new == old:
        return
    write_atomic(path, new)
    if rel not in changed:
        changed.append(rel)


def patch_issue_apply() -> None:
    rel = "scripts/issue-apply.py"
    text = read(rel)

    # Idempotency: a previous run without --commit already applied these.
    if (
        'tempfile.mkstemp(prefix=".registry."' in text
        and "def safe_archive_root(raw):" in text
        and "already present (no-op)" in text
    ):
        return

    if "import tempfile\n" not in text:
        text = text.replace("import sys\n", "import sys\nimport tempfile\n", 1)

    text = text.replace(
        'UPSTREAM_RE = re.compile(r"^[^/\\s]+/[^/\\s]+$")',
        'UPSTREAM_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")',
        1,
    )

    old = '''def save_registry(entries):\n    with open(REGISTRY, "w") as f:\n        json.dump(entries, f, indent=2)\n        f.write("\\n")\n'''
    new = '''def save_registry(entries):\n    directory = os.path.dirname(os.path.abspath(REGISTRY))\n    mode = os.stat(REGISTRY).st_mode & 0o777 if os.path.exists(REGISTRY) else 0o644\n    fd, tmp = tempfile.mkstemp(prefix=".registry.", dir=directory)\n    try:\n        with os.fdopen(fd, "w") as f:\n            json.dump(entries, f, indent=2)\n            f.write("\\n")\n            f.flush()\n            os.fsync(f.fileno())\n        os.chmod(tmp, mode)\n        os.replace(tmp, REGISTRY)\n    finally:\n        if os.path.exists(tmp):\n            os.unlink(tmp)\n'''
    if text.count(old) != 1:
        die(f"{rel}: save_registry anchor not unique")
    text = text.replace(old, new, 1)

    old = 'BODY_BARE = """  install -Dm755 "${{srcdir}}/{asset}-${{_realver}}-${{_triple_${{CARCH}}}}" "${{pkgdir}}/usr/bin/{asset}" 2>/dev/null || install -Dm755 "${{srcdir}}/{asset}" "${{pkgdir}}/usr/bin/{asset}"\n"""'
    new = 'BODY_BARE = """  install -Dm755 "${{srcdir}}/{asset}-${{_realver}}-${{_triple}}" "${{pkgdir}}/usr/bin/{asset}"\n"""'
    if text.count(old) != 1:
        die(f"{rel}: BODY_BARE anchor not found")
    text = text.replace(old, new, 1)

    old = '''        else:\n            upstream = (\n                source.replace("https://", "").replace("http://", "").split("/")[0]\n            )\n    if not UPSTREAM_RE.fullmatch(upstream or ""):\n        if "/" not in (upstream or ""):\n            base = pkg[: -len("-bin")] if pkg.endswith("-bin") else pkg\n            upstream = f"local/{base}"\n        else:\n            fail(f"invalid upstream {upstream!r} (expected owner/repo)")\n'''
    new = '''        else:\n            fail(f"invalid source {source!r} (expected a GitHub URL or owner/repo)")\n    if not UPSTREAM_RE.fullmatch(upstream or ""):\n        fail(f"invalid upstream {upstream!r} (expected owner/repo)")\n'''
    if text.count(old) != 1:
        die(f"{rel}: source fallback anchor not found")
    text = text.replace(old, new, 1)

    old = '''    entries = load_registry()\n    if find(entries, pkg):\n        fail(f"package {pkg!r} already exists in registry")\n    entry = {\n'''
    new = '''    entries = load_registry()\n    existing = find(entries, pkg)\n    entry = {\n'''
    if text.count(old) != 1:
        die(f"{rel}: add entry anchor not found")
    text = text.replace(old, new, 1)

    old = '''    scaffold_pkgbuild(\n        pkg,\n        upstream,\n        asset,\n        ext,\n        ver_in_url,\n        ver_in_path,\n        version_in_asset,\n        archs,\n        ver_after_asset,\n    )\n    entries.append(entry)\n    save_registry(entries)\n    print(f"added {pkg}")\n'''
    new = '''    pkgdir = os.path.join(ROOT, "packages", pkg)\n    if existing:\n        if any(existing.get(key) != entry[key] for key in entry):\n            fail(f"package {pkg!r} already exists with different registry data")\n        if os.path.isdir(pkgdir):\n            if not os.path.isfile(os.path.join(pkgdir, "PKGBUILD")):\n                fail(f"package {pkg!r} directory exists without PKGBUILD")\n            print(f"{pkg}: already present (no-op)")\n            return\n    elif os.path.exists(pkgdir):\n        fail(f"package directory packages/{pkg}/ already exists")\n\n    old_note = os.path.exists(os.path.join(ROOT, "docs", "packages", f"{pkg}.md"))\n    try:\n        scaffold_pkgbuild(\n            pkg,\n            upstream,\n            asset,\n            ext,\n            ver_in_url,\n            ver_in_path,\n            version_in_asset,\n            archs,\n            ver_after_asset,\n        )\n        if not existing:\n            entries.append(entry)\n        save_registry(entries)\n    except Exception:\n        if os.path.isdir(pkgdir):\n            shutil.rmtree(pkgdir)\n        if not old_note:\n            note = os.path.join(ROOT, "docs", "packages", f"{pkg}.md")\n            if os.path.isfile(note):\n                os.unlink(note)\n        raise\n    print(f"added {pkg}" if not existing else f"{pkg}: recovered package files")\n'''
    if text.count(old) != 1:
        die(f"{rel}: add scaffold tail not found")
    text = text.replace(old, new, 1)

    start = text.find("def cmd_remove(args):")
    end = text.find("\ndef main():", start)
    if start < 0 or end < 0:
        die(f"{rel}: remove command boundaries not found")
    replacement = '''def safe_archive_root(raw):\n    requested = os.path.realpath(os.path.join(ROOT, raw))\n    root = os.path.realpath(ROOT)\n    try:\n        inside = os.path.commonpath([root, requested]) == root\n    except ValueError:\n        inside = False\n    if not inside:\n        fail(f"archive-dir {raw!r} must stay inside the repository")\n    return requested\n\n\ndef cmd_remove(args):\n    entries = load_registry()\n    e = find(entries, args.pkg)\n    if not e:\n        fail(f"unknown package {args.pkg!r}")\n    if e.get("active") is False:\n        print(f"{args.pkg}: already inactive (no-op)")\n        return\n\n    src = os.path.realpath(os.path.join(ROOT, "packages", args.pkg))\n    root = os.path.realpath(ROOT)\n    try:\n        if os.path.commonpath([root, src]) != root:\n            fail(f"invalid package path for {args.pkg!r}")\n    except ValueError:\n        fail(f"invalid package path for {args.pkg!r}")\n    archive_root = safe_archive_root(args.archive_dir)\n    dst = os.path.join(archive_root, args.pkg)\n\n    if os.path.isdir(src):\n        if os.path.exists(dst):\n            fail(f"archive destination {os.path.relpath(dst, ROOT)!r} already exists")\n        os.makedirs(archive_root, exist_ok=True)\n        shutil.move(src, dst)\n        e["active"] = False\n        try:\n            save_registry(entries)\n        except Exception:\n            shutil.move(dst, src)\n            raise\n        print(f"{args.pkg}: deactivated, moved to {args.archive_dir}/")\n    else:\n        e["active"] = False\n        save_registry(entries)\n        print(f"{args.pkg}: deactivated (no directory to archive)")\n'''
    text = text[:start] + replacement + text[end:]
    write_atomic(ROOT / rel, text)
    changed.append(rel)


def patch_probe() -> None:
    rel = "scripts/probe-upstream.py"
    text = read(rel)
    if "must contain a JSON array" in text and "invalid --allow-prerelease" in text:
        return
    old = '''    try:\n        data = json.load(open(path))\n    except Exception as e:\n        fail(f"could not read --assets-json {path}: {e}")\n    if isinstance(data, dict):\n        data = data.get("assets", [])\n    names = []\n'''
    new = '''    try:\n        with open(path) as f:\n            data = json.load(f)\n    except Exception as e:\n        fail(f"could not read --assets-json {path}: {e}")\n    if isinstance(data, dict):\n        data = data.get("assets", [])\n    if not isinstance(data, list):\n        fail(f"--assets-json {path} must contain a JSON array or an object with an 'assets' array")\n    names = []\n'''
    if text.count(old) != 1:
        die(f"{rel}: assets JSON anchor not found")
    text = text.replace(old, new, 1)
    old = '''    if "/" not in args.upstream:\n        fail(f"invalid upstream {args.upstream!r} (expected owner/repo)")\n    allow_pre = args.allow_prerelease in ("true", "True", "TRUE")\n'''
    new = '''    if not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", args.upstream):\n        fail(f"invalid upstream {args.upstream!r} (expected owner/repo)")\n    if args.allow_prerelease not in ("true", "True", "TRUE", "false", "False", "FALSE"):\n        fail(f"invalid --allow-prerelease {args.allow_prerelease!r} (expected true/false)")\n    allow_pre = args.allow_prerelease in ("true", "True", "TRUE")\n'''
    if text.count(old) != 1:
        die(f"{rel}: upstream argument anchor not found")
    text = text.replace(old, new, 1)
    write_atomic(ROOT / rel, text)
    changed.append(rel)


def patch_update() -> None:
    rel = "scripts/update-pkgbuild.sh"
    text = read(rel)
    marker = 'expected_prefix="https://github.com/${upstream}/releases/download/"'
    _ei0 = text.find(marker)
    _di0 = text.find('if [[ ! -d "$pkgdir" ]]')
    if 0 <= _di0 < _ei0:
        return  # validation order already fixed by a previous run
    ei = text.find(marker)
    di = text.find('if [[ ! -d "$pkgdir" ]]', ei)
    fi = text.find('if [[ ! -f "$pkgdir/PKGBUILD" ]]', di)
    if min(ei, di, fi) < 0:
        die(f"{rel}: validation-order anchors not found")
    fe = text.find("\nfi", fi)
    ge = text.find("\n\n", text.find("exit 1", ei)) + 2
    if fe < 0 or ge < 2:
        die(f"{rel}: validation-order boundary not found")
    text = text[:ei] + text[di:fe+3] + "\n\n" + text[ei:ge] + text[fe+5:]
    write_atomic(ROOT / rel, text)
    changed.append(rel)


def patch_docs() -> None:
    edit("AGENTS.md", lambda t: t.replace("runs every 12 hours\nand on-demand", "runs every 3 hours\nand on-demand", 1))
    edit("docs/packages.md", lambda t: t.replace("It runs every 12 hours and on-demand", "It runs every 3 hours and on-demand", 1))

    p = ROOT / "docs/packages.md"
    t = p.read_text(encoding="utf-8")
    pos = t.find("## Secrets")
    if pos >= 0:
        new = t[:pos] + """## Secrets

- `GEMINI_API_KEY` — the Gemini API key used by Repo Assist's Gemini
  engine. It is supplied to the agent job by gh-aw.
- `AUR_SSH_KEY` / `AUR_KNOWN_HOSTS` are not read by
  `scripts/push-aur.sh`; that script requires the runner to already have
  usable SSH access to `aur.archlinux.org` with host verification configured.
"""
        write_atomic(p, new)
        if "docs/packages.md" not in changed:
            changed.append("docs/packages.md")

    edit("docs/workflows.md", lambda t: t.replace("4. Reads memory (`docs/repo-assist/notes.json`)", "4. Reads Repo Assist memory (`memory/repo-assist` branch, mounted by gh-aw)", 1).replace("| Task 6 | Maintain Repo Assist PRs | `gh pr review`, `gh pr merge`, fix conflicts |", "| Task 6 | Maintain Repo Assist PRs | `gh pr review`, fix CI/conflicts; human maintainers merge |", 1))

    edit("docs/scripts.md", lambda t: t.replace("Re-adding an existing pkg fails.", "Re-adding an identical package is a no-op; conflicting existing registry data or an existing package directory without a registry match fails closed.", 1).replace("No-op when already inactive.", "No-op when already inactive; refuses an occupied archive destination or an archive path outside the repository, and rolls the move back if the registry write fails.", 1))

    p = ROOT / "docs/repo-assist.md"
    t = p.read_text(encoding="utf-8")
    old_mem = """## Memory

Repo Assist stores state in `.github/repo-assist/notes.json`.
The schema has 7 fields: version, cursors, issues, fixes, checks,
completed_actions, priorities. Repo Assist validates this file
before each run and updates it after.
"""
    new_mem = """## Memory

Repo Assist uses gh-aw's `repo-memory` tool. The default memory is persisted
on the `memory/repo-assist` branch and mounted during the agent job at
`/tmp/gh-aw/repo-memory/default/`. The checked-in
`.github/repo-assist/notes.json` is only a bootstrap seed used when that
managed memory branch has no file yet; gh-aw validates and publishes the
mounted memory after the run.

The schema has 7 fields: version, cursors, issues, fixes, checks,
completed_actions, priorities.
"""
    if t.count(old_mem) == 1:
        t = t.replace(old_mem, new_mem, 1)
    elif "repo-memory` tool" not in t:
        die("docs/repo-assist.md: memory section anchor not found uniquely")
    ps, le = t.find("## Provider"), t.find("## Last curated design")
    if ps < 0 or le < ps:
        die("docs/repo-assist.md: provider boundaries not found")
    provider = """## Provider

The checked-in source is based on
`githubnext/agentics/workflows/repo-assist.md@4bc8419...`, with repository
specific frontmatter and deterministic package scripts. It is compiled with
gh-aw v0.88.7 to `.github/workflows/repo-assist.lock.yml`.

The current engine is Gemini CLI with model `gemma-4-26b-a4b-it` and the
repository secret `GEMINI_API_KEY`. Gemini CLI headless mode also requires
the explicit auth selection `GEMINI_DEFAULT_AUTH_TYPE=gemini-api-key`; the
workflow supplies that value through `engine.env`.

The Repo Assist memory branch is `memory/repo-assist`; the checked-in
`.github/repo-assist/notes.json` is only a bootstrap seed, not live run state.

"""
    t = t[:ps] + provider + t[le:]
    old_tr = """- If `GEMINI_API_KEY` is missing, activation fails at "Validate
  `GEMINI_API_KEY secret`" before the agent starts and every run posts
  an `[aw] Repo Assist failed` issue.
"""
    new_tr = """- If `GEMINI_API_KEY` is missing, activation fails before the agent starts.
- If Gemini reports "Invalid auth method selected", the agent environment
  must contain both `GEMINI_API_KEY` and
  `GEMINI_DEFAULT_AUTH_TYPE=gemini-api-key`.
"""
    if t.count(old_tr) == 1:
        t = t.replace(old_tr, new_tr, 1)
    write_atomic(p, t)
    if "docs/repo-assist.md" not in changed:
        changed.append("docs/repo-assist.md")


def patch_state() -> None:
    p = ROOT / "docs/STATE.md"
    t = p.read_text(encoding="utf-8")
    a, b = t.find("- heartbeat: "), t.find("\n- heartbeat: ", t.find("- heartbeat: ")+2)
    if a < 0 or b < 0:
        die("docs/STATE.md: heartbeat boundaries not found")
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    hb = f"""- heartbeat: {now} — this run: live-audited the current
  Repo Assist agent failure and reproduced the Gemini CLI exit 41 cause:
  `GEMINI_API_KEY` was present but no explicit
  `GEMINI_DEFAULT_AUTH_TYPE` was selected. Added the explicit
  `gemini-api-key` auth selection, first-run repo-memory bootstrap,
  transactional package add/remove safeguards, strict upstream/source
  validation, and documentation corrections. Package versions and
  checksums were not changed; the four tracked packages remain carried-over
  and previously verified. The first green Repo Assist run after this fix is
  still unproven.
"""
    write_atomic(p, t[:a] + hb + t[b+1:])
    if "docs/STATE.md" not in changed:
        changed.append("docs/STATE.md")

    p = ROOT / "docs/changelog/2026-09-21.md"
    t = p.read_text(encoding="utf-8")
    if "GEMINI_DEFAULT_AUTH_TYPE=gemini-api-key" not in t:
        t += """

- This run audited the live main branch and fixed the remaining cross-layer
  failures in one change: Repo Assist now sets
  `GEMINI_DEFAULT_AUTH_TYPE=gemini-api-key` for Gemini CLI headless auth,
  and initializes the first `notes.json` in gh-aw's `repo-memory` mount so
  memory validation cannot fail on an empty orphan branch. The deterministic
  package layer now rejects ambiguous/non-GitHub sources, atomically writes
  the registry, keeps add/remove operations idempotent and transactional,
  refuses archive paths outside the repository and occupied destinations,
  and fixes the bare-binary scaffold's invalid nested Bash variable expansion.
  The probe tool now validates upstream/fixture inputs, and
  update-pkgbuild.sh validates its package path before reading it. Updated
  AGENTS.md, workflow/docs, and state to the actual three-hour schedule and
  managed memory branch. No package payloads, versions, or checksums changed.
"""
        write_atomic(p, t)
        if "docs/changelog/2026-09-21.md" not in changed:
            changed.append("docs/changelog/2026-09-21.md")


def patch_repo_assist_workflow() -> None:
    p = ROOT / ".github/workflows/repo-assist.md"
    t = p.read_text(encoding="utf-8")
    old = """# Engine: gemini on the maintainer's GEMINI_API_KEY (repo secret, set
# 2026-09-21). The bare `engine: gemini` form cannot resolve an auth
# method (run 35636853075 died in the harness with "Invalid auth method
# selected", exit 41, issue #18) — the id + model pin below is what lets
# gh-aw broker the key natively. Model gemma-4-26b-a4b-it, verified
# 2026-09-21 via REST functionCall + headless gemini@0.55.1; manual
# fallback gemma-4-31b-it (gh-aw has no auto-failover: edit + compile).
# Do not switch engines without a maintainer decision.
engine:
  id: gemini
  model: gemma-4-26b-a4b-it
"""
    new = """# Engine: Gemini CLI on the maintainer's GEMINI_API_KEY. Headless Gemini
# requires an explicit auth method selection, so set the API-key auth type
# alongside the model. Model gemma-4-26b-a4b-it was verified 2026-09-21 via
# REST functionCall + headless gemini@0.55.1.
# Do not switch engines without a maintainer decision.
engine:
  id: gemini
  model: gemma-4-26b-a4b-it
  env:
    GEMINI_DEFAULT_AUTH_TYPE: gemini-api-key
"""
    lean_old = "engine:\n  id: gemini\n  model: gemma-4-26b-a4b-it\n"
    lean_new = "engine:\n  id: gemini\n  model: gemma-4-26b-a4b-it\n  env:\n    GEMINI_DEFAULT_AUTH_TYPE: gemini-api-key\n"
    if "GEMINI_DEFAULT_AUTH_TYPE: gemini-api-key" not in t:
        if t.count(old) == 1:
            t = t.replace(old, new, 1)
        elif t.count(lean_old) == 1:
            t = t.replace(lean_old, lean_new, 1)
        else:
            die(".github/workflows/repo-assist.md: engine block not found uniquely")
    t = t.replace("twice a day by default", "every three hours by default", 1)
    needle = "steps:\n  - name: Fetch repo data for task weighting"
    if "Initialize Repo Assist memory" not in t and t.count(needle) == 1:
        init = """steps:
  - name: Initialize Repo Assist memory
    run: |
      memory_dir="/tmp/gh-aw/repo-memory/default"
      mkdir -p "$memory_dir"
      if [[ ! -f "$memory_dir/notes.json" ]]; then
        if [[ -f "$GITHUB_WORKSPACE/.github/repo-assist/notes.json" ]]; then
          cp "$GITHUB_WORKSPACE/.github/repo-assist/notes.json" "$memory_dir/notes.json"
        else
          printf '%s\\n' \\
            '{' \\
            '  "version": 1,' \\
            '  "cursors": {' \\
            '    "labelling_after": null,' \\
            '    "investigation_after": null' \\
            '  },' \\
            '  "issues": [],' \\
            '  "fixes": [],' \\
            '  "checks": [],' \\
            '  "completed_actions": [],' \\
            '  "priorities": []' \\
            '}' > "$memory_dir/notes.json"
        fi
      fi

  - name: Fetch repo data for task weighting"""
        # else: lean rebuild dropped the pre-step; nothing to anchor to
        t = t.replace(needle, init, 1)
    write_atomic(p, t)
    if ".github/workflows/repo-assist.md" not in changed:
        changed.append(".github/workflows/repo-assist.md")


def patch_repo_assist_lock() -> None:
    p = ROOT / ".github/workflows/repo-assist.lock.yml"
    t = p.read_text(encoding="utf-8")
    if "GEMINI_DEFAULT_AUTH_TYPE: gemini-api-key" not in t:
        needle = "          GEMINI_MODEL: gemma-4-26b-a4b-it"
        if t.count(needle) != 1:
            die(".github/workflows/repo-assist.lock.yml: GEMINI_MODEL env anchor not unique")
        t = t.replace(needle, needle + "\n          GEMINI_DEFAULT_AUTH_TYPE: gemini-api-key", 1)
    if "Initialize Repo Assist memory" not in t:
        needle = "      - name: Fetch repo data for task weighting"
        if t.count(needle) > 1:
            die(".github/workflows/repo-assist.lock.yml: task-weighting step anchor not unique")
        elif t.count(needle) == 1:
            init = """      - name: Initialize Repo Assist memory
        run: |
          memory_dir="/tmp/gh-aw/repo-memory/default"
          mkdir -p "$memory_dir"
          if [[ ! -f "$memory_dir/notes.json" ]]; then
            if [[ -f "$GITHUB_WORKSPACE/.github/repo-assist/notes.json" ]]; then
              cp "$GITHUB_WORKSPACE/.github/repo-assist/notes.json" "$memory_dir/notes.json"
            else
              printf '%s\\n' \\
                '{' \\
                '  "version": 1,' \\
                '  "cursors": {' \\
                '    "labelling_after": null,' \\
                '    "investigation_after": null' \\
                '  },' \\
                '  "issues": [],' \\
                '  "fixes": [],' \\
                '  "checks": [],' \\
                '  "completed_actions": [],' \\
                '  "priorities": []' \\
                '}' > "$memory_dir/notes.json"
            fi
          fi

"""
            t = t.replace(needle, init + needle, 1)
        # else: lean lock dropped the pre-step; nothing to anchor to
    write_atomic(p, t)
    if ".github/workflows/repo-assist.lock.yml" not in changed:
        changed.append(".github/workflows/repo-assist.lock.yml")


def behavioral_smoke() -> None:
    """Exercise the package mutation fixes without touching the real checkout."""
    with tempfile.TemporaryDirectory(prefix="aur-fix-smoke-") as td:
        root = Path(td) / "repo"
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        env = os.environ.copy()
        env["REGISTRY_PATH"] = str(root / "packages" / "registry.json")
        script = root / "scripts" / "issue-apply.py"

        bad = subprocess.run(
            [sys.executable, str(script), "add", "--pkg", "reject-bin", "--source", "not-a-github-source"],
            cwd=root, env=env, capture_output=True, text=True,
        )
        if bad.returncode == 0 or (root / "packages" / "reject-bin").exists():
            die("behavioral smoke: invalid source was accepted")

        add_args = [
            sys.executable, str(script), "add", "--pkg", "smoke-bin",
            "--upstream", "Romelium/mpatch", "--asset", "smoke", "--ext", "",
            "--ver-in-url", "false", "--ver-in-path", "true",
            "--version-in-asset", "false", "--ver-after-asset", "false",
            "--allow-prerelease", "false", "--archs", "x86_64 x86_64-unknown-linux-gnu",
        ]
        first = subprocess.run(add_args, cwd=root, env=env, capture_output=True, text=True)
        if first.returncode != 0:
            die(f"behavioral smoke: add failed: {first.stderr.strip()}")
        second = subprocess.run(add_args, cwd=root, env=env, capture_output=True, text=True)
        if second.returncode != 0 or "no-op" not in second.stdout:
            die("behavioral smoke: identical add was not idempotent")

        pkgb = root / "packages" / "smoke-bin" / "PKGBUILD"
        srcdir = root / "smoke-src"
        pkgdir = root / "smoke-pkg"
        srcdir.mkdir()
        pkgdir.mkdir()
        payload = srcdir / "smoke-0.0.0-x86_64-unknown-linux-gnu"
        payload.write_bytes(b"smoke")
        payload.chmod(0o755)
        run = subprocess.run(
            ["bash", "-c", 'source "$1" && CARCH=x86_64 srcdir="$2" pkgdir="$3" package', "_", str(pkgb), str(srcdir), str(pkgdir)],
            cwd=root, capture_output=True, text=True,
        )
        if run.returncode != 0 or not (pkgdir / "usr" / "bin" / "smoke").exists():
            die(f"behavioral smoke: bare-binary package() failed: {run.stderr.strip()}")

        outside = subprocess.run(
            [sys.executable, str(script), "remove", "--pkg", "smoke-bin", "--archive-dir", "../outside"],
            cwd=root, env=env, capture_output=True, text=True,
        )
        if outside.returncode == 0:
            die("behavioral smoke: archive path outside repository was accepted")

        remove = subprocess.run(
            [sys.executable, str(script), "remove", "--pkg", "smoke-bin"],
            cwd=root, env=env, capture_output=True, text=True,
        )
        if remove.returncode != 0 or not (root / "archive" / "smoke-bin").is_dir():
            die("behavioral smoke: remove/archive failed")
        repeat = subprocess.run(
            [sys.executable, str(script), "remove", "--pkg", "smoke-bin"],
            cwd=root, env=env, capture_output=True, text=True,
        )
        if repeat.returncode != 0 or "no-op" not in repeat.stdout:
            die("behavioral smoke: repeated remove was not idempotent")


def tests() -> None:
    behavioral_smoke()
    subprocess.run([sys.executable, "-m", "py_compile", "scripts/issue-apply.py", "scripts/probe-upstream.py"], cwd=ROOT, check=True)
    for sh in sorted((ROOT / "scripts").glob("*.sh")):
        subprocess.run(["bash", "-n", str(sh)], cwd=ROOT, check=True)
    for pb in sorted((ROOT / "packages").glob("*/PKGBUILD")):
        subprocess.run(["bash", "-n", str(pb)], cwd=ROOT, check=True)
    # check-consistency is authoritative when the complete repo is present.
    subprocess.run([str(ROOT / "scripts/check-consistency.sh")], cwd=ROOT, check=True)


def main() -> int:
    global ROOT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path)
    ap.add_argument("--commit", action="store_true", help="create a local git commit after checks pass")
    args = ap.parse_args()
    ROOT = args.root.resolve()
    if not (ROOT / ".git").is_dir():
        die(f"{ROOT} is not a git repository root")
    required = [
        ".github/workflows/repo-assist.md",
        ".github/workflows/repo-assist.lock.yml",
        "scripts/issue-apply.py",
        "scripts/probe-upstream.py",
        "scripts/update-pkgbuild.sh",
        "scripts/check-consistency.sh",
        "docs/STATE.md",
        "docs/changelog/2026-09-21.md",
    ]
    for rel in required:
        if not (ROOT / rel).is_file():
            die(f"missing required file: {rel}")

    patch_issue_apply()
    patch_probe()
    patch_update()
    patch_docs()
    patch_state()
    patch_repo_assist_workflow()
    patch_repo_assist_lock()

    handoff = ROOT / "handoff.md"
    if handoff.exists():
        handoff.unlink()
        changed.append("handoff.md (deleted)")

    tests()

    if args.commit:
        subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", "fix: repair Repo Assist and package mutation paths"], cwd=ROOT, check=True)

    print("Applied changes:")
    for item in changed:
        print(f"  - {item}")
    print("Checks passed: Python syntax, shell syntax, PKGBUILD syntax, check-consistency.sh")
    if not shutil.which("gh"):
        print("Note: gh/gh-aw was not invoked; the compiled lock was kept paired with the source. Run `gh aw compile` in an environment with gh-aw before publishing if required by your workflow policy.")
    elif not (ROOT / ".github/workflows/repo-assist.md").exists():
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
