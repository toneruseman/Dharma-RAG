"""OpenRouter-backed implementation of :class:`ContextProviderProtocol`.

OpenRouter is OpenAI-compatible, so we use the ``openai`` SDK pointed at
``https://openrouter.ai/api/v1``. This single class handles every model
OpenRouter routes to — Anthropic, Google, DeepSeek, Qwen — by varying
the ``model`` argument. The default for day-16 is
``anthropic/claude-3.5-haiku`` (validated for Contextual Retrieval by
Anthropic's own paper).

Why prompt caching matters
--------------------------
Per parent (~5000 tokens) we generate ~7 child contexts. Without
caching we'd pay full input price 7 times. With Anthropic-style
``cache_control: {"type": "ephemeral"}`` on the parent block:
* Cache write (5-min TTL): 1.25× base input price (one-off per parent).
* Cache reads: 0.10× base input price (×6 subsequent children).
* Net per parent: 1.25 + 6 × 0.10 = 1.85× input vs 7× without caching →
  **~74% reduction** on the input bill.

OpenRouter forwards ``cache_control`` to Anthropic transparently. Other
providers (DeepSeek, Qwen) don't honor it; the parameter is silently
ignored without breaking the request.

Why we don't subclass ``openai.OpenAI``
---------------------------------------
The SDK is fine as-is. We compose, not inherit. The wrapper's job is
narrow: turn a ``(parent, child)`` pair into a single OpenRouter call,
extract the text response, surface failures clearly. That's a function,
not a class hierarchy.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from src.contextual.contextualizer import PROMPT_TEMPLATE_V2

logger = logging.getLogger(__name__)

DEFAULT_OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# Anthropic Claude 3.5 Haiku rates on OpenRouter (April 2026, US dollars).
# Hard-coded here so the cost-cap logic in scripts/contextualize_corpus.py
# can compute spend without an extra API roundtrip. Refresh if/when
# OpenRouter changes pricing or we switch model.
HAIKU_3_5_INPUT_USD_PER_MTOK: float = 0.80
HAIKU_3_5_OUTPUT_USD_PER_MTOK: float = 4.00
HAIKU_3_5_CACHE_WRITE_MULTIPLIER: float = 1.25  # 5-minute TTL
HAIKU_3_5_CACHE_READ_MULTIPLIER: float = 0.10


def estimate_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
    input_per_mtok: float = HAIKU_3_5_INPUT_USD_PER_MTOK,
    output_per_mtok: float = HAIKU_3_5_OUTPUT_USD_PER_MTOK,
    cache_write_mult: float = HAIKU_3_5_CACHE_WRITE_MULTIPLIER,
    cache_read_mult: float = HAIKU_3_5_CACHE_READ_MULTIPLIER,
) -> float:
    """Rough USD cost estimate for one or many requests.

    All four token counts are passed separately so the caller can
    aggregate across many requests without re-classifying tokens.
    Multipliers default to Anthropic Haiku 3.5 via OpenRouter; pass
    overrides when running on a different model.
    """
    base_input = (input_tokens / 1_000_000) * input_per_mtok
    output = (output_tokens / 1_000_000) * output_per_mtok
    cache_write = (cache_write_tokens / 1_000_000) * input_per_mtok * cache_write_mult
    cache_read = (cache_read_tokens / 1_000_000) * input_per_mtok * cache_read_mult
    return base_input + output + cache_write + cache_read


class OpenRouterProvider:
    """Generate Contextual Retrieval contexts via OpenRouter's chat API.

    Designed for day-16's batch indexer pattern: one provider instance
    per process, shared across threads/coroutines (the underlying
    ``openai.OpenAI`` client is thread-safe per its own docs). Token
    accounting is captured per call into ``self.usage`` so the CLI can
    print running totals + enforce a cost cap.

    Parameters
    ----------
    api_key:
        OpenRouter API key (``sk-or-v1-...``).
    model:
        OpenRouter model identifier. Default
        ``"anthropic/claude-3.5-haiku"``. Anything OpenRouter routes to
        works; non-Anthropic models silently ignore ``cache_control``.
    base_url:
        OpenAI-compatible endpoint. Defaults to OpenRouter's. Override
        for testing against a local mock server.
    client_factory:
        Test injection point. Production leaves this ``None``; tests
        pass a ``lambda **kw: FakeOpenAI(...)`` to swap in a stub.
    enable_caching:
        Adds ``cache_control: {"type": "ephemeral"}`` to the parent
        message block. Defaults True. Set False for providers that
        choke on the parameter (we have not seen one yet in the
        OpenRouter catalogue, but the escape hatch exists).
    extra_headers:
        Forwarded as ``default_headers`` to the OpenAI client.
        OpenRouter recommends ``HTTP-Referer`` and ``X-Title`` so the
        request shows up correctly on their dashboard.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "anthropic/claude-3.5-haiku",
        base_url: str = DEFAULT_OPENROUTER_BASE_URL,
        client_factory: Callable[..., Any] | None = None,
        enable_caching: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenRouter API key is empty; set OPENROUTER_API_KEY.")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._enable_caching = enable_caching
        self._extra_headers = extra_headers or {
            "HTTP-Referer": "https://github.com/toneruseman/Dharma-RAG",
            "X-Title": "Dharma-RAG Contextual Retrieval",
        }
        self._client_factory = client_factory or _default_client_factory
        self._client: Any = None
        self._client_lock = threading.Lock()
        self.usage = _UsageAccumulator()

    @property
    def model_id(self) -> str:
        """Identifier we stamp into ``ContextualizedChunk.model_id``."""
        return f"openrouter/{self._model}"

    def generate_context(self, *, parent_text: str, child_text: str) -> str:
        """Return a 50-100 token context for ``child_text``.

        Single API call. Failures (rate limits, 5xx, malformed responses)
        propagate to the caller — the day-16 indexer wraps with retry/
        backoff so retry policy lives in one place.
        """
        if not parent_text.strip():
            raise ValueError("parent_text must be non-empty")
        if not child_text.strip():
            raise ValueError("child_text must be non-empty")

        client = self._ensure_client()
        messages = self._build_messages(parent_text=parent_text, child_text=child_text)

        response = client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=200,
            temperature=0.0,
        )
        self.usage.record(response)
        return _extract_text(response)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_client(self) -> Any:
        """Lazy-construct the underlying ``openai.OpenAI`` client."""
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is not None:
                return self._client
            self._client = self._client_factory(
                api_key=self._api_key,
                base_url=self._base_url,
                default_headers=self._extra_headers,
            )
            logger.info(
                "OpenRouter client ready: base=%s model=%s caching=%s",
                self._base_url,
                self._model,
                self._enable_caching,
            )
            return self._client

    def _build_messages(self, *, parent_text: str, child_text: str) -> list[dict[str, Any]]:
        """Compose the chat-completions payload with optional cache_control.

        The parent block carries ``cache_control`` so subsequent calls in
        the same 5-minute window reuse its tokens at 0.10× price. We use
        the OpenAI content-blocks shape (list of {type, text, ...}) which
        OpenRouter forwards verbatim to Anthropic.
        """
        system_block: dict[str, Any] = {
            "type": "text",
            "text": PROMPT_TEMPLATE_V2.strip(),
        }
        parent_block: dict[str, Any] = {
            "type": "text",
            "text": f"<document>\n{parent_text.strip()}\n</document>",
        }
        if self._enable_caching:
            parent_block["cache_control"] = {"type": "ephemeral"}
        child_block: dict[str, Any] = {
            "type": "text",
            "text": f"<chunk>\n{child_text.strip()}\n</chunk>",
        }
        return [
            {"role": "system", "content": [system_block]},
            {"role": "user", "content": [parent_block, child_block]},
        ]


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


