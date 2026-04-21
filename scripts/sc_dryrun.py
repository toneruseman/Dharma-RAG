"""Dry-run the SuttaCentral bilara parser on a small sample.

Usage (from repo root)::

    python scripts/sc_dryrun.py
    python scripts/sc_dryrun.py --bilara-root data/raw/suttacentral --limit 10

The rag-day-03 gate is: parser emits 10 well-formed records from the
sujato English translation of the Majjhima Nikāya. We deliberately do
not touch the database here — persistence is rag-day-04.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow ``python scripts/sc_dryrun.py`` without needing editable install.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Windows consoles default to cp1252 and choke on Pali diacritics. Force
# UTF-8 on stdout so the dry-run works identically on Windows and Linux.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.ingest.suttacentral import (  # noqa: E402
    FileKind,
    iter_bilara_files,
    iter_segments,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bilara-root",
        type=Path,
        default=_REPO_ROOT / "data" / "raw" / "suttacentral",
        help="Path to a checkout of suttacentral/bilara-data.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of segments to emit before stopping.",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Translation language (en, de, fr, ...). Default: en.",
    )
    parser.add_argument(
        "--author",
        default="sujato",
        help="Translator/root-edition slug. Default: sujato.",
    )
    parser.add_argument(
        "--nikaya",
        default="mn",
        help="Nikaya to sample (mn, dn, sn, an, kn). Default: mn.",
    )
    args = parser.parse_args()

    if not args.bilara_root.exists():
        print(
            f"ERROR: {args.bilara_root} does not exist.\n"
            "Clone it first:\n"
            "  git clone --depth 1 --branch published "
            "https://github.com/suttacentral/bilara-data.git "
            f"{args.bilara_root}",
            file=sys.stderr,
        )
        return 2

    files = iter_bilara_files(
        args.bilara_root,
        kind=FileKind.TRANSLATION,
        language=args.language,
        author=args.author,
        nikaya=args.nikaya,
    )

    emitted = 0
    for bf in files:
        for seg in iter_segments(bf):
            print(
                f"[{emitted + 1:>2}/{args.limit}] "
                f"{bf.nikaya}/{bf.uid} @ {seg.segment_id}\n"
                f"     {seg.text.strip()}"
            )
            emitted += 1
            if emitted >= args.limit:
                return 0
    if emitted == 0:
        print(
            f"WARNING: no segments produced — check filters "
            f"(lang={args.language}, author={args.author}, nikaya={args.nikaya}).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
