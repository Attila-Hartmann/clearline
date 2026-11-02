"""Tiered LLM access over OpenAI-compatible endpoints, with per-call cost accounting.

Two tiers: `worker` (cheap, high volume: triage, extraction, screening) and `drafter`
(strong: assessment, letters, judging). Every call returns its usage so the agent can
write it to the audit log.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from clearline.config import settings
from clearline.tracing import CAPTURE_CONTENT, tracer

TierName = Literal["worker", "drafter"]

# USD per 1M tokens: (input, cached input, output). Unknown models cost 0 and are flagged in the UI.
PRICES: dict[str, tuple[float, float, float]] = {
    "deepseek-chat": (0.27, 0.07, 1.10),
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
    "gpt-4.1": (2.00, 0.50, 8.00),
    "claude-sonnet-4-5": (3.00, 0.30, 15.00),
    "claude-haiku-4-5": (1.00, 0.10, 5.00),
}


@dataclass
class Usage:
    tier: str
    model: str
    tokens_in: int = 0
    tokens_cached: int = 0
    tokens_out: int = 0
    latency_ms: int = 0

    @property
    def cost_usd(self) -> float:
        p_in, p_cached, p_out = PRICES.get(self.model, (0.0, 0.0, 0.0))
        fresh = self.tokens_in - self.tokens_cached
        return (fresh * p_in + self.tokens_cached * p_cached + self.tokens_out * p_out) / 1_000_000


@dataclass
class Reply:
    content: str
    usage: Usage
    tool_calls: list[Any] = field(default_factory=list)
    message: Any = None


_clients: dict[str, OpenAI] = {}


def _client(tier: TierName) -> tuple[OpenAI, str]:
    t = settings().tier(tier)
    if tier not in _clients:
        _clients[tier] = OpenAI(api_key=t.api_key, base_url=t.base_url, timeout=90, max_retries=2)
    return _clients[tier], t.model


def chat(tier: TierName, messages: list[dict], *, json_mode: bool = False, tools: list[dict] | None = None,
         temperature: float = 0.0) -> Reply:
    client, model = _client(tier)
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if tools:
        kwargs["tools"] = tools
    # OTel GenAI semantic conventions, so Langfuse / Azure Monitor render this as a model generation with usage.
    with tracer.start_as_current_span(f"chat {model}", attributes={
        "gen_ai.operation.name": "chat", "gen_ai.request.model": model, "server.address": client.base_url.host,
        "clearline.tier": tier, "gen_ai.request.temperature": temperature}) as span:
        t0 = time.perf_counter()
        resp = client.chat.completions.create(**kwargs)
        u = resp.usage
        cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        usage = Usage(tier, model, u.prompt_tokens if u else 0, cached, u.completion_tokens if u else 0,
                      int((time.perf_counter() - t0) * 1000))
        msg = resp.choices[0].message
        span.set_attributes({"gen_ai.response.model": resp.model, "gen_ai.usage.input_tokens": usage.tokens_in,
                             "gen_ai.usage.output_tokens": usage.tokens_out, "gen_ai.usage.cache_read.input_tokens": cached,
                             "clearline.cost_usd": usage.cost_usd})
        if CAPTURE_CONTENT:
            span.set_attribute("gen_ai.input.messages", json.dumps(messages, ensure_ascii=False, default=str))
            span.set_attribute("gen_ai.output.messages", json.dumps([msg.model_dump(exclude_none=True)], ensure_ascii=False))
    return Reply(msg.content or "", usage, list(msg.tool_calls or []), msg)


def structured[T: BaseModel](tier: TierName, system: str, user: str, schema: type[T]) -> tuple[T, Usage]:
    """JSON-mode call validated against a Pydantic schema; one repair retry on invalid output."""
    messages = [
        {"role": "system", "content": f"{system}\n\nRespond with JSON only, matching this JSON schema:\n"
                                      f"{json.dumps(schema.model_json_schema())}"},
        {"role": "user", "content": user},
    ]
    reply = chat(tier, messages, json_mode=True)
    try:
        return schema.model_validate_json(reply.content), reply.usage
    except ValidationError as e:
        messages += [{"role": "assistant", "content": reply.content},
                     {"role": "user", "content": f"Invalid JSON for the schema: {e.errors()[:3]}. Return corrected JSON."}]
        retry = chat(tier, messages, json_mode=True)
        total = reply.usage
        total.tokens_in += retry.usage.tokens_in
        total.tokens_out += retry.usage.tokens_out
        total.latency_ms += retry.usage.latency_ms
        return schema.model_validate_json(retry.content), total
