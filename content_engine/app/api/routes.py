"""
API routes for wizard.

All state transitions go through RunStore and orchestrator.
Returns HTML fragments for HTMX requests, JSON for API calls.
"""

from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from content_engine.services.drive_guard import DriveGuard
from content_engine.services.preset_loader import PresetLoader
from content_engine.services.run_store import RunStore, RunStage
from content_engine.services.background_runner import start_continuation_async
from content_engine.services.concurrency import (
    get_concurrency_manager,
    RunLimitExceeded,
    RegenerationLimitExceeded,
)
from content_engine.pipeline.orchestrator import PipelineOrchestrator
from content_engine.pipeline.models.run_config import RunConfig

from .schemas import (
    GenerateRequest,
    ApproveScriptRequest,
    RegenerateScriptRequest,
    DriveStatusResponse,
    RunStatusResponse,
    NotesUpdateRequest,
    FeedbackRequest,
    FeedbackResponse,
    PresetStatsResponse,
    TuningMemoRequest,
    TuningMemoResponse,
    QuickFeedbackRequest,
    PresetEditRequest,
    PresetEditResponse,
    RegeneratePromptRequest,
    RegeneratePromptResponse,
    PromptVersionResponse,
    PromptStatsResponse,
    StorageConfigRequest,
    StorageConfigResponse,
    StorageStatsResponse,
    StorageCleanupRequest,
    StorageCleanupResponse,
    VoiceSettingsRequest,
    VoiceGenerateRequest,
    VoiceGenerationResponse,
    SceneContextResponse,
)
from content_engine.services.run_store import (
    FeedbackRecord,
    generate_display_title,
    ArtifactType,
    PromptStatus,
    EntityType,
)
from content_engine.services.storage_manager import (
    get_storage_manager,
    StorageConfig,
)

router = APIRouter(prefix="/api")

# Templates for HTML fragments
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=templates_dir)


def is_htmx_request(request: Request) -> bool:
    """Check if request is from HTMX."""
    return request.headers.get("HX-Request") == "true"


# === Drive Status ===

@router.get("/drive/status")
async def get_drive_status(request: Request):
    """Check G Drive availability."""
    guard = DriveGuard()
    result = guard.check()

    data = {
        "connected": result.can_write,
        "mount_path": str(result.mount_path) if result.mount_path else None,
        "error_message": result.error_message,
        "mount_command": result.mount_command,
    }

    if is_htmx_request(request):
        # Return HTML fragment
        if result.can_write:
            return HTMLResponse(
                '<div class="alert-success rounded-xl p-3">'
                '<span class="text-green-400 text-sm">G Drive connected</span>'
                '</div>'
            )
        else:
            return HTMLResponse(
                f'<div class="alert-error rounded-xl p-3">'
                f'<span class="text-red-400 text-sm">G Drive not connected: {result.error_message}</span>'
                f'</div>'
            )

    return JSONResponse(data)


# === Presets ===

@router.get("/presets/niches")
async def list_niches():
    """List available niches."""
    loader = PresetLoader()
    presets = loader.get_all_presets("niches")
    return [
        {
            "name": p.name,
            "display_name": p.data.get("display_name", p.name),
            "description": p.data.get("description", ""),
        }
        for p in presets
    ]


@router.get("/presets/styles")
async def list_styles():
    """List available styles."""
    loader = PresetLoader()
    presets = loader.get_all_presets("styles")
    return [
        {
            "name": p.name,
            "display_name": p.data.get("display_name", p.name),
            "description": p.data.get("description", ""),
            "energy": p.data.get("energy", "medium"),
        }
        for p in presets
    ]


@router.get("/presets/voices")
async def list_voices():
    """List available voice presets."""
    loader = PresetLoader()
    presets = loader.get_all_presets("voices")
    return [
        {
            "name": p.name,
            "display_name": p.data.get("display_name", p.name),
            "description": p.data.get("description", ""),
        }
        for p in presets
    ]


@router.get("/voices")
async def list_elevenlabs_voices():
    """Fetch all available ElevenLabs voices with preview URLs."""
    import os
    from elevenlabs.client import ElevenLabs

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY not set")

    try:
        client = ElevenLabs(api_key=api_key)
        response = client.voices.get_all()
        voices = []
        for v in response.voices:
            voices.append({
                "voice_id":    v.voice_id or "",
                "name":        v.name or "",
                "category":    v.category or "generated",
                "description": v.description or "",
                "preview_url": v.preview_url or "",
            })
        voices.sort(key=lambda v: (0 if v["category"] == "premade" else 1, v["name"].lower()))
        return voices
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ElevenLabs API error: {str(e)}")


@router.get("/presets/visuals")
async def list_visuals():
    """List available visual modes."""
    loader = PresetLoader()
    presets = loader.get_all_presets("visuals")
    return [
        {
            "name": p.name,
            "display_name": p.data.get("display_name", p.name),
            "description": p.data.get("description", ""),
        }
        for p in presets
    ]


# === Pipeline ===

@router.post("/pipeline/start")
async def start_pipeline(request: Request, payload: GenerateRequest):
    """
    Start pipeline and generate script (stages 1-5).

    Returns run_id for tracking. Stops at AWAITING_SCRIPT_APPROVAL.
    """
    # Check concurrency limits
    concurrency = get_concurrency_manager()
    if not concurrency.can_start_run():
        active_runs = concurrency.get_active_run_ids()
        error_msg = f"Max concurrent runs ({concurrency.config.max_active_runs}) reached. Active: {active_runs}"
        if is_htmx_request(request):
            return HTMLResponse(
                f'<div class="alert-error rounded-xl p-4">'
                f'<p class="text-red-300 text-sm">{error_msg}</p>'
                f'</div>',
                status_code=429
            )
        raise HTTPException(status_code=429, detail=error_msg)

    # Create config
    config = RunConfig(
        niche=payload.niche,
        style=payload.style,
        voice_preset=payload.voice_preset,
        visual_mode=payload.visual_mode,
        realism_mode=payload.realism_mode,
        topic=payload.topic,
        loop_friendly_ending=payload.loop_friendly_ending,
        dry_run=True,  # Always stub for now
        generate_shot_list=False,  # Stop before shot list
    )

    # Register run with concurrency manager
    try:
        concurrency.start_run(config.run_id, "starting")
    except RunLimitExceeded as e:
        if is_htmx_request(request):
            return HTMLResponse(
                f'<div class="alert-error rounded-xl p-4">'
                f'<p class="text-red-300 text-sm">{str(e)}</p>'
                f'</div>',
                status_code=429
            )
        raise HTTPException(status_code=429, detail=str(e))

    try:
        # Run pipeline up to script approval
        orchestrator = PipelineOrchestrator()
        success, paths, message, script_data = orchestrator.run_to_script_approval(config)
    finally:
        # Always complete the run in concurrency manager
        concurrency.complete_run(config.run_id)

    # Generate and save display title from hook
    if success and script_data.get("hook"):
        store = RunStore()
        display_title = generate_display_title(script_data["hook"])
        short_title = generate_display_title(script_data["hook"], max_words=4)
        store.update_title(config.run_id, display_title, short_title)

    if is_htmx_request(request):
        # Always redirect to status page - provides visual feedback
        response = HTMLResponse(content="", status_code=200)
        response.headers["HX-Redirect"] = f"/runs/{config.run_id}/status"
        return response

    # JSON response for API calls
    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {
        "run_id": config.run_id,
        "stage": "awaiting_script_approval",
        "script": script_data.get("script", ""),
        "hook": script_data.get("hook", ""),
        "output_path": str(paths.base_dir) if paths else None,
    }


@router.get("/pipeline/status/{run_id}")
async def get_pipeline_status(run_id: str):
    """Get current pipeline status."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    config = record.config
    return RunStatusResponse(
        run_id=record.run_id,
        stage=record.stage.value,
        niche=config.get("niche", "unknown"),
        style=config.get("style", "unknown"),
        display_title=record.display_title,
        output_path=record.output_path,
        error_message=record.error_message,
    )


@router.get("/runs/{run_id}/status-fragment")
async def get_run_status_fragment(request: Request, run_id: str):
    """Get status fragment for HTMX polling."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        return HTMLResponse(
            '<div class="alert-error rounded-xl p-4">'
            '<p class="text-red-300 text-sm">Run not found</p>'
            '</div>'
        )

    # Get last log lines if output exists
    log_lines = []
    if record.output_path:
        from pathlib import Path
        log_path = Path(record.output_path) / "run_log.txt"
        if log_path.exists():
            lines = log_path.read_text().strip().split("\n")
            log_lines = lines[-5:]

    return templates.TemplateResponse(
        "partials/run_status_fragment.html",
        {
            "request": request,
            "run_id": run_id,
            "stage": record.stage.value,
            "stage_display_name": record.stage_display_name,
            "progress_percent": record.computed_progress,
            "is_running": record.stage.is_running(),
            "error_message": record.error_message,
            "output_path": record.output_path,
            "log_lines": log_lines,
        },
    )


@router.post("/pipeline/approve/script/{run_id}")
async def approve_script(request: Request, run_id: str):
    """
    Approve script and continue pipeline.

    Transitions to SCRIPT_APPROVED, then starts background
    continuation to generate shot list and visual prompts.
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        if is_htmx_request(request):
            return templates.TemplateResponse(
                "partials/generation_error.html",
                {"request": request, "error": f"Run not found: {run_id}"},
                status_code=404
            )
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    if record.stage != RunStage.AWAITING_SCRIPT_APPROVAL:
        error_msg = f"Run not awaiting script approval (current: {record.stage.value})"
        if is_htmx_request(request):
            return templates.TemplateResponse(
                "partials/generation_error.html",
                {"request": request, "error": error_msg},
                status_code=400
            )
        raise HTTPException(status_code=400, detail=error_msg)

    # Update stage to approved
    store.update_stage(
        run_id,
        RunStage.SCRIPT_APPROVED,
        current_stage_name="Script Approved",
        progress_percent=10,
    )

    # Log approval to run_log.txt
    if record.output_path:
        from datetime import datetime
        log_path = Path(record.output_path) / "run_log.txt"
        with open(log_path, "a") as f:
            f.write(f"\n[{datetime.now().isoformat()}] [INFO] Script approved by user")
            f.write(f"\n[{datetime.now().isoformat()}] [INFO] Starting post-approval continuation")

    # Start background continuation to generate artifacts
    started = start_continuation_async(run_id)
    if started:
        import logging
        logging.getLogger(__name__).info(f"[{run_id}] Post-approval continuation started")

    # For HTMX: redirect to artifacts page to view/manage generated content
    if is_htmx_request(request):
        from fastapi.responses import Response
        response = Response(content="", status_code=200)
        response.headers["HX-Redirect"] = f"/runs/{run_id}/artifacts"
        return response

    return {
        "run_id": run_id,
        "stage": "script_approved",
        "message": "Script approved. View artifacts at /runs/{run_id}/artifacts",
        "continuation_started": started,
        "artifacts_url": f"/runs/{run_id}/artifacts",
    }


@router.post("/pipeline/regenerate/script/{run_id}")
async def regenerate_script(request: Request, run_id: str):
    """
    Regenerate script with optional feedback.

    Re-runs stages 1-5 with new stub response.
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        if is_htmx_request(request):
            return templates.TemplateResponse(
                "partials/generation_error.html",
                {"request": request, "error": f"Run not found: {run_id}"},
                status_code=404
            )
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    if record.stage != RunStage.AWAITING_SCRIPT_APPROVAL:
        error_msg = f"Run not awaiting script approval (current: {record.stage.value})"
        if is_htmx_request(request):
            return templates.TemplateResponse(
                "partials/generation_error.html",
                {"request": request, "error": error_msg},
                status_code=400
            )
        raise HTTPException(status_code=400, detail=error_msg)

    # Check regeneration limits
    concurrency = get_concurrency_manager()
    if not concurrency.can_regenerate(run_id):
        remaining = concurrency.get_remaining_regenerations(run_id)
        error_msg = f"Max regenerations ({concurrency.config.max_regenerations_per_run}) reached for this run"
        if is_htmx_request(request):
            return templates.TemplateResponse(
                "partials/generation_error.html",
                {"request": request, "error": error_msg},
                status_code=429
            )
        raise HTTPException(status_code=429, detail=error_msg)

    # Increment regeneration count
    try:
        new_count = concurrency.increment_regeneration(run_id)
    except RegenerationLimitExceeded as e:
        if is_htmx_request(request):
            return templates.TemplateResponse(
                "partials/generation_error.html",
                {"request": request, "error": str(e)},
                status_code=429
            )
        raise HTTPException(status_code=429, detail=str(e))

    # Log regeneration request
    if record.output_path:
        from datetime import datetime
        log_path = Path(record.output_path) / "run_log.txt"
        if log_path.exists():
            with open(log_path, "a") as f:
                f.write(f"\n[{datetime.now().isoformat()}] [INFO] Script regeneration requested")

    # Re-run with modified config
    config = RunConfig.from_dict(record.config)
    config.run_id = run_id  # Keep same run_id

    orchestrator = PipelineOrchestrator()
    success, paths, message, script_data = orchestrator.run_to_script_approval(
        config,
        regenerate=True,
    )

    if is_htmx_request(request):
        if success:
            return templates.TemplateResponse(
                "partials/regenerating.html",
                {"request": request}
            )
        else:
            return templates.TemplateResponse(
                "partials/generation_error.html",
                {"request": request, "error": message},
                status_code=500
            )

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {
        "run_id": run_id,
        "stage": "awaiting_script_approval",
        "script": script_data.get("script", ""),
        "hook": script_data.get("hook", ""),
        "regenerated": True,
    }


