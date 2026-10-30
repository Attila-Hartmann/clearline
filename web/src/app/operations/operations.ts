import { DecimalPipe, PercentPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, of } from 'rxjs';

import { Api } from '../api';
import { STEP } from '../labels';

@Component({
  selector: 'app-operations',
  imports: [DecimalPipe, PercentPipe],
  template: `
    <div class="page">
      <h1>Operations</h1>
      <p class="muted lede">Live numbers from the audit log: what each case costs, where the time goes, and how often people overrule the agent.</p>
      @if (m(); as m) {
        <dl class="stats panel">
          <div><dt>Cases processed</dt><dd>{{ m.per_case.cases }}</dd></div>
          <div><dt>Model cost per case</dt><dd>{{ '$' + ((m.per_case.avg_cost_usd ?? 0) | number: '1.4-4') }}</dd></div>
          <div><dt>Agent time per case, median</dt><dd>{{ ((m.per_case.p50_ms ?? 0) / 1000) | number: '1.1-1' }} s</dd></div>
          <div><dt>95th percentile</dt><dd>{{ ((m.per_case.p95_ms ?? 0) / 1000) | number: '1.1-1' }} s</dd></div>
          <div><dt>Drafts changed by a person</dt><dd>{{ override() | percent }}</dd></div>
        </dl>

        <div class="two">
          <section class="panel">
            <h2>Where the time goes</h2>
            <table>
              <thead><tr><th scope="col">Step</th><th scope="col">Calls</th><th scope="col">Median</th><th scope="col">p95</th><th scope="col">Cost</th></tr></thead>
              <tbody>
                @for (s of m.per_step; track s.step) {
                  <tr>
                    <th scope="row">{{ STEP[s.step] ?? s.step }}</th>
                    <td>{{ s.calls }}</td><td>{{ s.p50_ms }} ms</td><td>{{ s.p95_ms }} ms</td>
                    <td>{{ s.cost_usd ? '$' + (s.cost_usd | number: '1.4-4') : '' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </section>
          <section class="panel">
            <h2>Models</h2>
            <table>
              <thead><tr><th scope="col">Model</th><th scope="col">Calls</th><th scope="col">Tokens in</th><th scope="col">Cached</th><th scope="col">Tokens out</th><th scope="col">Cost</th></tr></thead>
              <tbody>
                @for (x of m.per_model; track x.model) {
                  <tr>
                    <th scope="row">{{ x.model }}</th><td>{{ x.calls }}</td><td>{{ x.tokens_in | number }}</td>
                    <td>{{ x.tokens_cached / (x.tokens_in || 1) | percent }}</td><td>{{ x.tokens_out | number }}</td>
                    <td>{{ '$' + (x.cost_usd | number: '1.4-4') }}</td>
                  </tr>
                }
              </tbody>
            </table>
            <h2 class="gap">Reviewer decisions</h2>
            <ul class="plain">
              @for (r of m.reviews; track r.action) { <li><strong>{{ r.n }}</strong> {{ label[r.action] ?? r.action }}</li> }
              @empty { <li class="muted">No reviews yet.</li> }
            </ul>
          </section>
        </div>
      } @else if (m() === null) {
        <p class="panel empty">The API is not reachable.</p>
      }
    </div>
  `,
  styles: `
    .lede { max-width: 70ch; margin: 8px 0 24px; }
    .stats { display: flex; flex-wrap: wrap; gap: 40px; padding: 20px; margin: 0 0 16px; }
    .stats dt { color: var(--ink-3); font-size: 0.82rem; }
    .stats dd { margin: 0; font-size: 1.5rem; font-weight: 700; }
    .two { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; align-items: start; }
    section { padding: 20px; overflow-x: auto; }
    h2 { margin-bottom: 12px; }
    .gap { margin-top: 24px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th, td { padding: 8px 10px; border-bottom: 1px solid var(--mist); text-align: right; white-space: nowrap; }
    th[scope='row'], thead th:first-child { text-align: left; font-weight: 600; }
    thead th { color: var(--ink-3); font-weight: 600; font-size: 0.8rem; }
    .plain { list-style: none; padding: 0; margin: 0; display: flex; gap: 24px; }
    .empty { padding: 24px; }
    @media (max-width: 1000px) { .two { grid-template-columns: 1fr; } }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Operations {
  protected readonly m = toSignal(inject(Api).metrics().pipe(catchError(() => of(null))));
  protected readonly STEP = STEP;
  protected readonly label: Record<string, string> = { approve: 'approved as drafted', edit: 'edited before sending', reject: 'rejected' };
  protected readonly override = computed(() => {
    const r = this.m()?.reviews ?? [];
    const total = r.reduce((s, x) => s + x.n, 0);
    return total ? r.filter((x) => x.action !== 'approve').reduce((s, x) => s + x.n, 0) / total : 0;
  });
}
