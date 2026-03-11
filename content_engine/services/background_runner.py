"""
Background runner for pipeline execution.

Runs pipeline stages in a background thread, updating progress via RunStore.
"""

import threading
import logging
import traceback
from datetime import datetime
from pathlib import Path

from content_engine.services.run_store import RunStore, RunStage, generate_display_title, ArtifactType
from content_engine.pipeline.models.run_config import RunConfig
from content_engine.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)

# Thread-local storage for tracking active runs
_active_runs: dict[str, threading.Thread] = {}


def _write_log(output_path: Path | None, message: str):
    """Append a message to run_log.txt."""
    if not output_path:
        return
    try:
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        log_file = output_dir / "run_log.txt"
        timestamp = datetime.utcnow().isoformat()
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        logger.warning(f"Failed to write log: {e}")


def _store_prompt_versions(run_id: str, shot_list: list[dict], visual_mode: str, store: RunStore):
    """
    Store prompt versions for each scene's NanoBanana prompts and stock queries.

    SEQUENTIAL GENERATION:
    - Scene 1: Generated immediately with full prompt (ACTIVE status)
    - Scenes 2+: Created as PENDING placeholders, waiting for previous scene to be locked

    This populates the prompt_versions table so the artifacts page shows real data.
    """
    from .run_store import PromptStatus

    try:
        total_scenes = len(shot_list)

        for scene in shot_list:
            scene_num = scene.get("scene_number", 0)
            beat_type = scene.get("beat_type", "UNKNOWN")
            item_key = f"scene_{scene_num}"

            # Determine if this is scene 1 (generate fully) or later (pending)
            is_first_scene = scene_num == 1
            prev_scene_key = f"scene_{scene_num - 1}" if scene_num > 1 else None

            # Store NanoBanana prompt
            nano_prompt = scene.get("nano_prompt", "")
            if visual_mode in ["nanobanana", "hybrid", "both", "nanobanana_cinematic"]:
                if is_first_scene:
                    # Scene 1: Generate fully with ACTIVE status
                    store.create_prompt_version(
                        run_id=run_id,
                        artifact_type=ArtifactType.NANOBANANA,
                        item_key=item_key,
                        prompt_text=nano_prompt,
                        notes=f"Beat: {beat_type}, Duration: {scene.get('duration', 0)}s",
                        created_by="system",
                        status=PromptStatus.ACTIVE,
                    )
                else:
                    # Scenes 2+: Create PENDING placeholder
                    store.create_prompt_version(
                        run_id=run_id,
                        artifact_type=ArtifactType.NANOBANANA,
                        item_key=item_key,
                        prompt_text="",  # Empty - will be generated when previous scene is locked
                        notes=f"Beat: {beat_type}, Duration: {scene.get('duration', 0)}s | Pending: waiting for {prev_scene_key} to be locked",
                        created_by="system",
                        status=PromptStatus.PENDING,
                        depends_on_scene=prev_scene_key,
                    )

            # Store stock queries (combine tight + broad)
            search_tight = scene.get("search_tight", "")
            search_broad = scene.get("search_broad", "")
            negative = scene.get("negative_search", [])

            if visual_mode in ["stock", "hybrid", "both", "stock_only"]:
                query_text = f"Tight: {search_tight}\nBroad: {search_broad}\nExclude: {', '.join(negative)}"
                if is_first_scene:
                    store.create_prompt_version(
                        run_id=run_id,
                        artifact_type=ArtifactType.STOCK_QUERY,
                        item_key=item_key,
                        prompt_text=query_text,
                        notes=f"Beat: {beat_type}",
                        created_by="system",
                        status=PromptStatus.ACTIVE,
                    )
                else:
                    store.create_prompt_version(
                        run_id=run_id,
                        artifact_type=ArtifactType.STOCK_QUERY,
                        item_key=item_key,
                        prompt_text="",  # Empty - will be generated when previous scene is locked
                        notes=f"Beat: {beat_type} | Pending: waiting for {prev_scene_key} to be locked",
                        created_by="system",
                        status=PromptStatus.PENDING,
                        depends_on_scene=prev_scene_key,
                    )

        logger.info(f"[{run_id}] Stored {len(shot_list)} prompt versions (scene 1 active, scenes 2-{total_scenes} pending)")

    except Exception as e:
        logger.warning(f"[{run_id}] Failed to store prompt versions: {e}")


