"""
PipelineOrchestrator: Main pipeline coordinator.

Manages the full content generation flow with:
- DriveGuard gating
- Stage transitions with logging
- RunStore persistence
- Provider abstraction for content generation
- Concurrency limits
"""

from pathlib import Path
from datetime import datetime
from typing import Callable, Optional
import json
import yaml

from content_engine.services.drive_guard import (
    DriveGuard,
    DriveNotAvailableError,
    DriveStatus,
)
from content_engine.services.output_writer import OutputWriter, OutputPaths
from content_engine.services.preset_loader import PresetLoader
from content_engine.services.run_store import RunStore, RunStage, RunRecord, STAGE_INFO
from content_engine.services.concurrency import (
    get_concurrency_manager,
    ConcurrencyManager,
    RunLimitExceeded,
    RegenerationLimitExceeded,
)
from content_engine.pipeline.models.run_config import RunConfig
from content_engine.providers.base import get_provider, ContentProvider, ProviderConfig
from content_engine.knowledge import (
    get_registry,
    build_knowledge_context,
    get_learning_context_prompt,
    KnowledgeContext,
)
from content_engine.pipeline.nanobanana_generator import (
    NanoBananaPromptGenerator,
    generate_nanobanana_prompt,
    ScenePromptSpec,
)
from content_engine.pipeline.prompt_spec import PromptDetailLevel