@router.get("/runs/pending")
async def get_pending_runs():
    """Get runs awaiting approval."""
    store = RunStore()
    pending = store.get_pending_runs()

    return [
        {
            "run_id": r.run_id,
            "stage": r.stage.value,
            "display_title": r.display_title,
            "niche": r.config.get("niche", "unknown"),
            "style": r.config.get("style", "unknown"),
            "created_at": r.created_at,
        }
        for r in pending
    ]


@router.get("/runs/recent")
async def get_recent_runs(limit: int = 10):
    """Get recent runs."""
    store = RunStore()
    runs = store.get_recent_runs(limit=limit)

    return [
        {
            "run_id": r.run_id,
            "stage": r.stage.value,
            "display_title": r.display_title,
            "niche": r.config.get("niche", "unknown"),
            "style": r.config.get("style", "unknown"),
            "output_path": r.output_path,
            "created_at": r.created_at,
        }
        for r in runs
    ]


# === Notes ===

@router.put("/runs/{run_id}/notes")
async def update_notes(request: Request, run_id: str, payload: NotesUpdateRequest):
    """Update notes for a run."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    store.update_notes(run_id, payload.notes)

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            'Notes saved</div>'
        )

    return {"run_id": run_id, "notes": payload.notes, "saved": True}


@router.get("/runs/{run_id}/notes")
async def get_notes(run_id: str):
    """Get notes for a run."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    return {"run_id": run_id, "notes": record.notes or ""}


# === Feedback ===

@router.get("/runs/{run_id}/feedback")
async def get_feedback(run_id: str):
    """Get feedback for a run."""
    store = RunStore()

    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    feedback = store.get_feedback(run_id)
    if not feedback:
        return FeedbackResponse(run_id=run_id)

    return FeedbackResponse(
        run_id=feedback.run_id,
        script_quality=feedback.script_quality,
        hook_strength=feedback.hook_strength,
        visual_match=feedback.visual_match,
        tags=feedback.tags,
        publish_status=feedback.publish_status,
        platform=feedback.platform,
        views=feedback.views,
        avg_watch_time=feedback.avg_watch_time,
        retention_pct=feedback.retention_pct,
        likes=feedback.likes,
        shares=feedback.shares,
        comments=feedback.comments,
        feedback_notes=feedback.feedback_notes,
        created_at=feedback.created_at,
        updated_at=feedback.updated_at,
    )


@router.put("/runs/{run_id}/feedback")
async def update_feedback(request: Request, run_id: str, payload: FeedbackRequest):
    """Save feedback for a run."""
    store = RunStore()

    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    feedback = FeedbackRecord(
        run_id=run_id,
        script_quality=payload.script_quality,
        hook_strength=payload.hook_strength,
        visual_match=payload.visual_match,
        tags=payload.tags,
        publish_status=payload.publish_status,
        platform=payload.platform,
        posted_url=payload.posted_url,
        post_date=payload.post_date,
        views=payload.views,
        avg_watch_time=payload.avg_watch_time,
        retention_pct=payload.retention_pct,
        likes=payload.likes,
        shares=payload.shares,
        comments=payload.comments,
        feedback_notes=payload.feedback_notes,
    )

    store.save_feedback(feedback)

    # Update preset tuning stats
    config = record.config
    if config.get("niche"):
        store.update_tuning_memo("niche", config["niche"])
    if config.get("style"):
        store.update_tuning_memo("style", config["style"])

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            'Feedback saved</div>'
        )

    return {"run_id": run_id, "saved": True}


# === Preset Stats & Tuning ===

@router.get("/presets/{preset_type}/{preset_name}/stats")
async def get_preset_stats(preset_type: str, preset_name: str):
    """Get aggregated stats for a preset."""
    if preset_type not in ("niche", "style"):
        raise HTTPException(status_code=400, detail="preset_type must be 'niche' or 'style'")

    store = RunStore()
    stats = store.get_preset_stats(preset_type, preset_name)

    return PresetStatsResponse(
        preset_type=preset_type,
        preset_name=preset_name,
        total_runs=stats["total_runs"],
        avg_script_quality=stats["avg_script_quality"],
        avg_hook_strength=stats["avg_hook_strength"],
        avg_visual_match=stats["avg_visual_match"],
        common_tags=stats["common_tags"],
    )


@router.get("/presets/{preset_type}/{preset_name}/tuning")
async def get_tuning_memo(preset_type: str, preset_name: str):
    """Get tuning memo for a preset."""
    if preset_type not in ("niche", "style"):
        raise HTTPException(status_code=400, detail="preset_type must be 'niche' or 'style'")

    store = RunStore()
    memo = store.get_tuning_memo(preset_type, preset_name)

    if not memo:
        return TuningMemoResponse(preset_type=preset_type, preset_name=preset_name)

    return TuningMemoResponse(
        preset_type=memo.preset_type,
        preset_name=memo.preset_name,
        memo_text=memo.memo_text,
        avg_script_quality=memo.avg_script_quality,
        avg_hook_strength=memo.avg_hook_strength,
        avg_visual_match=memo.avg_visual_match,
        common_tags=memo.common_tags,
        total_runs=memo.total_runs,
        updated_at=memo.updated_at,
    )


@router.put("/presets/{preset_type}/{preset_name}/tuning")
async def update_tuning_memo(
    request: Request,
    preset_type: str,
    preset_name: str,
    payload: TuningMemoRequest,
):
    """Update tuning memo for a preset."""
    if preset_type not in ("niche", "style"):
        raise HTTPException(status_code=400, detail="preset_type must be 'niche' or 'style'")

    store = RunStore()
    memo = store.update_tuning_memo(preset_type, preset_name, payload.memo_text)

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            'Tuning memo saved</div>'
        )

    return TuningMemoResponse(
        preset_type=memo.preset_type,
        preset_name=memo.preset_name,
        memo_text=memo.memo_text,
        avg_script_quality=memo.avg_script_quality,
        avg_hook_strength=memo.avg_hook_strength,
        avg_visual_match=memo.avg_visual_match,
        common_tags=memo.common_tags,
        total_runs=memo.total_runs,
        updated_at=memo.updated_at,
    )


# === Quick Feedback ===

@router.put("/runs/{run_id}/quick-feedback")
async def update_quick_feedback(request: Request, run_id: str, payload: QuickFeedbackRequest):
    """
    Save quick feedback (rating + notes only).

    Updates only the provided fields, preserving other feedback data.
    """
    store = RunStore()

    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Get existing feedback or create new
    existing = store.get_feedback(run_id)
    if existing:
        # Update only provided fields
        if payload.script_quality is not None:
            existing.script_quality = payload.script_quality
        if payload.feedback_notes is not None:
            existing.feedback_notes = payload.feedback_notes
        store.save_feedback(existing)
    else:
        # Create new feedback with just quick fields
        feedback = FeedbackRecord(
            run_id=run_id,
            script_quality=payload.script_quality,
            feedback_notes=payload.feedback_notes,
        )
        store.save_feedback(feedback)

    return {"run_id": run_id, "saved": True}


# === Mark as Posted ===

@router.post("/runs/{run_id}/mark-posted")
async def mark_as_posted(request: Request, run_id: str):
    """
    Mark content as posted to a platform.

    Required fields: platform, post_date
    Optional: posted_url
    """
    store = RunStore()

    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Parse form data
    form_data = await request.form()
    platform = form_data.get("platform")
    post_date = form_data.get("post_date")
    posted_url = form_data.get("posted_url", "")

    if not platform or not post_date:
        raise HTTPException(status_code=400, detail="Platform and post date are required")

    # Get existing feedback or create new
    existing = store.get_feedback(run_id)
    if existing:
        existing.platform = platform
        existing.post_date = post_date
        existing.posted_url = posted_url if posted_url else existing.posted_url
        existing.publish_status = "published"
        store.save_feedback(existing)
    else:
        feedback = FeedbackRecord(
            run_id=run_id,
            platform=platform,
            post_date=post_date,
            posted_url=posted_url,
            publish_status="published",
        )
        store.save_feedback(feedback)

    return {"run_id": run_id, "marked_posted": True, "platform": platform, "post_date": post_date}


# === Post Run (Workflow Transition) ===

