"""
Placeholder Generator for Missing Scene Footage

When no matching footage exists for a script segment, this module generates
proper placeholder frames that:
- Display exact duration needed
- Show description of required visual
- Use centered readable text
- Have neutral background
- Match narration timing exactly

Output: MP4 video file that can be used as placeholder in final video.
"""
import subprocess
from pathlib import Path
from typing import Optional

# Video specifications
WIDTH = 1080
HEIGHT = 1920
FPS = 30

# Visual styling
BG_COLOR = "#1a1a2e"  # Dark blue-gray neutral background
TEXT_COLOR = "#ffffff"
ACCENT_COLOR = "#e94560"  # Red accent for "Placeholder" label
FONT = "Arial"
FONT_SIZE_LABEL = 48
FONT_SIZE_DURATION = 72
FONT_SIZE_DESCRIPTION = 42


def generate_placeholder_video(
    duration: float,
    description: str,
    output_path: Path,
    scene_number: int = 1,
) -> Path:
    """
    Generate a placeholder video for a missing scene.

    Args:
        duration: Exact duration in seconds (must match narration)
        description: Short description of the visual needed
        output_path: Where to save the placeholder video
        scene_number: Scene number for labeling

    Returns:
        Path to the generated placeholder video
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Format duration for display
    duration_display = f"{duration:.1f}s"

    # Use simple placeholder generation (more reliable)
    return _generate_simple_placeholder(duration, description, output_path, scene_number)


def _generate_simple_placeholder(
    duration: float,
    description: str,
    output_path: Path,
    scene_number: int,
) -> Path:
    """Generate a simple placeholder with clean text layout."""
    import re

    # Clean description for FFmpeg (remove special chars that break filters)
    clean_desc = re.sub(r'[^\w\s\-]', '', description)
    # Truncate if too long
    if len(clean_desc) > 40:
        clean_desc = clean_desc[:37] + "..."

    # Build filter with escaped text
    vf = (
        f"drawtext=text='PLACEHOLDER':fontsize=60:fontcolor=0xe94560:"
        f"x=(w-text_w)/2:y=h/2-200,"
        f"drawtext=text='Scene {scene_number}':fontsize=80:fontcolor=white:"
        f"x=(w-text_w)/2:y=h/2-100,"
        f"drawtext=text='{duration:.1f} seconds':fontsize=60:fontcolor=white:"
        f"x=(w-text_w)/2:y=h/2,"
        f"drawtext=text='Visual needed':fontsize=48:fontcolor=0xaaaaaa:"
        f"x=(w-text_w)/2:y=h/2+120,"
        f"drawtext=text='{clean_desc}':fontsize=36:fontcolor=white:"
        f"x=(w-text_w)/2:y=h/2+200"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x1a1a2e:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}",
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # Ultra-simple fallback - just a colored rectangle
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x1a1a2e:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True)

    return output_path


def _wrap_text(text: str, max_chars: int = 35) -> str:
    """Wrap text to fit within max characters per line."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        if current_length + len(word) + 1 <= max_chars:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)

    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines[:4])  # Max 4 lines


