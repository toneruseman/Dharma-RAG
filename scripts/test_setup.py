#!/usr/bin/env python
"""
Test setup script — run after `pip install -e .[dev]` to verify environment.

Usage:
    python scripts/test_setup.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def check(name: str, condition: bool, details: str = "") -> bool:
    symbol = "✓" if condition else "✗"
    print(f"  {symbol} {name}{': ' + details if details else ''}")
    return condition


def main() -> int:
    print("=" * 60)
    print("Dharma RAG — Environment Check")
    print("=" * 60)

    all_ok = True

    # 1. Python version
    print("\n[1/6] Python version:")
    py_ver = sys.version_info
    ok = py_ver >= (3, 11)
    all_ok &= check(
        "Python >= 3.11",
        ok,
        f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}",
    )

    # 2. Environment file
    print("\n[2/6] Environment file:")
    env_path = Path(".env")
    ok = env_path.exists()
    all_ok &= check(
        ".env exists", ok, str(env_path.absolute()) if ok else "create from .env.example"
    )

    if ok:
        # Try to load
        try:
            from dotenv import load_dotenv

            load_dotenv()
            check("dotenv loaded", True)
        except ImportError:
            all_ok &= check("python-dotenv installed", False, "pip install python-dotenv")

        # Check critical vars
        critical = ["ANTHROPIC_API_KEY"]
        for var in critical:
            val = os.getenv(var, "")
            has_value = bool(val) and not val.startswith("sk-ant-...")
            all_ok &= check(f"{var} set", has_value)

    # 3. Critical imports
    print("\n[3/6] Critical imports:")
    imports = [
        ("anthropic", "Anthropic SDK"),
        ("qdrant_client", "Qdrant client"),
        ("fastapi", "FastAPI"),
        ("pydantic", "Pydantic"),
        ("torch", "PyTorch"),
        ("sentence_transformers", "sentence-transformers"),
    ]
    for module, name in imports:
        try:
            __import__(module)
            check(name, True)
        except ImportError as e:
            all_ok &= check(name, False, f"pip install -e . ({e})")

    # 4. Anthropic API
    print("\n[4/6] Anthropic API:")
    try:
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if api_key and not api_key.startswith("sk-ant-..."):
            client = Anthropic(api_key=api_key)
            # Minimal test call
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            check(
                "API call successful",
                True,
                f"used {resp.usage.input_tokens} in, {resp.usage.output_tokens} out tokens",
            )
        else:
            all_ok &= check("API call test", False, "set ANTHROPIC_API_KEY")
    except Exception as e:
        all_ok &= check("API call test", False, str(e)[:100])

    # 5. Qdrant connection
    print("\n[5/6] Qdrant connection:")
    try:
        from qdrant_client import QdrantClient

        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        client = QdrantClient(url=qdrant_url, timeout=5)
        collections = client.get_collections()
        check(
            "Qdrant connected",
            True,
            f"{qdrant_url}, {len(collections.collections)} collections",
        )
    except Exception as e:
        all_ok &= check(
            "Qdrant connected",
            False,
            f"run: docker compose up -d qdrant ({str(e)[:50]})",
        )

    # 6. Optional: Langfuse
    print("\n[6/6] Langfuse (optional):")
    try:
        import httpx

        langfuse_host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        r = httpx.get(f"{langfuse_host}/api/public/health", timeout=5)
        check("Langfuse reachable", r.status_code == 200, langfuse_host)
    except Exception as e:
        check("Langfuse reachable", False, f"optional, skip for now ({str(e)[:50]})")

    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ All critical checks passed — ready to start development!")
        print("\nNext steps:")
        print("  1. Read docs/DAY_BY_DAY_PLAN.md to understand the roadmap")
        print("  2. Continue with Day 4: data migration and initial indexing")
    else:
        print("✗ Some checks failed — fix the issues above before proceeding.")
        print("\nCommon fixes:")
        print("  - Create .env from .env.example and fill in keys")
        print("  - Install deps: pip install -e '.[dev]'")
        print("  - Start Qdrant: docker compose up -d qdrant")
    print("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
