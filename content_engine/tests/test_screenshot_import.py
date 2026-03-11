"""
Tests for Screenshot Import feature.

Tests cover:
- OCR importer (text extraction and metric parsing)
- Draft storage in RunStore
- Platform-specific parsers
- Number parsing (K/M/B suffixes)
- Confidence scoring
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json


class TestOCRImporter:
    """Test the OCR importer module."""

    def test_platform_enum(self):
        """Test Platform enum values."""
        from content_engine.services.ocr_importer import Platform

        assert Platform.TIKTOK.value == "tiktok"
        assert Platform.INSTAGRAM.value == "instagram"
        assert Platform.YOUTUBE.value == "youtube"

    def test_extracted_metrics_to_dict(self):
        """Test ExtractedMetrics serialization."""
        from content_engine.services.ocr_importer import ExtractedMetrics

        metrics = ExtractedMetrics(
            views=1000,
            likes=50,
            comments=10,
            shares=5,
            avg_watch_time_seconds=25.5,
            retention_percent=65.0,
            platform="tiktok",
            extracted_text="test text",
            confidence={"views": "high", "likes": "medium"},
        )

        result = metrics.to_dict()

        assert result["views"] == 1000
        assert result["likes"] == 50
        assert result["avg_watch_time_seconds"] == 25.5
        assert result["platform"] == "tiktok"
        assert result["confidence"]["views"] == "high"

    def test_parse_number_simple(self):
        """Test parsing simple numbers."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        assert importer._parse_number("1234") == 1234
        assert importer._parse_number("1,234") == 1234
        assert importer._parse_number("100") == 100

    def test_parse_number_with_k_suffix(self):
        """Test parsing numbers with K suffix."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        assert importer._parse_number("1.5K") == 1500
        assert importer._parse_number("10k") == 10000
        assert importer._parse_number("2.3K") == 2300

    def test_parse_number_with_m_suffix(self):
        """Test parsing numbers with M suffix."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        assert importer._parse_number("1M") == 1000000
        assert importer._parse_number("2.5m") == 2500000
        assert importer._parse_number("1.2M") == 1200000

    def test_parse_number_with_b_suffix(self):
        """Test parsing numbers with B suffix."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        assert importer._parse_number("1B") == 1000000000
        assert importer._parse_number("2.5b") == 2500000000

    def test_parse_number_none_for_invalid(self):
        """Test that invalid strings return None."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        assert importer._parse_number("abc") is None
        assert importer._parse_number("") is None
        assert importer._parse_number(None) is None

    def test_parse_time_mm_ss(self):
        """Test parsing time in mm:ss format."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        assert importer._parse_time("1:30") == 90.0
        assert importer._parse_time("0:45") == 45.0
        assert importer._parse_time("2:15") == 135.0

    def test_parse_time_seconds_only(self):
        """Test parsing time in seconds only."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        assert importer._parse_time("45") == 45.0
        assert importer._parse_time("45s") == 45.0
        assert importer._parse_time("30.5") == 30.5

    def test_parse_time_none_for_invalid(self):
        """Test that invalid time strings return None."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        assert importer._parse_time("invalid") is None
        assert importer._parse_time("") is None

    def test_parse_percent(self):
        """Test parsing percentage values."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        assert importer._parse_percent("65%") == 65.0
        assert importer._parse_percent("65.5%") == 65.5
        assert importer._parse_percent("100") == 100.0

    def test_parse_tiktok_sample(self):
        """Test parsing TikTok analytics text."""
        from content_engine.services.ocr_importer import OCRImporter, Platform

        importer = OCRImporter()

        # Simulated TikTok analytics text - using clearer formats
        sample_text = """
        15200 views
        1234 likes
        45 comments
        89 shares
        Average watch time: 12s
        Watched full video: 35%
        """

        metrics = importer._parse_tiktok(sample_text)

        assert metrics.views == 15200
        assert metrics.likes == 1234
        assert metrics.comments == 45
        assert metrics.shares == 89
        assert metrics.avg_watch_time_seconds == 12.0
        assert metrics.platform == "tiktok"

    def test_parse_youtube_sample(self):
        """Test parsing YouTube analytics text."""
        from content_engine.services.ocr_importer import OCRImporter, Platform

        importer = OCRImporter()

        # Simulated YouTube analytics text - using clearer formats
        sample_text = """
        5432 views
        Average view duration: 0:45
        234 likes
        18 comments
        12 shares
        """

        metrics = importer._parse_youtube(sample_text)

        assert metrics.views == 5432
        assert metrics.likes == 234
        assert metrics.comments == 18
        assert metrics.shares == 12
        assert metrics.avg_watch_time_seconds == 45.0
        assert metrics.platform == "youtube"

    def test_parse_instagram_sample(self):
        """Test parsing Instagram analytics text."""
        from content_engine.services.ocr_importer import OCRImporter, Platform

        importer = OCRImporter()

        # Simulated Instagram analytics text - using clearer formats
        sample_text = """
        8765 plays
        432 likes
        23 comments
        56 shares
        78 saves
        """

        metrics = importer._parse_instagram(sample_text)

        assert metrics.views == 8765
        assert metrics.likes == 432
        assert metrics.comments == 23
        assert metrics.shares == 56
        assert metrics.platform == "instagram"

    def test_confidence_levels(self):
        """Test that confidence levels are assigned."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        # Direct number match should be high confidence
        sample_text = "1234 views 100 likes"
        metrics = importer._parse_tiktok(sample_text)

        # Should have confidence dict when metrics are found
        assert metrics.views == 1234
        assert metrics.likes == 100
        assert "views" in metrics.confidence
        assert "likes" in metrics.confidence


class TestRunStoreDrafts:
    """Test draft storage in RunStore."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database."""
        from content_engine.services.run_store import RunStore

        db_path = tmp_path / "test_runs.db"
        return RunStore(db_path=db_path)

    def test_create_import_draft(self, temp_db):
        """Test creating an import draft."""
        draft_id = temp_db.create_import_draft(
            platform="tiktok",
            image_path="/path/to/image.png",
            extracted_json={"views": 1000, "likes": 50},
            run_id=None,
            post_url="https://tiktok.com/@user/video/123",
        )

        assert draft_id > 0

    def test_get_import_draft(self, temp_db):
        """Test retrieving an import draft."""
        draft_id = temp_db.create_import_draft(
            platform="instagram",
            image_path="/path/to/image.png",
            extracted_json={"views": 2000},
        )

        draft = temp_db.get_import_draft(draft_id)

        assert draft is not None
        assert draft["platform"] == "instagram"
        assert draft["image_path"] == "/path/to/image.png"

    def test_get_import_draft_not_found(self, temp_db):
        """Test getting non-existent draft returns None."""
        draft = temp_db.get_import_draft(99999)
        assert draft is None

    def test_get_pending_drafts(self, temp_db):
        """Test listing pending drafts."""
        # Create some drafts
        temp_db.create_import_draft("tiktok", "/a.png", {"views": 100})
        temp_db.create_import_draft("youtube", "/b.png", {"views": 200})
        temp_db.create_import_draft("instagram", "/c.png", {"views": 300})

        drafts = temp_db.get_pending_drafts(limit=10)

        assert len(drafts) == 3

    def test_confirm_import_draft(self, temp_db):
        """Test confirming a draft creates feedback and deletes draft."""
        # First create a run
        from content_engine.pipeline.models.run_config import RunConfig

        config = RunConfig(niche="motivation", style="affirming")
        temp_db.create_run(config.run_id, config.to_dict())

        # Create draft
        draft_id = temp_db.create_import_draft(
            platform="tiktok",
            image_path="/path/to/image.png",
            extracted_json={"views": 5000, "likes": 100},
        )

        # Confirm draft
        success = temp_db.confirm_import_draft(
            draft_id=draft_id,
            run_id=config.run_id,
            confirmed_values={
                "views": 5000,
                "likes": 100,
                "platform": "tiktok",
            },
        )

        assert success

        # Draft should be marked as confirmed (not deleted, for audit trail)
        draft = temp_db.get_import_draft(draft_id)
        assert draft is not None
        assert draft["status"] == "confirmed"
        assert draft["run_id"] == config.run_id

        # Feedback should be created
        feedback = temp_db.get_feedback(config.run_id)
        assert feedback is not None
        assert feedback.views == 5000
        assert feedback.likes == 100

    def test_delete_import_draft(self, temp_db):
        """Test deleting a draft."""
        draft_id = temp_db.create_import_draft(
            platform="youtube",
            image_path="/path/to/image.png",
            extracted_json={},
        )

        success = temp_db.delete_import_draft(draft_id)
        assert success

        # Should be gone
        draft = temp_db.get_import_draft(draft_id)
        assert draft is None

    def test_delete_import_draft_not_found(self, temp_db):
        """Test deleting non-existent draft returns False."""
        success = temp_db.delete_import_draft(99999)
        assert not success