def describe_scene_visual(scene_words: list, script_context: str = "") -> str:
    """
    Generate a DETAILED, ACTIONABLE description of what visual is needed.

    MUST INCLUDE:
    - Main subject (noun from script)
    - Action (verb from script)
    - Context or setting
    - Camera framing suggestion
    - Lighting or mood note

    FORBIDDEN vague phrases:
    - "support visual"
    - "generic footage"
    - "background clip"
    - "B-roll footage"

    Args:
        scene_words: List of word dicts from the scene
        script_context: Full script for additional context

    Returns:
        Detailed visual description with framing and lighting
    """
    import re

    # Extract the scene text
    scene_text = " ".join(w.get("word", "") for w in scene_words)
    scene_lower = scene_text.lower()

    # Extract nouns (subjects) - EXPANDED for fun facts content
    NOUNS = {
        'paper': ('sheet of paper', 'white paper on desk'),
        'fold': ('paper being folded', 'hands folding paper'),
        'moon': ('full moon', 'moon in night sky'),
        'space': ('stars and galaxies', 'deep space nebula'),
        'earth': ('Earth from space', 'planet Earth rotating'),
        'pyramid': ('Egyptian pyramid', 'Great Pyramid of Giza'),
        'cleopatra': ('Egyptian queen imagery', 'ancient Egyptian palace'),
        'ancient': ('ancient ruins', 'historical monuments'),
        'history': ('historical timeline', 'old photographs or artifacts'),
        'lightning': ('lightning bolt', 'storm clouds with lightning'),
        'sun': ('bright sun', 'sunrise or sunset'),
        'water': ('flowing water', 'ocean waves'),
        'ocean': ('vast ocean', 'underwater scene'),
        'fire': ('flames burning', 'campfire or bonfire'),
        'mountain': ('mountain peak', 'mountain landscape'),
        'city': ('city skyline', 'busy urban street'),
        'forest': ('dense forest', 'sunlight through trees'),
        'tree': ('tall tree', 'tree branches'),
        'animal': ('wildlife', 'animal in natural habitat'),
        'person': ('person', 'human figure'),
        'hand': ('human hands', 'hands performing action'),
        'eye': ('human eye', 'eye close-up'),
        'brain': ('brain visualization', 'neural network imagery'),
        'heart': ('beating heart', 'heart symbol or organ'),
        'food': ('fresh food', 'meal being prepared'),
        'science': ('laboratory equipment', 'scientific experiment'),
        'technology': ('modern technology', 'digital interface'),
        'computer': ('computer screen', 'laptop or desktop'),
        'money': ('currency', 'coins or bills'),
        'time': ('clock face', 'time-lapse'),
        'book': ('open book', 'pages turning'),
        'write': ('pen writing', 'handwriting on paper'),
        'think': ('person thinking', 'contemplative pose'),
        'walk': ('person walking', 'feet walking'),
        'run': ('person running', 'athletic movement'),
        'talk': ('person speaking', 'conversation'),
        'build': ('construction', 'building process'),
        'grow': ('plant growing', 'growth time-lapse'),
        'fall': ('falling object', 'autumn leaves falling'),
        'rise': ('rising motion', 'sun rising'),
        'strike': ('impact moment', 'lightning strike'),
        # Games and strategy
        'chess': ('chess board with pieces', 'chess game in progress'),
        'game': ('board game pieces', 'game being played'),
        'board': ('game board', 'board game setup'),
        'play': ('person playing game', 'gameplay action'),
        'strategy': ('strategy diagram', 'tactical planning'),
        'move': ('game piece being moved', 'chess move'),
        # Numbers and math
        'number': ('numbers on screen', 'mathematical equations'),
        'math': ('mathematics symbols', 'calculation being done'),
        'count': ('counting objects', 'numbers appearing'),
        'digit': ('digital numbers', 'number display'),
        'billion': ('large number visualization', 'billion scale concept'),
        'million': ('million scale visual', 'quantity concept'),
        'thousand': ('thousand count', 'quantity visualization'),
        # Scientific concepts
        'atom': ('atomic structure', '3D atom model'),
        'molecule': ('molecular structure', 'chemistry visualization'),
        'cell': ('cell structure', 'microscopic cell view'),
        'dna': ('DNA helix', 'genetic code visualization'),
        'star': ('star in space', 'stellar formation'),
        'planet': ('planet surface', 'planetary view'),
        'galaxy': ('spiral galaxy', 'galaxy formation'),
        # Abstract concepts
        'possible': ('infinite possibilities', 'branching paths visual'),
        'endless': ('infinite horizon', 'endless expanse'),
        'unique': ('one-of-a-kind object', 'distinctive visual'),
        'chance': ('probability visual', 'dice or random chance'),
        'random': ('random patterns', 'chaotic motion'),
    }

    # Extract verbs (actions)
    VERBS = {
        'fold': 'being folded',
        'strike': 'striking',
        'hit': 'hitting',
        'fall': 'falling',
        'rise': 'rising',
        'grow': 'growing',
        'move': 'moving',
        'flow': 'flowing',
        'spin': 'spinning',
        'turn': 'turning',
        'open': 'opening',
        'close': 'closing',
        'build': 'being built',
        'create': 'being created',
        'destroy': 'being destroyed',
        'burn': 'burning',
        'shine': 'shining',
        'glow': 'glowing',
        'flash': 'flashing',
        'walk': 'walking',
        'run': 'running',
        'fly': 'flying',
        'swim': 'swimming',
        'think': 'in thought',
        'write': 'writing',
        'read': 'reading',
    }

    # Camera framings based on subject type
    FRAMINGS = {
        'detail': 'Extreme close-up',
        'object': 'Close-up',
        'person': 'Medium shot',
        'landscape': 'Wide shot',
        'action': 'Tracking shot',
        'scale': 'Wide establishing shot',
    }

    # Lighting/mood based on content
    MOODS = {
        'dramatic': 'dramatic lighting with shadows',
        'calm': 'soft natural lighting',
        'bright': 'bright, well-lit',
        'dark': 'low-key moody lighting',
        'warm': 'warm golden hour lighting',
        'cool': 'cool blue tones',
        'neutral': 'neutral even lighting',
    }

    # Find matching subject
    subject = None
    subject_detail = None
    for keyword, (short, detail) in NOUNS.items():
        if keyword in scene_lower:
            subject = short
            subject_detail = detail
            break

    # Find matching action
    action = None
    for keyword, verb in VERBS.items():
        if keyword in scene_lower:
            action = verb
            break

    # Determine framing
    if subject and any(x in subject.lower() for x in ['hand', 'eye', 'paper', 'detail']):
        framing = FRAMINGS['detail']
    elif subject and any(x in subject.lower() for x in ['person', 'human', 'figure']):
        framing = FRAMINGS['person']
    elif subject and any(x in subject.lower() for x in ['mountain', 'ocean', 'space', 'earth', 'pyramid']):
        framing = FRAMINGS['landscape']
    elif action:
        framing = FRAMINGS['action']
    else:
        framing = FRAMINGS['object']

    # Determine mood/lighting
    if any(x in scene_lower for x in ['dark', 'night', 'shadow', 'mystery']):
        mood = MOODS['dark']
    elif any(x in scene_lower for x in ['bright', 'sun', 'light', 'shine']):
        mood = MOODS['bright']
    elif any(x in scene_lower for x in ['dramatic', 'intense', 'powerful']):
        mood = MOODS['dramatic']
    elif any(x in scene_lower for x in ['calm', 'peace', 'gentle', 'soft']):
        mood = MOODS['calm']
    else:
        mood = MOODS['neutral']

    # Build detailed description
    # REQUIRED: subject, action, context, framing, lighting
    if subject and action:
        description = f"{framing} of {subject} {action}"
    elif subject:
        description = f"{framing} of {subject_detail or subject}"
    elif action:
        description = f"{framing} showing {action} motion"
    else:
        # Extract significant words from the scene (5+ letters to avoid short words)
        # Filter out common stop words and generic words
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'that', 'this', 'with', 'from',
            'have', 'has', 'had', 'been', 'being', 'their', 'there', 'these', 'those',
            'would', 'could', 'should', 'about', 'which', 'where', 'while', 'after',
            'before', 'between', 'under', 'over', 'through', 'during', 'just', 'only',
            'more', 'most', 'some', 'other', 'every', 'each', 'very', 'than', 'then',
        }
        words = re.findall(r'\b[a-zA-Z]{5,}\b', scene_text)
        significant = [w for w in words if w.lower() not in stop_words]

        if significant:
            main_word = significant[0].lower()
            # Build a more descriptive visual suggestion
            if len(significant) >= 2:
                second_word = significant[1].lower()
                description = f"{framing} visualizing '{main_word}' concept with '{second_word}' elements"
            else:
                # Suggest what kind of visual would work
                description = f"{framing} representing '{main_word}' - use abstract or symbolic imagery"
        else:
            # Last resort: use the full scene text as guidance
            clean_text = re.sub(r'[^\w\s]', '', scene_text)[:50].strip()
            if clean_text:
                description = f"{framing} for narration: '{clean_text}' - use supporting visuals"
            else:
                description = f"{framing} - abstract background with subtle motion"

    # Add setting/context based on content
    context = ""
    if any(x in scene_lower for x in ['ancient', 'history', 'old', 'past']):
        context = "historical setting"
    elif any(x in scene_lower for x in ['modern', 'technology', 'digital']):
        context = "modern tech environment"
    elif any(x in scene_lower for x in ['nature', 'forest', 'ocean', 'mountain']):
        context = "natural environment"
    elif any(x in scene_lower for x in ['space', 'universe', 'stars', 'galaxy']):
        context = "cosmic/space backdrop"

    # Build final description with all required elements
    if context:
        full_description = f"{description} in {context}, {mood}"
    else:
        full_description = f"{description}, {mood}"

    return full_description


