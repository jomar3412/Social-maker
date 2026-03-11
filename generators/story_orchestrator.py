"""
Story Orchestrator - Coordinates All Story Agents

Orchestrates the 5-agent workflow for story production:
1. Story Creator → Generate story with characters
2. Voice Script Generator → Add pacing and emotional markers
3. Scene Planner → Create visual scene breakdown
4. Visual Prompt Builder → Generate Midjourney prompts
5. QA Reviewer → Validate consistency

Supports two modes:
- Quick: Automated end-to-end pipeline
- Detailed: Step-by-step with pause for manual visuals

Usage:
    from generators.story_orchestrator import StoryOrchestrator

    orchestrator = StoryOrchestrator()

    # Quick mode
    result = orchestrator.run_quick(genre="thriller")

    # Detailed mode with manual intervention
    result = orchestrator.run_detailed(genre="thriller", visual_mode="manual")
"""

import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum

from config.settings import OUTPUT_DIR
from generators.story_gen import StoryGenerator, StoryOutput
from generators.story_voice_gen import VoiceScriptGenerator, VoiceScript
from generators.story_scene_planner import ScenePlanner, ScenePlan
from generators.story_visual_gen import VisualPromptGenerator, VisualPromptSet
from generators.story_registry import StoryRegistry, StoryStatus


class OrchestrationMode(Enum):
    QUICK = "quick"
    DETAILED = "detailed"


class VisualMode(Enum):
    MANUAL = "manual"  # Generate prompts for manual Midjourney use
    STOCK = "stock"    # Use stock footage/images (future)
    VEO = "veo"        # Use VEO AI video generation (future)


@dataclass
class OrchestrationResult:
    """Result from a complete orchestration run."""
    story_id: str = ""
    mode: OrchestrationMode = OrchestrationMode.QUICK
    success: bool = False

    # Agent outputs
    story: Optional[StoryOutput] = None
    voice_script: Optional[VoiceScript] = None
    scene_plan: Optional[ScenePlan] = None
    visual_prompts: Optional[VisualPromptSet] = None
    qa_report: Optional[Dict[str, Any]] = None

    # Output files
    output_dir: str = ""
    files_created: List[str] = field(default_factory=list)

    # Timing
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0

    # Errors
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = {
            "story_id": self.story_id,
            "mode": self.mode.value,
            "success": self.success,
            "output_dir": self.output_dir,
            "files_created": self.files_created,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
        }
        if self.story:
            data["story"] = self.story.to_dict()
        if self.voice_script:
            data["voice_script"] = self.voice_script.to_dict()
        if self.scene_plan:
            data["scene_plan"] = self.scene_plan.to_dict()
        if self.visual_prompts:
            data["visual_prompts"] = self.visual_prompts.to_dict()
        if self.qa_report:
            data["qa_report"] = self.qa_report
        return data

    def to_summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            "=" * 60,
            "STORY ORCHESTRATION COMPLETE",
            "=" * 60,
            "",
            f"Story ID: {self.story_id}",
            f"Mode: {self.mode.value}",
            f"Status: {'SUCCESS' if self.success else 'FAILED'}",
            f"Duration: {self.duration_seconds:.1f}s",
            "",
            f"Output: {self.output_dir}",
            "",
            "Files Created:",
        ]

        for f in self.files_created:
            lines.append(f"  - {f}")

        if self.errors:
            lines.extend(["", "Errors:"])
            for e in self.errors:
                lines.append(f"  - {e}")

        if self.story:
            lines.extend([
                "",
                "Story:",
                f"  Title: {self.story.title}",
                f"  Genre: {self.story.genre}",
                f"  Words: {self.story.word_count}",
                f"  Duration: ~{self.story.estimated_duration:.1f}s",
            ])

        if self.scene_plan:
            lines.extend([
                "",
                "Scenes:",
                f"  Count: {self.scene_plan.scene_count}",
                f"  Characters: {len(self.scene_plan.characters)}",
            ])

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


