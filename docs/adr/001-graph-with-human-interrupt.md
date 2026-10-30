# ADR-001: A fixed LangGraph pipeline with a human interrupt, not a free-roaming agent

**Status:** accepted

## Context
Complaint handling is a regulated procedure: deadlines, mandatory content, escalation rules, an auditor who will ask
"why was this decided?". A single autonomous agent that plans its own steps is hard to audit and hard to evaluate.

## Decision
The workflow is a fixed state graph (guard → triage → extract → investigate → retrieve → assess → draft → human review →
finalize). Autonomy is used only where it adds value: the investigation step chooses which read-only tools to call.
The graph pauses with `interrupt()` before anything reaches the customer; the Postgres checkpointer persists the paused
run, so a reviewer can resume it hours later from another process.

## Consequences
- Every step is a node with its own prompt version, model, cost and latency in the audit log.
- Each node can be evaluated and swapped independently (e.g. a cheaper triage model).
- Deterministic rules the model must not override (escalation above HUF 200,000, citations must exist, injection flags)
  are enforced in code after the model call.
- Less flexible than an open agent for unforeseen complaint types; those are routed to `escalate`.