@router.post("/runs/{run_id}/post")
async def post_run(request: Request, run_id: str):
    """
    Mark a run as posted (workflow transition to POSTED stage).

    This is the Queue -> Reviews transition. Sets posted_at timestamp.
    The run must be in READY_TO_POST workflow stage.
    """
    store = RunStore()

    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Verify run is ready to post
    workflow_stage = store.compute_workflow_stage(run_id)
    if workflow_stage.value not in ("ready_to_post", "video_pending"):
        # Allow posting from video_pending or ready_to_post
        if workflow_stage.value in ("posted", "review_ready"):
            raise HTTPException(status_code=400, detail="Run is already posted")
        raise HTTPException(
            status_code=400,
            detail=f"Run must be ready to post (current stage: {workflow_stage.display_name})"
        )

    success = store.post_run(run_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to mark run as posted")

    if is_htmx_request(request):
        from fastapi.responses import Response
        response = Response(content="", status_code=200)
        response.headers["HX-Redirect"] = "/reviews"
        return response

    return {"run_id": run_id, "posted": True, "message": "Run marked as posted"}


# === Preset Editor ===

@router.get("/presets/{category}/{name}/content")
async def get_preset_content(category: str, name: str):
    """Get raw JSON content of a preset for editing."""
    loader = PresetLoader()
    preset = loader.get_preset(category, name)

    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {category}/{name}")

    import json
    return {
        "category": category,
        "name": name,
        "content": json.dumps(preset.data, indent=2),
        "path": str(preset.path),
    }


@router.put("/presets/{category}/{name}/content")
async def update_preset_content(
    request: Request,
    category: str,
    name: str,
    payload: PresetEditRequest,
):
    """
    Update preset JSON content.

    Validates JSON, creates backup, saves, and invalidates cache.
    """
    import json
    import shutil
    from datetime import datetime

    loader = PresetLoader()
    preset = loader.get_preset(category, name)

    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {category}/{name}")

    # Validate JSON
    try:
        new_data = json.loads(payload.content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    # Validate required keys based on category
    required_keys = _get_required_keys_for_category(category)
    missing_keys = [k for k in required_keys if k not in new_data]
    if missing_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required keys: {', '.join(missing_keys)}"
        )

    # Create backup directory
    history_dir = preset.path.parent.parent / "_history"
    history_dir.mkdir(parents=True, exist_ok=True)

    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{timestamp}_{name}.json"
    backup_path = history_dir / backup_name

    # Copy current file to backup
    shutil.copy2(preset.path, backup_path)

    # Write new content
    with open(preset.path, "w") as f:
        json.dump(new_data, f, indent=2)

    # Clear cache so changes take effect
    loader.clear_cache()

    # Compute new fingerprint
    new_fingerprint = loader.compute_fingerprint({category.rstrip("s"): name})

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            f'Preset saved. Backup: {backup_name}</div>'
        )

    return PresetEditResponse(
        success=True,
        message=f"Preset saved. Backup created at {backup_path}",
        backup_path=str(backup_path),
        new_fingerprint=new_fingerprint,
    )


def _get_required_keys_for_category(category: str) -> list[str]:
    """Get required keys for a preset category."""
    required = {
        "niches": ["display_name"],
        "styles": ["display_name"],
        "voices": ["display_name"],
        "visuals": ["display_name"],
        "realism": ["display_name"],
    }
    return required.get(category, ["display_name"])


@router.get("/presets/{category}/{name}/history")
async def get_preset_history(category: str, name: str):
    """Get backup history for a preset."""
    loader = PresetLoader()
    history_dir = loader.presets_dir / "_history"

    if not history_dir.exists():
        return {"backups": []}

    # Find backups matching this preset name
    backups = []
    for f in history_dir.glob(f"*_{name}.json"):
        # Extract timestamp from filename
        parts = f.stem.split("_")
        if len(parts) >= 3:
            timestamp = f"{parts[0]}_{parts[1]}"
            backups.append({
                "filename": f.name,
                "timestamp": timestamp,
                "path": str(f),
            })

    # Sort by timestamp descending
    backups.sort(key=lambda x: x["timestamp"], reverse=True)

    return {"backups": backups[:20]}  # Limit to 20 most recent


@router.post("/presets/{category}/{name}/restore/{backup_filename}")
async def restore_preset_backup(
    request: Request,
    category: str,
    name: str,
    backup_filename: str,
):
    """Restore a preset from a backup file."""
    import shutil
    from datetime import datetime

    loader = PresetLoader()
    preset = loader.get_preset(category, name)

    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {category}/{name}")

    history_dir = loader.presets_dir / "_history"
    backup_path = history_dir / backup_filename

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"Backup not found: {backup_filename}")

    # Create backup of current before restoring
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre_restore_backup = history_dir / f"{timestamp}_pre_restore_{name}.json"
    shutil.copy2(preset.path, pre_restore_backup)

    # Restore from backup
    shutil.copy2(backup_path, preset.path)

    # Clear cache
    loader.clear_cache()

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            f'Preset restored from {backup_filename}</div>'
        )

    return {"success": True, "message": f"Restored from {backup_filename}"}


# === Concurrency Status ===

@router.get("/concurrency/status")
async def get_concurrency_status():
    """Get current concurrency status."""
    concurrency = get_concurrency_manager()
    status = concurrency.get_status()

    return {
        "active_runs": status["active_runs"],
        "max_runs": status["max_runs"],
        "available_slots": status["available_slots"],
        "active_run_ids": status["active_run_ids"],
        "can_start_new": concurrency.can_start_run(),
    }


@router.get("/runs/{run_id}/regeneration-status")
async def get_regeneration_status(run_id: str):
    """Get regeneration status for a run."""
    concurrency = get_concurrency_manager()

    count = concurrency.get_regeneration_count(run_id)
    remaining = concurrency.get_remaining_regenerations(run_id)
    max_allowed = concurrency.config.max_regenerations_per_run

    return {
        "run_id": run_id,
        "regeneration_count": count,
        "remaining": remaining,
        "max_allowed": max_allowed,
        "can_regenerate": remaining > 0,
    }


# === Provider Info ===

@router.get("/provider/info")
async def get_provider_info():
    """Get current provider configuration."""
    orchestrator = PipelineOrchestrator()
    return orchestrator.get_provider_info()


# === Screenshot Import ===

from fastapi import UploadFile, File, Form as FormField
from datetime import datetime
import uuid
import os


@router.post("/reviews/import-screenshot")
async def import_screenshot(
    request: Request,
    platform: str = FormField(...),
    screenshot: UploadFile = File(...),
    run_id: str = FormField(None),
    post_url: str = FormField(None),
):
    """
    Import analytics from a screenshot.

    Accepts image upload, runs OCR, extracts metrics,
    and creates a draft for user confirmation.
    """
    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/webp"}
    if screenshot.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {screenshot.content_type}. Allowed: {allowed_types}"
        )

    # Validate file size (10MB max)
    max_size = 10 * 1024 * 1024
    content = await screenshot.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {max_size // (1024*1024)}MB"
        )

    # Generate safe filename
    ext = Path(screenshot.filename).suffix.lower() if screenshot.filename else ".png"
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".png"

    safe_filename = f"import-{uuid.uuid4().hex[:8]}{ext}"

    # Determine storage path
    from content_engine.services.drive_guard import DriveGuard
    guard = DriveGuard()
    drive_result = guard.check()

    if drive_result.can_write and drive_result.mount_path:
        # Store in gdrive under imports folder
        today = datetime.now().strftime("%Y-%m-%d")
        imports_dir = drive_result.mount_path / "content_engine" / "imports" / today
    else:
        # Fallback to local data folder
        imports_dir = Path(__file__).parent.parent.parent / "data" / "imports"

    imports_dir.mkdir(parents=True, exist_ok=True)
    image_path = imports_dir / safe_filename

    # Save file
    with open(image_path, "wb") as f:
        f.write(content)

    # Run OCR and extract metrics
    try:
        from content_engine.services.ocr_importer import OCRImporter, Platform

        importer = OCRImporter()
        platform_enum = Platform(platform.lower())
        metrics = importer.extract_metrics(image_path, platform_enum)
        extracted_data = metrics.to_dict()

    except ImportError as e:
        # OCR not available - save draft with empty extraction
        extracted_data = {
            "extracted_text": "",
            "platform": platform,
            "parse_errors": [f"OCR not available: {e}"],
            "confidence": {},
        }
    except Exception as e:
        extracted_data = {
            "extracted_text": "",
            "platform": platform,
            "parse_errors": [str(e)],
            "confidence": {},
        }

    # Create draft in database
    store = RunStore()
    draft_id = store.create_import_draft(
        platform=platform,
        image_path=str(image_path),
        extracted_json=extracted_data,
        run_id=run_id if run_id else None,
        post_url=post_url if post_url else None,
    )

    if is_htmx_request(request):
        # Redirect to draft review page
        from fastapi.responses import Response
        response = Response(content="", status_code=200)
        response.headers["HX-Redirect"] = f"/reviews/import/{draft_id}"
        return response

    return {
        "draft_id": draft_id,
        "extracted": extracted_data,
        "image_path": str(image_path),
    }


@router.get("/reviews/drafts/{draft_id}")
async def get_import_draft(draft_id: int):
    """Get an import draft by ID."""
    store = RunStore()
    draft = store.get_import_draft(draft_id)

    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft not found: {draft_id}")

    return draft


@router.post("/reviews/drafts/{draft_id}/confirm")
async def confirm_import_draft(
    request: Request,
    draft_id: int,
    run_id: str = FormField(...),
    views: int = FormField(None),
    avg_watch_time_seconds: float = FormField(None),
    retention_percent: float = FormField(None),
    likes: int = FormField(None),
    comments: int = FormField(None),
    shares: int = FormField(None),
    posted_url: str = FormField(None),
    post_date: str = FormField(None),
    feedback_notes: str = FormField(None),
):
    """
    Confirm an import draft and save as feedback.

    User must verify/edit extracted values before saving.
    """
    store = RunStore()

    # Verify draft exists
    draft = store.get_import_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft not found: {draft_id}")

    if draft["status"] != "pending":
        raise HTTPException(status_code=400, detail="Draft already confirmed or deleted")

    # Verify run exists
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Confirm with user-provided values
    confirmed_values = {
        "views": views,
        "avg_watch_time_seconds": avg_watch_time_seconds,
        "retention_percent": retention_percent,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "posted_url": posted_url,
        "post_date": post_date,
        "feedback_notes": feedback_notes,
    }

    success = store.confirm_import_draft(draft_id, run_id, confirmed_values)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to confirm draft")

    if is_htmx_request(request):
        return HTMLResponse(
            f'<div class="alert-success rounded-lg p-4">'
            f'<p class="text-green-300">Review saved successfully!</p>'
            f'<a href="/runs/{run_id}" class="text-blue-400 hover:underline mt-2 block">'
            f'View Run &rarr;</a></div>'
        )

    return {"success": True, "run_id": run_id}


@router.delete("/reviews/drafts/{draft_id}")
async def delete_import_draft(draft_id: int):
    """Delete an import draft."""
    store = RunStore()

    success = store.delete_import_draft(draft_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Draft not found: {draft_id}")

    return {"success": True}


@router.get("/reviews/drafts")
async def list_pending_drafts(limit: int = 20):
    """List pending import drafts."""
    store = RunStore()
    drafts = store.get_pending_drafts(limit=limit)
    return {"drafts": drafts}


@router.get("/reviews/drafts/{draft_id}/image")
async def get_draft_image(draft_id: int):
    """Serve the image associated with a draft."""
    store = RunStore()
    draft = store.get_import_draft(draft_id)

    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft not found: {draft_id}")

    image_path = Path(draft.get("image_path", ""))
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    # Determine content type from extension
    ext = image_path.suffix.lower()
    content_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    content_type = content_types.get(ext, "image/png")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(image_path),
        media_type=content_type,
        filename=image_path.name,
    )


# === Prompt Versioning ===

