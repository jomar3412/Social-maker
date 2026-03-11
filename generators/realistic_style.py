"""
Realistic Visual Style System for UGC/Brand Content

Defines the photorealistic visual style configuration for brand content:
- iPhone-quality UGC aesthetic
- Natural lighting presets
- Camera settings for different shot types
- Skin texture and detail specifications

This is the brand content parallel to ZackDFilmsStyle (3D animation).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class RealisticShotType(Enum):
    """Shot types for photorealistic content."""
    PRODUCT_HERO = "product_hero"
    LIFESTYLE = "lifestyle"
    CLOSE_UP = "close_up"
    FLAT_LAY = "flat_lay"
    SELFIE = "selfie"
    MIRROR = "mirror"
    POV = "pov"
    UNBOXING = "unboxing"


class LightingPreset(Enum):
    """Lighting presets for different environments."""
    STUDIO = "studio"
    NATURAL_WINDOW = "natural_window"
    GOLDEN_HOUR = "golden_hour"
    BATHROOM = "bathroom"
    OUTDOOR_SHADE = "outdoor_shade"
    RING_LIGHT = "ring_light"
    SOFT_DIFFUSED = "soft_diffused"


# Camera settings for different shot types
CAMERA_SETTINGS = {
    RealisticShotType.PRODUCT_HERO: {
        "lens": "50mm",
        "aperture": "f/2.8",
        "description": "50mm lens, f/2.8, shallow depth of field, product sharply focused",
    },
    RealisticShotType.LIFESTYLE: {
        "lens": "35mm",
        "aperture": "f/4",
        "description": "35mm lens, f/4, environmental context, natural framing",
    },
    RealisticShotType.CLOSE_UP: {
        "lens": "85mm macro",
        "aperture": "f/1.8",
        "description": "85mm macro, f/1.8, extreme detail, shallow focus",
    },
    RealisticShotType.FLAT_LAY: {
        "lens": "24mm",
        "aperture": "f/8",
        "description": "overhead shot, 24mm, f/8, sharp edge to edge",
    },
    RealisticShotType.SELFIE: {
        "lens": "24mm (front camera)",
        "aperture": "f/2.2",
        "description": "front camera perspective, slight wide angle, natural selfie look",
    },
    RealisticShotType.MIRROR: {
        "lens": "35mm",
        "aperture": "f/2.8",
        "description": "mirror reflection shot, bathroom/fitness setting, authentic UGC",
    },
    RealisticShotType.POV: {
        "lens": "24mm",
        "aperture": "f/2.4",
        "description": "first-person POV, hands visible, product interaction",
    },
    RealisticShotType.UNBOXING: {
        "lens": "35mm",
        "aperture": "f/2.8",
        "description": "overhead or 45-degree angle, hands opening package, anticipation shot",
    },
}

# Lighting presets for different environments
LIGHTING_PRESETS = {
    LightingPreset.STUDIO: {
        "description": "softbox lighting, white backdrop, clean shadows, professional",
        "color_temp": "5500K neutral",
    },
    LightingPreset.NATURAL_WINDOW: {
        "description": "natural window light, warm tones, soft shadows from side",
        "color_temp": "5000K daylight",
    },
    LightingPreset.GOLDEN_HOUR: {
        "description": "warm golden hour sunlight, orange tones, long shadows, cinematic",
        "color_temp": "4000K warm",
    },
    LightingPreset.BATHROOM: {
        "description": "bathroom vanity lighting, even illumination, mirror reflections",
        "color_temp": "4500K slightly warm",
    },
    LightingPreset.OUTDOOR_SHADE: {
        "description": "open shade, diffused sunlight, catchlights in eyes, flattering",
        "color_temp": "6500K cool daylight",
    },
    LightingPreset.RING_LIGHT: {
        "description": "ring light catchlights, even facial lighting, influencer aesthetic",
        "color_temp": "5500K neutral",
    },
    LightingPreset.SOFT_DIFFUSED: {
        "description": "soft diffused lighting, minimal shadows, clean beauty look",
        "color_temp": "5000K daylight",
    },
}

# Skin texture triggers for photorealism
SKIN_TEXTURE_TRIGGERS = [
    "visible skin pores",
    "natural skin texture with subtle imperfections",
    "realistic skin micro-details",
    "natural skin undertones",
    "soft natural shadows on face",
    "realistic skin highlights",
    "subtle skin blemishes for authenticity",
    "natural makeup look (if applicable)",
]


@dataclass
class RealisticStyle:
    """
    Photorealistic UGC visual style configuration.

    Creates consistent iPhone-quality aesthetic with:
    - Natural lighting
    - Authentic skin textures
    - UGC-style camera work
    - Social media ready vertical format
    """

    # Core style attributes
    style_name: str = "realistic_ugc"

    # Base style prefix (prepended to ALL prompts)
    base_prefix: str = field(default_factory=lambda: (
        "photorealistic photography, shot on iPhone 14 Pro, "
        "natural lighting, authentic UGC aesthetic, "
        "skin texture detail with pores and subtle imperfections, "
        "soft natural shadows, vertical 9:16 format, "
        "social media ready, high resolution"
    ))

    # Quality modifiers
    quality_suffix: str = field(default_factory=lambda: (
        "4K quality, sharp focus, natural color grading, "
        "professional but authentic look"
    ))

    # Current shot type for consistent application
    current_shot_type: RealisticShotType = RealisticShotType.LIFESTYLE
    current_lighting: LightingPreset = LightingPreset.NATURAL_WINDOW

    def get_style_prefix(self) -> str:
        """Get the full style prefix for AI image/video prompts."""
        return self.base_prefix

    def get_quality_suffix(self) -> str:
        """Get quality modifiers for the prompt."""
        return self.quality_suffix

    def get_camera_settings(self, shot_type: RealisticShotType = None) -> Dict:
        """Get camera settings for a shot type."""
        shot = shot_type or self.current_shot_type
        return CAMERA_SETTINGS.get(shot, CAMERA_SETTINGS[RealisticShotType.LIFESTYLE])

    def get_lighting(self, preset: LightingPreset = None) -> Dict:
        """Get lighting description for a preset."""
        light = preset or self.current_lighting
        return LIGHTING_PRESETS.get(light, LIGHTING_PRESETS[LightingPreset.NATURAL_WINDOW])

    def get_skin_triggers(self, count: int = 3) -> List[str]:
        """Get skin texture triggers for photorealism."""
        import random
        return random.sample(SKIN_TEXTURE_TRIGGERS, min(count, len(SKIN_TEXTURE_TRIGGERS)))

    def enhance_prompt(
        self,
        visual_direction: str,
        shot_type: RealisticShotType = None,
        lighting: LightingPreset = None,
        include_skin_detail: bool = True,
        model_description: str = None,
    ) -> str:
        """
        Enhance a visual direction prompt with realistic UGC style.

        Args:
            visual_direction: Original visual description
            shot_type: Type of shot (product_hero, lifestyle, etc.)
            lighting: Lighting preset
            include_skin_detail: Whether to add skin texture triggers
            model_description: Description of human model if present

        Returns:
            Enhanced prompt with style prefix and modifiers
        """
        shot = shot_type or self.current_shot_type
        light = lighting or self.current_lighting

        camera = self.get_camera_settings(shot)
        light_settings = self.get_lighting(light)

        # Build enhanced prompt
        parts = [
            self.base_prefix,
            visual_direction,
        ]

        # Add model description if provided
        if model_description:
            parts.append(model_description)

        # Add skin detail for shots with people
        if include_skin_detail and shot in [
            RealisticShotType.SELFIE,
            RealisticShotType.MIRROR,
            RealisticShotType.LIFESTYLE,
            RealisticShotType.CLOSE_UP,
        ]:
            skin_triggers = self.get_skin_triggers(2)
            parts.extend(skin_triggers)

        # Add camera settings
        parts.append(camera["description"])

        # Add lighting
        parts.append(light_settings["description"])

        # Add quality suffix
        parts.append(self.quality_suffix)

        return ", ".join(parts)

    def get_environment_setup(self, environment: str) -> Dict[str, str]:
        """
        Get recommended settings for a visual environment.

        Args:
            environment: studio, lifestyle, outdoor, home, bathroom, etc.

        Returns:
            Dict with recommended shot_type and lighting
        """
        env_setups = {
            "studio": {
                "shot_type": RealisticShotType.PRODUCT_HERO,
                "lighting": LightingPreset.STUDIO,
                "description": "clean professional studio with white backdrop",
            },
            "lifestyle": {
                "shot_type": RealisticShotType.LIFESTYLE,
                "lighting": LightingPreset.NATURAL_WINDOW,
                "description": "cozy home environment with natural light",
            },
            "outdoor": {
                "shot_type": RealisticShotType.LIFESTYLE,
                "lighting": LightingPreset.OUTDOOR_SHADE,
                "description": "outdoor setting with natural diffused light",
            },
            "home": {
                "shot_type": RealisticShotType.LIFESTYLE,
                "lighting": LightingPreset.NATURAL_WINDOW,
                "description": "comfortable home setting, lived-in feel",
            },
            "bathroom": {
                "shot_type": RealisticShotType.MIRROR,
                "lighting": LightingPreset.BATHROOM,
                "description": "bathroom vanity, skincare routine setting",
            },
            "gym": {
                "shot_type": RealisticShotType.MIRROR,
                "lighting": LightingPreset.SOFT_DIFFUSED,
                "description": "gym mirror selfie, fitness environment",
            },
            "cafe": {
                "shot_type": RealisticShotType.LIFESTYLE,
                "lighting": LightingPreset.NATURAL_WINDOW,
                "description": "cozy cafe setting, lifestyle vibe",
            },
            "kitchen": {
                "shot_type": RealisticShotType.POV,
                "lighting": LightingPreset.NATURAL_WINDOW,
                "description": "kitchen counter, food/cooking context",
            },
            "office": {
                "shot_type": RealisticShotType.LIFESTYLE,
                "lighting": LightingPreset.SOFT_DIFFUSED,
                "description": "professional workspace, productivity context",
            },
        }
        return env_setups.get(environment.lower(), env_setups["lifestyle"])


# Pre-configured style instance
REALISTIC_STYLE = RealisticStyle()


def get_realistic_style() -> RealisticStyle:
    """Get the realistic UGC style configuration."""
    return REALISTIC_STYLE


def enhance_brand_visual(
    visual_direction: str,
    environment: str = "lifestyle",
    include_model: bool = True,
    model_description: str = None,
) -> str:
    """
    Convenience function to enhance brand visual direction.

    Args:
        visual_direction: Original visual description
        environment: Visual environment (studio, lifestyle, bathroom, etc.)
        include_model: Whether scene includes a human model
        model_description: Description of the model if present

    Returns:
        Enhanced prompt string for AI image/video generation
    """
    style = get_realistic_style()
    env_setup = style.get_environment_setup(environment)

    return style.enhance_prompt(
        visual_direction=visual_direction,
        shot_type=env_setup["shot_type"],
        lighting=env_setup["lighting"],
        include_skin_detail=include_model,
        model_description=model_description,
    )


# Video model specific optimizations
VIDEO_MODEL_TRIGGERS = {
    "nano_banana": {
        "positive": [
            "realistic human",
            "natural movement",
            "professional lighting",
            "high quality video",
        ],
        "negative": [
            "cartoon",
            "anime",
            "3D render",
            "unrealistic",
        ],
    },
    "nano_banana_pro": {
        "positive": [
            "cinematic quality",
            "photorealistic",
            "natural skin texture",
            "professional video production",
            "4K resolution",
        ],
        "negative": [
            "artificial",
            "CGI",
            "animation",
            "low quality",
        ],
    },
}


def get_video_model_triggers(model: str) -> Dict[str, List[str]]:
    """Get positive/negative triggers for a specific video model."""
    return VIDEO_MODEL_TRIGGERS.get(model, VIDEO_MODEL_TRIGGERS["nano_banana_pro"])


if __name__ == "__main__":
    # Test the realistic style system
    print("Realistic UGC Visual Style System")
    print("=" * 50)

    style = get_realistic_style()

    # Test style prefix
    print("\nBase Style Prefix:")
    print(style.get_style_prefix())

    # Test prompt enhancement
    test_prompt = "Woman applying skincare serum to face"
    enhanced = style.enhance_prompt(
        test_prompt,
        shot_type=RealisticShotType.MIRROR,
        lighting=LightingPreset.BATHROOM,
        include_skin_detail=True,
        model_description="young woman, 25-30 years old, natural makeup",
    )
    print(f"\nOriginal: {test_prompt}")
    print(f"\nEnhanced:\n{enhanced}")

    # Test environment setups
    print("\n\nEnvironment Setups:")
    for env in ["studio", "bathroom", "lifestyle", "outdoor"]:
        setup = style.get_environment_setup(env)
        print(f"  {env}: {setup['description']}")

    # Test convenience function
    print("\n\nConvenience Function Test:")
    result = enhance_brand_visual(
        "Showing vitamin C serum bottle",
        environment="bathroom",
        include_model=True,
        model_description="female influencer, natural look",
    )
    print(result[:200] + "...")
