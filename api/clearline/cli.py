"""Dev commands: `python -m clearline.cli migrate|ingest|seed|export [dir]|run "<complaint text>"`."""

import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder
from langgraph.checkpoint.memory import InMemorySaver

from clearline import db, rag, service
from clearline.agent.graph import build
from clearline.config import ROOT, settings

# Showcase: one of each kind a recruiter should see (injection, vulnerable customer, escalation, reject, partial).
SHOWCASE = ["S17-en", "S01-hu", "S03-hu", "S07-en", "S18-hu", "S04-en", "S10-hu", "S14-en", "S06-hu", "S02-en"]


def seed() -> None:
    """Replace all cases with freshly processed showcase cases, left awaiting review for visitors."""
    golden = {c["id"]: c for c in map(json.loads, (ROOT / "evals" / "golden" / "cases.jsonl").read_text(encoding="utf-8").splitlines()) if c}
    with db.conn() as c:
        c.execute("delete from cases")
    ids = [service.create_case(golden[g]["subject"], golden[g]["body"], showcase=True, received="2026-10-21") for g in SHOWCASE]
    with ThreadPoolExecutor(5) as ex:
        list(ex.map(lambda i: list(service.run(i)), ids))
    print(f"seeded {len(ids)} showcase cases")


def export(out: Path) -> None:
    """Snapshot of the showcase as the API would serve it, for the static read-only demo (GitHub Pages)."""
    from clearline import main as api  # FastAPI handlers, so the JSON matches the live API exactly

    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, Any] = {"cases": [c for c in service.list_cases() if c["showcase"]], "metrics": service.metrics(),
                             "evals": api.evals(), "health": {"ok": True, "data_mode": "static-demo",
                                                              "models": {t: settings().tier(t).model for t in ("worker", "drafter")}}}
    for c in files["cases"]:
        files[f"cases-{c['id']}"] = api.case(c["id"])
    with db.conn() as c:
        files["chunks"] = {r["id"]: r for r in c.execute("select id, doc_id, title, section, lang, content, source_url from doc_chunks")}
    for name, data in files.items():
        (out / f"{name}.json").write_text(json.dumps(jsonable_encoder(data), ensure_ascii=False), encoding="utf-8")
    print(f"exported {len(files)} files to {out}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "migrate":
        db.migrate()
        print("schema ok")
    elif cmd == "ingest":
        db.migrate()
        print(f"ingested {rag.ingest()} chunks")
    elif cmd == "seed":
        db.migrate()
        seed()
    elif cmd == "export":
        export(Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "web" / "public" / "demo")
    elif cmd == "search":
        for h in rag.search(" ".join(sys.argv[2:])):
            print(h["score"], h["id"], h["section"])
    elif cmd == "run":
        graph = build(InMemorySaver())
        cfg: Any = {"configurable": {"thread_id": str(uuid.uuid4())}}
        state = graph.invoke({"case_id": "dev", "subject": "Complaint", "body": " ".join(sys.argv[2:]),
                              "received": "2026-10-21"}, cfg)
        for e in state["events"]:
            print(f"{e['step']:<28} {e.get('model', ''):<14} {e.get('cost_usd', '')!s:<10} {e.get('latency_ms', '')}")
        print(json.dumps({k: state[k] for k in ("triage", "assessment", "draft")}, ensure_ascii=False, indent=2))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
