"""
Multi-Scene Video Generator for Social Media Shorts

Supports:
- Video backgrounds (.mp4, .mov, .webm) and images (.jpg, .png)
- Multiple scenes with crossfade transitions
- ASS subtitle overlay
- Background music mixing
"""
import json
import random
import subprocess
from pathlib import Path
from config.settings import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, VIDEO_MAX_DURATION,
    MUSIC_DIR, MUSIC_VOLUME, OUTPUT_DIR, BACKGROUNDS_DIR,
)

# Supported file extensions
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Scene transition settings
CROSSFADE_DURATION = 0.5  # seconds
MIN_SCENE_DURATION = 6.0  # minimum seconds per scene
TARGET_SCENES = 4  # target number of scenes per video


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
    """Get a random background music track matched to content mood."""
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


def _select_scene_backgrounds(content_type, num_scenes, exclude=None, keywords=None):
    """
    Select unique backgrounds for each scene.

    Args:
        content_type: "motivation", "fact", or "health"
        num_scenes: Number of scenes to select for
        exclude: Set of filenames to exclude (already used)
        keywords: Optional list of keywords for smart matching

    Returns:
        List of background paths
    """
    # Try keyword-based matching first (for health/nutrition content)
    if keywords:
        try:
            from generators.asset_matcher import match_assets
            matched = match_assets(keywords, num_scenes, content_type)
            if matched and len(matched) >= num_scenes:
                paths = [m["path"] for m in matched[:num_scenes]]
                # Verify files exist
                existing = [p for p in paths if p.exists()]
                if len(existing) >= num_scenes:
                    print(f"  Using keyword-matched assets for {num_scenes} scenes")
                    for i, m in enumerate(matched[:num_scenes]):
                        print(f"    Scene {i+1}: {m['path'].name} (score: {m['score']:.2f})")
                    return existing[:num_scenes]
        except Exception as e:
            print(f"  Asset matching failed, using random: {e}")

    # Fallback to random selection (existing behavior)
    available = _get_backgrounds(content_type)
    if exclude:
        available = [bg for bg in available if bg.name not in exclude]

    if len(available) < num_scenes:
        # If not enough unique backgrounds, allow some repeats
        selected = random.sample(available, min(len(available), num_scenes))
        while len(selected) < num_scenes:
            selected.append(random.choice(available))
        return selected

    return random.sample(available, num_scenes)


def segment_into_scenes(word_timing, total_duration, target_scenes=TARGET_SCENES):
    """
    Split voiceover into scenes based on sentence boundaries.

    Args:
        word_timing: List of {"word": "hello", "start": 0.0, "end": 0.5}
        total_duration: Total video duration in seconds
        target_scenes: Target number of scenes

    Returns:
        List of {"start": 0.0, "end": 8.5, "words": [...]}
    """
    if not word_timing:
        # Fallback: equal splits
        scene_duration = total_duration / target_scenes
        return [
            {"start": i * scene_duration, "end": (i + 1) * scene_duration, "words": []}
            for i in range(target_scenes)
        ]

    # Find sentence boundaries (words ending with .!?)
    sentence_ends = []
    for i, word_info in enumerate(word_timing):
        word = word_info["word"].rstrip()
        if word.endswith(('.', '!', '?')):
            sentence_ends.append(i)

    if not sentence_ends:
        # No sentence boundaries found, split evenly
        scene_duration = total_duration / target_scenes
        return [
            {"start": i * scene_duration, "end": (i + 1) * scene_duration, "words": []}
            for i in range(target_scenes)
        ]

    # Select scene boundaries from sentence ends
    # Aim for roughly equal distribution
    target_interval = len(word_timing) / target_scenes
    scene_boundaries = [0]  # Start at beginning

    for target_pos in range(1, target_scenes):
        target_word_idx = int(target_pos * target_interval)
        # Find nearest sentence end
        best_end = min(sentence_ends, key=lambda x: abs(x - target_word_idx))
        if best_end > scene_boundaries[-1] and best_end not in scene_boundaries:
            scene_boundaries.append(best_end)

    # Create scenes
    scenes = []
    for i in range(len(scene_boundaries)):
        start_idx = scene_boundaries[i]
        end_idx = scene_boundaries[i + 1] if i + 1 < len(scene_boundaries) else len(word_timing) - 1

        start_time = word_timing[start_idx]["start"] if start_idx < len(word_timing) else 0
        end_time = word_timing[end_idx]["end"] if end_idx < len(word_timing) else total_duration

        scenes.append({
            "start": start_time,
            "end": end_time,
            "words": word_timing[start_idx:end_idx + 1],
        })

    # Ensure we cover full duration
    if scenes:
        scenes[0]["start"] = 0
        scenes[-1]["end"] = total_duration

    return scenes


