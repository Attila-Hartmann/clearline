import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-about',
  imports: [RouterLink],
  templateUrl: './about.html',
  styleUrl: './about.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class About {
  protected readonly pipeline = [
    { name: 'Guard', what: 'Redacts personal data with deterministic rules, then screens the message for prompt injection.', who: 'code + small model' },
    { name: 'Triage', what: 'Category, priority, vulnerability signals and the statutory deadline (15 business days or 30 days).', who: 'small model' },
    { name: 'Extract', what: 'Customer ID, amounts, dates and what the customer asks for.', who: 'small model' },
    { name: 'Investigate', what: 'Calls read-only core-banking tools: customer profile, transactions, fee rules. It can look, never move money.', who: 'small model + tools' },
    { name: 'Retrieve', what: 'Hybrid search over policy and Hungarian regulation: pgvector for meaning, Postgres full-text for exact terms.', who: 'code' },
    { name: 'Assess', what: 'Proposes uphold, partial, reject or escalate with the exact refund. Hard rules (escalation limits, valid citations) are enforced in code.', who: 'strong model + code' },
    { name: 'Draft', what: "Writes the reply in the customer's language, citing the policies it relies on.", who: 'strong model' },
    { name: 'Human review', what: 'The run pauses. A person approves, edits or rejects; every decision lands in the audit trail.', who: 'person' },
  ];
}