@router.get("/runs/{run_id}/prompts")
async def get_run_prompts(run_id: str, artifact_type: str = None):
    """Get all active prompts for a run."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    type_filter = None
    if artifact_type:
        try:
            type_filter = ArtifactType(artifact_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid artifact_type: {artifact_type}")

    prompts = store.get_all_active_prompts(run_id, type_filter)

    return [
        PromptVersionResponse(
            id=p.id,
            run_id=p.run_id,
            artifact_type=p.artifact_type.value,
            item_key=p.item_key,
            version=p.version,
            prompt_text=p.prompt_text,
            notes=p.notes,
            image_path=p.image_path,
            created_at=p.created_at,
            created_by=p.created_by,
            status=p.status.value,
        )
        for p in prompts
    ]


@router.get("/runs/{run_id}/prompts/stats")
async def get_prompt_stats(run_id: str):
    """Get prompt statistics for a run."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    stats = store.get_prompt_stats(run_id)
    return PromptStatsResponse(**stats)


@router.get("/runs/{run_id}/prompts/history")
async def get_prompt_history(run_id: str, artifact_type: str = None, item_key: str = None):
    """Get prompt version history for a run."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    type_filter = None
    if artifact_type:
        try:
            type_filter = ArtifactType(artifact_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid artifact_type: {artifact_type}")

    history = store.get_prompt_history(run_id, type_filter, item_key)

    return [
        PromptVersionResponse(
            id=p.id,
            run_id=p.run_id,
            artifact_type=p.artifact_type.value,
            item_key=p.item_key,
            version=p.version,
            prompt_text=p.prompt_text,
            notes=p.notes,
            image_path=p.image_path,
            created_at=p.created_at,
            created_by=p.created_by,
            status=p.status.value,
        )
        for p in history
    ]


@router.post("/runs/{run_id}/regenerate-prompt")
async def regenerate_prompt(request: Request, run_id: str, payload: RegeneratePromptRequest):
    """
    Regenerate a prompt for a specific artifact.

    Creates a new version, marks old as superseded, logs learning.
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        if is_htmx_request(request):
            return HTMLResponse(
                '<div class="alert-error rounded-xl p-4">'
                '<p class="text-red-300 text-sm">Run not found</p>'
                '</div>',
                status_code=404
            )
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Validate artifact type
    try:
        artifact_type = ArtifactType(payload.artifact_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid artifact_type: {payload.artifact_type}")

    # Get the old prompt if regenerating existing
    old_prompt = None
    if payload.prompt_id:
        old_prompt = store.get_prompt_version(payload.prompt_id)

    # Generate new prompt using CLI provider
    try:
        orchestrator = PipelineOrchestrator()

        # Build regeneration prompt based on artifact type
        if artifact_type == ArtifactType.NANOBANANA:
            # Get context from shot list
            shot_context = _get_shot_context(record.output_path, payload.item_key)
            new_prompt_text = orchestrator.regenerate_nanobanana_prompt(
                run_id=run_id,
                item_key=payload.item_key,
                shot_context=shot_context,
                feedback=payload.notes,
            )
        elif artifact_type == ArtifactType.STOCK_QUERY:
            shot_context = _get_shot_context(record.output_path, payload.item_key)
            new_prompt_text = orchestrator.regenerate_stock_query(
                run_id=run_id,
                item_key=payload.item_key,
                shot_context=shot_context,
                feedback=payload.notes,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Regeneration not supported for: {artifact_type.value}")

    except NotImplementedError:
        # Fallback: just duplicate with placeholder if orchestrator doesn't support it yet
        new_prompt_text = f"[REGENERATED] {old_prompt.prompt_text if old_prompt else 'New prompt'}"
    except Exception as e:
        if is_htmx_request(request):
            return HTMLResponse(
                f'<div class="alert-error rounded-xl p-4">'
                f'<p class="text-red-300 text-sm">Regeneration failed: {str(e)}</p>'
                f'</div>',
                status_code=500
            )
        raise HTTPException(status_code=500, detail=str(e))

    # Create new version
    new_version = store.create_prompt_version(
        run_id=run_id,
        artifact_type=artifact_type,
        item_key=payload.item_key,
        prompt_text=new_prompt_text,
        notes=payload.notes,
        created_by="user",
    )

    # Log learning
    learning_logged = _log_prompt_learning(
        run_id=run_id,
        artifact_type=artifact_type.value,
        item_key=payload.item_key,
        old_version=old_prompt.version if old_prompt else 0,
        new_version=new_version.version,
        feedback=payload.notes,
    )

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-xl p-4">'
            f'<p class="text-green-300 text-sm">Prompt regenerated (v{new_version.version})</p>'
            '</div>'
        )

    return RegeneratePromptResponse(
        success=True,
        prompt_id=new_version.id,
        version=new_version.version,
        message=f"Prompt regenerated successfully (v{new_version.version})",
        learning_logged=learning_logged,
    )


@router.get("/runs/{run_id}/prompt-regeneration-status")
async def get_prompt_regeneration_status(run_id: str):
    """Get regeneration status for prompts in a run."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    stats = store.get_prompt_stats(run_id)

    return {
        "run_id": run_id,
        "total_versions": stats["total_versions"],
        "active_prompts": stats["active_prompts"],
        "regenerations": stats["total_versions"] - stats["active_prompts"],
        "by_type": stats["by_type"],
    }


def _get_shot_context(output_path: str, item_key: str) -> dict:
    """Get shot context for regeneration."""
    if not output_path:
        return {}

    import json
    shot_list_path = Path(output_path) / "shot_list.json"
    if not shot_list_path.exists():
        return {}

    try:
        shots = json.loads(shot_list_path.read_text())
        # Find matching scene
        scene_num = int(item_key.replace("scene_", "")) if item_key.startswith("scene_") else None
        if scene_num is not None:
            for shot in shots:
                if shot.get("scene_number") == scene_num:
                    return shot
    except Exception:
        pass

    return {}


def _log_prompt_learning(
    run_id: str,
    artifact_type: str,
    item_key: str,
    old_version: int,
    new_version: int,
    feedback: str | None,
) -> bool:
    """Log prompt regeneration to knowledge base for learning."""
    try:
        # Create knowledge directory if needed
        knowledge_dir = Path(__file__).parent.parent.parent / "knowledge_base" / "internal"
        knowledge_dir.mkdir(parents=True, exist_ok=True)

        learnings_path = knowledge_dir / "prompt_learnings.md"

        from datetime import datetime

        # Append learning entry
        entry = f"""
## {datetime.now().isoformat()} - {artifact_type}/{item_key}

- **Run ID**: {run_id}
- **Artifact**: {artifact_type}
- **Item**: {item_key}
- **Versions**: v{old_version} -> v{new_version}
- **Feedback**: {feedback or "(no feedback provided)"}

---
"""
        with open(learnings_path, "a") as f:
            f.write(entry)

        return True
    except Exception:
        return False


# === Prompt Backfill (for older runs) ===

@router.post("/runs/{run_id}/sync-prompts")
async def sync_prompts_from_files(request: Request, run_id: str):
    """
    Sync/backfill prompts from generated files for older runs.

    Parses shot_list.json and creates prompt_versions if they don't exist.
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    if not record.output_path:
        raise HTTPException(status_code=400, detail="Run has no output path")

    output_dir = Path(record.output_path)
    shot_list_path = output_dir / "shot_list.json"

    if not shot_list_path.exists():
        raise HTTPException(status_code=404, detail="No shot_list.json found")

    import json
    shots = json.loads(shot_list_path.read_text())

    # Check if prompts already exist
    existing = store.get_all_active_prompts(run_id, ArtifactType.NANOBANANA)
    if existing:
        return {"synced": 0, "message": "Prompts already exist", "existing": len(existing)}

    # Get visual mode from config
    config = record.config
    visual_mode = config.get("visual_mode", "hybrid")

    synced_nano = 0
    synced_stock = 0

    for scene in shots:
        scene_num = scene.get("scene_number", 0)
        beat_type = scene.get("beat_type", "UNKNOWN")
        item_key = f"scene_{scene_num}_{beat_type}"

        # Sync NanoBanana prompt
        nano_prompt = scene.get("nano_prompt", "")
        if nano_prompt and visual_mode in ["nanobanana", "hybrid", "both", "nanobanana_cinematic"]:
            store.create_prompt_version(
                run_id=run_id,
                artifact_type=ArtifactType.NANOBANANA,
                item_key=item_key,
                prompt_text=nano_prompt,
                notes=f"Beat: {beat_type}, Duration: {scene.get('duration', 0)}s (synced from file)",
                created_by="system",
            )
            synced_nano += 1

        # Sync stock queries
        search_tight = scene.get("search_tight", "")
        search_broad = scene.get("search_broad", "")
        negative = scene.get("negative_search", [])

        if (search_tight or search_broad) and visual_mode in ["stock", "hybrid", "both", "stock_only"]:
            query_text = f"Tight: {search_tight}\nBroad: {search_broad}\nExclude: {', '.join(negative)}"
            store.create_prompt_version(
                run_id=run_id,
                artifact_type=ArtifactType.STOCK_QUERY,
                item_key=item_key,
                prompt_text=query_text,
                notes=f"Beat: {beat_type} (synced from file)",
                created_by="system",
            )
            synced_stock += 1

    return {
        "synced": synced_nano + synced_stock,
        "nanobanana": synced_nano,
        "stock_queries": synced_stock,
        "message": f"Synced {synced_nano} NanoBanana prompts and {synced_stock} stock queries",
    }


@router.post("/runs/{run_id}/regenerate-prompt-with-image")
async def regenerate_prompt_with_image(
    request: Request,
    run_id: str,
    artifact_type: str = Form(...),
    item_key: str = Form(...),
    notes: str = Form(None),
    image: UploadFile = File(None),
):
    """
    Regenerate a prompt with optional reference image upload.

    The image is stored and can be used to guide the regeneration.
    """
    from fastapi import UploadFile, File, Form

    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Validate artifact type
    try:
        art_type = ArtifactType(artifact_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid artifact_type: {artifact_type}")

    # Handle image upload if provided
    image_path = None
    if image and image.filename:
        # Create images directory
        images_dir = Path(record.output_path) / "reference_images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # Save image
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = Path(image.filename).suffix or ".png"
        image_filename = f"{item_key}_{timestamp}{ext}"
        image_path = images_dir / image_filename

        content = await image.read()
        image_path.write_bytes(content)
        image_path = str(image_path)

    # Get old prompt
    old_prompt = store.get_active_prompt(run_id, art_type, item_key)

    # Generate new prompt
    try:
        orchestrator = PipelineOrchestrator()
        shot_context = _get_shot_context(record.output_path, item_key)

        # Add image reference to feedback if image was uploaded
        feedback = notes or ""
        if image_path:
            feedback += f"\n[Reference image uploaded: {Path(image_path).name}]"

        if art_type == ArtifactType.NANOBANANA:
            new_prompt_text = orchestrator.regenerate_nanobanana_prompt(
                run_id=run_id,
                item_key=item_key,
                shot_context=shot_context,
                feedback=feedback,
            )
        elif art_type == ArtifactType.STOCK_QUERY:
            new_prompt_text = orchestrator.regenerate_stock_query(
                run_id=run_id,
                item_key=item_key,
                shot_context=shot_context,
                feedback=feedback,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Regeneration not supported for: {art_type.value}")

    except NotImplementedError:
        new_prompt_text = f"[REGENERATED] {old_prompt.prompt_text if old_prompt else 'New prompt'}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Create new version with image path
    new_version = store.create_prompt_version(
        run_id=run_id,
        artifact_type=art_type,
        item_key=item_key,
        prompt_text=new_prompt_text,
        notes=notes,
        image_path=image_path,
        created_by="user",
    )

    # Log learning
    _log_prompt_learning(
        run_id=run_id,
        artifact_type=art_type.value,
        item_key=item_key,
        old_version=old_prompt.version if old_prompt else 0,
        new_version=new_version.version,
        feedback=f"{notes or ''}\nImage: {image_path or 'none'}",
    )

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-xl p-4">'
            f'<p class="text-green-300 text-sm">Prompt regenerated (v{new_version.version})'
            f'{" with image" if image_path else ""}</p>'
            '</div>'
        )

    return {
        "success": True,
        "prompt_id": new_version.id,
        "version": new_version.version,
        "image_path": image_path,
        "message": f"Prompt regenerated successfully (v{new_version.version})",
    }


# === Knowledge Base ===

@router.get("/knowledge/status")
async def get_knowledge_status():
    """Get knowledge base status."""
    try:
        orchestrator = PipelineOrchestrator()
        return orchestrator.get_knowledge_base_status()
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/knowledge/documents")
async def list_knowledge_documents():
    """List all knowledge base documents."""
    try:
        from content_engine.knowledge import get_registry

        registry = get_registry()
        external = registry.get_external_documents()
        internal = registry.get_internal_documents()

        return {
            "external": [
                {
                    "id": d.id,
                    "title": d.title,
                    "type": d.type,
                    "path": d.path,
                    "description": d.description,
                    "tags": d.tags,
                    "priority": d.priority,
                    "added_at": d.added_at,
                    "exists": d.exists(),
                }
                for d in external
            ],
            "internal": [
                {
                    "id": d.id,
                    "title": d.title,
                    "type": d.type,
                    "path": d.path,
                }
                for d in internal
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/documents/{doc_id}")
async def get_knowledge_document(doc_id: str):
    """Get a specific knowledge document."""
    try:
        from content_engine.knowledge import get_registry

        registry = get_registry()
        doc = registry.get_document(doc_id)

        return {
            "id": doc.id,
            "title": doc.title,
            "type": doc.type,
            "scope": doc.scope,
            "path": doc.path,
            "description": doc.description,
            "tags": doc.tags,
            "priority": doc.priority,
            "sections": doc.sections,
            "content": doc.read_content() if doc.exists() else None,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/learning")
async def get_learning_summary():
    """Get internal learning summary."""
    try:
        from content_engine.knowledge import get_registry

        registry = get_registry()
        summary = registry.read_learning_summary()
        patterns = registry.read_patterns()
        overrides = registry.read_rule_overrides()

        return {
            "summary": summary,
            "patterns": patterns,
            "rule_overrides": overrides,
            "config": {
                "sample_size_threshold": registry.config.sample_size_threshold,
                "auto_learn_enabled": registry.config.auto_learn_enabled,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/conflicts")
async def get_knowledge_conflicts():
    """Get conflicts between internal and external knowledge."""
    try:
        from content_engine.knowledge import compare_internal_external

        result = compare_internal_external()
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge/compare")
async def run_knowledge_comparison():
    """Run comparison and update conflicts report."""
    try:
        from content_engine.knowledge.compare import KnowledgeComparator

        comparator = KnowledgeComparator()
        result = comparator.compare()
        conflicts_path = comparator.save_conflicts_report(result)

        return {
            "success": True,
            "conflicts_path": str(conflicts_path),
            "summary": result.to_dict()["summary"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Prompt Version Navigation ===

@router.get("/runs/{run_id}/prompts/{artifact_type}/{item_key}/version/{version}")
async def get_prompt_version(
    run_id: str,
    artifact_type: str,
    item_key: str,
    version: int,
):
    """Get a specific version of a prompt."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    try:
        art_type = ArtifactType(artifact_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid artifact_type: {artifact_type}")

    prompt = store.get_prompt_by_version(run_id, art_type, item_key, version)

    if not prompt:
        raise HTTPException(
            status_code=404,
            detail=f"Prompt version not found: {artifact_type}/{item_key} v{version}"
        )

    # Get version info for navigation
    version_info = store.get_prompt_version_info(run_id, art_type, item_key)

    return {
        "id": prompt.id,
        "run_id": prompt.run_id,
        "artifact_type": prompt.artifact_type.value,
        "item_key": prompt.item_key,
        "version": prompt.version,
        "prompt_text": prompt.prompt_text,
        "notes": prompt.notes,
        "image_path": prompt.image_path,
        "created_at": prompt.created_at,
        "created_by": prompt.created_by,
        "status": prompt.status.value,
        "has_prev": version > 1,
        "has_next": version < version_info.get("max_version", version),
        "max_version": version_info.get("max_version", version),
        "total_versions": version_info.get("total_versions", 1),
    }


@router.post("/runs/{run_id}/prompts/{prompt_id}/activate")
async def activate_prompt_version(request: Request, run_id: str, prompt_id: int):
    """
    Make a specific prompt version active.

    Marks the specified version as ACTIVE and all others for that item as SUPERSEDED.
    Also marks downstream scenes as OUTDATED for continuity.
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Get the prompt to activate
    prompt = store.get_prompt_version(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    if prompt.run_id != run_id:
        raise HTTPException(status_code=400, detail="Prompt does not belong to this run")

    # Activate this version (this will supersede others)
    success = store.activate_prompt_version(prompt_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to activate prompt version")

    # CONTINUITY: Mark downstream scenes as OUTDATED
    outdated_count = store.mark_downstream_outdated(run_id, prompt.artifact_type, prompt.item_key)

    warning_msg = ""
    if outdated_count > 0:
        warning_msg = f" ⚠ {outdated_count} downstream scene(s) need regeneration."

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-xl p-3">'
            f'<p class="text-green-300 text-sm">Version {prompt.version} is now active.{warning_msg}</p>'
            '</div>'
        )

    return {
        "success": True,
        "prompt_id": prompt_id,
        "version": prompt.version,
        "item_key": prompt.item_key,
        "message": f"Version {prompt.version} is now active",
        "outdated_downstream": outdated_count,
    }


@router.get("/runs/{run_id}/prompts/{artifact_type}/{item_key}/versions")
async def list_prompt_versions(run_id: str, artifact_type: str, item_key: str):
    """List all versions of a specific prompt."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    try:
        art_type = ArtifactType(artifact_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid artifact_type: {artifact_type}")

    versions = store.get_all_versions_for_item(run_id, art_type, item_key)

    return [
        {
            "id": v.id,
            "version": v.version,
            "status": v.status.value,
            "created_at": v.created_at,
            "created_by": v.created_by,
            "notes": v.notes,
            "has_image": bool(v.image_path),
        }
        for v in versions
    ]


# === Sequential Generation & Continuity ===

@router.post("/runs/{run_id}/prompts/{prompt_id}/lock")
async def lock_prompt(request: Request, run_id: str, prompt_id: int):
    """
    Lock a prompt version, confirming it for continuity.

    When a prompt is locked:
    1. Its status changes to LOCKED
    2. The next scene (if any) becomes ready to generate
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    prompt = store.get_prompt_version(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    if prompt.run_id != run_id:
        raise HTTPException(status_code=400, detail="Prompt does not belong to this run")

    if prompt.status != PromptStatus.ACTIVE:
        raise HTTPException(status_code=400, detail=f"Can only lock ACTIVE prompts (current: {prompt.status.value})")

    success = store.lock_prompt(prompt_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to lock prompt")

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-xl p-3">'
            f'<p class="text-green-300 text-sm">Scene locked! Next scene is now ready to generate.</p>'
            '</div>'
        )

    return {
        "success": True,
        "prompt_id": prompt_id,
        "item_key": prompt.item_key,
        "message": "Prompt locked successfully",
    }


@router.post("/runs/{run_id}/prompts/{prompt_id}/unlock")
async def unlock_prompt(request: Request, run_id: str, prompt_id: int):
    """Unlock a locked prompt, returning it to ACTIVE status."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    prompt = store.get_prompt_version(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    if prompt.status != PromptStatus.LOCKED:
        raise HTTPException(status_code=400, detail=f"Can only unlock LOCKED prompts (current: {prompt.status.value})")

    success = store.unlock_prompt(prompt_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to unlock prompt")

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-xl p-3">'
            '<p class="text-green-300 text-sm">Prompt unlocked</p>'
            '</div>'
        )

    return {"success": True, "prompt_id": prompt_id}


@router.post("/runs/{run_id}/prompts/generate-next/{item_key}")
async def generate_next_scene(request: Request, run_id: str, item_key: str):
    """
    Generate the prompt for a scene, using context from the previous locked scene.

    Prerequisites:
    - The previous scene must be LOCKED
    - This scene must be PENDING or OUTDATED
    """
    import json
    from content_engine.pipeline.orchestrator import PipelineOrchestrator

    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Get the pending prompt for this scene
    prompt = store.get_active_prompt(run_id, ArtifactType.NANOBANANA, item_key)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"No prompt found for {item_key}")

    if prompt.status not in (PromptStatus.PENDING, PromptStatus.OUTDATED):
        raise HTTPException(
            status_code=400,
            detail=f"Scene must be PENDING or OUTDATED to generate (current: {prompt.status.value})"
        )

    # Check if previous scene is locked
    scene_num = prompt.scene_number
    if scene_num and scene_num > 1:
        prev_scene_key = f"scene_{scene_num - 1}"
        prev_prompt = store.get_locked_prompt_for_scene(run_id, ArtifactType.NANOBANANA, prev_scene_key)
        if not prev_prompt:
            raise HTTPException(
                status_code=400,
                detail=f"Previous scene ({prev_scene_key}) must be locked before generating this scene"
            )

    # Load shot list to get scene data
    if not record.output_path:
        raise HTTPException(status_code=400, detail="Run has no output path")

    shot_list_path = Path(record.output_path) / "shot_list.json"
    if not shot_list_path.exists():
        raise HTTPException(status_code=400, detail="Shot list not found")

    shot_list = json.loads(shot_list_path.read_text())

    # Find this scene in the shot list
    scene_data = None
    for scene in shot_list:
        if f"scene_{scene['scene_number']}" == item_key:
            scene_data = scene
            break

    if not scene_data:
        raise HTTPException(status_code=404, detail=f"Scene {item_key} not found in shot list")

    # Build context from previous scene(s)
    context_parts = []
    if scene_num and scene_num > 1:
        prev_prompt = store.get_locked_prompt_for_scene(run_id, ArtifactType.NANOBANANA, f"scene_{scene_num - 1}")
        if prev_prompt:
            context_parts.append(f"PREVIOUS SCENE ({scene_num - 1}) - LOCKED:\n{prev_prompt.prompt_text}")

    # Generate the new prompt using orchestrator
    # For now, use the stub prompt with context prepended
    nano_prompt = scene_data.get("nano_prompt", "")

    if context_parts:
        # Prepend continuity context
        continuity_context = "\n\n".join(context_parts)
        nano_prompt = f"[CONTINUITY CONTEXT]\n{continuity_context}\n\n[SCENE {scene_num}]\n{nano_prompt}"

    # Update the pending prompt to ACTIVE with the generated content
    new_prompt = store.create_prompt_version(
        run_id=run_id,
        artifact_type=ArtifactType.NANOBANANA,
        item_key=item_key,
        prompt_text=nano_prompt,
        notes=f"Beat: {scene_data.get('beat_type', 'UNKNOWN')}, Duration: {scene_data.get('duration', 0)}s | Generated with continuity from scene {scene_num - 1}",
        created_by="system",
        status=PromptStatus.ACTIVE,
        depends_on_scene=f"scene_{scene_num - 1}" if scene_num and scene_num > 1 else None,
        depends_on_version_id=prev_prompt.id if scene_num and scene_num > 1 and prev_prompt else None,
    )

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-xl p-3">'
            f'<p class="text-green-300 text-sm">Scene {scene_num} prompt generated with continuity!</p>'
            '</div>'
        )

    return {
        "success": True,
        "prompt_id": new_prompt.id,
        "item_key": item_key,
        "scene_number": scene_num,
        "message": f"Generated prompt for scene {scene_num}",
    }


@router.get("/runs/{run_id}/prompts/scene-status")
async def get_scene_status(run_id: str, artifact_type: str = "nanobanana"):
    """
    Get the generation status for all scenes in a run.

    Returns info for each scene including:
    - status (PENDING, ACTIVE, LOCKED, OUTDATED)
    - can_generate (if previous scene is locked)
    - can_lock (if scene is ACTIVE)
    - continuity_warning (if upstream changed)
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    try:
        art_type = ArtifactType(artifact_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid artifact_type: {artifact_type}")

    status = store.get_scene_generation_status(run_id, art_type)

    return {"scenes": status, "total": len(status)}


@router.post("/runs/{run_id}/prompts/regenerate-downstream/{item_key}")
async def regenerate_downstream_scenes(request: Request, run_id: str, item_key: str):
    """
    Mark all scenes after the specified scene as OUTDATED.

    This is called when a scene is changed (regenerated or a different version made active).
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    outdated_count = store.mark_downstream_outdated(run_id, ArtifactType.NANOBANANA, item_key)

    if is_htmx_request(request):
        if outdated_count > 0:
            return HTMLResponse(
                f'<div class="alert-warning rounded-xl p-3">'
                f'<p class="text-yellow-300 text-sm">⚠ {outdated_count} downstream scene(s) marked for regeneration</p>'
                '</div>'
            )
        return HTMLResponse(
            '<div class="alert-success rounded-xl p-3">'
            '<p class="text-green-300 text-sm">No downstream scenes affected</p>'
            '</div>'
        )

    return {
        "success": True,
        "item_key": item_key,
        "outdated_count": outdated_count,
        "message": f"Marked {outdated_count} downstream scene(s) as outdated",
    }


# === Entities (Continuity Memory) ===

@router.get("/runs/{run_id}/entities")
async def list_entities(request: Request, run_id: str, entity_type: str = None, active_only: bool = True):
    """
    Get all entities for a run.
    Returns HTML fragment for HTMX requests, JSON otherwise.
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    type_filter = None
    if entity_type:
        try:
            type_filter = EntityType(entity_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entity_type: {entity_type}")

    entities = store.get_entities_for_run(run_id, type_filter, active_only)

    # Check if this is an HTMX request - return HTML fragment
    if request.headers.get("HX-Request"):
        if not entities:
            return HTMLResponse("""
                <div class="text-center py-8">
                    <svg class="w-12 h-12 text-gray-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
                    </svg>
                    <p class="text-gray-500 text-sm">No entities yet</p>
                    <p class="text-gray-600 text-xs mt-1">Click "Lock" on a prompt to create your first entity</p>
                </div>
            """)

        # Build HTML for entity cards
        html_parts = ['<div class="space-y-3">']

        # Entity type colors
        type_colors = {
            "character": ("purple", "Character"),
            "prop": ("blue", "Prop"),
            "location": ("green", "Location"),
            "style": ("orange", "Style"),
        }

        for entity in entities:
            etype = entity.entity_type.value if hasattr(entity.entity_type, 'value') else entity.entity_type
            color, label = type_colors.get(etype, ("gray", etype.title()))

            # Truncate description for display
            desc = entity.description
            if len(desc) > 150:
                desc = desc[:147] + "..."

            html_parts.append(f'''
                <div class="glass-card rounded-lg p-4" data-entity-id="{entity.id}">
                    <div class="flex items-start justify-between gap-3">
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="text-{color}-400 text-xs px-1.5 py-0.5 rounded bg-{color}-500/20">{label}</span>
                                <h5 class="text-sm font-medium text-white truncate">{entity.name}</h5>
                            </div>
                            <p class="text-xs text-gray-400 line-clamp-2">{desc}</p>
                            {f'<p class="text-xs text-gray-600 mt-1">From: {entity.created_from_scene_key}</p>' if entity.created_from_scene_key else ''}
                        </div>
                        <div class="flex items-center gap-1">
                            <button onclick="deleteEntity({entity.id})"
                                    class="p-1.5 rounded text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                                    title="Delete entity">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            ''')

        html_parts.append('</div>')
        return HTMLResponse("".join(html_parts))

    # Return JSON for non-HTMX requests (API usage)
    return [e.to_dict() for e in entities]


@router.post("/runs/{run_id}/entities")
async def create_entity(
    request: Request,
    run_id: str,
    name: str = Form(...),
    entity_type: str = Form(...),
    description: str = Form(...),
    created_from_scene_key: str = Form(None),
    image: UploadFile = File(None),
):
    """
    Create a new entity for continuity tracking.

    Optionally accepts an image upload as reference.
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    try:
        etype = EntityType(entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity_type: {entity_type}")

    # Handle image upload
    image_path = None
    if image and image.filename:
        # Create entities images directory
        if record.output_path:
            images_dir = Path(record.output_path) / "entity_images"
            images_dir.mkdir(parents=True, exist_ok=True)

            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = name.replace(" ", "_").lower()
            ext = Path(image.filename).suffix or ".png"
            image_filename = f"{safe_name}_{timestamp}{ext}"
            image_path = images_dir / image_filename

            content = await image.read()
            image_path.write_bytes(content)
            image_path = str(image_path)

    entity = store.create_entity(
        run_id=run_id,
        name=name,
        entity_type=etype,
        description=description,
        reference_image_path=image_path,
        created_from_scene_key=created_from_scene_key,
    )

    if is_htmx_request(request):
        return HTMLResponse(
            f'<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            f'Entity "{name}" created</div>'
        )

    return entity.to_dict()


@router.get("/runs/{run_id}/entities/{entity_id}")
async def get_entity(run_id: str, entity_id: int):
    """Get a specific entity."""
    store = RunStore()
    entity = store.get_entity(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    if entity.run_id != run_id:
        raise HTTPException(status_code=400, detail="Entity does not belong to this run")

    # Get linked scenes
    scenes = store.get_scenes_for_entity(entity_id)

    result = entity.to_dict()
    result["linked_scenes"] = scenes

    return result


@router.put("/runs/{run_id}/entities/{entity_id}")
async def update_entity(
    request: Request,
    run_id: str,
    entity_id: int,
    name: str = Form(None),
    description: str = Form(None),
):
    """Update an entity."""
    store = RunStore()
    entity = store.get_entity(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    if entity.run_id != run_id:
        raise HTTPException(status_code=400, detail="Entity does not belong to this run")

    success = store.update_entity(
        entity_id=entity_id,
        name=name,
        description=description,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update entity")

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            'Entity updated</div>'
        )

    return {"success": True, "entity_id": entity_id}


@router.delete("/runs/{run_id}/entities/{entity_id}")
async def delete_entity(request: Request, run_id: str, entity_id: int):
    """Soft delete an entity."""
    store = RunStore()
    entity = store.get_entity(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    if entity.run_id != run_id:
        raise HTTPException(status_code=400, detail="Entity does not belong to this run")

    success = store.delete_entity(entity_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete entity")

    return {"success": True, "entity_id": entity_id}


@router.post("/runs/{run_id}/entities/{entity_id}/link/{scene_key}")
async def link_entity_to_scene(request: Request, run_id: str, entity_id: int, scene_key: str):
    """Link an entity to a scene."""
    store = RunStore()
    entity = store.get_entity(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    if entity.run_id != run_id:
        raise HTTPException(status_code=400, detail="Entity does not belong to this run")

    link = store.link_entity_to_scene(entity_id, run_id, scene_key)

    if is_htmx_request(request):
        return HTMLResponse(
            f'<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            f'Entity linked to {scene_key}</div>'
        )

    return link.to_dict()


@router.delete("/runs/{run_id}/entities/{entity_id}/link/{scene_key}")
async def unlink_entity_from_scene(request: Request, run_id: str, entity_id: int, scene_key: str):
    """Unlink an entity from a scene."""
    store = RunStore()
    entity = store.get_entity(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    if entity.run_id != run_id:
        raise HTTPException(status_code=400, detail="Entity does not belong to this run")

    success = store.unlink_entity_from_scene(entity_id, run_id, scene_key)

    if not success:
        raise HTTPException(status_code=404, detail="Link not found")

    return {"success": True}


@router.get("/runs/{run_id}/entities/for-scene/{scene_key}")
async def get_entities_for_scene(run_id: str, scene_key: str):
    """Get all entities linked to a specific scene."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    entities = store.get_entities_for_scene(run_id, scene_key)

    return [e.to_dict() for e in entities]


@router.get("/runs/{run_id}/entities/context/{scene_key}")
async def get_entity_context(run_id: str, scene_key: str):
    """Get formatted entity context block for prompt injection."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    context = store.get_entity_context_for_scene(run_id, scene_key)

    return {"context": context, "scene_key": scene_key}


@router.post("/runs/{run_id}/entities/export")
async def export_entities(request: Request, run_id: str):
    """Export entities to JSON and Markdown files."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    if not record.output_path:
        raise HTTPException(status_code=400, detail="Run has no output path")

    success = store.export_entities_for_run(run_id, Path(record.output_path))

    if not success:
        if is_htmx_request(request):
            return HTMLResponse(
                '<div class="alert-warning rounded-lg p-3 text-sm text-yellow-400">'
                'No entities to export</div>'
            )
        return {"success": False, "message": "No entities to export"}

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            'Entities exported to entities.json and entities.md</div>'
        )

    return {"success": True, "files": ["entities.json", "entities.md"]}


@router.post("/runs/{run_id}/entities/from-prompt/{prompt_id}")
async def create_entity_from_prompt(
    request: Request,
    run_id: str,
    prompt_id: int,
    name: str = Form(...),
    entity_type: str = Form(...),
    description: str = Form(None),
    image: UploadFile = File(None),
):
    """
    Create an entity from an existing prompt.

    User can provide a custom description or use the prompt text as default.
    This is the "Lock as Entity" functionality.
    """
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Get the prompt
    prompt = store.get_prompt_version(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    if prompt.run_id != run_id:
        raise HTTPException(status_code=400, detail="Prompt does not belong to this run")

    try:
        etype = EntityType(entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity_type: {entity_type}")

    # Use provided description or fall back to prompt text
    entity_description = description if description else prompt.prompt_text

    # Handle image upload
    image_path = None
    if image and image.filename:
        if record.output_path:
            images_dir = Path(record.output_path) / "entity_images"
            images_dir.mkdir(parents=True, exist_ok=True)

            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
            filename = f"{safe_name}_{timestamp}{Path(image.filename).suffix}"
            image_path = str(images_dir / filename)

            with open(image_path, "wb") as f:
                f.write(await image.read())
    elif prompt.image_path:
        # Use prompt's existing image if no new one uploaded
        image_path = prompt.image_path

    # Create entity
    entity = store.create_entity(
        run_id=run_id,
        name=name,
        entity_type=etype,
        description=entity_description,
        reference_image_path=image_path,
        created_from_scene_key=prompt.item_key,
    )

    # Auto-link to the source scene
    store.link_entity_to_scene(entity.id, run_id, prompt.item_key)

    if is_htmx_request(request):
        return HTMLResponse(
            f'<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            f'Entity "{name}" created and linked to {prompt.item_key}</div>'
        )

    return entity.to_dict()


# === Storage Management ===

@router.get("/storage/stats")
async def get_storage_stats(request: Request):
    """Get current storage statistics."""
    manager = get_storage_manager()
    stats = manager.get_storage_stats()

    if is_htmx_request(request):
        # Return HTML fragment for storage indicator
        used_pct = stats.used_pct
        color = "green" if used_pct < 70 else "yellow" if used_pct < 90 else "red"
        return HTMLResponse(f'''
            <div class="storage-indicator">
                <div class="flex items-center justify-between mb-1">
                    <span class="text-sm text-gray-400">Storage</span>
                    <span class="text-sm text-{color}-400">{stats.used_gb:.1f} / {manager.config.max_storage_gb:.0f} GB</span>
                </div>
                <div class="w-full bg-gray-700 rounded-full h-2">
                    <div class="bg-{color}-500 h-2 rounded-full" style="width: {min(used_pct, 100):.0f}%"></div>
                </div>
                <div class="flex justify-between text-xs text-gray-500 mt-1">
                    <span>{stats.deletable_run_count} deletable</span>
                    <span>{stats.protected_run_count} protected</span>
                </div>
            </div>
        ''')

    return StorageStatsResponse(**stats.to_dict())


@router.get("/storage/config")
async def get_storage_config():
    """Get current storage configuration."""
    manager = get_storage_manager()
    return StorageConfigResponse(**manager.config.to_dict())


@router.put("/storage/config")
async def update_storage_config(request: Request, payload: StorageConfigRequest):
    """Update storage configuration."""
    manager = get_storage_manager()

    # Build kwargs from non-None values
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}

    if updates:
        manager.update_config(**updates)

    if is_htmx_request(request):
        return HTMLResponse(
            '<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            'Storage settings saved</div>'
        )

    return StorageConfigResponse(**manager.config.to_dict())


@router.post("/storage/cleanup")
async def run_storage_cleanup(request: Request, payload: StorageCleanupRequest = None):
    """Run storage cleanup manually."""
    manager = get_storage_manager()
    force = payload.force if payload else False

    result = manager.run_cleanup(force=force)

    if is_htmx_request(request):
        if result.runs_deleted > 0:
            return HTMLResponse(
                f'<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
                f'Cleaned up {result.runs_deleted} runs, freed {result.gb_freed:.2f} GB</div>'
            )
        else:
            msg = "No cleanup needed" if not result.errors else f"Cleanup failed: {result.errors[0]}"
            return HTMLResponse(
                f'<div class="alert-info rounded-lg p-3 text-sm text-blue-400">{msg}</div>'
            )

    return StorageCleanupResponse(**result.to_dict())


@router.post("/storage/cleanup-rejected-images")
async def cleanup_rejected_images(request: Request):
    """Delete rejected image iterations across all runs."""
    manager = get_storage_manager()
    bytes_freed = manager.cleanup_rejected_images()
    gb_freed = bytes_freed / (1024 ** 3)

    if is_htmx_request(request):
        return HTMLResponse(
            f'<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            f'Deleted rejected images, freed {gb_freed:.2f} GB</div>'
        )

    return {"bytes_freed": bytes_freed, "gb_freed": round(gb_freed, 2)}


@router.post("/storage/cleanup-intermediate-videos")
async def cleanup_intermediate_videos(request: Request):
    """Delete intermediate video files."""
    manager = get_storage_manager()
    bytes_freed = manager.cleanup_intermediate_videos()
    gb_freed = bytes_freed / (1024 ** 3)

    if is_htmx_request(request):
        return HTMLResponse(
            f'<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
            f'Deleted intermediate videos, freed {gb_freed:.2f} GB</div>'
        )

    return {"bytes_freed": bytes_freed, "gb_freed": round(gb_freed, 2)}


@router.get("/storage/run/{run_id}")
async def get_run_storage_info(run_id: str):
    """Get storage info for a specific run."""
    manager = get_storage_manager()
    info = manager.get_run_storage_info(run_id)

    if not info:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    return info


# === Voice Generation ===

@router.get("/runs/{run_id}/voice/status")
async def get_voice_status(request: Request, run_id: str):
    """Get voice generation status for a run."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Check if voice file exists
    voice_path = None
    voice_exists = False
    if record.output_path:
        from pathlib import Path
        output_dir = Path(record.output_path)
        voice_files = list(output_dir.glob("voiceover_v*.mp3")) + list(output_dir.glob("voiceover_v*.json"))
        if voice_files:
            voice_path = str(sorted(voice_files)[-1])  # Latest version
            voice_exists = True

    return {
        "run_id": run_id,
        "voice_exists": voice_exists,
        "voice_path": voice_path,
        "stage": record.stage.value,
        "can_generate": record.stage == RunStage.SCRIPT_APPROVED or record.stage == RunStage.AWAITING_VOICEOVER_APPROVAL,
    }


@router.post("/runs/{run_id}/voice/generate")
async def generate_voice(request: Request, run_id: str):
    """Generate voiceover for a run."""
    from content_engine.services.voice_service import get_voice_service, VoiceSettings, VOICE_PRESETS

    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    if not record.output_path:
        raise HTTPException(status_code=400, detail="No output path for this run")

    from pathlib import Path
    import json

    output_dir = Path(record.output_path)

    # Read form data first (stream can only be consumed once)
    form_data = await request.form()

    # Use voice_script from form if provided, else fall back to disk
    script_text = form_data.get("voice_script", "").strip()
    if not script_text:
        txt_path = output_dir / "script.txt"
        json_path = output_dir / "script.json"
        if txt_path.exists():
            script_text = txt_path.read_text().strip()
        elif json_path.exists():
            script_data = json.loads(json_path.read_text())
            script_text = script_data.get("script", "")

    if not script_text:
        raise HTTPException(status_code=400, detail="Script file not found or empty")

    # Get scenes for timestamps
    shot_list_path = output_dir / "shot_list.json"
    scenes = None
    if shot_list_path.exists():
        shot_data = json.loads(shot_list_path.read_text())
        scenes = shot_data if isinstance(shot_data, list) else shot_data.get("shot_list", [])

    # voice_id from POST body takes priority; fall back to preset from run config
    voice_id = form_data.get("voice_id", "").strip()

    # Read all ElevenLabs settings from form (with defaults matching VoiceSettings)
    model_id = form_data.get("model_id", "eleven_v3").strip() or "eleven_v3"
    try:
        stability = float(form_data.get("stability", 0.5))
        similarity_boost = float(form_data.get("similarity_boost", 0.75))
        style = float(form_data.get("style", 0.0))
        speed = float(form_data.get("speed", 1.0))
    except (ValueError, TypeError):
        stability, similarity_boost, style, speed = 0.5, 0.75, 0.0, 1.0
    use_speaker_boost = form_data.get("use_speaker_boost", "true").lower() != "false"

    if voice_id:
        settings = VoiceSettings(
            voice_id=voice_id,
            model_id=model_id,
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            speed=speed,
            use_speaker_boost=use_speaker_boost,
        )
    else:
        voice_preset = record.config.get("voice_preset", "deep_motivational")
        preset_data = VOICE_PRESETS.get(voice_preset, VOICE_PRESETS["deep_motivational"])
        settings = VoiceSettings(
            voice_id=preset_data["voice_id"],
            model_id=model_id,
            stability=stability if form_data.get("stability") else preset_data.get("stability", 0.5),
            similarity_boost=similarity_boost if form_data.get("similarity_boost") else preset_data.get("similarity_boost", 0.75),
            style=style,
            speed=speed,
            use_speaker_boost=use_speaker_boost,
        )

    # Generate voice
    voice_name = form_data.get("voice_name", "").strip()
    voice_service = get_voice_service()
    result = voice_service.generate_voiceover(
        script=script_text,
        output_dir=output_dir,
        settings=settings,
        scenes=scenes,
    )

    # Update stage if successful
    if result.success:
        store.update_stage(run_id, RunStage.AWAITING_VOICEOVER_APPROVAL)
        # Write sidecar metadata for version history
        meta = {
            "version": result.version,
            "voice_id": settings.voice_id,
            "voice_name": voice_name or settings.voice_id,
            "model_id": settings.model_id,
            "created_at": result.created_at,
        }
        (output_dir / f"voiceover_v{result.version}_meta.json").write_text(
            json.dumps(meta, indent=2)
        )

    if is_htmx_request(request):
        if result.success:
            return templates.TemplateResponse(
                "partials/voice_result.html",
                {
                    "request": request,
                    "run_id": run_id,
                    "success": True,
                    "duration_seconds": result.duration_seconds,
                    "audio_path": str(result.audio_path) if result.audio_path else None,
                    "scene_timestamps": [t.to_dict() for t in result.scene_timestamps],
                },
            )
        else:
            return templates.TemplateResponse(
                "partials/voice_result.html",
                {
                    "request": request,
                    "run_id": run_id,
                    "success": False,
                    "error_message": result.error_message,
                    "duration_seconds": 0,
                    "audio_path": None,
                    "scene_timestamps": [],
                },
            )

    return result.to_dict()


@router.post("/runs/{run_id}/voice/regenerate")
async def regenerate_voice(request: Request, run_id: str):
    """Regenerate voiceover with optional modified settings."""
    from content_engine.services.voice_service import get_voice_service, VoiceSettings, VOICE_PRESETS

    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    if not record.output_path:
        raise HTTPException(status_code=400, detail="No output path for this run")

    from pathlib import Path
    import json

    output_dir = Path(record.output_path)

    # Read form data first (stream can only be consumed once)
    form_data = await request.form()
    notes = form_data.get("notes", "")

    # Use voice_script from form if provided, else fall back to disk
    script_text = form_data.get("voice_script", "").strip()
    if not script_text:
        txt_path = output_dir / "script.txt"
        json_path = output_dir / "script.json"
        if txt_path.exists():
            script_text = txt_path.read_text().strip()
        elif json_path.exists():
            script_data = json.loads(json_path.read_text())
            script_text = script_data.get("script", "")

    if not script_text:
        raise HTTPException(status_code=400, detail="Script file not found or empty")
    voice_id = form_data.get("voice_id", "").strip()

    # Read all ElevenLabs settings from form
    model_id = form_data.get("model_id", "eleven_v3").strip() or "eleven_v3"
    try:
        stability = float(form_data.get("stability", 0.5))
        similarity_boost = float(form_data.get("similarity_boost", 0.75))
        style = float(form_data.get("style", 0.0))
        speed = float(form_data.get("speed", 1.0))
    except (ValueError, TypeError):
        stability, similarity_boost, style, speed = 0.5, 0.75, 0.0, 1.0
    use_speaker_boost = form_data.get("use_speaker_boost", "true").lower() != "false"

    if voice_id:
        settings = VoiceSettings(
            voice_id=voice_id,
            model_id=model_id,
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            speed=speed,
            use_speaker_boost=use_speaker_boost,
        )
    else:
        voice_preset = form_data.get("voice_preset", record.config.get("voice_preset", "deep_motivational"))
        preset_data = VOICE_PRESETS.get(voice_preset, VOICE_PRESETS["deep_motivational"])
        settings = VoiceSettings(
            voice_id=preset_data["voice_id"],
            model_id=model_id,
            stability=stability if form_data.get("stability") else preset_data.get("stability", 0.5),
            similarity_boost=similarity_boost if form_data.get("similarity_boost") else preset_data.get("similarity_boost", 0.75),
            style=style,
            speed=speed,
            use_speaker_boost=use_speaker_boost,
        )

    # Get scenes
    shot_list_path = output_dir / "shot_list.json"
    scenes = None
    if shot_list_path.exists():
        raw = shot_list_path.read_text().strip()
        if raw:
            shot_data = json.loads(raw)
            scenes = shot_data if isinstance(shot_data, list) else shot_data.get("shot_list", [])

    voice_name = form_data.get("voice_name", "").strip()
    voice_service = get_voice_service()
    result = voice_service.regenerate_voiceover(
        script=script_text,
        output_dir=output_dir,
        settings=settings,
        scenes=scenes,
        notes=notes,
    )

    if result.success:
        meta = {
            "version": result.version,
            "voice_id": settings.voice_id,
            "voice_name": voice_name or settings.voice_id,
            "model_id": settings.model_id,
            "created_at": result.created_at,
        }
        (output_dir / f"voiceover_v{result.version}_meta.json").write_text(
            json.dumps(meta, indent=2)
        )

    if is_htmx_request(request):
        if result.success:
            return HTMLResponse(
                f'<div class="alert-success rounded-lg p-3 text-sm text-green-400">'
                f'Voice regenerated (v{result.version})! Duration: {result.duration_seconds:.1f}s</div>'
            )
        else:
            return HTMLResponse(
                f'<div class="alert-error rounded-lg p-3 text-sm text-red-400">'
                f'{result.error_message}</div>'
            )

    return result.to_dict()


@router.post("/runs/{run_id}/voice/enhance-script")
async def enhance_script(request: Request, run_id: str):
    """Use Claude CLI to insert v3 audio tags into a script."""
    import subprocess
    import os

    store = RunStore()
    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    form_data = await request.form()
    script = form_data.get("script", "").strip()
    if not script:
        raise HTTPException(status_code=400, detail="No script provided")

    system_prompt = (
        "You are an ElevenLabs v3 voice director. Given a motivational script, insert appropriate "
        "v3 audio tags in square brackets to make it sound like a real human delivering emotional "
        "content. Use tags from these categories: emotional states [excited][nervous][calm][tired], "
        "reactions [sigh][laughs softly][gasps][whispers], cognitive beats [pauses][hesitates][stammers], "
        "tone cues [cheerfully][flatly][playfully]. Rules: don't over-tag — maximum one tag per 2-3 "
        "sentences. Place tags at natural emotional beats. Never tag every sentence. Return only the "
        "enhanced script with tags inserted, nothing else."
    )
    full_prompt = f"{system_prompt}\n\n---\n\n{script}"

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    try:
        result = subprocess.run(
            ["claude", "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Claude CLI timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Claude CLI not found")

    if result.returncode != 0:
        raise HTTPException(status_code=502, detail=f"Claude CLI error: {result.stderr[:200]}")

    enhanced = result.stdout.strip()
    if not enhanced:
        raise HTTPException(status_code=502, detail="Claude returned empty response")

    return {"enhanced_script": enhanced}


@router.post("/runs/{run_id}/voice/approve")
async def approve_voice(request: Request, run_id: str):
    """Approve voiceover and continue to visuals stage."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Transition to VOICEOVER_APPROVED, then continue to visual generation
    store.update_stage(run_id, RunStage.VOICEOVER_APPROVED)

    if is_htmx_request(request):
        response = HTMLResponse(content="", status_code=200)
        response.headers["HX-Redirect"] = f"/runs/{run_id}/artifacts"
        return response

    return {"run_id": run_id, "stage": "voiceover_approved"}


@router.get("/runs/{run_id}/voice/audio")
async def get_voice_audio(run_id: str):
    """Get the voice audio file."""
    from fastapi.responses import FileResponse

    store = RunStore()
    record = store.get_run(run_id)

    if not record or not record.output_path:
        raise HTTPException(status_code=404, detail="Run not found")

    from pathlib import Path
    output_dir = Path(record.output_path)

    # Find latest voice file
    voice_files = list(output_dir.glob("voiceover_v*.mp3"))
    if not voice_files:
        raise HTTPException(status_code=404, detail="No voice audio found")

    latest = sorted(voice_files)[-1]
    return FileResponse(latest, media_type="audio/mpeg", filename=latest.name)


@router.get("/runs/{run_id}/voice/timestamps")
async def get_voice_timestamps(run_id: str):
    """Get scene timestamps for the voiceover."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record or not record.output_path:
        raise HTTPException(status_code=404, detail="Run not found")

    from pathlib import Path
    import json

    output_dir = Path(record.output_path)

    # Find latest voice stub file (contains timestamps)
    stub_files = list(output_dir.glob("voiceover_v*_stub.json"))
    if stub_files:
        latest = sorted(stub_files)[-1]
        data = json.loads(latest.read_text())
        return {"timestamps": data.get("scene_timestamps", [])}

    return {"timestamps": []}


# === Clip Submission ===

@router.post("/runs/{run_id}/clips/submit")
async def submit_video_clips(request: Request, run_id: str):
    """
    Accept uploaded video clips and resume the pipeline from AWAITING_VIDEO_CLIPS.

    Expects multipart form fields named clip_scene_1 through clip_scene_N.
    Saves files to the run output directory, then calls resume_from_video_clips().
    """
    from content_engine.pipeline.orchestrator import PipelineOrchestrator

    store = RunStore()
    record = store.get_run(run_id)

    if not record:
        raise HTTPException(status_code=404, detail="Run not found")

    if record.stage not in [RunStage.AWAITING_VIDEO_CLIPS, RunStage.VIDEO_CLIPS_READY]:
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting clips (current stage: {record.stage.value})"
        )

    if not record.output_path:
        raise HTTPException(status_code=400, detail="Run has no output path")

    output_dir = Path(record.output_path)

    # Parse multipart form
    form = await request.form()
    saved = []
    for field_name, file_obj in form.multi_items():
        if field_name.startswith("clip_scene_") and hasattr(file_obj, "read"):
            scene_num = field_name.replace("clip_scene_", "")
            dest = output_dir / f"clip_scene_{scene_num}.mp4"
            content = await file_obj.read()
            dest.write_bytes(content)
            saved.append(f"clip_scene_{scene_num}.mp4")

    if not saved:
        raise HTTPException(status_code=400, detail="No clip files received")

    # Resume pipeline
    orchestrator = PipelineOrchestrator()
    success, message = orchestrator.resume_from_video_clips(run_id)

    if not success:
        raise HTTPException(status_code=500, detail=f"Pipeline resume failed: {message}")

    return {"success": True, "clips_saved": saved, "stage": message}


@router.get("/runs/{run_id}/scenes")
async def get_all_scenes(run_id: str):
    """Get all scenes with script segments for a run."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record or not record.output_path:
        raise HTTPException(status_code=404, detail="Run not found")

    from pathlib import Path
    import json

    output_dir = Path(record.output_path)

    # Load script from script.txt (primary) or script.json (fallback)
    full_script = ""
    script_txt_path = output_dir / "script.txt"
    script_json_path = output_dir / "script.json"

    if script_txt_path.exists():
        full_script = script_txt_path.read_text()
    elif script_json_path.exists():
        script_data = json.loads(script_json_path.read_text())
        full_script = script_data.get("script", "")

    # Load shot list
    shot_list_path = output_dir / "shot_list.json"
    if not shot_list_path.exists():
        raise HTTPException(status_code=404, detail=f"Shot list not found at {shot_list_path}")

    shot_data = json.loads(shot_list_path.read_text())

    # Handle both array format and object format
    if isinstance(shot_data, list):
        scenes = shot_data
    else:
        scenes = shot_data.get("scenes", [])

    if not scenes:
        raise HTTPException(status_code=404, detail="No scenes found in shot list")

    # Build response with all scenes
    result = {
        "full_script": full_script,
        "scenes": []
    }

    for scene in scenes:
        scene_num = scene.get("scene_number", 0)
        voiceover = scene.get("voiceover_segment", "")

        # Find position in full script
        highlight_start = full_script.find(voiceover) if voiceover else -1
        highlight_end = highlight_start + len(voiceover) if highlight_start >= 0 else 0

        result["scenes"].append({
            "scene_key": f"scene_{scene_num}",
            "scene_number": scene_num,
            "beat_type": scene.get("beat_type", ""),
            "voiceover_segment": voiceover,
            "duration": scene.get("duration", 0),
            "visual_description": scene.get("visual_description", ""),
            "highlight_start": highlight_start,
            "highlight_end": highlight_end,
        })

    return result


@router.get("/runs/{run_id}/scene-context/{scene_key}")
async def get_scene_context(run_id: str, scene_key: str):
    """Get script context for a specific scene (for visual prompt editor)."""
    store = RunStore()
    record = store.get_run(run_id)

    if not record or not record.output_path:
        raise HTTPException(status_code=404, detail="Run not found")

    from pathlib import Path
    import json

    output_dir = Path(record.output_path)

    # Load script from script.txt (primary) or script.json (fallback)
    full_script = ""
    script_txt_path = output_dir / "script.txt"
    script_json_path = output_dir / "script.json"

    if script_txt_path.exists():
        full_script = script_txt_path.read_text()
    elif script_json_path.exists():
        script_data = json.loads(script_json_path.read_text())
        full_script = script_data.get("script", "")

    if not full_script:
        raise HTTPException(status_code=404, detail="Script not found (checked script.txt and script.json)")

    # Load shot list for scene info
    shot_list_path = output_dir / "shot_list.json"
    if not shot_list_path.exists():
        raise HTTPException(status_code=404, detail=f"Shot list not found at {shot_list_path}")

    shot_data = json.loads(shot_list_path.read_text())

    # Handle both array format and object format
    if isinstance(shot_data, list):
        scenes = shot_data
    else:
        scenes = shot_data.get("scenes", [])

    # Find the requested scene
    scene_number = int(scene_key.replace("scene_", "")) if scene_key.startswith("scene_") else 1
    target_scene = None

    for scene in scenes:
        if scene.get("scene_number") == scene_number:
            target_scene = scene
            break

    if not target_scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_key} not found in {len(scenes)} scenes")

    voiceover_segment = target_scene.get("voiceover_segment", "")

    # Find position in full script
    highlight_start = full_script.find(voiceover_segment) if voiceover_segment else -1
    highlight_end = highlight_start + len(voiceover_segment) if highlight_start >= 0 else 0

    return {
        "scene_number": scene_number,
        "beat_type": target_scene.get("beat_type", ""),
        "voiceover_segment": voiceover_segment,
        "duration": target_scene.get("duration", 0),
        "visual_description": target_scene.get("visual_description", ""),
        "full_script": full_script,
        "highlight_start": highlight_start,
        "highlight_end": highlight_end,
    }
