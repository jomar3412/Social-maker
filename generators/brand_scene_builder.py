"""
Brand Scene Builder

Generates photorealistic prompts for brand/UGC content using
the realistic-prompt-builder agent. This module orchestrates
the visual direction generation for brand content.

AGENT INTEGRATION:
- ALWAYS invokes realistic-prompt-builder for brand content
- No opt-out - agent is the primary source for photorealistic prompts
- Built-in prompts only used as emergency fallback if agent fails

Pipeline Flow:
1. ClarificationGate -> Collect brand requirements
2. ScriptGenerator -> Generate brand script with CTA
3. BrandSceneBuilder -> Create scene breakdown
4. [realistic-prompt-builder agent] -> Generate photorealistic prompts  <- HERE
5. Video Model (Nano Banana / Pro) -> Generate AI video clips
6. VideoAssembler -> Combine into final video
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional

from generators.brand_config import BrandConfig
from generators.scene_builder import Scene, TextAnimation
from generators.realistic_style import (
    RealisticStyle,
    get_realistic_style,
    enhance_brand_visual,
    get_video_model_triggers,
    RealisticShotType,
    LightingPreset,
)


class VideoModelProvider(Enum):
    """
    Supported AI video generation models.

    Model-agnostic design to support future providers.
    """
    NANO_BANANA = "nano_banana"
    NANO_BANANA_PRO = "nano_banana_pro"
    # Future models can be added here
    # RUNWAY = "runway"
    # PIKA = "pika"
    # SORA = "sora"


# Model-specific settings
VIDEO_MODEL_SETTINGS = {
    VideoModelProvider.NANO_BANANA: {
        "max_duration": 8,
        "resolution": "1080x1920",
        "format": "vertical",
        "quality": "standard",
    },
    VideoModelProvider.NANO_BANANA_PRO: {
        "max_duration": 16,
        "resolution": "1080x1920",
        "format": "vertical",
        "quality": "high",
    },
}


def _invoke_realistic_prompt_builder(
    agent_prompt: str,
    timeout_seconds: int = 120,
) -> Optional[List[str]]:
    """
    Invoke the realistic-prompt-builder agent via Claude Code's Task tool.

    This function is called during content generation to get
    photorealistic prompts from the specialized agent.

    Args:
        agent_prompt: The prompt/context to send to the agent
        timeout_seconds: Maximum time to wait for agent response

    Returns:
        List of enhanced photorealistic prompts, or None if failed
    """
    # Note: In actual execution, this would be called via the Task tool
    # from the CLI or pipeline. This function documents the interface.
    #
    # The realistic-prompt-builder agent receives:
    # - Product/brand info
    # - Visual environment and placement style
    # - Model/avatar requirements
    # - Scene descriptions with voiceover text
    # - Target video model
    #
    # And returns scene-by-scene photorealistic prompts with:
    # - Camera language (lens, aperture, focus)
    # - Professional lighting terminology
    # - Skin/texture detail instructions
    # - Composition guidance
    # - Model-specific optimizations

    # This is a placeholder - actual invocation happens through CLI/Task tool
    print(f"  [Agent] realistic-prompt-builder invocation requested")
    print(f"  [Agent] Prompt length: {len(agent_prompt)} chars")
    return None


def _fallback_prompt_generation(
    brand_config: BrandConfig,
    scenes: List[Scene],
    model: VideoModelProvider,
) -> List[str]:
    """
    Emergency fallback prompt generation when agent fails.

    Only used if realistic-prompt-builder agent is unavailable.
    Uses built-in RealisticStyle for basic photorealistic prompts.
    """
    print("  [Fallback] Using built-in realistic style (agent unavailable)")

    style = get_realistic_style()
    prompts = []

    # Get environment setup
    env = brand_config.visual_environment.value if brand_config.visual_environment else "lifestyle"
    env_setup = style.get_environment_setup(env)

    # Get model triggers
    triggers = get_video_model_triggers(model.value)

    for i, scene in enumerate(scenes):
        # Build model description if needed
        model_desc = None
        if brand_config.model_requirements:
            model_desc = brand_config.model_requirements.to_prompt()

        # Create base visual direction
        visual_base = f"{brand_config.product_name} {brand_config.product_placement.value if brand_config.product_placement else 'in use'}"

        # Enhance with realistic style
        enhanced = style.enhance_prompt(
            visual_direction=visual_base,
            shot_type=env_setup["shot_type"],
            lighting=env_setup["lighting"],
            include_skin_detail=model_desc is not None,
            model_description=model_desc,
        )

        # Add scene-specific context
        if scene.voiceover_text:
            enhanced += f", scene context: {scene.voiceover_text[:100]}"

        # Add video model positive triggers
        enhanced += ", " + ", ".join(triggers["positive"])

        prompts.append(enhanced)

    return prompts


def build_agent_context(
    brand_config: BrandConfig,
    scenes: List[Scene],
    model: VideoModelProvider = VideoModelProvider.NANO_BANANA_PRO,
) -> str:
    """
    Build context string for realistic-prompt-builder agent.

    This creates the comprehensive prompt that the agent uses to
    generate photorealistic visual directions.

    Args:
        brand_config: Complete brand configuration
        scenes: List of scenes with voiceover text
        model: Target video model

    Returns:
        Formatted context string for the agent
    """
    # Prepare scene data
    scene_data = []
    for i, scene in enumerate(scenes):
        scene_data.append({
            "scene_number": scene.scene_number,
            "voiceover_text": scene.voiceover_text,
            "on_screen_text": scene.on_screen_text,
            "duration": scene.duration,
        })

    # Build comprehensive context
    context = f"""
