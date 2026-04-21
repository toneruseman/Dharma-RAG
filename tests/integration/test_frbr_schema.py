"""Tests that the FRBR schema and its seed data land in the DB correctly."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Language, Tradition


async def test_tradition_t_seeded(db_session: AsyncSession) -> None:
    """Migration 001 seeds the full list of traditions."""
    result = await db_session.execute(sa.select(Tradition).order_by(Tradition.code))
    codes = [row.code for row in result.scalars()]
    assert codes == [
        "chan",
        "mahayana",
        "pragmatic_dharma",
        "secular",
        "theravada",
        "vajrayana",
        "zen",
    ]


async def test_language_t_seeded(db_session: AsyncSession) -> None:
    """Pali and the core scholarly languages are present."""
    result = await db_session.execute(sa.select(Language).order_by(Language.code))
    rows = list(result.scalars())
    codes = {row.code for row in rows}
    # Must-haves for Phase 1.
    assert {"pli", "san", "bod", "zho", "eng", "rus"}.issubset(codes)
    # Pali keeps its Latin transliteration marker.
    pli = next(row for row in rows if row.code == "pli")
    assert pli.name == "Pāli"
    assert pli.script == "Latn"


async def test_schema_has_frbr_tables(db_session: AsyncSession) -> None:
    """All FRBR and lookup tables are present after migration."""
    result = await db_session.execute(
        sa.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    )
    tables = {row[0] for row in result}
    expected = {
        "alembic_version",
        "author_t",
        "chunk",
        "expression",
        "instance",
        "language_t",
        "tradition_t",
        "work",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


async def test_work_canonical_id_unique(db_session: AsyncSession) -> None:
    """The unique index on work.canonical_id is enforced."""
    from src.db.models import Work

    w1 = Work(
        canonical_id="mn10",
        title="Satipaṭṭhāna Sutta",
        tradition_code="theravada",
        primary_language_code="pli",
    )
    db_session.add(w1)
    await db_session.commit()

    w2 = Work(
        canonical_id="mn10",  # duplicate
        title="Satipaṭṭhāna Sutta (duplicate)",
        tradition_code="theravada",
        primary_language_code="pli",
    )
    db_session.add(w2)
    import sqlalchemy.exc

    try:
        await db_session.commit()
    except sqlalchemy.exc.IntegrityError:
        await db_session.rollback()
    else:
        raise AssertionError(
            "duplicate canonical_id should raise IntegrityError but commit succeeded"
        )
