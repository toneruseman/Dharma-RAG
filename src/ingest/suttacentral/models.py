"""Dataclasses for SuttaCentral bilara files and segments.

These are pure value objects: no I/O, no DB, no framework code. They
mirror the on-disk layout of ``bilara-data`` closely enough to be a
faithful parse target, while also carrying the FRBR-aligned fields the
rest of the pipeline will need (language, author, sutta uid, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class FileKind(StrEnum):
    """High-level category of a bilara JSON file.

    We only model the three kinds Phase 1 cares about; ``variant``,
    ``reference``, ``html`` and ``comment`` are ignored at parse time.
    """

    TRANSLATION = "translation"
    ROOT = "root"


@dataclass(frozen=True, slots=True)
class BilaraFile:
    """Metadata about a single bilara JSON file on disk.

    ``muid`` is SuttaCentral's "media UID" — the compound identifier
    that the bilara repository stamps onto every file name, e.g.
    ``translation-en-sujato``. We split it into ``kind``/``language``/
    ``author`` at parse time so consumers don't have to re-derive it.

    Fields
    ------
    path:
        Absolute path to the JSON file on disk.
    uid:
        SuttaCentral sutta/text UID (``mn1``, ``dn2``, ``an1.1-10``).
        This is the stable identifier we use as ``work.canonical_id``.
    kind:
        Whether this is a translation or the root-language source text.
    language:
        ISO 639-1/639-3 language code as it appears in the file name
        (``en``, ``pli``, ``de``, ...). We do not normalise here —
        normalisation happens when we match against ``language_t``.
    author:
        Translator or root-edition slug (``sujato``, ``ms``,
        ``brahmali``). Maps to ``author_t.slug`` downstream.
    nikaya:
        Top-level collection the file lives in (``mn``, ``dn``,
        ``sn``, ``an``, ``kn``, ...). Derived from the directory
        structure, not parsed from the uid — safer for outliers.
    """

    path: Path
    uid: str
    kind: FileKind
    language: str
    author: str
    nikaya: str


@dataclass(frozen=True, slots=True)
class Segment:
    """One line of text from a bilara file.

    Bilara keys segments as ``{uid}:{paragraph}.{sentence}[.{word}]``.
    We keep the raw ``segment_id`` verbatim because SuttaCentral's
    parallels and cross-references depend on this exact string — any
    reformatting would break joins with ``parallels.json`` later.
    """

    segment_id: str
    text: str
    source: BilaraFile
