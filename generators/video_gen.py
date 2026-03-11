"""
Multi-Scene Video Generator for Social Media Shorts

ENFORCED RULES:
1. Aspect Ratio: True 9:16 (1080x1920), no distortion
2. Text Overlay: Max 1-2 lines, 4 words per line (handled by subtitle_gen)
3. Visual Matching: Scene-by-scene keyword matching with confidence threshold
4. Fallback: Flag unmatched scenes, never use unrelated filler
5. Scene Structure: One narrative beat per scene
6. File Naming: Topic-based kebab-case with date

Supports:
- Video backgrounds (.mp4, .mov, .webm) and images (.jpg, .png)
- Multiple scenes with crossfade transitions
- ASS subtitle overlay
- Background music mixing
"""
import json
import random
import subprocess
from datetime import datetime
from pathlib import Path
from config.settings import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, VIDEO_MAX_DURATION,
    MUSIC_DIR, MUSIC_VOLUME, OUTPUT_DIR, BACKGROUNDS_DIR,
)

# Supported file extensions
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Scene transition settings - UPDATED PACING RULES
CROSSFADE_DURATION = 0.3  # seconds (shorter for more scenes)
MIN_SCENE_DURATION = 2.0  # minimum 2 seconds per scene
MAX_SCENE_DURATION = 5.0  # maximum 5 seconds (7 for sustained ideas)
AVG_SCENE_DURATION = 3.0  # target 2-4 seconds average

# Scene count rules for 30-45 second videos
MIN_SCENES = 8   # minimum scenes for proper pacing
MAX_SCENES = 15  # maximum scenes to avoid chaos
TARGET_SCENES = 10  # default target

# Aspect ratio validation
TARGET_ASPECT_RATIO = 9 / 16  # 0.5625 for vertical mobile


def _get_audio_duration(audio_path):
    """Get duration of an audio file in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(audio_path),
        ],
        capture_output=True, text=True,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def _get_video_duration(video_path):
    """Get duration of a video file in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", str(video_path),
        ],
        capture_output=True, text=True,
    )
    info = json.loads(result.stdout)
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            duration = stream.get("duration")
            if duration:
                return float(duration)
    # Fallback to format duration
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(video_path),
        ],
        capture_output=True, text=True,
    )
    info = json.loads(result.stdout)
    return float(info.get("format", {}).get("duration", 10))


def _get_random_music(content_type="motivation"):
    """
    DEPRECATED: Use get_matched_music() instead.
    Fallback random selection only when intelligent matching unavailable.
    """
    mood_dir = MUSIC_DIR / content_type
    search_dirs = [mood_dir, MUSIC_DIR] if mood_dir.exists() else [MUSIC_DIR]

    for search_dir in search_dirs:
        music_files = (
            list(search_dir.glob("*.mp3"))
            + list(search_dir.glob("*.wav"))
            + list(search_dir.glob("*.m4a"))
        )
        if search_dir == MUSIC_DIR:
            music_files = [f for f in music_files if f.parent == MUSIC_DIR]
        if music_files:
            return random.choice(music_files)

    return None


def get_matched_music(script_text: str, hook_text: str = "", content_type: str = "fact"):
    """
    Get music that matches the script's tone and energy.

    RULES:
    - Analyze script tone before choosing
    - Match emotion category
    - Energy within ±1 of script
    - Flag if no appropriate music available

    Returns:
        Tuple of (music_path, match_status_message)
    """
    try:
        from generators.music_matcher import get_music_for_content
        return get_music_for_content(script_text, hook_text, content_type)
    except Exception as e:
        print(f"  Music matching failed: {e}, using random selection")
        return _get_random_music(content_type), "Random selection (matching failed)"


