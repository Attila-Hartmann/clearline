# ADR-002: Hybrid retrieval inside Postgres instead of a separate vector database

**Status:** accepted

## Context
The corpus is small (bank policies and regulation summaries), bilingual (English policies, Hungarian regulation) and
must be auditable. Complaints mention exact terms ("Plus csomag", fee codes) as well as paraphrases.

## Decision
One Postgres instance holds cases, the audit log, LangGraph checkpoints and the document chunks.
Retrieval fuses two rankings with Reciprocal Rank Fusion:
- **pgvector** cosine search over multilingual embeddings (`paraphrase-multilingual-MiniLM-L12-v2`, run locally, so no
  document or query text leaves the service), which matches a Hungarian complaint to an English policy;
- **full-text search** with Hungarian and English stemming, which catches exact terms and codes.

## Consequences
- One database to back up, secure and audit; transactional consistency between cases and their evidence.
- Retrieval quality is measured in the eval suite (`retrieval_recall`), so changes are visible.
- At millions of chunks a dedicated vector store or a reranker may be needed; not before.
