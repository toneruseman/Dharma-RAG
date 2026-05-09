"""Answer service — wraps retrieval + LLM behind ``/api/answer``.

Composition-based design. ``AnswerService`` owns no retrieval
machinery itself; it depends on a :class:`RAGServiceProtocol` for
sources and a :class:`AsyncOpenRouterLLM` for synthesis. The system
prompt and citation extraction live here because they belong to the
*answer* layer, not the retrieval layer.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import structlog

from src.answer.llm import AsyncOpenRouterLLM
from src.answer.schemas import (
    AnswerMetadata,
    AnswerRequest,
    AnswerResponse,
    AnswerStyle,
)
from src.answer.stream_schemas import (
    CitationEvent,
    DoneEvent,
    ErrorEvent,
    RetrievalDoneEvent,
    TokenEvent,
)
from src.config import Settings, get_settings
from src.rag.protocol import RAGServiceProtocol
from src.rag.schemas import QueryRequest, Source

logger = logging.getLogger(__name__)


# Shared rules across all styles. The only thing that changes per
# style is the trailing length-guidance bullet. Keeping the bulk
# shared means style-specific changes are a one-line diff.
_BASE_SYSTEM_PROMPT: str = """\
You are a knowledgeable assistant on the Pāli Canon (early Buddhist scripture in the Theravāda tradition).

You answer using ONLY the source passages provided in the user message. Do not draw on outside knowledge, do not speculate.

