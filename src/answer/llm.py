"""Async OpenRouter wrapper for answer generation.

Sibling of :mod:`src.contextual.providers.openrouter` (which is sync,
batch-oriented for the day-16 indexer). This module is async and
single-call oriented: one user question → one LLM call inside a
FastAPI request handler.

Why a separate module
---------------------
* The indexer wants synchronous batch behaviour with token-cost
  accounting and prompt caching against a 5-min TTL.
* The endpoint wants async, low-latency, no caching needed (each
  user question is unique).
Sharing the same class would entangle two unrelated lifecycles. A
thin module per use-case keeps each one obvious.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Result of one LLM completion call."""

    text: str
    """The generated answer text."""

    tokens_in: int
    """Input tokens consumed."""

    tokens_out: int
    """Output tokens generated."""

    model: str
    """OpenRouter model identifier that produced the result."""


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """One delta from the streaming LLM response.

    Most chunks carry only ``delta``; the *final* chunk (fired after the
    upstream provider sends ``finish_reason``) carries the usage info
    and ``finish_reason`` instead — its ``delta`` is empty. Consumers
    that just care about the text concatenate ``delta`` across all
    chunks; consumers that care about totals look at the last one.
    """

    delta: str
    """Incremental text fragment. Empty on the terminal usage chunk."""

    finish_reason: str | None = None
    """Set on the terminal chunk only (``"stop"`` / ``"length"`` / ...)."""

    tokens_in: int | None = None
    """Set on the terminal chunk only."""

    tokens_out: int | None = None
    """Set on the terminal chunk only."""

    model: str | None = None
    """Set on the terminal chunk only — matches :class:`LLMResult.model`."""


class AsyncOpenRouterLLM:
    """Async OpenRouter client for answer generation.

    One instance per FastAPI app — the underlying ``AsyncOpenAI``
    client maintains its own connection pool. Thread-safe and
    coroutine-safe per the SDK's docs.

    Parameters
    ----------
    api_key:
        OpenRouter API key (``sk-or-v1-...``).
    default_model:
        Fallback model when the request doesn't override. Default
        ``anthropic/claude-haiku-4.5`` per :data:`Settings.answer_llm_model`.
    base_url:
        OpenAI-compatible endpoint. Defaults to OpenRouter's.
    client_factory:
        Test injection point. Production leaves this ``None``.
    extra_headers:
        OpenRouter recommends ``HTTP-Referer`` and ``X-Title`` so the
        request is attributed correctly on their dashboard.
    """

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str = "deepseek/deepseek-v4-flash",
        base_url: str = DEFAULT_OPENROUTER_BASE_URL,
        client_factory: Callable[..., Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenRouter API key is empty; set OPENROUTER_API_KEY.")
        self._api_key = api_key
        self._default_model = default_model
        self._base_url = base_url
        self._extra_headers = extra_headers or {
            "HTTP-Referer": "https://github.com/toneruseman/Dharma-RAG",
            "X-Title": "Dharma-RAG Answer Generation",
        }
        self._client_factory = client_factory or _default_async_client_factory
        self._client: Any = None

    @property
    def default_model(self) -> str:
        return self._default_model

    async def complete(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult:
        """Run a single chat-completion call and return the answer.

        ``temperature=0.2`` chosen for grounded RAG: low enough to
        keep the model honest about what's in the sources, high
        enough to avoid stilted phrasing on RU output.
        """
        client = self._ensure_client()
        chosen_model = model or self._default_model

        response = await client.chat.completions.create(
            model=chosen_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = _extract_text(response)
        usage = getattr(response, "usage", None)
        tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        tokens_out = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        return LLMResult(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=f"openrouter/{chosen_model}",
        )

    async def stream(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> AsyncIterator[StreamChunk]:
        """Stream the chat-completion call as :class:`StreamChunk` deltas.

        Pass-through over ``chat.completions.create(stream=True, ...)``
        plus ``stream_options={"include_usage": True}`` so OpenRouter
        forwards the final ``usage`` block to upstream providers and we
        can populate token counts on the terminal chunk.

        Yields one chunk per upstream delta. Yields a final chunk with
        ``delta=""`` and the usage / model / finish_reason populated.
        Empty deltas (keep-alive heartbeats, leading whitespace stripping)
        are dropped — consumers don't need to filter.
        """
        client = self._ensure_client()
        chosen_model = model or self._default_model

        stream = await client.chat.completions.create(
            model=chosen_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            stream_options={"include_usage": True},
        )

        finish_reason: str | None = None
        tokens_in: int | None = None
        tokens_out: int | None = None

        async for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if choices:
                choice = choices[0]
                delta_obj = getattr(choice, "delta", None)
                content = getattr(delta_obj, "content", None) if delta_obj else None
                if content:
                    yield StreamChunk(delta=content)
                fin = getattr(choice, "finish_reason", None)
                if fin:
                    finish_reason = fin
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
                tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)

        yield StreamChunk(
            delta="",
            finish_reason=finish_reason,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=f"openrouter/{chosen_model}",
        )

    def _ensure_client(self) -> Any:
        """Lazy-construct the underlying ``AsyncOpenAI`` client."""
        if self._client is not None:
            return self._client
        self._client = self._client_factory(
            api_key=self._api_key,
            base_url=self._base_url,
            default_headers=self._extra_headers,
        )
        logger.info(
            "AsyncOpenRouter client ready: base=%s default_model=%s",
            self._base_url,
            self._default_model,
        )
        return self._client


def _extract_text(response: Any) -> str:
    """Return the assistant's text content. Same robust extraction as
    the sync provider — covers both string and content-block shapes."""
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise RuntimeError("OpenRouter response has no choices")
    msg = getattr(choices[0], "message", None)
    if msg is None:
        raise RuntimeError("OpenRouter response choice has no message")
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            text = (
                getattr(block, "text", None) if not isinstance(block, dict) else block.get("text")
            )
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts).strip()
    raise RuntimeError(f"Unexpected message content shape: {type(content).__name__}")


def _default_async_client_factory(
    *, api_key: str, base_url: str, default_headers: dict[str, str]
) -> Any:
    """Real ``AsyncOpenAI`` client, lazy-imported so tests can stub it."""
    from openai import AsyncOpenAI  # noqa: PLC0415

    return AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=default_headers)


__all__ = [
    "AsyncOpenRouterLLM",
    "DEFAULT_OPENROUTER_BASE_URL",
    "LLMResult",
    "StreamChunk",
]
