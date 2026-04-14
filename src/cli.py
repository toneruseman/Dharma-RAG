"""Command-line interface entry point for dharma-rag."""

from __future__ import annotations

import argparse
import sys

from src import __version__
from src.config import get_settings
from src.logging_config import get_logger, setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dharma-rag",
        description="Open-source multilingual RAG for Buddhist contemplative teachings",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override the LOG_LEVEL from .env",
    )

    sub = parser.add_subparsers(dest="command")

    # --- check-env ---
    sub.add_parser("check-env", help="Verify environment and connectivity")

    # --- serve (Phase 4) ---
    serve_p = sub.add_parser("serve", help="Start the FastAPI server")
    serve_p.add_argument("--host", default=None)
    serve_p.add_argument("--port", type=int, default=None)

    return parser


def cmd_check_env() -> None:
    """Verify that core dependencies and connections work."""
    log = get_logger("cli")
    settings = get_settings()

    # 1. Check Anthropic API key
    if settings.anthropic_api_key:
        log.info("anthropic_api_key is set")
    else:
        log.warning("anthropic_api_key is NOT set — Claude calls will fail")

    # 2. Try Qdrant connection
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=settings.qdrant_url, timeout=5)
        collections = client.get_collections().collections
        log.info("qdrant connected", url=settings.qdrant_url, collections=len(collections))
    except Exception as exc:
        log.warning("qdrant unreachable", url=settings.qdrant_url, error=str(exc))

    # 3. Langfuse
    if settings.langfuse_public_key:
        log.info("langfuse keys are set", host=settings.langfuse_host)
    else:
        log.info("langfuse keys not set — tracing disabled")

    log.info("environment check complete")


def cmd_serve(host: str | None, port: int | None) -> None:
    """Start the FastAPI application (placeholder for Phase 4)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.api.app:app",
        host=host or settings.app_host,
        port=port or settings.app_port,
        reload=settings.is_development,
    )


def main() -> None:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.log_level:
        import logging

        logging.getLogger().setLevel(args.log_level)

    if args.command == "check-env":
        cmd_check_env()
    elif args.command == "serve":
        cmd_serve(args.host, args.port)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
