import { DecimalPipe, PercentPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, of } from 'rxjs';

import { Api } from '../api';
import { CATEGORY, DECISION, huf } from '../labels';

const METRICS: { key: string; label: string; explain: string }[] = [
  { key: 'decision_acc', label: 'Right decision', explain: 'Uphold, partial, reject or escalate matches the expected outcome.' },
  { key: 'refund_exact', label: 'Exact refund amount', explain: 'Money is not approximately right. The refund must match to the forint.' },
  { key: 'category_acc', label: 'Correct triage', explain: 'The complaint is put in the right category.' },
  { key: 'payment_flag_acc', label: 'Correct deadline type', explain: 'Payment-service complaints get 15 business days, others 30 days.' },
  { key: 'retrieval_recall', label: 'Right policy retrieved', explain: 'Hybrid search finds at least one policy the decision depends on.' },
  { key: 'citation_support', label: 'Letter cites the right policy', explain: 'The reply cites a policy the decision depends on.' },
  { key: 'groundedness', label: 'Grounded letter', explain: 'An LLM judge checks every claim in the letter against facts and cited policy.' },
  { key: 'injection_recall', label: 'Injection attempts caught', explain: 'Messages that try to instruct the AI are flagged.' },
  { key: 'injection_resist', label: 'Injection had no effect', explain: 'Flagged attempts did not change the refund.' },
  { key: 'injection_fpr', label: 'False injection alarms', explain: 'Ordinary complaints wrongly flagged. Lower is better.' },
];

@Component({
  selector: 'app-quality',
  imports: [PercentPipe, DecimalPipe],
  templateUrl: './quality.html',
  styleUrl: './quality.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Quality {
  private readonly data = toSignal(inject(Api).evals().pipe(catchError(() => of(null))));
  protected readonly report = computed(() => this.data()?.latest ?? null);
  protected readonly history = computed(() => this.data()?.history ?? []);
  protected readonly rows = computed(() => {
    const s = this.report()?.summary;
    if (!s) return [];
    return METRICS.map((m) => {
      const value = s.metrics[m.key];
      const t = s.thresholds?.[m.key] ?? {};
      const lowerIsBetter = t.max !== undefined;
      const pass = lowerIsBetter ? value <= (t.max ?? 1) : value >= (t.min ?? 0);
      return { ...m, value, threshold: lowerIsBetter ? t.max : t.min, lowerIsBetter, pass };
    });
  });
  protected readonly misses = computed(() => (this.report()?.results ?? []).filter((r) => r.error || Object.values(r.checks ?? {}).some((v) => !v)));
  protected readonly CATEGORY = CATEGORY;
  protected readonly DECISION = DECISION;
  protected readonly huf = huf;

  protected failed(checks: Record<string, boolean>) {
    return Object.entries(checks).filter(([, v]) => !v).map(([k]) => METRICS.find((m) => m.key === k)?.label ?? k);
  }
}
