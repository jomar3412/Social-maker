# Content Engine — Full Technical Reference

> Last updated: 2026-03-11
> Purpose: Complete reference for AI agents or developers working on the Content Engine.

## Overview

The Content Engine is a faceless short-form video content factory for platforms like YouTube Shorts, TikTok, and Instagram Reels. It automates the full workflow: script generation → visual prompt creation → voice generation → output to Google Drive.

**Stack:** Python, FastAPI, Jinja2, HTMX, SQLite, ElevenLabs, Claude CLI, Gemini CLI, rclone (Google Drive)

---

## Directory Structure

```
content_engine/
├── app/                    # FastAPI web application
│   ├── main.py             # App creation, page routes, template rendering
│   ├── api/
│   │   ├── routes.py       # All REST API endpoints
│   │   └── schemas.py      # Pydantic request/response models
│   └── templates/          # Jinja2 HTML templates (HTMX-powered UI)
│       ├── base.html
│       ├── wizard.html          # Screen 1: Preset selection
│       ├── script_approval.html # Screen 2: Script review
│       ├── run_artifacts.html   # Screen 3: Visual prompts
│       ├── voice.html           # Voice generation
│       ├── queue.html           # In-progress runs
│       ├── reviews.html         # Analytics & feedback
│       ├── library.html         # All runs archive
│       └── settings.html        # Storage config
│
├── pipeline/
│   ├── orchestrator.py          # Main pipeline coordinator
│   ├── prompt_spec.py           # Structured prompt dataclasses
│   ├── nanobanana_generator.py  # Visual prompt generation system
│   └── models/run_config.py     # RunConfig dataclass
│
├── providers/
│   ├── base.py                  # Abstract ContentProvider interface
│   ├── cli_provider.py          # Calls claude/gemini CLI via subprocess
│   └── stub_provider.py         # Mock responses for testing
│
├── services/
│   ├── run_store.py             # SQLite persistence (runs.db)
│   ├── drive_guard.py           # Google Drive mount validation
│   ├── output_writer.py         # Structured file output to Drive
│   ├── preset_loader.py         # Load/cache preset JSON files
│   ├── voice_service.py         # ElevenLabs TTS integration
│   ├── storage_manager.py       # Storage quota & auto-cleanup
│   ├── background_runner.py     # Background thread execution
│   ├── concurrency.py           # Thread-safe run limits
│   └── ocr_importer.py          # Analytics screenshot extraction
│
├── presets/                     # JSON configuration templates
│   ├── niches/                  # motivation.json, fun_facts.json
│   ├── styles/                  # affirming.json, edgy_funny.json, etc.
│   ├── voices/                  # deep_motivational.json, etc.
│   ├── visuals/                 # nanobanana.json, stock.json, hybrid.json
│   └── realism/                 # standard.json, photorealistic.json
│
├── knowledge/                   # Knowledge base system
├── cli/                         # Command-line interface
├── tests/                       # Unit & integration tests
├── config.yaml                  # Global configuration
├── cache/                       # Generation cache
└── logs/                        # Runtime logs
```

---

## Database Schema (runs.db — SQLite)

