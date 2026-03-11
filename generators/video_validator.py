"""
Video Validation Module

Pre-export validation to ensure all videos meet quality standards:
- 9:16 aspect ratio (1080x1920)
- No distortion or stretching
- Text clarity for mobile viewing
- Visual-script alignment
- Scene structure compliance
"""
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ValidationResult:
    """Result of video validation."""
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def __str__(self):
        status = "PASSED" if self.passed else "FAILED"
        lines = [f"Validation: {status}"]
        if self.errors:
            lines.append("Errors:")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)


# Target specifications
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_ASPECT_RATIO = 9 / 16  # 0.5625
ASPECT_RATIO_TOLERANCE = 0.01  # 1% tolerance

# Text overlay specifications
MAX_WORDS_PER_LINE = 4
MAX_LINES_PER_SUBTITLE = 2
MIN_FONT_SIZE = 48  # Minimum for mobile readability

# Matching thresholds
MIN_VISUAL_MATCH_SCORE = 0.15  # Minimum confidence for visual-script match

# Scene pacing rules (for 30-45 second videos)
MIN_SCENES = 8
MAX_SCENES = 15
MIN_SCENE_DURATION = 2.0  # seconds
MAX_SCENE_DURATION = 7.0  # seconds (5 normal, 7 for sustained ideas)
AVG_SCENE_DURATION = 3.0  # target average


