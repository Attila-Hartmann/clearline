import { today } from './api';

// Plain-language names for what the system does; the UI never shows internal identifiers unexplained.

export const CATEGORY: Record<string, string> = {
  unauthorised_transaction: 'Unauthorised payment',
  card_dispute: 'Card dispute',
  duplicate_charge: 'Duplicate charge',
  fee_dispute: 'Fee dispute',
  atm_cash: 'ATM cash not dispensed',
  loan_servicing: 'Loan servicing',
  account_closure: 'Account closure',
  service_quality: 'Service quality',
  data_protection: 'Data protection request',
  other: 'Other',
};

export const DECISION: Record<string, string> = {
  uphold: 'Uphold',
  partial: 'Partially uphold',
  reject: 'Reject',
  escalate: 'Escalate to specialist',
};

export const STEP: Record<string, string> = {
  redact_pii: 'Redacted personal data',
  screen_injection: 'Screened for prompt injection',
  triage: 'Triaged the complaint',
  extract: 'Extracted the facts',
  'investigate.llm': 'Planned the next lookup',
  'tool.get_customer': 'Looked up the customer',
  'tool.find_customer_by_card': 'Matched the card',
  'tool.list_transactions': 'Searched transactions',
  'tool.get_fee_rule': 'Checked the fee rule',
  retrieve: 'Retrieved policy and regulation',
  assess: 'Proposed a decision',
  draft: 'Drafted the reply',
  human_review: 'Human decision',
  finalize: 'Closed the case',
  error: 'Run failed',
};

export const FLAG: Record<string, { label: string; tone: 'danger' | 'warn' | 'info' }> = {
  prompt_injection_attempt: { label: 'Injection attempt', tone: 'danger' },
  vulnerable_customer: { label: 'Vulnerable customer', tone: 'warn' },
  high_value: { label: 'High value', tone: 'warn' },
  fraud_suspected: { label: 'Fraud suspected', tone: 'danger' },
  missing_information: { label: 'Missing information', tone: 'info' },
  deadline_risk: { label: 'Deadline risk', tone: 'warn' },
};

export const STATUS: Record<string, { label: string; css: string }> = {
  new: { label: 'Queued', css: 'new' },
  processing: { label: 'Agent working', css: 'processing' },
  awaiting_review: { label: 'Needs your review', css: 'review' },
  approved: { label: 'Sent', css: 'approved' },
  rejected: { label: 'Draft rejected', css: 'rejected' },
  failed: { label: 'Failed', css: 'failed' },
};

export function huf(n: number | null | undefined): string {
  return n == null ? '–' : `${new Intl.NumberFormat('hu-HU').format(n)} Ft`;
}

export function daysLeft(due: string | null | undefined, now = today()): number | null {
  if (!due) return null;
  const ms = new Date(due + 'T23:59:59').getTime() - now.getTime();
  return Math.ceil(ms / 86_400_000);
}
