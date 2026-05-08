"""rag-day-33 smoke: KN ingest verification (metta, dhammapada, etc.)."""

from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen

CASES = [
    # Foundational entries that depend on KN works
    ("What is loving-kindness?", "snp1.8"),
    ("Что такое метта?", "snp1.8"),
    ("Karaṇīya Mettā Sutta", "snp1.8"),
    # Other KN reachability probes (no foundational entry — testing raw retrieval)
    ("Discourse on the Elephants", "dhp"),  # dhp 320-333 chapter
    ("Verses of the Senior Monks", "thag"),
    ("Verses of the Senior Nuns", "thig"),
    ("Inspired Utterances", "ud"),
    ("Itivuttaka", "iti"),
    # Regression: existing foundational queries should keep working
    ("What is dukkha?", "sn56.11"),
    ("What is satipaṭṭhāna?", "mn10"),
    ("Что такое самадхи?", "an4.41"),
]


def query(q: str) -> dict:
    body = json.dumps({"query": q, "top_k": 5}).encode("utf-8")
    req = Request(
        "http://127.0.0.1:8000/api/query",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(req, timeout=120) as resp:  # noqa: S310 — localhost smoke
        return json.loads(resp.read().decode("utf-8"))


def fmt(top: list[dict]) -> str:
    return ", ".join(f"#{i + 1}={r['work_canonical_id']}" for i, r in enumerate(top[:3]))


def main() -> None:
    print(f"{'STATUS':6} {'EXPECT':12} | TOP-3")
    print("-" * 90)
    fails = 0
    for q, expected in CASES:
        d = query(q)
        sources = d.get("sources", [])
        version = d.get("metadata", {}).get("version", "")
        top1 = sources[0]["work_canonical_id"] if sources else "(empty)"
        # Allow prefix match (e.g. 'dhp' matches 'dhp1', 'thag' matches 'thag1.1')
        ok = (
            top1 == expected
            or top1.startswith(expected + ".")
            or top1.startswith(expected + "1")
            or any(s["work_canonical_id"].startswith(expected) for s in sources[:5])
        )
        status = "PASS" if ok else "FAIL"
        if not ok:
            fails += 1
        print(f"{status:6} {expected:12} | Q={q!r}")
        print(f"       {' ':12} | {fmt(sources)}  ({version})")
    print()
    print(f"Total: {len(CASES) - fails}/{len(CASES)} pass")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