def _get_backgrounds(content_type="motivation"):
    """Get list of available backgrounds (videos and images) for content type."""
    backgrounds = []

    # Try content-type specific folder first (including subdirectories)
    bg_dir = BACKGROUNDS_DIR / content_type
    if bg_dir.exists():
        for ext in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS:
            backgrounds.extend(bg_dir.rglob(f"*{ext}"))
            backgrounds.extend(bg_dir.rglob(f"*{ext.upper()}"))

    # If no content-specific backgrounds, fall back to main backgrounds folder
    if not backgrounds:
        for ext in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS:
            # Only get files directly in BACKGROUNDS_DIR (not in subdirectories)
            backgrounds.extend(BACKGROUNDS_DIR.glob(f"*{ext}"))
            backgrounds.extend(BACKGROUNDS_DIR.glob(f"*{ext.upper()}"))

    return backgrounds


def _is_video_file(path):
    """Check if a path is a video file."""
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def _select_scene_backgrounds(content_type, num_scenes, exclude=None, keywords=None,
                                scenes=None, strict_matching=True, output_dir=None):
    """
    Select unique backgrounds for each scene using intelligent matching.

    MATCHING RULES:
    - Scene-by-scene keyword analysis when scenes provided
    - Confidence threshold enforcement
    - Flag unmatched scenes instead of using random filler
    - Never insert unrelated generic visuals

    Args:
        content_type: "motivation", "fact", or "health"
        num_scenes: Number of scenes to select for
        exclude: Set of filenames to exclude (already used)
        keywords: Optional list of keywords for smart matching
        scenes: Scene list with word timing for scene-by-scene matching
        strict_matching: If True, flag low-confidence matches
        output_dir: Output directory for generated videos

    Returns:
        Tuple of (background_paths, match_results)
        - background_paths: List of Path objects (or None for unmatched)
        - match_results: List of match details per scene
    """
    # Try scene-by-scene matching first (best quality)
    if scenes and keywords:
        try:
            from generators.asset_matcher import (
                match_scene_by_scene,
                report_matching_quality,
                MIN_CONFIDENCE_THRESHOLD,
            )

            match_results = match_scene_by_scene(
                scenes=scenes,
                global_keywords=keywords,
                content_type=content_type,
                min_confidence=MIN_CONFIDENCE_THRESHOLD if strict_matching else 0.05,
            )

            # Report matching quality
            print(report_matching_quality(match_results))

            # Extract paths (None for unmatched scenes)
            paths = []
            flagged_scenes = []

            for i, result in enumerate(match_results):
                if result["matched"]:
                    paths.append(result["asset_path"])
                    if result["flagged"]:
                        flagged_scenes.append(i + 1)
                else:
                    # FALLBACK LOGIC: Don't use random filler
                    paths.append(None)
                    flagged_scenes.append(i + 1)

            if flagged_scenes:
                print(f"\n  WARNING: Scenes {flagged_scenes} need better footage")
                print("  Consider uploading relevant assets for these scenes")

            return paths, match_results

        except Exception as e:
            print(f"  Scene-by-scene matching failed: {e}")

    # Fallback: keyword-based matching (less precise)
    if keywords:
        try:
            from generators.asset_matcher import match_assets
            matched = match_assets(keywords, num_scenes, content_type)
            if matched and len(matched) >= num_scenes:
                paths = [m["path"] for m in matched[:num_scenes]]
                existing = [p for p in paths if p.exists()]
                if len(existing) >= num_scenes:
                    print(f"  Using keyword-matched assets for {num_scenes} scenes")
                    for i, m in enumerate(matched[:num_scenes]):
                        print(f"    Scene {i+1}: {m['path'].name} (score: {m['score']:.2f})")
                    # Create simplified match results
                    match_results = [
                        {"scene_idx": i, "asset_path": m["path"], "score": m["score"],
                         "matched": True, "flagged": m["score"] < 0.15}
                        for i, m in enumerate(matched[:num_scenes])
                    ]
                    return existing[:num_scenes], match_results
        except Exception as e:
            print(f"  Asset matching failed: {e}")

    # Last resort: random selection (NOT RECOMMENDED - flags all scenes)
    print("  WARNING: Using random selection - visual-script matching disabled")
    available = _get_backgrounds(content_type)
    if exclude:
        available = [bg for bg in available if bg.name not in exclude]

    if len(available) < num_scenes:
        selected = random.sample(available, min(len(available), num_scenes))
        while len(selected) < num_scenes:
            selected.append(random.choice(available))
    else:
        selected = random.sample(available, num_scenes)

    # Flag all as unmatched since we used random selection
    match_results = [
        {"scene_idx": i, "asset_path": p, "score": 0, "matched": True,
         "flagged": True, "reason": "Random selection - no keyword matching"}
        for i, p in enumerate(selected)
    ]

    return selected, match_results


