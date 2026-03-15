"""
NanoBanana Prompt Generator.

Generates detailed, structured visual prompts based on beat type,
voiceover content, and scene context. Ensures prompts are:
- Specific and reproducible
- Minimum 90-160 words (for ULTRA detail level)
- Include all required visual fields
- Reference continuity entities when applicable

Visual Strategy System:
- 'people': Human figures as subjects (traditional approach)
- 'environment': Abstract landscapes, metaphors, objects - NO PEOPLE
- 'auto': Chooses based on niche and script cues
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum
import re
import random

from content_engine.pipeline.prompt_spec import (
    ScenePromptSpec,
    CameraSpec,
    SubjectSpec,
    EnvironmentSpec,
    LightingSpec,
    ColorStyleSpec,
    ContinuitySpec,
    NegativeConstraints,
    OutputFormatSpec,
    ShotType,
    CameraAngle,
    CameraMovement,
    TimeOfDay,
    LightingStyle,
    PromptDetailLevel,
)


class VisualStrategy(str, Enum):
    """Visual strategy for prompt generation."""
    PEOPLE = "people"           # Human figures as subjects
    ENVIRONMENT = "environment" # Abstract/metaphor visuals, NO people
    AUTO = "auto"               # Choose based on niche and script cues


# Niche to default visual strategy mapping
NICHE_VISUAL_DEFAULTS = {
    "motivation": VisualStrategy.ENVIRONMENT,
    "stoicism": VisualStrategy.ENVIRONMENT,
    "stoic": VisualStrategy.ENVIRONMENT,
    "mindset": VisualStrategy.ENVIRONMENT,
    "philosophy": VisualStrategy.ENVIRONMENT,
    "fun_facts": VisualStrategy.ENVIRONMENT,
    "facts": VisualStrategy.ENVIRONMENT,
    "edgy_funny": VisualStrategy.ENVIRONMENT,
    # Niches that typically need people
    "fitness": VisualStrategy.PEOPLE,
    "beauty": VisualStrategy.PEOPLE,
    "lifestyle": VisualStrategy.PEOPLE,
    "fashion": VisualStrategy.PEOPLE,
}


# Minimum word counts by detail level
MIN_WORD_COUNTS = {
    PromptDetailLevel.SHORT: 40,
    PromptDetailLevel.NORMAL: 70,
    PromptDetailLevel.ULTRA: 90,
}

MAX_WORD_COUNTS = {
    PromptDetailLevel.SHORT: 60,
    PromptDetailLevel.NORMAL: 100,
    PromptDetailLevel.ULTRA: 180,
}


@dataclass
class BeatVisualProfile:
    """Visual profile for a beat type based on dopamine framework."""
    shot_types: list[ShotType]
    angles: list[CameraAngle]
    movements: list[CameraMovement]
    lighting_styles: list[LightingStyle]
    contrast_level: str
    energy: str  # "low", "medium", "high"
    suggested_subjects: list[str]  # Person-based subjects
    environment_moods: list[str]
    # Environment/metaphor subjects (no people)
    environment_subjects: list[str] = None

    def __post_init__(self):
        if self.environment_subjects is None:
            self.environment_subjects = []


# Dopamine-framework aligned beat profiles
BEAT_PROFILES = {
    "HOOK": BeatVisualProfile(
        shot_types=[ShotType.MEDIUM_CLOSE, ShotType.CLOSE_UP, ShotType.MEDIUM],
        angles=[CameraAngle.EYE_LEVEL, CameraAngle.LOW_ANGLE],
        movements=[CameraMovement.SLOW_PUSH, CameraMovement.STATIC],
        lighting_styles=[LightingStyle.DRAMATIC, LightingStyle.RIM_LIT, LightingStyle.HIGH_KEY],
        contrast_level="high",
        energy="high",
        suggested_subjects=["person with direct gaze", "figure emerging from shadow", "hands in motion"],
        environment_moods=["striking", "attention-grabbing", "contrasting"],
        environment_subjects=[
            "bold geometric symbol emerging from darkness",
            "single flame against void",
            "cracked mirror reflecting light",
            "lightning bolt frozen in time",
            "ancient key floating in beam of light",
            "hourglass with golden sand suspended",
        ],
    ),
    "TENSION": BeatVisualProfile(
        shot_types=[ShotType.MEDIUM, ShotType.MEDIUM_WIDE, ShotType.CLOSE_UP],
        angles=[CameraAngle.EYE_LEVEL, CameraAngle.HIGH_ANGLE],
        movements=[CameraMovement.STATIC, CameraMovement.SLOW_PUSH],
        lighting_styles=[LightingStyle.LOW_KEY, LightingStyle.DRAMATIC, LightingStyle.SILHOUETTE],
        contrast_level="high",
        energy="medium",
        suggested_subjects=["contemplative figure", "person in thought", "silhouette"],
        environment_moods=["moody", "uncertain", "weighted"],
        environment_subjects=[
            "tangled chains in shadows",
            "cluttered desk with scattered papers",
            "storm clouds gathering over barren landscape",
            "maze viewed from above",
            "thorny branches against gray sky",
            "weight pressing down on cracked surface",
        ],
    ),
    "SHIFT": BeatVisualProfile(
        shot_types=[ShotType.MEDIUM, ShotType.WIDE, ShotType.MEDIUM_WIDE],
        angles=[CameraAngle.LOW_ANGLE, CameraAngle.EYE_LEVEL],
        movements=[CameraMovement.SLOW_PUSH, CameraMovement.DRIFT],
        lighting_styles=[LightingStyle.NATURAL_SOFT, LightingStyle.HIGH_KEY, LightingStyle.RIM_LIT],
        contrast_level="medium",
        energy="medium",
        suggested_subjects=["person turning", "figure looking up", "moment of realization"],
        environment_moods=["transitional", "hopeful", "awakening"],
        environment_subjects=[
            "first rays of dawn breaking through clouds",
            "door opening to reveal light",
            "butterfly emerging from chrysalis",
            "fog lifting from mountain valley",
            "compass needle settling on direction",
            "seed sprouting through concrete",
        ],
    ),
    "CLIMB": BeatVisualProfile(
        shot_types=[ShotType.MEDIUM, ShotType.MEDIUM_CLOSE, ShotType.WIDE],
        angles=[CameraAngle.LOW_ANGLE, CameraAngle.EYE_LEVEL],
        movements=[CameraMovement.SLOW_PUSH, CameraMovement.CRANE],
        lighting_styles=[LightingStyle.HIGH_KEY, LightingStyle.NATURAL_SOFT, LightingStyle.RIM_LIT],
        contrast_level="medium",
        energy="high",
        suggested_subjects=["person in motion", "determined stance", "forward movement"],
        environment_moods=["ascending", "building", "energetic"],
        environment_subjects=[
            "staircase ascending toward golden light",
            "mountain path winding upward",
            "phoenix rising from embers",
            "arrow soaring toward target",
            "tree growing through obstacles",
            "bridge spanning a chasm",
        ],
    ),
    "RESOLUTION": BeatVisualProfile(
        shot_types=[ShotType.CLOSE_UP, ShotType.MEDIUM_CLOSE, ShotType.MEDIUM],
        angles=[CameraAngle.EYE_LEVEL, CameraAngle.LOW_ANGLE],
        movements=[CameraMovement.STATIC, CameraMovement.SLOW_PULL],
        lighting_styles=[LightingStyle.HIGH_KEY, LightingStyle.NATURAL_SOFT],
        contrast_level="low",
        energy="medium",
        suggested_subjects=["peaceful expression", "satisfied moment", "achievement"],
        environment_moods=["resolved", "warm", "accomplished"],
        environment_subjects=[
            "sunset over calm ocean",
            "trophy gleaming in soft light",
            "completed puzzle on wooden table",
            "open book with golden pages",
            "balanced stones in zen garden",
            "crown resting on velvet cushion",
        ],
    ),
    "CTA": BeatVisualProfile(
        shot_types=[ShotType.MEDIUM, ShotType.MEDIUM_CLOSE],
        angles=[CameraAngle.EYE_LEVEL, CameraAngle.LOW_ANGLE],
        movements=[CameraMovement.SLOW_PUSH, CameraMovement.STATIC],
        lighting_styles=[LightingStyle.HIGH_KEY, LightingStyle.RIM_LIT],
        contrast_level="medium",
        energy="high",
        suggested_subjects=["direct engagement", "inviting gesture", "open posture"],
        environment_moods=["inviting", "energetic", "call-to-action"],
        environment_subjects=[
            "open door leading to bright future",
            "path diverging with one illuminated",
            "notification bell with golden glow",
            "subscribe button pulsing with energy",
            "hand reaching toward glowing orb",
            "rising sun over new horizon",
        ],
    ),
}


class NanoBananaPromptGenerator:
    """
    Generates detailed NanoBanana prompts from scene context.

    Uses beat-type profiles aligned with the dopamine framework
    to create visually compelling, specific prompts.

    Visual Strategy System:
    - PEOPLE: Traditional human figures as subjects
    - ENVIRONMENT: Abstract landscapes, metaphors, objects - NO PEOPLE
    - AUTO: Chooses based on niche (motivation defaults to ENVIRONMENT)
    """

    def __init__(
        self,
        detail_level: PromptDetailLevel = PromptDetailLevel.ULTRA,
        visual_preset: Optional[dict] = None,
        entities: Optional[list[dict]] = None,
        visual_strategy: VisualStrategy = VisualStrategy.AUTO,
        niche: Optional[str] = None,
    ):
        """
        Initialize the generator.

        Args:
            detail_level: Level of detail for prompts
            visual_preset: Visual mode preset configuration
            entities: List of continuity entities for reference
            visual_strategy: Visual strategy (PEOPLE, ENVIRONMENT, AUTO)
            niche: Content niche (used for AUTO strategy selection)
        """
        self.detail_level = detail_level
        self.visual_preset = visual_preset or {}
        self.entities = entities or []
        self._entity_map = {e.get("name", ""): e for e in self.entities if e.get("name")}
        self.niche = niche or ""

        # Resolve visual strategy
        if visual_strategy == VisualStrategy.AUTO:
            # Check niche-based defaults
            niche_lower = self.niche.lower() if self.niche else ""
            self.visual_strategy = NICHE_VISUAL_DEFAULTS.get(
                niche_lower, VisualStrategy.ENVIRONMENT  # Default to environment for unknown niches
            )
        else:
            self.visual_strategy = visual_strategy

    def generate_scene_spec(
        self,
        scene_number: int,
        beat_type: str,
        voiceover_segment: str,
        prior_scene_spec: Optional[ScenePromptSpec] = None,
        overlay_text: Optional[str] = None,
        custom_guidance: Optional[str] = None,
        visual_description: Optional[str] = None,
    ) -> ScenePromptSpec:
        """
        Generate a complete ScenePromptSpec for a scene.

        Args:
            scene_number: Scene number (1-6 typically)
            beat_type: Beat type (HOOK, TENSION, SHIFT, CLIMB, RESOLUTION, CTA)
            voiceover_segment: The voiceover text for this scene
            prior_scene_spec: Previous scene's spec for continuity
            overlay_text: Text overlay if any
            custom_guidance: Additional generation guidance
            visual_description: Claude-written visual concept from shot list.
                When provided, used as the subject instead of random beat picks.

        Returns:
            Complete ScenePromptSpec with all visual details
        """
        profile = BEAT_PROFILES.get(beat_type, BEAT_PROFILES["TENSION"])

        # Analyze voiceover + visual_description for visual cues (LLM, with keyword fallback)
        visual_cues = self._extract_visual_cues(voiceover_segment, visual_description or "")

        # Generate each specification component
        camera = self._generate_camera_spec(profile, visual_cues, scene_number)
        subject = self._generate_subject_spec(profile, visual_cues, prior_scene_spec, visual_description)
        environment = self._generate_environment_spec(profile, visual_cues, prior_scene_spec)
        lighting = self._generate_lighting_spec(profile, visual_cues)
        color_style = self._generate_color_style_spec(profile, visual_cues)
        continuity = self._generate_continuity_spec(prior_scene_spec, visual_cues)
        negatives = self._generate_negatives(custom_guidance)
        output_format = self._generate_output_format()

        spec = ScenePromptSpec(
            scene_number=scene_number,
            beat_type=beat_type,
            voiceover_segment=voiceover_segment,
            camera=camera,
            subject=subject,
            environment=environment,
            lighting=lighting,
            color_style=color_style,
            continuity=continuity,
            negatives=negatives,
            output_format=output_format,
            overlay_text=overlay_text,
            detail_level=self.detail_level,
        )

        # Ensure minimum word count
        self._ensure_minimum_words(spec)

        return spec

    def _extract_visual_cues(self, voiceover: str, visual_description: str = "") -> dict:
        """
        Extract visual cues from voiceover + visual_description.

        Tries a Claude CLI call first for accurate environment analysis.
        Falls back to the keyword scanner if the CLI is unavailable or times out.
        """
        llm_cues = self._extract_visual_cues_llm(voiceover, visual_description)
        if llm_cues:
            return llm_cues
        return self._extract_visual_cues_keyword(voiceover, visual_description)

    def _extract_visual_cues_llm(self, voiceover: str, visual_description: str) -> dict:
        """
        Ask Claude CLI to extract environment context as JSON.

        Returns a merged cues dict on success, empty dict on any failure.
        """
        import subprocess, json as _json, os

        prompt = (
            "You are a cinematography assistant. Analyze this short video scene and return ONLY a JSON object — "
            "no explanation, no markdown, no code fences.\n\n"
            f'Voiceover: "{voiceover}"\n'
            f'Visual concept: "{visual_description}"\n\n'
            "Return exactly this JSON structure:\n"
            '{\n'
            '  "emotional_tone": "positive|challenging|reflective|neutral",\n'
            '  "environment_type": "interior|exterior|nature|urban|abstract|cosmic",\n'
            '  "time_of_day": "golden_hour|night|midday|morning|overcast|unspecified",\n'
            '  "key_visual_elements": ["element1", "element2"],\n'
            '  "avoid": ["contradiction1", "contradiction2"]\n'
            '}'
        )

        # Skip when running inside a Claude Code session to avoid process hangs
        if os.environ.get("CLAUDECODE"):
            return {}

        try:
            env = os.environ.copy()
            env.pop("CLAUDECODE", None)
            proc = subprocess.Popen(
                ["claude", "-p", prompt],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, preexec_fn=os.setsid,
            )
            try:
                raw_bytes, _ = proc.communicate(timeout=20)
                raw = raw_bytes.decode("utf-8", errors="replace").strip()
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()
                return {}

            if not raw:
                return {}

            # Strip markdown fences if Claude wrapped it
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            data = _json.loads(raw)

            # Map LLM output to the cues dict shape the rest of the code expects
            env_type = data.get("environment_type", "interior")
            tod = data.get("time_of_day", "unspecified")

            env_hint_map = {
                "interior": "indoor",
                "exterior": "outdoor",
                "nature": "natural",
                "urban": "urban",
                "abstract": "abstract",
                "cosmic": "abstract",
            }
            time_hint_map = {
                "golden_hour": "evening",
                "morning": "morning",
                "night": "night",
                "midday": "midday",
                "overcast": "overcast",
                "unspecified": "",
            }

            return {
                "emotional_tone": data.get("emotional_tone", "neutral"),
                "subject_references": [],
                "action_keywords": [],
                "environment_hints": [env_hint_map.get(env_type, "indoor")],
                "time_hints": [t for t in [time_hint_map.get(tod, "")] if t],
                # LLM-only extras consumed by _generate_environment_spec
                "llm_environment_type": env_type,
                "llm_time_of_day": tod,
                "llm_key_elements": data.get("key_visual_elements", []),
                "llm_avoid": data.get("avoid", []),
            }

        except (FileNotFoundError, ValueError, KeyError, _json.JSONDecodeError, OSError):
            return {}

    def _extract_visual_cues_keyword(self, voiceover: str, visual_description: str = "") -> dict:
        """Keyword-scanner fallback when LLM extraction is unavailable.

        Scans both voiceover and visual_description for environment/time cues.
        visual_description is given higher weight since it was written specifically
        for the visual context of the scene.
        """
        cues = {
            "emotional_tone": "neutral",
            "subject_references": [],
            "action_keywords": [],
            "environment_hints": [],
            "time_hints": [],
            # LLM-shaped keys populated from keyword scan of visual_description
            "llm_environment_type": "",
            "llm_time_of_day": "",
            "llm_key_elements": [],
            "llm_avoid": [],
        }

        vd_lower = visual_description.lower()
        vo_lower = voiceover.lower()
        combined = vd_lower + " " + vo_lower

        # ── Emotional tone ────────────────────────────────────────────────────
        positive_words = ["good", "great", "happy", "success", "proud", "strong", "won", "achieved",
                          "sunlight", "clarity", "parting", "hope", "warm", "light"]
        negative_words = ["hard", "struggle", "difficult", "pain", "tired", "heavy", "failed",
                          "rain", "dark", "weight", "shadow"]
        reflective_words = ["remember", "think", "realize", "understand", "know", "feel",
                            "contemplat", "floating", "empty", "space"]

        if any(w in combined for w in positive_words):
            cues["emotional_tone"] = "positive"
        elif any(w in combined for w in negative_words):
            cues["emotional_tone"] = "challenging"
        elif any(w in combined for w in reflective_words):
            cues["emotional_tone"] = "reflective"

        # ── Subject references ────────────────────────────────────────────────
        if "you" in vo_lower:
            cues["subject_references"].append("viewer-surrogate")
        if any(w in combined for w in ["person", "people", "someone", "anyone", "figure"]):
            cues["subject_references"].append("person")

        # ── Action keywords ───────────────────────────────────────────────────
        action_patterns = [
            ("walking", "walking"), ("running", "running"), ("standing", "standing"),
            ("sitting", "seated"), ("looking", "gazing"), ("thinking", "contemplating"),
            ("working", "working"), ("moving", "in motion"),
        ]
        for pattern, action in action_patterns:
            if pattern in combined:
                cues["action_keywords"].append(action)

        # ── Environment type (visual_description first, voiceover as fallback) ─
        # Map keyword patterns to LLM-style environment_type values
        env_type = ""
        if any(w in vd_lower for w in ["window", "room", "wall", "ceiling", "interior", "indoor", "inside", "home", "office"]):
            env_type = "interior"
        elif any(w in vd_lower for w in ["city", "street", "urban", "building", "skyscraper", "traffic"]):
            env_type = "urban"
        elif any(w in vd_lower for w in ["cloud", "sky", "field", "forest", "mountain", "ocean", "nature", "landscape", "outdoor"]):
            env_type = "nature" if any(w in vd_lower for w in ["forest", "mountain", "ocean", "field", "nature"]) else "exterior"
        elif any(w in vd_lower for w in ["cosmos", "stars", "galaxy", "space", "infinite", "universe"]):
            env_type = "cosmic"
        elif any(w in vd_lower for w in ["abstract", "geometry", "pattern", "void"]):
            env_type = "abstract"

        # Fallback to voiceover if visual_description gave nothing
        if not env_type:
            if any(w in vo_lower for w in ["city", "street"]):
                env_type = "urban"
            elif any(w in vo_lower for w in ["nature", "forest", "mountain"]):
                env_type = "nature"
            elif any(w in vo_lower for w in ["office", "home", "room"]):
                env_type = "interior"

        if env_type:
            cues["llm_environment_type"] = env_type
            indoor_map = {"interior": "indoor", "urban": "outdoor", "nature": "outdoor",
                          "exterior": "outdoor", "cosmic": "abstract", "abstract": "abstract"}
            cues["environment_hints"].append(indoor_map.get(env_type, "indoor"))

        # ── Time of day (visual_description first) ────────────────────────────
        tod = ""
        if any(w in vd_lower for w in ["golden hour", "golden light", "warm light", "sunset", "sunrise"]):
            tod = "golden_hour"
        elif any(w in vd_lower for w in ["night", "dark", "city lights", "neon", "midnight"]):
            tod = "night"
        elif any(w in vd_lower for w in ["morning", "dawn", "early"]):
            tod = "morning"
        elif any(w in vd_lower for w in ["overcast", "grey", "gray", "cloudy", "rain"]):
            tod = "overcast"
        elif any(w in vd_lower for w in ["dusk", "twilight"]):
            tod = "dusk"
        elif any(w in vd_lower for w in ["midday", "noon", "bright", "sun"]):
            tod = "midday"
        elif any(w in vd_lower for w in ["cloud", "clarity", "parting"]):
            tod = "overcast"

        if not tod:
            if any(w in vo_lower for w in ["morning", "sunrise", "dawn"]):
                tod = "morning"
            elif any(w in vo_lower for w in ["evening", "sunset", "dusk"]):
                tod = "golden_hour"
            elif any(w in vo_lower for w in ["night", "dark", "midnight"]):
                tod = "night"

        if tod:
            cues["llm_time_of_day"] = tod
            cues["time_hints"].append(tod.replace("_", " "))

        # ── Key visual elements from visual_description ───────────────────────
        element_patterns = [
            ("window", "window"),
            ("rain", "rain on glass"),
            ("city light", "blurred city lights"),
            ("cloud", "clouds"),
            ("sunlight", "rays of sunlight"),
            ("warm light", "warm light"),
            ("shadow", "shadows"),
            ("face", "close-up face"),
            ("silhouette", "silhouette"),
            ("forest", "trees and foliage"),
            ("ocean", "ocean waves"),
            ("mountain", "mountain landscape"),
            ("street", "city street"),
            ("office", "office environment"),
            ("book", "books"),
            ("sky", "open sky"),
        ]
        elements = []
        for pattern, label in element_patterns:
            if pattern in vd_lower:
                elements.append(label)
        if elements:
            cues["llm_key_elements"] = elements[:5]

        return cues

    def _generate_camera_spec(
        self,
        profile: BeatVisualProfile,
        visual_cues: dict,
        scene_number: int,
    ) -> CameraSpec:
        """Generate camera specification based on beat profile and cues."""
        # Select shot type based on beat
        shot_type = random.choice(profile.shot_types)

        # Select angle
        angle = random.choice(profile.angles)

        # Lens selection based on shot type
        lens_map = {
            ShotType.EXTREME_WIDE: 16,
            ShotType.WIDE: 24,
            ShotType.FULL: 35,
            ShotType.MEDIUM_WIDE: 35,
            ShotType.MEDIUM: 50,
            ShotType.MEDIUM_CLOSE: 50,
            ShotType.CLOSE_UP: 85,
            ShotType.EXTREME_CLOSE: 100,
            ShotType.INSERT: 50,
            ShotType.OVER_SHOULDER: 50,
            ShotType.POV: 35,
        }
        lens_mm = lens_map.get(shot_type, 50)

        # Movement
        movement = random.choice(profile.movements)

        # Depth of field
        dof = "shallow" if shot_type in [ShotType.CLOSE_UP, ShotType.MEDIUM_CLOSE] else "medium"

        # Framing notes based on beat
        framing_notes = ""
        if scene_number == 1:
            framing_notes = "subject centered for immediate engagement"
        elif profile.energy == "high":
            framing_notes = "dynamic composition with visual tension"
        else:
            framing_notes = "balanced rule-of-thirds framing"

        return CameraSpec(
            shot_type=shot_type,
            angle=angle,
            lens_mm=lens_mm,
            movement=movement,
            depth_of_field=dof,
            framing_notes=framing_notes,
        )

    def _generate_subject_spec(
        self,
        profile: BeatVisualProfile,
        visual_cues: dict,
        prior_scene: Optional[ScenePromptSpec],
        visual_description: Optional[str] = None,
    ) -> SubjectSpec:
        """Generate subject specification based on visual strategy."""

        # ENVIRONMENT strategy: abstract/metaphor subjects, NO PEOPLE
        if self.visual_strategy == VisualStrategy.ENVIRONMENT:
            return self._generate_environment_subject(profile, visual_cues, visual_description)

        # PEOPLE strategy: human figures (original behavior)
        return self._generate_person_subject(profile, visual_cues, prior_scene)

    def _generate_environment_subject(
        self,
        profile: BeatVisualProfile,
        visual_cues: dict,
        visual_description: Optional[str] = None,
    ) -> SubjectSpec:
        """Generate abstract/metaphor subject (NO PEOPLE).

        When visual_description is provided (Claude-written concept from the shot
        list), use it directly as the subject instead of a random beat-type pick.
        """

        if visual_description and visual_description.strip():
            # Use the Claude-written visual concept verbatim — it IS the subject.
            # Still add a light tone enhancement for atmosphere.
            tone = visual_cues.get("emotional_tone", "neutral")
            tone_enhancements = {
                "positive": "bathed in warm golden light",
                "challenging": "cast in dramatic shadows",
                "reflective": "soft diffused atmospheric light",
                "neutral": "",
            }
            enhancement = tone_enhancements.get(tone, "")
            full_description = f"{visual_description.strip()}, {enhancement}" if enhancement else visual_description.strip()
        else:
            # Fallback: random pick from beat-type hardcoded list
            if profile.environment_subjects:
                subject_description = random.choice(profile.environment_subjects)
            else:
                subject_description = random.choice([
                    "dramatic landscape with symbolic elements",
                    "abstract geometric composition",
                    "natural phenomenon with metaphorical significance",
                ])

            tone = visual_cues.get("emotional_tone", "neutral")
            tone_enhancements = {
                "positive": "bathed in warm golden light, evoking hope and triumph",
                "challenging": "cast in deep shadows, conveying weight and struggle",
                "reflective": "soft diffused atmosphere, inviting contemplation",
                "neutral": "balanced natural lighting, clean composition",
            }
            enhancement = tone_enhancements.get(tone, "")
            full_description = f"{subject_description}, {enhancement}" if enhancement else subject_description

        # Only enforce no-people when we fell back to random beat picks.
        # When visual_description is provided, Claude already made that decision.
        if visual_description and visual_description.strip():
            additional_notes = "cinematic, photorealistic. Follow the visual description faithfully."
        else:
            additional_notes = "cinematic abstract visual, NO PEOPLE, NO FACES, NO HUMAN FIGURES. Focus on symbolic imagery, textures, and atmosphere."

        return SubjectSpec(
            count=1,
            subject_type="environment",
            age_range="",
            gender_presentation="",
            wardrobe="",
            hair_style="",
            facial_expression="",
            pose=full_description,
            action="subtle atmospheric movement, dust motes or gentle light shifts",
            skin_texture="",
            additional_notes=additional_notes,
        )

    def _generate_person_subject(
        self,
        profile: BeatVisualProfile,
        visual_cues: dict,
        prior_scene: Optional[ScenePromptSpec],
    ) -> SubjectSpec:
        """Generate person-based subject specification."""
        # Check for continuity with prior scene
        if prior_scene and prior_scene.subject:
            # Maintain some consistency
            age_range = prior_scene.subject.age_range or "30s"
            wardrobe = prior_scene.subject.wardrobe or "casual professional attire"
        else:
            age_range = "late 20s to early 40s"
            wardrobe = "contemporary casual professional attire, muted earth tones"

        # Expression based on emotional tone
        expression_map = {
            "positive": "subtle smile, eyes showing warmth and satisfaction",
            "challenging": "determined expression, slight tension in jaw",
            "reflective": "thoughtful gaze, soft contemplative look",
            "neutral": "calm, present, engaged expression",
        }
        expression = expression_map.get(visual_cues.get("emotional_tone", "neutral"), "calm expression")

        # Pose based on beat energy
        if profile.energy == "high":
            pose = "upright confident posture, shoulders back"
        elif profile.energy == "low":
            pose = "relaxed natural stance, grounded"
        else:
            pose = "balanced natural posture"

        # Action from cues
        action = ", ".join(visual_cues.get("action_keywords", [])) or "subtle movement"

        return SubjectSpec(
            count=1,
            subject_type="person",
            age_range=age_range,
            gender_presentation="",  # Intentionally neutral unless specified
            wardrobe=wardrobe,
            hair_style="natural styled hair",
            facial_expression=expression,
            pose=pose,
            action=action,
            skin_texture="natural skin with visible pores, micro-textures, and subtle imperfections for realism",
            additional_notes="authentic human presence, avoiding uncanny valley",
        )

    def _generate_environment_spec(
        self,
        profile: BeatVisualProfile,
        visual_cues: dict,
        prior_scene: Optional[ScenePromptSpec],
    ) -> EnvironmentSpec:
        """Generate environment specification.

        Uses LLM-extracted fields (llm_environment_type, llm_time_of_day,
        llm_key_elements) when available; falls back to keyword hints otherwise.
        """
        # ── LLM path ──────────────────────────────────────────────────────────
        llm_env_type = visual_cues.get("llm_environment_type", "")
        llm_tod      = visual_cues.get("llm_time_of_day", "")
        llm_elements = visual_cues.get("llm_key_elements", [])

        if llm_env_type:
            env_type_map = {
                "interior": ("indoor",    "interior space"),
                "exterior": ("outdoor",   "outdoor environment"),
                "nature":   ("outdoor",   "natural landscape with organic textures"),
                "urban":    ("outdoor",   "urban environment with architectural elements"),
                "abstract": ("abstract",  "abstract visual space"),
                "cosmic":   ("abstract",  "cosmic or infinite space"),
            }
            indoor_outdoor, location_type = env_type_map.get(
                llm_env_type, ("indoor", "interior space")
            )

            tod_map = {
                "golden_hour": TimeOfDay.GOLDEN_HOUR,
                "morning":     TimeOfDay.MORNING,
                "night":       TimeOfDay.NIGHT,
                "midday":      TimeOfDay.MIDDAY,
                "overcast":    TimeOfDay.OVERCAST,
                "unspecified": TimeOfDay.GOLDEN_HOUR,
            }
            time_of_day = tod_map.get(llm_tod, TimeOfDay.GOLDEN_HOUR)

            key_objects = llm_elements if llm_elements else ["carefully placed contextual elements"]
            atmosphere_map = {
                "striking": "crisp air with high visibility",
                "moody": "slightly hazy with depth atmosphere",
                "transitional": "clearing atmosphere",
                "building": "energetic clear atmosphere",
                "resolved": "warm diffused atmosphere",
                "inviting": "welcoming atmospheric clarity",
            }
            mood = random.choice(profile.environment_moods)
            atmosphere = atmosphere_map.get(mood, "natural atmosphere")

            return EnvironmentSpec(
                indoor_outdoor=indoor_outdoor,
                location_type=location_type,
                key_objects=key_objects,
                background_elements="soft blurred background with depth, subtle environmental details",
                time_of_day=time_of_day,
                weather="",
                atmosphere=atmosphere,
            )

        # ── Keyword fallback path ──────────────────────────────────────────────
        env_hints = visual_cues.get("environment_hints", [])

        indoor_outdoor = "indoor"
        if "outdoor" in env_hints or "natural" in env_hints:
            indoor_outdoor = "outdoor"

        location_types = {
            "urban":   "modern city environment with architectural elements",
            "office":  "contemporary minimalist office space with clean lines",
            "home":    "warm residential interior with personal touches",
            "natural": "natural landscape with organic textures",
        }
        location_type = "contemporary interior space with soft furnishings"
        for hint in env_hints:
            if hint in location_types:
                location_type = location_types[hint]
                break

        time_hints = visual_cues.get("time_hints", [])
        if "morning" in time_hints:
            time_of_day = TimeOfDay.MORNING
        elif "evening" in time_hints:
            time_of_day = TimeOfDay.GOLDEN_HOUR
        elif "night" in time_hints:
            time_of_day = TimeOfDay.NIGHT
        else:
            time_of_day = TimeOfDay.GOLDEN_HOUR

        atmosphere_map = {
            "striking": "crisp air with high visibility",
            "moody": "slightly hazy with depth atmosphere",
            "transitional": "clearing atmosphere",
            "building": "energetic clear atmosphere",
            "resolved": "warm diffused atmosphere",
            "inviting": "welcoming atmospheric clarity",
        }
        mood = random.choice(profile.environment_moods)
        atmosphere = atmosphere_map.get(mood, "natural atmosphere")

        return EnvironmentSpec(
            indoor_outdoor=indoor_outdoor,
            location_type=location_type,
            key_objects=["minimal carefully placed props for context"],
            background_elements="soft blurred background with depth, subtle environmental details",
            time_of_day=time_of_day,
            weather="",
            atmosphere=atmosphere,
        )

    def _generate_lighting_spec(
        self,
        profile: BeatVisualProfile,
        visual_cues: dict,
    ) -> LightingSpec:
        """Generate lighting specification."""
        style = random.choice(profile.lighting_styles)

        # Key light direction
        key_directions = [
            "45 degrees from camera right",
            "45 degrees from camera left",
            "direct frontal soft",
            "side light from window",
        ]
        key_light = random.choice(key_directions)

        # Softness based on style
        softness = "soft" if style in [LightingStyle.NATURAL_SOFT, LightingStyle.HIGH_KEY] else "mixed"

        # Rim light for separation
        rim_light = profile.energy == "high" or style == LightingStyle.RIM_LIT

        # Mood from emotional tone
        tone = visual_cues.get("emotional_tone", "neutral")
        mood_map = {
            "positive": "warm inviting",
            "challenging": "cool dramatic",
            "reflective": "soft contemplative",
            "neutral": "balanced natural",
        }
        mood = mood_map.get(tone, "balanced")

        return LightingSpec(
            style=style,
            key_light_direction=key_light,
            softness=softness,
            rim_light=rim_light,
            practicals="ambient environmental light sources" if style != LightingStyle.STUDIO else "",
            shadow_style="soft graduated shadows with detail in shadows",
            mood=mood,
            contrast_level=profile.contrast_level,
        )

    def _generate_color_style_spec(
        self,
        profile: BeatVisualProfile,
        visual_cues: dict,
    ) -> ColorStyleSpec:
        """Generate color and style specification."""
        tone = visual_cues.get("emotional_tone", "neutral")

        # Color palette based on emotional tone
        palette_map = {
            "positive": "warm amber and soft gold tones with touches of cream",
            "challenging": "cool desaturated blues and grays with warm accent",
            "reflective": "muted earth tones with gentle warm highlights",
            "neutral": "balanced natural tones with subtle warmth",
        }
        palette = palette_map.get(tone, "natural balanced color palette")

        # Preset overrides
        color_grading = self.visual_preset.get("style", {}).get("color_grading", "filmic")

        return ColorStyleSpec(
            color_palette=palette,
            contrast=profile.contrast_level,
            saturation="natural" if tone == "neutral" else "slightly desaturated",
            film_grain="subtle organic film grain for texture",
            realism_level="photoreal with cinematic qualities",
            texture_detail="high detail with visible material textures and fabric weave",
            color_grading=f"{color_grading} color grading",
        )

    def _generate_continuity_spec(
        self,
        prior_scene: Optional[ScenePromptSpec],
        visual_cues: dict,
    ) -> ContinuitySpec:
        """Generate continuity specification."""
        entities = []
        prior_refs = []
        notes = ""

        # Add any registered entities
        for name, entity in self._entity_map.items():
            if entity.get("description"):
                entities.append(f"{name}: {entity['description']}")

        # Reference prior scene if available
        if prior_scene:
            prior_refs.append(f"maintain subject consistency from scene {prior_scene.scene_number}")
            if prior_scene.environment.location_type:
                prior_refs.append(f"same general environment: {prior_scene.environment.location_type}")

        if entities or prior_refs:
            notes = "ensure visual consistency across scenes"

        return ContinuitySpec(
            entities=entities,
            prior_scene_references=prior_refs,
            consistency_notes=notes,
        )

    def _generate_negatives(self, custom_guidance: Optional[str]) -> NegativeConstraints:
        """Generate negative constraints."""
        custom = []

        # Add no-people constraints for environment strategy
        if self.visual_strategy == VisualStrategy.ENVIRONMENT:
            custom.extend([
                "no people",
                "no human figures",
                "no faces",
                "no hands",
                "no body parts",
                "no silhouettes of people",
                "no crowds",
            ])

        if custom_guidance:
            # Extract any negative instructions from guidance
            if "no " in custom_guidance.lower() or "avoid " in custom_guidance.lower():
                # Simple extraction - in production would use NLP
                custom.append(custom_guidance)

        return NegativeConstraints(custom=custom)

    def _generate_output_format(self) -> OutputFormatSpec:
        """Generate output format specification."""
        gen_config = self.visual_preset.get("generation", {})

        return OutputFormatSpec(
            aspect_ratio=gen_config.get("aspect_ratio", "9:16"),
            resolution=gen_config.get("resolution", "1080x1920"),
            fps_look=f"{gen_config.get('fps', 24)}fps cinematic motion",
            style="photoreal cinematic",
        )

    def _ensure_minimum_words(self, spec: ScenePromptSpec) -> None:
        """
        Ensure the prompt meets minimum word count.

        Adds additional detail if needed.
        """
        current_count = spec.word_count()
        min_count = MIN_WORD_COUNTS.get(spec.detail_level, 90)

        if current_count >= min_count:
            return

        # Add more detail to reach minimum
        additional_details = [
            "professional cinematic production quality",
            "subtle atmospheric haze for depth",
            "careful attention to micro-details",
            "authentic human presence and emotion",
            "balanced visual composition",
            "natural material textures visible",
            "environmental storytelling elements",
            "subtle color harmony throughout frame",
        ]

        # Add details to subject spec
        if spec.subject.additional_notes:
            spec.subject.additional_notes += ", " + ", ".join(additional_details[:2])
        else:
            spec.subject.additional_notes = ", ".join(additional_details[:2])

        # Add to color style
        if not spec.color_style.texture_detail.endswith("detail"):
            spec.color_style.texture_detail += ", " + additional_details[2]


def generate_nanobanana_prompt(
    scene_number: int,
    beat_type: str,
    voiceover: str,
    detail_level: str = "ultra",
    visual_preset: Optional[dict] = None,
    entities: Optional[list[dict]] = None,
    prior_scene_spec: Optional[ScenePromptSpec] = None,
    overlay_text: Optional[str] = None,
    visual_strategy: str = "auto",
    niche: Optional[str] = None,
    visual_description: Optional[str] = None,
) -> ScenePromptSpec:
    """
    Convenience function to generate a NanoBanana prompt.

    Args:
        scene_number: Scene number
        beat_type: Beat type (HOOK, TENSION, etc.)
        voiceover: Voiceover text for the scene
        detail_level: "short", "normal", or "ultra"
        visual_preset: Visual mode preset
        entities: Continuity entities
        prior_scene_spec: Previous scene spec for continuity
        overlay_text: Optional overlay text
        visual_strategy: "people", "environment", or "auto" (default)
        niche: Content niche (e.g., "motivation", "fun_facts")
        visual_description: Claude-written visual concept from the shot list.
            When provided, used as the subject instead of random beat-type picks.

    Returns:
        Complete ScenePromptSpec
    """
    level = PromptDetailLevel(detail_level.lower())

    strategy = VisualStrategy(visual_strategy.lower()) if visual_strategy else VisualStrategy.AUTO

    generator = NanoBananaPromptGenerator(
        detail_level=level,
        visual_preset=visual_preset,
        entities=entities,
        visual_strategy=strategy,
        niche=niche,
    )

    return generator.generate_scene_spec(
        scene_number=scene_number,
        beat_type=beat_type,
        voiceover_segment=voiceover,
        prior_scene_spec=prior_scene_spec,
        overlay_text=overlay_text,
        visual_description=visual_description,
    )
