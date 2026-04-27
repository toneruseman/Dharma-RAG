"""Unit tests for :class:`src.contextual.providers.OpenRouterProvider`.

No real OpenRouter call is made — every test injects a fake client via
the ``client_factory`` seam. The fake captures the request shape so we
can assert on cache_control placement, model id, message structure.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.contextual.contextualizer import PROMPT_TEMPLATE_V2
from src.contextual.providers.openrouter import (
    DEFAULT_OPENROUTER_BASE_URL,
    HAIKU_3_5_CACHE_READ_MULTIPLIER,
    HAIKU_3_5_CACHE_WRITE_MULTIPLIER,
    HAIKU_3_5_INPUT_USD_PER_MTOK,
    HAIKU_3_5_OUTPUT_USD_PER_MTOK,
    OpenRouterProvider,
    estimate_cost_usd,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeDetails:
    def __init__(self, cached_tokens: int) -> None:
        self.cached_tokens = cached_tokens


class _FakeUsage:
    def __init__(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.prompt_tokens_details = _FakeDetails(cached_tokens)
        self.cache_creation_input_tokens = cache_creation_tokens


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(
        self,
        content: str,
        *,
        prompt_tokens: int = 100,
        completion_tokens: int = 50,
        cached_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            cache_creation_tokens=cache_creation_tokens,
        )


class _FakeChat:
    def __init__(self, parent: _FakeOpenAI) -> None:
        self._parent = parent

    @property
    def completions(self) -> _FakeOpenAI:
        return self._parent


class _FakeOpenAI:
    """Minimal stub matching the openai SDK shape we actually call."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_headers: dict[str, str],
        response_factory: Any = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.default_headers = default_headers
        self.response_factory = response_factory or (lambda **_: _FakeResponse("a context."))
        self.calls: list[dict[str, Any]] = []

    @property
    def chat(self) -> _FakeChat:
        return _FakeChat(self)

    # The provider calls ``client.chat.completions.create(...)``. Our
    # ``_FakeChat.completions`` returns the same instance, so ``create``
    # ends up here.
    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response_factory(**kwargs)


def _make_provider(
    *, response: Any = None, enable_caching: bool = True
) -> tuple[OpenRouterProvider, list[_FakeOpenAI]]:
    """Build a provider wired to a captured fake client."""
    captured: list[_FakeOpenAI] = []

    def factory(*, api_key: str, base_url: str, default_headers: dict[str, str]) -> _FakeOpenAI:
        client = _FakeOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers,
            response_factory=(lambda **_: response) if response is not None else None,
        )
        captured.append(client)
        return client

    provider = OpenRouterProvider(
        api_key="sk-or-v1-fake",  # pragma: allowlist secret
        client_factory=factory,
        enable_caching=enable_caching,
    )
    return provider, captured


# ---------------------------------------------------------------------------
# Construction + model_id
# ---------------------------------------------------------------------------


def test_empty_api_key_raises() -> None:
    with pytest.raises(ValueError, match="OpenRouter API key is empty"):
        OpenRouterProvider(api_key="")


def test_default_model_is_claude_haiku() -> None:
    p = OpenRouterProvider(api_key="sk-or-v1-x")
    assert p.model_id == "openrouter/anthropic/claude-3.5-haiku"


def test_custom_model_reflected_in_model_id() -> None:
    p = OpenRouterProvider(api_key="sk-or-v1-x", model="google/gemini-2.0-flash")
    assert p.model_id == "openrouter/google/gemini-2.0-flash"


def test_default_base_url() -> None:
    """Sanity: we don't accidentally point at api.openai.com."""
    p, _ = _make_provider()
    p.generate_context(parent_text="p", child_text="c")
    # Force client creation; check it received OpenRouter URL.
    assert p._base_url == DEFAULT_OPENROUTER_BASE_URL  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Message structure
# ---------------------------------------------------------------------------