Create photorealistic AI image/video prompts for {model.value}:

BRAND INFORMATION:
- Brand: {brand_config.brand_name}
- Product: {brand_config.product_name}
- Category: {brand_config.product_category or 'general'}
- Key Benefits: {', '.join(brand_config.key_benefits) if brand_config.key_benefits else 'N/A'}

VISUAL REQUIREMENTS:
- Environment: {brand_config.visual_environment.value if brand_config.visual_environment else 'lifestyle'}
- Product Placement: {brand_config.product_placement.value if brand_config.product_placement else 'in_use'}
- Script Type: {brand_config.script_type.value if brand_config.script_type else 'product_review'}

MODEL/AVATAR REQUIREMENTS:
{brand_config.model_requirements.to_prompt() if brand_config.model_requirements else 'Include realistic human model with natural skin texture'}

SCENES TO GENERATE PROMPTS FOR:
{json.dumps(scene_data, indent=2)}

GENERATION RULES:
1. Generate UGC-style photorealistic prompts with:
   - Camera language (focal length, aperture, depth of field)
   - Professional lighting terms (softbox, natural window light, etc.)
   - Skin texture and imperfection details for authenticity
   - Natural, authentic feel - NOT overly polished

2. Each prompt should be optimized for vertical 9:16 format

3. Include iPhone 14 Pro camera aesthetic for authentic UGC look

4. Model-specific optimizations for: {model.value}
   - Prioritize natural movement and realistic skin
   - Avoid CGI/3D/cartoon aesthetics

5. Maintain visual consistency across all scenes:
   - Same lighting style
   - Same color grading
   - Same model appearance
   - Same environment details

