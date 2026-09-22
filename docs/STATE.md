# State

First thing every run reads, after `AGENTS.md`. If this file disagrees with
anything else, this file wins for status, and you fix the loser in the same
change.

This file is capped. When the heartbeat log below exceeds 50 entries, move
the oldest to `docs/archive/STATE-<year>.md` (create it if needed). Old
closed questions: keep at most 5 closed entries in this file; move older
closed ones to the same archive. Open questions are never pruned.

- heartbeat: 2026-09-22T15:05Z — token redesign shipped per user order
  (<100k total, <5k system, <20 requests). Split: new plain
  `.github/workflows/discover.yml` (cron 17 */3, zero AI tokens) runs
  `scripts/discover.sh` — probe (probe-upstream.py `--latest-tag-only
  --newer-than`, prerelease-aware), bump transaction, one PR per pkg,
  ≥10d-silent keepalive commit. repo-assist.md: schedule dropped,
  `max-turns: 12`, repo-memory disabled (seed notes.json deleted), body
  dieted; lock recompiled v0.88.7 (GH_AW_MAX_TURNS=12 in agent env,
  no `schedule:`, github MCP stays out via gh-proxy). check-consistency
  gates split: discover.yml must schedule, lock must not, md must carry
  max-turns. Proven locally: comparator cases green; live discover
  probed 4/4 current; injected 1.6.3 drift ran the full transaction
  (download, sha256, printsrcinfo, verifysource, consistency) and
  reverted clean. Pending: dispatch discover.yml + gh aw run proof,
  measure tokens against bounds, fill changelog numbers.
- heartbeat: 2026-09-22T08:45Z — GREEN. Proof run 35703973675 fully
  green on user-picked gemini-3.5-flash-lite (served as pinned, no
  remap; agent success, safe_outputs, memory). Agent's update
  discovery: all four packages current, no bumps. Closed #23 (proof
  met) and #24 (noop report). #20 stays (auto-managed log).
- heartbeat: 2026-09-22T08:10Z — this run: answered "19.5k for WHAT"
  with measurements (memory 150B and md 3.2KB ruled out; github MCP
  schemas+icons are the bulk, ~8.8k tokens in icons alone in a partial
  sample) and cut it: toolsets [all] dropped, github mode gh-proxy
  (reads via gh CLI, no MCP server in context). Proof run 35701470825:
  input/req fell 19527→15117 (-23%) but STILL red on 429 — 15.1k/req
  leaves ~900 headroom under the 16k TPM cap, so any two requests in
  one minute exceed it; retries can never pace a multi-step loop.
  Gemma 4 free tier is structurally unfit here. #23 open. Pending:
  revert to proven-green flash-lite or keep Gemma red.
- heartbeat: 2026-09-22T06:50Z — this run: switched pin to
  gemma-4-26b-a4b-it per user request (lock recompiled, consistency
  green) and dispatched proof run 35694811135: RED after 15.5 min,
  7 tool calls — free-tier input TPM limit is 16000, prompt is
  ~19.5k/request, so every request is over budget and retries can
  never succeed. Gemma 4 structurally unworkable on this key's free
  tier. #23 stays open. Awaiting user call: keep Gemma or revert to
  proven-green flash-lite.
- heartbeat: 2026-09-22T05:10Z — this run: diagnosed the two latest
  Repo Assist failures (35688439003 dispatch, 35689069855 schedule)
  as Gemini daily quota exhaustion on gemini-2.5-flash-lite (429,
  exit 173, "exhausted your daily quota"), not config. Lint green.
  Unfixable from here — waits on quota reset / AI Studio increase.
  #23 stays open as live tracker.
- heartbeat: 2026-09-22T00:50Z — this run: full `verify-package.sh`
  pass on all four packages (real artifact download, sha256 match,
  `.SRCINFO` parity; namcap/shellcheck skipped, not installed here —
  the lint gate is authoritative for those). Per-package notes bumped
  to verified 2026-09-22.