def segment_into_scenes(word_timing, total_duration, target_scenes=None):
    """
    Split voiceover into scenes based on keyword shifts and sentence boundaries.

    UPDATED PACING RULES:
    - For 30-45 second videos: 8-15 scenes
    - Average scene length: 2-4 seconds
    - Longer scenes (5-7s) only for sustained ideas
    - Visual changes follow script beats or keyword shifts

    Args:
        word_timing: List of {"word": "hello", "start": 0.0, "end": 0.5}
        total_duration: Total video duration in seconds
        target_scenes: Target number of scenes (auto-calculated if None)

    Returns:
        List of {"start": 0.0, "end": 3.2, "words": [...], "keywords": [...]}
    """
    # Auto-calculate target scenes based on duration
    if target_scenes is None:
        # For 30-45 second videos: 8-15 scenes (avg 3 seconds each)
        target_scenes = max(MIN_SCENES, min(MAX_SCENES, int(total_duration / AVG_SCENE_DURATION)))

    if not word_timing:
        # Fallback: equal splits
        scene_duration = total_duration / target_scenes
        return [
            {"start": i * scene_duration, "end": (i + 1) * scene_duration,
             "words": [], "keywords": []}
            for i in range(target_scenes)
        ]

    # Find ALL break points: sentence ends, clause breaks, keyword shifts
    break_points = []

    for i, word_info in enumerate(word_timing):
        word = word_info["word"].rstrip()
        time = word_info["end"]

        # Sentence boundaries (strong breaks)
        if word.endswith(('.', '!', '?')):
            break_points.append({"idx": i, "time": time, "strength": 3, "type": "sentence"})
        # Clause breaks (medium breaks)
        elif word.endswith((',', ';', ':')):
            break_points.append({"idx": i, "time": time, "strength": 2, "type": "clause"})

    if not break_points:
        # No natural breaks - create time-based splits
        scene_duration = total_duration / target_scenes
        return [
            {"start": i * scene_duration, "end": (i + 1) * scene_duration,
             "words": [], "keywords": []}
            for i in range(target_scenes)
        ]

    # Build scenes targeting 2-4 second duration
    scenes = []
    current_start_idx = 0
    current_start_time = 0

    for bp in break_points:
        scene_duration = bp["time"] - current_start_time

        # Check if we should create a scene here
        should_split = False

        # Always split at sentence boundaries if duration >= 2s
        if bp["type"] == "sentence" and scene_duration >= MIN_SCENE_DURATION:
            should_split = True

        # Split at clause if duration >= 3s (good average)
        if bp["type"] == "clause" and scene_duration >= AVG_SCENE_DURATION:
            should_split = True

        # Force split if duration exceeds max
        if scene_duration >= MAX_SCENE_DURATION:
            should_split = True

        if should_split:
            # Extract keywords from this scene's words
            scene_words = word_timing[current_start_idx:bp["idx"] + 1]
            keywords = _extract_scene_keywords(scene_words)

            scenes.append({
                "start": current_start_time,
                "end": bp["time"],
                "words": scene_words,
                "keywords": keywords,
                "break_type": bp["type"],
            })

            current_start_idx = bp["idx"] + 1
            current_start_time = bp["time"]

    # Handle remaining words
    if current_start_idx < len(word_timing):
        scene_words = word_timing[current_start_idx:]
        keywords = _extract_scene_keywords(scene_words)
        scenes.append({
            "start": current_start_time,
            "end": total_duration,
            "words": scene_words,
            "keywords": keywords,
            "break_type": "end",
        })

    # Ensure we cover full duration
    if scenes:
        scenes[0]["start"] = 0
        scenes[-1]["end"] = total_duration

    # Validate scene count and adjust if needed
    if len(scenes) < MIN_SCENES:
        scenes = _subdivide_scenes(scenes, word_timing, total_duration, MIN_SCENES)
    elif len(scenes) > MAX_SCENES:
        scenes = _merge_short_scenes(scenes, MAX_SCENES)

    return scenes


