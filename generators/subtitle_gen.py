"""
ASS Subtitle Generator for Social Media Videos

Generates Advanced SubStation Alpha (.ass) subtitle files with:
- Large white text at bottom of screen
- Black outline + shadow for readability
- Gold color for highlighted keywords
- Fade-in effect on each caption chunk
"""
import re
from pathlib import Path

# ASS color format: &HAABBGGRR (alpha, blue, green, red)
COLOR_WHITE = "&H00FFFFFF"
COLOR_GOLD = "&H00FFD700"  # Note: ASS uses BGR, so gold (#FFD700) = &H00D7FF (actually &H0000D7FF in BGR)
COLOR_GOLD_BGR = "&H0000D7FF"  # Correct BGR format for gold
COLOR_BLACK = "&H00000000"
COLOR_SHADOW = "&H80000000"  # Semi-transparent black

# Default style settings
DEFAULT_FONT = "Arial"
DEFAULT_FONT_SIZE = 72
DEFAULT_OUTLINE = 4
DEFAULT_SHADOW = 2
DEFAULT_MARGIN_V = 80  # Vertical margin from bottom


def _format_ass_time(seconds):
    """Convert seconds to ASS time format: H:MM:SS.CC (centiseconds)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centiseconds = int((secs - int(secs)) * 100)
    return f"{hours}:{minutes:02d}:{int(secs):02d}.{centiseconds:02d}"


def _create_ass_header(video_width=1080, video_height=1920, font_name=DEFAULT_FONT,
                       font_size=DEFAULT_FONT_SIZE):
    """Generate the ASS file header with styles."""
    return f"""[Script Info]
