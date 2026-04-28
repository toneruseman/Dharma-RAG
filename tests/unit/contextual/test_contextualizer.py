"""Unit tests for :mod:`src.contextual.contextualizer`.

Day-15 ships only the prompt template + DI plumbing; no real LLM call
happens in code yet (validation was done in-conversation, see
``docs/contextual/validation_output_opus_v1.md``). These tests verify
the pure helpers and the dataclass contract — the parts that day-16's
indexer will rely on.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.contextual.contextualizer import (
    PROMPT_TEMPLATE_V1,
    PROMPT_TEMPLATE_V2,
    PROMPT_VERSION_V1,
    PROMPT_VERSION_V2,
    ContextProviderProtocol,
    ContextualizedChunk,
    build_contextualized_chunk,
    build_request_messages,
    format_prefixed_chunk,
)

# ---------------------------------------------------------------------------
# PROMPT_TEMPLATE_V1
# ---------------------------------------------------------------------------


def test_prompt_template_mentions_required_elements() -> None:
    """The prompt MUST instruct the LLM to produce the five required pieces.

    If someone refactors the prompt and accidentally drops "sutta canonical
    ID" or "Pāli terms preserved", the day-16 industrial run produces
    silently lower-quality contexts. These tests are the regression net.
    """
    p = PROMPT_TEMPLATE_V1.lower()
    assert "canonical id" in p
    assert "pāli" in p
    assert "preserved verbatim" in p or "preserve" in p.replace("\n", " ")
    assert "50-100 tokens" in p
    assert "single paragraph" in p or "plain prose" in p


def test_prompt_template_explicitly_forbids_paraphrase() -> None:
    """Doctrine paraphrase risks distorting the embedding semantically."""
    assert "do not paraphrase" in PROMPT_TEMPLATE_V1.lower()


def test_prompt_template_is_str() -> None:
    """Sanity: must be a non-empty string with length in a sane range."""
    assert isinstance(PROMPT_TEMPLATE_V1, str)
    assert 200 < len(PROMPT_TEMPLATE_V1) < 2000


def test_prompt_template_v2_lists_known_pali_pitfalls() -> None:
    """v2 was added specifically to fix the MN 118 / Satipaṭṭhāna mix-up
    seen in the day-16 smoke run. The fix is data, not just instruction:
    naming the actual sutta titles in the prompt forces the model to
    look at the exact ID before guessing."""
    p = PROMPT_TEMPLATE_V2
    assert "MN 118" in p
    assert "Anāpānassati" in p
    assert "Satipaṭṭhāna" in p
    assert "Dhammacakkappavattana" in p


def test_prompt_v2_tells_model_to_omit_when_uncertain() -> None:
    """The whole reason v2 exists — make the model omit rather than guess."""
    p = PROMPT_TEMPLATE_V2.lower()
    assert "omit" in p
    assert "uncertain" in p or "100% certain" in p


def test_prompt_versions_are_distinct_strings() -> None:
    assert PROMPT_VERSION_V1 != PROMPT_VERSION_V2
    assert PROMPT_VERSION_V2.startswith("v2-")


# ---------------------------------------------------------------------------
# build_request_messages
# ---------------------------------------------------------------------------


def test_build_request_messages_shape() -> None:
    """Output is a 2-element list: system prompt, then user content."""
    msgs = build_request_messages(parent_text="parent body", child_text="child body")
    assert isinstance(msgs, list)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"


def test_build_request_messages_carries_parent_and_child() -> None:
    """Both the parent and the child must appear in the user message,
    correctly tagged so the prompt template's references resolve."""
    msgs = build_request_messages(
        parent_text="PARENT TEXT 12345",
        child_text="CHILD TEXT 67890",
    )
    user_content = msgs[1]["content"]
    assert "<document>" in user_content
    assert "PARENT TEXT 12345" in user_content
    assert "<chunk>" in user_content
    assert "CHILD TEXT 67890" in user_content
    # Order matters for prompt caching: parent (cacheable) BEFORE child.
    assert user_content.index("PARENT TEXT") < user_content.index("CHILD TEXT")


def test_build_request_messages_uses_prompt_template_v1_by_default() -> None:
    msgs = build_request_messages(parent_text="p", child_text="c")
    assert msgs[0]["content"] == PROMPT_TEMPLATE_V1.strip()


def test_build_request_messages_accepts_custom_template() -> None:
    """Tests can pass a short stand-in template to keep fixtures readable."""
    msgs = build_request_messages(parent_text="p", child_text="c", prompt_template="SHORT TEMPLATE")
    assert msgs[0]["content"] == "SHORT TEMPLATE"


def test_build_request_messages_empty_parent_raises() -> None:
    with pytest.raises(ValueError, match="parent_text must be non-empty"):
        build_request_messages(parent_text="", child_text="c")


def test_build_request_messages_whitespace_only_parent_raises() -> None:
    with pytest.raises(ValueError, match="parent_text must be non-empty"):
        build_request_messages(parent_text="   \n  ", child_text="c")


