# ADR-005: Core-banking tools sit behind an MCP server

**Status:** accepted

## Context
The agent needs read-only lookups (customer, card lookup, transactions, fee rules) from the core bank. In a bank, those systems belong to another team and sit behind their own boundary. In-process functions with hand-written JSON schemas hide that boundary: nothing shows what the bank exposes, and no other client can use the same tools.

## Decision
- The tools live on an MCP server (`api/clearline/tools.py`). It is defined once and run in three ways: in-process, streamable HTTP (`python -m clearline.tools --http`, port 8100), and stdio for local clients such as Claude Code (`.mcp.json`).
- The `investigate` node is an MCP client. It gets the tool list from the server (`list_tools`) and builds the OpenAI schemas from that, instead of from a hard-coded `SCHEMAS`.
- `CORE_BANKING_MCP_URL` decides the transport. If it is empty, the client talks to the in-process server. Otherwise it connects over HTTP (in compose, `http://core-banking:8100/mcp`).
- Tool results go through `result_of`, which returns structured content, or parsed text, or `{"error": ...}` for bad arguments or unknown tools. A bad tool call is reported back to the model and does not crash the run.
- Every tool is annotated `read_only_hint=True`; the tool set cannot move money.
- In docker-compose the server runs as a separate `core-banking` service and is not published to the host.
- The MCP SDK propagates OpenTelemetry trace context, so tool calls show up under the case's trace in the same way as the agent's own spans.
- Tests talk to the same server object through an MCP client (`test_mcp_server_exposes_only_read_only_lookups`), so the schema and the annotations are checked, not just the functions.

## Consequences
- The tool surface is defined in one place, and the agent sees exactly what the server lists. Adding a tool means adding it on the server; the agent needs no change.
- There is a real boundary that can point at a real core-banking MCP server later by setting `CORE_BANKING_MCP_URL`.
- The in-process path keeps tests and single-process runs simple, with no extra container.
- **Ceiling, stated plainly:** the compose `core-banking` server has no authentication. It is only reachable inside the compose network and is never published to the host, and this is acceptable only because all data is synthetic. A production deployment would add mTLS or OAuth between the client and the server, and per-tool authorization on the server side, so that a tool like `list_transactions` is checked against the caller's identity and not just annotated as read-only.
- In compose, each tool call adds a network hop of a few milliseconds.
- Tool descriptions come from the functions' docstrings. An empty docstring or a missing description shows up as an empty description in the schema.