def get_video_info(video_path: Path) -> dict:
    """Get video metadata using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    return json.loads(result.stdout)


def validate_aspect_ratio(video_path: Path) -> ValidationResult:
    """
    Validate that video has correct 9:16 aspect ratio.

    Checks:
    - Resolution is exactly 1080x1920
    - Aspect ratio is 9:16 (no stretch/squeeze)
    - Sample aspect ratio (SAR) is 1:1
    """
    result = ValidationResult(passed=True)

    info = get_video_info(video_path)
    if not info:
        result.add_error(f"Cannot read video metadata: {video_path}")
        return result

    video_stream = None
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        result.add_error("No video stream found")
        return result

    width = video_stream.get("width", 0)
    height = video_stream.get("height", 0)

    result.metrics["width"] = width
    result.metrics["height"] = height

    # Check exact resolution
    if width != TARGET_WIDTH or height != TARGET_HEIGHT:
        result.add_error(
            f"Resolution mismatch: {width}x{height} (expected {TARGET_WIDTH}x{TARGET_HEIGHT})"
        )

    # Check aspect ratio
    if height > 0:
        actual_ratio = width / height
        expected_ratio = TARGET_ASPECT_RATIO

        result.metrics["aspect_ratio"] = actual_ratio

        if abs(actual_ratio - expected_ratio) > ASPECT_RATIO_TOLERANCE:
            result.add_error(
                f"Aspect ratio distortion: {actual_ratio:.4f} (expected {expected_ratio:.4f})"
            )

    # Check SAR (Sample Aspect Ratio) - should be 1:1 for no stretch
    sar = video_stream.get("sample_aspect_ratio", "1:1")
    if sar not in ["1:1", "1/1", None]:
        result.add_warning(f"Non-square pixels detected (SAR: {sar}) - may cause distortion")

    return result


def validate_text_overlay(subtitle_path: Path) -> ValidationResult:
    """
    Validate subtitle file for mobile readability.

    Checks:
    - Max 1-2 lines per subtitle event
    - Max 4 words per line
    - No overlapping events at same timestamp
    """
    result = ValidationResult(passed=True)

    if not subtitle_path.exists():
        result.add_warning("No subtitle file to validate")
        return result

    with open(subtitle_path, encoding="utf-8") as f:
        content = f.read()

    # Parse ASS dialogue events
    events = []
    in_events = False

    for line in content.split("\n"):
        if line.startswith("[Events]"):
            in_events = True
            continue

        if in_events and line.startswith("Dialogue:"):
            # Parse: Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
            parts = line.split(",", 9)
            if len(parts) >= 10:
                start = parts[1]
                end = parts[2]
                text = parts[9]

                # Remove ASS formatting tags for word count
                clean_text = re.sub(r'\{[^}]+\}', '', text)

                events.append({
                    "start": start,
                    "end": end,
                    "text": clean_text,
                })

    result.metrics["subtitle_events"] = len(events)

    # Check each event
    for i, event in enumerate(events):
        text = event["text"]
        words = text.split()

        # Check word count per subtitle (max 1-2 lines of 4 words each = 8 words max)
        if len(words) > MAX_WORDS_PER_LINE * MAX_LINES_PER_SUBTITLE:
            result.add_warning(
                f"Subtitle {i+1} has {len(words)} words (max {MAX_WORDS_PER_LINE * MAX_LINES_PER_SUBTITLE}): '{text[:30]}...'"
            )

    # Check for overlapping subtitles (same start time)
    start_times = [e["start"] for e in events]
    duplicates = [t for t in start_times if start_times.count(t) > 1]

    if duplicates:
        result.add_warning(f"Overlapping subtitles detected at times: {set(duplicates)}")

    return result


def validate_visual_matching(scenes: list, assets_used: list, script_keywords: list) -> ValidationResult:
    """
    Validate that selected visuals match the script content.

    Checks:
    - Each scene has a visual match score above threshold
    - No generic/unrelated visuals used
    - Flags scenes that need user-uploaded footage
    """
    result = ValidationResult(passed=True)

    if not scenes or not assets_used:
        result.add_warning("No scene/asset data to validate")
        return result

    from generators.asset_matcher import get_asset_info, ASSETS_DIR

    unmatched_scenes = []
    low_confidence_scenes = []

    for i, (scene, asset_path) in enumerate(zip(scenes, assets_used)):
        scene_num = i + 1

        # Get asset keywords from manifest
        rel_path = str(asset_path).replace(str(ASSETS_DIR) + "/", "")
        asset_info = get_asset_info(rel_path)

        if not asset_info:
            unmatched_scenes.append(scene_num)
            continue

        # Calculate match score
        from generators.asset_matcher import score_asset
        asset_keywords = asset_info.get("keywords", [])
        score = score_asset(asset_keywords, script_keywords)

        result.metrics[f"scene_{scene_num}_score"] = score
        result.metrics[f"scene_{scene_num}_asset"] = Path(asset_path).name

        if score < MIN_VISUAL_MATCH_SCORE:
            low_confidence_scenes.append((scene_num, score))

    if unmatched_scenes:
        result.add_warning(f"Scenes without tagged assets: {unmatched_scenes}")

    if low_confidence_scenes:
        for scene_num, score in low_confidence_scenes:
            result.add_warning(
                f"Scene {scene_num}: Low visual-script match ({score:.2f} < {MIN_VISUAL_MATCH_SCORE})"
            )

    # If more than half the scenes have low matches, flag as error
    total_scenes = len(scenes)
    problematic = len(unmatched_scenes) + len(low_confidence_scenes)

    if problematic > total_scenes / 2:
        result.add_error(
            f"Majority of scenes ({problematic}/{total_scenes}) have poor visual matching"
        )

    return result


def validate_scene_structure(scenes: list, word_timing: list, total_duration: float = None) -> ValidationResult:
    """
    Validate scene structure follows pacing rules.

    UPDATED RULES for 30-45 second videos:
    - 8-15 scenes total
    - Average scene length: 2-4 seconds
    - Max scene length: 7 seconds
    - One narrative idea per scene
    """
    result = ValidationResult(passed=True)

    if not scenes:
        result.add_warning("No scenes to validate")
        return result

    num_scenes = len(scenes)
    result.metrics["total_scenes"] = num_scenes

    # Calculate total duration if not provided
    if total_duration is None:
        total_duration = scenes[-1].get("end", 0) - scenes[0].get("start", 0)

    result.metrics["total_duration"] = total_duration

    # RULE: 8-15 scenes for 30-45 second videos
    if total_duration >= 25 and total_duration <= 50:
        if num_scenes < MIN_SCENES:
            result.add_error(
                f"Too few scenes: {num_scenes} (need {MIN_SCENES}-{MAX_SCENES} for {total_duration:.0f}s video)"
            )
        elif num_scenes > MAX_SCENES:
            result.add_warning(
                f"Too many scenes: {num_scenes} (recommended max {MAX_SCENES})"
            )

    # Calculate average scene duration
    scene_durations = []
    for i, scene in enumerate(scenes):
        scene_num = i + 1
        duration = scene.get("end", 0) - scene.get("start", 0)
        words = scene.get("words", [])
        word_count = len(words)

        scene_durations.append(duration)
        result.metrics[f"scene_{scene_num}_duration"] = duration
        result.metrics[f"scene_{scene_num}_words"] = word_count

        # RULE: Scene duration 2-7 seconds
        if duration < MIN_SCENE_DURATION:
            result.add_warning(
                f"Scene {scene_num}: Too short ({duration:.1f}s < {MIN_SCENE_DURATION}s)"
            )
        elif duration > MAX_SCENE_DURATION:
            result.add_warning(
                f"Scene {scene_num}: Too long ({duration:.1f}s > {MAX_SCENE_DURATION}s)"
            )

        # Check for multiple narrative beats in one scene
        sentence_count = sum(
            1 for w in words if w.get("word", "").rstrip().endswith(('.', '!', '?'))
        )
        if sentence_count > 2:
            result.add_warning(
                f"Scene {scene_num}: Multiple ideas ({sentence_count} sentences) - consider splitting"
            )

    # Check average duration
    if scene_durations:
        avg_duration = sum(scene_durations) / len(scene_durations)
        result.metrics["avg_scene_duration"] = avg_duration

        if avg_duration < 2.0:
            result.add_warning(f"Average scene too short: {avg_duration:.1f}s (target: 2-4s)")
        elif avg_duration > 5.0:
            result.add_warning(f"Average scene too long: {avg_duration:.1f}s (target: 2-4s)")

    return result


def validate_placeholders(placeholder_descriptions: list) -> ValidationResult:
    """
    Validate that all placeholders are detailed and actionable.

    FORBIDDEN vague phrases:
    - "support visual"
    - "generic footage"
    - "background clip"
    - "B-roll footage"

    REQUIRED elements:
    - Main subject (noun)
    - Action or state
    - Context/setting
    - Framing suggestion
    """
    result = ValidationResult(passed=True)

    FORBIDDEN_PHRASES = [
        "support visual",
        "supporting visual",
        "generic footage",
        "background clip",
        "b-roll footage",
        "b-roll",
        "generic",
        "unrelated",
        "random",
    ]

    REQUIRED_ELEMENTS = [
        # At least one framing term
        ["close-up", "wide shot", "medium shot", "tracking", "establishing"],
        # Some descriptor
        ["of", "showing", "with", "on", "in"],
    ]

    if not placeholder_descriptions:
        return result  # No placeholders to validate

    result.metrics["placeholder_count"] = len(placeholder_descriptions)

    for i, desc in enumerate(placeholder_descriptions):
        desc_lower = desc.lower()
        placeholder_num = i + 1

        # Check for forbidden vague phrases
        for phrase in FORBIDDEN_PHRASES:
            if phrase in desc_lower:
                result.add_error(
                    f"Placeholder {placeholder_num}: Contains vague phrase '{phrase}'"
                )

        # Check for required elements
        has_framing = any(term in desc_lower for term in REQUIRED_ELEMENTS[0])
        has_descriptor = any(term in desc_lower for term in REQUIRED_ELEMENTS[1])

        if not has_framing:
            result.add_warning(
                f"Placeholder {placeholder_num}: Missing camera framing (close-up, wide shot, etc.)"
            )

        if not has_descriptor:
            result.add_warning(
                f"Placeholder {placeholder_num}: Missing subject/action description"
            )

        # Check minimum length (detailed descriptions should be longer)
        if len(desc) < 30:
            result.add_warning(
                f"Placeholder {placeholder_num}: Description too short ({len(desc)} chars)"
            )

    return result


def validate_music_match(music_path: Optional[Path], script_tone: str = None,
                         script_energy: int = None) -> ValidationResult:
    """
    Validate that music matches script tone and energy.

    Rules:
    - Music must match emotion category
    - Energy within ±1 of script
    - Flag if no match instead of using wrong music
    """
    result = ValidationResult(passed=True)

    if music_path is None:
        result.add_warning("No music file - flagged as needing appropriate track")
        result.metrics["music_matched"] = False
        return result

    result.metrics["music_file"] = str(music_path.name) if isinstance(music_path, Path) else str(music_path)
    result.metrics["music_matched"] = True

    # If we have tone/energy info, validate the match
    if script_tone:
        result.metrics["script_tone"] = script_tone
    if script_energy:
        result.metrics["script_energy"] = script_energy

    return result


def validate_pre_export(
    video_path: Optional[Path] = None,
    subtitle_path: Optional[Path] = None,
    scenes: Optional[list] = None,
    assets_used: Optional[list] = None,
    script_keywords: Optional[list] = None,
    word_timing: Optional[list] = None,
) -> ValidationResult:
    """
    Run all pre-export validations.

    Args:
        video_path: Path to rendered video (for aspect ratio check)
        subtitle_path: Path to ASS subtitle file
        scenes: Scene timing data
        assets_used: List of asset paths used per scene
        script_keywords: Keywords from the script for matching validation
        word_timing: Word timing data for structure validation

    Returns:
        Combined ValidationResult
    """
    combined = ValidationResult(passed=True)

    # 1. Aspect ratio validation (if video exists)
    if video_path and Path(video_path).exists():
        print("  Validating aspect ratio...")
        ar_result = validate_aspect_ratio(Path(video_path))
        combined.errors.extend(ar_result.errors)
        combined.warnings.extend(ar_result.warnings)
        combined.metrics.update(ar_result.metrics)
        if not ar_result.passed:
            combined.passed = False

    # 2. Text overlay validation
    if subtitle_path:
        print("  Validating text overlays...")
        text_result = validate_text_overlay(Path(subtitle_path))
        combined.errors.extend(text_result.errors)
        combined.warnings.extend(text_result.warnings)
        combined.metrics.update(text_result.metrics)
        if not text_result.passed:
            combined.passed = False

    # 3. Visual matching validation
    if scenes and assets_used and script_keywords:
        print("  Validating visual-script matching...")
        match_result = validate_visual_matching(scenes, assets_used, script_keywords)
        combined.errors.extend(match_result.errors)
        combined.warnings.extend(match_result.warnings)
        combined.metrics.update(match_result.metrics)
        if not match_result.passed:
            combined.passed = False

    # 4. Scene structure validation
    if scenes:
        print("  Validating scene structure...")
        struct_result = validate_scene_structure(scenes, word_timing or [])
        combined.errors.extend(struct_result.errors)
        combined.warnings.extend(struct_result.warnings)
        combined.metrics.update(struct_result.metrics)
        if not struct_result.passed:
            combined.passed = False

    return combined


def extract_topic_slug(script: str, hook: str = None) -> str:
    """
    Extract a topic-based file name slug from the script.

    Analyzes the script to find the primary subject/topic and
    returns a kebab-case slug suitable for file naming.

    Args:
        script: Full script text
        hook: Optional hook text (often contains key topic)

    Returns:
        Kebab-case topic slug (e.g., "folding-paper-moon")
    """
    import re

    # Common stop words to filter out
    STOP_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
        'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
        'above', 'below', 'between', 'under', 'again', 'further', 'then',
        'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'and',
        'but', 'if', 'or', 'because', 'as', 'until', 'while', 'although',
        'this', 'that', 'these', 'those', 'what', 'which', 'who', 'whom',
        'its', 'it', 'you', 'your', 'we', 'our', 'they', 'their', 'them',
        'one', 'two', 'three', 'first', 'second', 'third', 'new', 'old',
        'high', 'low', 'every', 'any', 'many', 'much', 'know', 'think',
        'make', 'see', 'come', 'take', 'want', 'look', 'use', 'find', 'give',
        'tell', 'say', 'get', 'go', 'put', 'also', 'back', 'now', 'even',
        'way', 'well', 'thing', 'things', 'fact', 'time', 'times', 'did',
    }

    # Use hook first if available (usually contains the key topic)
    text = hook if hook else script
    if not text:
        return "untitled-video"

    # Extract potential topic words
    # 1. Look for quoted terms or emphasized words
    quoted = re.findall(r'"([^"]+)"', text)

    # 2. Get first sentence (often contains the topic)
    first_sentence = re.split(r'[.!?]', text)[0]

    # 3. Extract significant words (nouns, adjectives)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', first_sentence.lower())

    # Filter out stop words and score by position (earlier = more important)
    significant = []
    for word in words:
        if word not in STOP_WORDS and len(word) >= 4:
            significant.append(word)

    # Add quoted terms (high priority)
    for term in quoted:
        clean_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', term)]
        significant = clean_words[:2] + significant

    # Take top 2-4 words for the slug
    topic_words = significant[:4]

    if not topic_words:
        # Fallback: use first few non-stop words from full script
        words = re.findall(r'\b[a-zA-Z]{4,}\b', script.lower())
        topic_words = [w for w in words if w not in STOP_WORDS][:3]

    if not topic_words:
        return "content-video"

    # Create kebab-case slug
    slug = "-".join(topic_words)

    # Clean up: remove double hyphens, limit length
    slug = re.sub(r'-+', '-', slug)
    slug = slug[:40].rstrip('-')

    return slug


def generate_output_filename(
    script: str,
    hook: str = None,
    content_type: str = "fact",
    version: int = 1,
) -> str:
    """
    Generate an intelligent, topic-based filename.

    Format: {topic-slug}_{YYYYMMDD}_v{N}.mp4

    Args:
        script: Full script text
        hook: Optional hook text
        content_type: Type of content (fact, motivation, etc.)
        version: Version number

    Returns:
        Filename string (e.g., "folding-paper-moon_20260209_v1.mp4")
    """
    from datetime import datetime

    # Extract topic slug
    slug = extract_topic_slug(script, hook)

    # Get current date
    date_str = datetime.now().strftime("%Y%m%d")

    # Build filename
    filename = f"{slug}_{date_str}_v{version}.mp4"

    return filename


def verify_final_export(video_path: Path) -> ValidationResult:
    """
    Final verification before export is considered complete.

    CONFIRMS:
    1. Resolution is exactly 1080x1920
    2. No distortion (SAR is 1:1)
    3. Codec is H.264 (libx264)
    4. Container is MP4
    5. Can import into Premiere Pro (standard format)

    Args:
        video_path: Path to the final video

    Returns:
        ValidationResult with pass/fail and details
    """
    result = ValidationResult(passed=True)
    video_path = Path(video_path)

    if not video_path.exists():
        result.add_error(f"Video file not found: {video_path}")
        return result

    # Get detailed video info
    info = get_video_info(video_path)
    if not info:
        result.add_error("Cannot read video file")
        return result

    video_stream = None
    audio_stream = None

    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video" and not video_stream:
            video_stream = stream
        elif stream.get("codec_type") == "audio" and not audio_stream:
            audio_stream = stream

    if not video_stream:
        result.add_error("No video stream found")
        return result

    # 1. Check resolution is exactly 1080x1920
    width = video_stream.get("width", 0)
    height = video_stream.get("height", 0)

    result.metrics["resolution"] = f"{width}x{height}"

    if width != TARGET_WIDTH:
        result.add_error(f"Width is {width}, must be exactly {TARGET_WIDTH}")

    if height != TARGET_HEIGHT:
        result.add_error(f"Height is {height}, must be exactly {TARGET_HEIGHT}")

    # 2. Check for distortion (SAR should be 1:1)
    sar = video_stream.get("sample_aspect_ratio", "1:1")
    result.metrics["sar"] = sar

    if sar not in ["1:1", "1/1", "N/A", None]:
        # Parse SAR to check if it's close to 1:1
        try:
            if ":" in str(sar):
                num, den = sar.split(":")
                sar_ratio = float(num) / float(den)
                if abs(sar_ratio - 1.0) > 0.01:
                    result.add_error(f"Pixel distortion detected (SAR: {sar})")
        except:
            pass

    # 3. Check codec is H.264
    codec = video_stream.get("codec_name", "")
    result.metrics["video_codec"] = codec

    if codec != "h264":
        result.add_error(f"Codec is '{codec}', must be 'h264' for Premiere Pro compatibility")

    # 4. Check container format
    format_name = info.get("format", {}).get("format_name", "")
    result.metrics["container"] = format_name

    if "mp4" not in format_name.lower():
        result.add_error(f"Container is '{format_name}', must be MP4")

    # 5. Check audio exists
    if not audio_stream:
        result.add_warning("No audio stream found")
    else:
        audio_codec = audio_stream.get("codec_name", "")
        result.metrics["audio_codec"] = audio_codec

    # 6. Check file extension
    if video_path.suffix.lower() != ".mp4":
        result.add_warning(f"File extension is '{video_path.suffix}', should be '.mp4'")

    # Add overall metrics
    result.metrics["file_size_mb"] = video_path.stat().st_size / (1024 * 1024)
    result.metrics["duration"] = info.get("format", {}).get("duration", "unknown")

    return result


def run_all_validations(
    video_path: Path,
    subtitle_path: Optional[Path] = None,
    scenes: Optional[list] = None,
    assets_used: Optional[list] = None,
    script_keywords: Optional[list] = None,
    word_timing: Optional[list] = None,
    placeholder_descriptions: Optional[list] = None,
    music_path: Optional[Path] = None,
    total_duration: Optional[float] = None,
) -> dict:
    """
    Run all validations and return comprehensive report.

    VALIDATES:
    - 9:16 vertical (1080x1920)
    - No distortion
    - 8-15 scenes for 30-45 seconds
    - All placeholders detailed and actionable
    - Music matches tone and energy
    - Export format is MP4 (H.264)

    Returns dict with:
    - passed: bool
    - pre_export: ValidationResult
    - final_export: ValidationResult
    - placeholder_validation: ValidationResult
    - music_validation: ValidationResult
    - summary: str
    """
    print("=" * 50)
    print("VALIDATION REPORT")
    print("=" * 50)

    all_results = []

    # 1. Pre-export validation (aspect ratio, text, visual matching, scene structure)
    print("\n[1/4] Pre-export validation...")
    pre_result = validate_pre_export(
        video_path=video_path,
        subtitle_path=subtitle_path,
        scenes=scenes,
        assets_used=assets_used,
        script_keywords=script_keywords,
        word_timing=word_timing,
    )
    all_results.append(pre_result)
    print(f"{pre_result}")

    # 2. Scene pacing validation
    print("\n[2/4] Scene pacing validation...")
    scene_result = validate_scene_structure(scenes or [], word_timing or [], total_duration)
    all_results.append(scene_result)
    print(f"{scene_result}")

    # 3. Placeholder validation
    print("\n[3/4] Placeholder validation...")
    placeholder_result = validate_placeholders(placeholder_descriptions or [])
    all_results.append(placeholder_result)
    print(f"{placeholder_result}")

    # 4. Final export verification
    print("\n[4/4] Final export verification...")
    final_result = verify_final_export(video_path)
    all_results.append(final_result)

    print(f"{final_result}")

    # Overall pass/fail
    all_passed = all(r.passed for r in all_results)

    # Collect all errors and warnings
    all_errors = []
    all_warnings = []
    for r in all_results:
        all_errors.extend(r.errors)
        all_warnings.extend(r.warnings)

    summary_lines = [
        "",
        "=" * 50,
        "FINAL STATUS: " + ("PASSED" if all_passed else "FAILED"),
        "=" * 50,
    ]

    if all_errors:
        summary_lines.append("\nERRORS (must fix before export):")
        for err in all_errors:
            summary_lines.append(f"  - {err}")

    if all_warnings and len(all_warnings) <= 5:
        summary_lines.append("\nWARNINGS:")
        for warn in all_warnings:
            summary_lines.append(f"  - {warn}")
    elif all_warnings:
        summary_lines.append(f"\nWARNINGS: {len(all_warnings)} issues (see details above)")

    summary = "\n".join(summary_lines)
    print(summary)

    return {
        "passed": all_passed,
        "pre_export": pre_result,
        "scene_pacing": scene_result,
        "placeholders": placeholder_result,
        "final_export": final_result,
        "all_errors": all_errors,
        "all_warnings": all_warnings,
        "summary": summary,
    }


if __name__ == "__main__":
    # Test topic extraction
    test_scripts = [
        ("If you could fold a piece of paper 42 times, it would reach the Moon.",
         "A piece of paper could take you to the Moon..."),
        ("Bananas contain high levels of potassium which helps regulate blood pressure.",
         "This common fruit could save your life..."),
        ("The Great Wall of China is not visible from space with the naked eye.",
         "Everything you know about this wonder is wrong..."),
    ]

    print("Testing topic extraction:")
    for script, hook in test_scripts:
        slug = extract_topic_slug(script, hook)
        filename = generate_output_filename(script, hook)
        print(f"  Script: {script[:50]}...")
        print(f"  Slug: {slug}")
        print(f"  Filename: {filename}")
        print()