def test_build_request_messages_empty_child_raises() -> None:
    with pytest.raises(ValueError, match="child_text must be non-empty"):
        build_request_messages(parent_text="p", child_text="")


# ---------------------------------------------------------------------------
# format_prefixed_chunk
# ---------------------------------------------------------------------------


def test_format_prefixed_chunk_basic() -> None:
    out = format_prefixed_chunk(context="CTX about MN 118.", child_text="Body of chunk.")
    assert out == "CTX about MN 118.\n\nBody of chunk."


def test_format_prefixed_chunk_strips_whitespace() -> None:
    """Leading/trailing whitespace from either side must not bleed into the
    output — embeddings should see clean text."""
    out = format_prefixed_chunk(context="  CTX  \n", child_text="\n  CHUNK  ")
    assert out == "CTX\n\nCHUNK"


def test_format_prefixed_chunk_context_first() -> None:
    """Order matters for retrieval: metadata-style cues (sutta IDs) should
    sit at the FRONT of the embedded text, not the back."""
    out = format_prefixed_chunk(context="CTX", child_text="CHUNK")
    assert out.index("CTX") < out.index("CHUNK")


def test_format_prefixed_chunk_empty_context_raises() -> None:
    with pytest.raises(ValueError, match="context must be non-empty"):
        format_prefixed_chunk(context="", child_text="c")


def test_format_prefixed_chunk_empty_child_raises() -> None:
    with pytest.raises(ValueError, match="child_text must be non-empty"):
        format_prefixed_chunk(context="ctx", child_text="")


def test_format_prefixed_chunk_whitespace_only_context_raises() -> None:
    with pytest.raises(ValueError, match="context must be non-empty"):
        format_prefixed_chunk(context="   ", child_text="c")


# ---------------------------------------------------------------------------
# ContextualizedChunk dataclass
# ---------------------------------------------------------------------------


def test_contextualized_chunk_is_frozen() -> None:
    """Frozen so the day-16 indexer can't accidentally mutate after build."""
    cc = ContextualizedChunk(
        chunk_id=uuid4(),
        parent_chunk_id=None,
        child_text="c",
        context="ctx",
        prefixed_text="ctx\n\nc",
        prompt_version=PROMPT_VERSION_V1,
        model_id="test/fake",
    )
    with pytest.raises((AttributeError, TypeError)):
        cc.context = "tampered"  # type: ignore[misc]


def test_contextualized_chunk_carries_versioning() -> None:
    """The version + model_id fields are the cornerstone of future
    re-context migrations — must be present and string-typed."""
    cc = ContextualizedChunk(
        chunk_id=uuid4(),
        parent_chunk_id=None,
        child_text="c",
        context="ctx",
        prefixed_text="ctx\n\nc",
        prompt_version="v1-2026-04-27",
        model_id="anthropic/claude-haiku-3.5",
    )
    assert cc.prompt_version == "v1-2026-04-27"
    assert cc.model_id == "anthropic/claude-haiku-3.5"


# ---------------------------------------------------------------------------
# build_contextualized_chunk helper
# ---------------------------------------------------------------------------


def test_build_contextualized_chunk_computes_prefixed_text() -> None:
    """The whole point of having a single helper: nobody ever forgets the
    ``prefixed_text`` field."""
    chunk_id = uuid4()
    cc = build_contextualized_chunk(
        chunk_id=chunk_id,
        parent_chunk_id=None,
        child_text="CHILD",
        context="CTX",
        model_id="test",
    )
    assert cc.prefixed_text == "CTX\n\nCHILD"
    assert cc.chunk_id == chunk_id


def test_build_contextualized_chunk_default_prompt_version() -> None:
    cc = build_contextualized_chunk(
        chunk_id=uuid4(),
        parent_chunk_id=None,
        child_text="c",
        context="ctx",
        model_id="test",
    )
    assert cc.prompt_version == PROMPT_VERSION_V1


def test_build_contextualized_chunk_preserves_parent_link() -> None:
    parent_id = uuid4()
    cc = build_contextualized_chunk(
        chunk_id=uuid4(),
        parent_chunk_id=parent_id,
        child_text="c",
        context="ctx",
        model_id="test",
    )
    assert cc.parent_chunk_id == parent_id


# ---------------------------------------------------------------------------
# ContextProviderProtocol — structural typing smoke
# ---------------------------------------------------------------------------


class _FakeProvider:
    """Trivial structural-type witness used in protocol-conformance tests."""

    @property
    def model_id(self) -> str:
        return "fake/0.0"

    def generate_context(self, *, parent_text: str, child_text: str) -> str:
        return f"context for: {child_text[:20]}"


def test_fake_provider_satisfies_protocol() -> None:
    """If this fails after a refactor, downstream day-16 code will break.
    Catch the contract drift here, with a one-line fake."""
    provider: ContextProviderProtocol = _FakeProvider()
    out = provider.generate_context(parent_text="p", child_text="hello world")
    assert out.startswith("context for")
    assert provider.model_id == "fake/0.0"