Rules:
- Answer in the language of the user's question. Russian question → Russian answer; English question → English answer.
- Cite sources inline using the format [work_id], e.g. "as the Buddha teaches [mn36]" or "found in [sn56.11]". The work_id is shown above each source passage. Multiple works in one bracket are fine: [mn39, dn10].
- Use the work_id EXACTLY as shown in the source header — always lowercase ASCII (mn, sn, dn, an, kn, snp, dhp, ud, iti, thag, thig, …). Do NOT transliterate to Cyrillic or any other script: write [mn43], NEVER [мн43]; write [an9.32], NEVER [ан9.32]. This rule applies even when the answer is in Russian.
- Output plain prose only. Do NOT use markdown formatting in the answer body: no **bold**, no *italics*, no `code`, no headers (#, ##), no bullet/numbered lists. The renderer is plain-text with bracket citations only.
- When multiple sources are relevant, cite them all.
- If the sources do not contain enough information to answer the question, say so honestly. Do not fabricate. Examples of acceptable fallback: "The provided passages do not directly address X." / "На основе предоставленных источников нельзя ответить на этот вопрос."
- Preserve canonical Pāli terms with their diacritics on first mention (jhāna, paṭiccasamuppāda, dukkha, sati). After first mention you may use a transliteration (jhana) or translation in the answer's target language.
- Stay within the Theravāda tradition reflected in the Pāli Canon. Do not introduce Mahāyāna or Vajrayāna concepts unless a source passage explicitly discusses them."""


# Output-token cap per style. Sized so the model never gets cut
# off mid-paragraph for the typical "what is X?" question. Numbers
# tuned 2026-04-29 after a 6-model comparison where 5/6 models hit
# the previous flat 1024 cap on `detailed` and were truncated.
_MAX_TOKENS_BY_STYLE: dict[AnswerStyle, int] = {
    "concise": 512,
    "auto": 1024,
    "detailed": 3072,
}


_STYLE_GUIDANCE: dict[AnswerStyle, str] = {
    "auto": (
        "Match length to question complexity. A simple factual question "
        '("когда жил Будда?") deserves 1-2 sentences with citations. A '
        'fundamental "what is X?" question that the sources address in '
        "depth deserves a structured multi-paragraph explanation drawing "
        "on all relevant passages. Don't pad, don't artificially compress."
    ),
    "concise": (
        "Be concise. A focused 2-4 sentence answer with citations beats a long paraphrase."
    ),
    "detailed": (
        "Provide a thorough, structured answer drawing on all relevant "
        "source passages. Use multiple paragraphs or numbered points where "
        "appropriate. Every claim must carry a citation."
    ),
}


def build_system_prompt(style: AnswerStyle) -> str:
    """Compose the full system prompt for the requested style.

    The ``base + per-style suffix`` split keeps the bulk of the prompt
    immutable so style tweaks don't risk breaking unrelated behaviour
    (citation format, language matching, Theravāda-only).
    """
    return _BASE_SYSTEM_PROMPT + "\n- " + _STYLE_GUIDANCE[style]


# Kept for backwards-compat with code that imports the module-level
# constant. Equivalent to ``build_system_prompt("auto")`` post day-24
# follow-up; pre-follow-up this was the one-and-only ("concise") prompt.
SYSTEM_PROMPT: str = build_system_prompt("auto")


# Match the **contents** of any bracket pair, then split on commas.
# Models naturally emit two patterns:
#   1. ``[mn10]`` — single work
#   2. ``[mn10, dn22]`` — multiple works in one bracket (Claude prefers this)
# Earlier regex ``\[([a-zA-Z0-9._-]+)\]`` rejected pattern (2) entirely
# because the character class doesn't include comma/space. We now match
# anything between brackets and split client-side, then validate each
# fragment against ``source_ids`` so non-citation brackets (e.g.
# ``[stub fixture — ...]``, code, footnote markers) are filtered out.
_CITATION_BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")
_CITATION_FRAGMENT_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _build_user_message(query: str, sources: list[Source]) -> str:
    """Compose the user message with numbered source passages.

    Each source is wrapped with its ``work_canonical_id`` so the LLM
    can cite it back. We use plain markdown-ish headers rather than
    XML tags — Claude handles both, and plain text is easier to read
    in logs / Phoenix spans.
    """
    if not sources:
        return f"User question: {query}\n\n(No source passages were retrieved.)"

    parts: list[str] = [
        "The following passages from the Pāli Canon were retrieved as relevant to the user's question.",
        "",
    ]
    for i, src in enumerate(sources, start=1):
        seg = f" ({src.segment_id})" if src.segment_id else ""
        parts.append(f"--- Source {i} [{src.work_canonical_id}]{seg} ---")
        parts.append(src.text)
        parts.append("")
    parts.append(f"User question: {query}")
    return "\n".join(parts)


def _extract_citations(answer_text: str, source_ids: set[str]) -> list[str]:
    """Pull citation strings out of the answer and intersect with sources.

    Handles three real-world model output patterns:
      * ``[mn10]`` — single work
      * ``[mn10, dn22]`` — multi-citation, comma-separated (Claude default)
      * ``[mn10][dn22]`` — adjacent single brackets

    Filtering rules:
      * Each comma-separated fragment must look like a work_id
        (``^[a-zA-Z0-9._-]+$``) — kicks out free-form text accidentally
        wrapped in brackets (e.g. ``[stub fixture — ...]``).
      * Fragment is then lowercased and intersected with ``source_ids``;
        anything missing (model hallucinations) is dropped.
      * Order is first-appearance, deduplicated.
    """
    seen: set[str] = set()
    out: list[str] = []
    for match in _CITATION_BRACKET_RE.finditer(answer_text):
        contents = match.group(1)
        for fragment in contents.split(","):
            cid = fragment.strip()
            if not _CITATION_FRAGMENT_RE.match(cid):
                continue
            cid = cid.lower()
            if cid in source_ids and cid not in seen:
                seen.add(cid)
                out.append(cid)
    return out


@dataclass(frozen=True, slots=True)
class CitationFound:
    """A newly-detected citation in the streaming buffer."""

    id: str
    """Lowercased canonical work_id."""

    position: int
    """Character offset in the buffer where the closing ``]`` sits."""


class IncrementalCitationScanner:
    """Stateful scanner that detects citations as text streams in.

    Maintains a running buffer plus a cursor; each :meth:`feed` call
    appends new text and reports any *newly closed* brackets that
    contain valid work_ids. A citation is reported at most once per
    work_id (subsequent duplicates ignored), preserving first-appearance
    order across the whole stream.

    Designed to be unit-testable in isolation — it has no LLM or
    HTTP dependencies.
    """

    def __init__(self, valid_ids: set[str]) -> None:
        self._valid_ids = valid_ids
        self._buffer: list[str] = []
        self._buffer_len = 0
        self._scan_from = 0
        self._seen: set[str] = set()
        self._ordered: list[str] = []

    def feed(self, delta: str) -> list[CitationFound]:
        """Append ``delta`` and return any newly-found citations."""
        if not delta:
            return []
        self._buffer.append(delta)
        self._buffer_len += len(delta)
        text = self.text
        results: list[CitationFound] = []
        last_end = self._scan_from
        for match in _CITATION_BRACKET_RE.finditer(text, self._scan_from):
            contents = match.group(1)
            for fragment in contents.split(","):
                cid = fragment.strip()
                if not _CITATION_FRAGMENT_RE.match(cid):
                    continue
                cid = cid.lower()
                if cid in self._valid_ids and cid not in self._seen:
                    self._seen.add(cid)
                    self._ordered.append(cid)
                    results.append(CitationFound(id=cid, position=match.end()))
            last_end = match.end()
        self._scan_from = last_end
        return results

    @property
    def text(self) -> str:
        return "".join(self._buffer)

    @property
    def citations(self) -> list[str]:
        return list(self._ordered)


class AnswerService:
    """Production answer service.

    Composes :class:`RAGServiceProtocol` for sources and
    :class:`AsyncOpenRouterLLM` for synthesis. Stateless across
    requests — safe to share one instance across all incoming
    queries.
    """

    def __init__(
        self,
        *,
        rag_service: RAGServiceProtocol,
        llm: AsyncOpenRouterLLM,
        settings: Settings | None = None,
    ) -> None:
        self._rag = rag_service
        self._llm = llm
        self._settings = settings or get_settings()

    async def answer(self, request: AnswerRequest) -> AnswerResponse:
        """Run retrieval + LLM and return the synthesised answer."""
        wall_start = time.perf_counter()
        trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        # Effective style: request override wins, else server default.
        effective_style: AnswerStyle = (
            request.style if request.style is not None else self._settings.answer_default_style
        )

        retrieval_request = QueryRequest(
            query=request.query,
            top_k=request.top_k,
            expand_pali=request.expand_pali,
            expand_definitional=request.expand_definitional,
            foundational_boost=request.foundational_boost,
            forbidden_works=request.forbidden_works,
        )
        retrieval_start = time.perf_counter()
        rag_response = await self._rag.query(retrieval_request)
        retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000.0

        sources = rag_response.sources
        if not sources:
            # No retrieval hits → don't call the LLM. Return an honest
            # empty answer; consumers display a fallback UI state.
            llm_latency_ms = 0.0
            answer_text = ""
            llm_model = self._llm.default_model
            tokens_in = 0
            tokens_out = 0
        else:
            user_message = _build_user_message(request.query, list(sources))
            llm_start = time.perf_counter()
            llm_result = await self._llm.complete(
                system_prompt=build_system_prompt(effective_style),
                user_message=user_message,
                model=request.model,
                max_tokens=_MAX_TOKENS_BY_STYLE[effective_style],
            )
            llm_latency_ms = (time.perf_counter() - llm_start) * 1000.0
            answer_text = llm_result.text
            llm_model = llm_result.model
            tokens_in = llm_result.tokens_in
            tokens_out = llm_result.tokens_out

        source_ids = {s.work_canonical_id.lower() for s in sources}
        citations = _extract_citations(answer_text, source_ids)
        total_latency_ms = (time.perf_counter() - wall_start) * 1000.0

        return AnswerResponse(
            query=request.query,
            answer=answer_text,
            sources=list(sources),
            citations=citations,
            latency_ms=total_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            metadata=AnswerMetadata(
                trace_id=trace_id,
                pipeline_version=rag_response.metadata.version,
                llm_model=llm_model,
                llm_tokens_in=tokens_in,
                llm_tokens_out=tokens_out,
                style=effective_style,
                retrieval_metadata=rag_response.metadata,
            ),
        )

    async def stream_answer(  # noqa: PLR0915
        self,
        request: AnswerRequest,
    ) -> AsyncIterator[RetrievalDoneEvent | TokenEvent | CitationEvent | DoneEvent | ErrorEvent]:
        """Stream retrieval + LLM as SSE events.

        See :func:`src.answer.protocol.AnswerServiceProtocol.stream_answer`
        for the wire contract. Implementation mirrors :meth:`answer`
        for the retrieval-and-prompt setup and diverges at the LLM call,
        where it iterates :meth:`AsyncOpenRouterLLM.stream` and emits
        ``token`` events as deltas arrive.
        """
        wall_start = time.perf_counter()
        trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        effective_style: AnswerStyle = (
            request.style if request.style is not None else self._settings.answer_default_style
        )

        retrieval_request = QueryRequest(
            query=request.query,
            top_k=request.top_k,
            expand_pali=request.expand_pali,
            expand_definitional=request.expand_definitional,
            foundational_boost=request.foundational_boost,
            forbidden_works=request.forbidden_works,
        )
        retrieval_start = time.perf_counter()
        try:
            rag_response = await self._rag.query(retrieval_request)
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("stream_answer.retrieval_failed")
            yield ErrorEvent(code="retrieval_failed", message=str(exc))
            return
        retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000.0

        sources = list(rag_response.sources)
        yield RetrievalDoneEvent(
            sources=sources,
            retrieval_latency_ms=retrieval_latency_ms,
            pipeline_version=rag_response.metadata.version,
        )

        if not sources:
            # No retrieval hits → skip LLM, return empty answer.
            total_latency_ms = (time.perf_counter() - wall_start) * 1000.0
            yield DoneEvent(
                answer="",
                citations=[],
                latency_ms=total_latency_ms,
                llm_latency_ms=0.0,
                metadata=AnswerMetadata(
                    trace_id=trace_id,
                    pipeline_version=rag_response.metadata.version,
                    llm_model=self._llm.default_model,
                    llm_tokens_in=0,
                    llm_tokens_out=0,
                    style=effective_style,
                    retrieval_metadata=rag_response.metadata,
                ),
            )
            return

        source_ids = {s.work_canonical_id.lower() for s in sources}
        scanner = IncrementalCitationScanner(source_ids)
        user_message = _build_user_message(request.query, sources)
        llm_start = time.perf_counter()
        llm_model = self._llm.default_model
        tokens_in = 0
        tokens_out = 0

        try:
            async for chunk in self._llm.stream(
                system_prompt=build_system_prompt(effective_style),
                user_message=user_message,
                model=request.model,
                max_tokens=_MAX_TOKENS_BY_STYLE[effective_style],
            ):
                if chunk.delta:
                    yield TokenEvent(delta=chunk.delta)
                    for found in scanner.feed(chunk.delta):
                        yield CitationEvent(id=found.id, position=found.position)
                if chunk.tokens_in is not None:
                    tokens_in = chunk.tokens_in
                if chunk.tokens_out is not None:
                    tokens_out = chunk.tokens_out
                if chunk.model is not None:
                    llm_model = chunk.model
        except Exception as exc:
            logger.exception("stream_answer.llm_failed")
            yield ErrorEvent(code="llm_failed", message=str(exc))
            return

        llm_latency_ms = (time.perf_counter() - llm_start) * 1000.0
        total_latency_ms = (time.perf_counter() - wall_start) * 1000.0

        yield DoneEvent(
            answer=scanner.text,
            citations=scanner.citations,
            latency_ms=total_latency_ms,
            llm_latency_ms=llm_latency_ms,
            metadata=AnswerMetadata(
                trace_id=trace_id,
                pipeline_version=rag_response.metadata.version,
                llm_model=llm_model,
                llm_tokens_in=tokens_in,
                llm_tokens_out=tokens_out,
                style=effective_style,
                retrieval_metadata=rag_response.metadata,
            ),
        )


__all__ = [
    "AnswerService",
    "CitationFound",
    "IncrementalCitationScanner",
    "SYSTEM_PROMPT",
    "build_system_prompt",
]
