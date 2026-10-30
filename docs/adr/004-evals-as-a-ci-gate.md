# ADR-004: Evals are a CI gate, not a dashboard

**Status:** accepted

## Context
Prompt and model changes silently change behaviour. "It looked fine on three examples" is how wrong refunds ship.

## Decision
- A golden set of synthetic complaints (`evals/golden/cases.jsonl`) is generated from scenario specs whose expected
  outcome is derived from the mock core-banking data and the policies, and every generated email is checked to contain
  the key facts verbatim.
- `evals/run.py` measures decision accuracy, exact refund, triage, deadline type, retrieval recall, citation support,
  groundedness (LLM judge), injection recall / false positives / resistance, cost and latency.
- `evals/thresholds.json` defines the bar; CI fails below it.

## Consequences
- The first run failed the gate (decision accuracy 0.84, groundedness 0.73). Root causes were a data bug (signatures not
  matching account holders, which the agent correctly treated as an identity risk) and judge context; both were fixed
  in the harness, not by loosening thresholds.
- Two known misses stay visible (a hardship case where the agent also refunded a bank error the customer did not raise;
  a staff-conduct case escalated to the branch manager). They are documented rather than tuned away.
- Each eval run costs about USD 0.10 on the default models.
