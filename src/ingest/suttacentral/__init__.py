"""SuttaCentral bilara-data ingest pipeline.

The public surface is intentionally small — the parser layer does *not*
touch the database. It emits plain dataclasses so downstream stages
(normalisation, chunking, persistence) can be swapped or tested in
isolation.
"""

from __future__ import annotations

from src.ingest.suttacentral.models import (
    BilaraFile,
    FileKind,
    Segment,
)
from src.ingest.suttacentral.parser import (
    iter_bilara_files,
    iter_segments,
    parse_bilara_file,
)

__all__ = [
    "BilaraFile",
    "FileKind",
    "Segment",
    "iter_bilara_files",
    "iter_segments",
    "parse_bilara_file",
]
