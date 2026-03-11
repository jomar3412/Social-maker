"""
Pydantic schemas for API requests/responses.
"""

from pydantic import BaseModel, Field
from typing import Optional


class GenerateRequest(BaseModel):
    """Request to start content generation."""
    niche: str
    style: str
    voice_preset: str = "deep_motivational"
    visual_mode: str = "hybrid"
    realism_mode: str = "standard"
    topic: Optional[str] = None
    loop_friendly_ending: bool = False  # Enable ending that flows back to hook


class ApproveScriptRequest(BaseModel):
    """Request to approve a script."""
    run_id: str


class RegenerateScriptRequest(BaseModel):
    """Request to regenerate a script."""
    run_id: str
    feedback: Optional[str] = None


class DriveStatusResponse(BaseModel):
    """G Drive status response."""
    connected: bool
    mount_path: Optional[str]
    error_message: Optional[str]
    mount_command: Optional[str]


class RunStatusResponse(BaseModel):
    """Run status response."""
    run_id: str
    stage: str
    niche: str
    style: str
    display_title: Optional[str] = None
    output_path: Optional[str]
    error_message: Optional[str]


class NotesUpdateRequest(BaseModel):
    """Request to update run notes."""
    notes: str


class FeedbackRequest(BaseModel):
    """Request to save feedback for a run."""
    script_quality: Optional[int] = Field(None, ge=1, le=5)
    hook_strength: Optional[int] = Field(None, ge=1, le=5)
    visual_match: Optional[int] = Field(None, ge=1, le=5)
    tags: list[str] = []
    publish_status: Optional[str] = None  # draft, published, archived
    platform: Optional[str] = None  # youtube, tiktok, instagram
    posted_url: Optional[str] = None  # URL to the published video
    post_date: Optional[str] = None  # Date posted (YYYY-MM-DD)
    views: Optional[int] = None
    avg_watch_time: Optional[float] = None
    retention_pct: Optional[float] = Field(None, ge=0, le=100)
    likes: Optional[int] = None
    shares: Optional[int] = None
    comments: Optional[int] = None
    feedback_notes: Optional[str] = None


class FeedbackResponse(BaseModel):
    """Feedback response."""
    run_id: str
    script_quality: Optional[int] = None
    hook_strength: Optional[int] = None
    visual_match: Optional[int] = None
    tags: list[str] = []
    publish_status: Optional[str] = None
    platform: Optional[str] = None
    posted_url: Optional[str] = None
    post_date: Optional[str] = None
    views: Optional[int] = None
    avg_watch_time: Optional[float] = None
    retention_pct: Optional[float] = None
    likes: Optional[int] = None
    shares: Optional[int] = None
    comments: Optional[int] = None
    feedback_notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PresetStatsResponse(BaseModel):
    """Aggregated stats for a preset."""
    preset_type: str
    preset_name: str
    total_runs: int
    avg_script_quality: Optional[float] = None
    avg_hook_strength: Optional[float] = None
    avg_visual_match: Optional[float] = None
    common_tags: list[str] = []


class TuningMemoRequest(BaseModel):
    """Request to update tuning memo."""
    memo_text: str


class TuningMemoResponse(BaseModel):
    """Tuning memo response."""
    preset_type: str
    preset_name: str
    memo_text: Optional[str] = None
    avg_script_quality: Optional[float] = None
    avg_hook_strength: Optional[float] = None
    avg_visual_match: Optional[float] = None
    common_tags: list[str] = []
    total_runs: int = 0
    updated_at: Optional[str] = None


class QuickFeedbackRequest(BaseModel):
    """Request for quick feedback (rating + notes only)."""
    script_quality: Optional[int] = Field(None, ge=1, le=5)
    feedback_notes: Optional[str] = None


class PresetEditRequest(BaseModel):
    """Request to edit a preset."""
    content: str  # JSON content as string


class PresetEditResponse(BaseModel):
    """Response after editing a preset."""
    success: bool
    message: str
    backup_path: Optional[str] = None
    new_fingerprint: Optional[str] = None


class RegeneratePromptRequest(BaseModel):
    """Request to regenerate a prompt."""
    prompt_id: Optional[int] = None  # If regenerating existing prompt
    artifact_type: str  # nanobanana, stock_query, shot_list
    item_key: str  # scene_1, hook, etc.
    notes: Optional[str] = None  # Why regenerating


class RegeneratePromptResponse(BaseModel):
    """Response after regenerating a prompt."""
    success: bool
    prompt_id: int
    version: int
    message: str
    learning_logged: bool = False


class PromptVersionResponse(BaseModel):
    """Response for a prompt version."""
    id: int
    run_id: str
    artifact_type: str
    item_key: str
    version: int
    prompt_text: str
    notes: Optional[str] = None
    image_path: Optional[str] = None
    created_at: Optional[str] = None
    created_by: str
    status: str


class PromptStatsResponse(BaseModel):
    """Stats about prompts for a run."""
    total_versions: int
    active_prompts: int
    by_type: dict


# === Storage Management Schemas ===

class StorageConfigRequest(BaseModel):
    """Request to update storage configuration."""
    max_storage_gb: Optional[float] = None
    cleanup_threshold_pct: Optional[float] = Field(None, ge=0, le=100)
    cleanup_target_pct: Optional[float] = Field(None, ge=0, le=100)
    deletion_policy: Optional[str] = None  # "full" or "assets_only"
    delete_rejected_images: Optional[bool] = None
    delete_intermediate_videos: Optional[bool] = None


class StorageConfigResponse(BaseModel):
    """Storage configuration response."""
    max_storage_gb: float
    cleanup_threshold_pct: float
    cleanup_target_pct: float
    deletion_policy: str
    delete_rejected_images: bool
    delete_intermediate_videos: bool


class StorageStatsResponse(BaseModel):
    """Storage statistics response."""
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_gb: float
    total_gb: float
    free_gb: float
    used_pct: float
    run_count: int
    deletable_run_count: int
    protected_run_count: int


class StorageCleanupRequest(BaseModel):
    """Request to run storage cleanup."""
    force: bool = False  # Run even if not above threshold


class StorageCleanupResponse(BaseModel):
    """Response after storage cleanup."""
    success: bool
    runs_deleted: int
    bytes_freed: int
    gb_freed: float
    errors: list[str] = []
    deleted_run_ids: list[str] = []


# === Voice Generation Schemas ===

class VoiceSettingsRequest(BaseModel):
    """Voice generation settings."""
    voice_id: Optional[str] = None
    stability: Optional[float] = Field(None, ge=0, le=1)
    similarity_boost: Optional[float] = Field(None, ge=0, le=1)
    style: Optional[float] = Field(None, ge=0, le=1)
    use_speaker_boost: Optional[bool] = None
    model_id: Optional[str] = None


class VoiceGenerateRequest(BaseModel):
    """Request to generate voiceover."""
    settings: Optional[VoiceSettingsRequest] = None
    notes: Optional[str] = None


class VoiceGenerationResponse(BaseModel):
    """Response after voice generation."""
    success: bool
    audio_path: Optional[str] = None
    duration_seconds: float = 0.0
    scene_timestamps: list[dict] = []
    error_message: Optional[str] = None
    version: int = 1


class SceneContextResponse(BaseModel):
    """Scene context for visual prompt editor."""
    scene_number: int
    beat_type: str
    voiceover_segment: str
    duration: float
    full_script: str
    highlight_start: int  # Character offset in full script
    highlight_end: int
