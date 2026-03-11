"""
Kinetic Typography System for Zack D Films Style

Generates animated text overlays with:
- 140pt font for hooks (BIG kinetic text)
- 100pt font for body text
- Scale-pop animation on first appearance
- Slide-in effects (alternating left/right)
- Gold highlighting for keywords
- 8px outline for mobile readability

Output: ASS subtitle files with advanced animation effects
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path
import re


# ASS color format: &HAABBGGRR (alpha, blue, green, red)
COLOR_WHITE = "&H00FFFFFF"
COLOR_GOLD_BGR = "&H0000D7FF"  # Gold in BGR format
COLOR_CORAL_BGR = "&H005050FF"  # Coral accent
COLOR_CYAN_BGR = "&H00FFE4CA"  # Cyan accent
COLOR_BLACK = "&H00000000"
COLOR_SHADOW = "&H80000000"


class KineticAnimation(Enum):
    """Kinetic text animation types."""
    SCALE_POP = "scale_pop"         # Scale from 0 to 100 with bounce
    SLIDE_LEFT = "slide_left"       # Slide in from left
    SLIDE_RIGHT = "slide_right"     # Slide in from right
    SLIDE_UP = "slide_up"           # Slide in from bottom
    FADE_SCALE = "fade_scale"       # Fade in with slight scale
    TYPEWRITER = "typewriter"       # Letter by letter reveal
    BOUNCE_IN = "bounce_in"         # Bounce effect entrance
    ZOOM_BLUR = "zoom_blur"         # Zoom in with motion blur effect


@dataclass
class KineticTextConfig:
    """Configuration for kinetic typography."""

    # Font settings - LARGE for mobile
    hook_font_size: int = 140       # BIG font for hooks
    body_font_size: int = 100       # Still large for body
    font_name: str = "Arial Black"  # Bold, readable font

    # Outline for readability
    outline_size: int = 8           # Thick outline for contrast
    shadow_size: int = 4            # Subtle shadow

    # Colors
    primary_color: str = COLOR_WHITE
    highlight_color: str = COLOR_GOLD_BGR
    accent_color: str = COLOR_CORAL_BGR
    outline_color: str = COLOR_BLACK
    shadow_color: str = COLOR_SHADOW

    # Animation timing
    animation_duration_ms: int = 300    # Animation duration
    hold_before_exit_ms: int = 200      # Hold time before exit

    # Position
    margin_v: int = 150             # Vertical margin from bottom
    margin_h: int = 60              # Horizontal margins

    # Video dimensions
    video_width: int = 1080
    video_height: int = 1920


def _format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format: H:MM:SS.CC"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centiseconds = int((secs - int(secs)) * 100)
    return f"{hours}:{minutes:02d}:{int(secs):02d}.{centiseconds:02d}"


def _create_kinetic_header(config: KineticTextConfig) -> str:
    """Generate ASS header with kinetic text styles."""
    return f"""[Script Info]
