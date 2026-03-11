"""
Story Visual Prompt Generator

Generates Midjourney prompts for story scenes with:
- Character consistency via --cref and --cw parameters
- Vertical format (--ar 9:16)
- Genre-appropriate styling
- Character reference prompts first, then scene prompts

Maps to the "Visual Prompt Builder" agent in the 5-agent orchestration.

Usage:
    from generators.story_visual_gen import VisualPromptGenerator, VisualPromptSet

    generator = VisualPromptGenerator()
    prompts = generator.generate_prompts(
        scene_plan=scene_plan,
        characters=characters,
        genre="thriller"
    )
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path
from enum import Enum

from training.niche_config import NicheConfig


# Midjourney parameters
DEFAULT_MJ_PARAMS = {
    "aspect_ratio": "--ar 9:16",
    "version": "--v 6.1",
    "quality": "--q 1",
}

# Style presets by genre
GENRE_STYLE_PRESETS = {
    "thriller": {
        "style": "cinematic noir, dramatic lighting, high contrast, shadows",
        "color_grade": "desaturated, cold tones, deep blacks",
        "mood_words": ["tense", "mysterious", "dark", "atmospheric"],
        "lighting": "low-key lighting, harsh shadows, single light source",
    },
    "mystery": {
        "style": "moody atmosphere, fog, depth of field, film grain",
        "color_grade": "muted colors, blue-gray tones",
        "mood_words": ["enigmatic", "curious", "intriguing", "shadowy"],
        "lighting": "diffused lighting, ambient glow, soft shadows",
    },
    "comedy": {
        "style": "bright, expressive, dynamic composition, vibrant",
        "color_grade": "saturated, warm tones, high contrast",
        "mood_words": ["playful", "energetic", "fun", "lively"],
        "lighting": "bright even lighting, soft shadows",
    },
    "horror": {
        "style": "dark atmosphere, unsettling, minimal visibility, dread",
        "color_grade": "desaturated, sickly greens, deep shadows",
        "mood_words": ["terrifying", "eerie", "disturbing", "nightmarish"],
        "lighting": "extreme low-key, underlighting, red accents",
    },
    "drama": {
        "style": "emotional, cinematic composition, natural, intimate",
        "color_grade": "rich tones, golden hour warmth",
        "mood_words": ["emotional", "intimate", "profound", "moving"],
        "lighting": "natural lighting, soft window light, golden hour",
    },
    "romance": {
        "style": "soft focus, dreamy, warm, intimate framing",
        "color_grade": "warm pastels, pink and gold tones",
        "mood_words": ["romantic", "tender", "warm", "dreamy"],
        "lighting": "soft diffused lighting, backlighting, lens flare",
    }
}


class PromptType(Enum):
    CHARACTER_REF = "character_reference"
    SCENE = "scene"
    ESTABLISHING = "establishing"
    DETAIL = "detail"


@dataclass
class MidjourneyPrompt:
    """A single Midjourney prompt."""
    prompt_type: PromptType
    prompt_text: str = ""
    parameters: str = ""
    full_prompt: str = ""  # prompt_text + parameters
    scene_number: Optional[int] = None
    character_name: Optional[str] = None
    notes: str = ""
    reference_url: Optional[str] = None  # For --cref

    def to_dict(self) -> dict:
        data = asdict(self)
        data["prompt_type"] = self.prompt_type.value
        return data

    def get_copy_paste_prompt(self) -> str:
        """Get the full prompt ready to paste into Midjourney."""
        return self.full_prompt


@dataclass
class VisualPromptSet:
    """Complete set of prompts for a story."""
    story_id: str = ""
    title: str = ""
    genre: str = ""
    character_prompts: List[MidjourneyPrompt] = field(default_factory=list)
    scene_prompts: List[MidjourneyPrompt] = field(default_factory=list)
    style_reference: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["character_prompts"] = [p.to_dict() for p in self.character_prompts]
        data["scene_prompts"] = [p.to_dict() for p in self.scene_prompts]
        return data

    def to_markdown(self) -> str:
        """Export as markdown for copy-pasting into Midjourney."""
        lines = [
            "# Midjourney Visual Prompts",
            "",
            f"**Story:** {self.title}",
            f"**Genre:** {self.genre}",
            "",
            "---",
            "",
            "## STEP 1: Generate Character References",
            "",
            "Generate these first. Save the image URLs for --cref in scene prompts.",
            ""
        ]

        for i, prompt in enumerate(self.character_prompts, 1):
            lines.extend([
                f"### Character {i}: {prompt.character_name or 'Unknown'}",
                "",
                "```",
                prompt.full_prompt,
                "```",
                "",
                f"*Notes: {prompt.notes}*",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## STEP 2: Generate Scene Images",
            "",
            "After generating character refs, add their URLs to --cref parameter.",
            ""
        ])

        for prompt in self.scene_prompts:
            lines.extend([
                f"### Scene {prompt.scene_number}",
                "",
                "```",
                prompt.full_prompt,
                "```",
                "",
                f"*Notes: {prompt.notes}*",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## Style Reference",
            "",
            f"Overall style: {self.style_reference}",
            "",
            f"Notes: {self.notes}",
        ])

        return "\n".join(lines)


class VisualPromptGenerator:
    """
    Generates Midjourney prompts for story visualization.

    Workflow:
    1. Generate character reference prompts first
    2. Generate scene prompts with --cref to maintain consistency
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

    def _get_style_preset(self, genre: str) -> Dict[str, Any]:
        """Get style preset for a genre."""
        return GENRE_STYLE_PRESETS.get(genre, GENRE_STYLE_PRESETS["thriller"])

    def _build_base_params(self, include_cref: bool = False, cref_url: str = None) -> str:
        """Build base Midjourney parameters."""
        params = [
            DEFAULT_MJ_PARAMS["aspect_ratio"],
            DEFAULT_MJ_PARAMS["version"],
        ]

        if include_cref and cref_url:
            params.extend([
                f"--cref {cref_url}",
                "--cw 100",  # High character weight for consistency
            ])

        return " ".join(params)

    def generate_character_prompt(
        self,
        character_name: str,
        character_info: Dict[str, Any],
        genre: str = "thriller",
    ) -> MidjourneyPrompt:
        """
        Generate a character reference prompt.

        This should be generated first, then the resulting image URL
        used as --cref for scene prompts.
        """
        style = self._get_style_preset(genre)

        # Build character description
        desc_parts = []
        if character_info.get("description"):
            desc_parts.append(character_info["description"])
        else:
            # Build from individual fields
            if character_info.get("age"):
                desc_parts.append(character_info["age"])
            if character_info.get("gender"):
                desc_parts.append(character_info["gender"])
            if character_info.get("hair"):
                desc_parts.append(f"with {character_info['hair']} hair")
            if character_info.get("clothing"):
                desc_parts.append(f"wearing {character_info['clothing']}")
            if character_info.get("distinctive_features"):
                desc_parts.append(character_info["distinctive_features"])

        character_desc = ", ".join(desc_parts)

        # Build prompt
        prompt_parts = [
            f"portrait of {character_desc}",
            "neutral expression",
            "facing camera",
            "clean background",
            f"{style['lighting']}",
            "photorealistic",
            "8k",
            "detailed",
        ]

        prompt_text = ", ".join(prompt_parts)
        params = self._build_base_params()

        return MidjourneyPrompt(
            prompt_type=PromptType.CHARACTER_REF,
            prompt_text=prompt_text,
            parameters=params,
            full_prompt=f"{prompt_text} {params}",
            character_name=character_name,
            notes=f"Generate this first. Save the image URL to use as --cref for scenes featuring {character_name}.",
        )

    def generate_scene_prompt(
        self,
        scene_number: int,
        visual_description: str,
        characters_present: List[str],
        character_refs: Dict[str, str],  # name -> cref URL
        genre: str = "thriller",
        mood: str = "",
        lighting: str = "",
        shot_type: str = "medium",
        location: str = "",
    ) -> MidjourneyPrompt:
        """
        Generate a scene prompt with character references.
        """
        style = self._get_style_preset(genre)

        # Build prompt
        prompt_parts = [visual_description]

        # Add shot type
        shot_mapping = {
            "wide": "wide shot, establishing shot",
            "medium": "medium shot",
            "close_up": "close-up shot, detailed",
            "extreme_close_up": "extreme close-up, macro",
            "over_shoulder": "over the shoulder shot",
            "pov": "first person POV, subjective camera",
            "establishing": "establishing shot, wide angle",
        }
        prompt_parts.append(shot_mapping.get(shot_type, "medium shot"))

        # Add location context
        if location:
            prompt_parts.append(location)

        # Add mood
        if mood:
            prompt_parts.append(f"{mood} atmosphere")

        # Add lighting
        if lighting:
            prompt_parts.append(lighting)
        else:
            prompt_parts.append(style["lighting"])

        # Add style
        prompt_parts.append(style["style"])

        # Add quality
        prompt_parts.extend(["cinematic", "8k", "photorealistic"])

        prompt_text = ", ".join(prompt_parts)

        # Build parameters with character references
        cref_urls = []
        for char_name in characters_present:
            if char_name in character_refs:
                cref_urls.append(character_refs[char_name])

        if cref_urls:
            # Can only use one --cref, use the first character
            params = self._build_base_params(include_cref=True, cref_url=cref_urls[0])
            notes = f"Using character reference for: {characters_present[0]}"
            if len(characters_present) > 1:
                notes += f" (Note: Midjourney --cref only supports one reference, {characters_present[1:]} may vary)"
        else:
            params = self._build_base_params()
            notes = "No character reference available. Generate character refs first."

        return MidjourneyPrompt(
            prompt_type=PromptType.SCENE,
            prompt_text=prompt_text,
            parameters=params,
            full_prompt=f"{prompt_text} {params}",
            scene_number=scene_number,
            notes=notes,
        )

    def generate_prompts(
        self,
        scenes: List[Dict[str, Any]],
        characters: Dict[str, Dict[str, Any]],
        genre: str = "thriller",
        title: str = "Untitled",
        story_id: str = "",
        character_refs: Dict[str, str] = None,  # Pre-existing refs
    ) -> VisualPromptSet:
        """
        Generate complete prompt set for a story.

        Args:
            scenes: List of scene dictionaries from scene planner
            characters: Character information
            genre: Story genre
            title: Story title
            story_id: Story ID for reference
            character_refs: Pre-existing character reference URLs

        Returns:
            VisualPromptSet with all prompts
        """
        character_refs = character_refs or {}
        style = self._get_style_preset(genre)

        # Generate character prompts
        character_prompts = []
        for name, info in characters.items():
            if name not in character_refs:
                prompt = self.generate_character_prompt(name, info, genre)
                character_prompts.append(prompt)

        # Generate scene prompts
        scene_prompts = []
        for scene in scenes:
            prompt = self.generate_scene_prompt(
                scene_number=scene.get("scene_number", len(scene_prompts) + 1),
                visual_description=scene.get("visual_description", ""),
                characters_present=scene.get("characters_present", []),
                character_refs=character_refs,
                genre=genre,
                mood=scene.get("mood", ""),
                lighting=scene.get("lighting", ""),
                shot_type=scene.get("shot_type", "medium"),
                location=scene.get("location", ""),
            )
            scene_prompts.append(prompt)

        return VisualPromptSet(
            story_id=story_id,
            title=title,
            genre=genre,
            character_prompts=character_prompts,
            scene_prompts=scene_prompts,
            style_reference=style["style"],
            notes=f"Color grade: {style['color_grade']}. Generate character refs first, then add URLs to scene prompts.",
        )

    def generate_prompts_with_ai(
        self,
        story_text: str,
        characters: Dict[str, Dict[str, Any]],
        genre: str = "thriller",
        scene_count: int = 10,
    ) -> VisualPromptSet:
        """
        Use AI to generate optimized Midjourney prompts.

        This uses Claude to craft better prompts than the template approach.
        """
        style = self._get_style_preset(genre)

        # Get character consistency params from style guide
        style_guide = self._load_style_guide()
        mj_params = style_guide.style_guide.get("character_consistency", {}).get("midjourney_params", {})

        prompt = f"""You are a Midjourney prompt expert creating prompts for a {genre} short story.

STORY:
{story_text}

CHARACTERS:
{json.dumps(characters, indent=2)}

GENRE STYLE:
- Visual style: {style['style']}
- Color grade: {style['color_grade']}
- Lighting: {style['lighting']}

MIDJOURNEY PARAMETERS TO USE:
- Aspect ratio: {mj_params.get('aspect_ratio', '--ar 9:16')}
- Version: {mj_params.get('version', '--v 6.1')}
- Character reference: {mj_params.get('character_reference', '--cref [URL]')}
- Character weight: {mj_params.get('character_weight', '--cw 100')}

YOUR TASK:
1. Create character reference prompts (for generating consistent character images)
2. Create {scene_count} scene prompts that tell the story visually
3. Each prompt should be optimized for Midjourney v6

PROMPT RULES:
- Be specific and descriptive
- Include lighting, mood, and camera angle
- Use Midjourney-friendly terms
- Keep prompts under 200 words
- Include all required parameters

Respond in JSON:
{{
    "character_prompts": [
        {{
            "character_name": "Name",
            "prompt": "Full Midjourney prompt including parameters",
            "notes": "What to do with the generated image"
        }}
    ],
    "scene_prompts": [
        {{
            "scene_number": 1,
            "prompt": "Full Midjourney prompt including parameters",
            "characters_in_scene": ["character names"],
            "notes": "Scene context"
        }}
    ],
    "style_notes": "Overall style guidance"
}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())

            # Build prompt objects
            character_prompts = []
            for cp in data.get("character_prompts", []):
                character_prompts.append(MidjourneyPrompt(
                    prompt_type=PromptType.CHARACTER_REF,
                    full_prompt=cp.get("prompt", ""),
                    character_name=cp.get("character_name", ""),
                    notes=cp.get("notes", ""),
                ))

            scene_prompts = []
            for sp in data.get("scene_prompts", []):
                scene_prompts.append(MidjourneyPrompt(
                    prompt_type=PromptType.SCENE,
                    full_prompt=sp.get("prompt", ""),
                    scene_number=sp.get("scene_number", len(scene_prompts) + 1),
                    notes=sp.get("notes", ""),
                ))

            return VisualPromptSet(
                genre=genre,
                character_prompts=character_prompts,
                scene_prompts=scene_prompts,
                style_reference=style["style"],
                notes=data.get("style_notes", ""),
            )

        except Exception as e:
            print(f"Error generating AI prompts: {e}")
            raise


def format_prompts_for_clipboard(prompt_set: VisualPromptSet) -> str:
    """Format all prompts for easy copy-pasting."""
    lines = ["=== CHARACTER REFERENCE PROMPTS ===", ""]

    for p in prompt_set.character_prompts:
        lines.append(f"# {p.character_name}")
        lines.append(p.full_prompt)
        lines.append("")

    lines.extend(["", "=== SCENE PROMPTS ===", ""])

    for p in prompt_set.scene_prompts:
        lines.append(f"# Scene {p.scene_number}")
        lines.append(p.full_prompt)
        lines.append("")

    return "\n".join(lines)


# CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Visual Prompt Generator")
        print("=" * 50)
        print("\nCommands:")
        print("  python story_visual_gen.py generate <story_file> --genre thriller")
        print("  python story_visual_gen.py character <name> '<description>'")
        print("  python story_visual_gen.py styles")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "generate":
        if len(sys.argv) < 3:
            print("Usage: python story_visual_gen.py generate <story_file> [--genre thriller]")
            sys.exit(1)

        story_file = Path(sys.argv[2])
        genre = "thriller"

        if "--genre" in sys.argv:
            idx = sys.argv.index("--genre")
            if idx + 1 < len(sys.argv):
                genre = sys.argv[idx + 1]

        # Load story
        with open(story_file) as f:
            data = json.load(f)
            story_text = data.get("full_story", "")
            characters = data.get("characters", {})

        print(f"Generating Midjourney prompts for {genre} story...")
        generator = VisualPromptGenerator()
        prompts = generator.generate_prompts_with_ai(
            story_text=story_text,
            characters=characters,
            genre=genre,
        )

        print(prompts.to_markdown())

    elif cmd == "character":
        if len(sys.argv) < 4:
            print("Usage: python story_visual_gen.py character <name> '<description>'")
            sys.exit(1)

        name = sys.argv[2]
        description = sys.argv[3]

        generator = VisualPromptGenerator()
        prompt = generator.generate_character_prompt(
            character_name=name,
            character_info={"description": description},
            genre="thriller",
        )

        print(f"\n{name} Character Reference Prompt:")
        print("-" * 50)
        print(prompt.full_prompt)

    elif cmd == "styles":
        print("Genre Style Presets:")
        print("-" * 50)
        for genre, style in GENRE_STYLE_PRESETS.items():
            print(f"\n{genre.upper()}:")
            print(f"  Style: {style['style']}")
            print(f"  Color: {style['color_grade']}")
            print(f"  Lighting: {style['lighting']}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