def execute_run(run_id: str, config: RunConfig) -> None:
    """
    Execute a pipeline run in the background.

    Updates run stage as it progresses, writes to run_log.txt,
    catches exceptions and marks FAILED on error.

    Note: Run record should already exist (created by /wizard/start).
    The orchestrator will update stages as it progresses.

    Args:
        run_id: Run identifier
        config: RunConfig for this run
    """
    store = RunStore()
    output_path = None

    try:
        # Mark as running (orchestrator will update to more specific stages)
        store.update_stage(
            run_id,
            RunStage.RUNNING,
            current_stage_name="Initializing",
            progress_percent=5,
        )
        logger.info(f"[{run_id}] Background execution started")

        # Run the pipeline (orchestrator updates stages via RunStore internally)
        orchestrator = PipelineOrchestrator()

        # Execute pipeline to script approval
        # Note: orchestrator.run_to_script_approval expects run record to NOT exist,
        # but since we already created it, we pass regenerate=True to skip creation
        success, paths, message, script_data = orchestrator.run_to_script_approval(
            config,
            regenerate=True,  # Skip run record creation since we already did it
        )

        # Get output path from paths object
        if paths:
            output_path = str(paths.base_dir)
            _write_log(output_path, f"Pipeline execution completed")

        if success:
            # Generate display title from hook
            if script_data and script_data.get("hook"):
                display_title = generate_display_title(script_data["hook"])
                short_title = generate_display_title(script_data["hook"], max_words=4)
                store.update_title(run_id, display_title, short_title)
                _write_log(output_path, f"Generated title: {display_title}")

            # Stage is already set by orchestrator, just log
            _write_log(output_path, "Pipeline complete - awaiting script approval")
            logger.info(f"[{run_id}] Pipeline complete - awaiting script approval")

        else:
            # Mark as failed
            store.update_stage(
                run_id,
                RunStage.FAILED,
                output_path=output_path,
                error_message=message,
                current_stage_name="Failed",
                progress_percent=0,
            )
            _write_log(output_path, f"Pipeline failed: {message}")
            logger.error(f"[{run_id}] Pipeline failed: {message}")

    except Exception as e:
        # Log full traceback
        tb = traceback.format_exc()
        error_msg = f"{type(e).__name__}: {str(e)}"

        logger.exception(f"[{run_id}] Pipeline exception: {e}")
        _write_log(output_path, f"EXCEPTION: {error_msg}\n{tb}")

        # Mark as failed
        store.update_stage(
            run_id,
            RunStage.FAILED,
            output_path=output_path,
            error_message=error_msg,
            current_stage_name="Failed",
            progress_percent=0,
        )

    finally:
        # Remove from active runs
        if run_id in _active_runs:
            del _active_runs[run_id]


def start_run_async(run_id: str, config: RunConfig) -> bool:
    """
    Start a pipeline run in a background thread.

    Args:
        run_id: Run identifier
        config: RunConfig for this run

    Returns:
        True if started, False if run is already active
    """
    if run_id in _active_runs:
        logger.warning(f"[{run_id}] Run already active, skipping")
        return False

    # Create and start thread
    thread = threading.Thread(
        target=execute_run,
        args=(run_id, config),
        name=f"run-{run_id}",
        daemon=True,  # Don't block process exit
    )

    _active_runs[run_id] = thread
    thread.start()

    logger.info(f"[{run_id}] Started background execution")
    return True