```sql
-- Tracks all pipeline runs and their current state
CREATE TABLE runs (
    run_id        TEXT PRIMARY KEY,
    stage         TEXT NOT NULL,        -- RunStage enum (see below)
    config_json   TEXT NOT NULL,        -- Full RunConfig as JSON
    output_path   TEXT,                 -- Absolute path to Google Drive output folder
    created_at    TEXT,
    updated_at    TEXT,
    error_message TEXT,
    display_title TEXT,                 -- Human-readable title (from script hook)
    short_title   TEXT
);

-- User quality ratings and publishing data
CREATE TABLE feedback (
    run_id           TEXT PRIMARY KEY,
    script_quality   INTEGER,           -- 1-5
    hook_strength    INTEGER,           -- 1-5
    visual_match     INTEGER,           -- 1-5
    tags             TEXT DEFAULT '[]', -- JSON array
    publish_status   TEXT,              -- draft, published
    platform         TEXT,
    posted_url       TEXT,
    post_date        TEXT,
    views            INTEGER,
    engagement       INTEGER
);

-- All versions of NanoBanana prompts and stock queries per scene
CREATE TABLE prompt_versions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT,
    artifact_type TEXT,                -- 'nanobanana' or 'stock_query'
    item_key      TEXT,                -- 'scene_1', 'scene_2', etc.
    version       INTEGER,             -- Increments on each regeneration
    prompt_text   TEXT,
    status        TEXT,                -- active, pending, locked, outdated
    image_path    TEXT,                -- Optional reference image
    created_at    TEXT,
    created_by    TEXT,
    notes         TEXT
);

-- Named visual entities for cross-scene consistency
CREATE TABLE entities (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                 TEXT,
    name                   TEXT,       -- e.g. "Young Professional"
    entity_type            TEXT,       -- character, prop, location, style
    description            TEXT,       -- Injected into prompts
    reference_image_path   TEXT,
    created_at             TEXT,
    created_from_scene_key TEXT
);

-- Links an entity to the scenes it should appear in
CREATE TABLE entity_links (
    entity_id  INTEGER,
    run_id     TEXT,
    scene_key  TEXT
);

-- Analytics screenshot import drafts (before user verification)
CREATE TABLE review_import_drafts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT,
    platform       TEXT,
    extracted_json TEXT,               -- OCR-extracted metrics
    status         TEXT,               -- pending, verified, rejected
    created_at     TEXT
);

-- Aggregate stats and memos per preset combination
CREATE TABLE preset_tuning (
    preset_type        TEXT,
    preset_name        TEXT,
    memo_text          TEXT,
    avg_script_quality REAL,
    avg_hook_strength  REAL,
    avg_visual_match   REAL,
    total_runs         INTEGER,
    PRIMARY KEY (preset_type, preset_name)
);
```

### RunStage Enum (in order)

```
PENDING → RESEARCH → DRAFT → HOOK_REVIEW → RELEVANCE → FINALIZE
→ AWAITING_SCRIPT_APPROVAL → SCRIPT_APPROVED
→ GENERATING_SHOT_LIST → GENERATING_VISUALS → POST_PROCESSING
→ COMPLETE | FAILED | CANCELLED
```

---

## Full Pipeline Flow

### Phase 1: Script Generation (Stages 1–5)

```
User fills wizard form (niche, style, voice, visual_mode, topic)
    ↓
POST /api/pipeline/start
    ↓
Create RunConfig → Start background thread
    ↓
DriveGuard.check() — validates Google Drive is mounted
    ↓
OutputWriter.create_run_directory()
    → ~/gdrive_mount/content_engine/{niche}/{style}/{date}/{run_id}/
    ↓
Stage 1: RESEARCH
    → Provider generates research notes for niche/topic
Stage 2: DRAFT
    → Provider writes initial script (hook + body + CTA)
Stage 3: HOOK_REVIEW
    → Provider sharpens the hook
Stage 4: RELEVANCE
    → Provider scores relevance, suggests updates
Stage 5: FINALIZE
    → Provider assembles final script with loop-friendly ending if set
    ↓
Write: script.txt, script.json, script_meta.json
RunStore.update_stage(AWAITING_SCRIPT_APPROVAL)
```

### Phase 2: Script Approval

```
User views script at /wizard/approve/{run_id}
    ├── Regenerate (up to 3x) → Reruns stages 1-5 with feedback
    └── Approve → POST /api/pipeline/approve/script/{run_id}
            ↓
        Stage 6: GENERATING_SHOT_LIST
            → NanoBananaPromptGenerator builds shot list
            → 6 scenes, each with beat_type + voiceover_segment
            → Write: shot_list.json, shot_list.md
        Stage 7: GENERATING_VISUALS
            → Scene 1 prompt: ACTIVE
            → Scenes 2-6: PENDING (sequential unlock)
            → Write: nanobanana_prompts.txt, stock_queries.txt
        Stage 8: POST_PROCESSING
            → Timeline alignment, coherence check
            ↓
        RunStore.update_stage(COMPLETE)
```

### Phase 3: Sequential Prompt Management

