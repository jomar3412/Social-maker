"""
Brand Content Configuration

Defines all configuration options for brand/UGC content generation:
- Campaign objectives (awareness, conversion, engagement)
- CTA types (shop_now, learn_more, swipe_up, link_in_bio)
- Visual environments (studio, lifestyle, outdoor, home, office)
- Product placements (hero_shot, in_use, flat_lay, unboxing)
- Content lengths (15s, 30s, 60s)

This module provides the data structures needed for photorealistic
UGC-style advertisements, product shots, and influencer content.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class CampaignObjective(Enum):
    """Campaign marketing objectives."""
    AWARENESS = "awareness"
    CONVERSION = "conversion"
    ENGAGEMENT = "engagement"


class CTAType(Enum):
    """Call-to-action types for brand content."""
    SHOP_NOW = "shop_now"
    LEARN_MORE = "learn_more"
    SWIPE_UP = "swipe_up"
    LINK_IN_BIO = "link_in_bio"
    COMMENT = "comment"
    SAVE = "save"


class VisualEnvironment(Enum):
    """Visual environment/setting for brand content."""
    STUDIO = "studio"
    LIFESTYLE = "lifestyle"
    OUTDOOR = "outdoor"
    HOME = "home"
    OFFICE = "office"
    GYM = "gym"
    CAFE = "cafe"
    BATHROOM = "bathroom"
    KITCHEN = "kitchen"


class ProductPlacement(Enum):
    """How the product is shown in the content."""
    HERO_SHOT = "hero_shot"
    IN_USE = "in_use"
    FLAT_LAY = "flat_lay"
    UNBOXING = "unboxing"
    BEFORE_AFTER = "before_after"
    COMPARISON = "comparison"


class ContentLength(Enum):
    """Content duration options."""
    SHORT_15S = "15s"
    MEDIUM_30S = "30s"
    LONG_60S = "60s"


class ScriptType(Enum):
    """Brand content script types."""
    PRODUCT_REVIEW = "product_review"
    UNBOXING = "unboxing"
    LIFESTYLE_INTEGRATION = "lifestyle_integration"
    PROBLEM_SOLUTION = "problem_solution"
    TUTORIAL = "tutorial"
    TESTIMONIAL = "testimonial"


class VoiceoverStyle(Enum):
    """Voiceover styles for brand content."""
    CONVERSATIONAL = "conversational"
    ENTHUSIASTIC = "enthusiastic"
    CALM_SOOTHING = "calm_soothing"
    PROFESSIONAL = "professional"
    TEXT_ONLY = "text_only"


@dataclass
class ModelRequirements:
    """Requirements for human models in brand content."""
    gender: Optional[str] = None  # male, female, any
    age_range: Optional[str] = None  # e.g., "25-35"
    ethnicity: Optional[str] = None  # diverse, specific
    style: Optional[str] = None  # casual, professional, athletic
    skin_detail: bool = True  # Include realistic skin texture

    def to_prompt(self) -> str:
        """Convert requirements to prompt description."""
        parts = []
        if self.gender and self.gender != "any":
            parts.append(self.gender)
        if self.age_range:
            parts.append(f"{self.age_range} years old")
        if self.style:
            parts.append(f"{self.style} style")
        if self.skin_detail:
            parts.append("realistic skin with natural texture and pores")
        return ", ".join(parts) if parts else "photorealistic person"


@dataclass
class BrandConfig:
    """
    Configuration specific to brand/UGC content.

    Follows the pattern from MotivationConfig with is_complete()
    and get_missing_fields() methods for clarification gate.
    """
    # Required fields
    brand_name: Optional[str] = None
    product_name: Optional[str] = None
    product_category: Optional[str] = None  # skincare, tech, fashion, food, etc.

    # Content settings
    script_type: Optional[ScriptType] = None
    objective: Optional[CampaignObjective] = None
    cta_type: Optional[CTAType] = None
    content_length: Optional[ContentLength] = None

    # Visual settings
    visual_environment: Optional[VisualEnvironment] = None
    product_placement: Optional[ProductPlacement] = None

    # Voice settings
    voiceover_style: Optional[VoiceoverStyle] = None

    # Model/avatar settings
    model_requirements: Optional[ModelRequirements] = None

    # Additional context
    key_benefits: List[str] = field(default_factory=list)
    target_audience: Optional[str] = None
    brand_guidelines: Optional[str] = None

    def is_complete(self) -> bool:
        """Check if all required fields are set."""
        return all([
            self.brand_name is not None,
            self.product_name is not None,
            self.objective is not None,
            self.visual_environment is not None,
            self.product_placement is not None,
            self.voiceover_style is not None,
        ])

    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields."""
        missing = []
        if self.brand_name is None:
            missing.append("brand_name")
        if self.product_name is None:
            missing.append("product_name")
        if self.objective is None:
            missing.append("objective")
        if self.visual_environment is None:
            missing.append("visual_environment")
        if self.product_placement is None:
            missing.append("product_placement")
        if self.voiceover_style is None:
            missing.append("voiceover_style")
        return missing

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "brand_name": self.brand_name,
            "product_name": self.product_name,
            "product_category": self.product_category,
            "script_type": self.script_type.value if self.script_type else None,
            "objective": self.objective.value if self.objective else None,
            "cta_type": self.cta_type.value if self.cta_type else None,
            "content_length": self.content_length.value if self.content_length else None,
            "visual_environment": self.visual_environment.value if self.visual_environment else None,
            "product_placement": self.product_placement.value if self.product_placement else None,
            "voiceover_style": self.voiceover_style.value if self.voiceover_style else None,
            "model_requirements": self.model_requirements.to_prompt() if self.model_requirements else None,
            "key_benefits": self.key_benefits,
            "target_audience": self.target_audience,
            "brand_guidelines": self.brand_guidelines,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BrandConfig":
        """Create from dictionary."""
        config = cls()
        config.brand_name = data.get("brand_name")
        config.product_name = data.get("product_name")
        config.product_category = data.get("product_category")

        if data.get("script_type"):
            config.script_type = ScriptType(data["script_type"])
        if data.get("objective"):
            config.objective = CampaignObjective(data["objective"])
        if data.get("cta_type"):
            config.cta_type = CTAType(data["cta_type"])
        if data.get("content_length"):
            config.content_length = ContentLength(data["content_length"])
        if data.get("visual_environment"):
            config.visual_environment = VisualEnvironment(data["visual_environment"])
        if data.get("product_placement"):
            config.product_placement = ProductPlacement(data["product_placement"])
        if data.get("voiceover_style"):
            config.voiceover_style = VoiceoverStyle(data["voiceover_style"])

        config.key_benefits = data.get("key_benefits", [])
        config.target_audience = data.get("target_audience")
        config.brand_guidelines = data.get("brand_guidelines")

        return config

    def get_duration_seconds(self) -> int:
        """Get content duration in seconds."""
        duration_map = {
            ContentLength.SHORT_15S: 15,
            ContentLength.MEDIUM_30S: 30,
            ContentLength.LONG_60S: 60,
        }
        return duration_map.get(self.content_length, 30)

    def get_script_structure(self) -> Dict[str, str]:
        """Get script structure based on script type."""
        structures = {
            ScriptType.PRODUCT_REVIEW: {
                "description": "Honest product review style",
                "structure": "Problem -> Discovery -> Demo -> Result",
                "sections": ["hook", "problem", "discovery", "demonstration", "result", "cta"],
            },
            ScriptType.UNBOXING: {
                "description": "First impressions and reactions",
                "structure": "Anticipation -> Reveal -> Details -> Verdict",
                "sections": ["hook", "anticipation", "reveal", "details", "verdict", "cta"],
            },
            ScriptType.LIFESTYLE_INTEGRATION: {
                "description": "Product naturally in daily routine",
                "structure": "Day in Life -> Problem Moment -> Product Use -> Benefit",
                "sections": ["hook", "day_intro", "problem_moment", "product_use", "benefit", "cta"],
            },
            ScriptType.PROBLEM_SOLUTION: {
                "description": "Classic problem-solution format",
                "structure": "Pain Point -> Failed Attempts -> Solution -> Transformation",
                "sections": ["hook", "pain_point", "failed_attempts", "solution", "transformation", "cta"],
            },
            ScriptType.TUTORIAL: {
                "description": "How-to demonstration",
                "structure": "Goal -> Steps -> Tips -> Result",
                "sections": ["hook", "goal", "step1", "step2", "step3", "tips", "result", "cta"],
            },
            ScriptType.TESTIMONIAL: {
                "description": "Personal experience story",
                "structure": "Before -> Journey -> After -> Recommendation",
                "sections": ["hook", "before", "journey", "after", "recommendation", "cta"],
            },
        }
        return structures.get(self.script_type, structures[ScriptType.PRODUCT_REVIEW])


