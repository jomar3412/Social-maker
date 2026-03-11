"""
Scene Prompt Specification for NanoBanana prompt generation.

Provides structured, detailed visual prompts that are reproducible and
specific enough to consistently generate the intended image/video.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ShotType(Enum):
    """Camera shot types."""
    EXTREME_WIDE = "extreme wide shot"
    WIDE = "wide shot"
    FULL = "full shot"
    MEDIUM_WIDE = "medium wide shot"
    MEDIUM = "medium shot"
    MEDIUM_CLOSE = "medium close-up"
    CLOSE_UP = "close-up"
    EXTREME_CLOSE = "extreme close-up"
    INSERT = "insert shot"
    OVER_SHOULDER = "over-the-shoulder"
    POV = "POV shot"


class CameraAngle(Enum):
    """Camera angles."""
    EYE_LEVEL = "eye level"
    LOW_ANGLE = "low angle"
    HIGH_ANGLE = "high angle"
    BIRDS_EYE = "bird's eye view"
    DUTCH = "dutch angle"
    WORMS_EYE = "worm's eye view"


class CameraMovement(Enum):
    """Camera movement types."""
    STATIC = "static"
    SLOW_PUSH = "slow push-in"
    SLOW_PULL = "slow pull-out"
    PAN_LEFT = "slow pan left"
    PAN_RIGHT = "slow pan right"
    TILT_UP = "slow tilt up"
    TILT_DOWN = "slow tilt down"
    DOLLY = "dolly movement"
    CRANE = "crane movement"
    HANDHELD = "subtle handheld"
    DRIFT = "gentle drift"


class TimeOfDay(Enum):
    """Time of day for lighting context."""
    GOLDEN_HOUR = "golden hour"
    BLUE_HOUR = "blue hour"
    MIDDAY = "midday"
    MORNING = "morning light"
    AFTERNOON = "afternoon"
    DUSK = "dusk"
    NIGHT = "night"
    OVERCAST = "overcast day"


class LightingStyle(Enum):
    """Lighting style presets."""
    NATURAL_SOFT = "soft natural light"
    NATURAL_HARD = "hard natural light"
    DRAMATIC = "dramatic cinematic lighting"
    HIGH_KEY = "high-key bright lighting"
    LOW_KEY = "low-key moody lighting"
    SILHOUETTE = "silhouette backlit"
    RIM_LIT = "rim lighting"
    STUDIO = "studio three-point lighting"
    PRACTICAL = "practical lights only"
    NEON = "neon accent lighting"


class PromptDetailLevel(Enum):
    """Detail level for prompt generation."""
    SHORT = "short"       # ~40-60 words, essential elements only
    NORMAL = "normal"     # ~70-100 words, balanced detail
    ULTRA = "ultra"       # ~120-180 words, maximum specificity


@dataclass
class CameraSpec:
    """Camera and framing specifications."""
    shot_type: ShotType = ShotType.MEDIUM
    angle: CameraAngle = CameraAngle.EYE_LEVEL
    lens_mm: int = 35  # Focal length feel (24, 35, 50, 85, etc.)
    movement: CameraMovement = CameraMovement.STATIC
    depth_of_field: str = "shallow"  # "shallow", "medium", "deep"
    framing_notes: str = ""  # e.g., "subject centered", "rule of thirds left"

    def to_prompt_text(self) -> str:
        """Convert to prompt fragment."""
        parts = [
            self.shot_type.value,
            self.angle.value,
            f"{self.lens_mm}mm lens feel",
            self.movement.value,
            f"{self.depth_of_field} depth of field",
        ]
        if self.framing_notes:
            parts.append(self.framing_notes)
        return ", ".join(parts)


@dataclass
class SubjectSpec:
    """Subject/character specifications."""
    count: int = 1
    subject_type: str = "person"  # "person", "group", "animal", "object"
    age_range: str = ""  # e.g., "30s", "young adult", "elderly"
    gender_presentation: str = ""  # Only if narratively relevant
    wardrobe: str = ""  # e.g., "dark business suit", "casual athleisure"
    hair_style: str = ""
    facial_expression: str = ""  # e.g., "contemplative", "determined"
    pose: str = ""  # e.g., "standing arms crossed", "seated leaning forward"
    action: str = ""  # e.g., "walking", "typing", "looking out window"
    skin_texture: str = "natural skin with visible pores and texture"
    additional_notes: str = ""

    def to_prompt_text(self) -> str:
        """Convert to prompt fragment."""
        parts = []

        # Subject count and type
        if self.count > 1:
            parts.append(f"{self.count} people")
        elif self.subject_type == "person":
            parts.append("single person")
        else:
            parts.append(self.subject_type)

        # Demographics (only if specified)
        if self.age_range:
            parts.append(self.age_range)
        if self.gender_presentation:
            parts.append(self.gender_presentation)

        # Appearance
        if self.wardrobe:
            parts.append(f"wearing {self.wardrobe}")
        if self.hair_style:
            parts.append(f"{self.hair_style} hair")
        if self.facial_expression:
            parts.append(f"{self.facial_expression} expression")

        # Pose and action
        if self.pose:
            parts.append(self.pose)
        if self.action:
            parts.append(self.action)

        # Texture for realism
        if self.skin_texture:
            parts.append(self.skin_texture)

        if self.additional_notes:
            parts.append(self.additional_notes)

        return ", ".join(parts)


@dataclass
class EnvironmentSpec:
    """Environment and setting specifications."""
    indoor_outdoor: str = "indoor"  # "indoor", "outdoor", "mixed"
    location_type: str = ""  # e.g., "modern office", "city street", "forest"
    key_objects: list[str] = field(default_factory=list)  # Important props
    background_elements: str = ""
    time_of_day: TimeOfDay = TimeOfDay.GOLDEN_HOUR
    weather: str = ""  # e.g., "light rain", "foggy", "clear"
    atmosphere: str = ""  # e.g., "hazy", "crisp", "dusty"

    def to_prompt_text(self) -> str:
        """Convert to prompt fragment."""
        parts = []

        if self.location_type:
            parts.append(f"{self.indoor_outdoor} {self.location_type}")
        else:
            parts.append(self.indoor_outdoor)

        if self.key_objects:
            parts.append(f"with {', '.join(self.key_objects)}")

        if self.background_elements:
            parts.append(f"background: {self.background_elements}")

        parts.append(self.time_of_day.value)

        if self.weather:
            parts.append(self.weather)
        if self.atmosphere:
            parts.append(f"{self.atmosphere} atmosphere")

        return ", ".join(parts)


@dataclass
class LightingSpec:
    """Lighting specifications."""
    style: LightingStyle = LightingStyle.NATURAL_SOFT
    key_light_direction: str = "45 degrees from camera right"
    softness: str = "soft"  # "soft", "hard", "mixed"
    rim_light: bool = False
    practicals: str = ""  # e.g., "desk lamp", "window light"
    shadow_style: str = "soft shadows"
    mood: str = ""  # e.g., "warm", "cold", "neutral"
    contrast_level: str = "medium"  # "low", "medium", "high"

    def to_prompt_text(self) -> str:
        """Convert to prompt fragment."""
        parts = [
            self.style.value,
            f"key light {self.key_light_direction}",
            f"{self.softness} light",
        ]

        if self.rim_light:
            parts.append("subtle rim light separation")
        if self.practicals:
            parts.append(f"practical lights: {self.practicals}")
        if self.shadow_style:
            parts.append(self.shadow_style)
        if self.mood:
            parts.append(f"{self.mood} mood")
        if self.contrast_level != "medium":
            parts.append(f"{self.contrast_level} contrast")

        return ", ".join(parts)


@dataclass
class ColorStyleSpec:
    """Color and visual style specifications."""
    color_palette: str = "natural warm tones"  # e.g., "cool blues", "warm oranges"
    contrast: str = "medium"  # "low", "medium", "high"
    saturation: str = "natural"  # "desaturated", "natural", "vibrant"
    film_grain: str = "subtle film grain"  # "none", "subtle", "heavy"
    realism_level: str = "photoreal"  # "photoreal", "cinematic", "stylized"
    texture_detail: str = "high detail"  # "soft", "medium", "high detail"
    color_grading: str = "filmic"  # "natural", "filmic", "teal-orange", etc.

    def to_prompt_text(self) -> str:
        """Convert to prompt fragment."""
        parts = [
            self.color_palette,
            f"{self.contrast} contrast",
            f"{self.saturation} saturation",
            self.color_grading,
            self.texture_detail,
        ]

        if self.film_grain and self.film_grain != "none":
            parts.append(self.film_grain)
        if self.realism_level:
            parts.append(self.realism_level)

        return ", ".join(parts)


@dataclass
class ContinuitySpec:
    """Continuity anchors for scene consistency."""
    entities: list[str] = field(default_factory=list)  # Entity references
    prior_scene_references: list[str] = field(default_factory=list)
    consistency_notes: str = ""  # e.g., "same character from scene 1"

    def to_prompt_text(self) -> str:
        """Convert to prompt fragment."""
        if not self.entities and not self.prior_scene_references and not self.consistency_notes:
            return ""

        parts = []
        if self.entities:
            parts.append(f"[Entities: {', '.join(self.entities)}]")
        if self.prior_scene_references:
            parts.append(f"[Continuity: {', '.join(self.prior_scene_references)}]")
        if self.consistency_notes:
            parts.append(self.consistency_notes)

        return ", ".join(parts)


@dataclass
class NegativeConstraints:
    """Things that must NOT appear in the generated content."""
    standard: list[str] = field(default_factory=lambda: [
        "text overlays",
        "watermarks",
        "logos",
        "distorted anatomy",
        "extra limbs",
        "deformed hands",
        "blurry",
        "low quality",
        "pixelated",
        "cartoon style",
        "anime style",
        "illustration",
    ])
    custom: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Convert to negative prompt."""
        all_negatives = self.standard + self.custom
        return ", ".join(all_negatives)


