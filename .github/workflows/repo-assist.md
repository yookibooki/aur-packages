---
engine:
  id: gemini
  model: gemma-4-26b-a4b-it
  env:
    GEMINI_DEFAULT_AUTH_TYPE: gemini-api-key
on:
  schedule:
    - cron: "17 */3 * * *"
  workflow_dispatch:
    inputs:
      command:
        description: "Optional command-mode instruction"
        required: false
        type: string
        default: ""
  slash_command:
    name: repo-assist
  reaction: "eyes"
source: githubnext/agentics/workflows/repo-assist.md@4bc8419fad05e6b032741cbfd189986700bcf71c
permissions: read-all
sandbox:
  agent:
    model-fallback: false
    token-steering: false
network:
  allowed: [defaults, github]
tools:
  bash: true
  github:
    toolsets: [all]
  repo-memory: true
---

# Repo Assist — aur-packages

Lean custom workflow (cut from the stock agentics template 2026-09-22):
engine pin kept, task-selection pre-step and threat-detection job
dropped. Smaller lock, less quota per run.

## Non-Command Mode
Runs every 3h plus /repo-assist commands. Triages open issues/PRs,
makes small focused fixes via safe-outputs, updates notes.json.

## Memory
Schema version 1, 7 fields: version, cursors, issues, fixes, checks, completed_actions, priorities. Stored in.github/repo-assist/notes.json.

## Provider
Engine gemini id:gemini model:gemma-4-26b-a4b-it, fallback gemma-4-31b-it (manual edit + gh aw compile). Auth via GEMINI_API_KEY. Sandbox enabled, model-fallback false, token-steering false. No threat-detection job in this lean build. Lock compiled with gh-aw v0.88.7.