class PlaceholderReport:
    """Track placeholders generated for a video for user follow-up."""

    def __init__(self):
        self.placeholders = []

    def add(self, scene_num: int, duration: float, description: str, path: Path):
        self.placeholders.append({
            "scene": scene_num,
            "duration": duration,
            "description": description,
            "path": str(path),
        })

    def has_placeholders(self) -> bool:
        return len(self.placeholders) > 0

    def to_markdown(self) -> str:
        """Generate markdown report of placeholders for user."""
        if not self.placeholders:
            return "No placeholders - all scenes have matching footage."

        lines = [
            "# Placeholder Report",
            "",
            "The following scenes need footage uploaded:",
            "",
        ]

        for p in self.placeholders:
            lines.append(f"## Scene {p['scene']} ({p['duration']:.1f}s)")
            lines.append(f"**Visual needed:** {p['description']}")
            lines.append(f"**Placeholder file:** `{p['path']}`")
            lines.append("")

        lines.append("---")
        lines.append("Replace placeholder files with matching footage and re-run pipeline.")

        return "\n".join(lines)

    def save_report(self, output_dir: Path) -> Path:
        """Save placeholder report to file."""
        report_path = output_dir / "PLACEHOLDERS_NEEDED.md"
        with open(report_path, "w") as f:
            f.write(self.to_markdown())
        return report_path


if __name__ == "__main__":
    # Test placeholder generation
    test_output = Path("/tmp/test_placeholder.mp4")

    generate_placeholder_video(
        duration=3.5,
        description="Close-up of paper being folded in half repeatedly",
        output_path=test_output,
        scene_number=2,
    )

    print(f"Generated test placeholder: {test_output}")

    # Verify
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration",
         "-of", "csv=p=0", str(test_output)],
        capture_output=True, text=True,
    )
    print(f"Placeholder specs: {result.stdout.strip()}")