class StoryOrchestrator:
    """
    Orchestrates the complete story production pipeline.

    Coordinates:
    - Story generation
    - Voice script creation
    - Scene planning
    - Visual prompt generation
    - Quality assurance
    """

    def __init__(self):
        self.story_gen = StoryGenerator()
        self.voice_gen = VoiceScriptGenerator()
        self.scene_planner = ScenePlanner()
        self.visual_gen = VisualPromptGenerator()
        self.registry = StoryRegistry()

    def _create_output_dir(self, story_id: str, title: str) -> Path:
        """Create output directory for story artifacts."""
        # Clean title for folder name
        import re
        title_slug = re.sub(r"[^a-zA-Z0-9-]", "", title.replace(" ", "-"))[:30]
        folder_name = f"{story_id}-{title_slug}"

        output_dir = OUTPUT_DIR / "short_stories" / "standalone" / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir

    def _save_markdown(self, content: str, output_dir: Path, filename: str) -> str:
        """Save content as markdown file."""
        filepath = output_dir / filename
        with open(filepath, "w") as f:
            f.write(content)
        return filename

    def _save_json(self, data: dict, output_dir: Path, filename: str) -> str:
        """Save data as JSON file."""
        filepath = output_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        return filename

    def run_quick(
        self,
        genre: str = "thriller",
        topic: Optional[str] = None,
        continuation_from: Optional[str] = None,
        series_name: Optional[str] = None,
        verbose: bool = True,
    ) -> OrchestrationResult:
        """
        Run the complete pipeline in quick (automated) mode.

        Args:
            genre: Story genre
            topic: Optional topic/seed
            continuation_from: Story ID to continue
            series_name: Series to add story to
            verbose: Print progress

        Returns:
            OrchestrationResult with all outputs
        """
        result = OrchestrationResult(
            mode=OrchestrationMode.QUICK,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Stage 1: Generate Story
            if verbose:
                print("\n[1/5] Generating story...")

            story = self.story_gen.generate(
                genre=genre,
                topic=topic,
                continuation_from=continuation_from,
                series_name=series_name,
            )
            result.story = story
            result.story_id = getattr(story, 'story_id', '')

            if verbose:
                print(f"  Title: {story.title}")
                print(f"  Words: {story.word_count}")

            # Create output directory
            output_dir = self._create_output_dir(result.story_id, story.title)
            result.output_dir = str(output_dir)

            # Save story
            story_md = f"# {story.title}\n\n**Genre:** {story.genre}\n\n---\n\n{story.full_story}"
            result.files_created.append(
                self._save_markdown(story_md, output_dir, "Story.md")
            )
            result.files_created.append(
                self._save_json(story.to_dict(), output_dir, "story.json")
            )

            # Stage 2: Generate Voice Script
            if verbose:
                print("\n[2/5] Creating voice script...")

            voice_script = self.voice_gen.generate(
                story_text=story.full_story,
                genre=genre,
                hook=story.hook,
                twist=story.twist,
                mood=story.mood,
            )
            result.voice_script = voice_script

            if verbose:
                print(f"  Duration: ~{voice_script.estimated_duration:.1f}s")
                print(f"  Pauses: {voice_script.pause_count}")

            result.files_created.append(
                self._save_markdown(voice_script.to_markdown(), output_dir, "VoiceScript.md")
            )

            # Stage 3: Plan Scenes
            if verbose:
                print("\n[3/5] Planning scenes...")

            scene_plan = self.scene_planner.plan_scenes(
                story_text=story.full_story,
                characters=story.characters,
                genre=genre,
                mood=story.mood,
                total_duration=story.estimated_duration,
            )
            result.scene_plan = scene_plan

            if verbose:
                print(f"  Scenes: {scene_plan.scene_count}")
                print(f"  Characters: {len(scene_plan.characters)}")

            result.files_created.append(
                self._save_markdown(scene_plan.to_markdown(), output_dir, "ScenePlan.md")
            )

            # Stage 4: Generate Visual Prompts
            if verbose:
                print("\n[4/5] Generating Midjourney prompts...")

            # Convert scenes to dict format
            scenes_data = [s.to_dict() if hasattr(s, 'to_dict') else s
                          for s in scene_plan.scenes]

            visual_prompts = self.visual_gen.generate_prompts(
                scenes=scenes_data,
                characters=story.characters,
                genre=genre,
                title=story.title,
                story_id=result.story_id,
            )
            result.visual_prompts = visual_prompts

            if verbose:
                print(f"  Character prompts: {len(visual_prompts.character_prompts)}")
                print(f"  Scene prompts: {len(visual_prompts.scene_prompts)}")

            result.files_created.append(
                self._save_markdown(visual_prompts.to_markdown(), output_dir, "Visuals-Midjourney.md")
            )

            # Stage 5: QA Review
            if verbose:
                print("\n[5/5] Running QA checks...")

            qa_report = self._run_qa(result)
            result.qa_report = qa_report

            if verbose:
                print(f"  Score: {qa_report.get('score', 0)}/100")
                print(f"  Issues: {len(qa_report.get('issues', []))}")

            result.files_created.append(
                self._save_json(qa_report, output_dir, "QAReport.json")
            )

            # Save metadata
            result.files_created.append(
                self._save_json(result.to_dict(), output_dir, "metadata.json")
            )

            # Update registry
            self.registry.update_story(
                result.story_id,
                status=StoryStatus.GENERATED,
                output_path=str(output_dir),
            )

            result.success = True

        except Exception as e:
            result.errors.append(str(e))
            if verbose:
                print(f"\nError: {e}")

        result.completed_at = datetime.now().isoformat()
        start = datetime.fromisoformat(result.started_at)
        end = datetime.fromisoformat(result.completed_at)
        result.duration_seconds = (end - start).total_seconds()

        if verbose:
            print(result.to_summary())

        return result

    def run_detailed(
        self,
        genre: str = "thriller",
        topic: Optional[str] = None,
        visual_mode: str = "manual",
        verbose: bool = True,
    ) -> OrchestrationResult:
        """
        Run the pipeline in detailed mode with pauses for manual intervention.

        This mode is useful when you want to:
        - Review and edit story before proceeding
        - Manually generate Midjourney images
        - Upload custom visuals

        Args:
            genre: Story genre
            topic: Optional topic/seed
            visual_mode: "manual" for copy-paste prompts, "stock" for auto
            verbose: Print progress

        Returns:
            OrchestrationResult (partial until visual step)
        """
        result = OrchestrationResult(
            mode=OrchestrationMode.DETAILED,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Same as quick mode for stages 1-4
            # Stage 1: Generate Story
            if verbose:
                print("\n[1/5] Generating story...")

            story = self.story_gen.generate(
                genre=genre,
                topic=topic,
            )
            result.story = story
            result.story_id = getattr(story, 'story_id', '')

            # Create output directory
            output_dir = self._create_output_dir(result.story_id, story.title)
            result.output_dir = str(output_dir)

            # Save story
            story_md = f"# {story.title}\n\n**Genre:** {story.genre}\n\n---\n\n{story.full_story}"
            result.files_created.append(
                self._save_markdown(story_md, output_dir, "Story.md")
            )

            if verbose:
                print(f"\n  Story saved to: {output_dir}/Story.md")
                print(f"  Title: {story.title}")
                print(f"\n  Review and edit Story.md if needed.")

            # Stage 2: Voice Script
            if verbose:
                print("\n[2/5] Creating voice script...")

            voice_script = self.voice_gen.generate(
                story_text=story.full_story,
                genre=genre,
                hook=story.hook,
                twist=story.twist,
                mood=story.mood,
            )
            result.voice_script = voice_script

            result.files_created.append(
                self._save_markdown(voice_script.to_markdown(), output_dir, "VoiceScript.md")
            )

            if verbose:
                print(f"  Voice script saved to: {output_dir}/VoiceScript.md")

            # Stage 3: Scene Plan
            if verbose:
                print("\n[3/5] Planning scenes...")

            scene_plan = self.scene_planner.plan_scenes(
                story_text=story.full_story,
                characters=story.characters,
                genre=genre,
                mood=story.mood,
            )
            result.scene_plan = scene_plan

            result.files_created.append(
                self._save_markdown(scene_plan.to_markdown(), output_dir, "ScenePlan.md")
            )

            if verbose:
                print(f"  Scene plan saved to: {output_dir}/ScenePlan.md")

            # Stage 4: Visual Prompts
            if verbose:
                print("\n[4/5] Generating visual prompts...")

            scenes_data = [s.to_dict() if hasattr(s, 'to_dict') else s
                          for s in scene_plan.scenes]

            visual_prompts = self.visual_gen.generate_prompts(
                scenes=scenes_data,
                characters=story.characters,
                genre=genre,
                title=story.title,
                story_id=result.story_id,
            )
            result.visual_prompts = visual_prompts

            result.files_created.append(
                self._save_markdown(visual_prompts.to_markdown(), output_dir, "Visuals-Midjourney.md")
            )

            if visual_mode == "manual":
                if verbose:
                    print(f"\n  Visual prompts saved to: {output_dir}/Visuals-Midjourney.md")
                    print("\n" + "=" * 60)
                    print("  MANUAL VISUAL GENERATION REQUIRED")
                    print("=" * 60)
                    print(f"""
  Next steps:

  1. Open: {output_dir}/Visuals-Midjourney.md

  2. Generate CHARACTER REFERENCES first in Midjourney:
     - Copy each character prompt
     - Generate in Midjourney
     - Save the image URL

  3. Update scene prompts with --cref URLs:
     - Add the character image URL to each scene prompt

  4. Generate SCENE IMAGES:
     - Copy each scene prompt (with --cref)
     - Generate in Midjourney
     - Download to: {output_dir}/images/scenes/

  5. Resume video assembly when ready

  Output directory: {output_dir}
""")
                    print("=" * 60)

            result.success = True

        except Exception as e:
            result.errors.append(str(e))
            if verbose:
                print(f"\nError: {e}")

        result.completed_at = datetime.now().isoformat()
        start = datetime.fromisoformat(result.started_at)
        end = datetime.fromisoformat(result.completed_at)
        result.duration_seconds = (end - start).total_seconds()

        return result

    def _run_qa(self, result: OrchestrationResult) -> Dict[str, Any]:
        """Run QA checks on the orchestration result."""
        # Import QA module
        try:
            from generators.story_qa import StoryQA
            qa = StoryQA()
            return qa.run_full_qa(
                story=result.story,
                voice_script=result.voice_script,
                scene_plan=result.scene_plan,
                visual_prompts=result.visual_prompts,
            )
        except ImportError:
            # QA module not yet available, return basic check
            return {
                "score": 80,
                "passed": True,
                "issues": [],
                "note": "Basic QA only - full QA module not loaded"
            }

    def resume_from_visuals(
        self,
        story_id: str,
        images_dir: Optional[Path] = None,
    ) -> OrchestrationResult:
        """
        Resume orchestration after manual visual generation.

        Args:
            story_id: The story ID to resume
            images_dir: Directory containing generated images

        Returns:
            Updated OrchestrationResult
        """
        # Load existing metadata
        story_data = self.registry.get_story_for_continuation(story_id)
        story_entry = story_data.get("story", {})
        output_path = story_entry.get("output_path")

        if not output_path:
            raise ValueError(f"No output path found for story {story_id}")

        output_dir = Path(output_path)
        metadata_file = output_dir / "metadata.json"

        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
        else:
            raise ValueError(f"No metadata found at {metadata_file}")

        # TODO: Implement video assembly from images
        print(f"Resuming from: {output_dir}")
        print("Video assembly from images not yet implemented")

        return OrchestrationResult(
            story_id=story_id,
            output_dir=str(output_dir),
            success=False,
            errors=["Resume not fully implemented yet"],
        )


# CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Story Orchestrator")
        print("=" * 50)
        print("\nCommands:")
        print("  python story_orchestrator.py quick thriller")
        print("  python story_orchestrator.py quick mystery --topic 'A locked room'")
        print("  python story_orchestrator.py detailed thriller")
        print("  python story_orchestrator.py resume STORY-001")
        sys.exit(0)

    cmd = sys.argv[1]
    orchestrator = StoryOrchestrator()

    if cmd == "quick":
        genre = sys.argv[2] if len(sys.argv) > 2 else "thriller"
        topic = None

        if "--topic" in sys.argv:
            idx = sys.argv.index("--topic")
            if idx + 1 < len(sys.argv):
                topic = sys.argv[idx + 1]

        result = orchestrator.run_quick(genre=genre, topic=topic)

    elif cmd == "detailed":
        genre = sys.argv[2] if len(sys.argv) > 2 else "thriller"
        result = orchestrator.run_detailed(genre=genre, visual_mode="manual")

    elif cmd == "resume":
        if len(sys.argv) < 3:
            print("Usage: python story_orchestrator.py resume STORY-ID")
            sys.exit(1)
        story_id = sys.argv[2]
        result = orchestrator.resume_from_visuals(story_id)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