- heartbeat: 2026-09-22T00:35Z — this run: answered the "packages far
  behind" complaint with a live probe — all four upstreams match
  packaged versions (mpatch 1.6.4, umadev 1.1.1, axonhub 1.0.0-beta10,
  gitcrawl 0.10.0), nothing to bump. Found the real gap instead: the
  lean rebuild dropped task selection and with it any standing
  update-discovery duty (old discover workflow was deleted at cutover),
  so drift had no guard. Fixed: "Update discovery" section added to
  `.github/workflows/repo-assist.md` (probe every active entry each
  scheduled run, bump + PR on drift), lock recompiled with gh-aw
  v0.88.7 (source/lock paired, check-consistency green), duty
  documented in docs/workflows.md + docs/repo-assist.md.
- heartbeat: 2026-09-22T01:00Z — GREEN. Proof run #4 (35656158316)
  fully green: agent success, 15 tool calls, 599k tokens, served
  gemini-2.5-flash-lite as pinned. Closed #21 (failure tracker, proof
  met) and #22 (green-run noop report). #20 stays (auto-managed
  detection log). Chain that fixed it: sandbox.agent=false (exit 41) →
  flash pin (Gemma TPM) → flash-lite pin (3.5-flash RPD remap).
- heartbeat: 2026-09-22T00:45Z — proof run 35652288698: auth FIXED (agent ran
  15 min, 6 tool calls) but died on quota — Gemma free-tier TPM is 16k,
  prompt is ~92k, every retry over budget. Fix: model pin switched to
  gemini-2.5-flash (250k TPM free). Lock recompiled, consistency green.
  Dispatching second proof run.
- heartbeat: 2026-09-22T00:30Z — maintainer fix for the exit-41 outage:
  root-caused in gemini-cli 0.55.1 bundle + gh-aw 0.88.7 sources —
  (1) GEMINI_DEFAULT_AUTH_TYPE is interactive-only, inert in stream-json
  mode (prior fix never could work); (2) the AWF firewall strips
  GEMINI_API_KEY from the agent container while the CLI ignores
  GEMINI_API_BASE_URL, so no auth method resolves; (3) gateway auth
  fails CLI validation in 0.55.1 and latest 0.60.0 alike. Fix:
  sandbox.agent=false (+ strict:false + dangerous opt-out), so the CLI
  reads GEMINI_API_KEY directly. Lock recompiled, consistency green.
  Proof dispatch next.
- heartbeat: 2026-09-22T00:15Z — maintainer rewrote AGENTS.md: the agent
  is now the responsible maintainer — red workflows are its failure to
  diagnose, fix, prove with a real run, and close. Halt-only posture
  survives solely for the release path (checksums, tarballs,
  credentials). Test dispatch of run 35651101879 still in flight.
- heartbeat: 2026-09-22T00:10Z — maintainer decision: #21 stays OPEN.
  Proof condition unmet — no green scheduled agent run since the
  exit-41 failure (latest Repo Assist runs: failure/cancelled/skipped;
  the 18:29–18:30 successes are issue_comment safe-outputs, not agent
  dispatches). #20 likewise stays (auto-managed detection log).
- heartbeat: 2026-09-22T00:05Z — this run: asked to close open issues;
  halted clean: #21 is the maintainer-kept live tracker for the exit-41
  gemini auth handoff (no green agent run since; latest runs still
  failure/cancelled), #20 is the auto-managed threat-detection log.
  Closing either would destroy evidence. Left both open.
- heartbeat: 2026-09-22T00:00Z — this run: optimized lint.yml
  (split consistency/verify, 4-way matrix, no -Syu, cancel-in-progress,
  read-only perms, timeouts). Gate green.
- heartbeat: 2026-09-21T20:19Z — this run: bumped lint.yml to latest
  (checkout v4→v7, runs-on ubuntu-24.04→ubuntu-latest; archlinux:base-devel
  already rolling-latest, pacman deps float via -Syu). Gate green.
  and trimmed docs to the lean rebuild (dropped superseded history and
  task tables, fixed stale pointers, removed dead fallback code);
  per-package notes record 2026-09-21 verification. Suite green.
