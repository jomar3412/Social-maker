"""
Clean Caption Generator for Social Media Videos

STRICT STABILITY RULES:
1. Break captions by natural speech phrases
2. Maximum 2 lines per caption block
3. Maximum 6 words per line
4. Maximum 42 characters per line
5. Only one caption active at any time (no overlap)
6. No overlapping timestamps - minimum 0.1s buffer
7. Fixed bottom-center alignment (Alignment=2)
8. Consistent font size - no auto-scaling
9. Simple fade in/out animations ONLY
10. No movement, scaling, or position changes

Output: Clean, stable, non-overlapping ASS subtitle files
"""
import re
from pathlib import Path
from typing import List, Dict, Optional, Set

# ASS color format: &HAABBGGRR (alpha, blue, green, red)
COLOR_WHITE = "&H00FFFFFF"
COLOR_GOLD_BGR = "&H0000D7FF"  # Gold in BGR format
COLOR_BLACK = "&H00000000"
COLOR_SHADOW = "&H80000000"  # Semi-transparent black

# === STRICT CAPTION RULES ===
MAX_WORDS_PER_LINE = 6      # Rule 3: Max 6 words per line
MAX_LINES = 2               # Rule 2: Max 2 lines per caption
MAX_CHARS_PER_LINE = 42     # Rule 4: Max 42 characters per line
MAX_WORDS_PER_CAPTION = MAX_WORDS_PER_LINE * MAX_LINES  # 12 words max
CAPTION_BUFFER_SEC = 0.1    # Rule 6: Minimum gap between captions

# Style settings - FIXED, no auto-scaling (Rule 8)
DEFAULT_FONT = "Arial Black"
DEFAULT_FONT_SIZE = 90      # Fixed size for consistency
DEFAULT_OUTLINE = 6         # Thick outline for readability
DEFAULT_SHADOW = 3
DEFAULT_MARGIN_V = 120      # Fixed bottom margin (Rule 7)

# Timing - captions must stay until phrase is COMPLETELY spoken
MIN_DISPLAY_TIME = 1.8      # Minimum time caption stays on screen
FADE_IN_MS = 100            # Quick fade in (Rule 10)
FADE_OUT_MS = 150           # Slightly longer fade out (Rule 10)
DEFAULT_POST_ROLL = 0.3     # Keep caption 0.3s AFTER last word ends


def _format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format: H:MM:SS.CC"""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centiseconds = int((secs - int(secs)) * 100)
    return f"{hours}:{minutes:02d}:{int(secs):02d}.{centiseconds:02d}"


def _create_ass_header(video_width: int = 1080, video_height: int = 1920) -> str:
    """
    Generate ASS header with clean, stable styles.

    - Alignment=2: Bottom center (Rule 7)
    - Fixed font size (Rule 8)
    - No dynamic scaling
    """
    return f"""[Script Info]
