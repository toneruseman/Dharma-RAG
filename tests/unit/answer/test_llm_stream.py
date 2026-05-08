"""Unit tests for :meth:`AsyncOpenRouterLLM.stream`.

The real client is mocked so we exercise the iteration / accumulation
logic without hitting OpenRouter. Test fakes mimic the shape of the
official SDK's ``ChatCompletionChunk`` objects so attribute access is
identical to production.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest

from src.answer.llm import AsyncOpenRouterLLM, StreamChunk


@dataclass
class _FakeDelta:
    content: str | None


@dataclass
class _FakeChoice:
    delta: _FakeDelta
    finish_reason: str | None = None


@dataclass
class _FakeUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass
class _FakeChunk:
    choices: list[_FakeChoice]
    usage: _FakeUsage | None = None


class _FakeAsyncStream:
    """Async iterator returning a fixed sequence of chunks."""

    def __init__(self, chunks: list[_FakeChunk]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator[_FakeChunk]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[_FakeChunk]:
        for chunk in self._chunks:
            yield chunk


class _FakeChatCompletions:
    def __init__(self, chunks: list[_FakeChunk]) -> None:
        self._chunks = chunks
        self.last_kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> _FakeAsyncStream:
        self.last_kwargs = kwargs
        return _FakeAsyncStream(self._chunks)


class _FakeChat:
    def __init__(self, chunks: list[_FakeChunk]) -> None:
        self.completions = _FakeChatCompletions(chunks)


class _FakeAsyncOpenAI:
    def __init__(self, chunks: list[_FakeChunk]) -> None:
        self.chat = _FakeChat(chunks)


def _make_client_factory(chunks: list[_FakeChunk]) -> Any:
    """Inject a factory that returns the fake client unchanged."""
    fake = _FakeAsyncOpenAI(chunks)

    def factory(**_: Any) -> _FakeAsyncOpenAI:
        return fake

    factory.fake = fake  # type: ignore[attr-defined]  — for assertions
    return factory


def _delta_chunks(*deltas: str) -> list[_FakeChunk]:
    """Build chunks with content deltas (no finish, no usage)."""
    return [_FakeChunk(choices=[_FakeChoice(delta=_FakeDelta(content=d))]) for d in deltas]


def _terminal_chunk(
    *, finish: str = "stop", tokens_in: int = 100, tokens_out: int = 30
) -> _FakeChunk:
    """Build the OpenRouter-style terminal chunk: empty choices + usage."""
    return _FakeChunk(
        choices=[_FakeChoice(delta=_FakeDelta(content=None), finish_reason=finish)],
        usage=_FakeUsage(prompt_tokens=tokens_in, completion_tokens=tokens_out),
    )


@pytest.mark.asyncio
async def test_stream_yields_deltas_and_terminal_usage() -> None:
    """Three text deltas followed by a usage-only chunk → four StreamChunks
    with the terminal one carrying token counts and model id."""
    chunks = [
        *_delta_chunks("Mindful", "ness is", " taught."),
        _terminal_chunk(tokens_in=42, tokens_out=8),
    ]
    factory = _make_client_factory(chunks)
    llm = AsyncOpenRouterLLM(
        api_key="sk-test",  # pragma: allowlist secret
        default_model="test/model",
        client_factory=factory,
    )

    received: list[StreamChunk] = []
    async for chunk in llm.stream(system_prompt="sys", user_message="msg"):
        received.append(chunk)

    # Three text chunks plus one terminal usage chunk.
    assert len(received) == 4
    assert [c.delta for c in received[:3]] == ["Mindful", "ness is", " taught."]

    terminal = received[-1]
    assert terminal.delta == ""
    assert terminal.finish_reason == "stop"
    assert terminal.tokens_in == 42
    assert terminal.tokens_out == 8
    assert terminal.model == "openrouter/test/model"


@pytest.mark.asyncio
async def test_stream_drops_empty_keepalive_deltas() -> None:
    """Chunks with ``content=None`` (keep-alive heartbeats from
    upstream) must not be yielded as empty StreamChunks — they'd just
    add JSON-encoding overhead on the wire for no information."""
    chunks = [
        _FakeChunk(choices=[_FakeChoice(delta=_FakeDelta(content=None))]),  # keep-alive
        *_delta_chunks("hi"),
        _FakeChunk(choices=[_FakeChoice(delta=_FakeDelta(content=None))]),  # keep-alive
        _terminal_chunk(),
    ]
    factory = _make_client_factory(chunks)
    llm = AsyncOpenRouterLLM(
        api_key="sk-test",  # pragma: allowlist secret
        default_model="test/model",
        client_factory=factory,
    )

    received = [c async for c in llm.stream(system_prompt="s", user_message="m")]

    # Only the "hi" delta and the terminal chunk survive.
    assert len(received) == 2
    assert received[0].delta == "hi"
    assert received[1].delta == ""
    assert received[1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_passes_options_to_underlying_client() -> None:
    """Sanity: stream=True and stream_options{include_usage:True} are
    actually sent — without the latter OpenRouter strips usage from
    the terminal chunk for many providers."""
    chunks = [_terminal_chunk()]
    factory = _make_client_factory(chunks)
    llm = AsyncOpenRouterLLM(
        api_key="sk-test",  # pragma: allowlist secret
        default_model="test/model",
        client_factory=factory,
    )

    async for _ in llm.stream(
        system_prompt="s",
        user_message="m",
        max_tokens=512,
        temperature=0.5,
    ):
        pass

    fake = factory.fake  # type: ignore[attr-defined]
    kwargs = fake.chat.completions.last_kwargs
    assert kwargs is not None
    assert kwargs["stream"] is True
    assert kwargs["stream_options"] == {"include_usage": True}
    assert kwargs["max_tokens"] == 512
    assert kwargs["temperature"] == 0.5
    assert kwargs["model"] == "test/model"


@pytest.mark.asyncio
async def test_stream_respects_per_call_model_override() -> None:
    """Per-request `model` arg wins over `default_model`."""
    chunks = [_terminal_chunk()]
    factory = _make_client_factory(chunks)
    llm = AsyncOpenRouterLLM(
        api_key="sk-test",  # pragma: allowlist secret
        default_model="default/model",
        client_factory=factory,
    )

    received = [
        c
        async for c in llm.stream(
            system_prompt="s",
            user_message="m",
            model="override/model",
        )
    ]

    fake = factory.fake  # type: ignore[attr-defined]
    assert fake.chat.completions.last_kwargs is not None
    assert fake.chat.completions.last_kwargs["model"] == "override/model"
    assert received[-1].model == "openrouter/override/model"
