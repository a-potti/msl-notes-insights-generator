"""A thin, instrumented wrapper around the Anthropic Messages API.

Built in Chapter 1. Every LLM call in InsightHub goes through here, which is what
makes Chapter 6's tracing a ten-line change instead of a rewrite.

Design notes:
  * Nothing clever. If you cannot read this file in two minutes, it is too clever.
  * Usage, latency and cost are captured on every call, always. You cannot optimise
    what you never measured, and retrofitting measurement is miserable.
  * Retries handle the two errors you will actually hit (overloaded, rate limit) and
    nothing else. Silently retrying a 400 hides your own bugs.
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

import anthropic

from .config import MODEL_WORK, cost_usd

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


# Opus 5, Sonnet 5, Fable 5, Mythos 5 and Opus 4.7/4.8 reject temperature/top_p
# outright (400) in favour of adaptive thinking + effort. Gate here so callers
# can pass temperature=0.0 uniformly across model tiers without special-casing.
_NO_SAMPLING_PREFIXES = (
    "claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-mythos-5",
    "claude-opus-4-7", "claude-opus-4-8",
)


def _accepts_sampling(model: str) -> bool:
    return not model.startswith(_NO_SAMPLING_PREFIXES)


@dataclass
class LLMResult:
    """Everything you need to debug, price or replay a single call."""
    text: str
    blocks: list[Any]
    model: str
    stop_reason: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    latency_s: float
    cost_usd: float
    attempts: int = 1
    meta: dict = field(default_factory=dict)

    @property
    def total_input(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    def tool_uses(self) -> list[Any]:
        return [b for b in self.blocks if getattr(b, "type", None) == "tool_use"]

    def summary(self) -> str:
        return (f"{self.model} | in {self.total_input:,} "
                f"(cache r/w {self.cache_read_tokens:,}/{self.cache_write_tokens:,}) "
                f"| out {self.output_tokens:,} | {self.latency_s:.2f}s "
                f"| ${self.cost_usd:.5f} | stop={self.stop_reason}")


# Hook point. Chapter 6 replaces this with a trace writer.
_observers: list[Callable[[LLMResult], None]] = []


def add_observer(fn: Callable[[LLMResult], None]) -> None:
    _observers.append(fn)


RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIStatusError,
    anthropic.APIConnectionError,
)


def call(
    *,
    messages: list[dict],
    system: str | list[dict] | None = None,
    model: str = MODEL_WORK,
    max_tokens: int = 2048,
    temperature: float | None = None,
    top_p: float | None = None,
    tools: list[dict] | None = None,
    tool_choice: dict | None = None,
    thinking: dict | None = None,
    stop_sequences: list[str] | None = None,
    max_retries: int = 4,
    meta: dict | None = None,
) -> LLMResult:
    """One Messages API call, instrumented.

    `system` may be a plain string or a list of content blocks (needed for
    cache_control breakpoints — see Chapter 1 §1.7).
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system is not None:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    if thinking:
        kwargs["thinking"] = thinking
    if stop_sequences:
        kwargs["stop_sequences"] = stop_sequences
    # anthropic>=1.0 removed temperature/top_p as direct kwargs — pass them
    # through extra_body instead, and only for models that still accept them.
    extra_body: dict[str, Any] = {}
    if _accepts_sampling(model):
        if temperature is not None:
            extra_body["temperature"] = temperature
        if top_p is not None:
            extra_body["top_p"] = top_p
    if extra_body:
        kwargs["extra_body"] = extra_body

    t0 = time.perf_counter()
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client().messages.create(**kwargs)
            break
        except RETRYABLE as exc:  # noqa: PERF203
            status = getattr(exc, "status_code", None)
            # 4xx other than 429 is our bug — surface it immediately.
            if status is not None and 400 <= status < 500 and status != 429:
                raise
            last_exc = exc
            if attempt == max_retries:
                raise
            sleep = min(30.0, (2 ** attempt) + random.random())
            time.sleep(sleep)
    else:  # pragma: no cover
        raise last_exc  # type: ignore[misc]

    latency = time.perf_counter() - t0
    u = resp.usage
    cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")

    result = LLMResult(
        text=text,
        blocks=list(resp.content),
        model=resp.model,
        stop_reason=resp.stop_reason,
        input_tokens=u.input_tokens,
        output_tokens=u.output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        latency_s=latency,
        cost_usd=cost_usd(model, u.input_tokens, u.output_tokens, cache_read, cache_write),
        attempts=attempt,
        meta=meta or {},
    )
    for obs in _observers:
        try:
            obs(result)
        except Exception:  # observers must never break the call path
            pass
    return result


def count_tokens(
    *,
    messages: list[dict],
    system: str | list[dict] | None = None,
    model: str = MODEL_WORK,
    tools: list[dict] | None = None,
) -> int:
    """Exact-ish token count without paying for generation. Free endpoint."""
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if system is not None:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
    return client().messages.count_tokens(**kwargs).input_tokens


def tool_result_block(tool_use_id: str, content: Any, is_error: bool = False) -> dict:
    """Helper for the agent loop in Chapter 4."""
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False, default=str)
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    return block


def batched(seq: Iterable, n: int):
    """Chunk an iterable — used for concurrency fan-out in Chapter 4."""
    buf = []
    for item in seq:
        buf.append(item)
        if len(buf) == n:
            yield buf
            buf = []
    if buf:
        yield buf
