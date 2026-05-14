"""GET /api/works — corpus browsing endpoints.

Provides two read-only listing endpoints that drive the Reading Room
browse UI:

* ``GET /api/works/teachers`` — distinct teachers who have dharmaseed
  talks in the corpus, with a talk count each.
* ``GET /api/works`` — paginated list of works for one teacher (or by
  source_type).

These endpoints bypass the ``RAGServiceProtocol`` because they need
plain SQL against the FRBR tables, not vector retrieval. They follow
the same stub/real factory pattern as :mod:`src.api.feedback`.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["works"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TeacherCard(BaseModel):
    """One teacher entry for the browse landing."""

    slug: str
    name: str
    talk_count: int
    tradition_code: str | None = None


class WorkCard(BaseModel):
    """Minimal talk metadata for the teacher's talk list."""

    canonical_id: str
    title: str
    talk_date: str | None = None
    tradition_code: str | None = None


class WorkListResponse(BaseModel):
    """Paginated list of works."""

    items: list[WorkCard]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Stub implementation (no DB required)
# ---------------------------------------------------------------------------


class _StubWorksService:
    async def list_teachers(self) -> list[TeacherCard]:
        return []

    async def list_works(
        self,
        *,
        source_type: str,
        teacher_slug: str | None,
        limit: int,
        offset: int,
    ) -> WorkListResponse:
        return WorkListResponse(items=[], total=0, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Real implementation (async SQLAlchemy)
# ---------------------------------------------------------------------------


class _RealWorksService:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sm = sessionmaker

    async def list_teachers(self) -> list[TeacherCard]:
        from src.db.models.frbr import Expression, Work
        from src.db.models.lookups import Author

        stmt = (
            sa.select(
                Author.slug,
                Author.name,
                sa.func.count(Work.id.distinct()).label("talk_count"),
                Author.tradition_code,
            )
            .join(Expression, Expression.author_id == Author.id)
            .join(Work, Work.id == Expression.work_id)
            .where(Work.source_type == "dharmaseed_talk")
            .where(Author.slug.isnot(None))
            .group_by(Author.slug, Author.name, Author.tradition_code)
            .order_by(sa.desc("talk_count"))
        )
        async with self._sm() as session:
            rows = (await session.execute(stmt)).all()
        return [
            TeacherCard(
                slug=row.slug,
                name=row.name,
                talk_count=row.talk_count,
                tradition_code=row.tradition_code,
            )
            for row in rows
        ]

    async def list_works(
        self,
        *,
        source_type: str,
        teacher_slug: str | None,
        limit: int,
        offset: int,
    ) -> WorkListResponse:
        from src.db.models.frbr import Expression, Work
        from src.db.models.lookups import Author

        # talk_date lives in metadata_json as an ISO string "YYYY-MM-DD"
        date_col = Work.metadata_json["date"].astext

        base = (
            sa.select(
                Work.canonical_id,
                Work.title,
                date_col.label("talk_date"),
                Work.tradition_code,
            )
            .distinct()
            .where(Work.source_type == source_type)
        )
        if teacher_slug is not None:
            base = (
                base.join(Expression, Expression.work_id == Work.id)
                .join(Author, Author.id == Expression.author_id)
                .where(Author.slug == teacher_slug)
            )
        count_stmt = sa.select(sa.func.count()).select_from(base.subquery())
        items_stmt = base.order_by(sa.nullslast(sa.desc(date_col))).limit(limit).offset(offset)

        async with self._sm() as session:
            total = (await session.execute(count_stmt)).scalar_one()
            rows = (await session.execute(items_stmt)).all()

        return WorkListResponse(
            items=[
                WorkCard(
                    canonical_id=row.canonical_id,
                    title=row.title,
                    talk_date=row.talk_date,
                    tradition_code=row.tradition_code,
                )
                for row in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )


# Module-level service, populated by install_router.
_service: _StubWorksService | _RealWorksService | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/works/teachers",
    response_model=list[TeacherCard],
    summary="List teachers with dharmaseed talks in the corpus",
)
async def list_teachers() -> list[TeacherCard]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Works service initialising.")
    return await _service.list_teachers()


@router.get(
    "/works",
    response_model=WorkListResponse,
    summary="Paginated list of works, optionally filtered by teacher",
)
async def list_works(
    source_type: str = Query(default="dharmaseed_talk", description="Work source type"),
    teacher_slug: str | None = Query(default=None, description="Author slug to filter by"),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> WorkListResponse:
    if _service is None:
        raise HTTPException(status_code=503, detail="Works service initialising.")
    return await _service.list_works(
        source_type=source_type,
        teacher_slug=teacher_slug,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def install_router(app: FastAPI) -> None:
    global _service
    if _service is None:
        from src.config import get_settings

        settings = get_settings()
        if settings.rag_backend == "stub":
            _service = _StubWorksService()
        else:
            from src.db.session import get_sessionmaker

            _service = _RealWorksService(sessionmaker=get_sessionmaker())
    app.include_router(router)


def shutdown_service() -> None:
    global _service
    _service = None