# Convenience functions for CLI and quick access
def get_objective_options() -> List[Dict[str, str]]:
    """Return objective options for CLI/UI."""
    return [
        {"value": "awareness", "label": "Brand Awareness", "description": "Build recognition and reach"},
        {"value": "conversion", "label": "Conversion", "description": "Drive sales and signups"},
        {"value": "engagement", "label": "Engagement", "description": "Encourage interaction and shares"},
    ]


def get_environment_options() -> List[Dict[str, str]]:
    """Return environment options for CLI/UI."""
    return [
        {"value": "studio", "label": "Studio", "description": "Clean professional backdrop"},
        {"value": "lifestyle", "label": "Lifestyle", "description": "Natural home/daily setting"},
        {"value": "outdoor", "label": "Outdoor", "description": "Natural outdoor setting"},
        {"value": "home", "label": "Home", "description": "Cozy home environment"},
        {"value": "office", "label": "Office", "description": "Professional workspace"},
        {"value": "gym", "label": "Gym", "description": "Fitness/athletic setting"},
        {"value": "cafe", "label": "Cafe", "description": "Casual coffee shop vibe"},
        {"value": "bathroom", "label": "Bathroom", "description": "Skincare/beauty setting"},
        {"value": "kitchen", "label": "Kitchen", "description": "Food/cooking setting"},
    ]