Title: Clean Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {video_width}
PlayResY: {video_height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{DEFAULT_FONT},{DEFAULT_FONT_SIZE},{COLOR_WHITE},&H000000FF,{COLOR_BLACK},{COLOR_SHADOW},-1,0,0,0,100,100,0,0,1,{DEFAULT_OUTLINE},{DEFAULT_SHADOW},2,60,60,{DEFAULT_MARGIN_V},1
Style: Highlight,{DEFAULT_FONT},{DEFAULT_FONT_SIZE},{COLOR_GOLD_BGR},&H000000FF,{COLOR_BLACK},{COLOR_SHADOW},-1,0,0,0,100,100,0,0,1,{DEFAULT_OUTLINE},{DEFAULT_SHADOW},2,60,60,{DEFAULT_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _is_natural_break(word: str) -> tuple:
    """
    Check if word ends with a natural speech break.

    Returns:
        (is_sentence_end, is_clause_break)
    """
    stripped = word.rstrip()
    is_sentence_end = stripped.endswith(('.', '!', '?'))
    is_clause_break = stripped.endswith((',', ':', ';', '-'))
    return is_sentence_end, is_clause_break


def _split_into_lines(words: List[str]) -> List[str]:
    """
    Split words into lines following strict rules.

    Rules:
    - Max 6 words per line
    - Max 42 characters per line
    - Max 2 lines total

    Returns:
        List of line strings (1-2 lines)
    """
    if not words:
        return []

    lines = []
    current_line = []
    current_chars = 0

    for word in words:
        word_len = len(word) + (1 if current_line else 0)  # +1 for space

        # Check if adding word exceeds limits
        would_exceed_chars = (current_chars + word_len) > MAX_CHARS_PER_LINE
        would_exceed_words = len(current_line) >= MAX_WORDS_PER_LINE

        if current_line and (would_exceed_chars or would_exceed_words):
            # Start new line
            lines.append(" ".join(current_line))
            current_line = [word]
            current_chars = len(word)

            # Check if we've hit max lines
            if len(lines) >= MAX_LINES:
                break
        else:
            current_line.append(word)
            current_chars += word_len

    # Add remaining words if we haven't hit max lines
    if current_line and len(lines) < MAX_LINES:
        lines.append(" ".join(current_line))

    return lines


def _chunk_by_speech_phrases(word_timing: List[Dict]) -> List[Dict]:
    """
    Group words into caption chunks by natural speech phrases.

    Rules:
    - Break at sentence boundaries
    - Break at clause boundaries when approaching limits
    - Respect max words (12) and max lines (2)
    - Ensure no overlap - each chunk has clear start/end

    Returns:
        List of chunks: {
            "words": ["word1", "word2"],
            "start": 0.0,
            "end": 1.5,
            "lines": ["line 1", "line 2"]
        }
    """
    chunks = []
    current_words = []
    current_timing = []

    def flush_chunk():
        """Save current chunk and reset."""
        nonlocal current_words, current_timing

        if not current_words:
            return

        # Calculate timing
        start_time = current_timing[0]["start"]
        end_time = current_timing[-1]["end"]

        # Ensure minimum display time
        if end_time - start_time < MIN_DISPLAY_TIME:
            end_time = start_time + MIN_DISPLAY_TIME

        # Split into lines
        lines = _split_into_lines(current_words)

        chunks.append({
            "words": current_words.copy(),
            "timing": current_timing.copy(),
            "start": start_time,
            "end": end_time,
            "lines": lines,
        })

        current_words = []
        current_timing = []

    for word_info in word_timing:
        word = word_info["word"]
        current_words.append(word)
        current_timing.append(word_info)

        # Check for natural breaks
        is_sentence_end, is_clause_break = _is_natural_break(word)

        # Calculate current state
        word_count = len(current_words)
        is_approaching_limit = word_count >= MAX_WORDS_PER_LINE  # 6+ words
        is_at_max = word_count >= MAX_WORDS_PER_CAPTION  # 12 words

        # Flush conditions (priority order):
        if is_at_max:
            # Hard limit - always flush
            flush_chunk()
        elif is_sentence_end:
            # Natural sentence break - always flush
            flush_chunk()
        elif is_clause_break and is_approaching_limit:
            # Clause break when getting long - flush
            flush_chunk()
        elif word_count >= MAX_WORDS_PER_LINE + 2:
            # Getting too long without natural break - force flush
            flush_chunk()

    # Flush remaining words
    flush_chunk()

    return chunks


def _ensure_no_overlap(chunks: List[Dict], pre_roll: float = 0.05, post_roll: float = DEFAULT_POST_ROLL) -> List[Dict]:
    """
    Ensure no caption overlap with minimum buffer between captions.

    Rule 5 & 6: Only one caption active at a time, 0.1s buffer minimum.

    CRITICAL: Captions must stay on screen until the phrase is FULLY spoken.
    We NEVER shorten caption end times - only delay start times if needed.
    """
    if not chunks:
        return chunks

    for i in range(1, len(chunks)):
        # Calculate actual display times (with pre/post roll)
        prev_display_end = chunks[i - 1]["end"] + post_roll
        curr_display_start = chunks[i]["start"] - pre_roll

        # Check if they would overlap when displayed
        if curr_display_start < prev_display_end + CAPTION_BUFFER_SEC:
            # NEVER shorten previous caption - it must stay until phrase is done
            # Instead, DELAY the next caption's start time
            required_gap = CAPTION_BUFFER_SEC + pre_roll + post_roll
            chunks[i]["start"] = chunks[i - 1]["end"] + required_gap

            # Note: This may cause the next caption to appear slightly late,
            # but it's better than cutting off the previous phrase early

    return chunks


def _normalize_word(word: str) -> str:
    """Remove punctuation for keyword matching."""
    return re.sub(r'[^\w\s]', '', word.lower())


def _build_caption_text(lines: List[str], timing: List[Dict], keywords: Set[str]) -> str:
    """
    Build ASS text for caption with keyword highlighting.

    Uses \\N for line breaks in ASS format.
    Simple fade in/out only (Rule 10).
    """
    # Build word-by-word with highlighting
    highlighted_lines = []
    word_idx = 0

    for line in lines:
        line_parts = []
        line_words = line.split()

        for word in line_words:
            if word_idx < len(timing):
                word_normalized = _normalize_word(word)
                if word_normalized in keywords:
                    line_parts.append(f"{{\\rHighlight}}{word}{{\\rDefault}}")
                else:
                    line_parts.append(word)
                word_idx += 1
            else:
                line_parts.append(word)

        highlighted_lines.append(" ".join(line_parts))

    # Join lines with ASS line break
    text = "\\N".join(highlighted_lines)

    # Add simple fade animation ONLY (Rule 10)
    text = f"{{\\fad({FADE_IN_MS},{FADE_OUT_MS})}}{text}"

    return text


def generate_subtitles(
    word_timing: List[Dict],
    keywords: Optional[List[str]] = None,
    output_path: Optional[Path] = None,
    video_width: int = 1080,
    video_height: int = 1920,
    words_per_chunk: Optional[int] = None,  # Ignored - using speech phrase chunking
    fade_duration: float = 0.2,  # Ignored - using fixed fade
    pre_roll: float = 0.05,
    post_roll: float = DEFAULT_POST_ROLL,  # 0.3s - keeps caption after phrase ends
) -> Path:
    """
    Generate clean, stable ASS subtitles following strict rules.

    RULES ENFORCED:
    1. Natural speech phrase breaks
    2. Max 2 lines per caption
    3. Max 6 words per line
    4. Max 42 chars per line
    5. One caption at a time
    6. No overlapping timestamps (0.1s buffer)
    7. Fixed bottom-center alignment
    8. Consistent font size
    9. Container height based on line count
    10. Simple fade in/out only

    Args:
        word_timing: List of {"word": "hello", "start": 0.0, "end": 0.5}
        keywords: Words to highlight in gold
        output_path: Where to save the .ass file
        video_width: Video width
        video_height: Video height
        pre_roll: Seconds to show text before spoken
        post_roll: Seconds to keep text after spoken

    Returns:
        Path to generated .ass file
    """
    if output_path is None:
        output_path = Path("subtitles.ass")
    else:
        output_path = Path(output_path)

    # Normalize keywords
    keywords_set = set()
    if keywords:
        keywords_set = {k.lower() for k in keywords}

    # Generate header
    ass_content = _create_ass_header(video_width, video_height)

    # Chunk by natural speech phrases
    chunks = _chunk_by_speech_phrases(word_timing)

    # Ensure no overlap (Rule 5 & 6) - pass pre/post roll for accurate calculation
    chunks = _ensure_no_overlap(chunks, pre_roll=pre_roll, post_roll=post_roll)

    # Generate dialogue lines
    for chunk in chunks:
        # Apply pre-roll and post-roll
        start_time = max(0, chunk["start"] - pre_roll)
        end_time = chunk["end"] + post_roll

        # Format timestamps
        start_str = _format_ass_time(start_time)
        end_str = _format_ass_time(end_time)

        # Build caption text with highlighting and fade
        text = _build_caption_text(
            chunk["lines"],
            chunk["timing"],
            keywords_set
        )

        # Create dialogue line (Layer 0, fixed margins from style)
        ass_content += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"

    # Write file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return output_path


def extract_keywords_auto(text: str, content: Optional[Dict] = None) -> List[str]:
    """
    Automatically extract keywords from text.

    Extracts:
    - Explicit keywords from content dict
    - Capitalized words (proper nouns)
    - Repeated significant words
    """
    # Check for explicit keywords first
    if content and "keywords" in content:
        return content["keywords"]

    keywords = set()

    # Common words to skip
    common_words = {
        'that', 'this', 'with', 'from', 'have', 'been', 'were',
        'they', 'their', 'what', 'when', 'where', 'which', 'will',
        'would', 'could', 'should', 'about', 'your', 'into', 'only',
        'other', 'than', 'then', 'them', 'these', 'some', 'very',
        'just', 'like', 'more', 'most', 'such', 'even', 'also',
        'back', 'after', 'first', 'being', 'those', 'made', 'well',
    }

    words = text.split()

    # Find capitalized words (not at sentence start)
    for i, word in enumerate(words):
        if i > 0:
            prev_word = words[i - 1]
            if not prev_word.endswith(('.', '!', '?')):
                clean = _normalize_word(word)
                if word[0].isupper() and len(clean) > 2:
                    keywords.add(clean)

    # Find repeated significant words
    word_counts = {}
    for word in words:
        clean = _normalize_word(word)
        if len(clean) > 4 and clean not in common_words:
            word_counts[clean] = word_counts.get(clean, 0) + 1

    for word, count in word_counts.items():
        if count >= 2:
            keywords.add(word)

    return list(keywords)[:10]


if __name__ == "__main__":
    # Test with sample word timing
    print("Clean Caption Generator Test")
    print("=" * 50)

    test_timing = [
        {"word": "What", "start": 0.0, "end": 0.2},
        {"word": "if", "start": 0.2, "end": 0.3},
        {"word": "your", "start": 0.3, "end": 0.5},
        {"word": "feet", "start": 0.5, "end": 0.8},
        {"word": "could", "start": 0.8, "end": 1.0},
        {"word": "taste", "start": 1.0, "end": 1.3},
        {"word": "your", "start": 1.3, "end": 1.5},
        {"word": "food?", "start": 1.5, "end": 2.0},
        {"word": "Sounds", "start": 2.2, "end": 2.5},
        {"word": "crazy,", "start": 2.5, "end": 2.8},
        {"word": "but", "start": 2.8, "end": 3.0},
        {"word": "one", "start": 3.0, "end": 3.2},
        {"word": "creature", "start": 3.2, "end": 3.6},
        {"word": "does", "start": 3.6, "end": 3.8},
        {"word": "exactly", "start": 3.8, "end": 4.2},
        {"word": "that.", "start": 4.2, "end": 4.6},
        {"word": "Butterflies", "start": 5.0, "end": 5.5},
        {"word": "taste", "start": 5.5, "end": 5.8},
        {"word": "with", "start": 5.8, "end": 6.0},
        {"word": "their", "start": 6.0, "end": 6.2},
        {"word": "feet.", "start": 6.2, "end": 6.8},
    ]

    test_keywords = ["butterflies", "taste", "feet"]

    output = generate_subtitles(
        test_timing,
        keywords=test_keywords,
        output_path=Path("/tmp/clean_captions_test.ass")
    )

    print(f"Generated: {output}")
    print("\n--- Caption Chunks ---")

    chunks = _chunk_by_speech_phrases(test_timing)
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i + 1}:")
        print(f"  Time: {chunk['start']:.2f}s - {chunk['end']:.2f}s")
        print(f"  Lines: {chunk['lines']}")
        print(f"  Words: {len(chunk['words'])}")

    print("\n--- ASS Content ---")
    with open(output) as f:
        print(f.read())
