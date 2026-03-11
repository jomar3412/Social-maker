"""
Stub provider for fast testing and development.

Returns predefined responses without external API calls.
"""

import time
import json
from pathlib import Path
from typing import Optional

from .base import (
    ContentProvider,
    ProviderConfig,
    GenerationResult,
)


class StubProvider(ContentProvider):
    """
    Stub provider that returns mock responses.

    Used for:
    - Testing the pipeline without API costs
    - Development and UI testing
    - Dry-run mode
    """

    def generate_script(
        self,
        run_id: str,
        niche: str,
        style: str,
        topic: Optional[str],
        output_dir: Path,
        loop_friendly_ending: bool = False,
    ) -> GenerationResult:
        """Generate a mock script."""
        start_time = time.time()

        # Simulate processing delay
        time.sleep(self.config.stub_delay_ms / 1000)
        self._report_progress("Research", 20)

        # Stage 1: Research (stub)
        research = self._stub_research(niche, topic)
        self._report_progress("Draft", 40)

        # Stage 2: Draft (stub)
        time.sleep(self.config.stub_delay_ms / 1000)
        draft = self._stub_draft(niche, style, research)
        self._report_progress("Hook Review", 60)

        # Stage 3: Hook Review (stub)
        time.sleep(self.config.stub_delay_ms / 1000)
        hook = self._stub_hook_review(draft)
        self._report_progress("Relevance", 75)

        # Stage 4: Relevance Check (stub)
        time.sleep(self.config.stub_delay_ms / 1000)
        relevance = self._stub_relevance(draft, niche, style)
        self._report_progress("Finalize", 90)

        # Stage 5: Finalize (stub)
        time.sleep(self.config.stub_delay_ms / 1000)
        final = self._stub_finalize(draft, hook)

        # Write outputs
        script_path = output_dir / "script.txt"
        script_path.write_text(final["script"])

        meta_path = output_dir / "script_meta.json"
        meta_path.write_text(json.dumps({
            "hook": final["hook"],
            "keywords": final["keywords"],
            "hashtags": final["hashtags"],
            "duration_estimate": final["duration_estimate"],
        }, indent=2))

        self._report_progress("Complete", 100)

        duration_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            success=True,
            output_files={
                "script": script_path,
                "script_meta": meta_path,
            },
            artifacts=final,
            duration_ms=duration_ms,
        )

    def regenerate_script(
        self,
        run_id: str,
        niche: str,
        style: str,
        prior_script: dict,
        feedback: Optional[str],
        output_dir: Path,
    ) -> GenerationResult:
        """Regenerate script with variations."""
        start_time = time.time()

        self._report_progress("Regenerating", 50)
        time.sleep(self.config.stub_delay_ms / 1000)

        # Get base script and modify slightly
        prior_hook = prior_script.get("hook", "")
        prior_body = prior_script.get("script", "")

        # Create variation
        if niche == "motivation":
            new_script = """Sometimes the bravest thing you can do is rest.

Not every day has to be a battle.
Not every moment needs to be a victory.

Today, you survived. You made it through.
That alone is enough.

Stop measuring yourself by productivity.
Start measuring yourself by presence.

You showed up. You're here.
That's the only metric that matters today."""
        else:
            new_script = """The human brain uses 20% of your body's energy.

That's more than any other organ.
Even when you're sleeping, it never stops working.

Every thought you have
triggers millions of neurons.
Every memory you form
reshapes your brain's structure.

You're not just thinking right now.
You're literally rebuilding your brain.

The most powerful computer in the world
is sitting between your ears."""

        final = {
            "script": new_script,
            "hook": new_script.split("\n")[0],
            "keywords": ["mindset", "rest", "presence", "growth"],
            "hashtags": ["#mindset", "#selfcare", "#growth", "#motivation"],
            "duration_estimate": len(new_script.split()) / 2.5,
            "regeneration_note": f"Based on feedback: {feedback}" if feedback else "Variation generated",
        }

        # Write outputs
        script_path = output_dir / "script.txt"
        script_path.write_text(final["script"])

        meta_path = output_dir / "script_meta.json"
        meta_path.write_text(json.dumps({
            "hook": final["hook"],
            "keywords": final["keywords"],
            "hashtags": final["hashtags"],
            "duration_estimate": final["duration_estimate"],
            "regeneration_note": final["regeneration_note"],
        }, indent=2))

        self._report_progress("Complete", 100)

        duration_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            success=True,
            output_files={
                "script": script_path,
                "script_meta": meta_path,
            },
            artifacts=final,
            duration_ms=duration_ms,
        )

    def generate_shot_list(
        self,
        run_id: str,
        script: dict,
        visual_mode: str,
        output_dir: Path,
    ) -> GenerationResult:
        """Generate shot list from script."""
        start_time = time.time()

        self._report_progress("Parsing beats", 30)
        time.sleep(self.config.stub_delay_ms / 1000)

        # Generate shot list
        shot_list = self._stub_shot_list(script, visual_mode)

        self._report_progress("Writing files", 80)

        # Write shot_list.json
        shot_list_path = output_dir / "shot_list.json"
        shot_list_path.write_text(json.dumps(shot_list, indent=2))

        # Write shot_list.md
        md_content = self._format_shot_list_md(shot_list)
        md_path = output_dir / "shot_list.md"
        md_path.write_text(md_content)

        self._report_progress("Complete", 100)

        duration_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            success=True,
            output_files={
                "shot_list": shot_list_path,
                "shot_list_md": md_path,
            },
            artifacts={"shot_list": shot_list},
            duration_ms=duration_ms,
        )

    def generate_visual_prompts(
        self,
        run_id: str,
        shot_list: dict,
        visual_mode: str,
        realism_mode: str,
        output_dir: Path,
    ) -> GenerationResult:
        """Generate NanoBanana prompts from shot list."""
        start_time = time.time()

        self._report_progress("Generating prompts", 50)
        time.sleep(self.config.stub_delay_ms / 1000)

        scenes = shot_list.get("shot_list", shot_list)
        if isinstance(scenes, dict):
            scenes = scenes.get("scenes", [])

        prompts = self._format_nanobanana_prompts(scenes, realism_mode)

        prompts_path = output_dir / "nanobanana_prompts.txt"
        prompts_path.write_text(prompts)

        self._report_progress("Complete", 100)

        duration_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            success=True,
            output_files={"nanobanana_prompts": prompts_path},
            artifacts={"prompts": prompts},
            duration_ms=duration_ms,
        )

    def generate_stock_queries(
        self,
        run_id: str,
        shot_list: dict,
        output_dir: Path,
    ) -> GenerationResult:
        """Generate stock footage search queries."""
        start_time = time.time()

        self._report_progress("Generating queries", 50)
        time.sleep(self.config.stub_delay_ms / 1000)

        scenes = shot_list.get("shot_list", shot_list)
        if isinstance(scenes, dict):
            scenes = scenes.get("scenes", [])

        queries = self._format_stock_queries(scenes)

        queries_path = output_dir / "stock_queries.txt"
        queries_path.write_text(queries)

        self._report_progress("Complete", 100)

        duration_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            success=True,
            output_files={"stock_queries": queries_path},
            artifacts={"queries": queries},
            duration_ms=duration_ms,
        )

    # === Internal stub methods ===

    def _stub_research(self, niche: str, topic: Optional[str]) -> dict:
        """Stub research response."""
        return {
            "topics": [
                "self-worth and daily progress",
                "acknowledging unseen struggles",
                "future self accountability",
            ],
            "trending": ["mindset shift", "daily reminder"],
            "avoid": ["toxic positivity", "hustle culture"],
        }

    def _stub_draft(self, niche: str, style: str, research: dict) -> dict:
        """Stub draft response."""
        if niche == "motivation":
            script = """You did good today. Really good.

You woke up when you didn't want to.
You kept going when everything felt heavy.
You showed up even when no one noticed.

That's not weakness. That's strength.
Real strength isn't always loud.
Sometimes it's just... getting through the day.

And you did that.
You're still here.
You're still fighting.

That matters more than you know.
So take a breath.
You earned it."""
        else:
            script = """Did you know that honey never spoils?

Archaeologists found 3,000-year-old honey in Egyptian tombs.
It was still perfectly edible.

The secret is honey's unique chemistry.
Low moisture content starves bacteria.
High acidity kills most microorganisms.
Natural hydrogen peroxide acts as a preservative.

Scientists call it "eternally fresh."
No other food on Earth can make this claim.

So the next time you see honey,
remember you're looking at something
that could outlast civilization itself."""

        return {
            "script": script,
            "word_count": len(script.split()),
            "estimated_duration": len(script.split()) / 2.5,
        }

    def _stub_hook_review(self, draft: dict) -> dict:
        """Stub hook review response."""
        lines = draft["script"].strip().split("\n")
        hook = lines[0] if lines else "You did good today."
        return {
            "hook": hook,
            "hook_type": "validation",
            "hook_score": 0.85,
            "suggestions": [],
        }

    def _stub_relevance(self, draft: dict, niche: str, style: str) -> dict:
        """Stub relevance check response."""
        return {
            "score": 0.92,
            "on_topic": True,
            "style_match": True,
            "issues": [],
        }

    def _stub_finalize(self, draft: dict, hook: dict) -> dict:
        """Stub finalize response."""
        return {
            "script": draft["script"],
            "hook": hook["hook"],
            "keywords": ["motivation", "self-worth", "daily reminder", "strength"],
            "hashtags": ["#motivation", "#mindset", "#dailyreminder", "#selflove"],
            "duration_estimate": draft["estimated_duration"],
        }

    def _split_script_into_segments(self, script: str, num_segments: int = 6) -> list[str]:
        """
        Split script into segments for beat assignment.

        Handles both multi-line scripts and single-paragraph scripts by:
        1. First trying to split by newlines
        2. If that yields too few segments, split by sentences
        3. Distribute segments evenly among beats
        """
        import re

        # First try splitting by newlines
        lines = [l.strip() for l in script.split("\n") if l.strip()]

        # If we have enough lines (at least 1 per beat), use them
        if len(lines) >= num_segments:
            return lines

        # Otherwise, split by sentences
        # Match sentences ending with . ? ! followed by space or end
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])$'
        sentences = re.split(sentence_pattern, script.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        # If still too few, return what we have
        if len(sentences) < num_segments:
            # Pad with empty strings if needed, or repeat last sentence
            while len(sentences) < num_segments:
                sentences.append(sentences[-1] if sentences else "")

        return sentences

    def _stub_shot_list(self, script: dict, visual_mode: str) -> list[dict]:
        """Stub shot list response."""
        script_text = script.get("script", "")

        beats = ["HOOK", "TENSION", "SHIFT", "CLIMB", "RESOLUTION", "CTA"]
        num_beats = len(beats)

        # Get segments properly split
        segments = self._split_script_into_segments(script_text, num_beats)
        scenes = []

        # Distribute segments among beats
        segments_per_beat = max(1, len(segments) // num_beats)

        for i, beat in enumerate(beats):
            start_idx = i * segments_per_beat
            end_idx = start_idx + segments_per_beat

            # Last beat gets remaining segments
            if i == num_beats - 1:
                end_idx = len(segments)

            # Extract this beat's segment
            if start_idx < len(segments):
                beat_segments = segments[start_idx:end_idx]
                segment = " ".join(beat_segments) if beat_segments else segments[-1]
            else:
                segment = segments[-1] if segments else ""

            scene = {
                "scene_number": i + 1,
                "beat_type": beat,
                "voiceover_segment": segment,
                "duration": 3.0 + (i * 1.5),
                "visual_description": self._stub_visual_for_beat(beat, segment),
                "search_tight": self._stub_search_tight(beat, segment),
                "search_broad": self._stub_search_broad(beat),
                "negative_search": ["text overlay", "watermark", "logo", "cartoon"],
                "nano_prompt": self._stub_nano_prompt(beat, segment),
                "overlay": self._stub_overlay(beat, segment) if i in [0, 2, 4, 5] else None,
                "match_score": 0.85 + (i * 0.02),
            }
            scenes.append(scene)

        return scenes

    def _stub_visual_for_beat(self, beat: str, segment: str) -> str:
        """Generate visual description for beat."""
        visuals = {
            "HOOK": "Person standing by window at golden hour, soft warm light on face, contemplative mood",
            "TENSION": "Rain on window, blurred city lights, sense of weight and struggle",
            "SHIFT": "Clouds parting to reveal sunlight, moment of clarity",
            "CLIMB": "Person walking forward on path, mountains in background, determination",
            "RESOLUTION": "Peaceful sunrise over calm water, sense of accomplishment",
            "CTA": "Warm closeup of hands holding coffee, comfort and presence",
        }
        return visuals.get(beat, "Cinematic nature footage, emotional lighting")

    def _stub_search_tight(self, beat: str, segment: str) -> str:
        """Generate tight search query."""
        queries = {
            "HOOK": "person window golden hour contemplative",
            "TENSION": "rain window city lights night",
            "SHIFT": "clouds parting sunlight rays",
            "CLIMB": "person walking mountain path determination",
            "RESOLUTION": "sunrise calm water peaceful",
            "CTA": "hands coffee cup warm light",
        }
        return queries.get(beat, "cinematic nature emotional")

    def _stub_search_broad(self, beat: str) -> str:
        """Generate broad search query."""
        queries = {
            "HOOK": "person contemplating sunset",
            "TENSION": "moody weather urban",
            "SHIFT": "breakthrough moment hope",
            "CLIMB": "journey progress forward",
            "RESOLUTION": "peace achievement calm",
            "CTA": "comfort warmth connection",
        }
        return queries.get(beat, "emotional cinematic mood")

    def _stub_nano_prompt(self, beat: str, segment: str) -> str:
        """Generate NanoBanana prompt."""
        base = self._stub_visual_for_beat(beat, segment)
        return f"Cinematic 9:16 vertical video, {base}, filmic color grading, shallow depth of field, professional lighting, 24fps"

    def _stub_overlay(self, beat: str, segment: str) -> dict:
        """Generate overlay config."""
        words = segment.split()[:4]
        overlay_text = " ".join(words)

        positions = {
            "HOOK": "upper_safe",
            "SHIFT": "center",
            "RESOLUTION": "center",
            "CTA": "lower_third",
        }

        return {
            "text": overlay_text,
            "position": positions.get(beat, "lower_third"),
            "animation": "scale_pop" if beat == "HOOK" else "fade_in",
            "display_start": 0.3,
            "display_duration": 2.5,
        }

    def _format_shot_list_md(self, shot_list: list[dict]) -> str:
        """Format shot list as markdown."""
        lines = ["# Shot List\n"]

        for scene in shot_list:
            lines.append(f"## Scene {scene['scene_number']}: {scene['beat_type']}")
            lines.append(f"**Duration:** {scene['duration']:.1f}s")
            lines.append(f"**Match Score:** {scene['match_score']:.2f}\n")
            lines.append(f"**Voiceover:**\n> {scene['voiceover_segment']}\n")
            lines.append(f"**Visual:** {scene['visual_description']}\n")

            if scene.get("overlay"):
                overlay = scene["overlay"]
                lines.append(f"**Overlay:** \"{overlay['text']}\" ({overlay['position']}, {overlay['animation']})\n")

            lines.append("---\n")

        return "\n".join(lines)

    def _format_nanobanana_prompts(self, shot_list: list[dict], realism_mode: str = "standard") -> str:
        """Format NanoBanana prompts for copy-paste."""
        lines = ["# NanoBanana Prompts\n"]

        realism_suffix = ""
        if realism_mode == "photorealistic":
            realism_suffix = ", photorealistic, hyperdetailed, 8K resolution"

        for scene in shot_list:
            lines.append(f"## Scene {scene['scene_number']} ({scene['beat_type']})")
            prompt = scene.get('nano_prompt', self._stub_nano_prompt(scene['beat_type'], scene.get('voiceover_segment', '')))
            lines.append(f"{prompt}{realism_suffix}\n")

        return "\n".join(lines)

    def _format_stock_queries(self, shot_list: list[dict]) -> str:
        """Format stock footage search queries."""
        lines = ["# Stock Footage Queries\n"]

        for scene in shot_list:
            lines.append(f"## Scene {scene['scene_number']} ({scene['beat_type']})")
            lines.append(f"**Tight:** {scene.get('search_tight', 'cinematic footage')}")
            lines.append(f"**Broad:** {scene.get('search_broad', 'emotional content')}")
            negative = scene.get('negative_search', ['text', 'watermark'])
            lines.append(f"**Exclude:** {', '.join(negative)}\n")

        return "\n".join(lines)