```
User at /runs/{run_id}/artifacts
    ├── Scene 1: ACTIVE — can Copy, Regenerate, Lock
    ├── Scene 2: PENDING — locked until scene 1 is locked
    ├── Scene 3: PENDING — locked until scene 2 is locked
    └── ...
    ↓
User locks scene 1 → Scene 2 becomes generatable
User regenerates scene 2 → New version created (v2 ACTIVE, v1 OUTDATED)
User locks scene 2 → Scene 3 becomes generatable
    ↓
All scenes locked → Stage: READY_TO_POST
```

### Phase 4: Voice Generation

```
User at /runs/{run_id}/voice
    ↓
POST /api/voice/{run_id}/generate
    ↓
VoiceService.generate(script_text, voice_preset)
    ├── ELEVENLABS_API_KEY present?
    │   ├── YES: Real ElevenLabs TTS → voiceover_v1.mp3
    │   └── NO:  Stub JSON with estimated timestamps
    ↓
Split script into scenes, calculate per-scene timestamps
Write: voiceover_v1.mp3, word_timing.json, scene_timestamps
```

### Phase 5: Publishing & Analytics

```
All scenes locked → Mark READY_TO_POST
    ↓
User uploads to YouTube/TikTok/Instagram manually
POST /api/runs/{run_id}/post (platform, url)
    ↓
Run moves to Reviews page
    ↓
User uploads analytics screenshot
    ↓
OCRImporter → Claude extracts metrics (views, likes, engagement)
    ↓
User verifies → Saved to feedback table
    ↓
preset_tuning stats updated (avg ratings per niche/style combo)
```

---

## API Endpoints (Complete)

### Pipeline
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/pipeline/start` | Generate script (stages 1-5) |
| POST | `/api/pipeline/approve/script/{run_id}` | Approve script, start artifacts |
| POST | `/api/pipeline/regenerate/script/{run_id}` | Regenerate with feedback |
| GET | `/api/pipeline/status/{run_id}` | Get current stage |
| GET | `/api/runs/{run_id}/status-fragment` | HTMX polling fragment |

### Runs
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/runs` | List all runs |
| GET | `/api/runs/pending` | Runs awaiting approval |
| GET | `/api/runs/recent` | Recent runs |
| POST | `/api/runs/{run_id}/notes` | Save notes |
| POST | `/api/runs/{run_id}/feedback` | Save quality ratings |
| POST | `/api/runs/{run_id}/quick-feedback` | Quick rating |
| POST | `/api/runs/{run_id}/post` | Mark as posted |

### Prompts & Artifacts
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/runs/{run_id}/scenes` | All scenes with script highlights |
| GET | `/api/runs/{run_id}/scene-context/{scene_key}` | Single scene context |
| POST | `/api/runs/{run_id}/prompts/generate-next/{item_key}` | Generate pending scene |
| POST | `/api/runs/{run_id}/prompts/{prompt_id}/lock` | Lock scene |
| POST | `/api/runs/{run_id}/prompts/{prompt_id}/unlock` | Unlock scene |
| POST | `/api/runs/{run_id}/regenerate-prompt` | Regenerate with notes |
| POST | `/api/runs/{run_id}/sync-prompts` | Import from shot_list.json |

### Entities (Continuity)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/runs/{run_id}/entities` | List entities |
| POST | `/api/runs/{run_id}/entities` | Create entity |
| POST | `/api/runs/{run_id}/entities/from-prompt/{prompt_id}` | Create from prompt |
| DELETE | `/api/runs/{run_id}/entities/{entity_id}` | Delete entity |
| POST | `/api/runs/{run_id}/entities/export` | Export to files |

### Voice
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/voice/{run_id}/generate` | Generate voiceover |
| POST | `/api/voice/{run_id}/settings` | Update voice settings |

### Presets
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/presets/{category}/{name}` | Get preset |
| POST | `/api/presets/{category}/{name}` | Update preset (auto-backup) |
| GET | `/api/presets/{category}/{name}/history` | Backup history |
| POST | `/api/presets/{category}/{name}/restore` | Restore backup |
| GET | `/api/presets/{type}/{name}/stats` | Performance stats |

### Storage & Drive
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/drive/status` | Check Drive mount |
| GET | `/api/storage/status` | Storage usage |
| POST | `/api/storage/cleanup` | Manual cleanup |
| POST | `/api/storage/config` | Update policy |

### Analytics
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/reviews/import` | Upload screenshot |
| GET | `/api/reviews/import/drafts/{id}` | View extracted metrics |
| POST | `/api/reviews/import/drafts/{id}/save` | Save verified metrics |

