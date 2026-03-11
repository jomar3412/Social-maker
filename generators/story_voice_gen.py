"""
Story Voice Script Generator

Transforms stories into voice-ready scripts with:
- Pacing markers: [pause: short/medium/long]
- Emotional directions: [whisper], [urgent], [calm]
- Genre-to-voice mapping (Ethan for thriller, Adam for comedy)
- Natural speech patterns for narration

Maps to the "Voice Script Generator" agent in the 5-agent orchestration.

Usage:
    from generators.story_voice_gen import VoiceScriptGenerator

    generator = VoiceScriptGenerator()
    voice_script = generator.generate(story_output, genre="thriller")
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path

from config.settings import ELEVENLABS_VOICE_ID
from training.niche_config import NicheConfig


# Voice recommendations by genre
GENRE_VOICE_MAP = {
    "thriller": {
        "voice_id": "Ethan",  # Deep, serious
        "style": "measured, building tension, whispers at key moments",
        "pace": "medium, slowing at suspense points",
        "energy": "controlled, with sudden intensity shifts"
    },
    "mystery": {
        "voice_id": "Ethan",
        "style": "thoughtful, curious, dramatic reveals",
        "pace": "steady with strategic pauses for clues",
        "energy": "medium, building intrigue"
    },
    "comedy": {
        "voice_id": "Adam",  # Warm, friendly
        "style": "playful, varied pace, comedic timing",
        "pace": "quick with pauses for beats",
        "energy": "high, expressive"
    },
    "horror": {
        "voice_id": "Ethan",
        "style": "low, creeping dread, sudden intensity shifts",
        "pace": "slow, deliberate, sudden accelerations",
        "energy": "low with sudden spikes"
    },
    "drama": {
        "voice_id": "Ethan",
        "style": "emotional, varied, authentic delivery",
        "pace": "natural conversation rhythm",
        "energy": "medium with emotional peaks"
    },
    "romance": {
        "voice_id": "Rachel",  # Warm, intimate
        "style": "warm, intimate, yearning",
        "pace": "gentle, lingering on emotional moments",
        "energy": "low to medium, soft"
    }
}

# Pacing markers
PAUSE_MARKERS = {
    "short": 0.3,   # seconds
    "medium": 0.7,
    "long": 1.2,
    "dramatic": 2.0
}

# Emotional markers
EMOTIONAL_MARKERS = [
    "[whisper]",
    "[urgent]",
    "[trembling]",
    "[calm]",
    "[intense]",
    "[soft]",
    "[cold]",
    "[warm]",
    "[fearful]",
    "[relieved]"
]


@dataclass
class VoiceScript:
    """Voice-ready script with pacing and emotional directions."""
    raw_text: str = ""
    marked_text: str = ""  # Text with [pause] and [emotion] markers
    voice_id: str = ""
    voice_style: str = ""
    pace: str = ""
    energy: str = ""
    sections: List[Dict[str, Any]] = field(default_factory=list)
    estimated_duration: float = 0.0
    word_count: int = 0
    pause_count: int = 0
    emotion_markers: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        """Export as markdown for human review."""
        lines = [
            "# Voice Script",
            "",
            f"**Voice:** {self.voice_id}",
            f"**Style:** {self.voice_style}",
            f"**Pace:** {self.pace}",
            f"**Duration:** ~{self.estimated_duration:.1f}s",
            f"**Words:** {self.word_count}",
            "",
            "---",
            "",
            "## Script with Directions",
            "",
            self.marked_text,
            "",
            "---",
            "",
            "## Section Breakdown",
            ""
        ]

        for i, section in enumerate(self.sections, 1):
            lines.append(f"### Section {i}: {section.get('type', 'body').upper()}")
            lines.append(f"**Emotion:** {section.get('emotion', 'neutral')}")
            lines.append(f"**Pace:** {section.get('pace', 'normal')}")
            lines.append("")
            lines.append(section.get('text', ''))
            lines.append("")

        return "\n".join(lines)


class VoiceScriptGenerator:
    """
    Generates voice-ready scripts from story content.

    Adds pacing markers, emotional directions, and maps
    genre to appropriate voice characteristics.
    """

    def __init__(self, anthropic_key: str = None):
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        self._niche_config = None

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.anthropic_key)
        return self._client

    def _load_style_guide(self) -> NicheConfig:
        """Load the short_stories style guide."""
        if self._niche_config is None:
            self._niche_config = NicheConfig("short_stories")
        return self._niche_config

    def _get_voice_config(self, genre: str) -> Dict[str, str]:
        """Get voice configuration for a genre."""
        return GENRE_VOICE_MAP.get(genre, GENRE_VOICE_MAP["thriller"])

    def generate(
        self,
        story_text: str,
        genre: str = "thriller",
        hook: str = "",
        twist: str = "",
        mood: str = "",
        custom_voice_id: str = None,
    ) -> VoiceScript:
        """
        Generate a voice-ready script from story text.

        Args:
            story_text: The full story text
            genre: Story genre for voice selection
            hook: The hook section (for special treatment)
            twist: The twist/ending section (for special treatment)
            mood: Overall mood for emotional calibration
            custom_voice_id: Override the genre-default voice

        Returns:
            VoiceScript with marked text and sections
        """
        voice_config = self._get_voice_config(genre)
        voice_id = custom_voice_id or voice_config["voice_id"]

        # Get genre-specific audio style from style guide
        style_guide = self._load_style_guide()
        audio_style = style_guide.style_guide.get("audio_style", {})
        voice_directions = audio_style.get("voice_directions", {})

        prompt = f"""Transform this story into a voice-ready script for narration.

