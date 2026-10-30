create extension if not exists vector;

create table if not exists doc_chunks (
  id          text primary key,              -- e.g. fee-schedule#3
  doc_id      text not null,
  title       text not null,
  section     text not null,
  lang        text not null,                 -- hu | en
  content     text not null,
  source_url  text,
  embedding   vector(384) not null,
  tsv         tsvector generated always as (
                to_tsvector(case lang when 'hu' then 'hungarian'::regconfig else 'english'::regconfig end,
                            title || ' ' || section || ' ' || content)) stored
);
create index if not exists doc_chunks_embedding on doc_chunks using hnsw (embedding vector_cosine_ops);
create index if not exists doc_chunks_tsv on doc_chunks using gin (tsv);

create table if not exists cases (
  id             text primary key,
  created_at     timestamptz not null default now(),
  received_at    timestamptz not null default now(),
  channel        text not null default 'email',
  subject        text not null,
  body           text not null,               -- raw text; never sent to an LLM
  body_redacted  text,
  lang           text,
  status         text not null default 'new', -- new | processing | awaiting_review | approved | rejected | failed
  showcase       boolean not null default false,
  state          jsonb not null default '{}'::jsonb,  -- latest agent state snapshot for the UI
  decision       jsonb,
  final_response text
);

create table if not exists audit_events (
  id             bigserial primary key,
  case_id        text not null references cases(id) on delete cascade,
  ts             timestamptz not null default now(),
  step           text not null,
  actor          text not null,               -- agent | tool | human | system
  model          text,
  prompt_version text,
  tokens_in      int,
  tokens_cached  int,
  tokens_out     int,
  cost_usd       numeric(12, 6),
  latency_ms     int,
  payload        jsonb not null default '{}'::jsonb
);
create index if not exists audit_events_case on audit_events (case_id, id);