def _build_scene_filter(bg_path, scene_start, scene_duration, scene_idx, total_scenes):
    """
    Build FFmpeg filter for a single scene.

    Args:
        bg_path: Path to background (video or image)
        scene_start: Start time in seconds
        scene_duration: Duration in seconds
        scene_idx: Scene index (0-based)
        total_scenes: Total number of scenes

    Returns:
        Filter string component
    """
    is_video = _is_video_file(bg_path)

    if is_video:
        # For video: trim, scale, and pad to exact duration
        # Loop if clip is shorter than scene
        return (
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"setsar=1,"
            f"fps={VIDEO_FPS}"
        )
    else:
        # For image: zoompan effect with varied directions
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
        return (
            f"scale={VIDEO_WIDTH * 2}:{VIDEO_HEIGHT * 2},"
            f"{zoom_effect}:d={frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS}"
        )


def assemble_video(voice_path, output_path=None, music_path=None, content_type="motivation",
                   word_timing=None, keywords=None, subtitle_path=None, scenes=None):
    """
    Assemble final video with multiple scenes, transitions, and subtitles.

    Args:
        voice_path: Path to voiceover audio
        output_path: Path to save final video
        music_path: Path to background music (optional, auto-selected if None)
        content_type: "motivation" or "fact"
        word_timing: List of word timing dicts for scene segmentation
        keywords: List of keywords for subtitle highlighting
        subtitle_path: Path to ASS subtitle file (optional)
        scenes: Pre-computed scene list (optional)

    Returns:
        Dict with keys:
            - video_path: Path to the generated video
            - backgrounds_used: List of background file paths
            - music_file: Path to music file used (or None)
            - scenes: Scene timing data
            - total_duration: Video duration in seconds
    """
    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / "final_video.mp4"

    # Get voiceover duration
    voice_duration = _get_audio_duration(voice_path)
    # Add padding (1s intro + 1s outro)
    total_duration = min(voice_duration + 2, VIDEO_MAX_DURATION)

    # Get background music
    if music_path is None:
        music_path = _get_random_music(content_type)

    # Calculate scenes if not provided
    if scenes is None:
        scenes = segment_into_scenes(word_timing or [], total_duration, TARGET_SCENES)

    num_scenes = len(scenes)

    # Select backgrounds for each scene (use keyword matching if available)
    backgrounds = _select_scene_backgrounds(content_type, num_scenes, keywords=keywords)

    print(f"Assembling video ({total_duration:.1f}s) with {num_scenes} scenes...")

    # Build FFmpeg command for multi-scene video
    # Strategy: Create each scene separately, then crossfade them together

    input_args = []
    filter_parts = []

    # Add inputs for each background
    for i, (scene, bg_path) in enumerate(zip(scenes, backgrounds)):
        scene_duration = scene["end"] - scene["start"] + CROSSFADE_DURATION
        is_video = _is_video_file(bg_path)

        if is_video:
            # Video input: use stream_loop for looping if needed
            bg_duration = _get_video_duration(bg_path)
            if bg_duration < scene_duration:
                loop_count = int(scene_duration / bg_duration) + 1
                input_args.extend(["-stream_loop", str(loop_count)])
            input_args.extend(["-i", str(bg_path)])
        else:
            # Image input: loop as video
            input_args.extend(["-loop", "1", "-t", str(scene_duration), "-i", str(bg_path)])

    # Add audio inputs
    voice_input_idx = num_scenes
    input_args.extend(["-i", str(voice_path)])

    music_input_idx = None
    if music_path:
        music_input_idx = num_scenes + 1
        input_args.extend(["-i", str(music_path)])

    # Build video filter chain
    scene_outputs = []
    for i, (scene, bg_path) in enumerate(zip(scenes, backgrounds)):
        scene_duration = scene["end"] - scene["start"] + CROSSFADE_DURATION
        scene_filter = _build_scene_filter(bg_path, scene["start"], scene_duration, i, num_scenes)

        # Trim to exact duration
        is_video = _is_video_file(bg_path)
        if is_video:
            filter_parts.append(
                f"[{i}:v]trim=0:{scene_duration},setpts=PTS-STARTPTS,{scene_filter}[v{i}]"
            )
        else:
            filter_parts.append(f"[{i}:v]{scene_filter}[v{i}]")

        scene_outputs.append(f"[v{i}]")

    # Apply crossfade transitions between scenes
    if len(scene_outputs) > 1:
        # Chain crossfades
        current = scene_outputs[0]
        for i in range(1, len(scene_outputs)):
            offset = scenes[i]["start"] - CROSSFADE_DURATION
            offset = max(0, offset)  # Ensure non-negative
            next_output = f"[xfade{i}]" if i < len(scene_outputs) - 1 else "[vbase]"
            filter_parts.append(
                f"{current}{scene_outputs[i]}xfade=transition=fade:duration={CROSSFADE_DURATION}:offset={offset}{next_output}"
            )
            current = next_output
    else:
        filter_parts.append(f"{scene_outputs[0]}copy[vbase]")

    # Add subtitles if provided
    if subtitle_path and Path(subtitle_path).exists():
        # Escape special characters in path for FFmpeg
        sub_path_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
        filter_parts.append(f"[vbase]ass='{sub_path_escaped}'[vfinal]")
    else:
        filter_parts.append("[vbase]copy[vfinal]")

    # Build audio filter
    # Delay voiceover by 1 second (intro padding)
    audio_filters = [f"[{voice_input_idx}:a]adelay=1000|1000[voice]"]

    if music_input_idx is not None:
        audio_filters.append(
            f"[{music_input_idx}:a]atrim=0:{total_duration},afade=t=in:d=1,afade=t=out:st={total_duration-1}:d=1,volume={MUSIC_VOLUME}[music]"
        )
        audio_filters.append("[voice][music]amix=inputs=2:duration=first:dropout_transition=2[afinal]")
    else:
        audio_filters.append("[voice]acopy[afinal]")

    # Combine all filters
    filter_complex = ";".join(filter_parts + audio_filters)

    # Build full command
    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_complex,
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

    print(f"Running FFmpeg with {num_scenes} scenes...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr[-1000:]}")
        # Try simpler fallback
        return _assemble_video_simple(voice_path, output_path, music_path, content_type,
                                       subtitle_path, total_duration, backgrounds[0], scenes)

    print(f"Video saved: {output_path}")
    return {
        "video_path": output_path,
        "backgrounds_used": [str(bg) for bg in backgrounds],
        "music_file": str(music_path) if music_path else None,
        "scenes": scenes,
        "total_duration": total_duration,
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

    # Audio setup
    audio_filter = "[1:a]adelay=1000|1000[voice]"
    if music_path:
        audio_filter += (
            f";[2:a]atrim=0:{total_duration},volume={MUSIC_VOLUME}[music]"
            ";[voice][music]amix=inputs=2:duration=first:dropout_transition=2[afinal]"
        )
        audio_inputs = ["-i", str(voice_path), "-i", str(music_path)]
    else:
        audio_filter += ";[voice]acopy[afinal]"
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