STORY:
{story_text}

GENRE: {genre}
MOOD: {mood or "match the story"}
HOOK SECTION: {hook or "(first few sentences)"}
TWIST SECTION: {twist or "(ending)"}

VOICE STYLE GUIDANCE:
- Style: {voice_config['style']}
- Pace: {voice_config['pace']}
- Energy: {voice_config['energy']}
- Narrator default: {voice_directions.get('narrator_default', 'first-person, intimate')}

YOUR TASK:
Add pacing and emotional markers to make this script perfect for voice narration.

AVAILABLE MARKERS:
Pacing: [pause: short], [pause: medium], [pause: long], [pause: dramatic]
Emotions: [whisper], [urgent], [trembling], [calm], [intense], [soft], [cold], [warm], [fearful], [relieved]

RULES:
1. Add [pause: short] after periods for natural breathing
2. Add [pause: medium] at paragraph breaks or scene transitions
3. Add [pause: long] or [pause: dramatic] before major reveals
4. Add emotional markers before sentences that need special delivery
5. HOOK should have attention-grabbing delivery
6. TWIST should have dramatic build-up pauses
7. Don't over-mark - let some parts flow naturally
8. Keep original text intact, just add markers

Respond in JSON:
{{
    "marked_text": "Full text with [pause] and [emotion] markers inserted",
    "sections": [
        {{
            "type": "hook|buildup|twist",
            "text": "Section text with markers",
            "emotion": "primary emotion for this section",
            "pace": "slow|medium|fast",
            "intensity": 1-10
        }}
    ],
    "emotion_markers_used": ["list of emotions used"],
    "pause_count": 15,
    "delivery_notes": "Overall guidance for the voice actor"
}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())

            marked_text = data.get("marked_text", story_text)

            # Calculate duration including pauses
            word_count = len(re.sub(r'\[.*?\]', '', marked_text).split())
            pause_count = data.get("pause_count", marked_text.count("[pause:"))

            # Estimate pause time
            pause_time = 0
            for pause_type, duration in PAUSE_MARKERS.items():
                count = marked_text.count(f"[pause: {pause_type}]")
                pause_time += count * duration

            estimated_duration = (word_count / 2.5) + pause_time

            return VoiceScript(
                raw_text=story_text,
                marked_text=marked_text,
                voice_id=voice_id,
                voice_style=voice_config["style"],
                pace=voice_config["pace"],
                energy=voice_config["energy"],
                sections=data.get("sections", []),
                estimated_duration=estimated_duration,
                word_count=word_count,
                pause_count=pause_count,
                emotion_markers=data.get("emotion_markers_used", []),
            )

        except Exception as e:
            print(f"Error generating voice script: {e}")
            # Return basic script without markers
            word_count = len(story_text.split())
            return VoiceScript(
                raw_text=story_text,
                marked_text=story_text,
                voice_id=voice_id,
                voice_style=voice_config["style"],
                pace=voice_config["pace"],
                energy=voice_config["energy"],
                estimated_duration=word_count / 2.5,
                word_count=word_count,
            )

    def strip_markers(self, marked_text: str) -> str:
        """Remove all markers to get clean text for TTS."""
        # Remove emotion markers
        text = re.sub(r'\[(whisper|urgent|trembling|calm|intense|soft|cold|warm|fearful|relieved)\]', '', marked_text)
        # Remove pause markers
        text = re.sub(r'\[pause:\s*\w+\]', '', text)
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def get_ssml(self, voice_script: VoiceScript) -> str:
        """
        Convert marked text to SSML for TTS engines that support it.

        Note: ElevenLabs uses its own markup, but this produces
        standard SSML for other engines.
        """
        text = voice_script.marked_text

        # Convert pauses to SSML breaks
        for pause_type, duration in PAUSE_MARKERS.items():
            text = text.replace(
                f"[pause: {pause_type}]",
                f'<break time="{int(duration * 1000)}ms"/>'
            )

        # Convert emotions to prosody (simplified)
        emotion_prosody = {
            "[whisper]": '<prosody volume="soft" rate="slow">',
            "[urgent]": '<prosody rate="fast" pitch="+10%">',
            "[trembling]": '<prosody rate="slow" pitch="-5%">',
            "[calm]": '<prosody rate="slow" volume="soft">',
            "[intense]": '<prosody volume="loud" rate="medium" pitch="+5%">',
            "[soft]": '<prosody volume="soft">',
            "[cold]": '<prosody rate="slow" pitch="-10%">',
            "[warm]": '<prosody volume="medium" pitch="+5%">',
            "[fearful]": '<prosody rate="fast" pitch="+15%">',
            "[relieved]": '<prosody rate="slow" volume="soft" pitch="-5%">',
        }

        for marker, prosody in emotion_prosody.items():
            # Find the next sentence after each marker and wrap it
            pattern = re.escape(marker) + r'\s*([^.!?]+[.!?])'
            text = re.sub(pattern, prosody + r'\1</prosody>', text)

        return f'<speak>{text}</speak>'


