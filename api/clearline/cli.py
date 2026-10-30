"""Dev commands: `python -m clearline.cli migrate|ingest|run "<complaint text>"`."""

import json
import sys
import uuid
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from clearline import db, rag
from clearline.agent.graph import build


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "migrate":
        db.migrate()
        print("schema ok")
    elif cmd == "ingest":
        db.migrate()
        print(f"ingested {rag.ingest()} chunks")
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
