"""
Video Assembler - Robust multi-scene video assembly with proper segmentation.

This module ensures:
1. Each scene renders as a distinct video segment
2. Each segment uses its assigned visual (matched asset or placeholder)
3. Segments are concatenated in order
4. Full logging of scene-to-asset mapping
5. Placeholders are real video clips burned into the timeline
"""
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config.settings import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, MUSIC_VOLUME,
    COLOR_GRADING_ENABLED, VISUAL_STYLE,
)


@dataclass
class SceneSegment:
    """A single scene segment for video assembly."""
    scene_idx: int
    start_time: float
    end_time: float
    duration: float
    source_path: Path
    source_type: str  # "video", "image", "placeholder"
    is_placeholder: bool = False
    keywords: list = field(default_factory=list)


@dataclass
class AssemblyLog:
    """Log of the assembly process for debugging."""
    segments: list = field(default_factory=list)
    ffmpeg_commands: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def add_segment(self, seg: SceneSegment):
        self.segments.append({
            "scene": seg.scene_idx + 1,
            "start": seg.start_time,
            "end": seg.end_time,
            "duration": seg.duration,
            "source": str(seg.source_path.name),
            "type": seg.source_type,
            "is_placeholder": seg.is_placeholder,
        })

    def print_mapping(self):
        """Print the scene-to-asset mapping."""
        print("\n" + "=" * 60)
        print("SCENE SEGMENTATION MAPPING")
        print("=" * 60)
        print(f"{'Scene':<8} {'Duration':<10} {'Type':<12} {'Source'}")
        print("-" * 60)
        for seg in self.segments:
            marker = "[PLACEHOLDER]" if seg["is_placeholder"] else ""
            print(f"{seg['scene']:<8} {seg['duration']:.1f}s{'':<5} {seg['type']:<12} {seg['source'][:35]} {marker}")
        print("=" * 60 + "\n")

    def save_log(self, output_path: Path):
        """Save assembly log to file."""
        log_path = output_path.parent / "assembly_log.json"
        with open(log_path, "w") as f:
            json.dump({
                "segments": self.segments,
                "commands": self.ffmpeg_commands,
                "errors": self.errors,
                "warnings": self.warnings,
            }, f, indent=2)
        return log_path


