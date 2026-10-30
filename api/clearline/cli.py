"""Dev commands: `python -m clearline.cli migrate|ingest|seed|run "<complaint text>"`."""

import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from clearline import db, rag, service
from clearline.agent.graph import build
from clearline.config import ROOT

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
