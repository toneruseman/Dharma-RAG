#!/usr/bin/env python
"""
Hello-world test for the Claude API via the Dharma RAG config layer.

Usage:
    python scripts/test_claude.py
"""

from __future__ import annotations

import sys

from anthropic import Anthropic

from src.config import get_settings
from src.logging_config import get_logger, setup_logging


def main() -> int:
    setup_logging()
    log = get_logger("test_claude")

    settings = get_settings()
    if not settings.anthropic_api_key:
        log.error("ANTHROPIC_API_KEY is not set — add it to .env")
        return 1

    client = Anthropic(api_key=settings.anthropic_api_key)

    log.info("sending test request", model=settings.router_llm)
    resp = client.messages.create(
        model=settings.router_llm,
        max_tokens=100,
        messages=[{"role": "user", "content": "Say hi in Pāli"}],
    )

    text = resp.content[0].text
    log.info(
        "response received",
        text=text,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )
    print(f"\nClaude says: {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
