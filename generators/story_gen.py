"""
Story Generator - Core Story Creation Agent

Generates 200-300 word short stories using the multi-model pipeline.
Maps to the "Story Creator" agent in the 5-agent orchestration.

Features:
- Hook-buildup-twist structure
- Character description extraction for visual consistency
- Genre-specific tone and pacing
- Series/continuation support

Usage:
    from generators.story_gen import StoryGenerator, StoryOutput

    generator = StoryGenerator()
    story = generator.generate(
        genre="thriller",
        topic="A coffee stain that shouldn't be there"
    )
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config.settings import ANTHROPIC_API_KEY, STORY_WORD_COUNT, STORY_TARGET_DURATION
from training.niche_config import NicheConfig
from generators.story_registry import StoryRegistry, Character, StoryStatus


@dataclass
class StoryOutput:
    """Structured output from story generation."""
    title: str = ""
    genre: str = ""
    hook: str = ""
    buildup: str = ""
    twist: str = ""
    full_story: str = ""
    characters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    setting: str = ""
    mood: str = ""
    pov: str = "first_person"
    word_count: int = 0
    estimated_duration: float = 0.0
    keywords: List[str] = field(default_factory=list)
    visual_cues: List[Dict[str, Any]] = field(default_factory=list)
    ending_type: str = ""
    expandable: bool = True
    continuation_hooks: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "StoryOutput":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class StoryGenerator:
    """
    Generates short stories optimized for short-form video.

    Uses Claude for story generation with genre-specific prompting
    based on the short_stories style guide.
    """

    def __init__(self, anthropic_key: str = None):
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        self._niche_config = None
        self.registry = StoryRegistry()

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

    def _build_prompt(
        self,
        genre: str,
        topic: Optional[str] = None,
        continuation_from: Optional[str] = None,
        characters: Optional[Dict[str, Character]] = None,
        additional_instructions: Optional[str] = None,
    ) -> str:
        """Build the story generation prompt."""
        style_config = self._load_style_guide()
        style_additions = style_config.get_prompt_additions(genre=genre)

        # Get genre-specific info
        genres = style_config.style_guide.get("genres", {})
        genre_info = genres.get(genre, {})

        # Build continuation context if continuing a story
        continuation_context = ""
        if continuation_from:
            try:
                prev_data = self.registry.get_story_for_continuation(continuation_from)
                prev_story = prev_data.get("story", {})
                continuation_context = f"""
CONTINUATION CONTEXT:
You are continuing an existing story. Here's what happened before:

Previous Story ID: {continuation_from}
Previous Title: {prev_story.get('title', 'Unknown')}

IMPORTANT: Maintain consistency with:
- Same characters (descriptions below)
- Same world/setting rules
- Same narrative voice
- Pick up where the story left off or explore aftermath

Previous characters to reuse:
{json.dumps(prev_data.get('characters', {}), indent=2)}
"""
            except Exception as e:
                continuation_context = f"(Could not load continuation context: {e})"

        # Build character context if provided
        character_context = ""
        if characters:
            char_descs = []
            for name, char in characters.items():
                if isinstance(char, Character):
                    char_descs.append(f"- {name}: {char.to_prompt()}")
                elif isinstance(char, dict):
                    char_descs.append(f"- {name}: {char.get('description', '')}")
            if char_descs:
                character_context = f"""
ESTABLISHED CHARACTERS (use these exactly):
{chr(10).join(char_descs)}
"""

        # Topic context
        topic_section = ""
        if topic:
            topic_section = f"""
STORY SEED/TOPIC:
{topic}

Use this as inspiration for the story. The story should revolve around or incorporate this element.
"""

        prompt = f"""You are a masterful short story writer creating content for short-form video (TikTok, YouTube Shorts, Instagram Reels).

{style_additions}

GENRE: {genre.upper()}
- Voice style: {genre_info.get('voice_style', 'narrative')}
- Energy: {genre_info.get('energy', 'medium')}
- Pacing: {genre_info.get('pacing', 'varied')}
- Themes: {', '.join(genre_info.get('themes', []))}
{topic_section}
{continuation_context}
{character_context}

