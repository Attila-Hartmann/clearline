"""The complaint-resolution agent as a LangGraph state machine.

guard → triage → extract → investigate (tool loop) → retrieve → assess → draft → human_review ⏸ → finalize

Every node appends audit events (model, prompt version, tokens, cost, latency) to `events`. The graph pauses
at human_review with `interrupt()`; nothing reaches the customer until a person approves, edits or rejects.
"""

import asyncio
import hashlib
import json
import operator
import time
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from clearline import guardrails, llm, rag, sla, tools, tracing
from clearline.agent.models import Assessment, Draft, Extraction, ReviewDecision, Screen, Triage

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
MAX_TOOL_ROUNDS = 5
ESCALATION_LIMIT_HUF = 200_000


class State(TypedDict, total=False):
    case_id: str
    subject: str
    body: str
    received: str                      # ISO date
    redacted: str
    pii: list[dict]
    screen: dict
    triage: dict
    due_date: str
    extraction: dict
    evidence: list[dict]
    investigation: str
    retrieved: list[dict]
    assessment: dict
    draft: dict
    review: dict
    final: dict
    events: Annotated[list[dict], operator.add]


@lru_cache
def prompt(name: str) -> tuple[str, str]:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    return text, f"{name}@{hashlib.sha1(text.encode()).hexdigest()[:8]}"


def event(step: str, actor: str = "agent", usage: llm.Usage | None = None, prompt_version: str | None = None,
          **payload: Any) -> dict:
    e: dict[str, Any] = {"step": step, "actor": actor, "prompt_version": prompt_version, "payload": payload}
    if usage:
        e |= {"model": usage.model, "tier": usage.tier, "tokens_in": usage.tokens_in, "tokens_cached": usage.tokens_cached,
              "tokens_out": usage.tokens_out, "cost_usd": round(usage.cost_usd, 6), "latency_ms": usage.latency_ms}
    return e


def _message(state: State) -> str:
    return guardrails.wrap_untrusted(f"Subject: {state.get('subject', '')}\n\n{state['redacted']}")


# ── nodes ────────────────────────────────────────────────────────────────────────────────────────────────

def guard(state: State) -> dict:
    t0 = time.perf_counter()
    redacted, pii = guardrails.redact(state["body"])
    hints = guardrails.injection_heuristic(state["body"])
    system, pv = prompt("screen")
    screen, usage = llm.structured("worker", system, guardrails.wrap_untrusted(redacted), Screen)
    flagged = screen.is_injection or bool(hints)
    return {
        "redacted": redacted, "pii": pii,
        "screen": {"is_injection": flagged, "reason": screen.reason, "heuristic_hits": hints},
        "events": [
            event("redact_pii", "system", found=[p["type"] for p in pii], latency_ms=int((time.perf_counter() - t0) * 1000)),
            event("screen_injection", usage=usage, prompt_version=pv, flagged=flagged, reason=screen.reason, heuristic_hits=hints),
        ],
    }


def triage(state: State) -> dict:
    system, pv = prompt("triage")
    t, usage = llm.structured("worker", system, _message(state), Triage)
    received = date.fromisoformat(state.get("received") or date.today().isoformat())
    due = sla.due_date(received, t.is_payment_service)
    return {"triage": t.model_dump(), "due_date": due.isoformat(),
            "events": [event("triage", usage=usage, prompt_version=pv, **t.model_dump(), due_date=due.isoformat())]}


def extract(state: State) -> dict:
    system, pv = prompt("extract")
    x, usage = llm.structured("worker", system, _message(state), Extraction)
    return {"extraction": x.model_dump(), "events": [event("extract", usage=usage, prompt_version=pv, **x.model_dump())]}


def investigate(state: State) -> dict:
    return asyncio.run(_investigate(state))


async def _investigate(state: State) -> dict:
    """Tool loop against the core-banking MCP server: the agent only sees the tools the server lists."""
    system, pv = prompt("investigate")
    facts = {"triage": state["triage"], "extraction": state["extraction"]}
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{_message(state)}\n\nExtracted so far:\n{json.dumps(facts, ensure_ascii=False)}"},
    ]
    evidence, events = [], []
    summary = ""
    async with tools.connect() as mcp:
        schemas = [tools.openai_schema(t) for t in (await mcp.list_tools()).tools]
        for _ in range(MAX_TOOL_ROUNDS):
            reply = await asyncio.to_thread(llm.chat, "worker", messages, tools=schemas)
            events.append(event("investigate.llm", usage=reply.usage, prompt_version=pv, tool_calls=len(reply.tool_calls)))
            if not reply.tool_calls:
                summary = reply.content
                break
            messages.append(reply.message.model_dump(exclude_none=True))
            for tc in reply.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                t0 = time.perf_counter()
                result = tools.result_of(await mcp.call_tool(tc.function.name, args))
                evidence.append({"tool": tc.function.name, "args": args, "result": result})
                events.append(event(f"tool.{tc.function.name}", "tool", args=args,
                                    latency_ms=int((time.perf_counter() - t0) * 1000), result_preview=str(result)[:300]))
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, ensure_ascii=False)})
    return {"evidence": evidence, "investigation": summary or "Tool budget exhausted.", "events": events}


