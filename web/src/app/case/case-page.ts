import { DecimalPipe, JsonPipe, PercentPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ButtonModule } from '@openng/optimus-ui/button';
import { DialogModule } from '@openng/optimus-ui/dialog';
import { TextareaModule } from '@openng/optimus-ui/textarea';

import { Api, AuditEvent, DEMO, CaseDetail, CaseState, Chunk } from '../api';
import { CATEGORY, DECISION, FLAG, STATUS, STEP, daysLeft, huf } from '../labels';
import { Letter } from './letter';
import { RedactedText } from './redacted-text';

type Mode = 'idle' | 'edit' | 'reject';

@Component({
  selector: 'app-case-page',
  imports: [RouterLink, FormsModule, DecimalPipe, PercentPipe, JsonPipe, ButtonModule, DialogModule, TextareaModule, Letter, RedactedText],
  templateUrl: './case-page.html',
  styleUrl: './case-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CasePage {
  private readonly api = inject(Api);
  private readonly destroyRef = inject(DestroyRef);

  readonly id = input.required<string>();

  protected readonly detail = signal<CaseDetail | null>(null);
  protected readonly state = signal<CaseState>({});
  protected readonly events = signal<AuditEvent[]>([]);
  protected readonly running = signal(false);
  protected readonly failure = signal<string | null>(null);
  protected readonly source = signal<Chunk | null>(null);

  protected readonly mode = signal<Mode>('idle');
  protected readonly deciding = signal(false);
  protected editedBody = '';
  protected rejectReason = '';

  protected readonly CATEGORY = CATEGORY;
  protected readonly DECISION = DECISION;
  protected readonly FLAG = FLAG;
  protected readonly STATUS = STATUS;
  protected readonly STEP = STEP;
  protected readonly huf = huf;
  protected readonly demo = DEMO;

  protected readonly status = computed(() => this.detail()?.status ?? 'new');
  protected readonly daysLeft = computed(() => daysLeft(this.state().due_date));
  protected readonly totals = computed(() => {
    const ev = this.events();
    return {
      cost: ev.reduce((s, e) => s + Number(e.cost_usd ?? 0), 0),
      ms: ev.reduce((s, e) => s + (e.latency_ms ?? 0), 0),
      tools: ev.filter((e) => e.actor === 'tool').length,
      llm: ev.filter((e) => e.model).length,
    };
  });
  protected readonly cited = computed(() => {
    const ids = new Set(this.state().assessment?.rules_applied ?? []);
    return (this.state().retrieved ?? []).filter((c) => ids.has(c.id));
  });

  constructor() {
    effect(() => this.load(this.id()));
  }

  private load(id: string) {
    this.api.case(id).subscribe((d) => {
      this.detail.set(d);
      this.state.set(d.state ?? {});
      this.events.set(d.events ?? []);
      if (d.status === 'new') this.start(id);
    });
  }

  private start(id: string) {
    this.running.set(true);
    const sub = this.api.run(id).subscribe({
      next: (msg) => {
        if (msg.type === 'node') {
          this.events.update((ev) => [...ev, ...msg.events]);
          this.state.update((s) => ({ ...s, ...msg.state }));
        } else if (msg.type === 'error') {
          this.failure.set(msg.message);
        }
      },
      complete: () => {
        this.running.set(false);
        this.api.case(id).subscribe((d) => this.detail.set(d));
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  protected beginEdit() {
    this.editedBody = this.state().draft?.body ?? '';
    this.mode.set('edit');
  }

  protected decide(action: 'approve' | 'edit' | 'reject') {
    this.deciding.set(true);
    const payload = action === 'edit' ? { action, body: this.editedBody } : action === 'reject' ? { action, reason: this.rejectReason } : { action };
    this.api.decide(this.id(), payload).subscribe({
      next: () => {
        this.deciding.set(false);
        this.mode.set('idle');
        this.load(this.id());
      },
      error: () => this.deciding.set(false),
    });
  }

  protected stepLabel(e: AuditEvent) {
    return STEP[e.step] ?? e.step;
  }

  protected detailFor(e: AuditEvent): unknown {
    const { latency_ms: _l, ...rest } = e.payload as Record<string, unknown>;
    return rest;
  }

  protected cost(e: AuditEvent) {
    const c = Number(e.cost_usd ?? 0);
    return c ? `$${c.toFixed(4)}` : '';
  }
}