def _extract_scene_keywords(scene_words):
    """Extract key nouns and verbs from scene words for matching."""
    import re

    STOP_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'to', 'of', 'in', 'for', 'on',
        'with', 'at', 'by', 'from', 'up', 'about', 'into', 'through',
        'and', 'but', 'or', 'so', 'yet', 'this', 'that', 'these', 'those',
        'it', 'its', 'you', 'your', 'we', 'our', 'they', 'their', 'them',
    }

    keywords = []
    for word_info in scene_words:
        word = word_info.get("word", "")
        clean = re.sub(r'[^\w]', '', word.lower())

        if len(clean) >= 3 and clean not in STOP_WORDS:
            keywords.append(clean)

    return keywords


def _subdivide_scenes(scenes, word_timing, total_duration, min_count):
    """Subdivide long scenes to meet minimum scene count."""
    while len(scenes) < min_count:
        # Find longest scene
        longest_idx = max(range(len(scenes)),
                         key=lambda i: scenes[i]["end"] - scenes[i]["start"])
        longest = scenes[longest_idx]

        duration = longest["end"] - longest["start"]
        if duration < MIN_SCENE_DURATION * 2:
            break  # Can't subdivide further

        # Split in half
        mid_time = longest["start"] + duration / 2
        mid_words = []
        split_idx = 0

        for i, w in enumerate(longest["words"]):
            if w["end"] >= mid_time:
                split_idx = i
                break

        first_half = {
            "start": longest["start"],
            "end": mid_time,
            "words": longest["words"][:split_idx],
            "keywords": _extract_scene_keywords(longest["words"][:split_idx]),
            "break_type": "subdivided",
        }
        second_half = {
            "start": mid_time,
            "end": longest["end"],
            "words": longest["words"][split_idx:],
            "keywords": _extract_scene_keywords(longest["words"][split_idx:]),
            "break_type": longest.get("break_type", "subdivided"),
        }

        scenes = scenes[:longest_idx] + [first_half, second_half] + scenes[longest_idx + 1:]

    return scenes


def _merge_short_scenes(scenes, max_count):
    """Merge shortest adjacent scenes to meet maximum scene count."""
    while len(scenes) > max_count:
        # Find shortest scene
        shortest_idx = min(range(len(scenes)),
                          key=lambda i: scenes[i]["end"] - scenes[i]["start"])

        # Merge with adjacent (prefer shorter neighbor)
        if shortest_idx == 0:
            merge_with = 1
        elif shortest_idx == len(scenes) - 1:
            merge_with = shortest_idx - 1
        else:
            # Merge with shorter neighbor
            prev_dur = scenes[shortest_idx - 1]["end"] - scenes[shortest_idx - 1]["start"]
            next_dur = scenes[shortest_idx + 1]["end"] - scenes[shortest_idx + 1]["start"]
            merge_with = shortest_idx - 1 if prev_dur < next_dur else shortest_idx + 1

        # Merge scenes
        if merge_with < shortest_idx:
            first, second = merge_with, shortest_idx
        else:
            first, second = shortest_idx, merge_with

        merged = {
            "start": scenes[first]["start"],
            "end": scenes[second]["end"],
            "words": scenes[first]["words"] + scenes[second]["words"],
            "keywords": scenes[first]["keywords"] + scenes[second]["keywords"],
            "break_type": scenes[second].get("break_type", "merged"),
        }

        scenes = scenes[:first] + [merged] + scenes[second + 1:]

    return scenes