Title: Kinetic Typography
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {config.video_width}
PlayResY: {config.video_height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,{config.font_name},{config.hook_font_size},{config.primary_color},&H000000FF,{config.outline_color},{config.shadow_color},-1,0,0,0,100,100,0,0,1,{config.outline_size},{config.shadow_size},2,{config.margin_h},{config.margin_h},{config.margin_v},1
Style: Body,{config.font_name},{config.body_font_size},{config.primary_color},&H000000FF,{config.outline_color},{config.shadow_color},-1,0,0,0,100,100,0,0,1,{config.outline_size},{config.shadow_size},2,{config.margin_h},{config.margin_h},{config.margin_v},1
Style: Highlight,{config.font_name},{config.body_font_size},{config.highlight_color},&H000000FF,{config.outline_color},{config.shadow_color},-1,0,0,0,100,100,0,0,1,{config.outline_size},{config.shadow_size},2,{config.margin_h},{config.margin_h},{config.margin_v},1
Style: HookHighlight,{config.font_name},{config.hook_font_size},{config.highlight_color},&H000000FF,{config.outline_color},{config.shadow_color},-1,0,0,0,100,100,0,0,1,{config.outline_size},{config.shadow_size},2,{config.margin_h},{config.margin_h},{config.margin_v},1
Style: Accent,{config.font_name},{config.body_font_size},{config.accent_color},&H000000FF,{config.outline_color},{config.shadow_color},-1,0,0,0,100,100,0,0,1,{config.outline_size},{config.shadow_size},2,{config.margin_h},{config.margin_h},{config.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _get_animation_tags(
    animation: KineticAnimation,
    duration_ms: int = 300,
    is_exit: bool = False,
) -> str:
    """
    Generate ASS override tags for kinetic animation.

    IMPORTANT: Uses only fade and scale effects - NO \pos() overrides.
    \pos() conflicts with ASS margin system and causes off-screen glitches.
    ASS margins (set in styles) handle positioning reliably.

    Args:
        animation: Type of animation
        duration_ms: Animation duration in milliseconds
        is_exit: Whether this is an exit animation

    Returns:
        ASS override tag string
    """
    if is_exit:
        # Exit animation: simple fade out only (no position changes)
        return f"{{\\t(0,{duration_ms},\\alpha&HFF&)}}"

    # Entrance animations - use only fade and scale (no \pos())
    if animation == KineticAnimation.SCALE_POP:
        # Scale from 0 to 110% then settle to 100%
        settle_time = duration_ms // 3
        return (
            f"{{\\fscx0\\fscy0"
            f"\\t(0,{duration_ms},\\fscx110\\fscy110)"
            f"\\t({duration_ms},{duration_ms + settle_time},\\fscx100\\fscy100)}}"
        )

    elif animation == KineticAnimation.FADE_SCALE:
        # Fade in with scale from 90% to 100%
        return (
            f"{{\\alpha&HFF&\\fscx90\\fscy90"
            f"\\t(0,{duration_ms},\\alpha&H00&\\fscx100\\fscy100)}}"
        )

    elif animation == KineticAnimation.BOUNCE_IN:
        # Bounce effect: scale overshoot then settle
        mid_time = duration_ms * 2 // 3
        return (
            f"{{\\fscx0\\fscy0"
            f"\\t(0,{mid_time},\\fscx115\\fscy115)"
            f"\\t({mid_time},{duration_ms},\\fscx100\\fscy100)}}"
        )

    elif animation == KineticAnimation.ZOOM_BLUR:
        # Start large and blurred, zoom to normal
        return (
            f"{{\\fscx150\\fscy150\\blur5"
            f"\\t(0,{duration_ms},\\fscx100\\fscy100\\blur0)}}"
        )

    elif animation == KineticAnimation.TYPEWRITER:
        # For typewriter, we use karaoke-style reveal
        return f"{{\\k{duration_ms // 10}}}"

    # SLIDE_LEFT, SLIDE_RIGHT, SLIDE_UP all fall through to default
    # These caused off-screen issues with \pos() - use simple fade instead

    # Default: simple fade in
    return f"{{\\fad({duration_ms},0)}}"


def _select_animation_for_scene(
    scene_index: int,
    total_scenes: int,
    is_hook: bool = False,
) -> KineticAnimation:
    """
    Select appropriate animation based on scene position.

    NOTE: Only uses animations that work reliably with ASS margins.
    SLIDE_LEFT, SLIDE_RIGHT, SLIDE_UP removed - they used \pos() which
    conflicts with margin positioning and caused off-screen glitches.

    Args:
        scene_index: Current scene (0-indexed)
        total_scenes: Total number of scenes
        is_hook: Whether this is a hook/opening text

    Returns:
        Appropriate KineticAnimation
    """
    if is_hook or scene_index == 0:
        # Hooks and opening: BIG scale pop
        return KineticAnimation.SCALE_POP

    if scene_index == total_scenes - 1:
        # Closing: zoom blur for impact
        return KineticAnimation.ZOOM_BLUR

    # Alternate between WORKING animations only (no slide/position effects)
    animations = [
        KineticAnimation.FADE_SCALE,
        KineticAnimation.BOUNCE_IN,
        KineticAnimation.SCALE_POP,
        KineticAnimation.FADE_SCALE,
    ]

    return animations[scene_index % len(animations)]


def _highlight_keywords(text: str, keywords: List[str], is_hook: bool = False) -> str:
    """
    Apply gold highlighting to keywords using ASS inline styles.

    Args:
        text: Original text
        keywords: List of keywords to highlight
        is_hook: Whether this is hook text (uses HookHighlight style)

    Returns:
        Text with ASS style overrides for keywords
    """
    if not keywords:
        return text

    keywords_lower = {k.lower() for k in keywords}
    highlight_style = "HookHighlight" if is_hook else "Highlight"

    words = text.split()
    result_words = []

    for word in words:
        # Check if word (without punctuation) matches a keyword
        clean_word = re.sub(r'[^\w]', '', word.lower())
        if clean_word in keywords_lower:
            # Apply highlight style to this word
            result_words.append(f"{{\\r{highlight_style}}}{word}{{\\r}}")
        else:
            result_words.append(word)

    return " ".join(result_words)


@dataclass
class KineticTextChunk:
    """A chunk of text with kinetic animation."""
    text: str
    start_time: float
    end_time: float
    animation: KineticAnimation
    is_hook: bool = False
    keywords: List[str] = field(default_factory=list)


def generate_kinetic_subtitles(
    word_timing: List[Dict],
    keywords: Optional[List[str]] = None,
    output_path: Optional[Path] = None,
    config: Optional[KineticTextConfig] = None,
    hook_text: Optional[str] = None,
    hook_duration: float = 2.0,
) -> Path:
    """
    Generate kinetic typography ASS subtitles.

    Args:
        word_timing: List of {"word": "hello", "start": 0.0, "end": 0.5}
        keywords: Words to highlight in gold
        output_path: Where to save the .ass file
        config: KineticTextConfig (uses defaults if None)
        hook_text: Optional opening hook text
        hook_duration: How long to display the hook

    Returns:
        Path to generated .ass file
    """
    if config is None:
        config = KineticTextConfig()

    if output_path is None:
        output_path = Path("kinetic_subtitles.ass")
    else:
        output_path = Path(output_path)

    keywords = keywords or []

    # Generate header
    ass_content = _create_kinetic_header(config)

    # Track y position (for potential multi-line layouts)
    y_pos = config.video_height - config.margin_v

    # Add hook if provided
    time_offset = 0.0
    if hook_text:
        animation = KineticAnimation.SCALE_POP
        anim_tags = _get_animation_tags(animation, config.animation_duration_ms)

        # Highlight keywords in hook
        styled_text = _highlight_keywords(hook_text, keywords, is_hook=True)

        start = _format_ass_time(0)
        end = _format_ass_time(hook_duration)

        ass_content += f"Dialogue: 0,{start},{end},Hook,,0,0,0,,{anim_tags}{styled_text}\n"
        time_offset = hook_duration

    # Group words into display chunks (max 6 words per chunk for readability)
    MAX_WORDS = 6
    MIN_DISPLAY_TIME = 1.2

    chunks = []
    current_words = []
    current_timing = []

    for word_info in word_timing:
        current_words.append(word_info["word"])
        current_timing.append(word_info)

        # Check for natural breaks
        word = word_info["word"]
        is_sentence_end = word.rstrip().endswith(('.', '!', '?'))
        is_chunk_full = len(current_words) >= MAX_WORDS

        if is_sentence_end or is_chunk_full:
            if current_timing:
                chunks.append({
                    "words": current_words.copy(),
                    "timing": current_timing.copy(),
                    "start": current_timing[0]["start"] + time_offset,
                    "end": current_timing[-1]["end"] + time_offset,
                })
            current_words = []
            current_timing = []

    # Flush remaining
    if current_timing:
        chunks.append({
            "words": current_words.copy(),
            "timing": current_timing.copy(),
            "start": current_timing[0]["start"] + time_offset,
            "end": current_timing[-1]["end"] + time_offset,
        })

    # Generate dialogue lines for each chunk
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks):
        # Select animation based on position
        animation = _select_animation_for_scene(i, total_chunks)
        anim_tags = _get_animation_tags(animation, config.animation_duration_ms)

        # Replace {y} placeholder with actual y position
        anim_tags = anim_tags.replace("{y}", str(y_pos))

        # Build text with keyword highlighting
        text = " ".join(chunk["words"])
        styled_text = _highlight_keywords(text, keywords)

        # Adjust timing for readability
        start_time = max(0, chunk["start"] - 0.1)  # Show slightly early
        end_time = chunk["end"] + 0.3  # Hold slightly longer

        # Ensure minimum display time
        if end_time - start_time < MIN_DISPLAY_TIME:
            end_time = start_time + MIN_DISPLAY_TIME

        start = _format_ass_time(start_time)
        end = _format_ass_time(end_time)

        ass_content += f"Dialogue: 0,{start},{end},Body,,0,0,0,,{anim_tags}{styled_text}\n"

    # Write file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return output_path


def create_hook_overlay(
    hook_text: str,
    duration: float = 2.0,
    output_path: Optional[Path] = None,
    config: Optional[KineticTextConfig] = None,
    keywords: Optional[List[str]] = None,
) -> Path:
    """
    Create a standalone hook overlay ASS file.

    For use when you want just the opening hook animation.

    Args:
        hook_text: The hook text to display
        duration: How long to display
        output_path: Where to save
        config: Style configuration
        keywords: Words to highlight

    Returns:
        Path to generated .ass file
    """
    if config is None:
        config = KineticTextConfig()

    if output_path is None:
        output_path = Path("hook_overlay.ass")

    # Generate with just the hook
    return generate_kinetic_subtitles(
        word_timing=[],
        keywords=keywords,
        output_path=output_path,
        config=config,
        hook_text=hook_text,
        hook_duration=duration,
    )


if __name__ == "__main__":
    # Test kinetic text generation
    print("Kinetic Typography System")
    print("=" * 50)

    # Test word timing
    test_timing = [
        {"word": "On", "start": 0.0, "end": 0.2},
        {"word": "Venus,", "start": 0.2, "end": 0.5},
        {"word": "a", "start": 0.5, "end": 0.6},
        {"word": "day", "start": 0.6, "end": 0.9},
        {"word": "is", "start": 0.9, "end": 1.0},
        {"word": "longer", "start": 1.0, "end": 1.4},
        {"word": "than", "start": 1.4, "end": 1.6},
        {"word": "a", "start": 1.6, "end": 1.7},
        {"word": "year.", "start": 1.7, "end": 2.2},
        {"word": "The", "start": 2.5, "end": 2.7},
        {"word": "planet", "start": 2.7, "end": 3.0},
        {"word": "rotates", "start": 3.0, "end": 3.4},
        {"word": "incredibly", "start": 3.4, "end": 3.9},
        {"word": "slowly.", "start": 3.9, "end": 4.4},
    ]

    test_keywords = ["Venus", "day", "year", "planet"]
    test_hook = "Mind-blowing space fact!"

    config = KineticTextConfig()
    print(f"\nConfig:")
    print(f"  Hook font size: {config.hook_font_size}pt")
    print(f"  Body font size: {config.body_font_size}pt")
    print(f"  Outline size: {config.outline_size}px")

    output = generate_kinetic_subtitles(
        test_timing,
        keywords=test_keywords,
        output_path=Path("/tmp/kinetic_test.ass"),
        hook_text=test_hook,
    )

    print(f"\nGenerated: {output}")

    # Print sample of content
    with open(output) as f:
        content = f.read()
        print("\n--- Sample ASS Content ---")
        lines = content.split('\n')
        for line in lines[-10:]:  # Last 10 lines
            print(line)
