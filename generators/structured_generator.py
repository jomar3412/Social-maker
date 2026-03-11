"""
Structured Content Generator

Generates content based on clarified inputs from the ClarificationGate.
Outputs content in clearly separated sections.
"""

import json
import random
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from generators.clarification_gate import (
    ClarificationGate,
    StructuredOutput,
    Niche,
    MotivationTone,
    QuoteType,
    VoiceoverStyle,
    TimeSlot,
)

PROJECT_ROOT = Path(__file__).parent.parent
CONTENT_BANK_FILE = PROJECT_ROOT / "content_bank.json"


class StructuredContentGenerator:
    """
    Generates structured content based on clarified parameters.

    Ensures all outputs include:
    - Hook
    - Full Script
    - Caption
    - Hashtags
    - Visual Direction
    - Voice Direction
    - Posting Time Recommendation
    """

    def __init__(self, gate: ClarificationGate):
        if not gate.is_ready():
            raise ValueError("ClarificationGate is not ready. Complete clarification first.")

        self.gate = gate
        self.params = gate.get_generation_params()
        self.content_bank = self._load_content_bank()

    def _load_content_bank(self) -> dict:
        """Load content bank."""
        if CONTENT_BANK_FILE.exists():
            with open(CONTENT_BANK_FILE) as f:
                return json.load(f)
        return {"motivation": [], "fact": [], "health": []}

    def generate(self) -> StructuredOutput:
        """Generate structured content based on clarified parameters."""
        niche = self.params.get("niche")

        if niche == "motivation":
            return self._generate_motivation()
        elif niche == "facts":
            return self._generate_facts()
        elif niche == "finance":
            return self._generate_finance()
        elif niche == "fitness":
            return self._generate_fitness()
        elif niche == "random":
            return self._generate_random()
        elif niche == "custom":
            return self._generate_custom()
        else:
            raise ValueError(f"Unknown niche: {niche}")

    def _generate_motivation(self) -> StructuredOutput:
        """Generate motivation content with all structured sections."""
        motivation_params = self.params.get("motivation", {})
        tone = motivation_params.get("tone", "generic_affirmation")
        quote_type = motivation_params.get("quote_type", "original")
        voiceover_style = motivation_params.get("voiceover_style", "neutral_ai")
        posting_time = motivation_params.get("posting_time")
        time_slot = motivation_params.get("time_slot", "auto")

        # Map tone to script_type in content bank
        tone_to_script_type = {
            "generic_affirmation": "affirming",
            "aggressive_gym": "aggressive_energy",
            "calm_reflective": "calm_minimal",
            "spiritual": "calm_minimal",
            "business_focused": "future_accountability",
        }
        target_script_type = tone_to_script_type.get(tone, "affirming")

        # Find matching content from bank
        available = self.content_bank.get("motivation", [])
        matching = [c for c in available if c.get("script_type") == target_script_type]

        if not matching:
            matching = available  # Fallback to all available

        if not matching:
            # Generate placeholder if no content available
            return self._generate_motivation_placeholder(motivation_params)

        content = random.choice(matching)

        # Build visual direction based on tone
        visual_direction = self._get_visual_direction_for_tone(tone)

        # Build voice direction based on style and tone
        voice_direction = self._get_voice_direction(voiceover_style, tone, content)

        # Calculate posting time
        if not posting_time:
            posting_time = self._calculate_posting_recommendation(time_slot)

        output = StructuredOutput(
            hook=content.get("hook", ""),
            full_script=content.get("voiceover", ""),
            caption=content.get("caption", ""),
            hashtags=content.get("hashtags", []),
            visual_direction=visual_direction,
            voice_direction=voice_direction,
            posting_time_recommendation=posting_time,
            niche="motivation",
            tone=tone,
            quote_type=quote_type,
            generation_params=self.params,
        )

        return output

    def _generate_motivation_placeholder(self, params: Dict[str, Any]) -> StructuredOutput:
        """Generate placeholder motivation content when bank is empty."""
        tone = params.get("tone", "generic_affirmation")

        # Placeholder content based on tone
        placeholders = {
            "generic_affirmation": {
                "hook": "You did good today. Really good.",
                "script": "You did good today. You might not see it. But every step forward matters. You're building something. Keep going.",
            },
            "aggressive_gym": {
                "hook": "Wake up! Today is the day!",
                "script": "No excuses! Get up and make it happen! Your future self is watching what you do right now. Make them proud!",
            },
            "calm_reflective": {
                "hook": "Today is a new day.",
                "script": "Take a breath. You've been through a lot. And you're still here. That matters. Let this moment be enough.",
            },
            "spiritual": {
                "hook": "The universe is always speaking to you.",
                "script": "Listen closely. Everything is connected. Your journey has purpose. Trust the path you're on.",
            },
            "business_focused": {
                "hook": "One year from now, you'll wish you started today.",
                "script": "Every successful person started somewhere. The difference? They started. What are you waiting for?",
            },
        }

        placeholder = placeholders.get(tone, placeholders["generic_affirmation"])

        return StructuredOutput(
            hook=placeholder["hook"],
            full_script=placeholder["script"],
            caption="You needed to hear this today.",
            hashtags=["#motivation", "#mindset", "#dailyreminder"],
            visual_direction=self._get_visual_direction_for_tone(tone),
            voice_direction=self._get_voice_direction(
                params.get("voiceover_style", "neutral_ai"),
                tone,
                {}
            ),
            posting_time_recommendation=self._calculate_posting_recommendation(
                params.get("time_slot", "auto")
            ),
            niche="motivation",
            tone=tone,
            quote_type=params.get("quote_type", "original"),
            generation_params=params,
        )

    def _get_visual_direction_for_tone(self, tone: str) -> str:
        """Get visual direction based on tone."""
        directions = {
            "generic_affirmation": (
                "Warm, soft visuals. Sunrise/sunset shots. Person walking alone on beach or mountain. "
                "Soft color grading (warm tones). Slow pans. Nature close-ups. "
                "Text overlays: key phrases in clean sans-serif font, subtle fade-in animations."
            ),
            "aggressive_gym": (
                "High contrast, dark visuals. Gym footage, weights, sweat. "
                "Fast cuts, zoom effects. Flash transitions. "
                "Bold, impact text - large, caps, shake effects on key words. "
                "Color grading: high contrast, desaturated with red/orange highlights."
            ),
            "calm_reflective": (
                "Serene, peaceful imagery. Rain on windows, ocean waves, forest paths. "
                "Very slow motion. Minimal text, soft fade transitions. "
                "Muted, cool color palette. Soft vignette. "
                "Text: elegant serif font, subtle opacity."
            ),
            "spiritual": (
                "Ethereal visuals. Space imagery, stars, cosmic scenes. Light rays, meditation poses. "
                "Smooth, flowing transitions. Soft glow effects. "
                "Text: flowing script or minimal modern font. Light flares."
            ),
            "business_focused": (
                "Urban cityscapes, office environments, success imagery. "
                "Time-lapse cities, business meetings, modern architecture. "
                "Clean, professional transitions. "
                "Text: bold sans-serif, corporate colors. Stats and numbers highlighted."
            ),
        }
        return directions.get(tone, directions["generic_affirmation"])

    def _get_voice_direction(
        self,
        voiceover_style: str,
        tone: str,
        content: dict
    ) -> str:
        """Get voice direction based on style and tone."""
        # Check if content has its own voice direction
        if content.get("voice_direction"):
            return content["voice_direction"]

        style_directions = {
            "neutral_ai": "Clean, clear AI voice. Professional pacing. Neutral emotion.",
            "deep_motivational": "Rich, deep voice. Slow, deliberate pacing. Emphasis on key phrases. Slight pauses for impact.",
            "energetic": "Fast-paced, high energy. Enthusiastic delivery. Rising intonation. Short punchy phrases.",
            "text_only": "NO VOICEOVER. Text-only display. Sync text reveals with background music beats.",
        }

        tone_modifications = {
            "generic_affirmation": " Warm undertone. Supportive and encouraging.",
            "aggressive_gym": " Intense. Commanding. Yelling energy on key phrases.",
            "calm_reflective": " Very slow. Soft. Almost whispered in places.",
            "spiritual": " Ethereal quality. Gentle but profound.",
            "business_focused": " Confident. Authoritative. Matter-of-fact.",
        }

        base = style_directions.get(voiceover_style, style_directions["neutral_ai"])
        modification = tone_modifications.get(tone, "")

        return base + modification

    def _calculate_posting_recommendation(self, time_slot: str) -> str:
        """Calculate posting time recommendation."""
        now = datetime.now()

        slot_times = {
            "morning": ("8:00 AM - 9:00 AM", 8),
            "midday": ("11:00 AM - 12:00 PM", 11),
            "after_work": ("5:00 PM - 6:00 PM", 17),
            "night": ("9:00 PM - 10:00 PM", 21),
        }

        if time_slot == "auto":
            current_hour = now.hour

            # Find next available slot
            for slot_name, (_, hour) in slot_times.items():
                if current_hour < hour:
                    slot_info = slot_times[slot_name]
                    return f"Recommended: {slot_info[0]} today ({slot_name} slot)"

            # Past all slots, recommend tomorrow morning
            return "Recommended: 8:00 AM - 9:00 AM tomorrow (morning slot)"

        if time_slot in slot_times:
            slot_info = slot_times[time_slot]
            return f"Selected: {slot_info[0]} ({time_slot} slot)"

        return f"Custom time: {time_slot}"

    def _generate_facts(self) -> StructuredOutput:
        """Generate facts content."""
        available = self.content_bank.get("fact", [])

        if not available:
            return StructuredOutput(
                hook="Did you know?",
                full_script="Here's something incredible you probably didn't know...",
                caption="Save this for later!",
                hashtags=["#facts", "#didyouknow", "#learning"],
                visual_direction="Educational visuals. Infographic style. Text reveals synced with narration.",
                voice_direction="Clear, engaging narrator voice. Curious tone. Building excitement.",
                posting_time_recommendation=self._calculate_posting_recommendation("auto"),
                niche="facts",
                generation_params=self.params,
            )

        content = random.choice(available)

        return StructuredOutput(
            hook=content.get("hook", ""),
            full_script=content.get("voiceover", ""),
            caption=content.get("caption", ""),
            hashtags=content.get("hashtags", []),
            visual_direction=(
                "Educational B-roll matching the topic. Text callouts for key facts. "
                "Numbers and stats highlighted with motion graphics. "
                "Clean transitions, subtle zoom on important visuals."
            ),
            voice_direction="Engaging narrator. Building curiosity. Emphasis on surprising facts. Clear articulation.",
            posting_time_recommendation=self._calculate_posting_recommendation("auto"),
            niche="facts",
            generation_params=self.params,
        )

    def _generate_finance(self) -> StructuredOutput:
        """Generate finance content."""
        return StructuredOutput(
            hook="This one money rule changed everything for me.",
            full_script=(
                "This one money rule changed everything for me. "
                "Most people focus on making more money. But the wealthy focus on keeping it. "
                "Pay yourself first. Before bills, before expenses, before anything else. "
                "Even if it's just 10%. That small habit, compounded over time, "
                "is the difference between retiring at 40 or working until 70. "
                "Start today. Your future self is counting on it."
            ),
            caption="The money rule that changes everything.",
            hashtags=["#finance", "#moneytips", "#investing", "#wealth", "#financialfreedom"],
            visual_direction=(
                "Clean, professional visuals. Money/growth imagery. "
                "Charts and graphs (animated). Calculator, savings growth visualization. "
                "Text: key numbers and percentages highlighted."
            ),
            voice_direction="Confident, authoritative. Educational but not condescending. Clear and deliberate.",
            posting_time_recommendation=self._calculate_posting_recommendation("auto"),
            niche="finance",
            generation_params=self.params,
        )

    def _generate_fitness(self) -> StructuredOutput:
        """Generate fitness content."""
        return StructuredOutput(
            hook="Stop making this workout mistake.",
            full_script=(
                "Stop making this workout mistake. "
                "You're not training hard. You're training wrong. "
                "More reps won't help if your form is broken. "
                "Slow down. Focus on the muscle, not the movement. "
                "Quality over quantity. Every single time. "
                "Your body doesn't count reps. It counts tension. "
                "Master the basics. Everything else follows."
            ),
            caption="Quality over quantity. Always.",
            hashtags=["#fitness", "#gym", "#workout", "#gains", "#fitnessmotivation"],
            visual_direction=(
                "Gym footage. Proper form demonstrations. "
                "Slow-motion muscle engagement. Before/after comparison cuts. "
                "High contrast, dramatic lighting."
            ),
            voice_direction="Intense but educational. Authoritative. Coach-like delivery.",
            posting_time_recommendation=self._calculate_posting_recommendation("auto"),
            niche="fitness",
            generation_params=self.params,
        )

    def _generate_random(self) -> StructuredOutput:
        """Generate random content from any niche."""
        niches = ["motivation", "facts"]
        chosen_niche = random.choice(niches)

        if chosen_niche == "motivation":
            available = self.content_bank.get("motivation", [])
            if available:
                content = random.choice(available)
                return StructuredOutput(
                    hook=content.get("hook", ""),
                    full_script=content.get("voiceover", ""),
                    caption=content.get("caption", ""),
                    hashtags=content.get("hashtags", []),
                    visual_direction=self._get_visual_direction_for_tone("generic_affirmation"),
                    voice_direction=content.get("voice_direction", "Calm, warm, supportive."),
                    posting_time_recommendation=self._calculate_posting_recommendation("auto"),
                    niche="motivation (random)",
                    generation_params=self.params,
                )

        elif chosen_niche == "facts":
            return self._generate_facts()

        return self._generate_motivation_placeholder({"tone": "generic_affirmation"})

    def _generate_custom(self) -> StructuredOutput:
        """Generate custom niche content."""
        custom_niche = self.params.get("custom_niche", "general")
        custom_instructions = self.params.get("custom_instructions", "")

        return StructuredOutput(
            hook=f"[Custom: {custom_niche}] Hook goes here.",
            full_script=f"[Custom content for {custom_niche}]. Instructions: {custom_instructions}",
            caption=f"Custom content for {custom_niche}.",
            hashtags=[f"#{custom_niche.replace(' ', '')}", "#custom", "#content"],
            visual_direction=f"Visuals matching {custom_niche} theme. {custom_instructions}",
            voice_direction="To be determined based on custom niche requirements.",
            posting_time_recommendation=self._calculate_posting_recommendation("auto"),
            niche=f"custom: {custom_niche}",
            generation_params=self.params,
        )


def generate_with_clarification(gate: ClarificationGate) -> StructuredOutput:
    """
    Main entry point for structured generation with clarification.

    Args:
        gate: A fully clarified ClarificationGate

    Returns:
        StructuredOutput with all required sections
    """
    if not gate.is_ready():
        missing = gate.request.get_missing_inputs()
        raise ValueError(f"Clarification incomplete. Missing: {missing}")

    generator = StructuredContentGenerator(gate)
    return generator.generate()


# CLI interface
if __name__ == "__main__":
    from generators.clarification_gate import run_interactive_clarification

    print("\n" + "=" * 60)
    print("STRUCTURED CONTENT GENERATOR")
    print("=" * 60)

    # Run clarification
    gate = run_interactive_clarification()

    if gate.is_ready():
        # Generate content
        output = generate_with_clarification(gate)

        # Display structured output
        print(output.to_formatted_string())

        # Also save to file
        output_file = PROJECT_ROOT / "output" / "last_generated.json"
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, "w") as f:
            f.write(output.to_json())
        print(f"\nSaved to: {output_file}")
    else:
        print("\nClarification incomplete. Cannot generate.")
        print(json.dumps(gate.get_status(), indent=2))
