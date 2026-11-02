# Clearline

**Agentic complaint resolution for regulated banking.** A customer email goes in. Out comes an approved, cited reply
that is ready for audit, and a person decides before anything is sent.

![Case view: the agent caught a prompt injection, refunded exactly the duplicated 89,990 Ft and drafted a cited reply](docs/img/case-injection.png)

Clearline is an open-source reference implementation of an AI agent inside a real, regulated business process:
complaint handling at a (fictional) Hungarian bank. The point is not "an LLM can write a letter". It is the engineering
that makes an agent shippable in a bank: deterministic guardrails, tool use against core-banking data, retrieval over
policy and law, evals that gate every change, cost and latency per case, an audit trail and human oversight.

> Danubia Bank is fictional and all data is synthetic. Regulation summaries are simplified and are not legal advice.

## What happens to a complaint

```mermaid
flowchart LR
  A[Customer email] --> G[Guard<br/>PII redaction + injection screen]
  G --> T[Triage<br/>category, priority,<br/>statutory deadline]
  T --> X[Extract facts]
  X --> I[Investigate<br/>MCP client: read-only<br/>core-banking tools]
  I --> R[Retrieve<br/>hybrid RAG over<br/>policy + HU regulation]
  R --> S[Assess<br/>decision + exact refund<br/>+ code-enforced rules]
  S --> D[Draft cited reply<br/>in customer's language]
  D --> H{{Human review<br/>approve / edit / reject}}
  H --> F[Final + audit trail]
```

| Step | Model tier | What is deterministic |
|---|---|---|
| Guard | worker | PII redaction (regex, unit-tested) before any model call; injection heuristics |
| Triage | worker | Deadline: 15 business days (payment services) or 30 days, Hungarian holidays |
| Investigate | worker + MCP client | Core-banking tools are served over MCP, annotated read-only; the agent can look, never move money |
| Retrieve | – | pgvector + Postgres full-text, Reciprocal Rank Fusion |
| Assess | drafter | Citations must exist; refunds above HUF 200,000 force escalation; injection and vulnerability flags |
| Human review | person | LangGraph `interrupt()`; the paused run persists in Postgres |

## Quality: evals are a CI gate

The agent runs on a golden set of synthetic complaints (Hungarian and English) whose correct outcomes come from the mock
core-banking data and the policies. CI fails if any metric drops below threshold ([ADR-004](docs/adr/004-evals-as-a-ci-gate.md)).

| Metric | Threshold | Latest |
|---|---|---|
| Right decision (uphold / partial / reject / escalate) | ≥ 0.85 | **0.97** |
| Exact refund amount, to the forint | ≥ 0.90 | **0.97** |
| Correct triage | ≥ 0.85 | **1.00** |
| Correct deadline type | ≥ 0.85 | **1.00** |
| Right policy retrieved | ≥ 0.90 | **1.00** |
| Grounded letter (LLM judge) | ≥ 0.80 | **0.96** |
| Injection attempts caught / had no effect | 1.00 | **1.00 / 1.00** |
| False injection alarms | ≤ 0.05 | **0.00** |

31 cases, about $0.003 and 16 s per case on `deepseek-chat` (synthetic data only, see [ADR-003](docs/adr/003-data-residency.md)).
The first run failed the gate. The three remaining misses are kept visible on the Quality page instead of being tuned away.

![Quality page](docs/img/quality.png)

## Observability

Every case is one OpenTelemetry trace: a span per agent step and a span per model call with token usage and cost,
following the GenAI semantic conventions. The trace context is propagated into the MCP server, so core-banking tool calls
show up in the same trace. Tracing is off unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set. The local stack ships Jaeger;
Langfuse or Azure Monitor work through the same standard OTLP variables. Message content is captured only when enabled.

![One complaint as a trace in Jaeger: agent steps, model calls and MCP tool calls into the core-banking service](docs/img/trace.png)

## Tools over MCP

Core-banking lookups (customer, card lookup, transactions, fee rules) are a read-only MCP server. The investigate step is
an MCP client: it can call only the tools the server lists, with the server's schemas, and has no write path.

- In the full compose stack the server is a separate `core-banking` container over streamable HTTP. When
  `CORE_BANKING_MCP_URL` is empty (tests, evals) the same server runs in-process.
- Tools are annotated `readOnlyHint`; a unit test checks that the server exposes these four tools and nothing else.
- Any MCP client can use it. The repo's `.mcp.json` gives Claude Code the server over stdio (`python -m clearline.tools`).
  See [ADR-005](docs/adr/005-tools-behind-mcp.md).

## Run it locally

Requirements: Docker and an API key for any OpenAI-compatible endpoint.

```bash
cp .env.example .env                       # set WORKER_API_KEY
docker compose --profile full up --build   # app on http://localhost:4200, traces on http://localhost:16686
```

For development, also Python 3.12 with [uv](https://docs.astral.sh/uv/) and Node 24:

```bash
cp .env.example .env            # set WORKER_API_KEY (and optionally a separate DRAFTER_* tier)
docker compose up -d db         # Postgres 17 + pgvector

cd api
uv sync
uv run python -m clearline.cli seed          # ingest policies, process 10 showcase complaints
uv run uvicorn clearline.main:app --port 8000

cd ../web
npm ci
npx ng serve --proxy-config proxy.conf.json  # http://localhost:4200
```

Checks: `uv run pytest`, `uv run ruff check . ../evals`, `uv run pyright`, `uv run python ../evals/run.py`.

## Design decisions

- [ADR-001](docs/adr/001-graph-with-human-interrupt.md): a fixed LangGraph pipeline with a human interrupt, not a free-roaming agent
- [ADR-002](docs/adr/002-hybrid-retrieval-in-postgres.md): hybrid retrieval inside Postgres instead of a separate vector database
- [ADR-003](docs/adr/003-data-residency.md): customer data never goes to a non-EU model endpoint
- [ADR-004](docs/adr/004-evals-as-a-ci-gate.md): evals are a CI gate, not a dashboard
- [ADR-005](docs/adr/005-tools-behind-mcp.md): core-banking tools sit behind an MCP server

## What a production deployment would add

Authentication and per-tool authorization on the MCP server, single sign-on with role-based access (e.g. Keycloak) and four-eyes approval above a threshold, NER-based redaction for
names in prose, a DPIA and AI Act documentation for the deployment, integration with the real complaint register and
core banking, a reranker once the corpus grows, and online monitoring of reviewer override rates per category.

## Stack

Python 3.12, LangGraph, FastAPI (server-sent events), PostgreSQL 17 + pgvector, fastembed (multilingual, local),
OpenAI-compatible model tiers with cost accounting, MCP (Python SDK 2), OpenTelemetry + Jaeger, Angular 22 (signals, zoneless) with Optimus UI, pytest, ruff, pyright,
Docker, GitHub Actions.

---

Built by [Attila Hartmann](https://www.linkedin.com/in/attila-hartmann-b7b41a24b), AI engineer in Budapest.
