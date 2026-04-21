"""File discovery and JSON parsing for SuttaCentral bilara-data.

Design goals:

* Pure functions over a local directory tree — no network, no DB.
* Streaming (``Iterator``) rather than list-return so a full-corpus
  scan does not materialise ~40k filenames in memory.
* Fail loudly on malformed file names; silently-skipped data is how
  coverage bugs sneak into a RAG corpus.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

from src.ingest.suttacentral.models import BilaraFile, FileKind, Segment

# File names in bilara follow ``{uid}_{muid}.json`` where the muid is
# ``{kind}-{language}-{author}``. Examples:
#   mn1_translation-en-sujato.json
#   mn1_root-pli-ms.json
#   an1.1-10_translation-de-sabbamitta.json
# We deliberately keep the regex loose about ``uid`` so range-form
# identifiers (``an1.1-10``) still parse — they are legitimate
# SuttaCentral UIDs, not malformed names.
_FILENAME_RE = re.compile(
    r"""
    ^(?P<uid>[A-Za-z0-9._-]+)
    _
    (?P<kind>translation|root)
    -
    (?P<language>[A-Za-z]+)
    -
    (?P<author>[A-Za-z0-9]+)
    \.json$
    """,
    re.VERBOSE,
)


def iter_bilara_files(
    bilara_root: Path,
    *,
    kind: FileKind | None = None,
    language: str | None = None,
    author: str | None = None,
    nikaya: str | None = None,
) -> Iterator[BilaraFile]:
    """Walk a bilara clone and yield every file that matches the filters.

    Parameters
    ----------
    bilara_root:
        Path to a checkout of ``suttacentral/bilara-data``. The walk
        starts at ``{bilara_root}/translation`` or ``{bilara_root}/root``
        depending on ``kind`` — restricting like this is orders of
        magnitude faster than scanning the whole tree, which contains
        large ``variant`` / ``comment`` / ``html`` trees we don't need.
    kind:
        Limit to translations or roots. ``None`` yields both.
    language, author, nikaya:
        Exact-match filters. ``None`` means "any".

    Raises
    ------
    FileNotFoundError:
        If ``bilara_root`` does not exist or does not look like a
        bilara checkout (missing ``translation/`` and ``root/``).
    """
    if not bilara_root.exists():
        raise FileNotFoundError(f"bilara-data root does not exist: {bilara_root}")

    tops: list[Path] = []
    if kind in (None, FileKind.TRANSLATION):
        tops.append(bilara_root / "translation")
    if kind in (None, FileKind.ROOT):
        tops.append(bilara_root / "root")

    if not any(t.exists() for t in tops):
        raise FileNotFoundError(
            f"{bilara_root} does not look like a bilara-data checkout "
            "(no 'translation/' or 'root/' subdirectory found)"
        )

    for top in tops:
        if not top.exists():
            continue
        for path in top.rglob("*.json"):
            bf = _try_parse_filename(path, bilara_root)
            if bf is None:
                continue
            if language is not None and bf.language != language:
                continue
            if author is not None and bf.author != author:
                continue
            if nikaya is not None and bf.nikaya != nikaya:
                continue
            yield bf


def parse_bilara_file(path: Path, bilara_root: Path) -> BilaraFile:
    """Return a ``BilaraFile`` for a single path.

    Useful when the caller already knows the file they want (e.g. for
    targeted tests) and does not need the full walk.

    Raises
    ------
    ValueError:
        If the filename does not follow the bilara convention.
    """
    bf = _try_parse_filename(path, bilara_root)
    if bf is None:
        raise ValueError(f"Not a bilara file name: {path.name}")
    return bf


def iter_segments(bf: BilaraFile) -> Iterator[Segment]:
    """Stream segments from a single bilara JSON file.

    Bilara files are small flat dicts (typically < 1 MB, a few hundred
    keys), so ``json.load`` is fine — streaming parsers would be
    over-engineering here. Text values in bilara often carry a trailing
    space that is meaningful for concatenation; we preserve it verbatim
    and leave whitespace handling to the downstream cleaner.
    """
    with bf.path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(
            f"{bf.path}: expected a JSON object of segment_id -> text, got {type(data).__name__}"
        )
    for segment_id, text in data.items():
        if not isinstance(text, str):
            raise ValueError(
                f"{bf.path}: segment {segment_id!r} has non-string value "
                f"({type(text).__name__}); bilara should never ship this."
            )
        yield Segment(segment_id=segment_id, text=text, source=bf)


def _try_parse_filename(path: Path, bilara_root: Path) -> BilaraFile | None:
    """Parse ``path.name`` and derive ``nikaya`` from the directory path.

    Returns ``None`` when the filename does not match the bilara
    convention — for example the ``_author.json`` / ``_language.json``
    metadata files at the top level. Those are valid JSON but don't
    describe a text, so ignoring them is deliberate.
    """
    m = _FILENAME_RE.match(path.name)
    if m is None:
        return None
    nikaya = _derive_nikaya(path, bilara_root)
    if nikaya is None:
        return None
    return BilaraFile(
        path=path,
        uid=m.group("uid"),
        kind=FileKind(m.group("kind")),
        language=m.group("language"),
        author=m.group("author"),
        nikaya=nikaya,
    )


def _derive_nikaya(path: Path, bilara_root: Path) -> str | None:
    """Find the nikaya directory above a bilara JSON file.

    Layout is ``{root}/{translation|root}/{lang}/{author}/sutta/{nikaya}/...``
    (with a further subdir for very deep collections like ``kn``). We
    walk up from the file until we find a parent whose *own* parent is
    ``sutta`` — that parent is the nikaya.
    """
    try:
        rel_parts = path.relative_to(bilara_root).parts
    except ValueError:
        return None
    for i in range(len(rel_parts) - 1, 0, -1):
        if rel_parts[i - 1] == "sutta":
            return rel_parts[i]
    return None
