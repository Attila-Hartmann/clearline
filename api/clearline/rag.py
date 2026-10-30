"""Hybrid retrieval over the policy/regulation corpus: pgvector (semantic, cross-lingual) + Postgres FTS
(exact terms like fee codes), fused with Reciprocal Rank Fusion."""

import re
from functools import lru_cache
from pathlib import Path

from fastembed import TextEmbedding

from clearline.config import ROOT, settings
from clearline.db import conn

DOCS_DIR = ROOT / "data" / "docs"
RRF_K = 60


@lru_cache
def embedder() -> TextEmbedding:
    return TextEmbedding(settings().embedding_model)


def embed(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in embedder().embed(texts)]


def parse_doc(path: Path) -> list[dict]:
    """Split a markdown doc with front matter into one chunk per `## ` section."""
    raw = path.read_text(encoding="utf-8")
    meta_block, body = raw.split("---", 2)[1:] if raw.startswith("---") else ("", raw)
    meta = dict(line.split(":", 1) for line in meta_block.strip().splitlines() if ":" in line)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    sections = re.split(r"^## +", body, flags=re.M)[1:]
    chunks = []
    for i, sec in enumerate(sections, 1):
        heading, _, content = sec.partition("\n")
        chunks.append({
            "id": f"{path.stem}#{i}", "doc_id": path.stem, "title": meta.get("title", path.stem),
            "section": heading.strip(), "lang": meta.get("lang", "en"), "content": content.strip(),
            "source_url": meta.get("source") if str(meta.get("source", "")).startswith("http") else None,
        })
    return chunks


def ingest() -> int:
    chunks = [c for p in sorted(DOCS_DIR.glob("*.md")) for c in parse_doc(p)]
    vectors = embed([f"{c['title']} – {c['section']}\n{c['content']}" for c in chunks])
    with conn() as c:
        c.execute("delete from doc_chunks")
        for ch, v in zip(chunks, vectors, strict=True):
            c.execute(
                "insert into doc_chunks (id, doc_id, title, section, lang, content, source_url, embedding) "
                "values (%(id)s, %(doc_id)s, %(title)s, %(section)s, %(lang)s, %(content)s, %(source_url)s, %(v)s)",
                {**ch, "v": v},
            )
    return len(chunks)


def search(query: str, k: int = 6) -> list[dict]:
    [qv] = embed([query])
    with conn() as c:
        vec = c.execute("select id from doc_chunks order by embedding <=> %s::vector limit 20", (qv,)).fetchall()
        fts = c.execute(
            "select id from doc_chunks, websearch_to_tsquery('english', %(q)s) qe, websearch_to_tsquery('hungarian', %(q)s) qh "
            "where tsv @@ (qe || qh) order by ts_rank(tsv, qe || qh) desc limit 20",
            {"q": _or_query(query)},
        ).fetchall()
        scores: dict[str, float] = {}
        for ranking in (vec, fts):
            for rank, row in enumerate(ranking):
                scores[row["id"]] = scores.get(row["id"], 0) + 1 / (RRF_K + rank + 1)
        top = sorted(scores, key=lambda i: scores[i], reverse=True)[:k]
        rows = c.execute("select id, doc_id, title, section, lang, content, source_url from doc_chunks where id = any(%s)",
                         (top,)).fetchall()
    by_id = {r["id"]: r for r in rows}
    return [{**by_id[i], "score": round(scores[i], 4)} for i in top]


def _or_query(q: str) -> str:
    # websearch syntax: OR-join meaningful words so FTS behaves like keyword recall, not an AND filter.
    words = [w for w in re.findall(r"\w{4,}", q.lower())][:24]
    return " or ".join(words) or q


def get_chunk(chunk_id: str) -> dict | None:
    with conn() as c:
        return c.execute("select id, doc_id, title, section, lang, content, source_url from doc_chunks where id = %s",
                         (chunk_id,)).fetchone()
