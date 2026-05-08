"""Smoke test for rag-day-30: regression + new Russian definitional queries."""

from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen

CASES = [
    # === Regression (must remain) ===
    ("What is dukkha?", "sn56.11"),
    ("What is anatta?", "sn22.59"),
    ("What is satipaṭṭhāna?", "mn10"),
    ("What is dependent origination?", "sn12.2"),
    ("What is anapanasati?", "mn118"),
    ("What is right view?", "mn117"),
    # === rag-day-30 new Russian definitional (hard expectation) ===
    ("Что такое самадхи?", "an4.41"),
    ("Что такое нравственность?", "dn31"),
    ("Что такое факторы пробуждения?", "sn46.3"),
    ("Что такое брахмавихара?", "dn13"),
    # === rag-day-30 lower-confidence (alias maps but corpus retrieval
    # does not surface the canonical work — Russian text on dense channel
    # finds different sutras and BM25 phrases ('three jewels', '12 links')
    # have zero matches in Sujato body) ===
    ("Что такое 12 нидан?", None),
    ("Что такое три прибежища?", None),
]


def query(q: str) -> dict:
    body = json.dumps(
        {
            "query": q,
            "top_k": 5,
            "expand_pali": False,
            "expand_definitional": True,
            "foundational_boost": True,
        }
    ).encode("utf-8")
    req = Request(
        "http://127.0.0.1:8000/api/query",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(req, timeout=120) as resp:  # noqa: S310 — localhost smoke test
        return json.loads(resp.read().decode("utf-8"))


def fmt(top: list[dict]) -> str:
    return ", ".join(f"#{i + 1}={r['work_canonical_id']}" for i, r in enumerate(top[:3]))


def main() -> None:
    print(f"{'STATUS':6} {'EXPECT':10} | TOP-3")
    print("-" * 90)
    fails = 0
    for q, expected in CASES:
        d = query(q)
        sources = d.get("sources", [])
        version = d.get("metadata", {}).get("version", "")
        if expected is None:
            status = "INFO"
        else:
            top1 = sources[0]["work_canonical_id"] if sources else "(empty)"
            ok = top1 == expected
            status = "PASS" if ok else "FAIL"
            if not ok:
                fails += 1
        print(f"{status:6} {expected or '-':10} | Q={q!r}")
        print(f"       {' ':10} | {fmt(sources)}  ({version})")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