def _resegment_scenes(word_timing, sentence_ends, total_duration, target_scenes):
    """
    Fallback segmentation when initial approach gives too few scenes.
    Uses target_scenes as the guide.
    """
    target_interval = len(word_timing) / target_scenes
    scene_boundaries = [0]

    for target_pos in range(1, target_scenes):
        target_word_idx = int(target_pos * target_interval)
        # Find nearest sentence end
        candidates = [e for e in sentence_ends if e > scene_boundaries[-1]]
        if candidates:
            best_end = min(candidates, key=lambda x: abs(x - target_word_idx))
            scene_boundaries.append(best_end)

    scenes = []
    for i in range(len(scene_boundaries)):
        start_idx = scene_boundaries[i]
        end_idx = scene_boundaries[i + 1] if i + 1 < len(scene_boundaries) else len(word_timing) - 1

        start_time = word_timing[start_idx]["start"] if start_idx < len(word_timing) else 0
        end_time = word_timing[end_idx]["end"] if end_idx < len(word_timing) else total_duration

        # Count sentences in this scene
        sentence_count = sum(1 for j in range(start_idx, end_idx + 1)
                            if word_timing[j]["word"].rstrip().endswith(('.', '!', '?')))

        scenes.append({
            "start": start_time,
            "end": end_time,
            "words": word_timing[start_idx:end_idx + 1],
            "sentence_count": sentence_count,
        })

    if scenes:
        scenes[0]["start"] = 0
        scenes[-1]["end"] = total_duration

    return scenes


