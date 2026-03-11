"""
Clarification Gate System

Implements a structured clarification phase before content generation.
Ensures all required inputs are confirmed before proceeding.
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum


class Niche(Enum):
    MOTIVATION = "motivation"
    FACTS = "facts"
    FINANCE = "finance"
    FITNESS = "fitness"
    BRAND = "brand"
    SHORT_STORIES = "short_stories"
    RANDOM = "random"
    CUSTOM = "custom"


class TimeSlot(Enum):
    MORNING = "morning"  # 8-9 AM
    MIDDAY = "midday"  # 11-12 PM
    AFTER_WORK = "after_work"  # 5-6 PM
    NIGHT = "night"  # 9-10 PM
    AUTO = "auto"


class MotivationTone(Enum):
    GENERIC_AFFIRMATION = "generic_affirmation"
    AGGRESSIVE_GYM = "aggressive_gym"
    CALM_REFLECTIVE = "calm_reflective"
    SPIRITUAL = "spiritual"
    BUSINESS_FOCUSED = "business_focused"


class QuoteType(Enum):
    ORIGINAL = "original"
    REAL_PERSON = "real_person"
    MIX = "mix"


class VoiceoverStyle(Enum):
    NEUTRAL_AI = "neutral_ai"
    DEEP_MOTIVATIONAL = "deep_motivational"
    ENERGETIC = "energetic"
    TEXT_ONLY = "text_only"


@dataclass
class MotivationConfig:
    """Configuration specific to motivation niche."""
    time_slot: Optional[TimeSlot] = None
    tone: Optional[MotivationTone] = None
    quote_type: Optional[QuoteType] = None
    voiceover_style: Optional[VoiceoverStyle] = None
    calculated_posting_time: Optional[str] = None

    def is_complete(self) -> bool:
        return all([
            self.time_slot is not None,
            self.tone is not None,
            self.quote_type is not None,
            self.voiceover_style is not None
        ])

    def get_missing_fields(self) -> List[str]:
        missing = []
        if self.time_slot is None:
            missing.append("time_slot")
        if self.tone is None:
            missing.append("tone")
        if self.quote_type is None:
            missing.append("quote_type")
        if self.voiceover_style is None:
            missing.append("voiceover_style")
        return missing


@dataclass
class FactsConfig:
    """Configuration specific to facts niche."""
    category: Optional[str] = None  # science, history, nature, space, etc.
    complexity: Optional[str] = None  # simple, detailed, deep-dive
    voiceover_style: Optional[VoiceoverStyle] = None

    def is_complete(self) -> bool:
        return self.voiceover_style is not None

    def get_missing_fields(self) -> List[str]:
        missing = []
        if self.voiceover_style is None:
            missing.append("voiceover_style")
        return missing


@dataclass
class FinanceConfig:
    """Configuration specific to finance niche."""
    topic: Optional[str] = None  # investing, saving, crypto, budgeting, etc.
    audience: Optional[str] = None  # beginner, intermediate, advanced
    tone: Optional[str] = None  # educational, motivational, cautionary
    voiceover_style: Optional[VoiceoverStyle] = None

    def is_complete(self) -> bool:
        return self.voiceover_style is not None

    def get_missing_fields(self) -> List[str]:
        missing = []
        if self.voiceover_style is None:
            missing.append("voiceover_style")
        return missing


@dataclass
class FitnessConfig:
    """Configuration specific to fitness niche."""
    focus: Optional[str] = None  # motivation, tips, workout, nutrition
    intensity: Optional[str] = None  # beginner, intermediate, advanced
    tone: Optional[str] = None  # encouraging, intense, educational
    voiceover_style: Optional[VoiceoverStyle] = None

    def is_complete(self) -> bool:
        return self.voiceover_style is not None

    def get_missing_fields(self) -> List[str]:
        missing = []
        if self.voiceover_style is None:
            missing.append("voiceover_style")
        return missing


class StoryGenre(Enum):
    THRILLER = "thriller"
    MYSTERY = "mystery"
    COMEDY = "comedy"
    HORROR = "horror"
    DRAMA = "drama"
    ROMANCE = "romance"


class StoryEndingType(Enum):
    TWIST = "twist"
    CLIFFHANGER = "cliffhanger"
    RESOLUTION = "resolution"
    OPEN_ENDED = "open_ended"
    CALLBACK = "callback"


class StoryOrchestrationMode(Enum):
    QUICK = "quick"
    DETAILED = "detailed"


@dataclass
class StoryConfig:
    """Configuration specific to short_stories niche."""
    genre: Optional[StoryGenre] = None
    ending_type: Optional[StoryEndingType] = None
    orchestration_mode: Optional[StoryOrchestrationMode] = None
    series_name: Optional[str] = None
    continue_from: Optional[str] = None  # Story ID to continue
    voiceover_style: Optional[VoiceoverStyle] = None
    topic: Optional[str] = None

    def is_complete(self) -> bool:
        return all([
            self.genre is not None,
            self.voiceover_style is not None
        ])

    def get_missing_fields(self) -> List[str]:
        missing = []
        if self.genre is None:
            missing.append("genre")
        if self.voiceover_style is None:
            missing.append("voiceover_style")
        return missing


# Import BrandConfig from brand_config module
try:
    from generators.brand_config import BrandConfig
except ImportError:
    # Fallback for when running from different context
    BrandConfig = None


@dataclass
class ContentRequest:
    """Complete content generation request with all clarified inputs."""
    niche: Optional[Niche] = None
    motivation_config: Optional[MotivationConfig] = None
    facts_config: Optional[FactsConfig] = None
    finance_config: Optional[FinanceConfig] = None
    fitness_config: Optional[FitnessConfig] = None
    brand_config: Optional["BrandConfig"] = None  # Brand/UGC content config
    story_config: Optional[StoryConfig] = None  # Short stories config
    custom_niche_name: Optional[str] = None
    custom_instructions: Optional[str] = None
    additional_constraints: Optional[str] = None
    clarification_complete: bool = False

    def is_ready_for_generation(self) -> bool:
        """Check if all required inputs are confirmed."""
        if self.niche is None:
            return False

        if self.niche == Niche.RANDOM:
            return True  # Random can proceed without niche-specific questions

        if self.niche == Niche.MOTIVATION:
            if self.motivation_config is None:
                return False
            return self.motivation_config.is_complete()

        if self.niche == Niche.FACTS:
            if self.facts_config is None:
                return False
            return self.facts_config.is_complete()

        if self.niche == Niche.FINANCE:
            if self.finance_config is None:
                return False
            return self.finance_config.is_complete()

        if self.niche == Niche.FITNESS:
            if self.fitness_config is None:
                return False
            return self.fitness_config.is_complete()

        if self.niche == Niche.BRAND:
            if self.brand_config is None:
                return False
            return self.brand_config.is_complete()

        if self.niche == Niche.SHORT_STORIES:
            if self.story_config is None:
                return False
            return self.story_config.is_complete()

        if self.niche == Niche.CUSTOM:
            return self.custom_niche_name is not None

        return False

    def get_missing_inputs(self) -> Dict[str, Any]:
        """Return what inputs are still needed."""
        missing = {"niche": None, "niche_config": [], "final_clarification": False}

        if self.niche is None:
            missing["niche"] = "required"
            return missing

        if self.niche == Niche.MOTIVATION:
            if self.motivation_config:
                missing["niche_config"] = self.motivation_config.get_missing_fields()
            else:
                missing["niche_config"] = ["time_slot", "tone", "quote_type", "voiceover_style"]

        elif self.niche == Niche.FACTS:
            if self.facts_config:
                missing["niche_config"] = self.facts_config.get_missing_fields()
            else:
                missing["niche_config"] = ["voiceover_style"]

        elif self.niche == Niche.FINANCE:
            if self.finance_config:
                missing["niche_config"] = self.finance_config.get_missing_fields()
            else:
                missing["niche_config"] = ["voiceover_style"]

        elif self.niche == Niche.FITNESS:
            if self.fitness_config:
                missing["niche_config"] = self.fitness_config.get_missing_fields()
            else:
                missing["niche_config"] = ["voiceover_style"]

        elif self.niche == Niche.BRAND:
            if self.brand_config:
                missing["niche_config"] = self.brand_config.get_missing_fields()
            else:
                missing["niche_config"] = [
                    "brand_name", "product_name", "objective",
                    "visual_environment", "product_placement", "voiceover_style"
                ]

        elif self.niche == Niche.SHORT_STORIES:
            if self.story_config:
                missing["niche_config"] = self.story_config.get_missing_fields()
            else:
                missing["niche_config"] = ["genre", "voiceover_style"]

        elif self.niche == Niche.CUSTOM:
            if not self.custom_niche_name:
                missing["niche_config"] = ["custom_niche_name"]

        if not self.clarification_complete:
            missing["final_clarification"] = True

        return missing

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "niche": self.niche.value if self.niche else None,
            "custom_niche_name": self.custom_niche_name,
            "custom_instructions": self.custom_instructions,
            "additional_constraints": self.additional_constraints,
            "clarification_complete": self.clarification_complete,
        }

        if self.motivation_config:
            result["motivation_config"] = {
                "time_slot": self.motivation_config.time_slot.value if self.motivation_config.time_slot else None,
                "tone": self.motivation_config.tone.value if self.motivation_config.tone else None,
                "quote_type": self.motivation_config.quote_type.value if self.motivation_config.quote_type else None,
                "voiceover_style": self.motivation_config.voiceover_style.value if self.motivation_config.voiceover_style else None,
                "calculated_posting_time": self.motivation_config.calculated_posting_time,
            }

        return result


class ClarificationGate:
    """
    Manages the clarification flow before content generation.

    Flow:
    1. Identify niche
    2. Trigger niche-specific question set if required
    3. Confirm all required inputs
    4. Ask for final clarification
    5. Generate structured output
    """

    def __init__(self):
        self.request = ContentRequest()
        self.current_step = "niche_selection"

    def get_niche_options(self) -> List[Dict[str, str]]:
        """Return available niche options."""
        return [
            {"value": "motivation", "label": "Motivation", "description": "Inspirational content for daily motivation"},
            {"value": "facts", "label": "Facts", "description": "Did you know? Fun facts and trivia"},
            {"value": "finance", "label": "Finance", "description": "Money, investing, and financial wisdom"},
            {"value": "fitness", "label": "Fitness", "description": "Workout motivation and health tips"},
            {"value": "brand", "label": "Brand", "description": "Photorealistic UGC ads and product content"},
            {"value": "short_stories", "label": "Short Stories", "description": "Thriller, mystery, comedy, horror stories"},
            {"value": "random", "label": "Random", "description": "Let the system choose - skip niche questions"},
            {"value": "custom", "label": "Custom", "description": "Define your own niche"},
        ]

    def set_niche(self, niche_value: str) -> bool:
        """Set the niche and return success status."""
        try:
            self.request.niche = Niche(niche_value)

            # Initialize niche-specific config
            if self.request.niche == Niche.MOTIVATION:
                self.request.motivation_config = MotivationConfig()
                self.current_step = "motivation_questions"
            elif self.request.niche == Niche.FACTS:
                self.request.facts_config = FactsConfig()
                self.current_step = "facts_questions"
            elif self.request.niche == Niche.FINANCE:
                self.request.finance_config = FinanceConfig()
                self.current_step = "finance_questions"
            elif self.request.niche == Niche.FITNESS:
                self.request.fitness_config = FitnessConfig()
                self.current_step = "fitness_questions"
            elif self.request.niche == Niche.BRAND:
                if BrandConfig:
                    self.request.brand_config = BrandConfig()
                self.current_step = "brand_questions"
            elif self.request.niche == Niche.SHORT_STORIES:
                self.request.story_config = StoryConfig()
                self.current_step = "story_questions"
            elif self.request.niche == Niche.RANDOM:
                self.current_step = "final_clarification"
            elif self.request.niche == Niche.CUSTOM:
                self.current_step = "custom_niche_input"

            return True
        except ValueError:
            return False

    def get_motivation_questions(self) -> List[Dict[str, Any]]:
        """Return motivation-specific questions."""
        return [
            {
                "id": "time_slot",
                "question": "What time slot are you targeting?",
                "type": "single_choice",
                "options": [
                    {"value": "morning", "label": "Morning (8-9 AM)", "description": "Start the day strong"},
                    {"value": "midday", "label": "Midday (11 AM-12 PM)", "description": "Midday motivation boost"},
                    {"value": "after_work", "label": "After Work (5-6 PM)", "description": "Post-work wind down"},
                    {"value": "night", "label": "Night (9-10 PM)", "description": "Reflective evening content"},
                    {"value": "auto", "label": "Auto-select", "description": "System calculates optimal slot"},
                ],
                "required": True,
            },
            {
                "id": "tone",
                "question": "What tone should the content have?",
                "type": "single_choice",
                "options": [
                    {"value": "generic_affirmation", "label": "Generic Affirmation", "description": "Warm, supportive, universal"},
                    {"value": "aggressive_gym", "label": "Aggressive / Gym Energy", "description": "High energy, intense, push hard"},
                    {"value": "calm_reflective", "label": "Calm Reflective", "description": "Peaceful, thoughtful, introspective"},
                    {"value": "spiritual", "label": "Spiritual", "description": "Soul-focused, deeper meaning"},
                    {"value": "business_focused", "label": "Business-Focused", "description": "Success, hustle, entrepreneurship"},
                ],
                "required": True,
            },
            {
                "id": "quote_type",
                "question": "What type of quote/message?",
                "type": "single_choice",
                "options": [
                    {"value": "original", "label": "Original Quote", "description": "AI-generated original message"},
                    {"value": "real_person", "label": "Real Person Quote", "description": "Quote from a known figure"},
                    {"value": "mix", "label": "Mix", "description": "Combination of both styles"},
                ],
                "required": True,
            },
            {
                "id": "voiceover_style",
                "question": "What voiceover style?",
                "type": "single_choice",
                "options": [
                    {"value": "neutral_ai", "label": "Neutral AI", "description": "Clean, professional AI voice"},
                    {"value": "deep_motivational", "label": "Deep Motivational", "description": "Rich, inspiring voice"},
                    {"value": "energetic", "label": "Energetic", "description": "Fast-paced, high energy"},
                    {"value": "text_only", "label": "Text Only", "description": "No voiceover, just text on screen"},
                ],
                "required": True,
            },
        ]

    def set_motivation_config(
        self,
        time_slot: Optional[str] = None,
        tone: Optional[str] = None,
        quote_type: Optional[str] = None,
        voiceover_style: Optional[str] = None,
    ) -> bool:
        """Set motivation-specific configuration."""
        if not self.request.motivation_config:
            self.request.motivation_config = MotivationConfig()

        config = self.request.motivation_config

        if time_slot:
            config.time_slot = TimeSlot(time_slot)
            if config.time_slot == TimeSlot.AUTO:
                config.calculated_posting_time = self._calculate_optimal_posting_time()

        if tone:
            config.tone = MotivationTone(tone)

        if quote_type:
            config.quote_type = QuoteType(quote_type)

        if voiceover_style:
            config.voiceover_style = VoiceoverStyle(voiceover_style)

        if config.is_complete():
            self.current_step = "final_clarification"

        return True

    def get_brand_questions(self) -> List[Dict[str, Any]]:
        """Return brand-specific questions for UGC/ad content."""
        return [
            {
                "id": "brand_name",
                "question": "What is the brand name?",
                "type": "text_input",
                "required": True,
            },
            {
                "id": "product_name",
                "question": "What is the product name?",
                "type": "text_input",
                "required": True,
            },
            {
                "id": "objective",
                "question": "What is the campaign objective?",
                "type": "single_choice",
                "options": [
                    {"value": "awareness", "label": "Brand Awareness", "description": "Build recognition and reach"},
                    {"value": "conversion", "label": "Conversion", "description": "Drive sales and signups"},
                    {"value": "engagement", "label": "Engagement", "description": "Encourage interaction and shares"},
                ],
                "required": True,
            },
            {
                "id": "visual_environment",
                "question": "What visual environment/setting?",
                "type": "single_choice",
                "options": [
                    {"value": "studio", "label": "Studio", "description": "Clean professional backdrop"},
                    {"value": "lifestyle", "label": "Lifestyle", "description": "Natural home/daily setting"},
                    {"value": "outdoor", "label": "Outdoor", "description": "Natural outdoor setting"},
                    {"value": "bathroom", "label": "Bathroom", "description": "Skincare/beauty setting"},
                    {"value": "kitchen", "label": "Kitchen", "description": "Food/cooking setting"},
                    {"value": "gym", "label": "Gym", "description": "Fitness/athletic setting"},
                ],
                "required": True,
            },
            {
                "id": "product_placement",
                "question": "How should the product be shown?",
                "type": "single_choice",
                "options": [
                    {"value": "hero_shot", "label": "Hero Shot", "description": "Product as main focus"},
                    {"value": "in_use", "label": "In Use", "description": "Product being actively used"},
                    {"value": "flat_lay", "label": "Flat Lay", "description": "Product arranged from above"},
                    {"value": "unboxing", "label": "Unboxing", "description": "Opening/revealing product"},
                ],
                "required": True,
            },
            {
                "id": "voiceover_style",
                "question": "What voiceover style?",
                "type": "single_choice",
                "options": [
                    {"value": "conversational", "label": "Conversational", "description": "Casual, like talking to a friend"},
                    {"value": "enthusiastic", "label": "Enthusiastic", "description": "Excited, high energy"},
                    {"value": "calm_soothing", "label": "Calm & Soothing", "description": "Relaxed, ASMR-like"},
                    {"value": "professional", "label": "Professional", "description": "Polished, authoritative"},
                    {"value": "text_only", "label": "Text Only", "description": "No voiceover, just on-screen text"},
                ],
                "required": True,
            },
            {
                "id": "cta_type",
                "question": "What call-to-action?",
                "type": "single_choice",
                "options": [
                    {"value": "shop_now", "label": "Shop Now", "description": "Direct purchase CTA"},
                    {"value": "link_in_bio", "label": "Link in Bio", "description": "Profile link CTA"},
                    {"value": "learn_more", "label": "Learn More", "description": "Information/education CTA"},
                    {"value": "comment", "label": "Comment", "description": "Engagement CTA"},
                ],
                "required": False,
            },
        ]

    def set_brand_config(
        self,
        brand_name: Optional[str] = None,
        product_name: Optional[str] = None,
        objective: Optional[str] = None,
        visual_environment: Optional[str] = None,
        product_placement: Optional[str] = None,
        voiceover_style: Optional[str] = None,
        cta_type: Optional[str] = None,
        script_type: Optional[str] = None,
        content_length: Optional[str] = None,
    ) -> bool:
        """Set brand-specific configuration."""
        if not BrandConfig:
            print("Warning: BrandConfig not available")
            return False

        if not self.request.brand_config:
            self.request.brand_config = BrandConfig()

        config = self.request.brand_config

        # Import brand enums
        from generators.brand_config import (
            CampaignObjective, VisualEnvironment, ProductPlacement,
            VoiceoverStyle as BrandVoiceoverStyle, CTAType, ScriptType, ContentLength,
        )

        if brand_name:
            config.brand_name = brand_name

        if product_name:
            config.product_name = product_name

        if objective:
            config.objective = CampaignObjective(objective)

        if visual_environment:
            config.visual_environment = VisualEnvironment(visual_environment)

        if product_placement:
            config.product_placement = ProductPlacement(product_placement)

        if voiceover_style:
            config.voiceover_style = BrandVoiceoverStyle(voiceover_style)

        if cta_type:
            config.cta_type = CTAType(cta_type)

        if script_type:
            config.script_type = ScriptType(script_type)

        if content_length:
            config.content_length = ContentLength(content_length)

        if config.is_complete():
            self.current_step = "final_clarification"

        return True

    def get_story_questions(self) -> List[Dict[str, Any]]:
        """Return short_stories-specific questions."""
        return [
            {
                "id": "genre",
                "question": "What genre should the story be?",
                "type": "single_choice",
                "options": [
                    {"value": "thriller", "label": "Thriller", "description": "Suspenseful with tension and unexpected reveals"},
                    {"value": "mystery", "label": "Mystery", "description": "Puzzle-driven with clues and revelations"},
                    {"value": "comedy", "label": "Comedy", "description": "Light-hearted with humor and punchlines"},
                    {"value": "horror", "label": "Horror", "description": "Scary stories designed to unsettle"},
                    {"value": "drama", "label": "Drama", "description": "Emotionally driven character stories"},
                    {"value": "romance", "label": "Romance", "description": "Love stories with emotional connection"},
                ],
                "required": True,
            },
            {
                "id": "ending_type",
                "question": "What type of ending?",
                "type": "single_choice",
                "options": [
                    {"value": "twist", "label": "Twist", "description": "Shocking reveal that recontextualizes the story"},
                    {"value": "cliffhanger", "label": "Cliffhanger", "description": "Leave viewers wanting more (Part 2?)"},
                    {"value": "resolution", "label": "Resolution", "description": "Satisfying closure"},
                    {"value": "open_ended", "label": "Open Ended", "description": "Leave interpretation to viewer"},
                ],
                "required": False,
            },
            {
                "id": "orchestration_mode",
                "question": "Production mode?",
                "type": "single_choice",
                "options": [
                    {"value": "quick", "label": "Quick", "description": "Automated end-to-end with stock visuals"},
                    {"value": "detailed", "label": "Detailed", "description": "Step-by-step with manual Midjourney for visuals"},
                ],
                "required": False,
            },
            {
                "id": "voiceover_style",
                "question": "What voiceover style?",
                "type": "single_choice",
                "options": [
                    {"value": "deep_motivational", "label": "Deep Narrative", "description": "Rich, immersive storytelling voice"},
                    {"value": "neutral_ai", "label": "Neutral AI", "description": "Clean, professional narration"},
                    {"value": "energetic", "label": "Energetic", "description": "Fast-paced, dynamic delivery"},
                    {"value": "text_only", "label": "Text Only", "description": "No voiceover, just text on screen"},
                ],
                "required": True,
            },
        ]

    def set_story_config(
        self,
        genre: Optional[str] = None,
        ending_type: Optional[str] = None,
        orchestration_mode: Optional[str] = None,
        voiceover_style: Optional[str] = None,
        series_name: Optional[str] = None,
        continue_from: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> bool:
        """Set story-specific configuration."""
        if not self.request.story_config:
            self.request.story_config = StoryConfig()

        config = self.request.story_config

        if genre:
            config.genre = StoryGenre(genre)

        if ending_type:
            config.ending_type = StoryEndingType(ending_type)

        if orchestration_mode:
            config.orchestration_mode = StoryOrchestrationMode(orchestration_mode)

        if voiceover_style:
            config.voiceover_style = VoiceoverStyle(voiceover_style)

        if series_name:
            config.series_name = series_name

        if continue_from:
            config.continue_from = continue_from

        if topic:
            config.topic = topic

        if config.is_complete():
            self.current_step = "final_clarification"

        return True

    def _calculate_optimal_posting_time(self) -> str:
        """Calculate the next optimal posting window based on current time."""
        now = datetime.now()
        current_hour = now.hour

        # Define posting windows with their start hours
        windows = [
            (8, "Morning (8-9 AM)"),
            (11, "Midday (11 AM-12 PM)"),
            (17, "After Work (5-6 PM)"),
            (21, "Night (9-10 PM)"),
        ]

        # Find the next available window
        for window_hour, window_name in windows:
            if current_hour < window_hour:
                target_time = now.replace(hour=window_hour, minute=0, second=0, microsecond=0)
                return f"{window_name} - {target_time.strftime('%Y-%m-%d %H:%M')}"

        # If past all windows today, schedule for tomorrow morning
        tomorrow = now + timedelta(days=1)
        target_time = tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)
        return f"Morning (8-9 AM) - {target_time.strftime('%Y-%m-%d %H:%M')}"

    def set_final_clarification(self, additional_constraints: Optional[str] = None) -> bool:
        """Set final clarification and mark clarification as complete."""
        self.request.additional_constraints = additional_constraints
        self.request.clarification_complete = True
        self.current_step = "ready_for_generation"
        return True

    def get_final_clarification_prompt(self) -> str:
        """Return the final clarification prompt."""
        return (
            "If you have any additional constraints, tone preferences, "
            "or niche-specific instructions, please specify them now before generation.\n\n"
            "Leave blank to proceed with current settings."
        )

    def is_ready(self) -> bool:
        """Check if ready for content generation."""
        return (
            self.request.is_ready_for_generation()
            and self.request.clarification_complete
        )

    def get_status(self) -> Dict[str, Any]:
        """Return current clarification status."""
        return {
            "current_step": self.current_step,
            "is_ready": self.is_ready(),
            "request": self.request.to_dict(),
            "missing_inputs": self.request.get_missing_inputs(),
        }

    def get_generation_params(self) -> Dict[str, Any]:
        """Return parameters for content generation."""
        if not self.is_ready():
            raise ValueError("Clarification not complete. Cannot generate.")

        params = {
            "niche": self.request.niche.value,
            "additional_constraints": self.request.additional_constraints,
        }

        if self.request.niche == Niche.MOTIVATION and self.request.motivation_config:
            config = self.request.motivation_config
            params["motivation"] = {
                "time_slot": config.time_slot.value if config.time_slot else None,
                "tone": config.tone.value if config.tone else None,
                "quote_type": config.quote_type.value if config.quote_type else None,
                "voiceover_style": config.voiceover_style.value if config.voiceover_style else None,
                "posting_time": config.calculated_posting_time,
            }

        if self.request.niche == Niche.CUSTOM:
            params["custom_niche"] = self.request.custom_niche_name
            params["custom_instructions"] = self.request.custom_instructions

        return params


@dataclass
class StructuredOutput:
    """Structured output format for generated content."""
    hook: str = ""
    full_script: str = ""
    caption: str = ""
    hashtags: List[str] = field(default_factory=list)
    visual_direction: str = ""
    voice_direction: str = ""
    posting_time_recommendation: str = ""

    # Additional metadata
    niche: str = ""
    tone: str = ""
    quote_type: str = ""
    generation_params: Dict[str, Any] = field(default_factory=dict)

    def to_formatted_string(self) -> str:
        """Return formatted output with clear section labels."""
        sections = []

        sections.append("=" * 60)
        sections.append("GENERATED CONTENT")
        sections.append("=" * 60)

        sections.append("\n--- HOOK ---")
        sections.append(self.hook)

        sections.append("\n--- FULL SCRIPT ---")
        sections.append(self.full_script)

        sections.append("\n--- CAPTION ---")
        sections.append(self.caption)

        sections.append("\n--- HASHTAGS ---")
        sections.append(" ".join(self.hashtags))

        sections.append("\n--- VISUAL DIRECTION ---")
        sections.append(self.visual_direction)

        sections.append("\n--- VOICE DIRECTION ---")
        sections.append(self.voice_direction)

        sections.append("\n--- POSTING TIME RECOMMENDATION ---")
        sections.append(self.posting_time_recommendation)

        sections.append("\n" + "=" * 60)

        return "\n".join(sections)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hook": self.hook,
            "full_script": self.full_script,
            "caption": self.caption,
            "hashtags": self.hashtags,
            "visual_direction": self.visual_direction,
            "voice_direction": self.voice_direction,
            "posting_time_recommendation": self.posting_time_recommendation,
            "metadata": {
                "niche": self.niche,
                "tone": self.tone,
                "quote_type": self.quote_type,
                "generation_params": self.generation_params,
            },
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


def run_interactive_clarification() -> ClarificationGate:
    """
    Run interactive clarification flow in CLI.
    Returns configured ClarificationGate ready for generation.
    """
    gate = ClarificationGate()

    print("\n" + "=" * 60)
    print("CONTENT GENERATION - CLARIFICATION PHASE")
    print("=" * 60)

    # Step 1: Niche Selection
    print("\nWhat niche would you like to create content for?\n")
    for i, option in enumerate(gate.get_niche_options(), 1):
        print(f"  {i}. {option['label']}: {option['description']}")

    while gate.request.niche is None:
        try:
            choice = input("\nEnter number (1-8): ").strip()
            niche_map = {
                "1": "motivation",
                "2": "facts",
                "3": "finance",
                "4": "fitness",
                "5": "brand",
                "6": "short_stories",
                "7": "random",
                "8": "custom",
            }
            if choice in niche_map:
                gate.set_niche(niche_map[choice])
            else:
                print("Invalid choice. Please enter 1-8.")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return gate

    # Step 2: Niche-specific questions
    if gate.request.niche == Niche.MOTIVATION:
        print("\n--- MOTIVATION SETTINGS ---\n")

        questions = gate.get_motivation_questions()

        for q in questions:
            print(f"\n{q['question']}\n")
            for i, opt in enumerate(q["options"], 1):
                print(f"  {i}. {opt['label']}: {opt['description']}")

            while True:
                try:
                    choice = input(f"\nEnter number (1-{len(q['options'])}): ").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(q["options"]):
                        value = q["options"][idx]["value"]
                        gate.set_motivation_config(**{q["id"]: value})
                        break
                    else:
                        print(f"Invalid choice. Please enter 1-{len(q['options'])}.")
                except (ValueError, KeyboardInterrupt):
                    print("Invalid input.")

    elif gate.request.niche == Niche.BRAND:
        print("\n--- BRAND CONTENT SETTINGS ---\n")
        print("Creating photorealistic UGC/ad content...")

        # Text inputs
        brand_name = input("Brand name: ").strip()
        product_name = input("Product name: ").strip()

        gate.set_brand_config(brand_name=brand_name, product_name=product_name)

        questions = gate.get_brand_questions()
        # Skip text input questions (already handled)
        choice_questions = [q for q in questions if q.get("type") == "single_choice"]

        for q in choice_questions:
            print(f"\n{q['question']}\n")
            for i, opt in enumerate(q["options"], 1):
                print(f"  {i}. {opt['label']}: {opt['description']}")

            while True:
                try:
                    choice = input(f"\nEnter number (1-{len(q['options'])}): ").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(q["options"]):
                        value = q["options"][idx]["value"]
                        gate.set_brand_config(**{q["id"]: value})
                        break
                    else:
                        print(f"Invalid choice. Please enter 1-{len(q['options'])}.")
                except (ValueError, KeyboardInterrupt):
                    print("Invalid input.")

    elif gate.request.niche == Niche.SHORT_STORIES:
        print("\n--- SHORT STORIES SETTINGS ---\n")

        questions = gate.get_story_questions()

        for q in questions:
            print(f"\n{q['question']}\n")
            for i, opt in enumerate(q["options"], 1):
                print(f"  {i}. {opt['label']}: {opt['description']}")

            while True:
                try:
                    choice = input(f"\nEnter number (1-{len(q['options'])}): ").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(q["options"]):
                        value = q["options"][idx]["value"]
                        gate.set_story_config(**{q["id"]: value})
                        break
                    else:
                        print(f"Invalid choice. Please enter 1-{len(q['options'])}.")
                except (ValueError, KeyboardInterrupt):
                    print("Invalid input.")

        # Optional: Ask for topic
        topic = input("\nStory topic/seed (optional, press Enter to skip): ").strip()
        if topic:
            gate.set_story_config(topic=topic)

    elif gate.request.niche == Niche.CUSTOM:
        print("\n--- CUSTOM NICHE ---\n")
        gate.request.custom_niche_name = input("Enter your custom niche name: ").strip()
        gate.request.custom_instructions = input("Enter any specific instructions: ").strip()
        gate.current_step = "final_clarification"

    # Step 3: Final clarification
    if gate.request.niche != Niche.RANDOM:
        print("\n--- FINAL CLARIFICATION ---\n")
        print(gate.get_final_clarification_prompt())
        additional = input("\nAdditional constraints (or press Enter to skip): ").strip()
        gate.set_final_clarification(additional if additional else None)
    else:
        gate.set_final_clarification(None)

    print("\n" + "=" * 60)
    print("CLARIFICATION COMPLETE - Ready for generation")
    print("=" * 60)

    return gate


# CLI test
if __name__ == "__main__":
    gate = run_interactive_clarification()
    print("\nGeneration Parameters:")
    print(json.dumps(gate.get_generation_params(), indent=2))