---

## UI Pages

| Route | Template | Purpose |
|-------|----------|---------|
| `/wizard` | wizard.html | Preset selection form |
| `/runs/{id}/status` | (polling) | Live generation status |
| `/wizard/approve/{id}` | script_approval.html | Review & approve script |
| `/runs/{id}/artifacts` | run_artifacts.html | Manage visual prompts |
| `/runs/{id}/voice` | voice.html | Voice generation |
| `/queue` | queue.html | In-progress runs |
| `/reviews` | reviews.html | Posted runs + analytics |
| `/library` | library.html | All runs archive |
| `/wizard/presets` | presets list | Browse all presets |
| `/wizard/presets/{cat}/{name}/edit` | preset editor | Edit preset JSON |
| `/settings` | settings.html | Storage management |
| `/knowledge` | knowledge_base.html | Knowledge docs |

---

## NanoBanana Visual Prompt Generator

This is the most sophisticated component. It generates detailed (90–180 word) prompts for AI video/image generation tools.

### Visual Strategy System

```python
class VisualStrategy(Enum):
    PEOPLE      = "people"       # Human figures
    ENVIRONMENT = "environment"  # Abstract/metaphor, NO people
    AUTO        = "auto"         # Choose by niche

# Niche defaults:
motivation → ENVIRONMENT  (abstract landscapes, symbols)
stoicism   → ENVIRONMENT
fun_facts  → ENVIRONMENT
fitness    → PEOPLE
beauty     → PEOPLE
```

### Beat Types & Their Visual Profiles

Each of the 6 scenes in a video maps to a beat type:

| Beat | Energy | Shot Types | Lighting | Environment Subjects |
|------|--------|------------|----------|---------------------|
| HOOK | High | Medium close, Close-up | Dramatic, Rim | Flame, lightning bolt, hourglass |
| TENSION | Medium | Medium, Wide | Low-key, Dramatic | Chains, storm clouds, thorns |
| SHIFT | Medium | Medium, Wide | Natural soft, High-key | Dawn breaking, door opening, butterfly |
| CLIMB | High | Medium, Wide | High-key, Rim | Staircase, phoenix, mountain path |
| RESOLUTION | Medium | Close-up, Medium | High-key, Natural | Sunset, zen garden, open book |
| CTA | High | Medium, Medium close | High-key, Rim | Open door, rising sun, subscribe bell |

### Prompt Structure (ScenePromptSpec)

```python
@dataclass
class ScenePromptSpec:
    camera:        CameraSpec          # shot_type, angle, lens_mm, movement, dof
    subject:       SubjectSpec         # person or environment description
    environment:   EnvironmentSpec     # location, time_of_day, atmosphere
    lighting:      LightingSpec        # style, key_light, rim, shadows, mood
    color_style:   ColorStyleSpec      # palette, contrast, film_grain, grading
    continuity:    ContinuitySpec      # entity references, prior scene refs
    negatives:     NegativeConstraints # what to exclude
    output_format: OutputFormatSpec    # 9:16, 1080x1920, 24fps
```

### No-People Mode (Environment Strategy)

When niche is `motivation`, `stoicism`, `fun_facts`, or similar:
- Subject becomes abstract: e.g. *"ancient key floating in beam of light, bathed in warm golden light, evoking hope and triumph"*
- Negative constraints include: `no people, no human figures, no faces, no hands, no body parts, no silhouettes, no crowds`
- All 6 beat types have 6 curated environment_subjects to choose from

---

## Providers System

### Provider Selection (`config.yaml`)
```yaml
provider:
  type: "cli"          # "stub" or "cli"
  cli_model: "claude"  # "claude" or "gemini"
  timeout_seconds: 120
```

### CLIProvider
- Calls `claude -p "{prompt}"` or `gemini "{prompt}"` via subprocess
- No API key needed — uses installed CLI tools (Claude Code login, Gemini login)
- Uses temp files for large prompts to avoid shell escaping issues

### StubProvider
- Returns realistic mock responses instantly
- Used for: dry-run mode, testing, demos without CLI available
- Simulates all 5 script stages with configurable delay