def get_placement_options() -> List[Dict[str, str]]:
    """Return product placement options for CLI/UI."""
    return [
        {"value": "hero_shot", "label": "Hero Shot", "description": "Product as main focus"},
        {"value": "in_use", "label": "In Use", "description": "Product being actively used"},
        {"value": "flat_lay", "label": "Flat Lay", "description": "Product arranged from above"},
        {"value": "unboxing", "label": "Unboxing", "description": "Opening/revealing product"},
        {"value": "before_after", "label": "Before/After", "description": "Transformation comparison"},
        {"value": "comparison", "label": "Comparison", "description": "Product vs alternatives"},
    ]


def get_cta_options() -> List[Dict[str, str]]:
    """Return CTA options for CLI/UI."""
    return [
        {"value": "shop_now", "label": "Shop Now", "description": "Direct purchase CTA"},
        {"value": "learn_more", "label": "Learn More", "description": "Information/education CTA"},
        {"value": "swipe_up", "label": "Swipe Up", "description": "Stories link CTA"},
        {"value": "link_in_bio", "label": "Link in Bio", "description": "Profile link CTA"},
        {"value": "comment", "label": "Comment", "description": "Engagement CTA"},
        {"value": "save", "label": "Save", "description": "Save for later CTA"},
    ]


def get_script_type_options() -> List[Dict[str, str]]:
    """Return script type options for CLI/UI."""
    return [
        {"value": "product_review", "label": "Product Review", "description": "Honest review format"},
        {"value": "unboxing", "label": "Unboxing", "description": "First impressions reveal"},
        {"value": "lifestyle_integration", "label": "Lifestyle Integration", "description": "Product in daily routine"},
        {"value": "problem_solution", "label": "Problem Solution", "description": "Pain point -> Solution"},
        {"value": "tutorial", "label": "Tutorial", "description": "How-to demonstration"},
        {"value": "testimonial", "label": "Testimonial", "description": "Personal experience story"},
    ]


if __name__ == "__main__":
    # Test BrandConfig
    print("Testing BrandConfig...")

    config = BrandConfig(
        brand_name="GlowSkin",
        product_name="Vitamin C Serum",
        product_category="skincare",
        objective=CampaignObjective.CONVERSION,
        visual_environment=VisualEnvironment.BATHROOM,
        product_placement=ProductPlacement.IN_USE,
        voiceover_style=VoiceoverStyle.CONVERSATIONAL,
        script_type=ScriptType.PRODUCT_REVIEW,
        cta_type=CTAType.SHOP_NOW,
        content_length=ContentLength.MEDIUM_30S,
        key_benefits=["Brightens skin", "Reduces dark spots", "Hydrates"],
        model_requirements=ModelRequirements(
            gender="female",
            age_range="25-35",
            style="casual",
            skin_detail=True,
        ),
    )

    print(f"\nIs complete: {config.is_complete()}")
    print(f"Missing fields: {config.get_missing_fields()}")
    print(f"Duration: {config.get_duration_seconds()}s")
    print(f"Script structure: {config.get_script_structure()}")
    print(f"\nConfig dict:\n{config.to_dict()}")
