"""rag-day-34 smoke: Russian SC translations verification."""

from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen

CASES = [
    # Russian definitional — covered by foundational + Russian retrieval
    ("Что такое страдание?", "sn56.11"),
    ("Что такое благородные истины?", "sn56.11"),
    ("Что такое анатта?", "sn22.59"),
    ("Что такое сатипаттхана?", "mn10"),
    ("Что такое анапанасати?", "mn118"),
    ("Что такое самадхи?", "an4.41"),
    ("Что такое метта?", "snp1.8"),
    # Russian without explicit "что такое"
    ("четыре благородные истины", "sn56.11"),
    ("восьмеричный путь", "sn45.8"),
    ("взаимозависимое возникновение", "sn12.2"),
    # English regression preserved
    ("What is dukkha?", "sn56.11"),
    ("What is loving-kindness?", "snp1.8"),
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
        ok = top1 == expected or any(s["work_canonical_id"] == expected for s in sources[:5])
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