---

## Services

### RunStore
Single source of truth for all run state. All pipeline operations read/write through here. Provides methods for: CRUD on runs, prompt versioning, feedback, entity management, preset stats.

### DriveGuard
Before any file write, validates Google Drive is mounted:
1. Check `/proc/mounts` for rclone remote
2. Fallback: `os.path.ismount()`
3. Fallback: marker file detection

If unmounted: raises `DriveNotAvailableError` with the exact rclone mount command to run.

### OutputWriter
Creates the run directory structure and writes all output files to Google Drive:
```
~/gdrive_mount/content_engine/{niche}/{style}/{YYYY-MM-DD}/{run_id}/
  config.json, script.txt, script.json, shot_list.json,
  nanobanana_prompts.txt, stock_queries.txt, voiceover.mp3,
  run_log.txt, coherence_report.json
```

### VoiceService
- **With ElevenLabs key**: Real TTS → MP3 with per-scene timestamps
- **Without key**: Stub JSON with estimated timestamps (word_count ÷ 150 WPM)
- Default voice: Rachel (ID: `21m00Tcm4TlvDq8ikWAM`), stability 0.5, model: `eleven_multilingual_v2`

### ConcurrencyManager
Thread-safe limits:
- Max 2 simultaneous pipeline runs
- Max 3 script regenerations per run
- Raises `RunLimitExceeded` or `RegenerationLimitExceeded`

### StorageManager
Auto-cleanup when Google Drive usage exceeds threshold:
- Default max: 50GB, cleanup at 90%, target 70%
- Policy `assets_only`: deletes videos/images, keeps metadata/logs
- Auto-deletes rejected images and intermediate video files

---

## Preset System

Presets are JSON files that configure the AI's behavior:

### Niche Preset (e.g. `motivation.json`)
```json
{
  "name": "motivation",
  "voice": { "tone": "direct-personal" },
  "hooks": { "types": {...}, "avoid": [...] },
  "vocabulary": { "power_words": [...], "forbidden": [...] },
  "structure": { "max_sentence_words": 15, "target_duration": 45 },
  "visual_style": { "footage_types": [...] },
  "hashtags": { "primary": [...] },
  "cta_templates": [...]
}
```

### Style Preset (e.g. `edgy_funny.json`)
```json
{
  "display_name": "Edgy & Funny",
  "energy": "high",
  "description": "Dark humor meets motivation"
}
```

Presets can be edited via the UI at `/wizard/presets/{category}/{name}/edit`.
Every edit creates an automatic backup in `presets/{category}/_history/`.

---

## Active API Keys & Services

| Service | Method | Cost |
|---------|--------|------|
| Claude | `claude -p` CLI (Claude Code login) | Free |
| Gemini | `gemini` CLI (Google login) | Free |
| ElevenLabs | API key (`ELEVENLABS_API_KEY` in `.env`) | Free tier (10K chars/mo) |
| OpenAI | Not active (on back burner) | — |
| Grok (xAI) | Not active (on back burner) | — |

---

## Architecture Summary

```
Browser (HTMX + Tailwind)
    ↕ REST API (FastAPI) — runs on port 8081
        ↕
    PipelineOrchestrator
        ├── DriveGuard          (is Drive mounted?)
        ├── ContentProvider     (CLI: claude/gemini, or Stub)
        ├── NanoBananaGenerator (visual prompts per beat type)
        ├── VoiceService        (ElevenLabs TTS)
        ├── OutputWriter        → Google Drive (~gdrive_mount/)
        └── RunStore            → SQLite (content_engine/data/runs.db)

Google Drive output structure:
    ~/gdrive_mount/content_engine/{niche}/{style}/{YYYY-MM-DD}/{run_id}/
        ├── config.json
        ├── script.txt
        ├── shot_list.json
        ├── nanobanana_prompts.txt
        ├── stock_queries.txt
        └── voiceover.mp3
```

---

## Starting the App

```bash
# From /home/markhuerta/Project/socal_maker/
source venv/bin/activate
uvicorn content_engine.app.main:app --host 0.0.0.0 --port 8081

# Access via:
# Local:     http://localhost:8081/wizard
# Tailscale: https://srv1102408.tail8ff0e.ts.net/wizard
```
