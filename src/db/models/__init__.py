"""ORM models for Dharma-RAG.

Import this package to register every model with ``Base.metadata``;
Alembic's ``env.py`` does exactly that before autogenerating migrations.
"""

from __future__ import annotations

from src.db.models.frbr import Chunk, Expression, Instance, Work
from src.db.models.lookups import Author, Language, Tradition

__all__ = [
    "Author",
    "Chunk",
    "Expression",
    "Instance",
    "Language",
    "Tradition",
    "Work",
]
