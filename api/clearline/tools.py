"""Mock core-banking tools. Read-only by design: the agent can look facts up, never move money.
The same functions are exposed to the LLM via function calling (and via the MCP server in mcp/)."""

import json
from functools import lru_cache
from typing import Any

from clearline.config import ROOT

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
    return _load("fees").get(fee_code.upper(), {"error": f"unknown fee code {fee_code}", "codes": list(_load("fees"))})


REGISTRY = {f.__name__: f for f in (get_customer, find_customer_by_card, list_transactions, get_fee_rule)}

SCHEMAS = [
    {"type": "function", "function": {"name": "get_customer", "description": get_customer.__doc__,
     "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {"name": "find_customer_by_card", "description": "Find a customer by card last 4 digits.",
     "parameters": {"type": "object", "properties": {"card_last4": {"type": "string"}}, "required": ["card_last4"]}}},
    {"type": "function", "function": {"name": "list_transactions", "description": list_transactions.__doc__,
     "parameters": {"type": "object", "properties": {
         "customer_id": {"type": "string"}, "date_from": {"type": "string"}, "date_to": {"type": "string"},
         "text": {"type": "string"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {"name": "get_fee_rule", "description": "Fee schedule rule for a fee code, e.g. PLUS_MONTHLY.",
     "parameters": {"type": "object", "properties": {"fee_code": {"type": "string"}}, "required": ["fee_code"]}}},
]


def call(name: str, args: dict) -> Any:
    fn = REGISTRY.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**args)
    except TypeError as e:  # bad arguments from the model: report back instead of crashing the run
        return {"error": str(e)}