def retrieve(state: State) -> dict:
    t0 = time.perf_counter()
    query = f"{state['triage']['category'].replace('_', ' ')}: {state['triage']['summary']} {state['extraction']['customer_request']}"
    hits = rag.search(query, k=6)
    return {"retrieved": hits, "events": [event("retrieve", "system", query=query, hits=[h["id"] for h in hits],
                                                latency_ms=int((time.perf_counter() - t0) * 1000))]}


def _excerpts(hits: list[dict]) -> str:
    return "\n\n".join(f"[{h['id']}] {h['title']} – {h['section']}\n{h['content']}" for h in hits)


def assess(state: State) -> dict:
    system, pv = prompt("assess")
    user = (f"{_message(state)}\n\nTriage: {json.dumps(state['triage'], ensure_ascii=False)}\n"
            f"Screening: {json.dumps(state['screen'], ensure_ascii=False)}\n\n"
            f"Investigation facts:\n{state['investigation']}\nRaw tool results:\n{json.dumps(state['evidence'], ensure_ascii=False)[:6000]}\n\n"
            f"Policy and regulation excerpts:\n{_excerpts(state['retrieved'])}")
    a, usage = llm.structured("drafter", system, user, Assessment)
    # Deterministic policy checks the model cannot talk its way around.
    valid_ids = {h["id"] for h in state["retrieved"]}
    a.rules_applied = [r for r in a.rules_applied if r in valid_ids]
    flags = set(a.risk_flags)
    if state["screen"]["is_injection"]:
        flags.add("prompt_injection_attempt")
    if state["triage"]["vulnerable_signals"] or any(e["tool"] == "get_customer" and isinstance(e["result"], dict)
                                                    and e["result"].get("vulnerable") for e in state["evidence"]):
        flags.add("vulnerable_customer")
    if a.refund_huf > ESCALATION_LIMIT_HUF:
        flags.add("high_value")
        a.decision = "escalate"
    a.risk_flags = sorted(flags)
    return {"assessment": a.model_dump(), "events": [event("assess", usage=usage, prompt_version=pv, **a.model_dump())]}


def draft(state: State) -> dict:
    system, pv = prompt("draft")
    lang = state["triage"]["lang"]
    customer = next((e["result"] for e in state["evidence"] if e["tool"] in ("get_customer", "find_customer_by_card")
                     and isinstance(e["result"], dict) and "name" in e["result"]), {})
    cited = [h for h in state["retrieved"] if h["id"] in state["assessment"]["rules_applied"]] or state["retrieved"][:3]
    user = (f"Customer name: {customer.get('name', 'Customer')}\nComplaint subject: {state.get('subject', '')}\n"
            f"Complaint summary: {state['triage']['summary']}\nDecision (final, do not change): "
            f"{json.dumps(state['assessment'], ensure_ascii=False)}\nResponse deadline: {state['due_date']}\n\n"
            f"Policy excerpts you may cite:\n{_excerpts(cited)}")
    d, usage = llm.structured("drafter", system.replace("{lang}", "Hungarian" if lang == "hu" else "English"), user, Draft)
    valid = {h["id"] for h in state["retrieved"]}
    d.citations = [c for c in d.citations if c.chunk_id in valid]
    return {"draft": d.model_dump(), "events": [event("draft", usage=usage, prompt_version=pv, subject=d.subject,
                                                      citations=[c.chunk_id for c in d.citations])]}


def human_review(state: State) -> dict:
    decision = ReviewDecision.model_validate(interrupt({"draft": state["draft"], "assessment": state["assessment"]}))
    return {"review": decision.model_dump(), "events": [event("human_review", "human", **decision.model_dump(exclude={"body"}),
                                                              edited=decision.action == "edit")]}


def finalize(state: State) -> dict:
    r = state["review"]
    if r["action"] == "reject":
        final = {"status": "rejected", "reason": r["reason"]}
    else:
        body = r["body"] if r["action"] == "edit" and r.get("body") else state["draft"]["body"]
        final = {"status": "approved", "subject": state["draft"]["subject"], "body": body,
                 "refund_huf": state["assessment"]["refund_huf"] + state["assessment"]["goodwill_huf"]}
    return {"final": final, "events": [event("finalize", "system", status=final["status"])]}


def build(checkpointer: Any = None, *, stop_before_review: bool = False):
    g = StateGraph(State)
    steps = [guard, triage, extract, investigate, retrieve, assess, draft]
    for fn in steps:
        g.add_node(fn.__name__, tracing.node(fn))
    g.add_edge(START, "guard")
    for a, b in zip(steps, steps[1:], strict=False):
        g.add_edge(a.__name__, b.__name__)
    if stop_before_review:  # evals: run the automated part only
        g.add_edge("draft", END)
    else:
        g.add_node("human_review", human_review)
        g.add_node("finalize", finalize)
        g.add_edge("draft", "human_review")
        g.add_edge("human_review", "finalize")
        g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)