REQUIREMENTS:
1. Target length: {STORY_WORD_COUNT} words (approximately {STORY_TARGET_DURATION} seconds when read)
2. Structure: Hook (15 words) → Buildup (150 words) → Twist (50 words)
3. First-person POV preferred (more immersive for video)
4. Short, punchy sentences for pacing
5. Create vivid sensory details for visual adaptation
6. End with impact (twist, revelation, or cliffhanger)

CHARACTER EXTRACTION:
For EACH character in the story, provide detailed visual description including:
- Age and gender
- Hair color and style
- Clothing description
- Distinctive features
- Emotional state in the story

{f"ADDITIONAL INSTRUCTIONS: {additional_instructions}" if additional_instructions else ""}

Respond in JSON:
{{
    "title": "Story title (short, intriguing)",
    "hook": "First 2-3 sentences that grab attention immediately",
    "buildup": "The middle section - develop tension, character, setting",
    "twist": "The ending - payoff, revelation, or cliffhanger",
    "full_story": "Complete story as one text block",
    "characters": {{
        "character_name": {{
            "description": "Full visual description",
            "age": "e.g., mid-30s",
            "gender": "e.g., male",
            "hair": "e.g., short dark hair, slightly messy",
            "clothing": "e.g., worn leather jacket, faded jeans",
            "distinctive_features": "e.g., scar above left eyebrow",
            "emotional_state": "e.g., paranoid, anxious"
        }}
    }},
    "setting": "Where and when the story takes place",
    "mood": "Overall emotional tone (e.g., tense, eerie, bittersweet)",
    "pov": "first_person or third_person",
    "keywords": ["important", "visual", "words"],
    "visual_cues": [
        {{"at_text": "specific phrase", "visual": "what to show", "shot_type": "close-up/wide/medium"}}
    ],
    "ending_type": "twist|cliffhanger|resolution|open_ended|callback",
    "expandable": true,
    "continuation_hooks": ["Potential directions for Part 2"],
    "estimated_duration": 60
}}"""

        return prompt

    def generate(
        self,
        genre: str = "thriller",
        topic: Optional[str] = None,
        continuation_from: Optional[str] = None,
        series_name: Optional[str] = None,
        characters: Optional[Dict[str, Character]] = None,
        additional_instructions: Optional[str] = None,
        save_to_registry: bool = True,
    ) -> StoryOutput:
        """
        Generate a short story.

        Args:
            genre: Story genre (thriller, mystery, comedy, horror, drama, romance)
            topic: Optional topic/seed for the story
            continuation_from: Story ID to continue from
            series_name: Optional series to add this story to
            characters: Pre-defined characters to use
            additional_instructions: Extra instructions for generation
            save_to_registry: Whether to save to story registry

        Returns:
            StoryOutput with the generated story
        """
        # Build prompt
        prompt = self._build_prompt(
            genre=genre,
            topic=topic,
            continuation_from=continuation_from,
            characters=characters,
            additional_instructions=additional_instructions,
        )

        # Generate story
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            # Parse JSON response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())

            # Calculate word count
            full_story = data.get("full_story", "")
            word_count = len(full_story.split())
            estimated_duration = word_count / 2.5  # ~2.5 words per second

            # Build StoryOutput
            output = StoryOutput(
                title=data.get("title", "Untitled"),
                genre=genre,
                hook=data.get("hook", ""),
                buildup=data.get("buildup", ""),
                twist=data.get("twist", ""),
                full_story=full_story,
                characters=data.get("characters", {}),
                setting=data.get("setting", ""),
                mood=data.get("mood", ""),
                pov=data.get("pov", "first_person"),
                word_count=word_count,
                estimated_duration=estimated_duration,
                keywords=data.get("keywords", []),
                visual_cues=data.get("visual_cues", []),
                ending_type=data.get("ending_type", "twist"),
                expandable=data.get("expandable", True),
                continuation_hooks=data.get("continuation_hooks", []),
            )

            # Save to registry if requested
            if save_to_registry:
                story_id = self.registry.create_story(
                    title=output.title,
                    genre=genre,
                    series_name=series_name,
                    metadata={
                        "topic": topic,
                        "continuation_from": continuation_from,
                        "word_count": word_count,
                        "estimated_duration": estimated_duration,
                    }
                )

                # Add characters to registry
                for name, char_data in output.characters.items():
                    char = Character(
                        name=name,
                        description=char_data.get("description", ""),
                        age=char_data.get("age"),
                        gender=char_data.get("gender"),
                        hair=char_data.get("hair"),
                        clothing=char_data.get("clothing"),
                        distinctive_features=char_data.get("distinctive_features"),
                    )
                    self.registry.update_story(
                        story_id,
                        characters={name: char}
                    )

                output.story_id = story_id

            return output

        except Exception as e:
            print(f"Error generating story: {e}")
            raise

    def generate_continuation(
        self,
        story_id: str,
        direction: Optional[str] = None,
    ) -> StoryOutput:
        """
        Generate a continuation of an existing story.

        Args:
            story_id: The story ID to continue
            direction: Optional direction hint for the continuation

        Returns:
            StoryOutput for the continuation
        """
        # Get the original story data
        prev_data = self.registry.get_story_for_continuation(story_id)
        prev_story = prev_data.get("story", {})

        # Get characters from the original story
        characters = {}
        for name, char_data in prev_data.get("characters", {}).items():
            if isinstance(char_data, dict):
                characters[name] = Character.from_dict(char_data)

        # Determine series
        series_name = None
        if prev_story.get("series_id"):
            series = self.registry.get_series(prev_story["series_id"])
            if series:
                series_name = series.name

        return self.generate(
            genre=prev_story.get("genre", "thriller"),
            continuation_from=story_id,
            series_name=series_name,
            characters=characters,
            additional_instructions=direction,
        )


def extract_characters_from_story(story_text: str, genre: str = "thriller") -> Dict[str, Dict]:
    """
    Extract character descriptions from an existing story text.
    Useful for retrofitting stories without character data.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    prompt = f"""Analyze this short story and extract detailed character descriptions.

STORY:
{story_text}

GENRE: {genre}

For each character mentioned in the story, provide:
- Full visual description suitable for image generation
- Age and gender
- Hair color and style
- Clothing description
- Distinctive features
- Emotional state in the story

Respond in JSON:
{{
    "characters": {{
        "character_name": {{
            "description": "Full visual description",
            "age": "e.g., mid-30s",
            "gender": "e.g., male",
            "hair": "e.g., short dark hair",
            "clothing": "e.g., worn leather jacket",
            "distinctive_features": "e.g., scar above left eyebrow",
            "emotional_state": "e.g., paranoid"
        }}
    }}
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        data = json.loads(response_text.strip())
        return data.get("characters", {})

    except Exception as e:
        print(f"Error extracting characters: {e}")
        return {}


# CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Story Generator")
        print("=" * 50)
        print("\nCommands:")
        print("  python story_gen.py generate thriller")
        print("  python story_gen.py generate mystery --topic 'A locked room'")
        print("  python story_gen.py continue STORY-001")
        print("  python story_gen.py extract 'story text here'")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "generate":
        genre = sys.argv[2] if len(sys.argv) > 2 else "thriller"
        topic = None

        # Parse --topic flag
        if "--topic" in sys.argv:
            idx = sys.argv.index("--topic")
            if idx + 1 < len(sys.argv):
                topic = sys.argv[idx + 1]

        print(f"Generating {genre} story...")
        generator = StoryGenerator()
        story = generator.generate(genre=genre, topic=topic)

        print(f"\nTitle: {story.title}")
        print(f"Genre: {story.genre}")
        print(f"Word count: {story.word_count}")
        print(f"Duration: ~{story.estimated_duration:.1f}s")
        print(f"\n--- STORY ---\n")
        print(story.full_story)
        print(f"\n--- CHARACTERS ---")
        for name, char in story.characters.items():
            print(f"\n{name}:")
            print(f"  {char.get('description', 'No description')}")

    elif cmd == "continue":
        if len(sys.argv) < 3:
            print("Usage: python story_gen.py continue STORY-ID")
            sys.exit(1)

        story_id = sys.argv[2]
        print(f"Continuing story {story_id}...")
        generator = StoryGenerator()
        story = generator.generate_continuation(story_id)

        print(f"\nTitle: {story.title}")
        print(f"\n--- CONTINUATION ---\n")
        print(story.full_story)

    elif cmd == "extract":
        if len(sys.argv) < 3:
            print("Usage: python story_gen.py extract 'story text'")
            sys.exit(1)

        story_text = sys.argv[2]
        characters = extract_characters_from_story(story_text)
        print(json.dumps(characters, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
