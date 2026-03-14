"""
Content Engine Wizard - FastAPI + Jinja2 + HTMX.

Server-rendered, thin UI for content generation with approval gates.
"""

from pathlib import Path
import logging
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from content_engine.services.drive_guard import DriveGuard
from content_engine.services.preset_loader import PresetLoader
from content_engine.services.run_store import RunStore, RunStage, FeedbackRecord, generate_display_title, WorkflowStage
from content_engine.services.background_runner import start_run_async
from content_engine.services.concurrency import get_concurrency_manager
from content_engine.services.storage_manager import get_storage_manager
from content_engine.pipeline.models.run_config import RunConfig
from content_engine.pipeline.orchestrator import PipelineOrchestrator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .api.routes import router as api_router


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Content Engine Wizard",
        description="Automated short-form video content generation",
        version="0.3.0",
    )

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Setup templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=templates_dir)

    # Add custom Jinja2 filters
    def basename_filter(path: str) -> str:
        """Extract filename from path."""
        return Path(path).name if path else ""

    templates.env.filters["basename"] = basename_filter

    # Include API routes
    app.include_router(api_router)

    # === Page Routes ===

    @app.get("/")
    async def index():
        """Root redirect to wizard (main UI)."""
        return RedirectResponse(url="/wizard", status_code=307)

    @app.get("/health")
    async def health():
        """Health check endpoint for tunnel/proxy monitoring."""
        return {"status": "ok"}

    @app.get("/wizard", response_class=HTMLResponse)
    async def wizard(request: Request):
        """Wizard Screen 1: Select presets and generate."""
        # Check drive status
        guard = DriveGuard()
        drive_result = guard.check()

        # Load presets
        loader = PresetLoader()
        niches = loader.get_all_presets("niches")
        styles = loader.get_all_presets("styles")
        voices = loader.get_all_presets("voices")
        visuals = loader.get_all_presets("visuals")

        return templates.TemplateResponse(
            "wizard.html",
            {
                "request": request,
                "drive_connected": drive_result.can_write,
                "drive_error": drive_result.error_message,
                "mount_command": drive_result.mount_command,
                "niches": niches,
                "styles": styles,
                "voices": voices,
                "visuals": visuals,
            },
        )

    @app.post("/wizard/start")
    async def wizard_start(
        request: Request,
        niche: str = Form(...),
        style: str = Form(...),
        voice_preset: str = Form("deep_motivational"),
        visual_mode: str = Form("hybrid"),
        visual_engine: str = Form("nanobanana"),
        topic: str = Form(""),
        loop_friendly_ending: str = Form(""),
    ):
        """
        Handle form submission from wizard.
        Creates run record, starts background execution, returns HX-Redirect to status page.
        """
        # Convert checkbox value to boolean
        loop_friendly = loop_friendly_ending == "true"
        logger.info(f"[wizard/start] Received: niche={niche}, style={style}, voice={voice_preset}, visual={visual_mode}, engine={visual_engine}, topic={topic}, loop_friendly={loop_friendly}")

        try:
            # Create config
            config = RunConfig(
                niche=niche,
                style=style,
                voice_preset=voice_preset,
                visual_mode=visual_mode,
                visual_engine=visual_engine,
                realism_mode="standard",
                topic=topic if topic else None,
                loop_friendly_ending=loop_friendly,
                dry_run=True,
                generate_shot_list=False,
            )

            # Create run record with STARTING stage
            store = RunStore()
            store.create_run(config.run_id, config.to_dict())
            store.update_stage(
                config.run_id,
                RunStage.STARTING,
                current_stage_name="Starting",
                progress_percent=0,
            )

            # Start background execution
            started = start_run_async(config.run_id, config)
            if started:
                logger.info(f"[wizard/start] Background run started: run_id={config.run_id}")
            else:
                logger.warning(f"[wizard/start] Run already active: run_id={config.run_id}")

            # Return HX-Redirect header to status page (immediately)
            response = Response(content="", status_code=200)
            response.headers["HX-Redirect"] = f"/runs/{config.run_id}/status"
            return response

        except Exception as e:
            logger.exception(f"[wizard/start] Error: {e}")
            # Return error HTML fragment
            return templates.TemplateResponse(
                "partials/generation_error.html",
                {"request": request, "error": str(e)},
                status_code=500,
            )

    @app.get("/runs/{run_id}/status", response_class=HTMLResponse)
    async def run_status_page(request: Request, run_id: str):
        """Run status page with live polling."""
        store = RunStore()
        record = store.get_run(run_id)

        if not record:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Run not found: {run_id}"},
            )

        # Get last log lines if output exists
        log_lines = []
        if record.output_path:
            log_path = Path(record.output_path) / "run_log.txt"
            if log_path.exists():
                lines = log_path.read_text().strip().split("\n")
                log_lines = lines[-5:]  # Last 5 lines

        return templates.TemplateResponse(
            "run_status.html",
            {
                "request": request,
                "run_id": run_id,
                "display_title": record.display_title,
                "stage": record.stage.value,
                "stage_display_name": record.stage_display_name,
                "progress_percent": record.computed_progress,
                "is_running": record.stage.is_running(),
                "output_path": record.output_path,
                "error_message": record.error_message,
                "log_lines": log_lines,
            },
        )

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    async def run_overview_page(request: Request, run_id: str):
        """Run overview page - comprehensive view of a run."""
        store = RunStore()
        record = store.get_run(run_id)

        if not record:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Run not found: {run_id}"},
            )

        config = record.config

        # Check for available artifacts
        has_shot_list = False
        has_nanobanana = False
        has_stock_queries = False
        available_files = []
        nanobanana_content = ""
        stock_queries_content = ""
        hook_text = ""

        if record.output_path:
            output_dir = Path(record.output_path)
            if output_dir.exists():
                # List available files
                for f in output_dir.iterdir():
                    if f.is_file():
                        available_files.append(f.name)

                # Check specific artifacts
                shot_list_path = output_dir / "shot_list.json"
                has_shot_list = shot_list_path.exists()

                nano_path = output_dir / "nanobanana_prompts.txt"
                if nano_path.exists():
                    has_nanobanana = True
                    nanobanana_content = nano_path.read_text()

                stock_path = output_dir / "stock_queries.txt"
                if stock_path.exists():
                    has_stock_queries = True
                    stock_queries_content = stock_path.read_text()

                # Get hook from script_meta
                meta_path = output_dir / "script_meta.json"
                if meta_path.exists():
                    import json
                    meta = json.loads(meta_path.read_text())
                    hook_text = meta.get("hook", "")

        # Check for voice file
        has_voice = False
        if record.output_path:
            output_dir = Path(record.output_path)
            if output_dir.exists():
                has_voice = bool(list(output_dir.glob("voiceover_v*.mp3")))

        # Get quick feedback if exists
        quick_feedback = store.get_feedback(run_id)

        # Get provider and concurrency info
        try:
            orchestrator = PipelineOrchestrator()
            provider_info = orchestrator.get_provider_info()
            provider_type = provider_info.get("type", "stub")
        except Exception:
            provider_type = "stub"

        concurrency = get_concurrency_manager()
        regenerations_remaining = concurrency.get_remaining_regenerations(run_id)
        max_regenerations = concurrency.config.max_regenerations_per_run

        return templates.TemplateResponse(
            "run_overview.html",
            {
                "request": request,
                "run_id": run_id,
                "display_title": record.display_title,
                "stage": record.stage.value,
                "stage_display_name": record.stage_display_name,
                "progress_percent": record.computed_progress,
                "is_running": record.stage.is_running(),
                "niche": config.get("niche", "unknown"),
                "style": config.get("style", "unknown"),
                "voice_preset": config.get("voice_preset", "default"),
                "visual_mode": config.get("visual_mode", "hybrid"),
                "created_at": record.created_at,
                "output_path": record.output_path,
                "error_message": record.error_message,
                "hook": hook_text,
                "has_shot_list": has_shot_list,
                "has_nanobanana": has_nanobanana,
                "has_stock_queries": has_stock_queries,
                "has_files": len(available_files) > 0,
                "available_files": sorted(available_files),
                "nanobanana_content": nanobanana_content,
                "stock_queries_content": stock_queries_content,
                "quick_feedback": quick_feedback,
                "provider_type": provider_type,
                "regenerations_remaining": regenerations_remaining,
                "max_regenerations": max_regenerations,
                "has_voice": has_voice,
                "posted_at": record.posted_at,
            },
        )

    @app.get("/runs/{run_id}/voice", response_class=HTMLResponse)
    async def run_voice_page(request: Request, run_id: str, next: str = ""):
        """Voice generation page."""
        import json
        import os
        from content_engine.services.voice_service import VOICE_PRESETS

        store = RunStore()
        record = store.get_run(run_id)

        if not record:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Run not found: {run_id}"},
            )

        config = record.config

        # Get script and hook
        script_text = ""
        hook_text = ""
        word_count = 0
        duration_estimate = 0

        if record.output_path:
            output_dir = Path(record.output_path)

            # Load script: check script.txt first (pipeline output), fall back to script.json
            txt_path = output_dir / "script.txt"
            json_path = output_dir / "script.json"
            meta_path = output_dir / "script_meta.json"

            if txt_path.exists():
                script_text = txt_path.read_text().strip()
            elif json_path.exists():
                script_data = json.loads(json_path.read_text())
                script_text = script_data.get("script", "")

            # Load hook from script_meta.json if available, else fall back to script.json
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                hook_text = meta.get("hook", "")
                duration_estimate = meta.get("duration_estimate", 0)
            elif json_path.exists() and not script_text:
                script_data = json.loads(json_path.read_text())
                hook_text = script_data.get("hook", "")

            if script_text and not duration_estimate:
                word_count = len(script_text.split())
                duration_estimate = (word_count / 150) * 60
            elif script_text:
                word_count = len(script_text.split())

        # Check for existing voice files
        voice_exists = False
        stub_exists = False
        voice_path = None
        duration_seconds = 0
        scene_timestamps = []

        if record.output_path:
            output_dir = Path(record.output_path)
            voice_files = sorted(output_dir.glob("voiceover_v*.mp3"))
            stub_files = sorted(output_dir.glob("voiceover_v*_stub.json"))

            if voice_files:
                voice_exists = True
                voice_path = str(voice_files[-1])

            if stub_files:
                stub_exists = True
                stub_data = json.loads(stub_files[-1].read_text())
                scene_timestamps = stub_data.get("scene_timestamps", [])
                duration_seconds = stub_data.get("estimated_duration", 0)

        # Build voice presets list
        voice_presets = [
            {"name": name, "display_name": data["display_name"], "description": data["description"]}
            for name, data in VOICE_PRESETS.items()
        ]

        # Check ElevenLabs availability
        elevenlabs_available = bool(os.environ.get("ELEVENLABS_API_KEY"))

        return templates.TemplateResponse(
            "voice.html",
            {
                "request": request,
                "run_id": run_id,
                "display_title": record.display_title,
                "script_text": script_text,
                "hook": hook_text,
                "word_count": word_count,
                "duration_estimate": int(duration_estimate),
                "voice_exists": voice_exists,
                "stub_exists": stub_exists,
                "voice_path": voice_path,
                "duration_seconds": duration_seconds,
                "scene_timestamps": scene_timestamps,
                "voice_presets": voice_presets,
                "current_preset": config.get("voice_preset", "deep_motivational"),
                "elevenlabs_available": elevenlabs_available,
                "next_page": next,
            },
        )

    @app.get("/runs/{run_id}/artifacts", response_class=HTMLResponse)
    async def run_artifacts_page(request: Request, run_id: str):
        """Run artifacts page - view and regenerate prompts."""
        from content_engine.services.run_store import ArtifactType

        store = RunStore()
        record = store.get_run(run_id)

        if not record:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Run not found: {run_id}"},
            )

        config = record.config

        # Get hook and script info
        hook_text = ""
        word_count = 0
        duration_estimate = 0
        full_script = ""

        if record.output_path:
            output_dir = Path(record.output_path)
            meta_path = output_dir / "script_meta.json"
            script_path = output_dir / "script.txt"
            script_json_path = output_dir / "script.json"

            if meta_path.exists():
                import json
                meta = json.loads(meta_path.read_text())
                hook_text = meta.get("hook", "")
                duration_estimate = meta.get("duration_estimate", 0)

            # Try to load script text
            if script_path.exists():
                full_script = script_path.read_text()
                word_count = len(full_script.split())
            elif script_json_path.exists():
                import json
                script_data = json.loads(script_json_path.read_text())
                full_script = script_data.get("script", "")
                word_count = len(full_script.split())
                if not hook_text:
                    hook_text = script_data.get("hook", "")

        # Get shot list FIRST (needed for beat_type lookup)
        shots = []
        beat_type_map = {}  # scene_number -> beat_type
        if record.output_path:
            output_dir = Path(record.output_path)
            json_path = output_dir / "shot_list.json"
            if json_path.exists():
                import json
                _raw = json_path.read_text().strip()
                raw_shots = json.loads(_raw) if _raw else []
                for s in raw_shots:
                    scene_num = s.get("scene_number", 0)
                    beat_type = s.get("beat_type", "UNKNOWN")
                    beat_type_map[scene_num] = beat_type
                    shots.append({
                        "scene_number": scene_num,
                        "beat_type": beat_type,
                        "duration": s.get("duration", 0),
                        "voiceover_segment": s.get("voiceover_segment", ""),
                        "visual_description": s.get("visual_description", ""),
                        "overlay_text": s.get("overlay", {}).get("text", "") if s.get("overlay") else "",
                        "overlay_position": s.get("overlay", {}).get("position", "") if s.get("overlay") else "",
                    })

        # Get prompts by type (ACTIVE + PENDING + LOCKED for sequential generation)
        nanobanana_prompts = store.get_prompts_for_artifacts(run_id, ArtifactType.NANOBANANA)
        stock_queries = store.get_prompts_for_artifacts(run_id, ArtifactType.STOCK_QUERY)

        # Add version navigation info to each prompt
        def enrich_with_version_info(prompts, artifact_type):
            enriched = []
            if not prompts:
                return enriched

            # Build a map of scene statuses to check if previous scenes are locked
            scene_status = {}
            for p in prompts:
                scene_status[p.item_key] = p.status.value if hasattr(p.status, 'value') else str(p.status)

            for p in prompts:
                try:
                    d = p.to_dict()
                    # Get version info for this item
                    version_info = store.get_prompt_version_info(run_id, p.artifact_type, p.item_key) or {}
                    d["has_prev"] = p.version > 1
                    d["has_next"] = p.version < version_info.get("max_version", p.version)
                    d["max_version"] = version_info.get("max_version", p.version)
                    d["total_versions"] = version_info.get("total_versions", 1)

                    # Determine if this scene can be generated (for PENDING/OUTDATED scenes)
                    scene_num = p.scene_number
                    can_generate = False
                    if scene_num:
                        if scene_num == 1:
                            can_generate = True  # First scene can always be generated
                        else:
                            prev_scene_key = f"scene_{scene_num - 1}"
                            prev_status = scene_status.get(prev_scene_key, "")
                            can_generate = prev_status == "locked"

                    d["can_generate"] = can_generate
                    d["scene_number"] = scene_num
                    # Add beat_type from shot list
                    d["beat_type"] = beat_type_map.get(scene_num, "")

                    enriched.append(d)
                except Exception as e:
                    # Log but don't crash on individual prompt errors
                    import logging
                    logging.getLogger(__name__).warning(f"Error enriching prompt {getattr(p, 'id', 'unknown')}: {e}")
            return enriched

        nanobanana_prompts_enriched = enrich_with_version_info(nanobanana_prompts, ArtifactType.NANOBANANA)
        stock_queries_enriched = enrich_with_version_info(stock_queries, ArtifactType.STOCK_QUERY)

        # Get full prompt history
        prompt_history = store.get_prompt_history(run_id)

        # Get files list
        files = []
        if record.output_path:
            output_dir = Path(record.output_path)
            if output_dir.exists():
                for f in output_dir.iterdir():
                    if f.is_file():
                        size = f.stat().st_size
                        if size < 1024:
                            size_display = f"{size} B"
                        elif size < 1024 * 1024:
                            size_display = f"{size / 1024:.1f} KB"
                        else:
                            size_display = f"{size / (1024 * 1024):.1f} MB"
                        files.append({
                            "name": f.name,
                            "size": size,
                            "size_display": size_display,
                        })
                files.sort(key=lambda x: x["name"])

        # Check if shot list exists (for sync button)
        has_shot_list = bool(shots)

        # Load voice timestamps from stub file
        scene_timestamps_map = {}
        has_voice = False
        if record.output_path:
            output_dir = Path(record.output_path)
            stub_files = sorted(output_dir.glob("voiceover_v*_stub.json"))
            if stub_files:
                import json as _json
                stub_data = _json.loads(stub_files[-1].read_text())
                for ts in stub_data.get("scene_timestamps", []):
                    sn = ts.get("scene_number", 0)
                    scene_timestamps_map[sn] = ts
            has_voice = bool(list(output_dir.glob("voiceover_v*.mp3")))

        if not has_voice:
            return RedirectResponse(
                url=f"/runs/{run_id}/voice?next=artifacts", status_code=303
            )

        # Check if run is still generating (for auto-refresh)
        is_generating = record.stage in [
            RunStage.SCRIPT_APPROVED,
            RunStage.GENERATING_SHOT_LIST,
            RunStage.GENERATING_VISUALS,
            RunStage.GENERATING_STOCK_QUERIES,
        ]

        return templates.TemplateResponse(
            "run_artifacts.html",
            {
                "request": request,
                "run_id": run_id,
                "display_title": record.display_title,
                "niche": config.get("niche", "unknown"),
                "style": config.get("style", "unknown"),
                "hook": hook_text,
                "word_count": word_count,
                "duration_estimate": duration_estimate,
                "created_at": record.created_at,
                "output_path": record.output_path,
                "nanobanana_prompts": nanobanana_prompts_enriched,
                "stock_queries": stock_queries_enriched,
                "prompt_history": [p.to_dict() for p in prompt_history],
                "shots": shots,
                "files": files,
                "has_shot_list": has_shot_list,
                "run_stage": record.stage.value,
                "is_generating": is_generating,
                "full_script": full_script,
                "scene_timestamps_map": scene_timestamps_map,
                "has_voice": has_voice,
            },
        )

    @app.get("/runs/{run_id}/shot-list", response_class=HTMLResponse)
    async def shot_list_view(request: Request, run_id: str):
        """View shot list for a run."""
        store = RunStore()
        record = store.get_run(run_id)

        if not record:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Run not found: {run_id}"},
            )

        shots = []
        shot_list_json = "{}"
        shot_list_md = ""

        if record.output_path:
            output_dir = Path(record.output_path)

            # Load JSON
            json_path = output_dir / "shot_list.json"
            if json_path.exists():
                import json
                shot_list_json = json_path.read_text()
                raw_shots = json.loads(shot_list_json)
                # Transform to template-friendly format
                for s in raw_shots:
                    shots.append({
                        "scene_number": s.get("scene_number", 0),
                        "beat_type": s.get("beat_type", "UNKNOWN"),
                        "duration": s.get("duration", 0),
                        "voiceover_segment": s.get("voiceover_segment", ""),
                        "visual_description": s.get("visual_description", ""),
                        "overlay_text": s.get("overlay", {}).get("text", "") if s.get("overlay") else "",
                        "overlay_position": s.get("overlay", {}).get("position", "") if s.get("overlay") else "",
                        "match_score": s.get("match_score", 0),
                    })

            # Load Markdown
            md_path = output_dir / "shot_list.md"
            if md_path.exists():
                shot_list_md = md_path.read_text()

        return templates.TemplateResponse(
            "shot_list_view.html",
            {
                "request": request,
                "run_id": run_id,
                "display_title": record.display_title,
                "shots": shots,
                "shot_list_json": shot_list_json,
                "shot_list_md": shot_list_md,
            },
        )

    @app.get("/wizard/approve/{run_id}", response_class=HTMLResponse)
    async def script_approval(request: Request, run_id: str):
        """Wizard Screen 2: Script preview and approval."""
        store = RunStore()
        record = store.get_run(run_id)

        if not record:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Run not found: {run_id}"},
            )

        # Load script from output
        script_text = ""
        hook_text = ""
        if record.output_path:
            script_path = Path(record.output_path) / "script.txt"
            meta_path = Path(record.output_path) / "script_meta.json"

            if script_path.exists():
                script_text = script_path.read_text()

            if meta_path.exists():
                import json
                meta = json.loads(meta_path.read_text())
                hook_text = meta.get("hook", "")

        config = record.config

        return templates.TemplateResponse(
            "script_approval.html",
            {
                "request": request,
                "run_id": run_id,
                "display_title": record.display_title,
                "stage": record.stage.value,
                "niche": config.get("niche", "unknown"),
                "style": config.get("style", "unknown"),
                "script": script_text,
                "hook": hook_text,
                "notes": record.notes or "",
                "output_path": record.output_path,
            },
        )

    @app.get("/wizard/feedback/{run_id}", response_class=HTMLResponse)
    async def feedback_page(request: Request, run_id: str):
        """Post-publish review page."""
        from datetime import date

        store = RunStore()
        record = store.get_run(run_id)

        if not record:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Run not found: {run_id}"},
            )

        # Get existing feedback if any
        feedback = store.get_feedback(run_id)
        if not feedback:
            feedback = FeedbackRecord(run_id=run_id)

        return templates.TemplateResponse(
            "feedback.html",
            {
                "request": request,
                "run_id": run_id,
                "display_title": record.display_title,
                "feedback": feedback,
                "today": date.today().isoformat(),
            },
        )

    @app.get("/wizard/pending", response_class=HTMLResponse)
    async def pending_runs(request: Request):
        """List runs awaiting approval."""
        store = RunStore()
        pending = store.get_pending_runs()
        recent = store.get_recent_runs(limit=5)

        return templates.TemplateResponse(
            "pending.html",
            {
                "request": request,
                "pending": pending,
                "recent": recent,
            },
        )

    @app.get("/queue", response_class=HTMLResponse)
    async def queue_page(request: Request, run_id: str = None):
        """Queue page - runs in progress (not yet posted)."""
        store = RunStore()
        runs = store.get_queue_runs(limit=50)

        # Select the specified run or default to first
        selected_run = None
        if runs:
            if run_id:
                selected_run = next((r for r in runs if r.run_id == run_id), runs[0])
            else:
                selected_run = runs[0]

        return templates.TemplateResponse(
            "queue.html",
            {
                "request": request,
                "runs": runs,
                "selected_run": selected_run,
            },
        )

    @app.get("/reviews", response_class=HTMLResponse)
    async def reviews_page(request: Request):
        """Reviews page - posted runs (POSTED or REVIEW_READY stages)."""
        store = RunStore()
        # Get posted runs instead of runs_with_feedback
        posted_runs = store.get_posted_runs(limit=50)
        # Also get runs with feedback for backwards compatibility
        runs_with_feedback = store.get_runs_with_feedback(limit=50)

        return templates.TemplateResponse(
            "reviews.html",
            {
                "request": request,
                "posted_runs": posted_runs,
                "runs_with_feedback": runs_with_feedback,
            },
        )

    @app.get("/reviews/import", response_class=HTMLResponse)
    async def reviews_import_page(request: Request):
        """Screenshot import page - upload analytics screenshot."""
        store = RunStore()
        recent_runs = store.get_recent_runs(limit=20)

        return templates.TemplateResponse(
            "reviews_import.html",
            {
                "request": request,
                "recent_runs": recent_runs,
            },
        )

    @app.get("/reviews/import/{draft_id}", response_class=HTMLResponse)
    async def reviews_import_draft_page(request: Request, draft_id: int):
        """Draft review page - verify extracted metrics before saving."""
        store = RunStore()
        draft = store.get_import_draft(draft_id)

        if not draft:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Draft not found: {draft_id}"},
            )

        # Parse extracted JSON
        import json
        extracted = json.loads(draft.get("extracted_json", "{}"))

        # Get recent runs for linking
        recent_runs = store.get_recent_runs(limit=20)

        # Platform color mapping
        platform_colors = {
            "tiktok": "pink",
            "instagram": "purple",
            "youtube": "red",
        }
        platform_color = platform_colors.get(draft.get("platform", ""), "gray")

        return templates.TemplateResponse(
            "reviews_import_draft.html",
            {
                "request": request,
                "draft": draft,
                "extracted": extracted,
                "recent_runs": recent_runs,
                "platform_color": platform_color,
            },
        )

    @app.get("/library", response_class=HTMLResponse)
    async def library_page(request: Request, filter: str = None):
        """Library page - all runs with filters."""
        store = RunStore()

        # Get all runs
        all_runs = store.get_recent_runs(limit=100)

        # Get run IDs that have feedback
        runs_with_feedback = store.get_runs_with_feedback(limit=100)
        reviewed_run_ids = {run.run_id for run, _ in runs_with_feedback}

        # Apply filter
        if filter == "pending":
            runs = [r for r in all_runs if r.stage.value == "awaiting_script_approval"]
        elif filter == "approved":
            runs = [r for r in all_runs if r.stage.value in ["script_approved", "complete"]]
        elif filter == "reviewed":
            runs = [r for r in all_runs if r.run_id in reviewed_run_ids]
        else:
            runs = all_runs

        return templates.TemplateResponse(
            "library.html",
            {
                "request": request,
                "runs": runs,
                "filter": filter,
                "reviewed_run_ids": reviewed_run_ids,
            },
        )

    @app.get("/wizard/presets", response_class=HTMLResponse)
    async def presets_list(request: Request):
        """List all presets with edit links."""
        loader = PresetLoader()
        niches = loader.get_all_presets("niches")
        styles = loader.get_all_presets("styles")
        voices = loader.get_all_presets("voices")
        visuals = loader.get_all_presets("visuals")
        realism = loader.get_all_presets("realism")

        return templates.TemplateResponse(
            "presets.html",
            {
                "request": request,
                "niches": niches,
                "styles": styles,
                "voices": voices,
                "visuals": visuals,
                "realism": realism,
            },
        )

    @app.get("/wizard/presets/{preset_type}/{preset_name}", response_class=HTMLResponse)
    async def preset_stats_page(request: Request, preset_type: str, preset_name: str):
        """Preset stats and tuning memo page."""
        if preset_type not in ("niche", "style"):
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Invalid preset type: {preset_type}"},
            )

        store = RunStore()
        stats = store.get_preset_stats(preset_type, preset_name)
        tuning = store.get_tuning_memo(preset_type, preset_name)

        if not tuning:
            from content_engine.services.run_store import PresetTuningMemo
            tuning = PresetTuningMemo(preset_type=preset_type, preset_name=preset_name, memo_text="")

        return templates.TemplateResponse(
            "preset_stats.html",
            {
                "request": request,
                "preset_type": preset_type,
                "preset_name": preset_name,
                "stats": stats,
                "tuning": tuning,
            },
        )

    @app.get("/wizard/presets/{category}/{name}/edit", response_class=HTMLResponse)
    async def preset_editor_page(request: Request, category: str, name: str):
        """Preset editor page."""
        import json

        loader = PresetLoader()
        preset = loader.get_preset(category, name)

        if not preset:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"Preset not found: {category}/{name}"},
            )

        # Get required keys for this category
        required_keys_map = {
            "niches": ["display_name", "description"],
            "styles": ["display_name", "description", "energy"],
            "voices": ["display_name", "description"],
            "visuals": ["display_name", "description"],
            "realism": ["display_name", "description"],
        }
        required_keys = required_keys_map.get(category, ["display_name"])

        # Get backup history
        history_dir = loader.presets_dir / "_history"
        backups = []
        if history_dir.exists():
            for f in history_dir.glob(f"*_{name}.json"):
                parts = f.stem.split("_")
                if len(parts) >= 3:
                    timestamp = f"{parts[0]}_{parts[1]}"
                    backups.append({
                        "filename": f.name,
                        "timestamp": timestamp,
                    })
            backups.sort(key=lambda x: x["timestamp"], reverse=True)
            backups = backups[:10]  # Limit to 10

        return templates.TemplateResponse(
            "preset_editor.html",
            {
                "request": request,
                "category": category,
                "preset_name": name,
                "content": json.dumps(preset.data, indent=2),
                "preset_path": str(preset.path),
                "required_keys": required_keys,
                "backups": backups,
            },
        )

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        """Settings page - storage management and configuration."""
        storage_manager = get_storage_manager()

        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "config": storage_manager.config.to_dict(),
            },
        )

    @app.get("/knowledge", response_class=HTMLResponse)
    async def knowledge_base_page(request: Request):
        """Knowledge Base management page."""
        try:
            from content_engine.knowledge import get_registry, compare_internal_external

            registry = get_registry()
            external_docs = registry.get_external_documents()
            learning_summary = registry.read_learning_summary()

            # Run comparison
            comparison = compare_internal_external()

            return templates.TemplateResponse(
                "knowledge_base.html",
                {
                    "request": request,
                    "external_docs": [
                        {
                            "id": d.id,
                            "title": d.title,
                            "type": d.type,
                            "description": d.description,
                            "tags": d.tags,
                            "priority": d.priority,
                            "added_at": d.added_at,
                        }
                        for d in external_docs
                    ],
                    "learning_summary": learning_summary,
                    "comparison": comparison.to_dict(),
                    "config": {
                        "sample_size_threshold": registry.config.sample_size_threshold,
                        "auto_learn_enabled": registry.config.auto_learn_enabled,
                    },
                },
            )
        except FileNotFoundError as e:
            return templates.TemplateResponse(
                "knowledge_base.html",
                {
                    "request": request,
                    "error": str(e),
                    "external_docs": [],
                    "learning_summary": {},
                    "comparison": {"agreements": [], "conflicts": [], "pending": []},
                    "config": {},
                },
            )

    return app


# Create app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
