# ADR-003: Customer data never goes to a non-EU model endpoint

**Status:** accepted

## Context
A bank's complaint text contains personal and financial data (GDPR, banking secrecy). Model choice is driven by cost and
quality, and the cheapest capable models are not always hosted in the EU.

## Decision
- Every model tier (`worker`, `drafter`) declares its region (`eu` / `non-eu`) in configuration.
- `DATA_MODE=live` (anything a real person may type) refuses to start if any tier is non-EU.
- `DATA_MODE=synthetic` (development, evals, the public demo's fictional bank) may use any endpoint.
- PII is redacted with deterministic rules **before** any model call; raw text is stored but never sent to a model,
  and visitor-submitted text is only ever served back in redacted form.
- Embeddings are computed locally.

## Consequences
- Cost/quality comparisons with non-EU models are done on synthetic data only.
- Moving to production means pointing the tiers at EU deployments (e.g. Azure OpenAI in an EU region) and flipping
  `DATA_MODE`; the code path is the same.
- Regex redaction misses free-text PII such as names in prose; the model sees those. A production deployment would add
  an NER-based redactor and a DPIA.
