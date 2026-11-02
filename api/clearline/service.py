"""Case lifecycle: create → run agent (streamed, audited) → await human review → resume → final."""

import json
import uuid
from collections.abc import Iterator
from datetime import date
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg.types.json import Jsonb

from clearline.agent.graph import build
from clearline.agent.models import ReviewDecision
from clearline.config import settings
from clearline.db import conn, pool
from clearline.tracing import carrier, tracer

SNAPSHOT_KEYS = ("redacted", "pii", "screen", "triage", "due_date", "extraction", "evidence", "investigation", "retrieved",
                 "assessment", "draft", "review", "final")


@lru_cache
def graph():
    saver = PostgresSaver(pool())  # type: ignore[arg-type]
    saver.setup()
    return build(saver)


def _cfg(case_id: str, trace: dict | None = None) -> RunnableConfig:
    return {"configurable": {"thread_id": case_id, "trace": trace or {}}}


def create_case(subject: str, body: str, *, showcase: bool = False, received: str | None = None) -> str:
    if not showcase:
        with conn() as c:
            n = c.execute("select count(*) n from cases where not showcase and created_at > now() - interval '1 day'").fetchone()
        if n and n["n"] >= settings().daily_live_case_limit:
            raise PermissionError("Daily demo limit reached. Explore the showcase cases, or try again tomorrow.")
    case_id = f"CL-{uuid.uuid4().hex[:8].upper()}"
    with conn() as c:
        c.execute("insert into cases (id, subject, body, showcase, received_at) values (%s, %s, %s, %s, %s)",
                  (case_id, subject, body, showcase, received or date.today().isoformat()))
    return case_id


def _persist(case_id: str, update: dict[str, Any]) -> list[dict]:
    """Store new audit events and the latest state snapshot; return the events for streaming."""
    events = update.get("events", [])
    with conn() as c:
        for e in events:
            c.execute(
                "insert into audit_events (case_id, step, actor, model, prompt_version, tokens_in, tokens_cached, "
                "tokens_out, cost_usd, latency_ms, payload) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (case_id, e["step"], e["actor"], e.get("model"), e.get("prompt_version"), e.get("tokens_in"),
                 e.get("tokens_cached"), e.get("tokens_out"), e.get("cost_usd"),
                 e.get("latency_ms") or e["payload"].get("latency_ms"), Jsonb(e["payload"])))
        snap = {k: v for k, v in update.items() if k in SNAPSHOT_KEYS}
        if snap:
            c.execute("update cases set state = state || %s, lang = coalesce(%s, lang) where id = %s",
                      (Jsonb(snap), (snap.get("triage") or {}).get("lang"), case_id))
    return events


def run(case_id: str) -> Iterator[dict]:
    """Run the agent until it pauses for human review, yielding each node's events as they happen."""
    with conn() as c:
        claimed = c.execute("update cases set status = 'processing' where id = %s and status = 'new' returning *",
                            (case_id,)).fetchone()
    if not claimed:
        yield {"type": "info", "message": "case already processed or processing"}
        return
    inputs: Any = {"case_id": case_id, "subject": claimed["subject"], "body": claimed["body"],
              "received": claimed["received_at"].date().isoformat()}
    # Explicit parent instead of a "current" span: this generator is resumed on different threadpool threads.
    root = tracer.start_span(f"case {case_id}", attributes={"clearline.case_id": case_id})
    try:
        for chunk in graph().stream(inputs, _cfg(case_id, carrier(root)), stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    continue
                yield {"type": "node", "node": node, "events": _persist(case_id, update or {}),
                       "state": {k: v for k, v in (update or {}).items() if k in SNAPSHOT_KEYS}}
        _set_status(case_id, "awaiting_review")
        yield {"type": "done", "status": "awaiting_review"}
    except Exception as e:  # surface failures to the UI and keep the case inspectable
        _set_status(case_id, "failed")
        _persist(case_id, {"events": [{"step": "error", "actor": "system", "payload": {"error": str(e)[:500]}}]})
        yield {"type": "error", "message": str(e)[:500]}
    finally:
        root.end()


def decide(case_id: str, decision: ReviewDecision) -> dict:
    if decision.action == "reject" and not decision.reason:
        raise ValueError("A rejection needs a reason.")
    case = get_case(case_id)
    if not case or case["status"] != "awaiting_review":
        raise ValueError("Case is not awaiting review.")
    final_state: dict = {}
    for chunk in graph().stream(Command(resume=decision.model_dump()), _cfg(case_id), stream_mode="updates"):
        for update in chunk.values():
            _persist(case_id, update or {})
            final_state |= update or {}
    final = final_state.get("final", {})
    with conn() as c:
        c.execute("update cases set status = %s, decision = %s, final_response = %s where id = %s",
                  (final.get("status", "approved"), Jsonb(decision.model_dump()), final.get("body"), case_id))
    return final


def _set_status(case_id: str, status: str) -> None:
    with conn() as c:
        c.execute("update cases set status = %s where id = %s", (status, case_id))


def list_cases() -> list[dict]:
    with conn() as c:
        return c.execute(
            "select c.id, c.subject, c.status, c.lang, c.showcase, c.received_at, c.state->'triage' triage, "
            "c.state->>'due_date' due_date, c.state->'assessment'->>'decision' decision, "
            "c.state->'assessment'->'risk_flags' risk_flags, coalesce(sum(a.cost_usd), 0)::float cost_usd "
            "from cases c left join audit_events a on a.case_id = c.id group by c.id order by c.received_at desc, c.created_at desc"
        ).fetchall()


def get_case(case_id: str) -> dict | None:
    with conn() as c:
        case = c.execute("select * from cases where id = %s", (case_id,)).fetchone()
        if case:
            case["events"] = c.execute("select * from audit_events where case_id = %s order by id", (case_id,)).fetchall()
    return case


def metrics() -> dict:
    with conn() as c:
        per_step = c.execute(
            "select step, count(*) calls, avg(latency_ms)::int avg_ms, "
            "percentile_cont(0.5) within group (order by latency_ms)::int p50_ms, "
            "percentile_cont(0.95) within group (order by latency_ms)::int p95_ms, coalesce(sum(cost_usd),0)::float cost_usd "
            "from audit_events where latency_ms is not null group by step order by min(id)").fetchall()
        per_model = c.execute(
            "select model, count(*) calls, sum(tokens_in)::int tokens_in, sum(tokens_cached)::int tokens_cached, "
            "sum(tokens_out)::int tokens_out, sum(cost_usd)::float cost_usd from audit_events where model is not null group by model"
        ).fetchall()
        per_case = c.execute(
            "select avg(cost)::float avg_cost_usd, percentile_cont(0.5) within group (order by ms)::int p50_ms, "
            "percentile_cont(0.95) within group (order by ms)::int p95_ms, count(*) cases from "
            "(select case_id, sum(cost_usd) cost, sum(latency_ms) ms from audit_events where step <> 'human_review' group by case_id) t"
        ).fetchone()
        outcomes = c.execute("select status, count(*) n from cases group by status").fetchall()
        reviews = c.execute("select decision->>'action' action, count(*) n from cases where decision is not null group by 1").fetchall()
    return {"per_step": per_step, "per_model": per_model, "per_case": per_case, "outcomes": outcomes, "reviews": reviews}


def dumps(o: Any) -> str:
    return json.dumps(o, ensure_ascii=False, default=str)
