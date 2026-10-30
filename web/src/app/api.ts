import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

export type CaseStatus = 'new' | 'processing' | 'awaiting_review' | 'approved' | 'rejected' | 'failed';
export type Decision = 'uphold' | 'partial' | 'reject' | 'escalate';

export interface CaseSummary {
  id: string;
  subject: string;
  status: CaseStatus;
  lang: string | null;
  showcase: boolean;
  received_at: string;
  triage: Triage | null;
  due_date: string | null;
  decision: Decision | null;
  risk_flags: string[] | null;
  cost_usd: number;
}

export interface Triage {
  category: string;
  product: string;
  is_payment_service: boolean;
  priority: 'low' | 'normal' | 'high';
  vulnerable_signals: boolean;
  lang: 'hu' | 'en';
  summary: string;
}

export interface Assessment {
  decision: Decision;
  refund_huf: number;
  goodwill_huf: number;
  rationale: string;
  rules_applied: string[];
  risk_flags: string[];
  confidence: number;
}

export interface Chunk { id: string; doc_id: string; title: string; section: string; lang: string; content: string; source_url: string | null; score?: number }
export interface Draft { subject: string; body: string; citations: { marker: number; chunk_id: string }[] }

export interface CaseState {
  redacted?: string;
  pii?: { type: string }[];
  screen?: { is_injection: boolean; reason: string; heuristic_hits: string[] };
  triage?: Triage;
  due_date?: string;
  extraction?: Record<string, unknown>;
  evidence?: { tool: string; args: Record<string, unknown>; result: unknown }[];
  investigation?: string;
  retrieved?: Chunk[];
  assessment?: Assessment;
  draft?: Draft;
  review?: { action: string; reason?: string; reviewer: string };
  final?: { status: string; body?: string; refund_huf?: number; reason?: string };
}

export interface AuditEvent {
  id?: number;
  step: string;
  actor: 'agent' | 'tool' | 'human' | 'system';
  model?: string | null;
  prompt_version?: string | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  tokens_cached?: number | null;
  cost_usd?: number | string | null;
  latency_ms?: number | null;
  payload: Record<string, unknown>;
}

export interface CaseDetail {
  id: string;
  subject: string;
  body: string;
  status: CaseStatus;
  showcase: boolean;
  received_at: string;
  state: CaseState;
  events: AuditEvent[];
  final_response: string | null;
  decision: { action: string; reason?: string } | null;
}

export type RunMessage =
  | { type: 'node'; node: string; events: AuditEvent[]; state: CaseState }
  | { type: 'done'; status: CaseStatus }
  | { type: 'error'; message: string }
  | { type: 'info'; message: string };

@Injectable({ providedIn: 'root' })
export class Api {
  private readonly http = inject(HttpClient);

  cases() { return this.http.get<CaseSummary[]>('/api/cases'); }
  case(id: string) { return this.http.get<CaseDetail>(`/api/cases/${id}`); }
  create(subject: string, body: string) { return this.http.post<{ id: string }>('/api/cases', { subject, body }); }
  decide(id: string, d: { action: 'approve' | 'edit' | 'reject'; body?: string; reason?: string }) {
    return this.http.post<CaseState['final']>(`/api/cases/${id}/decision`, d);
  }
  chunk(id: string) { return this.http.get<Chunk>(`/api/chunks/${encodeURIComponent(id)}`); }
  metrics() { return this.http.get<Metrics>('/api/metrics'); }
  evals() { return this.http.get<EvalPayload>('/api/evals'); }
  health() { return this.http.get<{ ok: boolean; data_mode: string; models: Record<string, string> }>('/api/health'); }

  /** Server-sent events for an agent run; completes when the run pauses for review or fails. */
  run(id: string): Observable<RunMessage> {
    return new Observable((sub) => {
      const es = new EventSource(`/api/cases/${id}/run`);
      es.onmessage = (e) => {
        const msg = JSON.parse(e.data) as RunMessage;
        sub.next(msg);
        if (msg.type !== 'node') { es.close(); sub.complete(); }
      };
      es.onerror = () => { es.close(); sub.complete(); };
      return () => es.close();
    });
  }
}

export interface Metrics {
  per_step: { step: string; calls: number; avg_ms: number; p50_ms: number; p95_ms: number; cost_usd: number }[];
  per_model: { model: string; calls: number; tokens_in: number; tokens_cached: number; tokens_out: number; cost_usd: number }[];
  per_case: { avg_cost_usd: number | null; p50_ms: number | null; p95_ms: number | null; cases: number };
  outcomes: { status: string; n: number }[];
  reviews: { action: string; n: number }[];
}

export interface EvalSummary {
  metrics: Record<string, number>;
  thresholds?: Record<string, { min?: number; max?: number }>;
  cases: number;
  avg_cost_usd: number;
  p50_latency_s: number;
  p95_latency_s: number;
  models: Record<string, string>;
  at: string;
  passed: boolean;
}

export interface EvalResult {
  id: string;
  lang: string;
  error?: string;
  expected: { category: string[]; decision: string[]; refund_huf: number; injection: boolean };
  got: { category: string; decision: string; refund_huf: number; injection: boolean; flags: string[] };
  checks: Record<string, boolean>;
  groundedness: number;
  unsupported: string[];
  cost_usd: number;
  latency_s: number;
}

export interface EvalPayload { latest: { summary: EvalSummary; failures: string[]; results: EvalResult[] }; history: EvalSummary[] }
