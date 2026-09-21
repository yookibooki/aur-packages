# HANDOFF — 2026-09-21 (supersedes the pi handoff)

`.github` was nuked entirely (commit follows this file's rewrite):
workflows (repo-assist + lint), agent memory, aw/ pins, skills, issue
templates. Manual setup is the maintainer's next step — gh-aw is NOT
currently installed in the repo; expect the lint gate and
check-consistency.sh to fail until it lands.

Proven facts to reuse (evidence in docs/changelog/2026-09-21.md, last
design in docs/repo-assist.md):
- gh-aw v0.88.7 brokers `engine: gemini` natively via GEMINI_API_KEY.
- Repo secret GEMINI_API_KEY is SET (maintainer's AI Studio key).
- gemma-4-26b-a4b-it + gemma-4-31b-it: REST functionCall AND headless
  gemini@0.55.1 verified with this key. No auto model-failover exists.
- AWF sandbox with gemma needs model-fallback:false + token-steering:false.
- pi/Nous OPENAI_API_KEY and BAI_API_KEY secrets are unreferenced —
  deletable at maintainer's discretion (credentials: deliberate only).
