# Demo video script

2:30 screen recording of Clearline for recruiters and hiring managers at Hungarian banks and consultancies. One take, local compose stack, synthetic Danubia Bank data only.

| Time | Screen | Voice-over |
|---|---|---|
| 0:00 | Inbox at `http://localhost:4200`. Show the "review" filter and the counts, point at the "days to the statutory deadline" pill on the urgent cases. | "This is Clearline. A customer email comes into a bank complaint queue. Each case already has its statutory deadline. Fifteen business days for payment services, thirty days for the rest, and Hungarian holidays are counted in. The deadline is computed in code, not by the model." |
| 0:20 | Open a showcase case. Section "Customer message" shows the redacted text. Hover a redaction bar. | "The personal data is redacted before any model sees the text. Card and account numbers, phone numbers, emails, tax IDs. Hover a bar and you see what was removed." |
| 0:35 | Section "What the agent did". Let the steps show: model calls, lookups, seconds, cost. Expand one step. | "Here is the run in order. Triage, then facts, then read only lookups into core banking, then policy retrieval, then the assessment. Each step has its model, its latency and its cost." |
| 0:55 | "Policy and law it retrieved" list. Click one source to open the dialog, close it. | "It retrieved policy and Hungarian regulation from Postgres, using hybrid search. The source opens here so the reviewer can check it." |
| 1:05 | "Agent's proposal" panel: decision and exact refund, then the letter. Click a citation in the letter to open the source. | "The proposal is uphold, partial or reject, with the exact refund to the forint. The letter cites each source. Click a citation and you get the text behind it. A refund above two hundred thousand forint forces escalation." |
| 1:20 | Back to inbox. "Try it", choose the sample "Fee complaint with a prompt injection", submit. On the case page, show the injected sentence and the flag, then the proposal with the same small refund. | "Now I submit my own complaint. This one has a line inside it that tries to instruct the AI to refund a million forint. The screen step flags it. The agent treated it as data. The refund for the fee is unchanged. The injection had no effect." |
| 1:45 | On "Agent's proposal" and letter: click "Edit letter", change one line, click "Send edited letter". Show the outcome line "Sent to the customer" and, if visible, the edited note. Mention "Reject draft" needs a reason in the audit trail. | "Nothing is sent without a person. I can approve, edit or reject. If I edit, the reviewer change is noted. If I reject, I have to write why, and that goes into the audit trail." |
| 1:58 | Jaeger at `http://localhost:16686`. Open the case trace. Show agent step spans, model call spans with tokens and cost, and MCP tool calls into core-banking inside the same trace. | "Every case is one OpenTelemetry trace. Each agent step is a span. Each model call has its token usage and cost. The core banking lookups come in here too, because the tool calls are on MCP and the trace context is passed along. The same OTLP output can go to Langfuse or Azure Monitor." |
| 2:10 | Quality page. Show the metric table and the three remaining misses. | "Quality is a CI gate. Every change runs the golden set of thirty one complaints and the build fails if a metric drops below its threshold. The first run failed the gate. The three misses that remain are kept visible here. I did not tune them away." |
| 2:20 | Operations page. Point at cost per case, about three thousandths of a dollar, and about sixteen seconds per case. | "Cost and latency per case. About zero point zero zero three dollars and sixteen seconds per case on deepseek chat. That model is used on synthetic data only. With real customer data the app refuses any non-EU endpoint. That is one of the architecture decisions." |
| 2:28 | End card: GitHub repo link, then a short list of what production would add. | "The repo is open source. Production would add authentication and per tool authorization on the MCP server, single sign on with roles, four eyes approval, better redaction for names, a DPIA, and integration with the real complaint register. Thanks for watching." |

## Recording checklist

- Resolution 1920x1080, browser zoom 125%, one window, no devtools.
- Reset the demo database, then run the seed so the ten showcase complaints are pre-run and approved cases look settled.
- Pre-run the showcase cases once so the trace and the letter are already there when you start.
- Hide bookmarks bar, close other tabs and notifications, quiet phone.
- Test the mic; use a headset; speak a little slower than feels natural.
- Keep the whole take under 2:45; trim pauses, not content.
- Add captions in plain English, and keep the on screen names as they are.
- Export as MP4.
