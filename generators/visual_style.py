"""
Visual Style System for Zack D Films-style Animation

Defines the visual style configuration for AI-generated content:
- 3D cartoon animation aesthetic (Blender/CGI style)
- Vibrant saturated colors for mobile screens
- Dynamic camera movements
- Cinematic lighting variations

The style prefix is injected into all VEO prompts to ensure
consistent visual output across scenes.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import random


class VisualStyleType(Enum):
    """Available visual styles."""
    ZACK_D_FILMS = "zack_d_films"
    MINIMAL = "minimal"
    CINEMATIC = "cinematic"
    DOCUMENTARY = "documentary"
    REALISTIC_UGC = "realistic_ugc"  # Photorealistic UGC for brand content


class CameraMovement(Enum):
    """Camera movement types with descriptions."""
    PUSH_IN_FAST = ("push_in_fast", "fast smooth push-in towards subject")
    SLOW_ZOOM = ("slow_zoom", "slow gradual zoom revealing details")
    PARALLAX_LEFT = ("parallax_left", "smooth parallax movement drifting left")
    PARALLAX_RIGHT = ("parallax_right", "smooth parallax movement drifting right")
    ORBIT_LEFT = ("orbit_left", "orbiting camera rotating left around subject")
    ORBIT_RIGHT = ("orbit_right", "orbiting camera rotating right around subject")
    PULL_BACK = ("pull_back", "slow pull back revealing wider scene")
    DUTCH_TILT = ("dutch_tilt", "slight Dutch angle with subtle movement")
    CRANE_UP = ("crane_up", "crane shot moving upward")
    CRANE_DOWN = ("crane_down", "crane shot moving downward")
    STATIC_DYNAMIC = ("static_dynamic", "static camera with dynamic subject movement")

    def __init__(self, key: str, description: str):
        self.key = key
        self.description = description


class LightingStyle(Enum):
    """Lighting styles for different moods."""
    DRAMATIC_RIM = ("dramatic_rim", "dramatic rim lighting with deep shadows")
    SOFT_AMBIENT = ("soft_ambient", "soft ambient lighting with gentle shadows")
    GOLDEN_HOUR = ("golden_hour", "warm golden hour lighting")
    NEON_GLOW = ("neon_glow", "neon glow lighting with vibrant colors")
    STUDIO_THREE = ("studio_three", "classic three-point studio lighting")
    VOLUMETRIC = ("volumetric", "volumetric god rays lighting")
    HIGH_KEY = ("high_key", "bright high-key lighting minimal shadows")
    LOW_KEY = ("low_key", "moody low-key lighting with contrast")

    def __init__(self, key: str, description: str):
        self.key = key
        self.description = description


@dataclass
class ColorPalette:
    """Color palette for visual consistency."""
    name: str
    primary: str      # Hex color
    secondary: str
    accent: str
    description: str

    def to_prompt(self) -> str:
        """Convert palette to prompt description."""
        return f"{self.description} color scheme"


# Zack D Films-inspired color palettes (vibrant for mobile)
ZACK_D_PALETTES = [
    ColorPalette("coral_teal", "#FF6B6B", "#4ECDC4", "#FFE66D",
                 "vibrant coral and teal with golden accents"),
    ColorPalette("electric_blue", "#00D9FF", "#FF00E5", "#FFFF00",
                 "electric blue and magenta with yellow highlights"),
    ColorPalette("sunset_orange", "#FF8C42", "#6B2D5C", "#F4D35E",
                 "warm sunset orange and deep purple"),
    ColorPalette("ocean_deep", "#00B4D8", "#0077B6", "#90E0EF",
                 "deep ocean blues with cyan highlights"),
    ColorPalette("neon_night", "#FF006E", "#8338EC", "#3A86FF",
                 "neon pink and purple with electric blue"),
    ColorPalette("forest_gold", "#2D6A4F", "#40916C", "#D4AF37",
                 "rich forest green with golden accents"),
    ColorPalette("sky_coral", "#48CAE4", "#FF7F50", "#FEFAE0",
                 "sky blue and coral with cream highlights"),
    ColorPalette("royal_purple", "#7209B7", "#3A0CA3", "#F72585",
                 "deep royal purple with hot pink accents"),
]


@dataclass
class ZackDFilmsStyle:
    """
    Zack D Films visual style configuration.

    Creates consistent 3D cartoon animation aesthetic with:
    - CGI/Blender-style rendering
    - Vibrant saturated colors
    - Dynamic camera movements
    - Cinematic lighting
    """

    # Core style attributes
    style_name: str = "zack_d_films"

    # Base style prefix (prepended to ALL prompts)
    base_prefix: str = field(default_factory=lambda: (
        "3D cartoon animation in Blender CGI style, "
        "vibrant saturated colors optimized for mobile screens, "
        "smooth motion blur, volumetric lighting, "
        "vertical 9:16 aspect ratio, faceless characters, "
        "cinematic depth of field"
    ))

    # Quality modifiers
    quality_suffix: str = field(default_factory=lambda: (
        "high detail render, smooth 30fps animation, "
        "professional quality, engaging visual"
    ))

    # Movement intensity (1.0 = normal, 1.5 = more dynamic)
    movement_intensity: float = 1.2

    # Color saturation boost (1.0 = normal, 1.3 = boosted)
    saturation_boost: float = 1.3

    # Current palette index for rotation
    _palette_index: int = 0

    def get_style_prefix(self) -> str:
        """Get the full style prefix for VEO prompts."""
        return self.base_prefix

    def get_quality_suffix(self) -> str:
        """Get quality modifiers for the prompt."""
        return self.quality_suffix

    def get_next_palette(self) -> ColorPalette:
        """Get next color palette in rotation."""
        palette = ZACK_D_PALETTES[self._palette_index]
        self._palette_index = (self._palette_index + 1) % len(ZACK_D_PALETTES)
        return palette

    def get_camera_for_scene(self, scene_index: int, total_scenes: int,
                              tone: str = "neutral") -> CameraMovement:
        """
        Select appropriate camera movement for a scene.

        Rules:
        - First scene: Fast push-in for impact
        - Last scene: Pull back for closure
        - Middle scenes: Variety based on tone and position
        """
        if scene_index == 0:
            # Opening: dramatic push in
            return CameraMovement.PUSH_IN_FAST
        elif scene_index == total_scenes - 1:
            # Closing: pull back
            return CameraMovement.PULL_BACK
        elif scene_index == 1:
            # Second scene: establish with orbit
            return CameraMovement.ORBIT_LEFT

        # Middle scenes: select based on tone and variety
        tone_cameras = {
            "dramatic": [CameraMovement.DUTCH_TILT, CameraMovement.PUSH_IN_FAST],
            "calm": [CameraMovement.SLOW_ZOOM, CameraMovement.PARALLAX_LEFT],
            "energetic": [CameraMovement.ORBIT_RIGHT, CameraMovement.CRANE_UP],
            "mysterious": [CameraMovement.SLOW_ZOOM, CameraMovement.DUTCH_TILT],
            "educational": [CameraMovement.PARALLAX_RIGHT, CameraMovement.SLOW_ZOOM],
            "playful": [CameraMovement.ORBIT_LEFT, CameraMovement.CRANE_DOWN],
        }

        options = tone_cameras.get(tone, [
            CameraMovement.PARALLAX_LEFT,
            CameraMovement.PARALLAX_RIGHT,
            CameraMovement.SLOW_ZOOM,
            CameraMovement.ORBIT_LEFT,
        ])

        # Alternate based on scene index for variety
        return options[scene_index % len(options)]

    def get_lighting_for_tone(self, tone: str, scene_index: int = 0) -> LightingStyle:
        """
        Select lighting style based on content tone.
        """
        tone_lighting = {
            "dramatic": LightingStyle.DRAMATIC_RIM,
            "calm": LightingStyle.SOFT_AMBIENT,
            "energetic": LightingStyle.NEON_GLOW,
            "mysterious": LightingStyle.LOW_KEY,
            "educational": LightingStyle.STUDIO_THREE,
            "playful": LightingStyle.HIGH_KEY,
            "inspiring": LightingStyle.VOLUMETRIC,
            "warm": LightingStyle.GOLDEN_HOUR,
        }

        return tone_lighting.get(tone, LightingStyle.STUDIO_THREE)

    def enhance_prompt(self, visual_direction: str, scene_index: int = 0,
                       total_scenes: int = 10, tone: str = "neutral") -> str:
        """
        Enhance a visual direction prompt with Zack D Films style.

        Args:
            visual_direction: Original visual description
            scene_index: Current scene number (0-indexed)
            total_scenes: Total number of scenes
            tone: Content tone (dramatic, calm, energetic, etc.)

        Returns:
            Enhanced prompt with style prefix and modifiers
        """
        # Get style components
        palette = self.get_next_palette()
        camera = self.get_camera_for_scene(scene_index, total_scenes, tone)
        lighting = self.get_lighting_for_tone(tone, scene_index)

        # Build enhanced prompt
        parts = [
            self.base_prefix,
            visual_direction,
            palette.to_prompt(),
            lighting.description,
            camera.description,
            self.quality_suffix,
        ]

        return ", ".join(parts)


# Pre-configured style instances
STYLES: Dict[str, ZackDFilmsStyle] = {
    "zack_d_films": ZackDFilmsStyle(),
}


def get_style(style_name: str = "zack_d_films"):
    """
    Get a visual style configuration by name.

    Args:
        style_name: Style identifier (zack_d_films, realistic_ugc, etc.)

    Returns:
        Style configuration object (ZackDFilmsStyle or RealisticStyle)
    """
    if style_name == "realistic_ugc":
        # Import and return realistic style for brand content
        try:
            from generators.realistic_style import get_realistic_style
            return get_realistic_style()
        except ImportError:
            print("Warning: RealisticStyle not available, using default")
            return ZackDFilmsStyle()

    return STYLES.get(style_name, ZackDFilmsStyle())


def enhance_visual_direction(
    visual_direction: str,
    style_name: str = "zack_d_films",
    scene_index: int = 0,
    total_scenes: int = 10,
    tone: str = "neutral",
) -> str:
    """
    Convenience function to enhance a visual direction with style.

    Args:
        visual_direction: Original visual description
        style_name: Style to apply (default: zack_d_films)
        scene_index: Current scene number
        total_scenes: Total scenes in video
        tone: Content tone

    Returns:
        Enhanced prompt string
    """
    style = get_style(style_name)
    return style.enhance_prompt(visual_direction, scene_index, total_scenes, tone)


# Topic-specific visual mappings for AI video generation
TOPIC_VISUAL_MAPPINGS = {
    # Space & Astronomy
    "planet": "3D animated planet with volumetric atmosphere and surface details",
    "earth": "3D Earth globe with animated cloud layers and city lights",
    "moon": "3D lunar surface with dramatic crater shadows and earthrise",
    "sun": "3D animated sun with solar flares and corona particles",
    "space": "deep space environment with animated nebulae and star fields",
    "star": "stellar formation with animated particle effects and lens flares",
    "galaxy": "3D spiral galaxy with animated rotation and dust lanes",
    "asteroid": "3D asteroid tumbling through space with surface detail",

    # Nature
    "ocean": "3D animated ocean with volumetric waves and light rays",
    "forest": "3D forest scene with animated foliage and light shafts",
    "mountain": "3D mountain landscape with volumetric clouds and mist",
    "volcano": "3D volcano with animated lava flow and smoke particles",
    "desert": "3D desert dunes with animated sand particles",
    "ice": "3D arctic scene with animated aurora and ice crystals",

    # Insects & Small Creatures
    "butterfly": "3D animated monarch butterfly with iridescent wings, landing on flower, macro detail",
    "butterflies": "3D animated colorful butterflies in graceful flight, garden scene, magical particles",
    "caterpillar": "3D animated caterpillar on leaf, transformation cocoon, nature macro",
    "insect": "3D animated insect with detailed exoskeleton, compound eyes, natural movement",
    "bee": "3D animated honeybee with fuzzy body, wing blur, pollen collection, golden particles",
    "ant": "3D animated ant carrying leaf, detailed colony, underground cross-section",
    "dragonfly": "3D animated dragonfly hovering over pond, iridescent wings, water reflection",
    "wing": "3D extreme close-up butterfly wing scales, iridescent patterns, microscopic detail",
    "metamorphosis": "3D animated cocoon transformation, butterfly emerging, wings unfolding",
    "taste": "3D butterfly landing on flower, proboscis unfurling, sensory visualization",
    "feet": "3D butterfly feet close-up showing taste receptors, sensory detail",

    # Science & Technology
    "brain": "3D brain visualization with animated neural network pulses",
    "dna": "3D DNA helix with animated base pair connections",
    "atom": "3D atomic model with animated electron orbits",
    "cell": "3D biological cell with animated organelles",
    "circuit": "3D circuit board with animated data flow patterns",
    "robot": "3D animated robot with mechanical movements",

    # Objects
    "paper": "3D animated paper with folding motion and light transmission",
    "book": "3D book with animated page turns and text reveals",
    "clock": "3D animated clock with moving hands and gears",
    "money": "3D animated currency with floating coin particles",
    "chess": "3D chess pieces on animated board with strategic positioning",
    "game": "3D animated game board with moving pieces",

    # Abstract
    "time": "3D abstract time visualization with flowing particles",
    "number": "3D animated numbers floating in abstract space",
    "data": "3D data visualization with animated charts and graphs",
    "energy": "3D animated energy waves and particle effects",
    "light": "3D animated light rays with volumetric scattering",
}


def get_topic_visual(topic: str) -> Optional[str]:
    """
    Get the 3D visual description for a topic.

    Args:
        topic: Topic keyword to look up

    Returns:
        3D visual description or None if not found
    """
    topic_lower = topic.lower()

    # Direct match
    if topic_lower in TOPIC_VISUAL_MAPPINGS:
        return TOPIC_VISUAL_MAPPINGS[topic_lower]

    # Partial match
    for key, visual in TOPIC_VISUAL_MAPPINGS.items():
        if key in topic_lower or topic_lower in key:
            return visual

    return None


if __name__ == "__main__":
    # Test the visual style system
    print("Zack D Films Visual Style System")
    print("=" * 50)

    style = get_style("zack_d_films")

    # Test style prefix
    print("\nBase Style Prefix:")
    print(style.get_style_prefix())

    # Test prompt enhancement
    test_prompt = "Close-up of paper being folded"
    enhanced = style.enhance_prompt(
        test_prompt,
        scene_index=0,
        total_scenes=10,
        tone="educational"
    )
    print(f"\nOriginal: {test_prompt}")
    print(f"\nEnhanced:\n{enhanced}")

    # Test palette rotation
    print("\n\nColor Palette Rotation:")
    for i in range(4):
        palette = style.get_next_palette()
        print(f"  {i+1}. {palette.name}: {palette.description}")

    # Test camera selection
    print("\n\nCamera Movement Selection:")
    for i in range(5):
        camera = style.get_camera_for_scene(i, 10, "educational")
        print(f"  Scene {i+1}: {camera.key} - {camera.description}")

    # Test topic visual mapping
    print("\n\nTopic Visual Mappings:")
    for topic in ["planet", "brain", "paper", "time"]:
        visual = get_topic_visual(topic)
        print(f"  {topic}: {visual[:60]}...")