def continue_after_approval(run_id: str) -> None:
    """
    Continue pipeline after script approval.

    Generates:
    - Shot list (shot_list.json, shot_list.md)
    - Visual prompts (nanobanana_prompts.txt)
    - Stock queries (stock_queries.txt)

    Then marks as COMPLETE.

    Args:
        run_id: Run identifier
    """
    store = RunStore()
    output_path = None

    try:
        # Get run record
        record = store.get_run(run_id)
        if not record:
            logger.error(f"[{run_id}] Run not found for continuation")
            return

        output_path = record.output_path
        config_dict = record.config

        # Mark as generating shot list
        store.update_stage(
            run_id,
            RunStage.GENERATING_SHOT_LIST,
            current_stage_name="Generating Shot List",
            progress_percent=20,
        )
        _write_log(output_path, "Starting post-approval continuation")
        _write_log(output_path, "Stage: Generating Shot List")
        logger.info(f"[{run_id}] Generating shot list")

        # Create orchestrator to use its stub methods
        orchestrator = PipelineOrchestrator()

        # Load script to generate shot list
        script_path = Path(output_path) / "script.txt"
        script_meta_path = Path(output_path) / "script_meta.json"

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found at {script_path}")

        script_text = script_path.read_text()
        script_meta = {}
        if script_meta_path.exists():
            import json
            script_meta = json.loads(script_meta_path.read_text())

        # Generate shot list using orchestrator's stub
        final_result = {
            "script": script_text,
            "hook": script_meta.get("hook", script_text.split("\n")[0]),
            "keywords": script_meta.get("keywords", []),
            "hashtags": script_meta.get("hashtags", []),
            "duration_estimate": script_meta.get("duration_estimate", 30),
        }

        # Create a mock config for visual mode
        visual_mode = config_dict.get("visual_mode", "hybrid")

        shot_list = orchestrator._stub_shot_list(final_result, type("Config", (), {"visual_mode": visual_mode})())
        _write_log(output_path, f"Generated {len(shot_list)} scenes")

        # Write shot_list.json
        import json
        shot_list_path = Path(output_path) / "shot_list.json"
        shot_list_path.write_text(json.dumps(shot_list, indent=2))
        _write_log(output_path, "Wrote shot_list.json")

        # Write shot_list.md
        store.update_stage(
            run_id,
            RunStage.GENERATING_VISUALS,
            current_stage_name="Creating Visual Prompts",
            progress_percent=50,
        )
        _write_log(output_path, "Stage: Creating Visual Prompts")

        md_content = orchestrator._format_shot_list_md(shot_list)
        md_path = Path(output_path) / "shot_list.md"
        md_path.write_text(md_content)
        _write_log(output_path, "Wrote shot_list.md")

        # Write nanobanana_prompts.txt
        if visual_mode in ["nanobanana", "hybrid", "both", "nanobanana_cinematic"]:
            prompts = orchestrator._format_nanobanana_prompts(shot_list)
            prompts_path = Path(output_path) / "nanobanana_prompts.txt"
            prompts_path.write_text(prompts)
            _write_log(output_path, "Wrote nanobanana_prompts.txt")

        # Write stock_queries.txt
        store.update_stage(
            run_id,
            RunStage.GENERATING_STOCK_QUERIES,
            current_stage_name="Building Stock Queries",
            progress_percent=80,
        )
        _write_log(output_path, "Stage: Building Stock Queries")

        if visual_mode in ["stock", "hybrid", "both", "stock_only"]:
            queries = orchestrator._format_stock_queries(shot_list)
            queries_path = Path(output_path) / "stock_queries.txt"
            queries_path.write_text(queries)
            _write_log(output_path, "Wrote stock_queries.txt")

        # Store prompt versions for each scene
        _write_log(output_path, "Storing prompt versions in database")
        _store_prompt_versions(run_id, shot_list, visual_mode, store)
        _write_log(output_path, f"Stored {len(shot_list)} scene prompts")

        # Mark as complete
        store.update_stage(
            run_id,
            RunStage.COMPLETE,
            current_stage_name="Complete",
            progress_percent=100,
        )
        _write_log(output_path, "Pipeline complete - all artifacts generated")
        logger.info(f"[{run_id}] Post-approval continuation complete")

    except Exception as e:
        # Log full traceback
        tb = traceback.format_exc()
        error_msg = f"{type(e).__name__}: {str(e)}"

        logger.exception(f"[{run_id}] Post-approval continuation failed: {e}")
        _write_log(output_path, f"EXCEPTION: {error_msg}\n{tb}")

        # Mark as failed
        store.update_stage(
            run_id,
            RunStage.FAILED,
            error_message=error_msg,
            current_stage_name="Failed",
            progress_percent=0,
        )

    finally:
        # Remove from active runs
        if run_id in _active_runs:
            del _active_runs[run_id]


def start_continuation_async(run_id: str) -> bool:
    """
    Start post-approval continuation in a background thread.

    Args:
        run_id: Run identifier

    Returns:
        True if started, False if run is already active
    """
    if run_id in _active_runs:
        logger.warning(f"[{run_id}] Run already active, skipping")
        return False

    # Create and start thread
    thread = threading.Thread(
        target=continue_after_approval,
        args=(run_id,),
        name=f"continue-{run_id}",
        daemon=True,
    )

    _active_runs[run_id] = thread
    thread.start()

    logger.info(f"[{run_id}] Started post-approval continuation")
    return True


def is_run_active(run_id: str) -> bool:
    """Check if a run is currently executing."""
    return run_id in _active_runs and _active_runs[run_id].is_alive()


def get_active_runs() -> list[str]:
    """Get list of currently executing run IDs."""
    return [rid for rid, thread in _active_runs.items() if thread.is_alive()]