OUTPUT FORMAT:
Return a list of prompts, one per scene, in JSON format:
[
  "Scene 1 prompt...",
  "Scene 2 prompt...",
  ...
]
"""
    return context


def generate_brand_prompts(
    brand_config: BrandConfig,
    scenes: List[Scene],
    model: VideoModelProvider = VideoModelProvider.NANO_BANANA_PRO,
    use_agent: bool = True,
) -> List[str]:
    """
    Generate photorealistic prompts for brand content.

    Uses realistic-prompt-builder agent to create prompts
    optimized for the target video model (Nano Banana by default).

    Args:
        brand_config: Complete brand configuration
        scenes: List of Scene objects to generate prompts for
        model: Target video model provider
        use_agent: Whether to use the agent (default True, always use)

    Returns:
        List of photorealistic prompts, one per scene
    """
    print(f"\n  Generating brand prompts for {len(scenes)} scenes...")
    print(f"  Video model: {model.value}")
    print(f"  Environment: {brand_config.visual_environment.value if brand_config.visual_environment else 'lifestyle'}")

    if use_agent:
        # Build context for agent
        agent_context = build_agent_context(brand_config, scenes, model)

        # Attempt to invoke agent
        agent_result = _invoke_realistic_prompt_builder(agent_context)

        if agent_result:
            print(f"  [Agent] Generated {len(agent_result)} prompts")
            return agent_result
        else:
            print("  [Agent] No response, using fallback")

    # Fallback to built-in generation
    return _fallback_prompt_generation(brand_config, scenes, model)


def generate_brand_scenes(
    brand_config: BrandConfig,
    script_text: str,
    word_timing: List[Dict] = None,
) -> List[Scene]:
    """
    Generate scene breakdown for brand content.

    Creates scenes optimized for brand storytelling with
    appropriate structure based on script type.

    Args:
        brand_config: Complete brand configuration
        script_text: Full script/voiceover text
        word_timing: Optional word timing data from voice generation

    Returns:
        List of Scene objects
    """
    # Get script structure
    structure = brand_config.get_script_structure()
    sections = structure.get("sections", ["hook", "body", "cta"])
    duration = brand_config.get_duration_seconds()

    # Calculate section durations
    section_count = len(sections)
    base_duration = duration / section_count

    scenes = []
    current_time = 0.0

    # Split script into sections
    script_parts = script_text.split('\n')
    if len(script_parts) < section_count:
        # Pad with empty strings
        script_parts.extend([''] * (section_count - len(script_parts)))

    for i, section in enumerate(sections):
        scene_duration = base_duration
        # Hook is shorter, CTA is shorter
        if section == "hook":
            scene_duration = min(5.0, base_duration)
        elif section == "cta":
            scene_duration = min(5.0, base_duration)

        # Get appropriate text animation
        if section == "hook":
            animation = TextAnimation.SCALE_POP
        elif section == "cta":
            animation = TextAnimation.ZOOM_IN
        else:
            animation = TextAnimation.FADE_IN

        # Get script for this section
        script_part = script_parts[i] if i < len(script_parts) else ""

        scene = Scene(
            scene_number=i + 1,
            on_screen_text=script_part[:50] if script_part else section.replace("_", " ").title(),
            voiceover_text=script_part,
            visual_direction=f"{section} scene for {brand_config.product_name}",
            text_animation=animation,
            duration=scene_duration,
            start_time=current_time,
            end_time=current_time + scene_duration,
            tone="brand",
        )
        scenes.append(scene)
        current_time += scene_duration

    return scenes


def get_model_settings(model: VideoModelProvider) -> Dict[str, Any]:
    """Get settings for a specific video model."""
    return VIDEO_MODEL_SETTINGS.get(model, VIDEO_MODEL_SETTINGS[VideoModelProvider.NANO_BANANA_PRO])


def format_brand_prompt_report(
    brand_config: BrandConfig,
    scenes: List[Scene],
    prompts: List[str],
) -> str:
    """Format brand prompts as a readable report."""
    lines = [
        "# Brand Content Prompt Report",
        "",
        f"**Brand:** {brand_config.brand_name}",
        f"**Product:** {brand_config.product_name}",
        f"**Environment:** {brand_config.visual_environment.value if brand_config.visual_environment else 'lifestyle'}",
        f"**Total Scenes:** {len(scenes)}",
        "",
    ]

    for i, (scene, prompt) in enumerate(zip(scenes, prompts)):
        lines.extend([
            f"## Scene {scene.scene_number}",
            f"**Duration:** {scene.duration:.1f}s",
            f"**Voiceover:** {scene.voiceover_text[:100]}{'...' if len(scene.voiceover_text) > 100 else ''}",
            "",
            f"**Visual Prompt:**",
            f"```",
            prompt,
            f"```",
            "",
        ])

    return "\n".join(lines)


if __name__ == "__main__":
    from generators.brand_config import (
        CampaignObjective, VisualEnvironment, ProductPlacement,
        VoiceoverStyle, ScriptType, ContentLength, ModelRequirements,
    )

    print("Testing Brand Scene Builder")
    print("=" * 50)

    # Create test config
    config = BrandConfig(
        brand_name="GlowSkin",
        product_name="Vitamin C Serum",
        product_category="skincare",
        objective=CampaignObjective.CONVERSION,
        visual_environment=VisualEnvironment.BATHROOM,
        product_placement=ProductPlacement.IN_USE,
        voiceover_style=VoiceoverStyle.CONVERSATIONAL,
        script_type=ScriptType.PRODUCT_REVIEW,
        content_length=ContentLength.MEDIUM_30S,
        key_benefits=["Brightens skin", "Reduces dark spots"],
        model_requirements=ModelRequirements(
            gender="female",
            age_range="25-35",
            style="casual",
        ),
    )

    # Generate scenes
    test_script = """Finally found a vitamin C serum that actually works.
I've been using this for 2 weeks and my dark spots are fading.
The texture is light, not greasy at all.
Look at the difference - link in bio to get yours."""

    scenes = generate_brand_scenes(config, test_script)
    print(f"\nGenerated {len(scenes)} scenes")

    # Generate prompts (fallback mode for testing)
    prompts = generate_brand_prompts(
        config, scenes,
        model=VideoModelProvider.NANO_BANANA_PRO,
        use_agent=False,  # Use fallback for testing
    )

    # Print report
    print("\n" + format_brand_prompt_report(config, scenes, prompts))

    # Print agent context (for reference)
    print("\n" + "=" * 50)
    print("AGENT CONTEXT (what realistic-prompt-builder receives):")
    print("=" * 50)
    print(build_agent_context(config, scenes))
