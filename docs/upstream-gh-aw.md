# Upstream gh-aw gaps (draft issue, unfiled — PAT is repo-scoped)

Target: https://github.com/github/gh-aw · version v0.88.7 (setup
5e508589), engine gemini/gemini-3.5-flash-lite. File when a credential
with cross-repo issue scope is available.

**Draft title:** gemini: max-turns never enforced (GH_AW_MAX_TURNS
unread); evaluateExpression returns defined-but-empty left side of `||`

## 1. `max-turns` compiled but never enforced for gemini

Frontmatter `max-turns: 12` → `GH_AW_MAX_TURNS: 12` in the agent job
env; `validateMaxTurnsSupport` accepts engine=gemini. But nothing on
the gemini path reads it: `grep -r GH_AW_MAX_TURNS setup/` matches only
`parse_claude_log.cjs` (parses `maxTurnsHit` for Claude) and an
unrelated workflow; `claude_harness.cjs` handles `error_max_turns`,
no gemini harness does. Observed: our run with `max-turns: 12`
produced 20 sequential single-call tool_use/tool_result pairs (≥20
model requests). The cap silently no-ops for gemini.

## 2. `evaluateExpression` `||` returns defined-but-empty left operand

`setup/js/runtime_import.cjs`, OR branch:

```js
const leftValue = evaluateExpression(leftExpr);
if (!leftValue.startsWith("${{")) {
  return leftValue;   // "" when left is defined-but-empty; right never evaluated
}
```

For `steps.sanitized.outputs.text || inputs.command` (the stock
repo-assist.md Command Mode line): on workflow_dispatch,
`GH_AW_STEPS_SANITIZED_OUTPUTS_TEXT` is defined as `''`, so lookup
returns `''`, the guard passes, and `inputs.command` (populated in
`GH_AW_INPUTS_COMMAND`) is never consulted. Prompt rendered
`Take heed of **instructions**: ""` while the same step's env dump
showed the full command. GitHub's own evaluation of the same expr
(`GH_AW_EXPR_*` env) is correct; only the node evaluator is wrong.

Repro: `inputs.a || inputs.b` with `a=''`, `b='x'` → `''`, not `x`.

Workaround shipped in repo-assist.md: two separate expressions, never
`||`. Evidence: runs 35710740988 / 35711836254 (empty rendered
instructions despite populated env).