class PipelineOrchestrator:
    """
    Orchestrates the content generation pipeline.

    Coordinates DriveGuard, OutputWriter, RunStore, and PresetLoader
    to produce structured output in G Drive.
    """

    def __init__(
        self,
        config_path: Path | None = None,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int], None] | None = None,
    ):
        """
        Initialize orchestrator.

        Args:
            config_path: Path to config.yaml. Defaults to content_engine/config.yaml
            on_log: Optional callback for log messages (for CLI output)
            on_progress: Optional callback for progress updates (stage, percent)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        self.config_path = config_path
        self.config = self._load_config(config_path)

        self.drive_guard = DriveGuard(config_path)
        self.output_writer = OutputWriter(self.drive_guard)
        self.preset_loader = PresetLoader()
        self.run_store = RunStore()

        # Initialize provider based on config
        provider_config = self.config.get("provider", {})
        self.provider = get_provider(provider_config)

        # Initialize concurrency manager
        concurrency_config = self.config.get("concurrency", {})
        self.concurrency = get_concurrency_manager(concurrency_config)

        # Initialize knowledge registry
        try:
            self.knowledge_registry = get_registry()
        except FileNotFoundError:
            self.knowledge_registry = None

        self._on_log = on_log or (lambda msg: None)
        self._on_progress = on_progress or (lambda stage, pct: None)
        self._log_buffer: list[str] = []
        self._current_knowledge_context: Optional[KnowledgeContext] = None

        # Set progress callback on provider
        if on_progress:
            self.provider.set_progress_callback(on_progress)

    def _load_config(self, config_path: Path) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _log(self, message: str, level: str = "INFO"):
        """Log message to buffer and callback."""
        timestamp = datetime.now().isoformat()
        entry = f"[{timestamp}] [{level}] {message}"
        self._log_buffer.append(entry)
        self._on_log(entry)

    def _progress(self, stage: str, percent: int):
        """Report progress."""
        self._on_progress(stage, percent)

    def can_start_run(self) -> tuple[bool, str]:
        """
        Check if a new run can be started.

        Returns:
            (can_start, message)
        """
        if self.concurrency.can_start_run():
            return True, "Ready to start"
        else:
            active = self.concurrency.get_active_run_ids()
            return False, f"Max concurrent runs reached. Active: {active}"

    def can_regenerate(self, run_id: str) -> tuple[bool, int, str]:
        """
        Check if a run can be regenerated.

        Returns:
            (can_regenerate, remaining, message)
        """
        remaining = self.concurrency.get_remaining_regenerations(run_id)
        if remaining > 0:
            return True, remaining, f"{remaining} regenerations remaining"
        else:
            return False, 0, "Max regenerations reached for this run"

    def get_concurrency_status(self) -> dict:
        """Get current concurrency status."""
        return self.concurrency.get_status()

    def get_provider_info(self) -> dict:
        """Get provider information."""
        return self.provider.get_provider_info()

    def _load_knowledge_context(
        self,
        config: RunConfig,
        paths: OutputPaths,
    ) -> Optional[KnowledgeContext]:
        """
        Load knowledge context for the run.

        Builds context from:
        - External specs (dopamine ladder, etc.)
        - Internal insights (learned patterns, rules)

        Saves to run folder as knowledge_context.json and knowledge_context.md
        """
        if not self.knowledge_registry:
            self._log("Knowledge registry not available, skipping knowledge context")
            return None

        try:
            self._log("Building knowledge context...")
            context = build_knowledge_context(
                run_id=config.run_id,
                niche=config.niche,
                style=config.style,
                visual_mode=config.visual_mode,
                content_mode=config.content_mode if hasattr(config, 'content_mode') else "ai_generated",
                registry=self.knowledge_registry,
            )

            # Save to run folder
            json_path, md_path = context.save_to_run_folder(paths.base_dir)
            self._log(f"Knowledge context saved: {md_path.name}")

            # Log summary
            self._log(f"  - Dopamine levels: {len(context.dopamine_requirements)}")
            self._log(f"  - Internal insights: {len(context.internal_insights)}")
            self._log(f"  - Applicable patterns: {len(context.applicable_patterns)}")
            self._log(f"  - Rule overrides: {len(context.rule_overrides)}")
            self._log(f"  - Conflicts: {len(context.conflicts)}")

            self._current_knowledge_context = context
            return context

        except Exception as e:
            self._log(f"Warning: Failed to build knowledge context: {e}", level="WARN")
            return None

    def get_learning_context_for_prompt(self) -> str:
        """
        Get the learning context injection for AI prompts.

        Returns a formatted string to inject into generation prompts.
        """
        if self._current_knowledge_context:
            return get_learning_context_prompt(self._current_knowledge_context)
        return ""

    def get_knowledge_base_status(self) -> dict:
        """Get knowledge base status for UI display."""
        if not self.knowledge_registry:
            return {"available": False, "error": "Knowledge registry not loaded"}

        try:
            external_docs = self.knowledge_registry.get_external_documents()
            internal_docs = self.knowledge_registry.get_internal_documents()
            learning = self.knowledge_registry.read_learning_summary()

            return {
                "available": True,
                "external_count": len(external_docs),
                "internal_count": len(internal_docs),
                "total_runs_analyzed": learning.get("total_runs_analyzed", 0),
                "external_docs": [
                    {"id": d.id, "title": d.title, "type": d.type}
                    for d in external_docs
                ],
                "config": {
                    "sample_size_threshold": self.knowledge_registry.config.sample_size_threshold,
                    "auto_learn_enabled": self.knowledge_registry.config.auto_learn_enabled,
                },
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _flush_log(self, paths: OutputPaths):
        """Write log buffer to run_log.txt."""
        if self._log_buffer:
            paths.run_log.write_text("\n".join(self._log_buffer))

    def run_to_script_approval(
        self,
        config: RunConfig,
        regenerate: bool = False,
    ) -> tuple[bool, OutputPaths | None, str, dict]:
        """
        Run pipeline stages 1-5 and stop at script approval.

        Args:
            config: Run configuration
            regenerate: If True, skip run record creation (reusing existing)

        Returns:
            (success, output_paths, message, script_data)
        """
        self._log_buffer = []
        self._log(f"Starting pipeline run (to script approval): {config.run_id}")
        self._log(f"Config: niche={config.niche}, style={config.style}")

        run_id = config.run_id

        # Step 1: Create or update run record
        if not regenerate:
            self._log("Creating run record in RunStore")
            self.run_store.create_run(run_id, config.to_dict())
        else:
            self._log("Regenerating script (reusing run record)")

        self._update_stage(run_id, RunStage.DRIVE_CHECK)

        # Step 2: DriveGuard check
        self._log("Checking G Drive availability...")
        try:
            drive_result = self.drive_guard.check()
            self._log(f"DriveGuard result: status={drive_result.status.value}, "
                     f"can_write={drive_result.can_write}, "
                     f"detection={drive_result.detection_method}")

            if not drive_result.can_write:
                error_msg = self.drive_guard.format_status_message(drive_result)
                self._log(f"DriveGuard FAILED: {error_msg}", level="ERROR")
                self._update_stage(run_id, RunStage.FAILED, error_message=error_msg)
                return False, None, error_msg, {}

            self._log(f"DriveGuard PASSED: mounted at {drive_result.mount_path}")

        except DriveNotAvailableError as e:
            self._log(f"DriveGuard exception: {e}", level="ERROR")
            self._update_stage(run_id, RunStage.FAILED, error_message=str(e))
            return False, None, str(e), {}

        # Step 3: Create output directory (or reuse existing)
        self._log("Creating output directory structure...")
        paths = self.output_writer.create_run_directory(
            run_id=config.run_id,
            niche=config.niche,
            style=config.style,
        )
        self._log(f"Output directory: {paths.base_dir}")

        # Update run record with output path
        self._update_stage(run_id, RunStage.RESEARCH, output_path=str(paths.base_dir))

        # Step 4: Write config.json
        self._log("Writing config.json...")
        self.output_writer.write_config(paths, config.to_dict())

        # Step 5: Load presets
        self._log("Loading presets...")
        selected_presets = {
            "niche": config.niche,
            "style": config.style,
            "voice": config.voice_preset,
            "visual": config.visual_mode,
            "realism": config.realism_mode,
        }
        fingerprint = self.preset_loader.compute_fingerprint(selected_presets)
        self._log(f"Presets fingerprint: {fingerprint}")

        # Step 5b: Load knowledge context
        knowledge_context = self._load_knowledge_context(config, paths)

        # Step 6: Run stages 1-5 (script generation)
        try:
            script_data = self._run_script_stages(config, paths, fingerprint, knowledge_context)
        except Exception as e:
            self._log(f"Pipeline error: {e}", level="ERROR")
            self._update_stage(run_id, RunStage.FAILED, error_message=str(e))
            self._flush_log(paths)
            return False, paths, str(e), {}

        # Step 7: Mark as awaiting approval
        self._update_stage(
            run_id,
            RunStage.AWAITING_SCRIPT_APPROVAL,
            approvals_pending=["script"],
        )
        self._log("Pipeline paused: awaiting script approval")

        # Flush log to file
        self._flush_log(paths)

        return True, paths, "Script generated. Awaiting approval.", script_data

    def continue_after_approval(
        self,
        run_id: str,
    ) -> tuple[bool, str]:
        """
        Continue pipeline after script approval.

        Generates shot list, visual prompts, and stock queries.

        Args:
            run_id: The run ID to continue

        Returns:
            (success, message)
        """
        self._log(f"Continuing pipeline after approval: {run_id}")

        # Get run record
        run_record = self.run_store.get_run(run_id)
        if not run_record:
            return False, f"Run not found: {run_id}"

        if run_record.stage != RunStage.SCRIPT_APPROVED:
            return False, f"Run not in SCRIPT_APPROVED stage: {run_record.stage.value}"

        # Get output path
        output_path = run_record.output_path
        if not output_path:
            return False, "No output path found for run"

        output_dir = Path(output_path)
        if not output_dir.exists():
            return False, f"Output directory not found: {output_dir}"

        # Load script data
        script_meta_path = output_dir / "script_meta.json"
        script_path = output_dir / "script.txt"

        if not script_meta_path.exists() or not script_path.exists():
            return False, "Script files not found"

        try:
            script_meta = json.loads(script_meta_path.read_text())
            script_text = script_path.read_text()
            script_data = {
                "script": script_text,
                "hook": script_meta.get("hook", ""),
                **script_meta,
            }
        except Exception as e:
            return False, f"Failed to load script: {e}"

        # Get config
        config_data = run_record.config_json
        if isinstance(config_data, str):
            config_data = json.loads(config_data)

        visual_mode = config_data.get("visual_mode", "hybrid")
        realism_mode = config_data.get("realism_mode", "standard")

        try:
            # Stage: Generate Shot List
            self._update_stage(
                run_id,
                RunStage.GENERATING_SHOT_LIST,
                current_stage_name="Generating Shot List",
                progress_percent=40,
            )
            self._log("Generating shot list...")
            self._progress("Generating Shot List", 40)

            shot_list_result = self.provider.generate_shot_list(
                run_id=run_id,
                script=script_data,
                visual_mode=visual_mode,
                output_dir=output_dir,
            )

            if not shot_list_result.success:
                raise Exception(f"Shot list generation failed: {shot_list_result.error_message}")

            shot_list = shot_list_result.artifacts.get("shot_list", [])
            self._log(f"Generated {len(shot_list)} scenes")

            # Stage: Generate Visual Prompts (if applicable)
            if visual_mode in ["nanobanana", "hybrid", "both"]:
                self._update_stage(
                    run_id,
                    RunStage.GENERATING_VISUALS,
                    current_stage_name="Generating Visual Prompts",
                    progress_percent=70,
                )
                self._log("Generating visual prompts...")
                self._progress("Generating Visual Prompts", 70)

                visual_result = self.provider.generate_visual_prompts(
                    run_id=run_id,
                    shot_list={"shot_list": shot_list},
                    visual_mode=visual_mode,
                    realism_mode=realism_mode,
                    output_dir=output_dir,
                )

                if not visual_result.success:
                    self._log(f"Visual prompts warning: {visual_result.error_message}", level="WARN")

            # Stage: Generate Stock Queries (if applicable)
            if visual_mode in ["stock", "hybrid", "both"]:
                self._update_stage(
                    run_id,
                    RunStage.GENERATING_STOCK_QUERIES,
                    current_stage_name="Generating Stock Queries",
                    progress_percent=90,
                )
                self._log("Generating stock queries...")
                self._progress("Generating Stock Queries", 90)

                stock_result = self.provider.generate_stock_queries(
                    run_id=run_id,
                    shot_list={"shot_list": shot_list},
                    output_dir=output_dir,
                )

                if not stock_result.success:
                    self._log(f"Stock queries warning: {stock_result.error_message}", level="WARN")

            # Write clip_prompts_ready.txt and pause for video clips
            self._write_clip_prompts_file(output_dir)
            self._update_stage(
                run_id,
                RunStage.AWAITING_VIDEO_CLIPS,
                current_stage_name="Awaiting Video Clips",
                progress_percent=95,
            )
            self._log("Pipeline paused: awaiting video clips")
            self._progress("Awaiting Video Clips", 95)

            return True, "awaiting_video_clips"

        except Exception as e:
            self._log(f"Post-approval error: {e}", level="ERROR")
            self._update_stage(
                run_id,
                RunStage.FAILED,
                error_message=str(e),
            )
            return False, str(e)

    def _write_clip_prompts_file(self, output_dir: Path) -> None:
        """
        Write clip_prompts_ready.txt with all NanoBanana prompts formatted
        for easy copy-paste into a video generation tool (Veo, Runway, etc.).
        """
        nano_path = output_dir / "nanobanana_prompts.txt"
        out_path = output_dir / "clip_prompts_ready.txt"

        lines = [
            "=" * 60,
            "CLIP PROMPTS READY FOR VIDEO GENERATION",
            "=" * 60,
            f"Generated: {datetime.now().isoformat()}",
            f"Run: {output_dir.name}",
            "",
        ]

        if nano_path.exists():
            for line in nano_path.read_text().strip().splitlines():
                if not line.strip():
                    continue
                if line.startswith("Scene ") and ": " in line:
                    label, _, prompt = line.partition(": ")
                    lines.append("─" * 60)
                    lines.append(label.upper())
                    lines.append("─" * 60)
                    lines.append(prompt)
                    lines.append("")
                else:
                    lines.append(line)
        else:
            lines.append("[WARNING] nanobanana_prompts.txt not found — re-run visual prompt generation")

        lines.append("=" * 60)
        lines.append("END OF CLIP PROMPTS")
        lines.append("=" * 60)

        out_path.write_text("\n".join(lines))
        self._log(f"clip_prompts_ready.txt written ({len(lines)} lines)")

    def resume_from_video_clips(self, run_id: str) -> tuple[bool, str]:
        """
        Resume pipeline after video clips have been submitted by the user.

        Moves stage from AWAITING_VIDEO_CLIPS → VIDEO_CLIPS_READY → COMPLETE.
        (FFmpeg assembly will be wired in here later.)

        Returns:
            (success, final_stage)
        """
        run_record = self.run_store.get_run(run_id)
        if not run_record:
            return False, f"Run not found: {run_id}"

        if run_record.stage not in [RunStage.AWAITING_VIDEO_CLIPS, RunStage.VIDEO_CLIPS_READY]:
            return False, f"Run not in clip-awaiting stage: {run_record.stage.value}"

        try:
            self._update_stage(
                run_id,
                RunStage.VIDEO_CLIPS_READY,
                current_stage_name="Video Clips Ready",
                progress_percent=97,
            )
            self._log(f"Video clips received for {run_id}, starting assembly stage")

            # Stage: Video Assembly
            self._update_stage(
                run_id,
                RunStage.VIDEO_ASSEMBLY,
                current_stage_name="Assembling Video",
                progress_percent=98,
            )
            self._log("Assembly stage (FFmpeg wiring pending)")

            # Mark complete
            self._update_stage(
                run_id,
                RunStage.COMPLETE,
                current_stage_name="Complete",
                progress_percent=100,
            )
            self._log("Pipeline complete")
            return True, "complete"

        except Exception as e:
            self._log(f"Resume from clips error: {e}", level="ERROR")
            self._update_stage(run_id, RunStage.FAILED, error_message=str(e))
            return False, str(e)

    def _run_script_stages(
        self,
        config: RunConfig,
        paths: OutputPaths,
        fingerprint: str,
        knowledge_context: Optional[KnowledgeContext] = None,
    ) -> dict:
        """Run stages 1-5 (script generation) using the configured provider."""
        run_id = config.run_id

        # Get learning context prompt if knowledge context is available
        learning_prompt = ""
        if knowledge_context:
            learning_prompt = get_learning_context_prompt(knowledge_context)
            self._log(f"Knowledge context loaded: {len(knowledge_context.dopamine_requirements)} dopamine levels")

        # Update stage to research
        self._update_stage(run_id, RunStage.RESEARCH)

        # Use the provider to generate script (handles all stages internally)
        provider_type = self.provider.config.provider_type.value
        self._log(f"Using provider: {provider_type}")

        result = self.provider.generate_script(
            run_id=run_id,
            niche=config.niche,
            style=config.style,
            topic=config.topic,
            output_dir=paths.base_dir,
            loop_friendly_ending=config.loop_friendly_ending,
        )

        if not result.success:
            raise RuntimeError(f"Script generation failed: {result.error_message}")

        # Get the generated script data from artifacts
        final_result = result.artifacts

        # Update stage to finalize
        self._update_stage(run_id, RunStage.FINALIZE)
        self._log("Script finalized")

        # The provider already writes script.txt and script_meta.json
        # But we need to add knowledge context and fingerprint to meta
        script_meta_path = paths.base_dir / "script_meta.json"
        if script_meta_path.exists():
            script_meta = json.loads(script_meta_path.read_text())
        else:
            script_meta = {
                "hook": final_result.get("hook", ""),
                "keywords": final_result.get("keywords", []),
                "hashtags": final_result.get("hashtags", []),
                "duration_estimate": final_result.get("duration_estimate", 0),
            }

        script_meta["presets_fingerprint"] = fingerprint

        # Add knowledge context reference if available
        if knowledge_context:
            script_meta["knowledge_context"] = {
                "dopamine_levels_applied": len(knowledge_context.dopamine_requirements),
                "internal_insights_applied": len(knowledge_context.internal_insights),
                "rule_overrides_applied": len(knowledge_context.rule_overrides),
                "conflicts_detected": len(knowledge_context.conflicts),
            }

        # Rewrite script_meta with additional fields
        script_meta_path.write_text(json.dumps(script_meta, indent=2))

        return final_result

    def run(self, config: RunConfig) -> tuple[bool, OutputPaths | None, str]:
        """
        Execute the full pipeline (all stages).

        Args:
            config: Run configuration

        Returns:
            (success, output_paths, message)
        """
        self._log_buffer = []
        self._log(f"Starting pipeline run: {config.run_id}")
        self._log(f"Config: niche={config.niche}, style={config.style}, dry_run={config.dry_run}")

        # Step 1: Create run record
        self._log("Creating run record in RunStore")
        run_record = self.run_store.create_run(config.run_id, config.to_dict())
        self._update_stage(run_record.run_id, RunStage.DRIVE_CHECK)

        # Step 2: DriveGuard check
        self._log("Checking G Drive availability...")
        try:
            drive_result = self.drive_guard.check()
            self._log(f"DriveGuard result: status={drive_result.status.value}, "
                     f"can_write={drive_result.can_write}, "
                     f"detection={drive_result.detection_method}")

            if not drive_result.can_write:
                error_msg = self.drive_guard.format_status_message(drive_result)
                self._log(f"DriveGuard FAILED: {error_msg}", level="ERROR")
                self._update_stage(
                    run_record.run_id,
                    RunStage.FAILED,
                    error_message=error_msg,
                )
                return False, None, error_msg

            self._log(f"DriveGuard PASSED: mounted at {drive_result.mount_path}")

        except DriveNotAvailableError as e:
            self._log(f"DriveGuard exception: {e}", level="ERROR")
            self._update_stage(
                run_record.run_id,
                RunStage.FAILED,
                error_message=str(e),
            )
            return False, None, str(e)

        # Step 3: Create output directory
        self._log("Creating output directory structure...")
        paths = self.output_writer.create_run_directory(
            run_id=config.run_id,
            niche=config.niche,
            style=config.style,
        )
        self._log(f"Output directory: {paths.base_dir}")

        # Update run record with output path
        self._update_stage(
            run_record.run_id,
            RunStage.RESEARCH,
            output_path=str(paths.base_dir),
        )

        # Step 4: Write config.json
        self._log("Writing config.json...")
        self.output_writer.write_config(paths, config.to_dict())

        # Step 5: Load presets and compute fingerprint
        self._log("Loading presets...")
        selected_presets = {
            "niche": config.niche,
            "style": config.style,
            "voice": config.voice_preset,
            "visual": config.visual_mode,
            "realism": config.realism_mode,
        }
        fingerprint = self.preset_loader.compute_fingerprint(selected_presets)
        self._log(f"Presets fingerprint: {fingerprint}")

        # Validate presets exist
        is_valid, missing = self.preset_loader.validate_selection(selected_presets)
        if not is_valid:
            self._log(f"Missing presets: {missing}", level="WARN")

        # Step 6: Run pipeline stages with stub responses
        try:
            script_result = self._run_stages(config, paths, fingerprint)
        except Exception as e:
            self._log(f"Pipeline error: {e}", level="ERROR")
            self._update_stage(run_record.run_id, RunStage.FAILED, error_message=str(e))
            self._flush_log(paths)
            return False, paths, str(e)

        # Step 7: Mark complete
        self._update_stage(run_record.run_id, RunStage.COMPLETE)
        self._log("Pipeline completed successfully")

        # Flush log to file
        self._flush_log(paths)

        return True, paths, "Pipeline completed successfully"

    def _update_stage(
        self,
        run_id: str,
        stage: RunStage,
        output_path: str | None = None,
        error_message: str | None = None,
        approvals_pending: list[str] | None = None,
        current_stage_name: str | None = None,
        progress_percent: int | None = None,
    ):
        """Update stage in RunStore and log."""
        self._log(f"Stage transition: -> {stage.value}")

        # Get stage info for progress
        stage_info = STAGE_INFO.get(stage.value, {})
        progress = progress_percent if progress_percent is not None else stage_info.get("progress", 0)
        stage_name = current_stage_name or stage_info.get("name", stage.value)

        self.run_store.update_stage(
            run_id,
            stage,
            output_path=output_path,
            error_message=error_message,
            approvals_pending=approvals_pending,
            current_stage_name=stage_name,
            progress_percent=progress,
        )

    def _run_stages(
        self,
        config: RunConfig,
        paths: OutputPaths,
        fingerprint: str,
    ) -> dict:
        """
        Run all pipeline stages.

        Uses stub responses - no external API calls.
        """
        run_id = config.run_id

        # Stage 1: Research (stub)
        self._update_stage(run_id, RunStage.RESEARCH)
        self._log("Stage 1: Research (stub)")
        research_result = self._stub_research(config)
        self._log(f"Research complete: {len(research_result['topics'])} topics found")

        # Stage 2: Draft (stub)
        self._update_stage(run_id, RunStage.DRAFT)
        self._log("Stage 2: Draft (stub)")
        draft_result = self._stub_draft(config, research_result)
        self._log(f"Draft complete: {len(draft_result['script'])} chars")

        # Stage 3: Hook Review (stub)
        self._update_stage(run_id, RunStage.HOOK_REVIEW)
        self._log("Stage 3: Hook Review (stub)")
        hook_result = self._stub_hook_review(draft_result)
        self._log(f"Hook: {hook_result['hook'][:50]}...")

        # Stage 4: Relevance Check (stub)
        self._update_stage(run_id, RunStage.RELEVANCE)
        self._log("Stage 4: Relevance Check (stub)")
        relevance_result = self._stub_relevance(draft_result, config)
        self._log(f"Relevance score: {relevance_result['score']}")

        # Stage 5: Finalize (stub)
        self._update_stage(run_id, RunStage.FINALIZE)
        self._log("Stage 5: Finalize (stub)")
        final_result = self._stub_finalize(draft_result, hook_result)
        self._log("Script finalized")

        # Write script artifacts
        self._log("Writing script.txt...")
        self.output_writer.write_script(paths, final_result["script"])

        self._log("Writing script_meta.json...")
        self.output_writer.write_script_meta(paths, {
            "hook": final_result["hook"],
            "keywords": final_result["keywords"],
            "hashtags": final_result["hashtags"],
            "duration_estimate": final_result["duration_estimate"],
            "presets_fingerprint": fingerprint,
        })

        # Stage 6: Shot List (stub) - if enabled
        if config.generate_shot_list:
            self._update_stage(run_id, RunStage.SHOT_LIST)
            self._log("Stage 6: Shot List (stub)")
            shot_list = self._stub_shot_list(final_result, config)
            self._log(f"Generated {len(shot_list)} scenes")

            # Write shot list artifacts
            self._log("Writing shot_list.json...")
            self.output_writer.write_shot_list(paths, shot_list)

            self._log("Writing shot_list.md...")
            md_content = self._format_shot_list_md(shot_list)
            self.output_writer.write_shot_list_markdown(paths, md_content)

            if config.visual_mode in ["nanobanana", "hybrid", "both"]:
                self._log("Writing nanobanana_prompts.txt...")
                prompts = self._format_nanobanana_prompts(shot_list)
                self.output_writer.write_nanobanana_prompts(paths, prompts)

            if config.visual_mode in ["stock", "hybrid", "both"]:
                self._log("Writing stock_queries.txt...")
                queries = self._format_stock_queries(shot_list)
                self.output_writer.write_stock_queries(paths, queries)

        return final_result

    # === STUB RESPONSES ===

    def _stub_research(self, config: RunConfig) -> dict:
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

    def _stub_draft(self, config: RunConfig, research: dict) -> dict:
        """Stub draft response."""
        if config.niche == "motivation":
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

    def _stub_relevance(self, draft: dict, config: RunConfig) -> dict:
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

    def _stub_shot_list(self, final: dict, config: RunConfig) -> list[dict]:
        """
        Generate shot list with detailed NanoBanana prompts.

        Uses the structured prompt generator to create reproducible,
        detailed visual specifications for each scene.
        """
        script = final["script"]

        # Create 6 beats from script
        beats = ["HOOK", "TENSION", "SHIFT", "CLIMB", "RESOLUTION", "CTA"]
        num_beats = len(beats)

        # Get segments properly split
        segments = self._split_script_into_segments(script, num_beats)
        scenes = []
        prior_spec = None

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

            # Get overlay text if this scene should have one
            overlay_text = None
            if i in [0, 2, 4, 5]:  # HOOK, SHIFT, RESOLUTION, CTA
                overlay = self._stub_overlay(beat, segment)
                overlay_text = overlay.get("text")

            # Generate detailed prompt with structured spec
            nano_prompt, prompt_spec = self._stub_nano_prompt(
                beat=beat,
                segment=segment,
                config=config,
                scene_number=i + 1,
                prior_spec=prior_spec,
                overlay_text=overlay_text,
            )

            # Update negatives from spec
            negative_search = prompt_spec.get("negatives", {}).get("standard", [])[:6]
            if not negative_search:
                negative_search = ["text overlay", "watermark", "logo", "cartoon", "distorted", "blurry"]

            scene = {
                "scene_number": i + 1,
                "beat_type": beat,
                "voiceover_segment": segment,
                "duration": 3.0 + (i * 1.5),
                "visual_description": self._stub_visual_for_beat(beat, segment),
                "search_tight": self._stub_search_tight(beat, segment),
                "search_broad": self._stub_search_broad(beat),
                "negative_search": negative_search,
                "nano_prompt": nano_prompt,
                "prompt_spec": prompt_spec,  # Full structured specification
                "overlay": self._stub_overlay(beat, segment) if i in [0, 2, 4, 5] else None,
                "match_score": 0.85 + (i * 0.02),
                "word_count": prompt_spec.get("full_prompt", "").count(" ") + 1,
            }
            scenes.append(scene)

            # Store spec for continuity to next scene
            # Reconstruct minimal spec for continuity reference
            prior_spec = self._dict_to_minimal_spec(prompt_spec)

        return scenes

    def _dict_to_minimal_spec(self, spec_dict: dict) -> ScenePromptSpec | None:
        """Convert spec dict back to minimal ScenePromptSpec for continuity."""
        try:
            from content_engine.pipeline.prompt_spec import (
                CameraSpec, SubjectSpec, EnvironmentSpec, LightingSpec,
                ColorStyleSpec, ContinuitySpec, OutputFormatSpec,
                ShotType, CameraAngle, CameraMovement, TimeOfDay, LightingStyle,
            )

            # Create minimal spec for continuity reference
            return ScenePromptSpec(
                scene_number=spec_dict.get("scene_number", 0),
                beat_type=spec_dict.get("beat_type", ""),
                voiceover_segment=spec_dict.get("voiceover_segment", ""),
                subject=SubjectSpec(
                    age_range=spec_dict.get("subject", {}).get("age_range", ""),
                    wardrobe=spec_dict.get("subject", {}).get("wardrobe", ""),
                ),
                environment=EnvironmentSpec(
                    location_type=spec_dict.get("environment", {}).get("location_type", ""),
                ),
            )
        except Exception:
            return None

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

    def _stub_nano_prompt(
        self,
        beat: str,
        segment: str,
        config: RunConfig,
        scene_number: int = 1,
        prior_spec: ScenePromptSpec | None = None,
        overlay_text: str | None = None,
    ) -> tuple[str, dict]:
        """
        Generate detailed NanoBanana prompt using the structured generator.

        Returns:
            Tuple of (prompt_text, prompt_spec_dict)
        """
        # Get visual preset for configuration
        visual_preset = {}
        if config and hasattr(config, 'visual_mode'):
            visual_preset = self.preset_loader.get_visual_preset(config.visual_mode) or {}

        # Get prompt detail level from preset (default to ultra)
        prompt_settings = visual_preset.get("prompt_settings", {})
        detail_level = prompt_settings.get("detail_level", "ultra")

        # Get entities for continuity
        entities = []
        if hasattr(self, 'run_store') and config:
            try:
                # Load entities from run store if available
                run_record = self.run_store.get_run(config.run_id) if hasattr(config, 'run_id') else None
                if run_record and run_record.output_path:
                    entities = self._load_entities_from_run(run_record.run_id)
            except Exception:
                pass

        # Get niche for visual strategy selection
        niche = config.niche if config and hasattr(config, 'niche') else None

        # Generate the structured prompt spec
        spec = generate_nanobanana_prompt(
            scene_number=scene_number,
            beat_type=beat,
            voiceover=segment,
            detail_level=detail_level,
            visual_preset=visual_preset,
            entities=entities,
            prior_scene_spec=prior_spec,
            overlay_text=overlay_text,
            niche=niche,  # Pass niche for visual strategy (motivation = no people)
        )

        return spec.to_full_prompt(), spec.to_dict()

    def _load_entities_from_run(self, run_id: str) -> list[dict]:
        """Load continuity entities for a run."""
        try:
            entities = self.run_store.get_entities(run_id)
            return [{"name": e.name, "description": e.description} for e in entities]
        except Exception:
            return []

    def _stub_nano_prompt_simple(self, beat: str, segment: str, config: RunConfig) -> str:
        """Fallback simple prompt generator (backward compatibility)."""
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

    def _format_nanobanana_prompts(self, shot_list: list[dict]) -> str:
        """
        Format NanoBanana prompts for copy-paste.

        Includes detailed prompts with negative prompts and word counts.
        """
        lines = [
            "# NanoBanana Prompts",
            "",
            "_Generated with ULTRA detail level for maximum reproducibility._",
            "",
        ]

        for scene in shot_list:
            scene_num = scene['scene_number']
            beat = scene['beat_type']
            prompt = scene['nano_prompt']
            word_count = scene.get('word_count', len(prompt.split()))

            lines.append(f"## Scene {scene_num}: {beat}")
            lines.append(f"**Word Count:** {word_count}")
            lines.append("")
            lines.append("### Positive Prompt")
            lines.append(f"```")
            lines.append(prompt)
            lines.append(f"```")
            lines.append("")

            # Add negative prompt if available
            prompt_spec = scene.get('prompt_spec', {})
            negative = prompt_spec.get('negative_prompt', '')
            if not negative:
                negative = ", ".join(scene.get('negative_search', []))

            if negative:
                lines.append("### Negative Prompt")
                lines.append(f"```")
                lines.append(negative)
                lines.append(f"```")
                lines.append("")

            # Add overlay info if present
            if scene.get('overlay'):
                overlay = scene['overlay']
                lines.append(f"**Overlay Text:** \"{overlay.get('text', '')}\" ({overlay.get('position', 'center')})")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _format_stock_queries(self, shot_list: list[dict]) -> str:
        """Format stock footage search queries."""
        lines = ["# Stock Footage Queries\n"]

        for scene in shot_list:
            lines.append(f"## Scene {scene['scene_number']} ({scene['beat_type']})")
            lines.append(f"**Tight:** {scene['search_tight']}")
            lines.append(f"**Broad:** {scene['search_broad']}")
            lines.append(f"**Exclude:** {', '.join(scene['negative_search'])}\n")

        return "\n".join(lines)

    # === PROMPT REGENERATION ===

    def regenerate_nanobanana_prompt(
        self,
        run_id: str,
        item_key: str,
        shot_context: dict,
        feedback: str | None = None,
    ) -> str:
        """
        Regenerate a NanoBanana prompt for a specific scene.

        Args:
            run_id: Run identifier
            item_key: Scene key (e.g., "scene_1")
            shot_context: Context from shot list
            feedback: Optional user feedback for improvement

        Returns:
            New prompt text
        """
        # Extract scene info from context
        beat_type = shot_context.get("beat_type", "HOOK")
        voiceover = shot_context.get("voiceover_segment", "")
        visual_desc = shot_context.get("visual_description", "")

        # Determine visual strategy based on niche
        no_people_niches = {"motivation", "stoicism", "stoic", "mindset", "philosophy", "fun_facts", "facts", "edgy_funny"}
        use_environment_visuals = False

        try:
            run_record = self.run_store.get_run(run_id) if hasattr(self, 'run_store') else None
            if run_record and run_record.config:
                niche = run_record.config.get("niche", "").lower()
                use_environment_visuals = niche in no_people_niches
        except Exception:
            pass

        # Build regeneration prompt
        system_prompt = """You are a visual prompt engineer for AI video generation.