class _UsageAccumulator:
    """Thread-safe running tally of token usage + cost."""

    __slots__ = (
        "_lock",
        "cache_read_tokens",
        "cache_write_tokens",
        "calls",
        "input_tokens",
        "output_tokens",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cache_write_tokens: int = 0
        self.cache_read_tokens: int = 0

    def record(self, response: Any) -> None:
        """Pull token counts out of an OpenAI-shape response.

        OpenRouter exposes Anthropic cache stats under
        ``response.usage.prompt_tokens_details.cached_tokens`` (cache
        reads) and ``cache_creation_input_tokens`` (cache writes). The
        SDK surfaces them as attributes when present; we read defensively
        so a model that returns a thinner usage block doesn't crash the
        run.
        """
        with self._lock:
            self.calls += 1
            usage = getattr(response, "usage", None)
            if usage is None:
                return
            input_total = int(getattr(usage, "prompt_tokens", 0) or 0)
            output_total = int(getattr(usage, "completion_tokens", 0) or 0)

            details = getattr(usage, "prompt_tokens_details", None)
            cache_read = 0
            if details is not None:
                cache_read = int(getattr(details, "cached_tokens", 0) or 0)
            # Some routings expose Anthropic-style cache_creation tokens.
            cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

            # Avoid double-counting: subtract cache reads from base input.
            base_input = max(0, input_total - cache_read - cache_write)
            self.input_tokens += base_input
            self.output_tokens += output_total
            self.cache_write_tokens += cache_write
            self.cache_read_tokens += cache_read

    def estimated_cost_usd(self) -> float:
        return estimate_cost_usd(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_write_tokens=self.cache_write_tokens,
            cache_read_tokens=self.cache_read_tokens,
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "calls": self.calls,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "cache_write_tokens": self.cache_write_tokens,
                "cache_read_tokens": self.cache_read_tokens,
                "estimated_cost_usd": self.estimated_cost_usd(),
            }


def _extract_text(response: Any) -> str:
    """Return the assistant's text content from a chat-completions response.

    Robust to both the simple shape (``content`` is a string) and the
    rich shape (list of content blocks). Anthropic-via-OpenRouter
    always returns the simple form for completion-only requests; the
    branching covers future model swaps without a code change.
    """
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
        # Concatenate all text blocks.
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


def _default_client_factory(*, api_key: str, base_url: str, default_headers: dict[str, str]) -> Any:
    """Real OpenAI-SDK client, lazy-imported so tests skip the import."""
    from openai import OpenAI  # noqa: PLC0415

    return OpenAI(api_key=api_key, base_url=base_url, default_headers=default_headers)


__all__ = [
    "DEFAULT_OPENROUTER_BASE_URL",
    "HAIKU_3_5_CACHE_READ_MULTIPLIER",
    "HAIKU_3_5_CACHE_WRITE_MULTIPLIER",
    "HAIKU_3_5_INPUT_USD_PER_MTOK",
    "HAIKU_3_5_OUTPUT_USD_PER_MTOK",
    "OpenRouterProvider",
    "estimate_cost_usd",
]
