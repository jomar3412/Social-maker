"""
Knowledge Base module for Content Engine.

Manages external specs, internal learning, and knowledge context for runs.
"""

from .registry import (
    KnowledgeRegistry,
    DocumentEntry,
    get_registry,
)
from .context import (
    KnowledgeContext,
    build_knowledge_context,
    get_learning_context_prompt,
)
from .compare import (
    KnowledgeComparator,
    ConflictRecord,
    compare_internal_external,
)

__all__ = [
    "KnowledgeRegistry",
    "DocumentEntry",
    "get_registry",
    "KnowledgeContext",
    "build_knowledge_context",
    "get_learning_context_prompt",
    "KnowledgeComparator",
    "ConflictRecord",
    "compare_internal_external",
]
