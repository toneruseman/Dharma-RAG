"""Smoke-test BGE-M3 on a sample of real chunks.

Meets the rag-day-08 gate: BGE-M3 produces dense + sparse vectors
for 100 chunks from the live Postgres corpus, vectors are the
expected shape, and cosine similarity is sensible between related
passages.

Usage
-----
    python scripts/test_bge_m3.py                  # 100 chunks default
    python scripts/test_bge_m3.py --limit 20       # quick sanity
    python scripts/test_bge_m3.py --device cpu     # force CPU (slow)

Expected CPU runtime for 100 child chunks on a recent laptop: ~2 min.
GPU runtime on 1080 Ti (11 GB): ~15 s. First run also downloads the
~2.3 GB BGE-M3 weights from HuggingFace into ~/.cache/huggingface.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db.models.frbr import Chunk  # noqa: E402
from src.embeddings.bge_m3 import DENSE_DIM, BGEM3Encoder  # noqa: E402


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity without a numpy dep in this hot-path free script."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def _fetch_sample_chunks(limit: int) -> list[tuple[str, str]]:
    """Return (segment_id, canonical_text) pairs from child chunks only.

    Sorting by ``id`` rather than random keeps runs reproducible — the
    same 100 chunks every invocation, so before/after comparisons are
    meaningful.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_maker() as session:
            rows = (
                await session.execute(
                    sa.select(Chunk.segment_id, Chunk.text)
                    .where(Chunk.is_parent.is_(False))
                    .order_by(Chunk.id)
                    .limit(limit)
                )
            ).all()
        return [(sid or "?", text) for sid, text in rows]
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=100, help="Number of chunks to encode (default 100)."
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Compute device (default auto).",
    )
    parser.add_argument(
        "--batch-size", type=int, default=12, help="Encode batch size (default 12)."
    )
    args = parser.parse_args()

    print(f"Fetching {args.limit} child chunks from Postgres...")
    chunks = asyncio.run(_fetch_sample_chunks(args.limit))
    if not chunks:
        print("ERROR: no chunks found — run `python scripts/ingest_sc.py` first.", file=sys.stderr)
        return 2
    print(f"  got {len(chunks)} chunks.")

    print("Loading BGE-M3 (this downloads ~2.3 GB on first run)...")
    t0 = time.monotonic()
    encoder = BGEM3Encoder(device=args.device)
    texts = [text for _, text in chunks]
    result = encoder.encode(texts, batch_size=args.batch_size)
    elapsed = time.monotonic() - t0
    print(
        f"Encoded {len(texts)} texts in {elapsed:.1f}s on {encoder.device} "
        f"(fp16={encoder.uses_fp16}). That is {elapsed / len(texts) * 1000:.1f} ms/chunk."
    )

    # Shape gates — these are the day-8 acceptance criteria. Use
    # explicit raises rather than `assert` so ``python -O`` never
    # silently erases the gate.
    if len(result.dense) != len(texts):
        raise RuntimeError(f"dense count mismatch: {len(result.dense)} vs {len(texts)}")
    if len(result.sparse) != len(texts):
        raise RuntimeError(f"sparse count mismatch: {len(result.sparse)} vs {len(texts)}")
    bad_dims = [i for i, v in enumerate(result.dense) if len(v) != DENSE_DIM]
    if bad_dims:
        raise RuntimeError(f"dense dim mismatch at positions {bad_dims[:5]} (expected {DENSE_DIM})")

    # Meaningful self-similarity: encode the first text again and
    # compare the two independent encodings. Comparing a vector to
    # itself is trivially 1.0 — re-encoding tests determinism.
    reencoded = encoder.encode([texts[0]], batch_size=args.batch_size)
    self_sim = _cosine(result.dense[0], reencoded.dense[0])
    neighbour_sim = _cosine(result.dense[0], result.dense[1]) if len(result.dense) > 1 else 0.0
    far_sim = _cosine(result.dense[0], result.dense[-1]) if len(result.dense) > 2 else neighbour_sim
    if self_sim < 0.999:
        raise RuntimeError(
            f"Deterministic self-similarity too low: {self_sim:.4f}. "
            "Re-encoding the same text should yield an essentially identical vector; "
            "if this fails the model is non-deterministic under our settings."
        )
    print(
        "\nCosine sanity check (higher = more similar):\n"
        f"  re-encode same text : {self_sim:.4f}  (must be >=0.999)\n"
        f"  consecutive chunks  : {neighbour_sim:.4f}\n"
        f"  first vs last       : {far_sim:.4f}"
    )

    # Show the first few sparse weights so we can eyeball that lexical
    # info survives (large weights on rare tokens = healthy).
    print("\nSparse sample (top-5 weights of the first chunk):")
    first_sparse = result.sparse[0]
    top = sorted(first_sparse.items(), key=lambda kv: -kv[1])[:5]
    for token_id, weight in top:
        print(f"  token_id={token_id:>6}  weight={weight:.4f}")

    # A tiny preview so the operator can see what was actually encoded.
    print("\nFirst three chunks:")
    for sid, text in chunks[:3]:
        preview = text[:90] + ("…" if len(text) > 90 else "")
        print(f"  [{sid}] {preview}")

    print("\n✓ BGE-M3 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
