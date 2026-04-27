"""Concrete :class:`ContextProviderProtocol` implementations.

Day-16 ships a single provider: :class:`OpenRouterProvider`. Future days
may add direct Anthropic, vLLM-on-cloud.ru, or local llama.cpp variants
— all sharing the same protocol.
"""

from src.contextual.providers.openrouter import (
    DEFAULT_OPENROUTER_BASE_URL,
    OpenRouterProvider,
    estimate_cost_usd,
)

__all__ = [
    "DEFAULT_OPENROUTER_BASE_URL",
    "OpenRouterProvider",
    "estimate_cost_usd",
]
