"""
Story Scene Planner

Creates 8-12 scenes from story content with:
- Character tracking per scene
- Variable duration based on narrative beats
- Shot types, camera movement, transitions
- Visual direction for each scene

Maps to the "Scene Planner" agent in the 5-agent orchestration.

Usage:
    from generators.story_scene_planner import ScenePlanner, ScenePlan

    planner = ScenePlanner()
    plan = planner.plan_scenes(
        story_output=story,
        voice_script=voice_script,
        target_scenes=10
    )
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
from pathlib import Path

from config.settings import STORY_SCENES_TARGET
from training.niche_config import NicheConfig


class ShotType(Enum):
    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"
    OVER_SHOULDER = "over_shoulder"
    POV = "pov"
    ESTABLISHING = "establishing"


class CameraMovement(Enum):
    STATIC = "static"
    SLOW_PUSH_IN = "slow_push_in"
    PULL_BACK = "pull_back"
    PAN = "pan"
    TILT = "tilt"
    HANDHELD = "handheld"
    TRACKING = "tracking"


class Transition(Enum):
    CUT = "cut"
    FADE_TO_BLACK = "fade_to_black"
    DISSOLVE = "dissolve"
    MATCH_CUT = "match_cut"
    QUICK_CUT = "quick_cut"
    SLOW_FADE = "slow_fade"


@dataclass
class Scene:
    """A single scene in the story."""
    scene_number: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    narration_text: str = ""
    visual_description: str = ""
    shot_type: ShotType = ShotType.MEDIUM
    camera_movement: CameraMovement = CameraMovement.STATIC
    transition_in: Transition = Transition.CUT
    transition_out: Transition = Transition.CUT
    characters_present: List[str] = field(default_factory=list)
    location: str = ""
    mood: str = ""
    lighting: str = ""
    key_action: str = ""
    on_screen_text: str = ""
    sound_design: str = ""
    music_cue: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["shot_type"] = self.shot_type.value
        data["camera_movement"] = self.camera_movement.value
        data["transition_in"] = self.transition_in.value
        data["transition_out"] = self.transition_out.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Scene":
        data = data.copy()
        if "shot_type" in data:
            data["shot_type"] = ShotType(data["shot_type"])
        if "camera_movement" in data:
            data["camera_movement"] = CameraMovement(data["camera_movement"])
        if "transition_in" in data:
            data["transition_in"] = Transition(data["transition_in"])
        if "transition_out" in data:
            data["transition_out"] = Transition(data["transition_out"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ScenePlan:
    """Complete scene plan for a story."""
    story_id: str = ""
    title: str = ""
    total_duration: float = 0.0
    scene_count: int = 0
    scenes: List[Scene] = field(default_factory=list)
    characters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    locations: List[str] = field(default_factory=list)
    overall_visual_style: str = ""
    color_palette: List[str] = field(default_factory=list)
    music_direction: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["scenes"] = [s.to_dict() if isinstance(s, Scene) else s for s in self.scenes]
        return data

    def to_markdown(self) -> str:
        """Export as markdown for human review."""
        lines = [
            "# Scene Plan",
            "",
            f"**Story:** {self.title}",
            f"**Duration:** {self.total_duration:.1f}s",
            f"**Scenes:** {self.scene_count}",
            "",
            f"**Visual Style:** {self.overall_visual_style}",
            f"**Color Palette:** {', '.join(self.color_palette)}",
            f"**Music:** {self.music_direction}",
            "",
            "---",
            "",
            "## Characters",
            ""
        ]

        for name, info in self.characters.items():
            lines.append(f"### {name}")
            if isinstance(info, dict):
                lines.append(f"- Description: {info.get('description', 'N/A')}")
                lines.append(f"- Appears in scenes: {info.get('scenes', [])}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## Scene Breakdown",
            ""
        ])

        for scene in self.scenes:
            s = scene if isinstance(scene, Scene) else Scene.from_dict(scene)
            lines.extend([
                f"### Scene {s.scene_number}",
                f"**Time:** {s.start_time:.1f}s - {s.end_time:.1f}s ({s.duration:.1f}s)",
                f"**Location:** {s.location}",
                f"**Characters:** {', '.join(s.characters_present) if s.characters_present else 'None'}",
                "",
                f"**Narration:**",
                f"> {s.narration_text}",
                "",
                f"**Visual Description:**",
                f"{s.visual_description}",
                "",
                f"| Shot | Camera | Transition |",
                f"|------|--------|------------|",
                f"| {s.shot_type.value if isinstance(s.shot_type, ShotType) else s.shot_type} | {s.camera_movement.value if isinstance(s.camera_movement, CameraMovement) else s.camera_movement} | {s.transition_out.value if isinstance(s.transition_out, Transition) else s.transition_out} |",
                "",
                f"**Mood:** {s.mood}",
                f"**Lighting:** {s.lighting}",
                f"**Key Action:** {s.key_action}",
                "",
                "---",
                ""
            ])

        return "\n".join(lines)


class ScenePlanner:
    """
    Plans visual scenes from story and voice script content.

    Creates detailed scene breakdowns with:
    - Character tracking
    - Shot types and camera movement
    - Transitions
    - Visual direction
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

    def plan_scenes(
        self,
        story_text: str,
        characters: Dict[str, Dict[str, Any]] = None,
        genre: str = "thriller",
        mood: str = "",
        total_duration: float = 60.0,
        target_scenes: int = None,
        voice_script_sections: List[Dict] = None,
    ) -> ScenePlan:
        """
        Plan scenes for a story.

        Args:
            story_text: The full story text
            characters: Character information from story generation
            genre: Story genre for visual style
            mood: Overall mood
            total_duration: Target duration in seconds
            target_scenes: Number of scenes to create (default from settings)
            voice_script_sections: Sections from voice script generator

        Returns:
            ScenePlan with all scenes
        """
        target_scenes = target_scenes or STORY_SCENES_TARGET

        # Load style guide for visual references
        style_guide = self._load_style_guide()
        visual_style = style_guide.style_guide.get("visual_style", {})
        genres = style_guide.style_guide.get("genres", {})
        genre_info = genres.get(genre, {})

        # Build character context
        char_context = ""
        if characters:
            char_lines = []
            for name, info in characters.items():
                if isinstance(info, dict):
                    char_lines.append(f"- {name}: {info.get('description', 'No description')}")
            char_context = "\n".join(char_lines)

        prompt = f"""You are a visual director creating a scene breakdown for a short-form video story.

STORY:
{story_text}

GENRE: {genre}
MOOD: {mood or "match the story"}
TARGET DURATION: {total_duration} seconds
TARGET SCENES: {target_scenes} scenes

CHARACTERS:
{char_context or "(extract from story)"}

VISUAL STYLE GUIDANCE:
- Genre visual style: {genre_info.get('visual_style', 'cinematic')}
- Shot types to use: {', '.join(visual_style.get('shot_types', ['wide', 'medium', 'close-up']))}
- Transitions: {', '.join(visual_style.get('transitions', ['cut', 'fade']))}
- Camera movements: {', '.join(visual_style.get('camera_movements', ['static', 'slow_push_in']))}

SCENE PLANNING RULES:
1. Create {target_scenes} scenes with variable duration based on narrative beats
2. Hook scenes should be shorter (3-5s), tension scenes longer (5-8s)
3. Track which characters appear in each scene
4. Use appropriate shot types for the emotion (close-up for intense moments)
5. Plan camera movements to build tension or reveal information
6. Choose transitions that match the pacing (quick cuts for action, fades for mood)
7. Include on-screen text for key phrases
8. Plan sound design cues for each scene

Respond in JSON:
{{
    "title": "Story title",
    "total_duration": {total_duration},
    "scene_count": {target_scenes},
    "overall_visual_style": "e.g., dark noir with high contrast",
    "color_palette": ["#1a1a1a", "#ff4444", "#ffffff"],
    "music_direction": "Overall music style guidance",
    "characters": {{
        "character_name": {{
            "description": "Visual description",
            "scenes": [1, 3, 5]
        }}
    }},
    "locations": ["Location 1", "Location 2"],
    "scenes": [
        {{
            "scene_number": 1,
            "start_time": 0.0,
            "end_time": 5.0,
            "duration": 5.0,
            "narration_text": "The exact narration for this scene",
            "visual_description": "Detailed visual description for image generation",
            "shot_type": "wide|medium|close_up|extreme_close_up|over_shoulder|pov|establishing",
            "camera_movement": "static|slow_push_in|pull_back|pan|tilt|handheld|tracking",
            "transition_in": "cut|fade_to_black|dissolve|match_cut|quick_cut",
            "transition_out": "cut|fade_to_black|dissolve|match_cut|quick_cut",
            "characters_present": ["character names"],
            "location": "Where this takes place",
            "mood": "tense|calm|eerie|hopeful|etc",
            "lighting": "e.g., dim ambient, harsh shadows",
            "key_action": "Main action in this scene",
            "on_screen_text": "Text to display (if any)",
            "sound_design": "Ambient sounds, sfx cues",
            "music_cue": "Music mood for this scene"
        }}
    ]
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

            # Build scenes
            scenes = []
            for scene_data in data.get("scenes", []):
                scene = Scene(
                    scene_number=scene_data.get("scene_number", len(scenes) + 1),
                    start_time=scene_data.get("start_time", 0.0),
                    end_time=scene_data.get("end_time", 0.0),
                    duration=scene_data.get("duration", 5.0),
                    narration_text=scene_data.get("narration_text", ""),
                    visual_description=scene_data.get("visual_description", ""),
                    shot_type=ShotType(scene_data.get("shot_type", "medium")),
                    camera_movement=CameraMovement(scene_data.get("camera_movement", "static")),
                    transition_in=Transition(scene_data.get("transition_in", "cut")),
                    transition_out=Transition(scene_data.get("transition_out", "cut")),
                    characters_present=scene_data.get("characters_present", []),
                    location=scene_data.get("location", ""),
                    mood=scene_data.get("mood", ""),
                    lighting=scene_data.get("lighting", ""),
                    key_action=scene_data.get("key_action", ""),
                    on_screen_text=scene_data.get("on_screen_text", ""),
                    sound_design=scene_data.get("sound_design", ""),
                    music_cue=scene_data.get("music_cue", ""),
                )
                scenes.append(scene)

            return ScenePlan(
                title=data.get("title", "Untitled"),
                total_duration=data.get("total_duration", total_duration),
                scene_count=len(scenes),
                scenes=scenes,
                characters=data.get("characters", {}),
                locations=data.get("locations", []),
                overall_visual_style=data.get("overall_visual_style", ""),
                color_palette=data.get("color_palette", []),
                music_direction=data.get("music_direction", ""),
            )

        except Exception as e:
            print(f"Error planning scenes: {e}")
            raise

    def adjust_scene_timing(
        self,
        scene_plan: ScenePlan,
        word_timing: List[Dict[str, Any]],
    ) -> ScenePlan:
        """
        Adjust scene timing based on actual word-level timing from TTS.

        Args:
            scene_plan: The initial scene plan
            word_timing: Word timing data from voice generation

        Returns:
            ScenePlan with adjusted timing
        """
        if not word_timing:
            return scene_plan

        # Build a mapping of narration text to timing
        # This is a simplified approach - production would need more sophisticated matching

        for scene in scene_plan.scenes:
            # Find words that match this scene's narration
            narration_words = scene.narration_text.lower().split()
            if not narration_words:
                continue

            # Find the first and last word timing
            first_word = narration_words[0]
            last_word = narration_words[-1]

            start_time = None
            end_time = None

            for wt in word_timing:
                word = wt.get("word", "").lower().strip(".,!?")
                if word == first_word and start_time is None:
                    start_time = wt.get("start", 0.0)
                if word == last_word:
                    end_time = wt.get("end", 0.0)

            if start_time is not None:
                scene.start_time = start_time
            if end_time is not None:
                scene.end_time = end_time
                scene.duration = end_time - scene.start_time

        return scene_plan

    def get_character_appearances(self, scene_plan: ScenePlan) -> Dict[str, List[int]]:
        """Get a summary of which scenes each character appears in."""
        appearances = {}
        for scene in scene_plan.scenes:
            s = scene if isinstance(scene, Scene) else Scene.from_dict(scene)
            for char in s.characters_present:
                if char not in appearances:
                    appearances[char] = []
                appearances[char].append(s.scene_number)
        return appearances


# CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Scene Planner")
        print("=" * 50)
        print("\nCommands:")
        print("  python story_scene_planner.py plan <story_file> --genre thriller")
        print("  python story_scene_planner.py shot-types")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "plan":
        if len(sys.argv) < 3:
            print("Usage: python story_scene_planner.py plan <story_file> [--genre thriller]")
            sys.exit(1)

        story_file = Path(sys.argv[2])
        genre = "thriller"
        target_scenes = STORY_SCENES_TARGET

        if "--genre" in sys.argv:
            idx = sys.argv.index("--genre")
            if idx + 1 < len(sys.argv):
                genre = sys.argv[idx + 1]

        if "--scenes" in sys.argv:
            idx = sys.argv.index("--scenes")
            if idx + 1 < len(sys.argv):
                target_scenes = int(sys.argv[idx + 1])

        # Load story
        if story_file.suffix == ".json":
            with open(story_file) as f:
                data = json.load(f)
                story_text = data.get("full_story", "")
                characters = data.get("characters", {})
                mood = data.get("mood", "")
        else:
            with open(story_file) as f:
                story_text = f.read()
                characters = {}
                mood = ""

        print(f"Planning {target_scenes} scenes for {genre} story...")
        planner = ScenePlanner()
        plan = planner.plan_scenes(
            story_text=story_text,
            characters=characters,
            genre=genre,
            mood=mood,
            target_scenes=target_scenes,
        )

        print(plan.to_markdown())

    elif cmd == "shot-types":
        print("Available Shot Types:")
        for st in ShotType:
            print(f"  - {st.value}")

        print("\nCamera Movements:")
        for cm in CameraMovement:
            print(f"  - {cm.value}")

        print("\nTransitions:")
        for tr in Transition:
            print(f"  - {tr.value}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