def get_voice_recommendation(genre: str) -> Dict[str, str]:
    """Get the recommended voice settings for a genre."""
    return GENRE_VOICE_MAP.get(genre, GENRE_VOICE_MAP["thriller"])


# CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Voice Script Generator")
        print("=" * 50)
        print("\nCommands:")
        print("  python story_voice_gen.py generate <story_file> --genre thriller")
        print("  python story_voice_gen.py voices")
        print("  python story_voice_gen.py strip <marked_text>")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "generate":
        if len(sys.argv) < 3:
            print("Usage: python story_voice_gen.py generate <story_file> [--genre thriller]")
            sys.exit(1)

        story_file = Path(sys.argv[2])
        genre = "thriller"

        if "--genre" in sys.argv:
            idx = sys.argv.index("--genre")
            if idx + 1 < len(sys.argv):
                genre = sys.argv[idx + 1]

        # Load story
        if story_file.suffix == ".json":
            with open(story_file) as f:
                data = json.load(f)
                story_text = data.get("full_story", "")
                hook = data.get("hook", "")
                twist = data.get("twist", "")
                mood = data.get("mood", "")
        else:
            with open(story_file) as f:
                story_text = f.read()
                hook = ""
                twist = ""
                mood = ""

        print(f"Generating voice script for {genre} story...")
        generator = VoiceScriptGenerator()
        script = generator.generate(
            story_text=story_text,
            genre=genre,
            hook=hook,
            twist=twist,
            mood=mood,
        )

        print(script.to_markdown())

    elif cmd == "voices":
        print("Voice Recommendations by Genre:")
        print("-" * 50)
        for genre, config in GENRE_VOICE_MAP.items():
            print(f"\n{genre.upper()}:")
            print(f"  Voice: {config['voice_id']}")
            print(f"  Style: {config['style']}")
            print(f"  Pace: {config['pace']}")
            print(f"  Energy: {config['energy']}")

    elif cmd == "strip":
        if len(sys.argv) < 3:
            print("Usage: python story_voice_gen.py strip '<marked text>'")
            sys.exit(1)

        marked_text = sys.argv[2]
        generator = VoiceScriptGenerator()
        clean_text = generator.strip_markers(marked_text)
        print(clean_text)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
