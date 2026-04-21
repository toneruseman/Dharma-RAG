"""ORM round-trip tests for the FRBR hierarchy.

We create a realistic mini-corpus (one Work, two English Expressions,
one Instance per Expression, parent + child chunks) and verify:

- every entity persists and reloads with the expected columns
- cascade deletes tear down the whole hierarchy
- parent/child chunk linking works as designed

Every test runs inside the ``db_session`` fixture which truncates
mutable tables afterwards, so tests are independent.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Author, Chunk, Expression, Instance, Work


async def test_full_frbr_roundtrip(db_session: AsyncSession) -> None:
    """Create the full Work → Expression → Instance → Chunk chain."""
    author = Author(
        name="Bhikkhu Bodhi",
        author_type="translator",
        tradition_code="theravada",
        birth_year=1944,
        bio="American Theravada monk and prolific Pali translator.",
    )
    db_session.add(author)
    await db_session.flush()

    work = Work(
        canonical_id="mn10",
        title="Satipaṭṭhāna Sutta",
        title_pali="Satipaṭṭhāna Sutta",
        tradition_code="theravada",
        primary_language_code="pli",
    )
    db_session.add(work)
    await db_session.flush()

    expression = Expression(
        work_id=work.id,
        author_id=author.id,
        language_code="eng",
        title="The Foundations of Mindfulness",
        publication_year=1995,
        license="CC-BY-NC-4.0",
        consent_ledger_ref="open-license/access-to-insight.yaml",
    )
    db_session.add(expression)
    await db_session.flush()

    instance = Instance(
        expression_id=expression.id,
        source_url="https://www.accesstoinsight.org/tipitaka/mn/mn.010.nysa.html",
        source_format="html",
        retrieved_at=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
        content_hash="a" * 64,
        storage_path="data/raw/ati/mn010_nysa.html",
    )
    db_session.add(instance)
    await db_session.flush()

    parent_chunk = Chunk(
        instance_id=instance.id,
        sequence=0,
        text="The Blessed One was staying among the Kurus at Kammāsadhamma...",
        text_ascii_fold="The Blessed One was staying among the Kurus at Kammasadhamma...",
        token_count=1800,
        is_parent=True,
        segment_id="mn10:1.0",
    )
    db_session.add(parent_chunk)
    await db_session.flush()

    child_a = Chunk(
        instance_id=instance.id,
        parent_chunk_id=parent_chunk.id,
        sequence=1,
        text="And what, monks, are the four foundations of mindfulness?",
        text_ascii_fold="And what, monks, are the four foundations of mindfulness?",
        token_count=380,
        is_parent=False,
        segment_id="mn10:1.1",
        speaker="Buddha",
        audience="bhikkhus",
    )
    child_b = Chunk(
        instance_id=instance.id,
        parent_chunk_id=parent_chunk.id,
        sequence=2,
        text="Here, a monk abides contemplating the body as body...",
        text_ascii_fold="Here, a monk abides contemplating the body as body...",
        token_count=370,
        is_parent=False,
        segment_id="mn10:1.2",
        speaker="Buddha",
        pericope_id="satipatthana_formula_body",
    )
    db_session.add_all([child_a, child_b])
    await db_session.commit()

    # --- Verify via a fresh query that everything roundtripped. ---
    reloaded = await db_session.execute(sa.select(Work).where(Work.canonical_id == "mn10"))
    reloaded_work = reloaded.scalar_one()
    assert reloaded_work.title_pali == "Satipaṭṭhāna Sutta"
    assert reloaded_work.is_restricted is False

    chunks = await db_session.execute(
        sa.select(Chunk).where(Chunk.instance_id == instance.id).order_by(Chunk.sequence)
    )
    chunk_rows = list(chunks.scalars())
    assert len(chunk_rows) == 3
    assert chunk_rows[0].is_parent is True
    assert chunk_rows[1].parent_chunk_id == parent_chunk.id
    assert chunk_rows[2].pericope_id == "satipatthana_formula_body"


async def test_cascade_delete_work_removes_hierarchy(db_session: AsyncSession) -> None:
    """Deleting a Work cascades to Expressions, Instances, Chunks."""
    work = Work(
        canonical_id="dn22",
        title="Mahāsatipaṭṭhāna Sutta",
        tradition_code="theravada",
        primary_language_code="pli",
    )
    db_session.add(work)
    await db_session.flush()

    expression = Expression(
        work_id=work.id,
        language_code="eng",
        license="CC0",
    )
    db_session.add(expression)
    await db_session.flush()

    instance = Instance(
        expression_id=expression.id,
        source_url="https://suttacentral.net/dn22/en/sujato",
        source_format="json",
        retrieved_at=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
        content_hash="b" * 64,
    )
    db_session.add(instance)
    await db_session.flush()

    chunk = Chunk(
        instance_id=instance.id,
        sequence=0,
        text="lorem ipsum",
        token_count=10,
    )
    db_session.add(chunk)
    await db_session.commit()

    # Delete the Work; expect cascade to remove Expression, Instance, Chunk.
    await db_session.delete(work)
    await db_session.commit()

    remaining_expr = await db_session.execute(sa.select(sa.func.count(Expression.id)))
    remaining_inst = await db_session.execute(sa.select(sa.func.count(Instance.id)))
    remaining_chunk = await db_session.execute(sa.select(sa.func.count(Chunk.id)))
    assert remaining_expr.scalar() == 0
    assert remaining_inst.scalar() == 0
    assert remaining_chunk.scalar() == 0


async def test_restricted_flag_defaults_false(db_session: AsyncSession) -> None:
    """Work.is_restricted defaults to False so accidental omission never
    leaks a Vajrayana text."""
    work = Work(
        canonical_id="sn56.11",
        title="Dhammacakkappavattana Sutta",
        tradition_code="theravada",
        primary_language_code="pli",
    )
    db_session.add(work)
    await db_session.commit()

    reloaded = await db_session.execute(sa.select(Work).where(Work.canonical_id == "sn56.11"))
    assert reloaded.scalar_one().is_restricted is False
