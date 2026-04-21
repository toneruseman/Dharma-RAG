"""Ingest SuttaCentral bilara translations into Postgres.

Usage (from repo root, with ``dharma-db`` running)::

    # MN only — fast sanity check (~150 files)
    python scripts/ingest_sc.py --nikayas mn

    # Full Phase-1 scope (~12k files)
    python scripts/ingest_sc.py --nikayas mn,dn,sn,an

    # Re-run is idempotent: files whose content_hash already exists
    # are skipped, so this is safe as a cron job.

The script intentionally uses a single async session across the whole
run. ``commit_every`` controls how much work a crash can lose. On a
laptop, MN (152 files) completes in a few seconds; the full SN + AN
takes a couple of minutes.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.ingest.suttacentral.loader import load_directory  # noqa: E402


async def _run(
    bilara_root: Path,
    author: str,
    language: str,
    nikayas: list[str] | None,
    commit_every: int,
) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_maker() as session:
            start = time.monotonic()
            counters = await load_directory(
                session,
                bilara_root,
                author=author,
                language=language,
                nikayas=nikayas,
                commit_every=commit_every,
            )
        elapsed = time.monotonic() - start
    finally:
        await engine.dispose()

    print(
        "\n=== Ingest summary ===\n"
        f"  files seen:       {counters['files_seen']:>6}\n"
        f"  files loaded:     {counters['files_loaded']:>6}\n"
        f"  files skipped:    {counters['files_skipped']:>6} (already in DB)\n"
        f"  chunks inserted:  {counters['chunks_inserted']:>6}\n"
        f"  elapsed:          {elapsed:>6.1f}s"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bilara-root",
        type=Path,
        default=_REPO_ROOT / "data" / "raw" / "suttacentral",
        help="Path to a checkout of suttacentral/bilara-data.",
    )
    parser.add_argument(
        "--author",
        default="sujato",
        help="Translator slug (default: sujato).",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Bilara short code of the translation language (default: en).",
    )
    parser.add_argument(
        "--nikayas",
        default="mn,dn,sn,an",
        help="Comma-separated list of nikayas. Default covers Phase 1 scope.",
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=50,
        help="Commit after N files (default: 50). Lower = safer but slower.",
    )
    args = parser.parse_args()

    if not args.bilara_root.exists():
        print(
            f"ERROR: {args.bilara_root} does not exist — clone bilara-data first.", file=sys.stderr
        )
        return 2

    nikayas = [n.strip() for n in args.nikayas.split(",") if n.strip()] or None
    return asyncio.run(
        _run(
            bilara_root=args.bilara_root,
            author=args.author,
            language=args.language,
            nikayas=nikayas,
            commit_every=args.commit_every,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
