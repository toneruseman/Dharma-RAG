"""Integration tests for :func:`src.retrieval.bm25.search`.

These tests run against the ``dharma_test`` DB seeded by
``tests/integration/conftest.py``. We create a tiny synthetic corpus
(one Work, one Expression, one Instance, a handful of chunks with
controlled text) and assert BM25 ranks them the way we expect.

Goals:
* Confirm that migration 003's ``fts_vector`` is populated on insert.
* Confirm ``ts_rank_cd`` ranks term-dense chunks above term-sparse ones.
* Confirm diacritic folding works end-to-end (query with diacritics
  retrieves chunks whose ``text_ascii_fold`` has no diacritics).
* Confirm ``include_parents`` gating.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.frbr import Chunk, Expression, Instance, Work
from src.processing.cleaner import to_ascii_fold
from src.retrieval.bm25 import BM25Hit, search

pytestmark = pytest.mark.integration


async def _make_work(db_session: AsyncSession, *, canonical_id: str) -> Work:
    work = Work(
        canonical_id=canonical_id,
        title=f"Fixture {canonical_id}",
        title_pali=None,
        tradition_code="theravada",
        primary_language_code="pli",
        metadata_json={},
    )
    db_session.add(work)
    await db_session.flush()
    return work


async def _make_expression_and_instance(db_session: AsyncSession, *, work: Work) -> Instance:
    # Any seeded author works — sujato is seeded in migration 002.
    author_id = (
        await db_session.execute(sa.text("SELECT id FROM author_t WHERE slug = 'sujato'"))
    ).scalar_one()

    expr = Expression(
        work_id=work.id,
        author_id=author_id,
        language_code="eng",
        title=None,
        license="CC0-1.0",
        consent_ledger_ref=None,
        metadata_json={},
    )
    db_session.add(expr)
    await db_session.flush()

    inst = Instance(
        expression_id=expr.id,
        source_url=f"test://fixture/{work.canonical_id}",
        source_format="test",
        retrieved_at=datetime.now(UTC),
        content_hash=uuid4().hex,
        storage_path=None,
        metadata_json={},
    )
    db_session.add(inst)
    await db_session.flush()
    return inst


async def _add_chunk(
    db_session: AsyncSession,
    *,
    instance: Instance,
    sequence: int,
    text: str,
    is_parent: bool = False,
    segment_id: str | None = None,
) -> Chunk:
    chunk = Chunk(
        instance_id=instance.id,
        parent_chunk_id=None,
        sequence=sequence,
        text=text,
        text_ascii_fold=to_ascii_fold(text),
        token_count=len(text.split()),
        is_parent=is_parent,
        segment_id=segment_id,
        metadata_json={},
    )
    db_session.add(chunk)
    await db_session.flush()
    return chunk


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty_list(db_session: AsyncSession) -> None:
    hits = await search(db_session, "")
    assert hits == []


@pytest.mark.asyncio
async def test_search_returns_zero_when_no_match(db_session: AsyncSession) -> None:
    work = await _make_work(db_session, canonical_id="testwork1")
    inst = await _make_expression_and_instance(db_session, work=work)
    await _add_chunk(db_session, instance=inst, sequence=0, text="the buddha taught")
    hits = await search(db_session, "quantum mechanics")
    assert hits == []


@pytest.mark.asyncio
async def test_search_ranks_term_dense_chunk_first(db_session: AsyncSession) -> None:
    """BM25/ts_rank_cd should rank a chunk with many occurrences of the
    query term above one with a single passing mention.
    """
    work = await _make_work(db_session, canonical_id="testwork2")
    inst = await _make_expression_and_instance(db_session, work=work)
    sparse = await _add_chunk(
        db_session,
        instance=inst,
        sequence=0,
        text="The mendicant sat quietly for a long time before speaking.",
    )
    dense = await _add_chunk(
        db_session,
        instance=inst,
        sequence=1,
        text=(
            "Mendicant, a mendicant meditates as a mendicant should. "
            "So the mendicant, being a mendicant, continues mendicant practice."
        ),
    )
    hits = await search(db_session, "mendicant", limit=5)
    assert hits, "expected at least one hit"
    assert hits[0].chunk_id == dense.id
    # Sanity: the sparse chunk may or may not appear depending on rank
    # cutoff, but if it does, its score must be lower.
    for hit in hits[1:]:
        if hit.chunk_id == sparse.id:
            assert hit.score < hits[0].score


@pytest.mark.asyncio
async def test_search_folds_diacritics_in_query(db_session: AsyncSession) -> None:
    """A query with diacritics should match ASCII-folded text."""
    work = await _make_work(db_session, canonical_id="testwork3")
    inst = await _make_expression_and_instance(db_session, work=work)
    target = await _add_chunk(
        db_session,
        instance=inst,
        sequence=0,
        text="At Sāvatthī the venerable Anāthapiṇḍika approached the Buddha.",
        segment_id="testwork3:0.1",
    )
    # Query carries diacritics; index stores diacritic-free fold.
    hits = await search(db_session, "Sāvatthī Anāthapiṇḍika")
    assert hits
    assert hits[0].chunk_id == target.id
    assert hits[0].work_canonical_id == "testwork3"
    assert hits[0].segment_id == "testwork3:0.1"


@pytest.mark.asyncio
async def test_search_folds_ascii_query_matches_diacritic_text(
    db_session: AsyncSession,
) -> None:
    """The reverse: a user types pure ASCII, the text has diacritics —
    BM25 must still match (because the fold column is what is indexed).
    """
    work = await _make_work(db_session, canonical_id="testwork4")
    inst = await _make_expression_and_instance(db_session, work=work)
    target = await _add_chunk(
        db_session,
        instance=inst,
        sequence=0,
        text="The town of Sāvatthī was home to Anāthapiṇḍika the householder.",
    )
    hits = await search(db_session, "savatthi anathapindika")
    assert hits
    assert hits[0].chunk_id == target.id


@pytest.mark.asyncio
async def test_search_excludes_parents_by_default(db_session: AsyncSession) -> None:
    work = await _make_work(db_session, canonical_id="testwork5")
    inst = await _make_expression_and_instance(db_session, work=work)
    parent = await _add_chunk(
        db_session,
        instance=inst,
        sequence=0,
        text="Buddha buddha buddha buddha buddha.",
        is_parent=True,
    )
    child = await _add_chunk(
        db_session,
        instance=inst,
        sequence=1,
        text="Buddha.",
        is_parent=False,
    )
    # Default: children only. Parent must be filtered out even though it
    # would score higher by term density.
    hits = await search(db_session, "buddha", limit=10)
    hit_ids = {h.chunk_id for h in hits}
    assert child.id in hit_ids
    assert parent.id not in hit_ids

    # include_parents=True flips it.
    hits2 = await search(db_session, "buddha", limit=10, include_parents=True)
    hit_ids2 = {h.chunk_id for h in hits2}
    assert child.id in hit_ids2
    assert parent.id in hit_ids2


@pytest.mark.asyncio
async def test_search_respects_limit(db_session: AsyncSession) -> None:
    work = await _make_work(db_session, canonical_id="testwork6")
    inst = await _make_expression_and_instance(db_session, work=work)
    for i in range(5):
        await _add_chunk(db_session, instance=inst, sequence=i, text=f"chunk {i} mentions buddha")
    hits = await search(db_session, "buddha", limit=3)
    assert len(hits) == 3


@pytest.mark.asyncio
async def test_search_returns_dataclass_instances(db_session: AsyncSession) -> None:
    work = await _make_work(db_session, canonical_id="testwork7")
    inst = await _make_expression_and_instance(db_session, work=work)
    await _add_chunk(db_session, instance=inst, sequence=0, text="the buddha taught")
    hits = await search(db_session, "buddha")
    assert hits
    assert all(isinstance(h, BM25Hit) for h in hits)
    assert all(isinstance(h.score, float) for h in hits)