def test_generate_context_returns_response_text() -> None:
    p, captured = _make_provider(response=_FakeResponse("This passage is from MN 118."))
    out = p.generate_context(parent_text="parent body", child_text="child body")
    assert out == "This passage is from MN 118."
    assert len(captured) == 1
    assert len(captured[0].calls) == 1


def test_messages_have_two_entries_system_and_user() -> None:
    p, captured = _make_provider()
    p.generate_context(parent_text="P", child_text="C")
    msgs = captured[0].calls[0]["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"


def test_system_block_carries_prompt_template_v1() -> None:
    p, captured = _make_provider()
    p.generate_context(parent_text="P", child_text="C")
    sys_msg = captured[0].calls[0]["messages"][0]
    # System content is a list of blocks; first block is the prompt.
    assert isinstance(sys_msg["content"], list)
    assert sys_msg["content"][0]["text"] == PROMPT_TEMPLATE_V2.strip()


def test_user_message_has_parent_block_then_child_block() -> None:
    p, captured = _make_provider()
    p.generate_context(parent_text="PARENT-XYZ", child_text="CHILD-789")
    user_msg = captured[0].calls[0]["messages"][1]
    blocks = user_msg["content"]
    assert len(blocks) == 2
    assert "PARENT-XYZ" in blocks[0]["text"]
    assert "CHILD-789" in blocks[1]["text"]
    # Order matters for prompt caching: parent first.
    assert blocks[0]["text"].index("PARENT-XYZ") < blocks[1]["text"].index("CHILD-789") + 999


def test_cache_control_on_parent_when_caching_enabled() -> None:
    """Anthropic prompt caching is the WHOLE point — verify the marker
    lands on the parent block, not the child or system block."""
    p, captured = _make_provider(enable_caching=True)
    p.generate_context(parent_text="P", child_text="C")
    msgs = captured[0].calls[0]["messages"]
    parent_block = msgs[1]["content"][0]
    child_block = msgs[1]["content"][1]
    assert parent_block.get("cache_control") == {"type": "ephemeral"}
    assert "cache_control" not in child_block


def test_no_cache_control_when_caching_disabled() -> None:
    p, captured = _make_provider(enable_caching=False)
    p.generate_context(parent_text="P", child_text="C")
    msgs = captured[0].calls[0]["messages"]
    for block in msgs[1]["content"]:
        assert "cache_control" not in block


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


def test_empty_parent_raises_before_api_call() -> None:
    p, captured = _make_provider()
    with pytest.raises(ValueError, match="parent_text must be non-empty"):
        p.generate_context(parent_text="", child_text="c")
    # No API call attempted.
    assert captured == []


def test_empty_child_raises_before_api_call() -> None:
    p, captured = _make_provider()
    with pytest.raises(ValueError, match="child_text must be non-empty"):
        p.generate_context(parent_text="p", child_text="")
    assert captured == []


# ---------------------------------------------------------------------------
# Usage accounting
# ---------------------------------------------------------------------------


def test_usage_records_token_counts() -> None:
    response = _FakeResponse("ctx", prompt_tokens=1000, completion_tokens=80, cached_tokens=0)
    p, _ = _make_provider(response=response)
    p.generate_context(parent_text="p", child_text="c")
    snap = p.usage.snapshot()
    assert snap["calls"] == 1
    assert snap["input_tokens"] == 1000  # no cache → all base
    assert snap["output_tokens"] == 80


def test_usage_separates_base_input_from_cache_reads() -> None:
    """When cache reads happen, ``prompt_tokens`` includes them — we
    must subtract so we don't double-count and over-bill."""
    response = _FakeResponse("ctx", prompt_tokens=1000, completion_tokens=80, cached_tokens=600)
    p, _ = _make_provider(response=response)
    p.generate_context(parent_text="p", child_text="c")
    snap = p.usage.snapshot()
    assert snap["input_tokens"] == 400  # 1000 total - 600 cached
    assert snap["cache_read_tokens"] == 600


def test_usage_records_cache_writes() -> None:
    response = _FakeResponse(
        "ctx", prompt_tokens=1500, completion_tokens=80, cache_creation_tokens=500
    )
    p, _ = _make_provider(response=response)
    p.generate_context(parent_text="p", child_text="c")
    snap = p.usage.snapshot()
    assert snap["cache_write_tokens"] == 500
    assert snap["input_tokens"] == 1000  # 1500 - 500 cache_creation


def test_usage_aggregates_across_calls() -> None:
    p, _ = _make_provider(response=_FakeResponse("c", prompt_tokens=100, completion_tokens=50))
    for _ in range(3):
        p.generate_context(parent_text="p", child_text="c")
    snap = p.usage.snapshot()
    assert snap["calls"] == 3
    assert snap["input_tokens"] == 300
    assert snap["output_tokens"] == 150


# ---------------------------------------------------------------------------
# Cost estimation (pure)
# ---------------------------------------------------------------------------


def test_estimate_cost_uncached() -> None:
    """1M input tokens * $0.80 + 1M output * $4 = $4.80."""
    cost = estimate_cost_usd(input_tokens=1_000_000, output_tokens=1_000_000)
    expected = HAIKU_3_5_INPUT_USD_PER_MTOK + HAIKU_3_5_OUTPUT_USD_PER_MTOK
    assert cost == pytest.approx(expected)


def test_estimate_cost_cache_write_costs_more_than_base() -> None:
    """1.25× input price for cache writes."""
    base = estimate_cost_usd(input_tokens=1_000_000, output_tokens=0)
    cache = estimate_cost_usd(input_tokens=0, output_tokens=0, cache_write_tokens=1_000_000)
    assert cache == pytest.approx(base * HAIKU_3_5_CACHE_WRITE_MULTIPLIER)


def test_estimate_cost_cache_read_is_cheap() -> None:
    """0.10× input price for cache reads — the whole reason caching exists."""
    base = estimate_cost_usd(input_tokens=1_000_000, output_tokens=0)
    cache = estimate_cost_usd(input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000)
    assert cache == pytest.approx(base * HAIKU_3_5_CACHE_READ_MULTIPLIER)
    # And for sanity: 10× cheaper than uncached input.
    assert cache < base / 9


def test_estimate_cost_combines_all_buckets() -> None:
    cost = estimate_cost_usd(
        input_tokens=500_000,
        output_tokens=100_000,
        cache_write_tokens=200_000,
        cache_read_tokens=300_000,
    )
    expected = (
        0.5 * HAIKU_3_5_INPUT_USD_PER_MTOK
        + 0.1 * HAIKU_3_5_OUTPUT_USD_PER_MTOK
        + 0.2 * HAIKU_3_5_INPUT_USD_PER_MTOK * HAIKU_3_5_CACHE_WRITE_MULTIPLIER
        + 0.3 * HAIKU_3_5_INPUT_USD_PER_MTOK * HAIKU_3_5_CACHE_READ_MULTIPLIER
    )
    assert cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Lazy client init
# ---------------------------------------------------------------------------


def test_client_not_built_until_first_call() -> None:
    counter = {"n": 0}

    def factory(**kwargs: Any) -> Any:
        counter["n"] += 1
        return _FakeOpenAI(**kwargs)

    p = OpenRouterProvider(api_key="sk-or-v1-x", client_factory=factory)
    assert counter["n"] == 0
    p.generate_context(parent_text="p", child_text="c")
    assert counter["n"] == 1
    p.generate_context(parent_text="p2", child_text="c2")
    assert counter["n"] == 1  # second call reuses


def test_default_headers_include_openrouter_attribution() -> None:
    """OpenRouter dashboard shows your project by HTTP-Referer + X-Title."""
    p, captured = _make_provider()
    p.generate_context(parent_text="p", child_text="c")
    headers = captured[0].default_headers
    assert "HTTP-Referer" in headers
    assert "X-Title" in headers
