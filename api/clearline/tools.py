"""Mock core-banking tools behind an MCP server. Read-only by design: the agent can look facts up, never move money."""

import json
import sys
from functools import lru_cache
from typing import Any

from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from clearline.config import ROOT, settings

BANK = ROOT / "data" / "bank"


@lru_cache
def _load(name: str) -> Any:
    return json.loads((BANK / f"{name}.json").read_text(encoding="utf-8"))


def get_customer(customer_id: str) -> dict:
    """Customer profile: package, card, flags. Name is returned for the letter salutation only."""
    for c in _load("customers"):
        if c["id"].lower() == customer_id.strip().lower():
            return c
    return {"error": f"no customer {customer_id}"}


def find_customer_by_card(card_last4: str) -> dict:
    """Find a customer by the last 4 digits of their card."""
    hits = [c for c in _load("customers") if c["card_last4"] == card_last4.strip()]
    return hits[0] if len(hits) == 1 else {"error": f"{len(hits)} customers match card ****{card_last4}"}


def list_transactions(customer_id: str, date_from: str | None = None, date_to: str | None = None,
                      text: str | None = None) -> list[dict]:
    """Transactions for a customer, optionally filtered by ISO date range and description/fee-code text."""
    out = []
    for t in _load("transactions"):
        if t["customer_id"].lower() != customer_id.strip().lower():
            continue
        if date_from and t["date"] < date_from or date_to and t["date"] > date_to:
            continue
        if text and text.lower() not in json.dumps(t, ensure_ascii=False).lower():
            continue
        out.append(t)
    return out


def get_fee_rule(fee_code: str) -> dict:
    """Fee schedule rule for a fee code, e.g. PLUS_MONTHLY."""
    return _load("fees").get(fee_code.upper(), {"error": f"unknown fee code {fee_code}", "codes": list(_load("fees"))})


TOOLS = (get_customer, find_customer_by_card, list_transactions, get_fee_rule)

# The bank's side of the boundary: an MCP server the agent (or Claude Code, or any MCP client) connects to.
# Run standalone with `python -m clearline.tools` (stdio) or `python -m clearline.tools --http` (streamable HTTP, :8100).
server = MCPServer("danubia-core-banking", instructions="Read-only lookups in Danubia Bank's (synthetic) core banking.")
for _fn in TOOLS:
    server.add_tool(_fn, annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))


def connect() -> Client:
    """MCP client for the agent: over HTTP when CORE_BANKING_MCP_URL is set, otherwise to the server in-process."""
    return Client(settings().core_banking_mcp_url or server)


def openai_schema(tool: Tool) -> dict:
    return {"type": "function", "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema}}


def result_of(r: CallToolResult) -> Any:
    text = "\n".join(c.text for c in r.content if isinstance(c, TextContent))
    if r.is_error:  # unknown tool, bad arguments: reported back to the model instead of crashing the run
        return {"error": text}
    if isinstance(r.structured_content, dict) and set(r.structured_content) == {"result"}:
        return r.structured_content["result"]  # non-object return values are wrapped by the server
    if r.structured_content is not None:
        return r.structured_content
    try:
        return json.loads(text)
    except ValueError:
        return text


if __name__ == "__main__":
    from clearline import tracing

    tracing.setup()
    if "--http" in sys.argv:
        server.run("streamable-http", host="0.0.0.0", port=8100,  # noqa: S104  # container-internal service
                   transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    else:
        server.run()