Title: Auto-generated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {video_width}
PlayResY: {video_height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{COLOR_WHITE},&H000000FF,{COLOR_BLACK},{COLOR_SHADOW},-1,0,0,0,100,100,0,0,1,{DEFAULT_OUTLINE},{DEFAULT_SHADOW},2,40,40,{DEFAULT_MARGIN_V},1
Style: Highlight,{font_name},{font_size},{COLOR_GOLD_BGR},&H000000FF,{COLOR_BLACK},{COLOR_SHADOW},-1,0,0,0,100,100,0,0,1,{DEFAULT_OUTLINE},{DEFAULT_SHADOW},2,40,40,{DEFAULT_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _chunk_words(word_timing, words_per_chunk=3, min_display_time=1.5):
    """
    Group words into display chunks with proper timing.

    Args:
        word_timing: List of {"word": "hello", "start": 0.0, "end": 0.5}
        words_per_chunk: Target words per subtitle chunk (reduced for better sync)
        min_display_time: Minimum time each chunk stays on screen

    Returns:
        List of {"words": ["hello", "world"], "start": 0.0, "end": 1.0, "timing": [...]}
    """
    chunks = []
    current_chunk = []
    current_timing = []

    for word_info in word_timing:
        current_chunk.append(word_info["word"])
        current_timing.append(word_info)

        # Check for sentence-ending punctuation or chunk limit
        is_sentence_end = word_info["word"].rstrip().endswith(('.', '!', '?', ':'))
        is_chunk_full = len(current_chunk) >= words_per_chunk

        if is_sentence_end or is_chunk_full:
            if current_chunk:
                start_time = current_timing[0]["start"]
                end_time = current_timing[-1]["end"]

                # Ensure minimum display time
                actual_duration = end_time - start_time
                if actual_duration < min_display_time:
                    end_time = start_time + min_display_time

                chunks.append({
                    "words": current_chunk,
                    "start": start_time,
                    "end": end_time,
                    "timing": current_timing,
                })
                current_chunk = []
                current_timing = []

    # Don't forget remaining words
    if current_chunk:
        start_time = current_timing[0]["start"]
        end_time = current_timing[-1]["end"]

        # Ensure minimum display time for last chunk
        actual_duration = end_time - start_time
        if actual_duration < min_display_time:
            end_time = start_time + min_display_time

        chunks.append({
            "words": current_chunk,
            "start": start_time,
            "end": end_time,
            "timing": current_timing,
        })

    return chunks


def _normalize_word(word):
    """Remove punctuation for keyword matching."""
    return re.sub(r'[^\w\s]', '', word.lower())


def _build_chunk_text(chunk, keywords):
    """
    Build the ASS text for a chunk, highlighting keywords.

    Args:
        chunk: Chunk dict with "words" and "timing"
        keywords: Set of keywords to highlight (lowercase)

    Returns:
        ASS-formatted text string with inline style overrides
    """
    keywords_lower = {k.lower() for k in keywords} if keywords else set()
    parts = []

    for word_info in chunk["timing"]:
        word = word_info["word"]
        word_normalized = _normalize_word(word)

        if word_normalized in keywords_lower:
            # Apply highlight style
            parts.append(f"{{\\rHighlight}}{word}{{\\rDefault}}")
        else:
            parts.append(word)

    return " ".join(parts)


def generate_subtitles(word_timing, keywords=None, output_path=None,
                       video_width=1080, video_height=1920,
                       words_per_chunk=3, fade_duration=0.15,
                       pre_roll=0.1, post_roll=0.3):
    """
    Generate an ASS subtitle file from word timing data.

    Args:
        word_timing: List of {"word": "hello", "start": 0.0, "end": 0.5}
        keywords: List of words to highlight in gold (optional)
        output_path: Path to save the .ass file
        video_width: Video width in pixels
        video_height: Video height in pixels
        words_per_chunk: Number of words per subtitle chunk
        fade_duration: Duration of fade-in effect in seconds
        pre_roll: Seconds to show text BEFORE the word is spoken
        post_roll: Seconds to keep text on screen AFTER the word ends

    Returns:
        Path to the generated .ass file
    """
    if output_path is None:
        output_path = Path("subtitles.ass")
    else:
        output_path = Path(output_path)

    # Normalize keywords for matching
    keywords_set = set()
    if keywords:
        keywords_set = {k.lower() for k in keywords}

    # Generate header
    ass_content = _create_ass_header(video_width, video_height)

    # Chunk words into subtitle segments
    chunks = _chunk_words(word_timing, words_per_chunk)

    # Generate dialogue lines
    for chunk in chunks:
        # Apply pre-roll (show text slightly early) and post-roll (keep text longer)
        adjusted_start = max(0, chunk["start"] - pre_roll)
        adjusted_end = chunk["end"] + post_roll

        start_time = _format_ass_time(adjusted_start)
        end_time = _format_ass_time(adjusted_end)

        # Build text with keyword highlighting
        text = _build_chunk_text(chunk, keywords_set)

        # Add fade-in effect
        fade_ms = int(fade_duration * 1000)
        text = f"{{\\fad({fade_ms},0)}}{text}"

        # Create dialogue line
        ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n"

    # Write file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return output_path


def extract_keywords_auto(text, content=None):
    """
    Automatically extract keywords from text if none provided.

    Extracts:
    - Words from the last sentence (often the call to action)
    - Capitalized words (proper nouns, emphasized words)
    - Repeated important terms

    Args:
        text: The voiceover text
        content: Optional content dict that may have explicit keywords

    Returns:
        List of keywords
    """
    # Check for explicit keywords first
    if content and "keywords" in content:
        return content["keywords"]

    keywords = set()

    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    # Get key words from last sentence (often the CTA)
    if sentences:
        last_sentence = sentences[-1]
        # Get significant words (length > 4, not common words)
        common_words = {'that', 'this', 'with', 'from', 'have', 'been', 'were',
                       'they', 'their', 'what', 'when', 'where', 'which', 'will',
                       'would', 'could', 'should', 'about', 'your', 'into', 'only',
                       'other', 'than', 'then', 'them', 'these', 'some', 'very'}
        words = last_sentence.split()
        for word in words:
            clean = _normalize_word(word)
            if len(clean) > 4 and clean not in common_words:
                keywords.add(clean)

    # Find capitalized words (not at sentence start)
    words = text.split()
    for i, word in enumerate(words):
        # Skip first word of sentences
        if i > 0:
            prev_word = words[i-1]
            if not prev_word.endswith(('.', '!', '?')):
                clean = _normalize_word(word)
                if word[0].isupper() and len(clean) > 2:
                    keywords.add(clean)

    # Look for repeated significant words (appear 2+ times)
    word_counts = {}
    for word in words:
        clean = _normalize_word(word)
        if len(clean) > 4:
            word_counts[clean] = word_counts.get(clean, 0) + 1

    for word, count in word_counts.items():
        if count >= 2:
            keywords.add(word)

    # Limit to top keywords
    return list(keywords)[:10]


if __name__ == "__main__":
    # Test with sample word timing
    test_timing = [
        {"word": "We", "start": 0.0, "end": 0.2},
        {"word": "suffer", "start": 0.2, "end": 0.5},
        {"word": "more", "start": 0.5, "end": 0.7},
        {"word": "often", "start": 0.7, "end": 1.0},
        {"word": "in", "start": 1.0, "end": 1.1},
        {"word": "imagination", "start": 1.1, "end": 1.8},
        {"word": "than", "start": 1.8, "end": 2.0},
        {"word": "in", "start": 2.0, "end": 2.1},
        {"word": "reality.", "start": 2.1, "end": 2.8},
        {"word": "Seneca", "start": 3.0, "end": 3.5},
        {"word": "wrote", "start": 3.5, "end": 3.8},
        {"word": "this.", "start": 3.8, "end": 4.2},
    ]

    test_keywords = ["imagination", "reality", "seneca"]

    output = generate_subtitles(
        test_timing,
        keywords=test_keywords,
        output_path="/tmp/test_subtitles.ass"
    )
    print(f"Generated subtitles: {output}")

    # Print content for verification
    with open(output) as f:
        print("\n--- ASS Content ---")
        print(f.read())