def _get_media_dimensions(media_path):
    """Get width and height of a video or image file."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(media_path)],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        parts = result.stdout.strip().split(",")
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1])
    return None, None


def _is_vertical_media(media_path):
    """Check if media is already vertical (height > width)."""
    width, height = _get_media_dimensions(media_path)
    if width and height:
        return height > width
    return False


def _build_scene_filter(bg_path, scene_start, scene_duration, scene_idx, total_scenes,
                        use_blur_padding=False):
    """
    Build FFmpeg filter for a single scene.

    RULES ENFORCED:
    - Never stretch or distort media
    - Preserve original aspect ratio
    - Either crop to fit OR use blur padding
    - Output must be exactly 1080x1920 (9:16)

    Args:
        bg_path: Path to background (video or image)
        scene_start: Start time in seconds
        scene_duration: Duration in seconds
        scene_idx: Scene index (0-based)
        total_scenes: Total number of scenes
        use_blur_padding: If True, add blurred background instead of cropping

    Returns:
        Filter string component
    """
    is_video = _is_video_file(bg_path)
    is_vertical = _is_vertical_media(bg_path)

    if use_blur_padding and not is_vertical:
        # BLUR PADDING: Scale to fit width, add blurred background for height
        if is_video:
            return (
                # Create blurred background
                f"split[bg][fg];"
                f"[bg]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},gblur=sigma=50[blurred];"
                # Scale foreground to fit
                f"[fg]scale={VIDEO_WIDTH}:-1:force_original_aspect_ratio=decrease[scaled];"
                # Overlay centered
                f"[blurred][scaled]overlay=(W-w)/2:(H-h)/2,"
                f"setsar=1:1,fps={VIDEO_FPS}"
            )
        else:
            frames = int(scene_duration * VIDEO_FPS)
            return (
                f"split[bg][fg];"
                f"[bg]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},gblur=sigma=50[blurred];"
                f"[fg]scale={VIDEO_WIDTH}:-1:force_original_aspect_ratio=decrease[scaled];"
                f"[blurred][scaled]overlay=(W-w)/2:(H-h)/2,"
                f"zoompan=z='min(zoom+0.0005,1.1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS},"
                f"setsar=1:1"
            )

    # DEFAULT: Crop to fill (no distortion)
    if is_video:
        # For video: scale to cover, then crop center
        # This preserves aspect ratio - no stretching
        return (
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"setsar=1:1,"
            f"fps={VIDEO_FPS}"
        )
    else:
        # For image: zoompan effect with crop
        zoom_directions = [
            # Zoom in center
            f"zoompan=z='min(zoom+0.0008,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            # Pan left to right
            f"zoompan=z='1.1':x='if(eq(on,1),0,x+1)':y='ih/2-(ih/zoom/2)'",
            # Pan right to left
            f"zoompan=z='1.1':x='if(eq(on,1),iw*0.1,x-1)':y='ih/2-(ih/zoom/2)'",
            # Zoom out
            f"zoompan=z='if(eq(on,1),1.3,max(zoom-0.0008,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        ]
        zoom_effect = zoom_directions[scene_idx % len(zoom_directions)]
        frames = int(scene_duration * VIDEO_FPS)

        # Scale up first to allow zoompan room, then output at exact size
        return (
            f"scale={VIDEO_WIDTH * 2}:{VIDEO_HEIGHT * 2}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH * 2}:{VIDEO_HEIGHT * 2},"
            f"{zoom_effect}:d={frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS},"
            f"setsar=1:1"
        )


def assemble_video(voice_path, output_path=None, music_path=None, content_type="motivation",
                   word_timing=None, keywords=None, subtitle_path=None, scenes=None,
                   script_text=None, hook_text=None, validate=True, strict_matching=True):
    """
    Assemble final video with multiple scenes, transitions, and subtitles.

    ENFORCED RULES:
    - 9:16 aspect ratio (1080x1920) with validation
    - Scene-by-scene visual matching with confidence threshold
    - Intelligent topic-based file naming
    - Pre-export validation

    Args:
        voice_path: Path to voiceover audio
        output_path: Path to save final video (auto-generated if None)
        music_path: Path to background music (optional, auto-selected if None)
        content_type: "motivation" or "fact"
        word_timing: List of word timing dicts for scene segmentation
        keywords: List of keywords for subtitle highlighting and asset matching
        subtitle_path: Path to ASS subtitle file (optional)
        scenes: Pre-computed scene list (optional)
        script_text: Full script text for intelligent file naming
        hook_text: Hook text for file naming (higher priority)
        validate: Run pre-export validation (default: True)
        strict_matching: Enforce confidence threshold for visuals (default: True)

    Returns:
        Dict with keys:
            - video_path: Path to the generated video
            - backgrounds_used: List of background file paths
            - music_file: Path to music file used (or None)
            - scenes: Scene timing data
            - total_duration: Video duration in seconds
            - match_results: Visual matching results per scene
            - validation: Validation results
            - flagged_scenes: List of scenes needing better footage
    """
    # Generate intelligent output path if not provided
    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        if script_text:
            # Use intelligent naming based on script content
            from generators.video_validator import generate_output_filename
            filename = generate_output_filename(script_text, hook_text, content_type)
            output_path = OUTPUT_DIR / filename
        else:
            # Fallback to timestamp-based naming
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = OUTPUT_DIR / f"{content_type}_{timestamp}.mp4"

    # Get voiceover duration
    voice_duration = _get_audio_duration(voice_path)
    # Add padding (1s intro + 3s outro for fade out)
    INTRO_PADDING = 1.0
    OUTRO_PADDING = 3.0
    total_duration = min(voice_duration + INTRO_PADDING + OUTRO_PADDING, VIDEO_MAX_DURATION)

    # Get background music using intelligent matching
    music_match_status = None
    if music_path is None:
        if script_text:
            music_path, music_match_status = get_matched_music(script_text, hook_text or "", content_type)
        else:
            music_path = _get_random_music(content_type)
            music_match_status = "Random selection (no script provided)"

    if music_path is None:
        print(f"  WARNING: No music available - {music_match_status}")

    # Calculate scenes if not provided
    if scenes is None:
        scenes = segment_into_scenes(word_timing or [], total_duration, TARGET_SCENES)

    num_scenes = len(scenes)

    # Select backgrounds using intelligent scene-by-scene matching
    backgrounds, match_results = _select_scene_backgrounds(
        content_type=content_type,
        num_scenes=num_scenes,
        keywords=keywords,
        scenes=scenes,
        strict_matching=strict_matching,
        output_dir=output_path.parent if output_path else OUTPUT_DIR,
    )

    # Identify flagged scenes (unmatched or low confidence)
    flagged_scenes = [i + 1 for i, r in enumerate(match_results) if r.get("flagged", False)]

    # Import placeholder generator
    from generators.placeholder_gen import (
        generate_placeholder_video,
        describe_scene_visual,
        PlaceholderReport,
    )

    # Track placeholders for report
    placeholder_report = PlaceholderReport()

    # Handle None backgrounds (unmatched scenes) with PLACEHOLDERS
    # RULE: Never use random/unrelated visuals - use placeholders instead
    for i, bg in enumerate(backgrounds):
        scene = scenes[i]
        scene_duration = scene["end"] - scene["start"]

        if bg is None or match_results[i].get("score", 0) < 0.10:
            # Generate placeholder instead of using random footage
            scene_words = scene.get("words", [])
            visual_desc = describe_scene_visual(scene_words, script_text or "")

            # Create placeholder video
            placeholder_path = Path(output_path).parent / f"placeholder_scene_{i+1}.mp4"
            generate_placeholder_video(
                duration=scene_duration,
                description=visual_desc,
                output_path=placeholder_path,
                scene_number=i + 1,
            )

            backgrounds[i] = placeholder_path
            placeholder_report.add(i + 1, scene_duration, visual_desc, placeholder_path)
            print(f"  Scene {i+1}: Generated placeholder ({scene_duration:.1f}s) - {visual_desc}")

    # Save placeholder report if any were generated
    if placeholder_report.has_placeholders():
        report_path = placeholder_report.save_report(Path(output_path).parent)
        print(f"\n  PLACEHOLDERS NEEDED: See {report_path}")

    print(f"\nAssembling video ({total_duration:.1f}s) with {num_scenes} scenes...")
    if flagged_scenes:
        print(f"  NOTE: Scenes {flagged_scenes} have low visual-script relevance")

    # =====================================================================
    # USE ROBUST SEGMENTED ASSEMBLY (video_assembler.py)
    # This guarantees each scene renders as a distinct segment
    # =====================================================================
    try:
        from generators.video_assembler import assemble_video_segmented

        assembly_result = assemble_video_segmented(
            scenes=scenes,
            backgrounds=backgrounds,
            voice_path=Path(voice_path),
            output_path=Path(output_path),
            subtitle_path=Path(subtitle_path) if subtitle_path else None,
            music_path=Path(music_path) if music_path else None,
            total_duration=total_duration,
            keywords=keywords,
        )

        print(f"\nVideo saved: {output_path}")
        print(f"  Segments rendered: {assembly_result['segments_rendered']}/{assembly_result['segments_total']}")

    except Exception as e:
        print(f"\nSegmented assembly failed: {e}")
        print("Falling back to simple assembly...")
        return _assemble_video_simple(voice_path, output_path, music_path, content_type,
                                       subtitle_path, total_duration, backgrounds[0], scenes)

    # Run comprehensive validation
    validation_result = None
    final_verification = None

    if validate:
        print("\n" + "=" * 50)
        print("RUNNING VALIDATIONS")
        print("=" * 50)

        try:
            from generators.video_validator import run_all_validations

            # Collect placeholder descriptions for validation
            placeholder_descriptions = []
            for p in placeholder_report.placeholders:
                placeholder_descriptions.append(p["description"])

            validation_report = run_all_validations(
                video_path=output_path,
                subtitle_path=subtitle_path,
                scenes=scenes,
                assets_used=backgrounds,
                script_keywords=keywords,
                word_timing=word_timing,
                placeholder_descriptions=placeholder_descriptions,
                music_path=music_path,
                total_duration=total_duration,
            )

            validation_result = validation_report["pre_export"]
            final_verification = validation_report["final_export"]

            if not validation_report["passed"]:
                print("\n  WARNING: Video has validation issues that need fixing")
        except Exception as e:
            print(f"  Validation error: {e}")

    return {
        "video_path": output_path,
        "backgrounds_used": [str(bg) for bg in backgrounds],
        "music_file": str(music_path) if music_path else None,
        "scenes": scenes,
        "total_duration": total_duration,
        "match_results": match_results,
        "validation": validation_result,
        "final_verification": final_verification,
        "flagged_scenes": flagged_scenes,
        "placeholders_used": placeholder_report.has_placeholders(),
        "placeholder_report": placeholder_report.to_markdown() if placeholder_report.has_placeholders() else None,
    }


def _assemble_video_simple(voice_path, output_path, music_path, content_type,
                           subtitle_path, total_duration, background, scenes=None):
    """
    Fallback: Simple single-scene video assembly.
    Used when complex multi-scene fails.
    """
    print("Falling back to simple single-scene assembly...")

    is_video = _is_video_file(background)

    if is_video:
        input_args = ["-i", str(background)]
        video_filter = (
            f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1,fps={VIDEO_FPS}[v]"
        )
    else:
        input_args = ["-loop", "1", "-i", str(background)]
        video_filter = (
            f"[0:v]scale={VIDEO_WIDTH * 2}:{VIDEO_HEIGHT * 2},"
            f"zoompan=z='min(zoom+0.0005,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={int(total_duration * VIDEO_FPS)}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS}[v]"
        )

    # Add subtitle overlay
    if subtitle_path and Path(subtitle_path).exists():
        sub_path_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
        video_filter += f";[v]ass='{sub_path_escaped}'[vfinal]"
    else:
        video_filter += ";[v]copy[vfinal]"

    # Audio setup with fade out
    audio_filter = "[1:a]adelay=1000|1000[voice]"
    if music_path:
        music_fade_start = total_duration - 2.5
        audio_filter += (
            f";[2:a]atrim=0:{total_duration},afade=t=in:d=1.5,afade=t=out:st={music_fade_start}:d=2.5,volume={MUSIC_VOLUME}[music]"
            f";[voice][music]amix=inputs=2:duration=longest:dropout_transition=2,afade=t=out:st={total_duration-2}:d=2[afinal]"
        )
        audio_inputs = ["-i", str(voice_path), "-i", str(music_path)]
    else:
        audio_filter += f";[voice]afade=t=out:st={total_duration-2}:d=2[afinal]"
        audio_inputs = ["-i", str(voice_path)]

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        *audio_inputs,
        "-filter_complex", video_filter + ";" + audio_filter,
        "-map", "[vfinal]",
        "-map", "[afinal]",
        "-t", str(total_duration),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Video assembly failed: {result.stderr[-500:]}")

    print(f"Video saved (simple mode): {output_path}")

    # Build scenes if not provided (single scene covering full duration)
    if scenes is None:
        scenes = [{"start": 0, "end": total_duration, "words": []}]

    return {
        "video_path": output_path,
        "backgrounds_used": [str(background)],
        "music_file": str(music_path) if music_path else None,
        "scenes": scenes,
        "total_duration": total_duration,
    }


# Legacy function signature for backward compatibility
def assemble_video_legacy(image_path, voice_path, output_path=None, music_path=None, content_type="motivation"):
    """
    Legacy video assembly (single image, no subtitles).
    Kept for backward compatibility.
    """
    return assemble_video(
        voice_path=voice_path,
        output_path=output_path,
        music_path=music_path,
        content_type=content_type,
    )


if __name__ == "__main__":
    # Test requires audio file to exist
    test_voice = OUTPUT_DIR / "voiceover.mp3"

    if test_voice.exists():
        # Test word timing
        test_timing = [
            {"word": "We", "start": 0.0, "end": 0.3},
            {"word": "suffer", "start": 0.3, "end": 0.8},
            {"word": "more.", "start": 0.8, "end": 1.2},
            {"word": "Test", "start": 1.5, "end": 1.8},
            {"word": "sentence.", "start": 1.8, "end": 2.5},
        ]

        path = assemble_video(
            test_voice,
            word_timing=test_timing,
            keywords=["suffer", "sentence"],
            content_type="motivation",
        )
        print(f"Assembled video: {path}")
    else:
        print("Run voice_gen.py first to create test audio.")
