<details>
<summary>MCP Gateway</summary>

- ✓ **startup** MCPG Gateway version: v0.4.18
- ✓ **startup** Starting MCPG with config: stdin, listen: 0.0.0.0:8080, log-dir: /tmp/gh-aw/mcp-logs/
- ✓ **startup** WASM compilation cache directory: /tmp/gh-aw/wazero-cache
- ✓ **startup** Environment validation passed
- ✓ **startup** Loaded 1 MCP server(s): [safeoutputs]
- ✓ **startup** Guards sink server ID logging enrichment disabled (no sink server IDs configured)
- ✓ **startup** OpenTelemetry tracing disabled (no OTLP endpoint configured)
- ✓ **backend**
  ```
  Successfully connected to MCP backend server, command=docker
  ```
- 🔍 rpc **safeoutputs**→`tools/list`
- 🔍 rpc **safeoutputs**←`resp` `{"jsonrpc":"2.0","id":1,"result":{"ttlMs":0,"cacheScope":"","tools":[{"description":"WRITE-ONCE: do NOT call this tool with empty or placeholder arguments to probe or discover its schema — required fields (title, body) are listed in this schema; if you are not ready to open the real issue, call `noop` instead. Creates a new GitHub issue for tracking bugs, feature requests, or tasks. Use this for actionable work items that need assignment, labeling, and status tracking. For reports, announcements, or statu...`
- ✓ **startup** Starting MCPG in ROUTED mode on 0.0.0.0:8080
- ✓ **startup** Routes: /mcp/<server> where <server> is one of: [safeoutputs]
- ✓ **startup** TLS not configured — listening on http://0.0.0.0:8080 (set --tls-cert/--tls-key to enable)
- ✓ **backend**
  ```
  Successfully connected to MCP backend server, command=docker
  ```
- 🔍 rpc **safeoutputs**→`tools/call` `{"jsonrpc":"2.0","method":"tools/call","params":{"arguments":{"body":"Probed all active packages in packages/registry.json for upstream updates:\n\n- mpatch-bin (Romelium/mpatch): packaged 1.6.4, upstream latest v1.6.4 (Current)\n- umadev-bin (umacloud/umadev): packaged 1.1.1, upstream latest v1.1.1 (Current)\n- axonhub-bin (looplj/axonhub): packaged 1.0.0-beta10, upstream latest v1.0.0-beta10 (Current)\n- gitcrawl-bin (openclaw/gitcrawl): packaged 0.10.0, upstream latest v0.10.0 (Current)\n\nAll packages a...`
- 🔍 rpc **safeoutputs**←`resp`
  
  ```json
  {"id":1,"result":{"content":[{"text":"{\"result\":\"success\"}","type":"text"}]}}
  ```
- ✓ **shutdown** Shutting down gateway...

</details>
