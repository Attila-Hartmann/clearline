import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

type Part = { text: string } | { redaction: string; hint: string };

/** Renders text with PII placeholders ([PHONE], [CARD ****4821], …) as black redaction bars. */
@Component({
  selector: 'app-redacted-text',
  template: `
    @for (p of parts(); track $index) {
      @if ('redaction' in p) {
        <span class="bar" tabindex="0" [attr.aria-label]="'Redacted ' + p.hint" [title]="'Redacted before any model saw it: ' + p.hint">
          <span class="kind">{{ p.hint }}</span>
        </span>
      } @else {{{ p.text }}}
    }
  `,
  styles: `
    :host { white-space: pre-wrap; overflow-wrap: anywhere; }
    .bar {
      display: inline-block; vertical-align: -2px; height: 1.05em; min-width: 5.5ch; padding: 0 0.4ch;
      background: var(--ink); border-radius: 2px; color: transparent; font-size: 0.85em; line-height: 1.05em; cursor: help;
    }
    .bar:hover .kind, .bar:focus .kind { color: #fff; }
    .kind { font-weight: 600; letter-spacing: 0.02em; }
    @media (prefers-reduced-motion: no-preference) { .kind { transition: color 120ms ease; } }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RedactedText {
  readonly text = input.required<string>();

  protected readonly parts = computed<Part[]>(() => {
    const out: Part[] = [];
    const re = /\[(IBAN|ACCOUNT|EMAIL|PHONE|TAX_ID|CARD \*{4}\d{4})\]/g;
    let last = 0;
    for (const m of this.text().matchAll(re)) {
      if (m.index > last) out.push({ text: this.text().slice(last, m.index) });
      out.push({ redaction: m[0], hint: m[1].startsWith('CARD') ? `card ${m[1].slice(5)}` : m[1].toLowerCase().replace('_', ' ') });
      last = m.index + m[0].length;
    }
    if (last < this.text().length) out.push({ text: this.text().slice(last) });
    return out;
  });
}
