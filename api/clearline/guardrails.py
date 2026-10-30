"""Input guardrails: PII redaction before any LLM call, and prompt-injection screening.

Redaction is deterministic (regex) so it is testable and never depends on a model. Internal customer
IDs (C-1234) and card last-4 digits are kept: the agent needs them to look facts up.
"""

import re

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[0-9A-Z]{4}){3,7}(?: ?[0-9A-Z]{1,4})?\b")),
    ("ACCOUNT", re.compile(r"\b\d{8}-\d{8}(?:-\d{8})?\b")),  # before CARD: 8-8 digit groups also look like a card
    ("CARD", re.compile(r"\b(?:\d[ -]?){12,15}(\d{4})\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("PHONE", re.compile(r"(?:\+36|\b06)[ -/]?\(?\d{1,2}\)?[ -/]?\d{3}[ -]?\d{3,4}\b")),
    ("TAX_ID", re.compile(r"\b8\d{9}\b")),
]


def redact(text: str) -> tuple[str, list[dict]]:
    """Return (redacted text, found spans). Card numbers keep their last 4 digits."""
    spans: list[dict] = []
    for kind, pat in PII_PATTERNS:
        def _sub(m: re.Match[str], kind: str = kind) -> str:
            spans.append({"type": kind, "value_hint": m.group(0)[-4:]})
            return f"[CARD ****{m.group(1)}]" if kind == "CARD" else f"[{kind}]"
        text = pat.sub(_sub, text)
    return text, spans


INJECTION_HINTS = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)|disregard (the|your) (rules|instructions)"
    r"|system prompt|you are now|act as (the|an?) |developer mode|\bSYSTEM:|\bASSISTANT:"
    r"|approve (a|the) refund of|felejtsd el|hagyd figyelmen kívül|az eddigi utasítás|új utasítás"
    r"|te most egy|rendszerüzenet",
    re.I,
)


def injection_heuristic(text: str) -> list[str]:
    return sorted({m.group(0) for m in INJECTION_HINTS.finditer(text)})


def wrap_untrusted(text: str) -> str:
    """Delimit customer text so prompts can say: everything inside is data, not instructions."""
    return f"<customer_message>\n{text.replace('</customer_message>', '')}\n</customer_message>"
