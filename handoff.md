# HANDOFF — 2026-09-21 (temporary; fold into STATE.md/changelog when done, then delete)

## The single open task
Repo Assist's first-ever real agent run is LIVE: **run 35629241128**
(workflow_dispatch, main). `activation` PASSED (first time since the
09-15 cutover); `agent` was `in_progress` when this session ended.

1. `gh run view 35629241128 --json status,conclusion,jobs`
2. **If green:** close issues #6 #7 #8 #15 #16 #17 (`[aw] Repo Assist
   failed` — all same root cause, root-cause comments already posted).
   Tell maintainer `BAI_API_KEY` repo secret is now deletable (do not
   delete it yourself; credentials change only deliberately). Update
   STATE heartbeat + changelog, delete this file, commit, push.
3. **If failed:** read the `agent` job log
   (`gh run view --log-failed --job <id>`; pi's provider attempts are
   logged `[gh-aw/pi-provider] provider_request ... url=...`). Diagnose
   against the unproven links below; fix in
   `.github/workflows/repo-assist.md`, `gh aw compile` (v0.88.7, local
   plugin matches), push, re-dispatch. If a new `[aw]` issue was filed,
   that's the failure's own report — read it.

## The unproven links (this is where it can still break)
Engine: pi (maintainer pin) on Nous Research inference API, model alias
`openai/laguna-s-2.1` in engine.model → compiled CLI
`--model openai/laguna-s-2.1` → pi must partial-match the models.json
entry (written by the "Configure pi custom provider" step) whose id is
the wire id `poolside/laguna-s-2.1:free`.

- **UNPROVEN A (local repro said NO, CI untested):** I ran pi 0.84.3
  locally with `HOME=$tmp/.pi/agent/models.json`; it did NOT load the
  file (key fell back to env, request went to api.openai.com, 401;
  `--list-models` showed no custom entry). pi's `getAgentDir()` is in
  `node_modules/@earendil-works/pi-coding-agent/dist/config.js:~420`
  (models.json = `join(getAgentDir(), "models.json")`). **Verify the
  exact directory pi reads** — if it is not `$HOME/.pi/agent/`, the CI
  step writes models.json to the WRONG PATH and must be fixed to match
  (gh-aw's own steps touch `~/.pi/agents`/`.pi` — check where the runner
  HOME points for the agent step, incl. any env restore step).
- **UNPROVEN B:** pi_provider.cjs (gh-aw extension) registers provider
  `openai` with `{apiKey: $OPENAI_API_KEY, api:"openai-responses"}`, no
  models/baseUrl. I read pi 0.84.3 `provider-composer.ts`:
  `applyExtension()` passes the models list through in that case and
  `configuredApiKey = extension?.apiKey ?? config?.apiKey` — same key
  value either way. Source-verified, not runtime-verified.
- If models.json path is wrong: fix the step's target dir; do NOT switch
  provider/engine names around — the routing comments in the workflow md
  record why alternatives die (COPILOT secret is format-checked as a
  `github_pat_*`; gh-aw schema forbids `/` after the model prefix;
  pi strips `:free` as a thinking level; unknown/`b-ai` prefixes compile
  to `github-copilot/`).

## Known-good facts (verified this session; re-verify if they matter)
- Secrets (repo): `AUR_SSH_KEY`, `AUR_KNOWN_HOSTS`, `OPENAI_API_KEY`
  (= **Nous key**, set 2026-09-21 from maintainer env; name is only
  gh-aw's broker for OpenAI-compatible pi models, presence-checked, no
  format check), `BAI_API_KEY` (unreferenced).
- Nous API: key has 0 credits → `:free` models only.
  `poolside/laguna-s-2.1:free` verified chat + function tools (262K ctx).
  `inclusionai/ling-3.0-flash-fin:free` verified tools (alt).
  `upstage/solar-pro4:free` (maintainer's first pick) is broken upstream:
  400 "missing tags" (wants `tags.user`, pi can't send it), then 500s.
  Tell the maintainer if they ask about it.
- Lint gate: green (run 35624285789, first since cutover). `bash
  scripts/check-consistency.sh` passes on plain Linux.
- gh-aw validate/agent-env plumbing and pi provider-composer internals:
  analysis in `.github/workflows/repo-assist.md` comments +
  `docs/repo-assist.md` "Provider" — written this session, mostly
  verified; treat any "verified" claim as re-checkable, not gospel.
- Repo Assist itself is still UNTRUSTED until run 35629241128 is green:
  it may push the `repo-memory` branch, file/label issues, open draft
  PRs. A green run's OUTPUT also needs review before trusting (first
  real run ever — check what it actually did to issues/PRs/memory).

## Done this session (all committed+pushed, tree clean; details in
## docs/changelog/2026-09-21.md and STATE.md heartbeat 17:00Z)
- Root-caused + fixed daily activation failure (engine block rewritten,
  lock recompiled: commits 27a09a2 → HEAD chain incl. 874f23f which had
  never been pushed).
- Issues #5 #9 #10 #11 #12 #13 #14 fixed and CLOSED with evidence;
  hold feature removed; latent lint.yml + verify-package.sh +
  shellcheck bugs that the old red gate had masked were found and fixed
  (83951b1, 2cd0aea, dc4c963).
- `[aw]` issues #6 #7 #8 #15 #16 #17: root-cause + pivot comments
  posted; left open on purpose.
- AGENTS.md one-line fix (wrong workflow filename) — logged in changelog
  per its constitution rule.
