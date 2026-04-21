"""Persist SuttaCentral bilara translations into the FRBR schema.

This layer is the first piece that actually touches Postgres. It takes
``BilaraFile`` objects emitted by :mod:`parser` and materialises them as
Work → Expression → Instance → Chunk rows.

Design notes
------------
* **Idempotency via content hash.** Re-running the loader on an
  unchanged file is a no-op: we compute a sha256 of the raw bytes and
  short-circuit when an ``Instance`` with that hash already exists.
  This makes "nightly ingest" a safe cron job.
* **No premature chunking.** Day 4's scope is "one chunk per bilara
  segment". Parent/child pairing, cleaning, and tokenisation land in
  rag-day-06/07 once the cleaner is in place.
* **Pure async.** Everything takes an ``AsyncSession``; the loader
  never opens its own connection. This lets a caller ingest in small
  per-file transactions (default) or batch many files into one.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.frbr import Chunk, Expression, Instance, Work
from src.db.models.lookups import Author, Language
from src.ingest.suttacentral.models import BilaraFile, FileKind, Segment
from src.ingest.suttacentral.parser import iter_bilara_files, iter_segments

# SuttaCentral's bilara-data is released under CC0-1.0. The license is
# stamped onto every Expression we create so the corpus is auditable
# without joining back to the original source tree.
SC_LICENSE: Final[str] = "CC0-1.0"
SC_CONSENT_LEDGER_REF: Final[str] = "public-domain/suttacentral-cc0.yaml"
SC_SOURCE_FORMAT: Final[str] = "bilara-json"

# Tradition assumed for the Pāli canon. Non-Theravāda bilara content
# (e.g. Chinese Āgamas under ``lzh``) is out of scope for day 4.
SC_TRADITION: Final[str] = "theravada"

# ISO 639-1 → ISO 639-3 mapping for the languages we seed in migration
# 001. Bilara file names carry the 639-1/regional short code; our
# ``language_t`` table is keyed by 639-3. Anything not in this map is
# rejected at ingest time rather than silently coerced.
_LANG_MAP: Final[dict[str, str]] = {
    "en": "eng",
    "pli": "pli",
    "de": "deu",
    "fr": "fra",
    "ru": "rus",
    "zh": "zho",
    "lzh": "lzh",
    "bo": "bod",
    "san": "san",
    "es": "spa",
    "it": "ita",
    "pt": "por",
    "ja": "jpn",
    "jpn": "jpn",
}


@dataclass(frozen=True, slots=True)
class LoadResult:
    """Summary of a single-file load.

    ``chunks_inserted == 0`` together with ``skipped`` means the file
    was already present (content hash match). That is the happy-path
    signal for idempotent re-runs.
    """

    work_id: UUID
    expression_id: UUID
    instance_id: UUID
    chunks_inserted: int
    skipped: bool


async def load_file(
    session: AsyncSession,
    bf: BilaraFile,
    *,
    tradition: str = SC_TRADITION,
    license_str: str = SC_LICENSE,
    consent_ledger_ref: str = SC_CONSENT_LEDGER_REF,
    primary_language_override: str | None = None,
) -> LoadResult:
    """Load one bilara translation file into the corpus schema.

    Parameters
    ----------
    session:
        Caller-owned async session. The function does not commit — the
        caller controls transaction boundaries.
    bf:
        File to load. Must be a ``FileKind.TRANSLATION``; roots are
        used only to enrich Work titles and are not ingested as
        Expressions themselves.
    tradition:
        Tradition code to stamp on new Work rows. Defaults to Theravāda.
    license_str, consent_ledger_ref:
        Stamped on the Expression; these travel with every chunk
        downstream so the app layer can enforce license rules.
    primary_language_override:
        Override the auto-detected Work primary language. Useful when
        the root text for a given translation is not Pāli (e.g. an
        Āgama translated from lzh). ``None`` = use ``pli``.

    Raises
    ------
    ValueError:
        If ``bf`` is a root file, if the language is unknown, or if
        the JSON payload is malformed.
    LookupError:
        If the bilara author slug is not present in ``author_t``. The
        loader deliberately does not auto-create authors — translator
        attribution is important enough to require explicit seeding.
    """
    if bf.kind is not FileKind.TRANSLATION:
        raise ValueError(f"load_file expects a translation file, got {bf.kind}")

    expression_lang = _iso639_3(bf.language)
    work_lang = _iso639_3(primary_language_override or "pli")

    # Validate FK targets up-front so we fail loudly on a missing
    # seed rather than producing a half-loaded expression.
    await _require_language(session, expression_lang)
    await _require_language(session, work_lang)
    author = await _require_author(session, bf.author)

    # Content hash before any DB writes so we can short-circuit.
    raw_bytes = bf.path.read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    existing_instance = (
        await session.execute(
            sa.select(Instance).where(Instance.content_hash == content_hash).limit(1)
        )
    ).scalar_one_or_none()
    if existing_instance is not None:
        return LoadResult(
            work_id=(
                await session.execute(
                    sa.select(Expression.work_id).where(
                        Expression.id == existing_instance.expression_id
                    )
                )
            ).scalar_one(),
            expression_id=existing_instance.expression_id,
            instance_id=existing_instance.id,
            chunks_inserted=0,
            skipped=True,
        )

    # Parse the translation JSON once; we need segments for chunks
    # and segment[1] for the descriptive title.
    segments = list(iter_segments(bf))
    if not segments:
        raise ValueError(f"{bf.path}: translation file has no segments")

    english_title = _pick_title(segments, uid=bf.uid)
    pali_title = _pick_root_title(bf)

    work = await _get_or_create_work(
        session,
        canonical_id=bf.uid,
        title=english_title,
        title_pali=pali_title,
        tradition_code=tradition,
        primary_language_code=work_lang,
        nikaya=bf.nikaya,
    )
    expression = await _get_or_create_expression(
        session,
        work_id=work.id,
        author=author,
        language_code=expression_lang,
        title=english_title,
        license_str=license_str,
        consent_ledger_ref=consent_ledger_ref,
    )

    instance = Instance(
        expression_id=expression.id,
        source_url=f"suttacentral://{bf.kind.value}/{bf.language}/{bf.author}/{bf.uid}",
        source_format=SC_SOURCE_FORMAT,
        retrieved_at=datetime.now(UTC),
        content_hash=content_hash,
        storage_path=str(bf.path),
        metadata_json={
            "bilara_file_bytes": len(raw_bytes),
            "nikaya": bf.nikaya,
        },
    )
    session.add(instance)
    await session.flush()  # populate instance.id for FK on chunks

    for seq, seg in enumerate(segments):
        text = seg.text
        session.add(
            Chunk(
                instance_id=instance.id,
                sequence=seq,
                text=text,
                # Normalisation / ASCII fold arrives in the cleaner
                # (rag-day-06); leave NULL for now so downstream knows
                # this chunk has not been processed yet.
                text_ascii_fold=None,
                token_count=max(1, len(text.split())),
                is_parent=False,
                segment_id=seg.segment_id,
                metadata_json={"stage": "bilara-raw"},
            )
        )
    await session.flush()

    return LoadResult(
        work_id=work.id,
        expression_id=expression.id,
        instance_id=instance.id,
        chunks_inserted=len(segments),
        skipped=False,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso639_3(code: str) -> str:
    """Translate a bilara language short-code to the ``language_t`` key."""
    try:
        return _LANG_MAP[code]
    except KeyError as exc:
        raise ValueError(
            f"Unknown bilara language code {code!r}; extend _LANG_MAP or "
            "seed the language in language_t first."
        ) from exc


async def _require_language(session: AsyncSession, code: str) -> None:
    exists = (
        await session.execute(sa.select(Language.code).where(Language.code == code))
    ).scalar_one_or_none()
    if exists is None:
        raise LookupError(
            f"language_t has no row for code={code!r}; add it via an Alembic migration."
        )


async def _require_author(session: AsyncSession, slug: str) -> Author:
    author = (
        await session.execute(sa.select(Author).where(Author.slug == slug))
    ).scalar_one_or_none()
    if author is None:
        raise LookupError(
            f"author_t has no row for slug={slug!r}; seed it via an Alembic migration "
            "before ingesting this author's translations."
        )
    return author


async def _get_or_create_work(
    session: AsyncSession,
    *,
    canonical_id: str,
    title: str,
    title_pali: str | None,
    tradition_code: str,
    primary_language_code: str,
    nikaya: str,
) -> Work:
    work = (
        await session.execute(sa.select(Work).where(Work.canonical_id == canonical_id))
    ).scalar_one_or_none()
    if work is not None:
        return work
    work = Work(
        canonical_id=canonical_id,
        title=title,
        title_pali=title_pali,
        tradition_code=tradition_code,
        primary_language_code=primary_language_code,
        metadata_json={"nikaya": nikaya, "source": "suttacentral"},
    )
    session.add(work)
    await session.flush()
    return work


async def _get_or_create_expression(
    session: AsyncSession,
    *,
    work_id: UUID,
    author: Author,
    language_code: str,
    title: str,
    license_str: str,
    consent_ledger_ref: str,
) -> Expression:
    expression = (
        await session.execute(
            sa.select(Expression).where(
                Expression.work_id == work_id,
                Expression.author_id == author.id,
                Expression.language_code == language_code,
            )
        )
    ).scalar_one_or_none()
    if expression is not None:
        return expression
    expression = Expression(
        work_id=work_id,
        author_id=author.id,
        language_code=language_code,
        title=title,
        license=license_str,
        consent_ledger_ref=consent_ledger_ref,
        metadata_json={"source": "suttacentral", "author_slug": author.slug},
    )
    session.add(expression)
    await session.flush()
    return expression


def _pick_title(segments: list[Segment], *, uid: str) -> str:
    """Pick a human-readable title from a translation's segments.

    Bilara convention: segment ``{uid}:0.1`` is the collection label
    ("Middle Discourses 1") and ``{uid}:0.2`` is the descriptive title
    ("The Root of All Things"). We prefer 0.2 — it's what a reader
    actually recognises as the sutta's name.
    """
    for preferred in (f"{uid}:0.2", f"{uid}:0.1"):
        for seg in segments:
            if seg.segment_id == preferred and seg.text.strip():
                return seg.text.strip()[:512]
    # Fallback: the first non-empty segment, or the uid itself.
    for seg in segments:
        if seg.text.strip():
            return seg.text.strip()[:512]
    return uid


def _pick_root_title(bf: BilaraFile) -> str | None:
    """Look next to the translation for a matching root-pli-ms file.

    Bilara places root texts under ``root/{lang}/{author}/sutta/{nikaya}/
    {uid}_root-{lang}-{author}.json``. We only bother with Pāli Mahāsaṅgīti
    here; other root traditions are handled when they become relevant.
    Failure to find a root file is *not* an error — many works have
    translations before any root text has been typeset.
    """
    # Walk up to the bilara repo root: translation/{lang}/{author}/sutta/{nikaya}/file.json
    # ⇒ the path has a ``translation`` part we replace with ``root``.
    parts = bf.path.parts
    try:
        idx = parts.index("translation")
    except ValueError:
        return None
    root_parts = list(parts)
    root_parts[idx] = "root"
    # Swap lang + author segments; hardcode to pli/ms for the Pāli canon.
    root_parts[idx + 1] = "pli"
    root_parts[idx + 2] = "ms"
    root_filename = f"{bf.uid}_root-pli-ms.json"
    root_parts[-1] = root_filename
    root_path = Path(*root_parts)
    if not root_path.exists():
        return None
    try:
        with root_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    for key in (f"{bf.uid}:0.2", f"{bf.uid}:0.1"):
        text = data.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()[:512]
    return None


async def load_directory(
    session: AsyncSession,
    bilara_root: Path,
    *,
    author: str,
    language: str,
    nikayas: list[str] | None = None,
    commit_every: int = 50,
) -> dict[str, int]:
    """Iterate a bilara tree and ingest every matching translation.

    Returns a counters dict (``files_seen``, ``files_skipped``,
    ``chunks_inserted``) for the caller to log. Commits every
    ``commit_every`` files so a crash mid-run loses at most that many.
    """
    counters = {"files_seen": 0, "files_loaded": 0, "files_skipped": 0, "chunks_inserted": 0}
    batch_since_commit = 0
    target_nikayas = set(nikayas) if nikayas else None

    for bf in iter_bilara_files(
        bilara_root,
        kind=FileKind.TRANSLATION,
        language=language,
        author=author,
    ):
        if target_nikayas is not None and bf.nikaya not in target_nikayas:
            continue
        counters["files_seen"] += 1
        result = await load_file(session, bf)
        if result.skipped:
            counters["files_skipped"] += 1
        else:
            counters["files_loaded"] += 1
            counters["chunks_inserted"] += result.chunks_inserted
        batch_since_commit += 1
        if batch_since_commit >= commit_every:
            await session.commit()
            batch_since_commit = 0
    if batch_since_commit > 0:
        await session.commit()
    return counters
