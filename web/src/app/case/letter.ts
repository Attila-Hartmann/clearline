import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { Chunk, Draft } from '../api';

type Seg = { text: string } | { marker: number };

/** The reply set as a letter: serif body, citation markers that point to margin notes with the policy source. */
@Component({
  selector: 'app-letter',
  template: `
    <div class="wrap">
    <article class="sheet" [attr.aria-label]="'Reply letter: ' + draft().subject">
      <p class="re"><span class="subtle">Subject</span> {{ draft().subject }}</p>
      @for (para of paragraphs(); track $index) {
        <p>
          @for (s of para; track $index) {
            @if ('marker' in s) {
              <button type="button" class="cite" (click)="emitFor(s.marker)" [disabled]="!chunkFor(s.marker)"
                      [attr.aria-label]="'Source ' + s.marker + ': ' + (chunkFor(s.marker)?.section ?? 'unknown')">{{ s.marker }}</button>
            } @else {{{ s.text }}}
          }
        </p>
      }
    </article>
    <aside class="margin" aria-label="Sources cited">
      @for (c of draft().citations; track c.marker) {
        @if (byId().get(c.chunk_id); as ch) {
          <button type="button" class="note" (click)="open.emit(ch)">
            <span class="n">{{ c.marker }}</span>
            <span><strong>{{ ch.section }}</strong><br /><span class="subtle">{{ ch.title }}</span></span>
          </button>
        }
      }
    </aside>
    </div>
  `,
  styles: `
    :host { display: block; container-type: inline-size; }
    .wrap { display: grid; grid-template-columns: minmax(0, 1fr) 190px; gap: 16px; }
    .sheet {
      background: var(--paper); border: 1px solid var(--rule); border-radius: 4px; padding: 32px 36px;
      font-family: var(--serif); font-size: 1.02rem; line-height: 1.65; box-shadow: 0 1px 0 var(--rule), 0 12px 24px -18px rgba(20, 33, 43, 0.35);
    }
    .sheet p { margin: 0 0 0.9em; max-width: 68ch; white-space: pre-wrap; }
    .sheet p.re { font-family: var(--sans); font-size: 0.9rem; font-weight: 600; padding-bottom: 12px; border-bottom: 1px solid var(--rule); margin-bottom: 20px; }
    .cite {
      font: 600 0.68rem/1 var(--sans); vertical-align: super; margin: 0 1px; padding: 2px 5px; border-radius: 3px;
      background: var(--danube-tint); color: var(--danube-2); border: 0; cursor: pointer;
    }
    .margin { display: flex; flex-direction: column; gap: 8px; }
    .note {
      display: flex; gap: 8px; text-align: left; font: inherit; font-size: 0.82rem; line-height: 1.35; padding: 8px;
      background: transparent; border: 0; border-left: 2px solid var(--danube); cursor: pointer; color: var(--ink);
    }
    .note:hover { background: var(--danube-tint); }
    .n { font-weight: 700; color: var(--danube); }
    @container (max-width: 640px) { .wrap { grid-template-columns: 1fr; } .sheet { padding: 24px; } .margin { flex-direction: row; flex-wrap: wrap; } }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Letter {
  readonly draft = input.required<Draft>();
  readonly sources = input<Chunk[]>([]);
  readonly open = output<Chunk>();

  protected readonly byId = computed(() => new Map(this.sources().map((c) => [c.id, c])));
  private readonly markers = computed(() => new Map(this.draft().citations.map((c) => [c.marker, c.chunk_id])));

  protected readonly paragraphs = computed<Seg[][]>(() =>
    this.draft().body.split(/\n{2,}/).map((p) =>
      p.split(/\[(\d+)\]/).map((part, i) => (i % 2 ? { marker: Number(part) } : { text: part })).filter((s) => !('text' in s) || s.text),
    ),
  );

  protected emitFor(marker: number) {
    const c = this.chunkFor(marker);
    if (c) this.open.emit(c);
  }

  protected chunkFor(marker: number): Chunk | undefined {
    const id = this.markers().get(marker);
    return id ? this.byId().get(id) : undefined;
  }
}
