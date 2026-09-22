#!/usr/bin/env bash
# discover.sh — deterministic update discovery. Zero AI tokens.
#
# Probes every active registry entry for a newer upstream release. On drift
# runs the full bump transaction per package:
#   update-pkgbuild.sh (real checksums from real artifacts)
#   -> makepkg --printsrcinfo -> verify-package.sh -> check-consistency.sh
#   -> branch discover/<pkg> + commit + PR (one PR per package).
#
# "No drift" is success. Any package error fails the run (red run = work
# order). Pushing only happens under GitHub Actions (GITHUB_ACTIONS=true);
# local runs probe + run the transaction up to verification, then revert.
#
# Keep-alive: GitHub disables scheduled workflows after 60 days without a
# commit. Normal activity resets that clock; when the repo has been silent
# for >= 10 days this run appends docs/heartbeat.log and pushes it.
set -euo pipefail
cd "$(dirname "$0")/.."

summary_lines=()
failures=0

note() { printf '%s\n' "$*"; summary_lines+=("$*"); }

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    summary_lines+=("FAIL: $*")
    failures=$((failures + 1))
}

git_commit() {
    git -c user.name="discover-bot" \
        -c user.email="discover-bot@users.noreply.github.com" commit "$@"
}

# Emit registry rows (active only) as TSV:
# pkg upstream allow_prerelease asset ext ver_in_url ver_in_path
# version_in_asset ver_after_asset archs(';' joined)
registry_rows() {
    python3 - <<'EOF'
import json
for e in json.load(open("packages/registry.json")):
    if e.get("active") not in (True, "true"):
        continue
    b = lambda k, d=False: str(e.get(k, d)).lower()
    archs = ";".join(
        l.strip() for l in (e.get("archs") or "").splitlines() if l.strip()
    )
    print("\t".join([
        e["pkg"], e["upstream"], b("allow_prerelease"),
        e["asset"], e.get("ext", ""),
        b("ver_in_url"), b("ver_in_path", True),
        b("version_in_asset"), b("ver_after_asset"),
        archs,
    ]))
EOF
}

packaged_version() {
    bash -c "set -u; source '$1/PKGBUILD'; printf %s \"\${_realver:-\$pkgver}\"" 2>/dev/null
}

has_open_pr() {
    local n
    n="$(gh pr list --state open --search "bump $1 in:title" \
        --json number --jq 'length' 2>/dev/null || echo 0)"
    [[ "$n" =~ ^[0-9]+$ ]] && ((n > 0))
}

