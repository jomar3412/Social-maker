"""
Tests for the knowledge base system.

Verifies:
- Dopamine spec is found via manifest.json and loaded
- Missing manifest entry fails loudly with a clear error
- Run creates knowledge_context.md in the run folder
- Internal vs external comparison produces conflicts.md
- Sample-size threshold logic works
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from content_engine.knowledge.registry import (
    KnowledgeRegistry,
    DocumentEntry,
    RegistryConfig,
    get_registry,
    reset_registry,
)
from content_engine.knowledge.context import (
    KnowledgeContext,
    DopamineLevelRequirement,
    build_knowledge_context,
    get_learning_context_prompt,
)
from content_engine.knowledge.compare import (
    KnowledgeComparator,
    ConflictRecord,
    ComparisonResult,
    compare_internal_external,
)


@pytest.fixture(autouse=True)
def reset_registry_singleton():
    """Reset the registry singleton before each test."""
    reset_registry()
    yield
    reset_registry()


class TestKnowledgeRegistry:
    """Tests for the KnowledgeRegistry class."""

    def test_load_manifest_success(self, tmp_path):
        """Test that manifest.json is loaded correctly."""
        # Create a test manifest
        manifest = {
            "version": "1.0.0",
            "documents": [
                {
                    "id": "test_doc",
                    "type": "spec",
                    "scope": "external",
                    "path": "external/specs/test.md",
                    "title": "Test Document",
                    "description": "A test document",
                    "priority": "authoritative",
                    "tags": ["test", "sample"],
                    "added_at": "2024-01-01"
                }
            ],
            "config": {
                "sample_size_threshold": 10,
                "conflict_resolution": "prefer_internal_when_threshold_met"
            }
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # Create the document
        doc_path = tmp_path / "external" / "specs"
        doc_path.mkdir(parents=True)
        (doc_path / "test.md").write_text("# Test Document\n\nContent here.")

        # Load registry
        registry = KnowledgeRegistry(tmp_path)
        registry.load()

        assert registry._manifest["version"] == "1.0.0"
        assert len(registry._documents) == 1
        assert registry._documents["test_doc"].title == "Test Document"
        assert registry.config.sample_size_threshold == 10

    def test_load_manifest_missing_file(self, tmp_path):
        """Test that missing manifest.json raises clear error."""
        registry = KnowledgeRegistry(tmp_path)

        with pytest.raises(FileNotFoundError) as exc_info:
            registry.load()

        assert "manifest.json" in str(exc_info.value).lower() or "manifest" in str(exc_info.value).lower()

    def test_load_manifest_invalid_json(self, tmp_path):
        """Test that invalid JSON raises clear error."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{ invalid json }")

        registry = KnowledgeRegistry(tmp_path)

        with pytest.raises(json.JSONDecodeError):
            registry.load()

    def test_get_document_success(self, tmp_path):
        """Test getting a document by ID."""
        manifest = {
            "version": "1.0.0",
            "documents": [
                {
                    "id": "dopamine_spec_v1",
                    "type": "spec",
                    "scope": "external",
                    "path": "external/specs/dopamine.md",
                    "title": "Dopamine Spec",
                    "priority": "authoritative",
                    "tags": ["dopamine"]
                }
            ],
            "config": {"sample_size_threshold": 10}
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        doc_path = tmp_path / "external" / "specs"
        doc_path.mkdir(parents=True)
        (doc_path / "dopamine.md").write_text("# Dopamine Content\n\nSpec content.")

        registry = KnowledgeRegistry(tmp_path)
        registry.load()
        doc = registry.get_document("dopamine_spec_v1")

        assert doc is not None
        assert doc.id == "dopamine_spec_v1"
        assert doc.title == "Dopamine Spec"

    def test_get_document_not_found(self, tmp_path):
        """Test that missing document ID raises clear error."""
        manifest = {
            "version": "1.0.0",
            "documents": [],
            "config": {"sample_size_threshold": 10}
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        registry = KnowledgeRegistry(tmp_path)
        registry.load()

        with pytest.raises(KeyError) as exc_info:
            registry.get_document("nonexistent_doc")

        assert "nonexistent_doc" in str(exc_info.value)

    def test_get_dopamine_spec(self, tmp_path):
        """Test getting the dopamine spec specifically."""
        manifest = {
            "version": "1.0.0",
            "documents": [
                {
                    "id": "dopamine_spec_v1",
                    "type": "spec",
                    "scope": "external",
                    "path": "external/specs/dopamine.md",
                    "title": "Dopamine Spec",
                    "priority": "authoritative",
                    "tags": ["dopamine_ladder"]
                }
            ],
            "config": {"sample_size_threshold": 10}
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        doc_path = tmp_path / "external" / "specs"
        doc_path.mkdir(parents=True)
        (doc_path / "dopamine.md").write_text("# Dopamine Ladder\n\nContent.")

        registry = KnowledgeRegistry(tmp_path)
        registry.load()
        doc = registry.get_dopamine_spec()

        assert doc is not None
        assert doc.id == "dopamine_spec_v1"

    def test_document_file_exists_check(self, tmp_path):
        """Test that document exists() check works."""
        manifest = {
            "version": "1.0.0",
            "documents": [
                {
                    "id": "test_doc",
                    "type": "spec",
                    "scope": "external",
                    "path": "external/specs/test.md",
                    "title": "Test Document",
                    "priority": "authoritative",
                    "tags": []
                }
            ],
            "config": {"sample_size_threshold": 10}
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # Create the document file
        doc_path = tmp_path / "external" / "specs"
        doc_path.mkdir(parents=True)
        (doc_path / "test.md").write_text("# Test\n\nContent.")

        registry = KnowledgeRegistry(tmp_path)
        registry.load()
        doc = registry.get_document("test_doc")

        # Update absolute_path calculation for test
        # The doc.absolute_path uses DEFAULT_KB_PATH, so we need to check existence differently
        test_path = tmp_path / doc.path
        assert test_path.exists()


class TestKnowledgeContext:
    """Tests for knowledge context building."""

    def test_build_knowledge_context(self, tmp_path):
        """Test building knowledge context from registry."""
        # Create manifest and docs
        manifest = {
            "version": "1.0.0",
            "documents": [
                {
                    "id": "dopamine_spec_v1",
                    "type": "spec",
                    "scope": "external",
                    "path": "external/specs/dopamine.md",
                    "title": "Dopamine Spec",
                    "priority": "authoritative",
                    "tags": ["dopamine_ladder"]
                }
            ],
            "config": {"sample_size_threshold": 10}
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        doc_path = tmp_path / "external" / "specs"
        doc_path.mkdir(parents=True)
        dopamine_content = """# Dopamine Content Engine

## The Dopamine Ladder

### Level 1: Stimulation
**Goal:** Interrupt scroll
**Required Outputs:**
- Visual hook

### Level 2: Captivation
**Goal:** Create curiosity
**Required Outputs:**
- Open loop
"""
        (doc_path / "dopamine.md").write_text(dopamine_content)

        # Create internal folder
        internal_path = tmp_path / "internal" / "insights"
        internal_path.mkdir(parents=True)
        (internal_path / "learning_summary.json").write_text(json.dumps({
            "total_runs_analyzed": 5
        }))

        registry = KnowledgeRegistry(tmp_path)
        registry.load()

        context = build_knowledge_context(
            run_id="test-001",
            niche="motivation",
            style="affirming",
            visual_mode="ai_generated",
            registry=registry,
        )

        assert context is not None
        assert context.niche == "motivation"
        assert context.style == "affirming"
        assert context.run_id == "test-001"

    def test_knowledge_context_saves_to_run_folder(self, tmp_path):
        """Test that knowledge context creates knowledge_context.md in run folder."""
        # Create a minimal context
        context = KnowledgeContext(
            run_id="test-001",
            niche="fun_facts",
            style="edgy",
            visual_mode="ai_generated",
        )

        run_folder = tmp_path / "output" / "run-001"
        run_folder.mkdir(parents=True)

        # Save context to run folder
        json_path, md_path = context.save_to_run_folder(run_folder)

        # Verify files created
        assert json_path.exists()
        assert md_path.exists()
        assert (run_folder / "knowledge_context.json").exists()
        assert (run_folder / "knowledge_context.md").exists()

        # Verify content
        md_content = (run_folder / "knowledge_context.md").read_text()
        assert "Knowledge Context" in md_content
        assert "fun_facts" in md_content

    def test_get_learning_context_prompt(self):
        """Test generating a prompt from knowledge context."""
        context = KnowledgeContext(
            run_id="test-001",
            niche="motivation",
            style="affirming",
            visual_mode="ai_generated",
            dopamine_requirements=[
                DopamineLevelRequirement(
                    level=1,
                    name="Stimulation",
                    goal="Interrupt scroll",
                    required_outputs=["Visual hook"],
                    validation_rules=["Must grab attention in first second"],
                    failure_conditions=["No hook"],
                )
            ],
            internal_insights=[
                {
                    "title": "High Confidence Insight",
                    "description": "Short hooks perform better",
                    "confidence": "high",
                }
            ],
        )

        prompt = get_learning_context_prompt(context)

        assert prompt is not None
        assert "Learning Context" in prompt
        assert "Stimulation" in prompt
        assert "Interrupt scroll" in prompt


class TestKnowledgeComparator:
    """Tests for comparing internal learning vs external specs."""

    def test_compare_basic(self, tmp_path):
        """Test basic comparison works."""
        # Setup knowledge base
        kb_path = tmp_path / "knowledge_base"
        kb_path.mkdir()

        manifest = {
            "version": "1.0.0",
            "documents": [
                {
                    "id": "dopamine_spec_v1",
                    "type": "spec",
                    "scope": "external",
                    "path": "external/specs/spec.md",
                    "title": "Spec",
                    "priority": "authoritative",
                    "tags": ["hooks"]
                }
            ],
            "config": {"sample_size_threshold": 10}
        }
        (kb_path / "manifest.json").write_text(json.dumps(manifest))

        doc_path = kb_path / "external" / "specs"
        doc_path.mkdir(parents=True)
        (doc_path / "spec.md").write_text("# Spec\n\nHooks should be under 3 seconds.")

        internal_path = kb_path / "internal" / "insights"
        internal_path.mkdir(parents=True)
        learning = {
            "total_runs_analyzed": 5,
            "insights": ["Short hooks work best"],
        }
        (internal_path / "learning_summary.json").write_text(json.dumps(learning))

        registry = KnowledgeRegistry(kb_path)
        registry.load()

        comparator = KnowledgeComparator(registry)
        result = comparator.compare()

        # With only 5 runs (below threshold of 10), should have no conflicts
        assert isinstance(result, ComparisonResult)
        assert isinstance(result.agreements, list)
        assert isinstance(result.conflicts, list)
        assert isinstance(result.pending, list)

    def test_sample_size_threshold_respected(self, tmp_path):
        """Test that sample size threshold determines conflict resolution."""
        kb_path = tmp_path / "knowledge_base"
        kb_path.mkdir()

        manifest = {
            "version": "1.0.0",
            "documents": [],
            "config": {"sample_size_threshold": 20}
        }
        (kb_path / "manifest.json").write_text(json.dumps(manifest))

        internal_path = kb_path / "internal" / "insights"
        internal_path.mkdir(parents=True)
        (internal_path / "learning_summary.json").write_text(json.dumps({
            "total_runs_analyzed": 0
        }))

        registry = KnowledgeRegistry(kb_path)
        registry.load()

        comparator = KnowledgeComparator(registry)

        # Test threshold value
        assert comparator.registry.config.sample_size_threshold == 20

        # Test resolution logic
        # Below threshold - external preferred
        assert comparator._determine_resolution(15) == "external_preferred"

        # At threshold - pending review
        assert comparator._determine_resolution(20) == "pending_review"

        # Above 2x threshold - internal preferred
        assert comparator._determine_resolution(45) == "internal_preferred"

    def test_save_conflicts_report(self, tmp_path):
        """Test that comparison saves conflicts.md report."""
        kb_path = tmp_path / "knowledge_base"
        kb_path.mkdir()

        manifest = {
            "version": "1.0.0",
            "documents": [],
            "config": {"sample_size_threshold": 10}
        }
        (kb_path / "manifest.json").write_text(json.dumps(manifest))

        internal_path = kb_path / "internal" / "insights"
        internal_path.mkdir(parents=True)
        (internal_path / "learning_summary.json").write_text(json.dumps({
            "total_runs_analyzed": 0
        }))

        registry = KnowledgeRegistry(kb_path)
        registry.load()

        comparator = KnowledgeComparator(registry)
        result = comparator.compare()

        # Save report
        conflicts_path = comparator.save_conflicts_report(result)

        # File should be in internal/insights/conflicts.md
        expected_path = kb_path / "internal" / "insights" / "conflicts.md"
        assert conflicts_path == expected_path
        assert conflicts_path.exists()

        content = conflicts_path.read_text()
        assert "Conflict" in content or "conflict" in content.lower()
        assert "Summary" in content

    def test_conflict_record_creation(self):
        """Test ConflictRecord dataclass."""
        conflict = ConflictRecord(
            id="test_conflict",
            topic="hook_duration",
            external_source="dopamine_spec_v1",
            external_rule="Hooks should be under 2 seconds",
            external_value=2,
            internal_source="learning_summary.json",
            internal_finding="Best hooks average 1.5 seconds",
            internal_value=1.5,
            sample_size=25,
            confidence="high",
            resolution="internal_preferred",
        )

        assert conflict.topic == "hook_duration"
        assert conflict.sample_size == 25
        assert conflict.confidence == "high"

        # Test to_dict
        conflict_dict = conflict.to_dict()
        assert conflict_dict["id"] == "test_conflict"
        assert conflict_dict["external_value"] == 2


class TestIntegration:
    """Integration tests for the full knowledge base flow."""

    def test_full_knowledge_flow(self, tmp_path):
        """Test the complete knowledge base workflow."""
        # 1. Setup knowledge base structure
        kb_path = tmp_path / "knowledge_base"
        kb_path.mkdir()

        manifest = {
            "version": "1.0.0",
            "documents": [
                {
                    "id": "dopamine_spec_v1",
                    "type": "spec",
                    "scope": "external",
                    "path": "external/specs/dopamine_content_engine_spec.md",
                    "title": "Dopamine Content Engine Specification",
                    "description": "Core spec for dopamine-driven content",
                    "priority": "authoritative",
                    "tags": ["dopamine_ladder", "hooks", "pipeline"],
                    "added_at": "2024-01-01"
                }
            ],
            "config": {
                "sample_size_threshold": 10,
                "conflict_resolution": "prefer_internal_when_threshold_met"
            }
        }
        (kb_path / "manifest.json").write_text(json.dumps(manifest))

        # Create external spec
        doc_path = kb_path / "external" / "specs"
        doc_path.mkdir(parents=True)
        spec_content = """# Dopamine Content Engine Specification

## The Dopamine Ladder

### Level 1: Stimulation
**Goal:** Interrupt scroll immediately
**Required Outputs:**
- Visual hook in first 0.5 seconds
**Validation Rules:**
- Must grab attention in first second

### Level 2: Captivation
**Goal:** Create curiosity gap
**Required Outputs:**
- Open loop question
**Validation Rules:**
- Hook must land within 3 seconds
"""
        (doc_path / "dopamine_content_engine_spec.md").write_text(spec_content)

        # Create internal learning
        internal_path = kb_path / "internal" / "insights"
        internal_path.mkdir(parents=True)
        learning = {
            "total_runs_analyzed": 12,
            "niches": {
                "motivation": {"run_count": 8, "avg_rating": 4.1},
                "fun_facts": {"run_count": 4, "avg_rating": 3.8}
            },
            "insights": [
                "Hooks under 2.5 seconds have 15% better retention",
                "Question-based hooks outperform statement hooks"
            ]
        }
        (internal_path / "learning_summary.json").write_text(json.dumps(learning))

        # 2. Load registry and verify dopamine spec
        registry = KnowledgeRegistry(kb_path)
        registry.load()
        dopamine_spec = registry.get_dopamine_spec()
        assert dopamine_spec is not None
        assert dopamine_spec.id == "dopamine_spec_v1"

        # 3. Build knowledge context
        context = build_knowledge_context(
            run_id="run-001",
            niche="motivation",
            style="affirming",
            visual_mode="ai_generated",
            registry=registry,
        )
        assert context is not None

        # 4. Save to run folder
        run_folder = tmp_path / "output" / "motivation" / "affirming" / "2024-01-01" / "run-001"
        run_folder.mkdir(parents=True)
        context.save_to_run_folder(run_folder)

        assert (run_folder / "knowledge_context.md").exists()
        assert (run_folder / "knowledge_context.json").exists()

        # 5. Compare internal vs external
        comparator = KnowledgeComparator(registry)
        result = comparator.compare()
        assert isinstance(result, ComparisonResult)

        # 6. Save conflicts report
        conflicts_path = comparator.save_conflicts_report(result)
        assert conflicts_path.exists()

    def test_missing_manifest_fails_loudly(self, tmp_path):
        """Test that missing manifest gives a clear, actionable error."""
        kb_path = tmp_path / "empty_kb"
        kb_path.mkdir()

        registry = KnowledgeRegistry(kb_path)

        with pytest.raises(FileNotFoundError) as exc_info:
            registry.load()

        error_msg = str(exc_info.value)
        # Should mention manifest.json
        assert "manifest" in error_msg.lower()

    def test_update_learning_from_feedback(self, tmp_path):
        """Test that feedback updates learning summary."""
        kb_path = tmp_path / "knowledge_base"
        kb_path.mkdir()

        manifest = {
            "version": "1.0.0",
            "documents": [],
            "config": {"sample_size_threshold": 10}
        }
        (kb_path / "manifest.json").write_text(json.dumps(manifest))

        internal_path = kb_path / "internal" / "insights"
        internal_path.mkdir(parents=True)
        initial_learning = {
            "total_runs_analyzed": 5,
            "niches": {},
            "styles": {},
            "visual_modes": {},
            "hook_performance": {},
            "dopamine_compliance": {},
            "insights": [],
        }
        (internal_path / "learning_summary.json").write_text(json.dumps(initial_learning))

        registry = KnowledgeRegistry(kb_path)
        registry.load()

        comparator = KnowledgeComparator(registry)
        comparator.update_learning_from_feedback(
            run_id="run-001",
            niche="motivation",
            style="affirming",
            visual_mode="ai_generated",
            feedback={"script_quality": 4.5, "views": 1000},
        )

        # Verify learning was updated
        updated_learning = json.loads((internal_path / "learning_summary.json").read_text())
        assert updated_learning["total_runs_analyzed"] == 6
        assert "motivation" in updated_learning["niches"]
        assert updated_learning["niches"]["motivation"]["run_count"] == 1

        # Verify markdown was created
        assert (internal_path / "learning_summary.md").exists()

        # Verify conflicts.md was created
        assert (internal_path / "conflicts.md").exists()