Generate a NanoBanana/MidJourney-style prompt for a short-form video scene.

Requirements:
- 9:16 vertical aspect ratio
- Cinematic, professional quality
- Emotional impact matching the beat type
- No text, logos, or watermarks in the visual
- Filmic color grading
"""

        # Add no-people constraint for motivation/stoic niches
        if use_environment_visuals:
            system_prompt += """
CRITICAL: This is for a motivation/philosophical content niche.
DO NOT include any people, human figures, faces, hands, or silhouettes.
Instead use: abstract metaphors, landscapes, symbols, objects, nature, light/shadow.
Focus on: environment, atmosphere, symbolic imagery that conveys emotion.
"""

        user_prompt = f"""Generate a NanoBanana prompt for this scene:

Beat Type: {beat_type}
Voiceover: {voiceover}
Visual Description: {visual_desc}
"""

        if use_environment_visuals:
            user_prompt += "\nIMPORTANT: NO PEOPLE in this visual. Use abstract/metaphor imagery only.\n"

        if feedback:
            user_prompt += f"\nUser feedback for improvement: {feedback}\n"

        user_prompt += "\nRespond with ONLY the prompt text, no explanations."

        # Use provider to generate
        try:
            result = self.provider.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return result.strip()
        except Exception as e:
            self._log(f"NanoBanana regeneration failed: {e}", level="ERROR")
            # Fallback to stub
            return self._stub_nano_prompt(beat_type, voiceover, None)

    def regenerate_stock_query(
        self,
        run_id: str,
        item_key: str,
        shot_context: dict,
        feedback: str | None = None,
    ) -> str:
        """
        Regenerate stock footage search queries for a scene.

        Args:
            run_id: Run identifier
            item_key: Scene key (e.g., "scene_1")
            shot_context: Context from shot list
            feedback: Optional user feedback for improvement

        Returns:
            Formatted search queries (tight, broad, negative)
        """
        beat_type = shot_context.get("beat_type", "HOOK")
        voiceover = shot_context.get("voiceover_segment", "")
        visual_desc = shot_context.get("visual_description", "")

        system_prompt = """You are a stock footage search expert.
Generate effective search queries for finding matching video clips.

Provide:
1. Tight query: Very specific, 4-6 keywords
2. Broad query: General mood/theme, 3-4 keywords
3. Negative terms: What to exclude

Format your response as:
TIGHT: [keywords]
BROAD: [keywords]
NEGATIVE: [keywords]
"""

        user_prompt = f"""Generate stock footage queries for this scene:

Beat Type: {beat_type}
Voiceover: {voiceover}
Visual Description: {visual_desc}
"""

        if feedback:
            user_prompt += f"\nUser feedback: {feedback}\n"

        try:
            result = self.provider.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return result.strip()
        except Exception as e:
            self._log(f"Stock query regeneration failed: {e}", level="ERROR")
            # Fallback to stub
            tight = self._stub_search_tight(beat_type, voiceover)
            broad = self._stub_search_broad(beat_type)
            return f"TIGHT: {tight}\nBROAD: {broad}\nNEGATIVE: text overlay, watermark, logo"