git_publish_branch() {
    local pkg="$1" version="$2" old="$3" tag="$4"
    local branch="discover/${pkg}"
    git checkout -B "$branch" >/dev/null 2>&1
    git add "packages/$pkg" "docs/packages/$pkg.md"
    if git diff --cached --quiet; then
        note "  $pkg: transaction left no diff; no PR"
        git checkout - >/dev/null 2>&1 || true
        git branch -D "$branch" >/dev/null 2>&1 || true
        return 0
    fi
    git_commit -m "bump ${pkg}: ${old} -> ${version}" >/dev/null
    if ! git push -f -u origin "$branch" >/dev/null 2>&1; then
        fail "$pkg: push of $branch failed"
        git checkout - >/dev/null 2>&1 || true
        git branch -D "$branch" >/dev/null 2>&1 || true
        return 0
    fi
    local body
    body="Automated update discovery (\`scripts/discover.sh\`, zero-token cron).

- package: \`$pkg\` ($old -> $version, tag \`$tag\`)
- checksums: real sha256 from real release artifacts (\`update-pkgbuild.sh\`)
- gates in this run: \`verify-package.sh\` + \`check-consistency.sh\` green

Test Status: ran in the discover run that opened this PR; \`lint.yml\`
re-runs them against this branch before merge."
    local create_out
    if create_out="$(gh pr create --base main --head "$branch" \
        --title "bump ${pkg}: ${old} -> ${version}" --body "$body" 2>&1)"; then
        note "  PR opened: $branch"
    else
        # Keep gh's real reason (was swallowed by >/dev/null — the very
        # first CI drift run failed PR creation with no evidence).
        note "  PR create failed for $pkg: ${create_out:0:300}"
    fi
    git checkout - >/dev/null 2>&1 || true
    git branch -D "$branch" >/dev/null 2>&1 || true
    return 0
}

bump_pkg() {
    local pkg="$1" upstream="$2" version="$3" old="$4" tag="$5"
    local asset="$6" ext="$7" ver_in_url="$8" ver_in_path="$9"
    local version_in_asset="${10}" ver_after_asset="${11}" archs="${12}"
    local pkgdir="packages/$pkg"

    note "- $pkg: drift $old -> $version (tag $tag), running bump transaction"

    if ! printf '%s\n' "$archs" | tr ';' '\n' \
        | scripts/update-pkgbuild.sh "$pkgdir" "$version" "$asset" "$ext" \
            "$ver_in_url" "$upstream" "$ver_in_path" "$version_in_asset" \
            "$ver_after_asset" >/dev/null; then
        fail "$pkg: update-pkgbuild.sh failed"
        git checkout -- "$pkgdir" 2>/dev/null || true
        return 0
    fi

    # Regenerate .SRCINFO. makepkg refuses root; discover.yml runs us as an
    # unprivileged user. Locally, if makepkg is missing we skip this and
    # lint.yml's arch container stays the authoritative gate (same policy
    # as verify-package.sh) — but then consistency would fail on stale
    # .SRCINFO, so skip consistency there too.
    local skip_consistency=0
    if command -v makepkg >/dev/null 2>&1 && [[ ${EUID:-$(id -u)} -ne 0 ]]; then
        if ! (cd "$pkgdir" && makepkg --printsrcinfo > .SRCINFO.tmp \
            && mv .SRCINFO.tmp .SRCINFO); then
            fail "$pkg: makepkg --printsrcinfo failed"
            git checkout -- "$pkgdir" 2>/dev/null || true
            return 0
        fi
    else
        skip_consistency=1
        note "  (makepkg unavailable or root: .SRCINFO + consistency deferred to lint gate)"
    fi

    if ! scripts/verify-package.sh "$pkgdir/"; then
        fail "$pkg: verify-package.sh failed"
        git checkout -- "$pkgdir" 2>/dev/null || true
        return 0
    fi
    if ((skip_consistency == 0)) && ! scripts/check-consistency.sh >/dev/null; then
        fail "$pkg: check-consistency.sh failed"
        git checkout -- "$pkgdir" 2>/dev/null || true
        return 0
    fi

    # Per-package note trail (one appended line).
    printf -- '- %s: bumped %s -> %s by scripts/discover.sh\n' \
        "$(date -u +%F)" "$old" "$version" >> "docs/packages/$pkg.md"

    if [[ "${GITHUB_ACTIONS:-}" != "true" ]]; then
        note "  (local run: commit/PR skipped, tree reverted)"
        git checkout -- "$pkgdir" "docs/packages/$pkg.md" 2>/dev/null || true
        return 0
    fi

    git_publish_branch "$pkg" "$version" "$old" "$tag"
}

keepalive() {
    # Best-effort: never fail the run for the heartbeat. docs/ is root-owned
    # in CI (discover.sh runs as builder), so builder only drops a marker;
    # the workflow's root step performs the actual append/commit/push.
    [[ "${GITHUB_ACTIONS:-}" == "true" ]] || return 0
    local last now
    if ! last="$(git log -1 --format=%ct 2>&1)" || [[ ! "$last" =~ ^[0-9]+$ ]]; then
        note "- keepalive: git log failed for this user: ${last:0:160}; skipped"
        return 0
    fi
    now="$(date +%s)"
    ((now - last > 10 * 86400)) || return 0
    : >/tmp/discover-keepalive-needed
    note "- keepalive: repo silent >10d; heartbeat queued for root step"
}

main() {
    local pkg upstream allow_pre asset ext ver_in_url ver_in_path
    local version_in_asset ver_after_asset archs packaged tag version rc
    local total=0 drifted=0

    while IFS=$'\t' read -r pkg upstream allow_pre asset ext ver_in_url \
        ver_in_path version_in_asset ver_after_asset archs; do
        [[ -n "$pkg" ]] || continue
        total=$((total + 1))
        if ! packaged="$(packaged_version "packages/$pkg")" || [[ -z "$packaged" ]]; then
            fail "$pkg: cannot read packaged version"
            continue
        fi
        rc=0
        tag="$(python3 scripts/probe-upstream.py --upstream "$upstream" \
            --pkg "$pkg" --allow-prerelease "$allow_pre" \
            --latest-tag-only --newer-than "$packaged")" || rc=$?
        case "$rc" in
            0) ;;
            4)
                note "- $pkg: current ($packaged, upstream $tag)"
                continue
                ;;
            *)
                fail "$pkg: probe of $upstream failed"
                continue
                ;;
        esac
        drifted=$((drifted + 1))
        version="$tag"
        [[ "$ver_in_path" == "true" && "$tag" == v* ]] && version="${tag#v}"
        if has_open_pr "$pkg"; then
            note "- $pkg: drift $packaged -> $version but an open bump PR exists; skipping"
            continue
        fi
        bump_pkg "$pkg" "$upstream" "$version" "$packaged" "$tag" \
            "$asset" "$ext" "$ver_in_url" "$ver_in_path" \
            "$version_in_asset" "$ver_after_asset" "$archs"
    done < <(registry_rows)

    note ""
    note "Probed $total active package(s), $drifted with drift, $failures failure(s)."
    # Write the summary to a file; publish to GITHUB_STEP_SUMMARY only if
    # writable (in CI discover.sh runs as `builder` while the summary file
    # is root-owned — the workflow publishes the file after su returns).
    local summary_file="${SUMMARY_FILE:-/tmp/discover-summary.md}"
    {
        printf '## Update discovery\n\n'
        printf '%s\n' "${summary_lines[@]}"
    } >"$summary_file"
    if [[ -n "${GITHUB_STEP_SUMMARY:-}" && -w "${GITHUB_STEP_SUMMARY:-/nonexistent}" ]]; then
        cat "$summary_file" >>"$GITHUB_STEP_SUMMARY"
    fi
    keepalive
    if ((failures > 0)); then
        exit 1
    fi
}

main "$@"