def _get_media_duration(media_path: Path) -> float:
    """Get duration of video file."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(media_path)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        info = json.loads(result.stdout)
        return float(info.get("format", {}).get("duration", 5.0))
    return 5.0


def _is_video_file(path: Path) -> bool:
    """Check if file is a video."""
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
    return path.suffix.lower() in VIDEO_EXTENSIONS


# Zack D Films style color grading filter
def get_color_grading_filter() -> str:
    """
    Get FFmpeg color grading filter for Zack D Films style.

    Returns filter string with:
    - Saturation boost (1.3x) for vibrant mobile colors
    - Contrast boost (1.1x) for punchier visuals
    - Warm color balance
    - Sharpening for mobile clarity
    """
    if not COLOR_GRADING_ENABLED:
        return ""

    # Saturation and contrast
    eq_filter = "eq=saturation=1.3:contrast=1.1"

    # Warm color balance (slight red/yellow push)
    colorbalance = "colorbalance=rs=0.05:gs=0:bs=-0.03:rm=0.03:gm=0:bm=-0.02"

    # Sharpening for mobile screens (unsharp mask)
    sharpen = "unsharp=5:5:0.8:5:5:0.0"

    return f"{eq_filter},{colorbalance},{sharpen}"


# Enhanced camera movements for image-based scenes
CAMERA_MOVEMENTS = {
    "push_in_fast": {
        "description": "Fast push-in for hooks and dramatic moments",
        "zoom_start": 1.0,
        "zoom_end": 1.3,
        "x_drift": 0,
        "y_drift": 0,
    },
    "slow_zoom": {
        "description": "Slow zoom for reveals",
        "zoom_start": 1.0,
        "zoom_end": 1.15,
        "x_drift": 0,
        "y_drift": 0,
    },
    "parallax_left": {
        "description": "Parallax drift to the left",
        "zoom_start": 1.15,
        "zoom_end": 1.15,
        "x_drift": -100,  # pixels to drift
        "y_drift": 0,
    },
    "parallax_right": {
        "description": "Parallax drift to the right",
        "zoom_start": 1.15,
        "zoom_end": 1.15,
        "x_drift": 100,
        "y_drift": 0,
    },
    "pull_back": {
        "description": "Pull back for endings",
        "zoom_start": 1.2,
        "zoom_end": 1.0,
        "x_drift": 0,
        "y_drift": 0,
    },
    "crane_up": {
        "description": "Crane up movement",
        "zoom_start": 1.1,
        "zoom_end": 1.15,
        "x_drift": 0,
        "y_drift": -50,
    },
    "ken_burns": {
        "description": "Classic Ken Burns zoom",
        "zoom_start": 1.0,
        "zoom_end": 1.2,
        "x_drift": 30,
        "y_drift": -20,
    },
}


def get_camera_for_scene(scene_idx: int, total_scenes: int, is_hook: bool = False) -> str:
    """
    Select appropriate camera movement based on scene position.

    Args:
        scene_idx: Current scene index (0-indexed)
        total_scenes: Total number of scenes
        is_hook: Whether this is the hook/opening

    Returns:
        Camera movement key from CAMERA_MOVEMENTS
    """
    if is_hook or scene_idx == 0:
        return "push_in_fast"
    elif scene_idx == total_scenes - 1:
        return "pull_back"
    elif scene_idx == 1:
        return "slow_zoom"
    else:
        # Alternate between parallax directions and other movements
        movements = ["parallax_left", "parallax_right", "slow_zoom", "ken_burns", "crane_up"]
        return movements[scene_idx % len(movements)]


def get_zoompan_filter(
    scene_idx: int,
    total_scenes: int,
    frames: int,
    output_width: int = VIDEO_WIDTH,
    output_height: int = VIDEO_HEIGHT,
) -> str:
    """
    Generate FFmpeg zoompan filter with enhanced camera movement.

    Args:
        scene_idx: Current scene index
        total_scenes: Total scenes in video
        frames: Number of frames for this scene
        output_width: Output video width
        output_height: Output video height

    Returns:
        FFmpeg zoompan filter string
    """
    if VISUAL_STYLE != "zack_d_films":
        # Use original zoom effects
        zoom_effects = [
            f"zoompan=z='min(zoom+0.001,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={output_width}x{output_height}:fps={VIDEO_FPS}",
            f"zoompan=z='1.15':x='if(eq(on,1),0,x+2)':y='ih/2-(ih/zoom/2)':d={frames}:s={output_width}x{output_height}:fps={VIDEO_FPS}",
            f"zoompan=z='1.15':x='if(eq(on,1),iw*0.15,x-2)':y='ih/2-(ih/zoom/2)':d={frames}:s={output_width}x{output_height}:fps={VIDEO_FPS}",
            f"zoompan=z='if(eq(on,1),1.3,max(zoom-0.001,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={output_width}x{output_height}:fps={VIDEO_FPS}",
        ]
        return zoom_effects[scene_idx % len(zoom_effects)]

    # Get enhanced camera movement for Zack D Films style
    camera_key = get_camera_for_scene(scene_idx, total_scenes)
    cam = CAMERA_MOVEMENTS[camera_key]

    zoom_start = cam["zoom_start"]
    zoom_end = cam["zoom_end"]
    x_drift = cam["x_drift"]
    y_drift = cam["y_drift"]

    # Calculate zoom increment per frame
    zoom_delta = (zoom_end - zoom_start) / frames if frames > 0 else 0
    x_delta = x_drift / frames if frames > 0 else 0
    y_delta = y_drift / frames if frames > 0 else 0

    # Build zoompan expression
    # z: zoom factor
    # x: x position (0 = left edge, iw/2-(iw/zoom/2) = centered)
    # y: y position

    if abs(zoom_delta) > 0.0001:
        # Zoom with optional drift
        z_expr = f"if(eq(on,1),{zoom_start},min(zoom+{zoom_delta:.6f},{max(zoom_start, zoom_end)}))"
    else:
        z_expr = f"{zoom_start}"

    # Center position with drift
    if abs(x_delta) > 0.0001:
        x_expr = f"iw/2-(iw/zoom/2)+if(eq(on,1),0,{x_delta:.3f}*on)"
    else:
        x_expr = "iw/2-(iw/zoom/2)"

    if abs(y_delta) > 0.0001:
        y_expr = f"ih/2-(ih/zoom/2)+if(eq(on,1),0,{y_delta:.3f}*on)"
    else:
        y_expr = "ih/2-(ih/zoom/2)"

    return f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={output_width}x{output_height}:fps={VIDEO_FPS}"


def render_segment(
    segment: SceneSegment,
    output_path: Path,
    log: AssemblyLog,
    total_scenes: int = 10,
    apply_color_grading: bool = True,
) -> Path:
    """
    Render a single scene segment to a video file.

    Each segment is rendered independently then concatenated.
    This ensures each scene has its own distinct visual.

    Args:
        segment: SceneSegment with source path and timing
        output_path: Where to save the rendered segment
        log: AssemblyLog for tracking
        total_scenes: Total number of scenes (for camera selection)
        apply_color_grading: Whether to apply Zack D Films color grading
    """
    is_video = _is_video_file(segment.source_path)

    # Get color grading filter if enabled
    color_grade = get_color_grading_filter() if apply_color_grading else ""

    # Build FFmpeg filter for this segment
    if is_video:
        # For video: scale, crop to 9:16, set duration
        source_duration = _get_media_duration(segment.source_path)

        if source_duration < segment.duration:
            # Loop if source is shorter than needed
            loop_count = int(segment.duration / source_duration) + 1
            input_args = ["-stream_loop", str(loop_count), "-i", str(segment.source_path)]
        else:
            input_args = ["-i", str(segment.source_path)]

        # Base video filter
        vf = (
            f"trim=0:{segment.duration},setpts=PTS-STARTPTS,"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"setsar=1,fps={VIDEO_FPS}"
        )

        # Add color grading for Zack D Films style
        if color_grade:
            vf = f"{vf},{color_grade}"

    else:
        # For image: create video with enhanced zoompan effect
        input_args = ["-loop", "1", "-i", str(segment.source_path)]
        frames = int(segment.duration * VIDEO_FPS)

        # Use enhanced camera movements for Zack D Films style
        zoom = get_zoompan_filter(
            scene_idx=segment.scene_idx,
            total_scenes=total_scenes,
            frames=frames,
            output_width=VIDEO_WIDTH,
            output_height=VIDEO_HEIGHT,
        )

        vf = (
            f"scale={VIDEO_WIDTH * 2}:{VIDEO_HEIGHT * 2}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH * 2}:{VIDEO_HEIGHT * 2},"
            f"{zoom},"
            f"setsar=1"
        )

        # Add color grading for Zack D Films style
        if color_grade:
            vf = f"{vf},{color_grade}"

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-vf", vf,
        "-t", str(segment.duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-an",  # No audio for individual segments
        str(output_path),
    ]

    log.ffmpeg_commands.append(" ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log.errors.append(f"Segment {segment.scene_idx + 1} failed: {result.stderr[-200:]}")
        return None

    return output_path


def concatenate_segments(
    segment_paths: list,
    output_path: Path,
    log: AssemblyLog,
    crossfade_duration: float = 0.3,
) -> Path:
    """
    Concatenate rendered segments into final video.

    Uses xfade for smooth transitions between segments.
    """
    if len(segment_paths) == 0:
        raise ValueError("No segments to concatenate")

    if len(segment_paths) == 1:
        # Single segment - just copy
        import shutil
        shutil.copy(segment_paths[0], output_path)
        return output_path

    # Build input args
    input_args = []
    for seg_path in segment_paths:
        input_args.extend(["-i", str(seg_path)])

    # Build xfade chain
    # Each xfade needs: offset = sum of previous durations - crossfade_duration
    filter_parts = []
    current_offset = 0

    # Get durations
    durations = [_get_media_duration(p) for p in segment_paths]

    # First segment doesn't need processing
    current = "[0:v]"

    for i in range(1, len(segment_paths)):
        # Calculate offset: previous segment end minus crossfade overlap
        current_offset = sum(durations[:i]) - (crossfade_duration * i)
        current_offset = max(0, current_offset)

        next_input = f"[{i}:v]"
        output_label = f"[v{i}]" if i < len(segment_paths) - 1 else "[vout]"

        filter_parts.append(
            f"{current}{next_input}xfade=transition=fade:duration={crossfade_duration}:offset={current_offset}{output_label}"
        )
        current = output_label

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    log.ffmpeg_commands.append(" ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log.errors.append(f"Concatenation failed: {result.stderr[-300:]}")
        # Fallback to concat demuxer (no crossfade)
        return _concatenate_simple(segment_paths, output_path, log)

    return output_path


def _concatenate_simple(segment_paths: list, output_path: Path, log: AssemblyLog) -> Path:
    """Simple concatenation without crossfade (fallback)."""
    print("  Using simple concat (no crossfade)...")

    # Create concat file
    concat_file = output_path.parent / "concat_list.txt"
    with open(concat_file, "w") as f:
        for seg_path in segment_paths:
            f.write(f"file '{seg_path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    log.ffmpeg_commands.append(" ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Concat failed: {result.stderr[-300:]}")

    return output_path


def add_audio_and_subtitles(
    video_path: Path,
    voice_path: Path,
    output_path: Path,
    subtitle_path: Optional[Path] = None,
    music_path: Optional[Path] = None,
    total_duration: float = 60,
    log: AssemblyLog = None,
) -> Path:
    """
    Add audio tracks and subtitles to the assembled video.
    """
    input_args = ["-i", str(video_path), "-i", str(voice_path)]

    # Voice filter with delay (1s intro)
    voice_fade_start = total_duration - 2
    audio_filter = f"[1:a]adelay=1000|1000,afade=t=out:st={voice_fade_start}:d=1.5[voice]"

    if music_path and Path(music_path).exists():
        input_args.extend(["-i", str(music_path)])
        music_fade_start = total_duration - 2.5
        audio_filter += (
            f";[2:a]atrim=0:{total_duration},afade=t=in:d=1.5,"
            f"afade=t=out:st={music_fade_start}:d=2.5,volume={MUSIC_VOLUME}[music]"
            f";[voice][music]amix=inputs=2:duration=longest:dropout_transition=2[aout]"
        )
        audio_map = "[aout]"
    else:
        audio_filter += ";[voice]acopy[aout]"
        audio_map = "[aout]"

    # Video filter (subtitles if provided)
    if subtitle_path and Path(subtitle_path).exists():
        sub_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
        video_filter = f"[0:v]ass='{sub_escaped}'[vout]"
        video_map = "[vout]"
    else:
        video_filter = "[0:v]copy[vout]"
        video_map = "[vout]"

    filter_complex = f"{video_filter};{audio_filter}"

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", video_map,
        "-map", audio_map,
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

    if log:
        log.ffmpeg_commands.append(" ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Audio/subtitle merge failed: {result.stderr[-300:]}")

    return output_path


def assemble_video_segmented(
    scenes: list,
    backgrounds: list,
    voice_path: Path,
    output_path: Path,
    subtitle_path: Optional[Path] = None,
    music_path: Optional[Path] = None,
    total_duration: float = 60,
    keywords: list = None,
) -> dict:
    """
    Main entry point: Assemble video with proper scene segmentation.

    GUARANTEES:
    1. Each scene renders as a distinct video segment
    2. Each segment uses its assigned visual
    3. Segments are concatenated in order
    4. Full logging of scene-to-asset mapping
    """
    log = AssemblyLog()

    print("\n" + "=" * 60)
    print("STARTING SEGMENTED VIDEO ASSEMBLY")
    print("=" * 60)

    # Step 1: Create SceneSegment objects
    segments = []
    for i, (scene, bg_path) in enumerate(zip(scenes, backgrounds)):
        duration = scene["end"] - scene["start"]

        # Determine source type
        if "placeholder" in str(bg_path).lower():
            source_type = "placeholder"
            is_placeholder = True
        elif _is_video_file(bg_path):
            source_type = "video"
            is_placeholder = False
        else:
            source_type = "image"
            is_placeholder = False

        seg = SceneSegment(
            scene_idx=i,
            start_time=scene["start"],
            end_time=scene["end"],
            duration=duration,
            source_path=Path(bg_path),
            source_type=source_type,
            is_placeholder=is_placeholder,
            keywords=scene.get("keywords", []),
        )
        segments.append(seg)
        log.add_segment(seg)

    # Print scene mapping
    log.print_mapping()

    # Step 2: Render each segment individually
    print("Rendering individual segments...")
    temp_dir = Path(output_path).parent / "temp_segments"
    temp_dir.mkdir(exist_ok=True)

    total_segments = len(segments)
    rendered_segments = []
    for seg in segments:
        seg_output = temp_dir / f"segment_{seg.scene_idx:02d}.mp4"
        print(f"  Segment {seg.scene_idx + 1}: {seg.source_path.name} ({seg.duration:.1f}s)")

        # Pass total_scenes for enhanced camera movement selection
        result = render_segment(
            seg, seg_output, log,
            total_scenes=total_segments,
            apply_color_grading=COLOR_GRADING_ENABLED,
        )
        if result:
            rendered_segments.append(result)
        else:
            log.warnings.append(f"Segment {seg.scene_idx + 1} failed to render")

    if len(rendered_segments) == 0:
        raise RuntimeError("No segments rendered successfully")

    print(f"\n  Rendered {len(rendered_segments)}/{len(segments)} segments")

    # Step 3: Concatenate segments
    print("\nConcatenating segments...")
    video_only_path = temp_dir / "video_only.mp4"
    concatenate_segments(rendered_segments, video_only_path, log)

    # Step 4: Add audio and subtitles
    print("Adding audio and subtitles...")
    add_audio_and_subtitles(
        video_path=video_only_path,
        voice_path=voice_path,
        output_path=output_path,
        subtitle_path=subtitle_path,
        music_path=music_path,
        total_duration=total_duration,
        log=log,
    )

    # Step 5: Save assembly log
    log_path = log.save_log(output_path)
    print(f"\nAssembly log saved: {log_path}")

    # Cleanup temp files
    try:
        import shutil
        shutil.rmtree(temp_dir)
    except:
        pass

    print(f"\nVideo saved: {output_path}")
    print("=" * 60 + "\n")

    return {
        "video_path": output_path,
        "segments_rendered": len(rendered_segments),
        "segments_total": len(segments),
        "log": log,
    }


if __name__ == "__main__":
    # Test with sample data
    print("Video Assembler Test")
    print("This module provides segmented video assembly.")
    print("Import and use assemble_video_segmented() for production.")
