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
from collections.abc import Callable
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
        default_model: str = "anthropic/claude-haiku-4.5",
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
]
