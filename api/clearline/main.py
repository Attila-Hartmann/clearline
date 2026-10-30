import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from clearline import db, rag, service
from clearline.agent.models import ReviewDecision
from clearline.config import ROOT, settings

EVAL_REPORT = ROOT / "evals" / "reports" / "latest.json"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.migrate()
    with db.conn() as c:
        empty = c.execute("select count(*) n from doc_chunks").fetchone()["n"] == 0  # type: ignore[index]
    if empty:
        rag.ingest()
    for tier in ("worker", "drafter"):
        settings().tier(tier)  # fail fast on DATA_MODE / region violations
    yield


app = FastAPI(title="Clearline API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"], allow_methods=["*"], allow_headers=["*"])


class NewCase(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=20, max_length=5000)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "data_mode": settings().data_mode,
            "models": {t: settings().tier(t).model for t in ("worker", "drafter")}}


@app.get("/api/cases")
def cases() -> list[dict]:
    return service.list_cases()


@app.post("/api/cases", status_code=201)
def new_case(body: NewCase) -> dict:
    try:
        return {"id": service.create_case(body.subject, body.body)}
    except PermissionError as e:
        raise HTTPException(429, str(e)) from e


@app.get("/api/cases/{case_id}")
def case(case_id: str) -> dict:
    c = service.get_case(case_id)
    if not c:
        raise HTTPException(404, "case not found")
    if not c["showcase"]:  # visitor-submitted text may contain real PII: only ever serve the redacted version
        c["body"] = c["state"].get("redacted", "[redacting…]")
    return c


@app.get("/api/cases/{case_id}/run")
def run(case_id: str) -> StreamingResponse:
    """Server-sent events: one message per agent node as it completes."""
    def stream():
        for msg in service.run(case_id):
            yield f"data: {service.dumps(msg)}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/cases/{case_id}/decision")
def decision(case_id: str, d: ReviewDecision) -> dict:
    try:
        return service.decide(case_id, d)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/api/chunks/{chunk_id}")
def chunk(chunk_id: str) -> dict:
    c = rag.get_chunk(chunk_id)
    if not c:
        raise HTTPException(404, "chunk not found")
    return c


@app.get("/api/metrics")
def metrics() -> dict:
    return service.metrics()


@app.get("/api/evals")
def evals() -> dict:
    if not EVAL_REPORT.exists():
        raise HTTPException(404, "no eval report yet")
    history = sorted((ROOT / "evals" / "reports").glob("history/*.json"))
    return {"latest": json.loads(EVAL_REPORT.read_text(encoding="utf-8")),
            "history": [json.loads(Path(p).read_text(encoding="utf-8"))["summary"] for p in history[-30:]]}