class TestIntegration:
    """Integration tests for the full import flow."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database."""
        from content_engine.services.run_store import RunStore

        db_path = tmp_path / "test_runs.db"
        return RunStore(db_path=db_path)

    def test_full_import_flow(self, temp_db):
        """Test complete import flow from draft creation to feedback."""
        from content_engine.pipeline.models.run_config import RunConfig

        # 1. Create a run first
        config = RunConfig(niche="fun_facts", style="calm_minimal")
        temp_db.create_run(config.run_id, config.to_dict())

        # 2. Simulate OCR extraction
        extracted_data = {
            "views": 10000,
            "likes": 500,
            "comments": 25,
            "shares": 30,
            "avg_watch_time_seconds": 28.5,
            "retention_percent": 72.0,
            "platform": "tiktok",
            "extracted_text": "Sample OCR text",
            "confidence": {
                "views": "high",
                "likes": "medium",
            },
        }

        # 3. Create draft
        draft_id = temp_db.create_import_draft(
            platform="tiktok",
            image_path="/path/to/screenshot.png",
            extracted_json=extracted_data,
            run_id=config.run_id,
            post_url="https://tiktok.com/@user/video/123",
        )

        assert draft_id > 0

        # 4. Retrieve and verify draft
        draft = temp_db.get_import_draft(draft_id)
        assert draft["platform"] == "tiktok"
        assert draft["run_id"] == config.run_id

        # 5. User reviews and confirms (with possible edits)
        confirmed_values = {
            "views": 10000,  # Confirmed as correct
            "likes": 505,  # User corrected from 500
            "comments": 25,
            "shares": 30,
            "avg_watch_time": 28.5,
            "retention_pct": 72.0,
            "platform": "tiktok",
            "posted_url": "https://tiktok.com/@user/video/123",
        }

        success = temp_db.confirm_import_draft(
            draft_id=draft_id,
            run_id=config.run_id,
            confirmed_values=confirmed_values,
        )
        assert success

        # 6. Verify feedback was created
        feedback = temp_db.get_feedback(config.run_id)
        assert feedback is not None
        assert feedback.views == 10000
        assert feedback.likes == 505  # User's corrected value
        assert feedback.platform == "tiktok"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_number_edge_cases(self):
        """Test number parsing edge cases."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        # Numbers with spaces
        assert importer._parse_number("1 234") is None  # Space in middle

        # Very small K values
        assert importer._parse_number("0.1K") == 100

        # Decimal without suffix
        assert importer._parse_number("123.45") == 123

    def test_empty_ocr_text(self):
        """Test handling empty OCR text."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        metrics = importer._parse_tiktok("")

        # Should have platform set but no metrics
        assert metrics.platform == "tiktok"
        assert metrics.views is None
        assert metrics.likes is None

    def test_malformed_metrics(self):
        """Test parsing malformed metric text."""
        from content_engine.services.ocr_importer import OCRImporter

        importer = OCRImporter()

        # Random text without clear metrics
        sample_text = "This is just some random text without any metrics."

        metrics = importer._parse_tiktok(sample_text)

        # Should not crash, just have empty values
        assert metrics.platform == "tiktok"
