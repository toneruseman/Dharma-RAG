"""Integration tests for the SuttaCentral loader against a real Postgres.

These tests rely on the shared ``engine`` / ``db_session`` fixtures in
:mod:`tests.integration.conftest`, which create a throwaway
``dharma_test`` database, run every migration once per session, and
truncate mutable tables between tests. No other test suite writes to
the same database, so row-count assertions here are safe.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.frbr import Chunk, Expression, Instance, Work
from src.ingest.suttacentral.loader import load_directory, load_file
from src.ingest.suttacentral.parser import parse_bilara_file


def _write(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def sc_tree(tmp_path: Path) -> Path:
    """Two MN translations + matching Pāli roots.

    The shape mirrors bilara-data: ``{translation|root}/{lang}/{author}/
    sutta/{nikaya}/{uid}_{muid}.json``. Keeping both a root and a
    translation lets us verify that Work titles get populated from
    both languages.
    """
    root = tmp_path / "bilara-data"
    _write(
        root / "translation" / "en" / "sujato" / "sutta" / "mn" / "mn1_translation-en-sujato.json",
        {
            "mn1:0.1": "Middle Discourses 1 ",
            "mn1:0.2": "The Root of All Things ",
            "mn1:1.1": "So I have heard. ",
            "mn1:1.2": "At one time the Buddha was staying near Ukkaṭṭhā. ",
        },
    )
    _write(
        root / "translation" / "en" / "sujato" / "sutta" / "mn" / "mn2_translation-en-sujato.json",
        {
            "mn2:0.1": "Middle Discourses 2 ",
            "mn2:0.2": "All the Defilements ",
            "mn2:1.1": "So I have heard. ",
        },
    )
    _write(
        root / "root" / "pli" / "ms" / "sutta" / "mn" / "mn1_root-pli-ms.json",
        {
            "mn1:0.1": "Majjhima Nikāya 1 ",
            "mn1:0.2": "Mūlapariyāyasutta ",
        },
    )
    return root


# ---------------------------------------------------------------------------
# load_file
# ---------------------------------------------------------------------------


async def test_load_file_creates_full_frbr_hierarchy(
    db_session: AsyncSession,
    sc_tree: Path,
) -> None:
    path = (
        sc_tree
        / "translation"
        / "en"
        / "sujato"
        / "sutta"
        / "mn"
        / "mn1_translation-en-sujato.json"
    )
    bf = parse_bilara_file(path, sc_tree)

    result = await load_file(db_session, bf)
    await db_session.commit()

    assert not result.skipped
    # 1 parent + 1 child for this tiny sutta (all 4 segments fit under
    # a single parent and a single child by token count).
    assert result.chunks_inserted == 2

    work = (
        await db_session.execute(sa.select(Work).where(Work.canonical_id == "mn1"))
    ).scalar_one()
    assert work.title == "The Root of All Things"
    assert work.title_pali == "Mūlapariyāyasutta"
    assert work.tradition_code == "theravada"
    assert work.primary_language_code == "pli"
    assert work.metadata_json["nikaya"] == "mn"

    expressions = (
        (await db_session.execute(sa.select(Expression).where(Expression.work_id == work.id)))
        .scalars()
        .all()
    )
    assert len(expressions) == 1
    assert expressions[0].language_code == "eng"
    assert expressions[0].license == "CC0-1.0"
    assert expressions[0].metadata_json["author_slug"] == "sujato"

    instances = (
        (
            await db_session.execute(
                sa.select(Instance).where(Instance.expression_id == expressions[0].id)
            )
        )
        .scalars()
        .all()
    )
    assert len(instances) == 1
    assert instances[0].source_format == "bilara-json"
    assert len(instances[0].content_hash) == 64  # sha256 hex

    chunks = (
        (
            await db_session.execute(
                sa.select(Chunk)
                .where(Chunk.instance_id == instances[0].id)
                .order_by(Chunk.sequence)
            )
        )
        .scalars()
        .all()
    )
    assert len(chunks) == 2
    parent, child = chunks
    assert parent.is_parent is True
    assert parent.parent_chunk_id is None
    assert parent.metadata_json["segment_ids"] == ["mn1:0.1", "mn1:0.2", "mn1:1.1", "mn1:1.2"]
    # Parent text is the joined canonical text of all four segments.
    assert parent.text.startswith("Middle Discourses 1")
    assert "At one time the Buddha" in parent.text

    assert child.is_parent is False
    assert child.parent_chunk_id == parent.id
    assert child.metadata_json["position_in_parent"] == 0
    # Child covers the same segments when the parent is short enough.
    assert child.metadata_json["segment_ids"] == parent.metadata_json["segment_ids"]
    # ASCII fold column is populated on both kinds of chunk.
    assert parent.text_ascii_fold is not None and parent.text_ascii_fold.isascii()
    assert child.text_ascii_fold is not None


async def test_load_file_is_idempotent_via_content_hash(
    db_session: AsyncSession,
    sc_tree: Path,
) -> None:
    path = (
        sc_tree
        / "translation"
        / "en"
        / "sujato"
        / "sutta"
        / "mn"
        / "mn1_translation-en-sujato.json"
    )
    bf = parse_bilara_file(path, sc_tree)

    first = await load_file(db_session, bf)
    await db_session.commit()
    second = await load_file(db_session, bf)
    await db_session.commit()

    assert first.skipped is False
    assert second.skipped is True
    # Second run must not insert any new rows.
    total_instances = (
        await db_session.execute(sa.select(sa.func.count()).select_from(Instance))
    ).scalar_one()
    total_chunks = (
        await db_session.execute(sa.select(sa.func.count()).select_from(Chunk))
    ).scalar_one()
    assert total_instances == 1
    # 1 parent + 1 child after structural chunking of a 4-segment sutta.
    assert total_chunks == 2


async def test_load_file_rejects_unknown_author(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    root = tmp_path / "bilara-data"
    path = (
        root / "translation" / "en" / "nobody" / "sutta" / "mn" / "mn1_translation-en-nobody.json"
    )
    _write(path, {"mn1:0.1": "Hello "})
    bf = parse_bilara_file(path, root)
    with pytest.raises(LookupError, match="author_t has no row for slug"):
        await load_file(db_session, bf)


# ---------------------------------------------------------------------------
# load_directory
# ---------------------------------------------------------------------------


async def test_load_directory_handles_multiple_works(
    db_session: AsyncSession,
    sc_tree: Path,
) -> None:
    counters = await load_directory(
        db_session,
        sc_tree,
        author="sujato",
        language="en",
        nikayas=["mn"],
        commit_every=1,
    )
    assert counters["files_seen"] == 2
    assert counters["files_loaded"] == 2
    assert counters["files_skipped"] == 0
    # Each short sutta collapses to 1 parent + 1 child under default
    # token targets, so 2 files × 2 chunks = 4.
    assert counters["chunks_inserted"] == 4

    works = (await db_session.execute(sa.select(Work))).scalars().all()
    assert {w.canonical_id for w in works} == {"mn1", "mn2"}

    # Every child must point at a real parent.
    all_chunks = (await db_session.execute(sa.select(Chunk))).scalars().all()
    parents_by_id = {c.id: c for c in all_chunks if c.is_parent}
    for chunk in all_chunks:
        if not chunk.is_parent:
            assert chunk.parent_chunk_id in parents_by_id


async def test_cleaner_produces_ascii_fold_for_pali_segments(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    """End-to-end check that the cleaner is wired into ingest.

    We use a translation segment full of Pali diacritics — the resulting
    chunk must carry the canonical text unchanged and an ASCII-only
    fold next to it, so BM25 can match ``satipatthana`` queries against
    ``satipaṭṭhāna`` indexed text.
    """
    root = tmp_path / "bilara-data"
    translation = (
        root / "translation" / "en" / "sujato" / "sutta" / "mn" / "mn10_translation-en-sujato.json"
    )
    _write(
        translation,
        {
            "mn10:0.1": "Middle Discourses 10 ",
            "mn10:0.2": "Satipaṭṭhānasutta ",
            "mn10:1.1": "Evaṃ me sutaṃ—saṅghe nibbānañca. ",
        },
    )
    bf = parse_bilara_file(translation, root)
    await load_file(db_session, bf)
    await db_session.commit()

    chunks = (await db_session.execute(sa.select(Chunk).order_by(Chunk.sequence))).scalars().all()
    # Three short segments collapse into one parent + one child.
    assert len(chunks) == 2
    parent, child = chunks
    assert parent.is_parent is True
    assert child.is_parent is False and child.parent_chunk_id == parent.id

    # Canonical text preserves diacritics; both kinds of chunk carry it.
    assert "Satipaṭṭhānasutta" in parent.text
    assert "nibbānañca" in parent.text
    assert "Satipaṭṭhānasutta" in child.text

    # ASCII fold exists on both rows, diacritics stripped, em-dash kept.
    assert parent.text_ascii_fold is not None
    assert child.text_ascii_fold is not None
    assert "Satipatthanasutta" in parent.text_ascii_fold
    assert "nibbananca" in parent.text_ascii_fold
    fold_without_dash = parent.text_ascii_fold.replace("—", " ")
    assert fold_without_dash.isascii()


# ---------------------------------------------------------------------------
# scripts/rechunk.py — idempotency
# ---------------------------------------------------------------------------


async def test_rechunk_on_fresh_ingest_is_noop(
    db_session: AsyncSession,
    sc_tree: Path,
) -> None:
    """Running rechunk over an Instance already in parent/child form skips it.

    Day-4 ingest produced flat chunks that had to be migrated on day 7.
    From day 7 onwards the loader emits parent/child directly, so a
    later rechunk has nothing to do. This test guards that invariant
    so the script stays safe to re-run as a cron.
    """
    from scripts.rechunk import _rechunk_one_instance

    path = (
        sc_tree
        / "translation"
        / "en"
        / "sujato"
        / "sutta"
        / "mn"
        / "mn1_translation-en-sujato.json"
    )
    bf = parse_bilara_file(path, sc_tree)
    await load_file(db_session, bf)
    await db_session.commit()

    instance_id = (await db_session.execute(sa.select(Instance.id).limit(1))).scalar_one()

    deleted, inserted, skipped = await _rechunk_one_instance(db_session, instance_id)
    assert (deleted, inserted, skipped) == (0, 0, 1)

    # Running again must also skip and never touch data.
    chunks_before = (
        await db_session.execute(sa.select(sa.func.count()).select_from(Chunk))
    ).scalar_one()
    deleted2, inserted2, skipped2 = await _rechunk_one_instance(db_session, instance_id)
    assert (deleted2, inserted2, skipped2) == (0, 0, 1)
    chunks_after = (
        await db_session.execute(sa.select(sa.func.count()).select_from(Chunk))
    ).scalar_one()
    assert chunks_after == chunks_before