- heartbeat: 2026-09-21T19:57Z — this run: backfilled the missing
  `ver_after_asset` key in registry.json (values confirmed by live probe;
  without it, re-adding a carried-over package misfired as conflicting
  data), live-probed all four upstreams (no version updates),
  re-verified every package end-to-end (real artifact download, sha256
  match, .SRCINFO parity), recompiled the lock with gh-aw v0.88.7
  (compiler natively emits the auth env fix; source/lock paired), and
  removed the one-shot apply helper. Full suite green.
- heartbeat: 2026-09-21T19:51Z — this run: live-audited the current
  Repo Assist agent failure and reproduced the Gemini CLI exit 41 cause:
  `GEMINI_API_KEY` was present but no explicit
  `GEMINI_DEFAULT_AUTH_TYPE` was selected. Added the explicit
  `gemini-api-key` auth selection, first-run repo-memory bootstrap,
  transactional package add/remove safeguards, strict upstream/source
  validation, and documentation corrections. Package versions and
  checksums were not changed; the four tracked packages remain carried-over
  and previously verified. The first green Repo Assist run after this fix is
  still unproven.
- heartbeat: 2026-09-21T23:45Z — this run: (1) PR #19 landed the
  stock agentics workflow (engine gemini, every 3h) replacing the curated
  gemma pin (survives at 91412c5); its first gemini run failed
  "Invalid auth method selected" (exit 41, issue #18) — fix needs a
  maintainer decision, left open with evidence. (2) Restored lint.yml
  from pre-nuke history; check-consistency green (shellcheck absent
  here). (3) Re-probed all four upstreams: packaged versions match
  latest tags, no updates. (4) Reverted staged deletions of
  `.vscode/settings.json` (editor pref, not this run's call) and left
  handoff.md deleted per maintainer. GEMINI_API_KEY set; OPENAI_API_KEY
  + BAI_API_KEY unreferenced, deletable.
- heartbeat: 2026-09-21T18:20Z — this run: maintainer decisions (1)
  dropped pi for the built-in gemini engine — deleted the alias/
  models.json plumbing; (2) pinned gemma-4-26b-a4b-it, 31b as manual
  fallback (gh-aw has no auto-failover — verified in schema/binary);
  (3) re-enabled sandbox + threat detection with model-fallback/
  token-steering off (gemma slugs aren't in AWF's catalog). Secret
  GEMINI_API_KEY set. All routes smoke-tested live (REST functionCall
  + headless gemini@0.55.1); no CI run completed because (4) maintainer
  nuked all of .github (incl. lint.yml, templates, agent memory) for a
  manual rebuild — evidence committed first; design recorded in
  docs/repo-assist.md. OPENAI_API_KEY + BAI_API_KEY now unreferenced;
  GEMINI_API_KEY is what the manual setup needs. check-consistency.sh
  will fail on the deleted workflow files until manual setup lands.
- heartbeat: 2026-09-21T17:00Z — this run: diagnosed the daily schedule
  failures (activation requires COPILOT_GITHUB_TOKEN for pi+bare model;
  never set — see changelog 2026-09-21), rerouted the engine to pi on
  the `openai/` prefix so a third-party OpenAI-compatible key rides
  gh-aw's native OPENAI_API_KEY broker (lock recompiled, v0.88.7),
  pushed the long-unpushed 09-15 sandbox-off work alongside it, removed
  the hold feature (#5), fixed check-consistency expectations (#9, #10 —
  gate green locally), verify.yml docs (#11), stale NOUS secrets docs
  (#12), update-pkgbuild input validation (#13), and the minor batch
  (#14). Getting main's Lint gate green for the first time since cutover
  (run 35624285789) required three latent fixes its early failure had
  masked: shellcheck SC2043 one-element loop (83951b1), unescaped `$p`
  expanded by lint.yml's `set -u` shell (2cd0aea), and verify-package.sh
  PKGBUILD shellcheck severity plus makepkg needing a writable BUILDDIR
  — now run from a temp copy (dc4c963). Maintainer then clarified
  credentials: no OpenAI/Anthropic access, only free models on the Nous
  inference API; b.ai is dead as a provider choice. Smoke-tested the
  Nous key live: `upstage/solar-pro4:free` broken upstream (400 "missing
  tags" → persistent 500s); pinned `poolside/laguna-s-2.1:free`
  (chat + function tools verified, 262K ctx), via a schema-legal
  gh-aw alias + models.json wire id. Set repo secret OPENAI_API_KEY to
  the maintainer-provided Nous key. **Open: prove the first green
  Repo Assist dispatch run, then close the [aw] failure issues;
  `BAI_API_KEY` then deletable.** See `docs/repo-assist.md` "Provider". Next run: read `handoff.md` at repo root first.
- heartbeat: 2026-09-15 — this run: (1) maintainer confirmed the legacy
  workflows were deleted intentionally, no archive wanted; fixed the four
  dangling references to `docs/legacy-workflows/` (AGENTS.md, docs/README.md,
  docs/workflows.md, STATE.md) to point to git history instead. (2) Moved
  the changelog out of AGENTS.md; per maintainer it is now one file per day
  in `docs/changelog/` (entries carry no date prefix; the filename is the
  date; prior days never edited). (3) Added the STATE.md cap rule above:
  heartbeat log rotates at 50 entries, closed questions at 5. Unrelated
  pre-existing breakage left open: check-consistency.sh expects
  `.github/workflows/repo-assist.yml` but the file is
  `repo-assist.lock.yml`, and expects sections absent from
  `.github/workflows/repo-assist.md`. Not falsifiable from here which name
  is intended — needs the Repo Assist config or next run to resolve.
- heartbeat: 2026-09-15T12:30Z — Repo Assist integrated as primary
  automation; old 7 workflows removed, lint.yml kept; notes.json
  initialized; check-consistency and docs updated for the new architecture.
- heartbeat: 2026-09-15T12:24Z — issue #4 removed; approval gate for
  pkg-remove eliminated; run_gh_safe + field extraction fixes in
  probe-upstream.py; issue #3 reached makepkg but failed there (run
  34964107817), awaiting next CI run.
- last full re-verification: never recorded under this system. A full
  re-verification means: fresh clone, clean chroot, every package rebuilt
  from source, every checksum re-derived, every `.SRCINFO` regenerated and
  diffed. Until that has run, every package is `carried-over`.
- halted packages: none recorded. (A halt here means: do not touch that
  package on schedule until the reason is resolved. See its note in
  `docs/packages/`.)

## Open questions

1. **CLOSED 2026-09-21: check-consistency.sh vs the actual Repo Assist
   filenames.** The script was the loser: it was fixed to validate
   `repo-assist.lock.yml` triggers and `repo-assist.md` sections that
   actually exist (issues #9/#10). `repo-assist.yml` was never meant to
   exist; the compiled workflow is `.lock.yml`, per `docs/repo-assist.md`
   and `gh aw compile` behavior (verified v0.88.7).

2. **Origin of every package is unknown.** All four predate the keeper
   system. Per-package notes carry a recovery path
   (`git log --diff-filter=A -- packages/<pkg>/`) and default to "presume
   deliberately requested; do not remove, rename, or drop without a halt."
   Recover what you can on the next run that has spare capacity.

3. **`docs/research.md`** is reference-only. It stays out of the agent
   reading order (see `docs/README.md`). Leave it in place unless it grows
   enough to confuse a cold reader; if so, delete it.

4. **CLOSED 2026-09-15: the add flow closes the SKIP lifecycle in the same
   job** (probe → issue-apply add → update-pkgbuild → printsrcinfo →
   check-consistency, with rollback). This was the failure behind issue #2.

5. **CLOSED 2026-09-15: leftovers are gitignored, not committed.** No
   tarballs or `src/` tracked under `packages/`.

## Why the heartbeat exists

GitHub disables scheduled workflows after 60 days of *repository* inactivity
— commits, not runs. A quiet repo reads as dead and the cron dies silently.
So every scheduled run updates the `heartbeat:` log above and commits, even
when nothing changed. One entry per run. History beyond the cap lives in
`docs/archive/` and in git. Ugly, load-bearing: it is the difference between
decades and two months.
