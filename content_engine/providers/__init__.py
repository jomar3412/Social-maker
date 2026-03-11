"""
Provider abstraction layer for content generation.

Providers implement the actual content generation logic:
- StubProvider: Fast mock responses for testing
- CLIProvider: Execute local CLI commands (claude, gemini, codex)
- APIProvider: Future - direct API calls
"""

from .base import (
    ContentProvider,
    ProviderConfig,
    ProviderType,
    GenerationResult,
    ProviderError,
    get_provider,
)
from .stub_provider import StubProvider
from .cli_provider import CLIProvider

__all__ = [
    "ContentProvider",
    "ProviderConfig",
    "ProviderType",
    "GenerationResult",
    "ProviderError",
    "get_provider",
    "StubProvider",
    "CLIProvider",
]
