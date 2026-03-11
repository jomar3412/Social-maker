"""
OCR-based screenshot importer for social media analytics.

Extracts metrics from TikTok, Instagram, and YouTube analytics screenshots
using local OCR (pytesseract) - NO API KEYS REQUIRED.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING
from datetime import datetime
import json

if TYPE_CHECKING:
    from PIL import Image as PILImage

try:
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


class Platform(Enum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"


class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ExtractedMetrics:
    """Structured metrics extracted from screenshot."""
    views: Optional[int] = None
    avg_watch_time_seconds: Optional[float] = None
    retention_percent: Optional[float] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    posted_at: Optional[str] = None
    extra_metrics: dict = field(default_factory=dict)
    extracted_text: str = ""
    confidence: dict = field(default_factory=dict)
    platform: str = ""
    parse_errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "views": self.views,
            "avg_watch_time_seconds": self.avg_watch_time_seconds,
            "retention_percent": self.retention_percent,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "posted_at": self.posted_at,
            "extra_metrics": self.extra_metrics,
            "extracted_text": self.extracted_text,
            "confidence": self.confidence,
            "platform": self.platform,
            "parse_errors": self.parse_errors,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractedMetrics":
        return cls(
            views=data.get("views"),
            avg_watch_time_seconds=data.get("avg_watch_time_seconds"),
            retention_percent=data.get("retention_percent"),
            likes=data.get("likes"),
            comments=data.get("comments"),
            shares=data.get("shares"),
            posted_at=data.get("posted_at"),
            extra_metrics=data.get("extra_metrics", {}),
            extracted_text=data.get("extracted_text", ""),
            confidence=data.get("confidence", {}),
            platform=data.get("platform", ""),
            parse_errors=data.get("parse_errors", []),
        )


class OCRImporter:
    """
    Extract analytics metrics from social media screenshots.

    Uses pytesseract for local OCR - no API keys needed.
    """

    # Allowed image types
    ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self):
        if not HAS_OCR:
            raise ImportError(
                "pytesseract and Pillow are required. "
                "Install with: pip install pytesseract Pillow"
            )

    def validate_image(self, file_path: Path) -> tuple[bool, str]:
        """
        Validate image file.

        Returns:
            (is_valid, error_message)
        """
        if not file_path.exists():
            return False, "File not found"

        # Check extension
        if file_path.suffix.lower() not in self.ALLOWED_EXTENSIONS:
            return False, f"Invalid file type. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}"

        # Check file size
        if file_path.stat().st_size > self.MAX_FILE_SIZE:
            return False, f"File too large. Max size: {self.MAX_FILE_SIZE // (1024*1024)}MB"

        # Try to open as image
        try:
            with Image.open(file_path) as img:
                img.verify()
        except Exception as e:
            return False, f"Invalid image file: {e}"

        return True, ""

    def preprocess_image(self, image: "PILImage.Image") -> "PILImage.Image":
        """
        Preprocess image for better OCR results.
        """
        # Convert to RGB if necessary
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Increase contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # Increase sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)

        # Convert to grayscale for OCR
        image = image.convert("L")

        # Apply slight blur to reduce noise
        image = image.filter(ImageFilter.MedianFilter(size=3))

        return image

    def extract_text(self, file_path: Path) -> str:
        """
        Extract text from image using OCR.
        """
        with Image.open(file_path) as img:
            # Preprocess
            processed = self.preprocess_image(img)

            # Run OCR with custom config for better number recognition
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(processed, config=custom_config)

        return text

    def extract_metrics(
        self,
        file_path: Path,
        platform: Platform,
    ) -> ExtractedMetrics:
        """
        Extract metrics from screenshot.

        Args:
            file_path: Path to screenshot image
            platform: Social media platform

        Returns:
            ExtractedMetrics with parsed values
        """
        # Validate
        is_valid, error = self.validate_image(file_path)
        if not is_valid:
            metrics = ExtractedMetrics()
            metrics.parse_errors.append(error)
            return metrics

        # Extract text
        try:
            text = self.extract_text(file_path)
        except Exception as e:
            metrics = ExtractedMetrics()
            metrics.parse_errors.append(f"OCR failed: {e}")
            return metrics

        # Parse based on platform
        if platform == Platform.TIKTOK:
            metrics = self._parse_tiktok(text)
        elif platform == Platform.INSTAGRAM:
            metrics = self._parse_instagram(text)
        elif platform == Platform.YOUTUBE:
            metrics = self._parse_youtube(text)
        else:
            metrics = ExtractedMetrics()
            metrics.parse_errors.append(f"Unknown platform: {platform}")

        metrics.extracted_text = text
        metrics.platform = platform.value

        return metrics

    def _parse_tiktok(self, text: str) -> ExtractedMetrics:
        """Parse TikTok analytics screenshot."""
        metrics = ExtractedMetrics()
        text_lower = text.lower()
        lines = text.split("\n")

        # Views - look for "views" with number nearby
        views = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*(?:views?|video views?)",
            r"(?:views?|video views?)\s*(\d[\d,\.]*)",
            r"total\s*(?:views?|plays?)\s*(\d[\d,\.]*)",
        ])
        if views is not None:
            metrics.views = views
            metrics.confidence["views"] = Confidence.HIGH.value

        # Average watch time - formats: "0:12", "12s", "1:30"
        avg_time = self._find_time_value(text, [
            r"(?:average|avg\.?)\s*(?:watch|view)\s*time\s*[:\s]*(\d+[:\d]*\s*(?:s|sec)?)",
            r"(\d+:\d+)\s*(?:average|avg)",
            r"(?:watched|watch)\s*(?:for)?\s*(\d+[:\d]*\s*(?:s|sec)?)",
        ])
        if avg_time is not None:
            metrics.avg_watch_time_seconds = avg_time
            metrics.confidence["avg_watch_time_seconds"] = Confidence.MEDIUM.value

        # Retention / Watched full video
        retention = self._find_percentage(text, [
            r"(?:watched\s*full\s*video|completion|retention)\s*[:\s]*(\d+\.?\d*)\s*%?",
            r"(\d+\.?\d*)\s*%?\s*(?:watched\s*full|completion|retention)",
            r"(?:average|avg)\s*(?:percentage|%)\s*(?:viewed|watched)\s*[:\s]*(\d+\.?\d*)",
        ])
        if retention is not None:
            metrics.retention_percent = retention
            metrics.confidence["retention_percent"] = Confidence.MEDIUM.value

        # Likes
        likes = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*(?:likes?|hearts?)",
            r"(?:likes?|hearts?)\s*(\d[\d,\.]*)",
        ])
        if likes is not None:
            metrics.likes = likes
            metrics.confidence["likes"] = Confidence.HIGH.value

        # Comments
        comments = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*comments?",
            r"comments?\s*(\d[\d,\.]*)",
        ])
        if comments is not None:
            metrics.comments = comments
            metrics.confidence["comments"] = Confidence.HIGH.value

        # Shares
        shares = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*shares?",
            r"shares?\s*(\d[\d,\.]*)",
        ])
        if shares is not None:
            metrics.shares = shares
            metrics.confidence["shares"] = Confidence.HIGH.value

        # Extra TikTok metrics
        total_play_time = self._find_time_value(text, [
            r"total\s*play\s*time\s*[:\s]*(\d+[:\d]*)",
        ])
        if total_play_time:
            metrics.extra_metrics["total_play_time_seconds"] = total_play_time

        # Traffic source
        if "for you" in text_lower or "fyp" in text_lower:
            metrics.extra_metrics["traffic_source"] = "For You Page"
        elif "following" in text_lower:
            metrics.extra_metrics["traffic_source"] = "Following"

        metrics.platform = "tiktok"
        return metrics

    def _parse_instagram(self, text: str) -> ExtractedMetrics:
        """Parse Instagram analytics screenshot."""
        metrics = ExtractedMetrics()
        text_lower = text.lower()

        # Views/Plays
        views = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*(?:plays?|views?)",
            r"(?:plays?|views?)\s*(\d[\d,\.]*)",
            r"(?:video|reel)\s*(?:plays?|views?)\s*(\d[\d,\.]*)",
        ])
        if views is not None:
            metrics.views = views
            metrics.confidence["views"] = Confidence.HIGH.value

        # Watch time (Instagram shows in various formats)
        avg_time = self._find_time_value(text, [
            r"(?:watch|view)\s*time\s*[:\s]*(\d+[:\d]*)",
            r"(?:average|avg)\s*(?:watch|view)\s*[:\s]*(\d+[:\d]*)",
        ])
        if avg_time is not None:
            metrics.avg_watch_time_seconds = avg_time
            metrics.confidence["avg_watch_time_seconds"] = Confidence.MEDIUM.value

        # Likes
        likes = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*likes?",
            r"likes?\s*(\d[\d,\.]*)",
        ])
        if likes is not None:
            metrics.likes = likes
            metrics.confidence["likes"] = Confidence.HIGH.value

        # Comments
        comments = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*comments?",
            r"comments?\s*(\d[\d,\.]*)",
        ])
        if comments is not None:
            metrics.comments = comments
            metrics.confidence["comments"] = Confidence.HIGH.value

        # Shares/Sends
        shares = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*(?:shares?|sends?)",
            r"(?:shares?|sends?)\s*(\d[\d,\.]*)",
        ])
        if shares is not None:
            metrics.shares = shares
            metrics.confidence["shares"] = Confidence.HIGH.value

        # Extra Instagram metrics
        reach = self._find_metric_value(text, [
            r"(?:accounts?\s*)?reached\s*(\d[\d,\.]*)",
            r"(\d[\d,\.]*)\s*(?:accounts?\s*)?reached",
            r"reach\s*(\d[\d,\.]*)",
        ])
        if reach:
            metrics.extra_metrics["accounts_reached"] = reach

        saves = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*saves?",
            r"saves?\s*(\d[\d,\.]*)",
        ])
        if saves:
            metrics.extra_metrics["saves"] = saves

        metrics.platform = "instagram"
        return metrics

    def _parse_youtube(self, text: str) -> ExtractedMetrics:
        """Parse YouTube analytics screenshot."""
        metrics = ExtractedMetrics()
        text_lower = text.lower()

        # Views
        views = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*views?",
            r"views?\s*(\d[\d,\.]*)",
        ])
        if views is not None:
            metrics.views = views
            metrics.confidence["views"] = Confidence.HIGH.value

        # Average view duration - YouTube format: "0:45" or "1:23"
        avg_time = self._find_time_value(text, [
            r"(?:average|avg\.?)\s*(?:view\s*)?duration\s*[:\s]*(\d+:\d+)",
            r"(?:average|avg\.?)\s*(?:watch|view)\s*time\s*[:\s]*(\d+:\d+)",
        ])
        if avg_time is not None:
            metrics.avg_watch_time_seconds = avg_time
            metrics.confidence["avg_watch_time_seconds"] = Confidence.HIGH.value

        # Average percentage viewed
        retention = self._find_percentage(text, [
            r"(?:average|avg\.?)\s*(?:percentage|%)\s*(?:viewed|watched)\s*[:\s]*(\d+\.?\d*)",
            r"(\d+\.?\d*)\s*%?\s*(?:average|avg\.?)?\s*(?:viewed|watched|retention)",
        ])
        if retention is not None:
            metrics.retention_percent = retention
            metrics.confidence["retention_percent"] = Confidence.MEDIUM.value

        # Likes
        likes = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*likes?",
            r"likes?\s*(\d[\d,\.]*)",
        ])
        if likes is not None:
            metrics.likes = likes
            metrics.confidence["likes"] = Confidence.HIGH.value

        # Comments
        comments = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*comments?",
            r"comments?\s*(\d[\d,\.]*)",
        ])
        if comments is not None:
            metrics.comments = comments
            metrics.confidence["comments"] = Confidence.HIGH.value

        # Shares
        shares = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*shares?",
            r"shares?\s*(\d[\d,\.]*)",
        ])
        if shares is not None:
            metrics.shares = shares
            metrics.confidence["shares"] = Confidence.HIGH.value

        # Extra YouTube metrics
        impressions = self._find_metric_value(text, [
            r"(\d[\d,\.]*)\s*impressions?",
            r"impressions?\s*(\d[\d,\.]*)",
        ])
        if impressions:
            metrics.extra_metrics["impressions"] = impressions

        ctr = self._find_percentage(text, [
            r"(?:click[- ]?through|ctr)\s*[:\s]*(\d+\.?\d*)",
        ])
        if ctr:
            metrics.extra_metrics["click_through_rate"] = ctr

        watch_time_hours = self._find_metric_value(text, [
            r"(?:watch\s*time|hours\s*watched)\s*[:\s]*(\d+\.?\d*)\s*(?:hours?|hrs?)",
        ])
        if watch_time_hours:
            metrics.extra_metrics["total_watch_time_hours"] = watch_time_hours

        metrics.platform = "youtube"
        return metrics

    def _find_metric_value(self, text: str, patterns: list[str]) -> Optional[int]:
        """
        Find a numeric metric value using regex patterns.

        Handles:
        - Commas in numbers (12,345)
        - Decimal points (12.3K)
        - K/M/B suffixes
        """
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value_str = match.group(1)
                return self._parse_number(value_str)
        return None

    def _find_time_value(self, text: str, patterns: list[str]) -> Optional[float]:
        """
        Find a time value and convert to seconds.

        Handles:
        - mm:ss format (1:30 -> 90)
        - hh:mm:ss format (1:02:30 -> 3750)
        - Xs format (45s -> 45)
        """
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                time_str = match.group(1).strip()
                return self._parse_time(time_str)
        return None

    def _find_percentage(self, text: str, patterns: list[str]) -> Optional[float]:
        """Find a percentage value."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value_str = match.group(1)
                try:
                    return float(value_str.replace(",", ""))
                except ValueError:
                    continue
        return None

    def _parse_number(self, value_str: str) -> Optional[int]:
        """
        Parse a number string to int.

        Handles:
        - 12,345 -> 12345
        - 12.3K -> 12300
        - 1.2M -> 1200000
        - 1B -> 1000000000
        """
        if value_str is None:
            return None
        value_str = value_str.strip().upper()
        if not value_str:
            return None

        # Remove commas
        value_str = value_str.replace(",", "")

        # Handle K/M/B suffixes
        multiplier = 1
        if value_str.endswith("K"):
            multiplier = 1000
            value_str = value_str[:-1]
        elif value_str.endswith("M"):
            multiplier = 1000000
            value_str = value_str[:-1]
        elif value_str.endswith("B"):
            multiplier = 1000000000
            value_str = value_str[:-1]

        try:
            return int(float(value_str) * multiplier)
        except ValueError:
            return None

    def _parse_time(self, time_str: str) -> Optional[float]:
        """
        Parse time string to seconds.

        Handles:
        - 1:30 -> 90
        - 1:02:30 -> 3750
        - 45s -> 45
        - 45 sec -> 45
        """
        time_str = time_str.strip().lower()

        # Remove 's', 'sec', 'seconds'
        time_str = re.sub(r"\s*(s|sec|seconds?)$", "", time_str)

        if ":" in time_str:
            parts = time_str.split(":")
            try:
                if len(parts) == 2:
                    # mm:ss
                    minutes, seconds = int(parts[0]), int(parts[1])
                    return minutes * 60 + seconds
                elif len(parts) == 3:
                    # hh:mm:ss
                    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                    return hours * 3600 + minutes * 60 + seconds
            except ValueError:
                return None
        else:
            try:
                return float(time_str)
            except ValueError:
                return None

        return None

    def _parse_percent(self, value_str: str) -> Optional[float]:
        """
        Parse percentage string to float.

        Handles:
        - 65% -> 65.0
        - 65.5% -> 65.5
        - 65 -> 65.0 (assumes percentage)
        """
        if value_str is None:
            return None
        value_str = value_str.strip()
        if not value_str:
            return None

        # Remove % sign if present
        value_str = value_str.rstrip("%").strip()

        try:
            return float(value_str)
        except ValueError:
            return None


def parse_text_for_platform(text: str, platform: str) -> ExtractedMetrics:
    """
    Parse pre-extracted text for a platform.

    Useful for testing without actual OCR.
    """
    importer = OCRImporter.__new__(OCRImporter)  # Skip __init__ check

    platform_enum = Platform(platform.lower())

    if platform_enum == Platform.TIKTOK:
        metrics = importer._parse_tiktok(text)
    elif platform_enum == Platform.INSTAGRAM:
        metrics = importer._parse_instagram(text)
    elif platform_enum == Platform.YOUTUBE:
        metrics = importer._parse_youtube(text)
    else:
        metrics = ExtractedMetrics()

    metrics.extracted_text = text
    metrics.platform = platform
    return metrics
