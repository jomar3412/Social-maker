"""
CLI provider for local terminal command execution.

Executes local CLI tools (claude, gemini, codex) via subprocess.
NO API KEYS REQUIRED - uses locally installed CLI tools.
"""

import subprocess
import time
import json
import shlex
from pathlib import Path
from typing import Optional
import tempfile
import os

from .base import (
    ContentProvider,
    ProviderConfig,
    GenerationResult,
    ProviderError,
)


class CLIProvider(ContentProvider):
    """
    CLI provider that executes local terminal commands.

    Supports:
    - claude: Claude CLI (claude.ai/code)
    - gemini: Google Gemini CLI
    - codex: OpenAI Codex CLI

    All commands run locally - no API keys needed.
    """

    # Default command templates for each model
    COMMAND_TEMPLATES = {
        "claude": 'claude -p "{prompt}"',
        "gemini": 'gemini "{prompt}"',
        "codex": 'codex "{prompt}"',
    }

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.model = config.cli_model
        self._validate_cli_available()

    def _validate_cli_available(self):
        """Check if the CLI tool is available."""
        try:
            # Check if command exists
            result = subprocess.run(
                ["which", self.model],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                # Try common paths
                common_paths = [
                    f"/usr/local/bin/{self.model}",
                    f"/usr/bin/{self.model}",
                    os.path.expanduser(f"~/.local/bin/{self.model}"),
                ]
                for path in common_paths:
                    if os.path.exists(path):
                        return
                # Not found but don't fail - might be installed later
                pass
        except Exception:
            pass

    def _run_cli_command(
        self,
        prompt: str,
        timeout: Optional[int] = None,
    ) -> tuple[bool, str, str]:
        """
        Run a CLI command with the given prompt.

        Returns:
            (success, stdout, stderr)
        """
        timeout = timeout or self.config.timeout_seconds

        # Create temp file for prompt (avoid shell escaping issues)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            # Build command based on model
            if self.model == "claude":
                # Claude CLI accepts file input
                cmd = ["claude", "-p", prompt]
            elif self.model == "gemini":
                cmd = ["gemini", prompt]
            elif self.model == "codex":
                cmd = ["codex", prompt]
            else:
                # Custom command template
                template = self.config.cli_command_template or self.COMMAND_TEMPLATES.get(
                    self.model, f'{self.model} "{{prompt}}"'
                )
                cmd = shlex.split(template.format(prompt=prompt))

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )

            return result.returncode == 0, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return False, "", f"Command timed out after {timeout}s"
        except FileNotFoundError:
            return False, "", f"CLI tool '{self.model}' not found. Install it first."
        except Exception as e:
            return False, "", str(e)
        finally:
            # Cleanup temp file
            try:
                os.unlink(prompt_file)
            except:
                pass

    def generate_script(
        self,
        run_id: str,
        niche: str,
        style: str,
        topic: Optional[str],
        output_dir: Path,
        loop_friendly_ending: bool = False,
    ) -> GenerationResult:
        """Generate script using CLI tool."""
        start_time = time.time()

        self._report_progress("Preparing prompt", 10)

        # Build the prompt for script generation
        prompt = self._build_script_prompt(niche, style, topic, loop_friendly_ending)

        self._report_progress("Running CLI", 30)

        # Execute CLI command
        success, stdout, stderr = self._run_cli_command(prompt)

        if not success:
            return GenerationResult(
                success=False,
                error_message=f"CLI failed: {stderr}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        self._report_progress("Parsing output", 70)

        # Parse the output
        try:
            result = self._parse_script_output(stdout, niche)
        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"Failed to parse output: {e}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        self._report_progress("Writing files", 90)

        # Write outputs
        script_path = output_dir / "script.txt"
        script_path.write_text(result["script"])

        meta_path = output_dir / "script_meta.json"
        meta_path.write_text(json.dumps({
            "hook": result["hook"],
            "keywords": result["keywords"],
            "hashtags": result["hashtags"],
            "duration_estimate": result["duration_estimate"],
            "cli_model": self.model,
        }, indent=2))

        self._report_progress("Complete", 100)

        duration_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            success=True,
            output_files={
                "script": script_path,
                "script_meta": meta_path,
            },
            artifacts=result,
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
        """Regenerate script based on feedback."""
        start_time = time.time()

        self._report_progress("Preparing regeneration prompt", 10)

        # Build regeneration prompt
        prompt = self._build_regeneration_prompt(niche, style, prior_script, feedback)

        self._report_progress("Running CLI", 40)

        success, stdout, stderr = self._run_cli_command(prompt)

        if not success:
            return GenerationResult(
                success=False,
                error_message=f"CLI failed: {stderr}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        self._report_progress("Parsing output", 80)

        try:
            result = self._parse_script_output(stdout, niche)
            result["regeneration_note"] = f"Regenerated based on: {feedback}" if feedback else "Variation"
        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"Failed to parse output: {e}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        # Write outputs
        script_path = output_dir / "script.txt"
        script_path.write_text(result["script"])

        meta_path = output_dir / "script_meta.json"
        meta_path.write_text(json.dumps({
            "hook": result["hook"],
            "keywords": result["keywords"],
            "hashtags": result["hashtags"],
            "duration_estimate": result["duration_estimate"],
            "regeneration_note": result.get("regeneration_note"),
            "cli_model": self.model,
        }, indent=2))

        self._report_progress("Complete", 100)

        duration_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            success=True,
            output_files={
                "script": script_path,
                "script_meta": meta_path,
            },
            artifacts=result,
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

        self._report_progress("Preparing shot list prompt", 10)

        prompt = self._build_shot_list_prompt(script, visual_mode)

        self._report_progress("Running CLI", 40)

        success, stdout, stderr = self._run_cli_command(prompt)

        if not success:
            return GenerationResult(
                success=False,
                error_message=f"CLI failed: {stderr}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        self._report_progress("Parsing output", 70)

        try:
            # Pass original script for validation of duplicate segments
            original_script = script.get("script", "") if isinstance(script, dict) else ""
            shot_list = self._parse_shot_list_output(stdout, original_script)
        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"Failed to parse shot list: {e}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        self._report_progress("Writing files", 90)

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
        """Generate NanoBanana prompts via NanoBananaPromptGenerator (no CLI call)."""
        start_time = time.time()

        self._report_progress("Generating prompts", 50)

        from content_engine.pipeline.nanobanana_generator import generate_nanobanana_prompt

        # Read niche from config.json written to run dir before this stage
        niche = None
        config_path = output_dir / "config.json"
        if config_path.exists():
            try:
                niche = json.loads(config_path.read_text()).get("niche")
            except Exception:
                pass

        scenes = shot_list if isinstance(shot_list, list) else shot_list.get("shot_list", [])

        prompt_lines = []
        specs = []
        prior_spec = None

        for i, scene in enumerate(scenes):
            spec = generate_nanobanana_prompt(
                scene_number=scene.get("scene_number", i + 1),
                beat_type=scene.get("beat_type", "HOOK"),
                voiceover=scene.get("voiceover_segment", ""),
                detail_level="ultra",
                niche=niche,
                prior_scene_spec=prior_spec,
            )
            specs.append(spec)
            prior_spec = spec
            prompt_lines.append(f"Scene {spec.scene_number}: {spec.to_full_prompt()}")

        prompts_text = "\n".join(prompt_lines)

        prompts_path = output_dir / "nanobanana_prompts.txt"
        prompts_path.write_text(prompts_text)

        json_path = output_dir / "nanobanana_prompts.json"
        json_path.write_text(json.dumps([s.to_dict() for s in specs], indent=2))

        self._report_progress("Complete", 100)

        duration_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            success=True,
            output_files={
                "nanobanana_prompts": prompts_path,
                "nanobanana_prompts_json": json_path,
            },
            artifacts={"prompts": prompts_text},
            duration_ms=duration_ms,
        )

    def generate_stock_queries(
        self,
        run_id: str,
        shot_list: dict,
        output_dir: Path,
    ) -> GenerationResult:
        """Generate stock footage queries."""
        start_time = time.time()

        self._report_progress("Generating queries", 50)

        prompt = self._build_stock_queries_prompt(shot_list)

        success, stdout, stderr = self._run_cli_command(prompt)

        if not success:
            return GenerationResult(
                success=False,
                error_message=f"CLI failed: {stderr}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        queries = stdout.strip() if stdout.strip() else self._fallback_stock_queries(shot_list)

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

    # === Prompt building methods ===

    def _build_script_prompt(
        self,
        niche: str,
        style: str,
        topic: Optional[str],
        loop_friendly_ending: bool = False,
    ) -> str:
        """Build prompt for script generation."""
        topic_line = f"Topic: {topic}" if topic else "Topic: Choose a compelling topic"

        # Loop-friendly ending instructions
        if loop_friendly_ending:
            ending_instruction = """- LOOP-FRIENDLY ENDING: The final line must naturally flow back to the opening hook
  - DO NOT use finality phrases like "thanks for watching", "that's all", "goodbye"
  - DO NOT use hard conclusions that feel like an ending
  - The last line should reference or echo the hook concept
  - When the video loops, the ending should seamlessly connect to the beginning
  - Create a circular narrative that encourages rewatching"""
        else:
            ending_instruction = "- Standard narrative ending with clear resolution"

        return f"""Generate a short-form video script for social media.

Niche: {niche}
Style: {style}
{topic_line}

Requirements:
- 30-60 seconds when read aloud (100-150 words)
- Strong opening hook (first line grabs attention)
- Emotional arc with tension and resolution
- No hashtags in the script itself
- Conversational, authentic tone
{ending_instruction}

Output format (JSON):
{{
  "script": "The full script text",
  "hook": "First line of the script",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "hashtags": ["#hashtag1", "#hashtag2"]
}}

Generate the script now:"""

    def _build_regeneration_prompt(
        self,
        niche: str,
        style: str,
        prior_script: dict,
        feedback: Optional[str],
    ) -> str:
        """Build prompt for script regeneration."""
        prior_text = prior_script.get("script", "")
        feedback_line = f"User feedback: {feedback}" if feedback else "Create a different variation"

        return f"""Regenerate this script with improvements.

Niche: {niche}
Style: {style}

Previous script:
{prior_text}

{feedback_line}

Requirements:
- Keep similar length (30-60 seconds)
- Improve based on feedback
- Different hook/opening
- Same emotional quality

Output format (JSON):
{{
  "script": "The full script text",
  "hook": "First line of the script",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "hashtags": ["#hashtag1", "#hashtag2"]
}}

Generate the improved script:"""

    def _build_shot_list_prompt(self, script: dict, visual_mode: str) -> str:
        """Build prompt for shot list generation."""
        script_text = script.get("script", "")

        return f"""Create a shot list for this video script by DIVIDING it into 6 beats.

CRITICAL: Each beat must have a UNIQUE, DISTINCT portion of the script.
DO NOT repeat the full script in each beat - SPLIT it into segments.

Script to divide:
{script_text}

Visual mode: {visual_mode}

INSTRUCTIONS:
1. Analyze the script and identify natural break points (sentences, paragraphs)
2. DIVIDE the script into 6 distinct segments - one per beat
3. Each voiceover_segment should be a DIFFERENT PART of the script

For each beat (HOOK, TENSION, SHIFT, CLIMB, RESOLUTION, CTA), provide:
- scene_number: 1-6
- beat_type: The beat name (HOOK, TENSION, SHIFT, CLIMB, RESOLUTION, CTA)
- voiceover_segment: ONLY the script portion for THIS beat (NOT the full script)
- duration: Seconds (3-10s) proportional to segment length
- visual_description: Detailed visual matching this segment
- search_tight: Specific stock search query
- search_broad: General stock search query
- negative_search: Terms to exclude ["text overlay", "watermark", "logo"]
- nano_prompt: AI video prompt for this segment

EXAMPLE structure (showing how to segment):
- HOOK (scene 1): First 1-2 sentences - the attention grabber
- TENSION (scene 2): Next portion introducing the challenge/question
- SHIFT (scene 3): The pivot/revelation moment
- CLIMB (scene 4): Building the narrative
- RESOLUTION (scene 5): The payoff/insight
- CTA (scene 6): Final call to action or closing thought

Output as JSON array of 6 scene objects:"""

    def _build_visual_prompts_prompt(
        self,
        shot_list: dict,
        visual_mode: str,
        realism_mode: str,
    ) -> str:
        """Build prompt for visual prompts generation."""
        scenes = shot_list if isinstance(shot_list, list) else shot_list.get("shot_list", [])

        scene_descriptions = "\n".join([
            f"Scene {s.get('scene_number', i+1)}: {s.get('visual_description', '')}"
            for i, s in enumerate(scenes)
        ])

        return f"""Generate NanoBanana/AI video prompts for these scenes.

Scenes:
{scene_descriptions}

Visual mode: {visual_mode}
Realism: {realism_mode}

For each scene, create a detailed prompt optimized for AI video generation:
- 9:16 vertical format
- Cinematic quality
- {"Photorealistic, hyperdetailed" if realism_mode == "photorealistic" else "Stylized, filmic"}

Output each prompt on its own line with scene number prefix."""

    def _build_stock_queries_prompt(self, shot_list: dict) -> str:
        """Build prompt for stock queries generation."""
        scenes = shot_list if isinstance(shot_list, list) else shot_list.get("shot_list", [])

        scene_descriptions = "\n".join([
            f"Scene {s.get('scene_number', i+1)}: {s.get('visual_description', '')}"
            for i, s in enumerate(scenes)
        ])

        return f"""Generate stock footage search queries for these scenes.

Scenes:
{scene_descriptions}

For each scene provide:
- Tight query: Specific, detailed search terms
- Broad query: General category terms
- Exclude: Terms to filter out (watermarks, text, etc.)

Format as markdown with scene headers."""

    # === Output parsing methods ===

    def _parse_script_output(self, output: str, niche: str) -> dict:
        """Parse CLI output into script structure."""
        # Try to find JSON in output
        try:
            # Look for JSON block
            start = output.find('{')
            end = output.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = output[start:end]
                data = json.loads(json_str)
                if "script" in data:
                    data["duration_estimate"] = len(data["script"].split()) / 2.5
                    return data
        except json.JSONDecodeError:
            pass

        # Fallback: treat entire output as script
        script = output.strip()
        lines = script.split('\n')
        hook = lines[0] if lines else "Generated content"

        return {
            "script": script,
            "hook": hook,
            "keywords": ["content", niche],
            "hashtags": [f"#{niche}", "#content"],
            "duration_estimate": len(script.split()) / 2.5,
        }

    def _parse_shot_list_output(self, output: str, original_script: str = None) -> list[dict]:
        """Parse CLI output into shot list with validation."""
        scenes = []

        try:
            # Try to find JSON array
            start = output.find('[')
            end = output.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = output[start:end]
                scenes = json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Fallback: create basic shot list
        if not scenes:
            scenes = self._fallback_shot_list(output)

        # Validate and fix duplicate segments
        return self._validate_shot_list(scenes, original_script)

    def _split_script_into_segments(self, script: str, num_segments: int = 6) -> list[str]:
        """
        Split script into segments for beat assignment.

        Handles both multi-line scripts and single-paragraph scripts.
        """
        import re

        # First try splitting by newlines
        lines = [l.strip() for l in script.split("\n") if l.strip()]

        # If we have enough lines (at least 1 per beat), use them
        if len(lines) >= num_segments:
            return lines

        # Otherwise, split by sentences
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])$'
        sentences = re.split(sentence_pattern, script.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        # If still too few, pad
        while len(sentences) < num_segments:
            sentences.append(sentences[-1] if sentences else "")

        return sentences

    def _validate_shot_list(self, scenes: list[dict], original_script: str = None) -> list[dict]:
        """
        Validate shot list and fix duplicate voiceover segments.

        If all beats have identical voiceover, re-segment using the original script.
        """
        if not scenes or len(scenes) < 2:
            return scenes

        # Check for duplicate voiceover segments
        voiceovers = [s.get("voiceover_segment", "") for s in scenes]
        unique_voiceovers = set(voiceovers)

        # If all voiceovers are the same (or most are duplicates), re-segment
        if len(unique_voiceovers) <= 2:  # Only 1-2 unique segments = broken
            # Try to extract script from first scene if original not provided
            script = original_script or voiceovers[0]
            if script:
                segments = self._split_script_into_segments(script, len(scenes))
                segments_per_beat = max(1, len(segments) // len(scenes))

                for i, scene in enumerate(scenes):
                    start_idx = i * segments_per_beat
                    end_idx = start_idx + segments_per_beat if i < len(scenes) - 1 else len(segments)

                    if start_idx < len(segments):
                        beat_segments = segments[start_idx:end_idx]
                        scene["voiceover_segment"] = " ".join(beat_segments)
                    else:
                        scene["voiceover_segment"] = segments[-1] if segments else ""

        return scenes

    def _fallback_shot_list(self, text: str) -> list[dict]:
        """Create fallback shot list from text with proper segmentation."""
        beats = ["HOOK", "TENSION", "SHIFT", "CLIMB", "RESOLUTION", "CTA"]
        scenes = []

        # Segment the text properly
        segments = self._split_script_into_segments(text, len(beats))
        segments_per_beat = max(1, len(segments) // len(beats))

        for i, beat in enumerate(beats):
            start_idx = i * segments_per_beat
            end_idx = start_idx + segments_per_beat if i < len(beats) - 1 else len(segments)

            if start_idx < len(segments):
                beat_segments = segments[start_idx:end_idx]
                voiceover = " ".join(beat_segments)
            else:
                voiceover = segments[-1] if segments else f"Scene {i + 1} content"

            scenes.append({
                "scene_number": i + 1,
                "beat_type": beat,
                "voiceover_segment": voiceover,
                "duration": 5.0,
                "visual_description": f"Visual for {beat.lower()} beat",
                "search_tight": f"{beat.lower()} footage",
                "search_broad": "cinematic content",
                "negative_search": ["watermark", "text"],
                "nano_prompt": f"Cinematic 9:16 video, {beat.lower()} mood, professional lighting",
                "match_score": 0.8,
            })

        return scenes

    def _fallback_visual_prompts(self, shot_list: dict, realism_mode: str) -> str:
        """Create fallback visual prompts."""
        scenes = shot_list if isinstance(shot_list, list) else shot_list.get("shot_list", [])
        lines = ["# NanoBanana Prompts\n"]

        realism_suffix = ", photorealistic, 8K" if realism_mode == "photorealistic" else ", cinematic, filmic"

        for i, scene in enumerate(scenes):
            beat = scene.get("beat_type", f"SCENE_{i+1}")
            visual = scene.get("visual_description", "Cinematic footage")
            lines.append(f"## Scene {i+1} ({beat})")
            lines.append(f"9:16 vertical video, {visual}{realism_suffix}\n")

        return "\n".join(lines)

    def _fallback_stock_queries(self, shot_list: dict) -> str:
        """Create fallback stock queries."""
        scenes = shot_list if isinstance(shot_list, list) else shot_list.get("shot_list", [])
        lines = ["# Stock Footage Queries\n"]

        for i, scene in enumerate(scenes):
            beat = scene.get("beat_type", f"SCENE_{i+1}")
            lines.append(f"## Scene {i+1} ({beat})")
            lines.append(f"**Tight:** {scene.get('search_tight', 'cinematic footage')}")
            lines.append(f"**Broad:** {scene.get('search_broad', 'stock video')}")
            lines.append(f"**Exclude:** watermark, text, logo\n")

        return "\n".join(lines)

    def _format_shot_list_md(self, shot_list: list[dict]) -> str:
        """Format shot list as markdown."""
        lines = ["# Shot List\n"]

        for scene in shot_list:
            lines.append(f"## Scene {scene.get('scene_number', '?')}: {scene.get('beat_type', 'UNKNOWN')}")
            lines.append(f"**Duration:** {scene.get('duration', 5):.1f}s")

            if "match_score" in scene:
                lines.append(f"**Match Score:** {scene['match_score']:.2f}")

            lines.append(f"\n**Voiceover:**\n> {scene.get('voiceover_segment', 'N/A')}\n")
            lines.append(f"**Visual:** {scene.get('visual_description', 'N/A')}\n")

            if scene.get("overlay"):
                overlay = scene["overlay"]
                lines.append(f"**Overlay:** \"{overlay.get('text', '')}\" ({overlay.get('position', 'center')})\n")

            lines.append("---\n")

        return "\n".join(lines)

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Generate text using the CLI tool.

        Combines system and user prompts for a single generation call.
        """
        # Combine prompts for CLI
        full_prompt = f"""{system_prompt}

---

{user_prompt}"""

        success, stdout, stderr = self._run_cli_command(full_prompt)

        if not success:
            raise ProviderError(f"CLI generation failed: {stderr}")

        return stdout.strip()
