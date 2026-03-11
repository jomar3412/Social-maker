"""
Knowledge Registry - loads and manages manifest.json and document references.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Default knowledge base path relative to project root
DEFAULT_KB_PATH = Path(__file__).parent.parent.parent / "knowledge_base"


@dataclass
class DocumentEntry:
    """A document registered in the knowledge base."""
    id: str
    type: str  # spec, transcript, research, insight, pattern, rule
    scope: str  # external or internal
    path: str  # relative to knowledge_base/
    title: str
    description: str = ""
    source: str = "unknown"
    added_at: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "reference"  # authoritative, reference, supplemental
    sections: dict = field(default_factory=dict)

    @property
    def absolute_path(self) -> Path:
        """Get absolute path to the document."""
        return DEFAULT_KB_PATH / self.path

    def exists(self) -> bool:
        """Check if the document file exists."""
        return self.absolute_path.exists()

    def read_content(self) -> str:
        """Read the document content."""
        if not self.exists():
            raise FileNotFoundError(f"Document not found: {self.absolute_path}")
        return self.absolute_path.read_text()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "scope": self.scope,
            "path": self.path,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "added_at": self.added_at,
            "tags": self.tags,
            "priority": self.priority,
            "sections": self.sections,
        }


@dataclass
class RegistryConfig:
    """Configuration for knowledge registry."""
    sample_size_threshold: int = 10
    conflict_resolution: str = "prefer_internal_when_threshold_met"
    auto_learn_enabled: bool = True


class KnowledgeRegistry:
    """
    Manages the knowledge base manifest and document access.

    Responsibilities:
    - Load manifest.json
    - Resolve document paths
    - Provide access to external specs and internal learning
    - Track document metadata
    """

    def __init__(self, kb_path: Optional[Path] = None):
        self.kb_path = kb_path or DEFAULT_KB_PATH
        self.manifest_path = self.kb_path / "manifest.json"
        self._manifest: Optional[dict] = None
        self._documents: dict[str, DocumentEntry] = {}
        self.config = RegistryConfig()

    def load(self) -> None:
        """Load manifest.json and populate document registry."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"Knowledge base manifest not found: {self.manifest_path}\n"
                f"Please ensure knowledge_base/manifest.json exists."
            )

        with open(self.manifest_path) as f:
            self._manifest = json.load(f)

        # Load config
        config_data = self._manifest.get("config", {})
        self.config = RegistryConfig(
            sample_size_threshold=config_data.get("sample_size_threshold", 10),
            conflict_resolution=config_data.get("conflict_resolution", "prefer_internal_when_threshold_met"),
            auto_learn_enabled=config_data.get("auto_learn_enabled", True),
        )

        # Load external documents
        for doc_data in self._manifest.get("documents", []):
            entry = DocumentEntry(
                id=doc_data["id"],
                type=doc_data["type"],
                scope=doc_data["scope"],
                path=doc_data["path"],
                title=doc_data["title"],
                description=doc_data.get("description", ""),
                source=doc_data.get("source", "unknown"),
                added_at=doc_data.get("added_at", ""),
                tags=doc_data.get("tags", []),
                priority=doc_data.get("priority", "reference"),
                sections=doc_data.get("sections", {}),
            )
            self._documents[entry.id] = entry

        # Load internal insights/patterns/rules references
        for insight in self._manifest.get("internal_insights", []):
            if isinstance(insight, dict):
                entry = DocumentEntry(**insight)
                self._documents[entry.id] = entry

        for pattern in self._manifest.get("internal_patterns", []):
            if isinstance(pattern, dict):
                entry = DocumentEntry(**pattern)
                self._documents[entry.id] = entry

        for rule in self._manifest.get("internal_rules", []):
            if isinstance(rule, dict):
                entry = DocumentEntry(**rule)
                self._documents[entry.id] = entry

        logger.info(f"Loaded {len(self._documents)} documents from knowledge base")

    def get_document(self, doc_id: str) -> DocumentEntry:
        """Get a document by ID."""
        if not self._manifest:
            self.load()

        if doc_id not in self._documents:
            raise KeyError(
                f"Document not found in manifest: {doc_id}\n"
                f"Available documents: {list(self._documents.keys())}"
            )

        return self._documents[doc_id]

    def get_documents_by_type(self, doc_type: str) -> list[DocumentEntry]:
        """Get all documents of a specific type."""
        if not self._manifest:
            self.load()

        return [doc for doc in self._documents.values() if doc.type == doc_type]

    def get_documents_by_scope(self, scope: str) -> list[DocumentEntry]:
        """Get all documents by scope (external or internal)."""
        if not self._manifest:
            self.load()

        return [doc for doc in self._documents.values() if doc.scope == scope]

    def get_documents_by_tag(self, tag: str) -> list[DocumentEntry]:
        """Get all documents with a specific tag."""
        if not self._manifest:
            self.load()

        return [doc for doc in self._documents.values() if tag in doc.tags]

    def get_authoritative_specs(self) -> list[DocumentEntry]:
        """Get all authoritative specification documents."""
        if not self._manifest:
            self.load()

        return [
            doc for doc in self._documents.values()
            if doc.type == "spec" and doc.priority == "authoritative"
        ]

    def get_external_documents(self) -> list[DocumentEntry]:
        """Get all external documents."""
        return self.get_documents_by_scope("external")

    def get_internal_documents(self) -> list[DocumentEntry]:
        """Get all internal documents."""
        return self.get_documents_by_scope("internal")

    def add_document(self, entry: DocumentEntry) -> None:
        """Add a new document to the registry."""
        if not self._manifest:
            self.load()

        self._documents[entry.id] = entry

        # Update manifest
        doc_dict = entry.to_dict()
        if entry.scope == "external":
            self._manifest["documents"].append(doc_dict)
        elif entry.type == "insight":
            self._manifest["internal_insights"].append(doc_dict)
        elif entry.type == "pattern":
            self._manifest["internal_patterns"].append(doc_dict)
        elif entry.type == "rule":
            self._manifest["internal_rules"].append(doc_dict)

        self._save_manifest()

    def _save_manifest(self) -> None:
        """Save manifest.json."""
        self._manifest["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        with open(self.manifest_path, "w") as f:
            json.dump(self._manifest, f, indent=2)

    def get_dopamine_spec(self) -> DocumentEntry:
        """Convenience method to get the dopamine spec."""
        return self.get_document("dopamine_spec_v1")

    def read_learning_summary(self) -> dict:
        """Read the internal learning summary."""
        summary_path = self.kb_path / "internal" / "insights" / "learning_summary.json"
        if summary_path.exists():
            with open(summary_path) as f:
                return json.load(f)
        return {}

    def read_patterns(self) -> dict:
        """Read the internal patterns."""
        patterns_path = self.kb_path / "internal" / "patterns" / "patterns.json"
        if patterns_path.exists():
            with open(patterns_path) as f:
                return json.load(f)
        return {}

    def read_rule_overrides(self) -> dict:
        """Read the internal rule overrides."""
        rules_path = self.kb_path / "internal" / "rules" / "rule_overrides.json"
        if rules_path.exists():
            with open(rules_path) as f:
                return json.load(f)
        return {}

    def get_applicable_overrides(
        self,
        niche: Optional[str] = None,
        style: Optional[str] = None,
        visual_mode: Optional[str] = None,
    ) -> list[dict]:
        """Get rule overrides applicable to the given scope."""
        overrides_data = self.read_rule_overrides()
        applicable = []

        for override in overrides_data.get("overrides", []):
            if override.get("status") != "active":
                continue

            scope = override.get("scope", {})

            # Check if override applies to this scope
            scope_niche = scope.get("niche")
            scope_style = scope.get("style")
            scope_visual = scope.get("visual_mode")

            # Global overrides (all None) apply to everything
            is_global = scope_niche is None and scope_style is None and scope_visual is None

            # Scoped overrides must match
            niche_match = scope_niche is None or scope_niche == niche
            style_match = scope_style is None or scope_style == style
            visual_match = scope_visual is None or scope_visual == visual_mode

            if is_global or (niche_match and style_match and visual_match):
                applicable.append(override)

        return applicable


# Singleton instance
_registry_instance: Optional[KnowledgeRegistry] = None


def get_registry() -> KnowledgeRegistry:
    """Get the singleton knowledge registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = KnowledgeRegistry()
        _registry_instance.load()
    return _registry_instance


def reset_registry() -> None:
    """Reset the singleton (for testing)."""
    global _registry_instance
    _registry_instance = None