@dataclass
class OutputFormatSpec:
    """Output format constraints."""
    aspect_ratio: str = "9:16"  # "9:16", "16:9", "1:1"
    resolution: str = "1080x1920"
    fps_look: str = "24fps cinematic"
    style: str = "photoreal"  # "photoreal", "cinematic", "stylized"

    def to_prompt_text(self) -> str:
        """Convert to prompt fragment."""
        return f"vertical {self.aspect_ratio}, {self.resolution}, {self.fps_look}, {self.style}"


@dataclass
class ScenePromptSpec:
    """
    Complete specification for a scene's visual prompt.

    This structured approach ensures all prompts are detailed,
    reproducible, and maintain consistency across scenes.
    """
    scene_number: int
    beat_type: str  # HOOK, TENSION, SHIFT, CLIMB, RESOLUTION, CTA
    voiceover_segment: str  # The text being spoken

    # Visual specifications
    camera: CameraSpec = field(default_factory=CameraSpec)
    subject: SubjectSpec = field(default_factory=SubjectSpec)
    environment: EnvironmentSpec = field(default_factory=EnvironmentSpec)
    lighting: LightingSpec = field(default_factory=LightingSpec)
    color_style: ColorStyleSpec = field(default_factory=ColorStyleSpec)
    continuity: ContinuitySpec = field(default_factory=ContinuitySpec)
    negatives: NegativeConstraints = field(default_factory=NegativeConstraints)
    output_format: OutputFormatSpec = field(default_factory=OutputFormatSpec)

    # Optional overlay text
    overlay_text: Optional[str] = None

    # Generation settings
    detail_level: PromptDetailLevel = PromptDetailLevel.ULTRA

    def to_full_prompt(self) -> str:
        """
        Generate the complete NanoBanana prompt from all specifications.

        Returns a detailed, reproducible prompt text.
        """
        sections = []

        # Output format first (establishes frame)
        sections.append(self.output_format.to_prompt_text())

        # Camera and framing
        sections.append(self.camera.to_prompt_text())

        # Subject details
        subject_text = self.subject.to_prompt_text()
        if subject_text:
            sections.append(subject_text)

        # Environment
        sections.append(self.environment.to_prompt_text())

        # Lighting
        sections.append(self.lighting.to_prompt_text())

        # Color and style
        sections.append(self.color_style.to_prompt_text())

        # Continuity (if any)
        continuity_text = self.continuity.to_prompt_text()
        if continuity_text:
            sections.append(continuity_text)

        # Join all sections
        prompt = ". ".join(filter(None, sections))

        return prompt

    def to_negative_prompt(self) -> str:
        """Generate the negative prompt."""
        return self.negatives.to_prompt_text()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "scene_number": self.scene_number,
            "beat_type": self.beat_type,
            "voiceover_segment": self.voiceover_segment,
            "camera": {
                "shot_type": self.camera.shot_type.value,
                "angle": self.camera.angle.value,
                "lens_mm": self.camera.lens_mm,
                "movement": self.camera.movement.value,
                "depth_of_field": self.camera.depth_of_field,
                "framing_notes": self.camera.framing_notes,
            },
            "subject": {
                "count": self.subject.count,
                "subject_type": self.subject.subject_type,
                "age_range": self.subject.age_range,
                "gender_presentation": self.subject.gender_presentation,
                "wardrobe": self.subject.wardrobe,
                "hair_style": self.subject.hair_style,
                "facial_expression": self.subject.facial_expression,
                "pose": self.subject.pose,
                "action": self.subject.action,
                "skin_texture": self.subject.skin_texture,
            },
            "environment": {
                "indoor_outdoor": self.environment.indoor_outdoor,
                "location_type": self.environment.location_type,
                "key_objects": self.environment.key_objects,
                "background_elements": self.environment.background_elements,
                "time_of_day": self.environment.time_of_day.value,
                "weather": self.environment.weather,
                "atmosphere": self.environment.atmosphere,
            },
            "lighting": {
                "style": self.lighting.style.value,
                "key_light_direction": self.lighting.key_light_direction,
                "softness": self.lighting.softness,
                "rim_light": self.lighting.rim_light,
                "practicals": self.lighting.practicals,
                "shadow_style": self.lighting.shadow_style,
                "mood": self.lighting.mood,
                "contrast_level": self.lighting.contrast_level,
            },
            "color_style": {
                "color_palette": self.color_style.color_palette,
                "contrast": self.color_style.contrast,
                "saturation": self.color_style.saturation,
                "film_grain": self.color_style.film_grain,
                "realism_level": self.color_style.realism_level,
                "texture_detail": self.color_style.texture_detail,
                "color_grading": self.color_style.color_grading,
            },
            "continuity": {
                "entities": self.continuity.entities,
                "prior_scene_references": self.continuity.prior_scene_references,
                "consistency_notes": self.continuity.consistency_notes,
            },
            "negatives": {
                "standard": self.negatives.standard,
                "custom": self.negatives.custom,
            },
            "output_format": {
                "aspect_ratio": self.output_format.aspect_ratio,
                "resolution": self.output_format.resolution,
                "fps_look": self.output_format.fps_look,
                "style": self.output_format.style,
            },
            "overlay_text": self.overlay_text,
            "detail_level": self.detail_level.value,
            "full_prompt": self.to_full_prompt(),
            "negative_prompt": self.to_negative_prompt(),
        }

    def word_count(self) -> int:
        """Count words in the generated prompt."""
        return len(self.to_full_prompt().split())
