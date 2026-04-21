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
    assert result.chunks_inserted == 4

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
    assert len(chunks) == 4
    assert [c.segment_id for c in chunks] == [
        "mn1:0.1",
        "mn1:0.2",
        "mn1:1.1",
        "mn1:1.2",
    ]
    assert all(c.is_parent is False for c in chunks)
    assert chunks[0].text == "Middle Discourses 1 "


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
    assert total_chunks == 4


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
    assert counters["chunks_inserted"] == 4 + 3  # mn1 has 4, mn2 has 3

    works = (await db_session.execute(sa.select(Work))).scalars().all()
    assert {w.canonical_id for w in works} == {"mn1", "mn2"}
