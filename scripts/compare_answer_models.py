"""Run the same query through several LLM models on /api/answer and
print a side-by-side comparison.

Hits a *running* uvicorn at ``--api-url`` (default ``http://localhost:8000``).
Requires ``RAG_BACKEND=real`` and a valid ``OPENROUTER_API_KEY`` server-
side. The script doesn't talk to OpenRouter directly — it forwards the
``model`` field through the API so each call exercises the same
production code path (retrieval + glossary + system prompt).

Usage::

    python scripts/compare_answer_models.py "что такое джхана?"
    python scripts/compare_answer_models.py "what is anatta?" --style detailed --top-k 5
    python scripts/compare_answer_models.py "..." --models anthropic/claude-haiku-4.5,anthropic/claude-opus-4.6

Output: markdown table to stdout + saved to
``docs/MODEL_COMPARISON_<utc_timestamp>.md`` for later review.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_MODELS: tuple[str, ...] = (
    "anthropic/claude-haiku-4.5",
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-opus-4.6",
)

# Per-Mtok pricing (USD) for OpenRouter Anthropic catalog as of
# 2026-04-29 (verified via /api/v1/models). Refresh if the script
# undercounts cost or a new model is added.
PRICING: dict[str, tuple[float, float]] = {
    "anthropic/claude-haiku-4.5": (1.00, 5.00),
    "anthropic/claude-sonnet-4.5": (3.00, 15.00),
    "anthropic/claude-sonnet-4.6": (3.00, 15.00),
    "anthropic/claude-opus-4.5": (5.00, 25.00),
    "anthropic/claude-opus-4.6": (5.00, 25.00),
    "anthropic/claude-opus-4.6-fast": (30.00, 150.00),
    "anthropic/claude-opus-4.7": (5.00, 25.00),
    "anthropic/claude-3.5-haiku": (0.80, 4.00),
    "anthropic/claude-3.7-sonnet": (3.00, 15.00),
}


def _estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float | None:
    rates = PRICING.get(model)
    if rates is None:
        return None
    in_per_mtok, out_per_mtok = rates
    return (tokens_in / 1_000_000) * in_per_mtok + (tokens_out / 1_000_000) * out_per_mtok


def _call_answer(*, api_url: str, query: str, model: str, top_k: int, style: str) -> dict[str, Any]:
    body = json.dumps(
        {"query": query, "model": model, "top_k": top_k, "style": style},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 — local API call
        f"{api_url.rstrip('/')}/api/answer",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 — local API
            payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_txt = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from /api/answer: {body_txt}") from exc
    payload["_wallclock_s"] = time.perf_counter() - t0
    return payload


def _render_md(
    *, query: str, style: str, top_k: int, results: list[tuple[str, dict[str, Any] | str]]
) -> str:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# Model comparison — `/api/answer`")
    lines.append("")
    lines.append(f"- **Generated**: {now}")
    lines.append(f"- **Query**: `{query}`")
    lines.append(f"- **Style**: `{style}`  /  **top_k**: {top_k}")
    lines.append("")

    # ---- Headline table ----
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| model | latency (s) | retrieval (ms) | LLM (ms) | tokens in | tokens out | cost USD | citations |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for model, payload in results:
        if isinstance(payload, str):
            lines.append(f"| `{model}` | — | — | — | — | — | — | **error**: {payload} |")
            continue
        tin = int(payload["metadata"]["llm_tokens_in"])
        tout = int(payload["metadata"]["llm_tokens_out"])
        cost = _estimate_cost_usd(model, tin, tout)
        cost_str = f"${cost:.4f}" if cost is not None else "—"
        cites = ", ".join(payload.get("citations", [])) or "(none)"
        lines.append(
            f"| `{model}` | "
            f"{payload['latency_ms']/1000:.2f} | "
            f"{payload['retrieval_latency_ms']:.0f} | "
            f"{payload['llm_latency_ms']:.0f} | "
            f"{tin} | {tout} | {cost_str} | {cites} |"
        )
    lines.append("")

    # ---- Per-model answer text ----
    for model, payload in results:
        lines.append(f"## `{model}`")
        lines.append("")
        if isinstance(payload, str):
            lines.append(f"**Error:** {payload}")
            lines.append("")
            continue
        lines.append(f"**Style applied:** `{payload['metadata'].get('style', '?')}`")
        lines.append("")
        lines.append("```")
        lines.append(payload["answer"])
        lines.append("```")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("query", help="The user question to send to /api/answer.")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the running uvicorn (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help=("Comma-separated OpenRouter model ids. Default: " f"{','.join(DEFAULT_MODELS)}."),
    )
    parser.add_argument(
        "--style",
        default="auto",
        choices=("auto", "concise", "detailed"),
        help="Forwarded to /api/answer (default: auto).",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of sources (default: 5).")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=("Output markdown path. Default: " "docs/MODEL_COMPARISON_<utc_timestamp>.md."),
    )
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    print(f"Comparing {len(models)} model(s) on query: {args.query!r}")
    print(f"  style={args.style}  top_k={args.top_k}  api={args.api_url}")
    print()

    results: list[tuple[str, dict[str, Any] | str]] = []
    for i, model in enumerate(models, start=1):
        print(f"[{i}/{len(models)}] {model} ...", end=" ", flush=True)
        try:
            payload = _call_answer(
                api_url=args.api_url,
                query=args.query,
                model=model,
                top_k=args.top_k,
                style=args.style,
            )
            print(
                f"OK  latency={payload['latency_ms']/1000:.1f}s  "
                f"in={payload['metadata']['llm_tokens_in']}  "
                f"out={payload['metadata']['llm_tokens_out']}"
            )
            results.append((model, payload))
        except Exception as exc:  # noqa: BLE001 — surface any error per-cell
            print(f"FAILED: {exc}")
            results.append((model, str(exc)))

    md = _render_md(query=args.query, style=args.style, top_k=args.top_k, results=results)
    out_path = args.out or Path(
        f"docs/MODEL_COMPARISON_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
