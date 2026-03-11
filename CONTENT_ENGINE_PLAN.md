# Content Engine: Portable Shot-List & Video Pipeline (v3)

## Executive Summary

Evolve the Stage 6 shot-list generator into a **self-contained, portable content engine** with:
- Interactive wizard UI (browser-based, works on desktop/mobile)
- Google Drive output with safety checks (DriveGuard)
- Preset-driven configuration (no hardcoded lists)
- Approval gates at script and voiceover stages
- Full CLI compatibility with `--wizard` mode

---

# A) Folder Layout

```
content_engine/
├── README.md
├── requirements.txt
├── config.yaml                     # Single config pointing to external resources
├── .env.example                    # API keys template
│
├── app/                            # Wizard UI (FastAPI + frontend)
│   ├── __init__.py
│   ├── main.py                     # FastAPI app entry
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py               # API endpoints
│   │   ├── websocket.py            # Real-time progress updates
│   │   └── schemas.py              # Pydantic models
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── wizard.js           # Frontend logic
│   └── templates/
│       ├── base.html
│       ├── wizard.html             # Main wizard UI
│       ├── script_preview.html
│       ├── shot_list_preview.html
│       └── final_output.html
│
├── cli/                            # CLI entry points
│   ├── __init__.py
│   ├── main.py                     # Unified CLI (replaces cli.py)
│   └── commands/
│       ├── generate.py
│       ├── wizard.py               # --wizard launcher
│       └── validate.py
│
├── pipeline/                       # Core pipeline (from existing generators/)
│   ├── __init__.py
│   ├── orchestrator.py             # Main pipeline coordinator
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── stage1_research.py      # Gemini + Grok
│   │   ├── stage2_draft.py         # ChatGPT
│   │   ├── stage3_hook.py          # Grok
│   │   ├── stage4_relevance.py     # Gemini
│   │   ├── stage5_finalize.py      # Claude
│   │   └── stage6_shotlist.py      # NEW: Beat parsing, shots, NanoBanana
│   ├── models/
│   │   ├── __init__.py
│   │   ├── run_config.py           # RunConfig dataclass
│   │   ├── script.py               # Script output model
│   │   ├── shot_list.py            # ShotListItem, Beat, etc.
│   │   └── timeline.py             # Timeline models
│   └── clients/
│       ├── __init__.py
│       ├── anthropic_client.py
│       ├── openai_client.py
│       ├── gemini_client.py
│       ├── grok_client.py
│       └── elevenlabs_client.py
│
├── presets/                        # All configuration presets (JSON)
│   ├── niches/
│   │   ├── motivation.json
│   │   ├── fun_facts.json
│   │   ├── finance.json
│   │   └── fitness.json
│   ├── styles/
│   │   ├── affirming.json
│   │   ├── aggressive_energy.json
│   │   ├── calm_minimal.json
│   │   ├── future_accountability.json
│   │   └── edgy_funny.json
│   ├── voices/
│   │   ├── deep_motivational.json
│   │   ├── energetic.json
│   │   ├── calm_reflective.json
│   │   └── text_only.json
│   ├── visuals/
│   │   ├── nanobanana_cinematic.json
│   │   ├── stock_only.json
│   │   └── hybrid.json
│   └── realism/
│       ├── standard.json
│       └── photorealistic.json
│
├── templates/                      # Output templates
│   ├── shot_list.md.jinja
│   ├── nanobanana_prompts.txt.jinja
│   └── stock_queries.txt.jinja
│
├── services/                       # Shared services
│   ├── __init__.py
│   ├── drive_guard.py              # G Drive detection/validation
│   ├── output_writer.py            # Structured output to G Drive
│   ├── preset_loader.py            # Load presets from /presets
│   ├── cache_manager.py            # Response caching
│   └── budget_tracker.py           # API call limits
│
├── cache/                          # Local cache (gitignored)
│   └── .gitkeep
│
├── logs/                           # Run logs (gitignored)
│   └── .gitkeep
│
└── tests/
    ├── test_drive_guard.py
    ├── test_pipeline.py
    └── test_presets.py
```

---

# B) DriveGuard Design

## Purpose
Ensure G Drive is mounted and writable BEFORE any expensive operations (API calls, ElevenLabs).

## Detection Logic

```python
# services/drive_guard.py

from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import subprocess
import os

class DriveStatus(Enum):
    MOUNTED = "mounted"
    NOT_MOUNTED = "not_mounted"
    READ_ONLY = "read_only"
    UNREACHABLE = "unreachable"

@dataclass
class DriveCheckResult:
    status: DriveStatus
    mount_path: Path | None
    can_write: bool
    error_message: str | None
    attempted_remount: bool

class DriveGuard:
    def __init__(self, config_path: Path = Path("config.yaml")):
        self.config = self._load_config(config_path)
        self.mount_name = self.config.get("gdrive_mount_name", "G Drive")
        self.mount_path = Path(self.config.get("gdrive_mount_path", "~/gdrive_mount")).expanduser()
        self.rclone_remote = self.config.get("rclone_remote", "gdrive:Social_Maker")

    def check(self, attempt_remount: bool = True) -> DriveCheckResult:
        """
        Check if G Drive is available and writable.

        Returns DriveCheckResult with status and details.
        """
        # Step 1: Check if mount point exists
        if not self.mount_path.exists():
            return DriveCheckResult(
                status=DriveStatus.NOT_MOUNTED,
                mount_path=None,
                can_write=False,
                error_message=f"Mount path {self.mount_path} does not exist",
                attempted_remount=False
            )

        # Step 2: Check if it's actually mounted (not empty dir)
        if not self._is_mounted():
            if attempt_remount:
                return self._try_remount()
            return DriveCheckResult(
                status=DriveStatus.NOT_MOUNTED,
                mount_path=self.mount_path,
                can_write=False,
                error_message="Directory exists but drive not mounted",
                attempted_remount=False
            )

        # Step 3: Check write permissions
        can_write = self._test_write()
        if not can_write:
            return DriveCheckResult(
                status=DriveStatus.READ_ONLY,
                mount_path=self.mount_path,
                can_write=False,
                error_message="Drive mounted but not writable",
                attempted_remount=False
            )

        return DriveCheckResult(
            status=DriveStatus.MOUNTED,
            mount_path=self.mount_path,
            can_write=True,
            error_message=None,
            attempted_remount=False
        )

    def _is_mounted(self) -> bool:
        """Check if path is a mount point with content."""
        # Method 1: Check if it's in /proc/mounts (Linux)
        try:
            with open("/proc/mounts") as f:
                mounts = f.read()
                if str(self.mount_path) in mounts:
                    return True
        except:
            pass

        # Method 2: Check if directory has content (rclone creates .marker files)
        try:
            contents = list(self.mount_path.iterdir())
            return len(contents) > 0
        except:
            return False

    def _test_write(self) -> bool:
        """Test write by creating and deleting a temp file."""
        test_file = self.mount_path / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            return True
        except:
            return False

    def _try_remount(self) -> DriveCheckResult:
        """Attempt to remount using rclone."""
        try:
            # Kill any existing mount
            subprocess.run(
                ["fusermount", "-uz", str(self.mount_path)],
                capture_output=True,
                timeout=5
            )

            # Remount
            subprocess.run(
                [
                    "rclone", "mount",
                    self.rclone_remote, str(self.mount_path),
                    "--daemon",
                    "--vfs-cache-mode", "writes"
                ],
                capture_output=True,
                timeout=10
            )

            # Wait and verify
            import time
            time.sleep(2)

            if self._is_mounted() and self._test_write():
                return DriveCheckResult(
                    status=DriveStatus.MOUNTED,
                    mount_path=self.mount_path,
                    can_write=True,
                    error_message=None,
                    attempted_remount=True
                )
        except Exception as e:
            pass

        return DriveCheckResult(
            status=DriveStatus.UNREACHABLE,
            mount_path=self.mount_path,
            can_write=False,
            error_message="Automatic remount failed. Please mount manually.",
            attempted_remount=True
        )

    def require_writable(self) -> Path:
        """
        Assert drive is writable or raise exception.
        Called before any expensive operations.
        """
        result = self.check()
        if not result.can_write:
            raise DriveNotAvailableError(result)
        return result.mount_path

class DriveNotAvailableError(Exception):
    def __init__(self, result: DriveCheckResult):
        self.result = result
        super().__init__(f"G Drive not available: {result.error_message}")
```

## Integration Points

| Where | What Happens |
|-------|--------------|
| CLI start | `DriveGuard().check()` → warn if not mounted |
| Wizard UI load | API call to `/api/drive/status` → show banner if unmounted |
| Before Stage 1 | `DriveGuard().require_writable()` → STOP if fails |
| Before ElevenLabs | `DriveGuard().require_writable()` → STOP if fails |
| Output write | Use `DriveGuard.mount_path` as base |

## UI/CLI Behavior

**CLI (unmounted):**
```
⚠️  G Drive not mounted at ~/gdrive_mount
    Run: rclone mount gdrive:Social_Maker ~/gdrive_mount --daemon --vfs-cache-mode writes
    Then re-run this command.
```

**Wizard UI (unmounted):**
- Red banner at top: "G Drive not connected"
- All "Generate" buttons disabled
- Link to manual mount instructions

---

# C) Tech Stack for Wizard UI

## Recommendation: FastAPI + HTMX + Tailwind CSS

**Why this stack:**
- **FastAPI**: Already Python-based (matches pipeline), async, easy API endpoints
- **HTMX**: No JavaScript framework needed, progressive enhancement, works on mobile
- **Tailwind CSS**: Responsive out of box, mobile-first
- **Jinja2 Templates**: Server-rendered, fast, no build step

**Alternatives considered:**
| Option | Pros | Cons |
|--------|------|------|
| Streamlit | Very easy | Heavy, not mobile-friendly, hard to customize |
| Gradio | AI-focused | Limited control, not easily customizable |
| React/Vue | Rich UI | Requires npm, build step, more complexity |
| **HTMX** | Simple, no JS build, mobile-ready | Slightly less dynamic |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser (Wizard UI)                │
│  ┌─────────────────────────────────────────────────┐ │
│  │  HTMX requests → FastAPI endpoints              │ │
│  │  WebSocket → Real-time progress updates         │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                   FastAPI Server                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ /api/*   │  │ /ws      │  │ Static + Templates│  │
│  │ endpoints│  │ websocket│  │ (Jinja2 + Tailwind│  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                   Pipeline Engine                    │
│  Stages 1-6 + DriveGuard + Cache + Budget Tracker   │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                   G Drive Output                     │
│  /motivation/affirming/2026-02-23/run-001/          │
└─────────────────────────────────────────────────────┘
```

## Running the Wizard

```bash
# Start wizard server
python -m cli.main --wizard

# Opens browser to http://localhost:8080
# Works on desktop, phone (same network), iPad
```

---

# D) Implementation Milestones

## Milestone 1: Project Structure & Presets (Day 1)
- [ ] Create `content_engine/` folder structure
- [ ] Move existing pipeline code into `pipeline/stages/`
- [ ] Create `config.yaml` with relative paths
- [ ] Create preset JSON files from existing style guides
- [ ] Implement `PresetLoader` service
- [ ] Test: Presets load correctly

## Milestone 2: DriveGuard & Output Writer (Day 2)
- [ ] Implement `DriveGuard` with mount detection
- [ ] Implement write test and remount logic
- [ ] Create `OutputWriter` for structured G Drive output
- [ ] Define output folder structure
- [ ] Test: DriveGuard detects mounted/unmounted states

## Milestone 3: Stage 6 Generator (Day 3-4)
- [ ] Implement `BeatParser` (script → beats)
- [ ] Implement `ShotListGenerator` (beats → shots with all fields)
- [ ] Implement NanoBanana prompt generator
- [ ] Implement stock query generator (tight/broad/negative)
- [ ] Implement overlay constraint enforcer
- [ ] Implement `CoherenceValidator`
- [ ] Implement `CacheManager` for responses
- [ ] Implement `BudgetTracker`
- [ ] Test: Full Stage 6 generates expected outputs

## Milestone 4: CLI Extension (Day 5)
- [ ] Create unified CLI in `cli/main.py`
- [ ] Add all flags: `--shot-list`, `--align-audio`, `--budget-mode`, `--max-calls`, `--max-regens`, `--wizard`, `--dry-run`
- [ ] Integrate approval gates (interactive prompts in CLI)
- [ ] Test: CLI generates full output to G Drive

## Milestone 5: Wizard UI - Core Screens (Day 6-7)
- [ ] FastAPI app structure
- [ ] Base template with Tailwind
- [ ] Screen 1: Settings (dropdowns from presets)
- [ ] Screen 2: Script preview with Approve/Regenerate/Edit
- [ ] Screen 3: Shot list/prompts preview
- [ ] Screen 4: Voiceover approval gate
- [ ] Screen 5: Final output with links
- [ ] WebSocket for progress updates
- [ ] Test: Full wizard flow on desktop

## Milestone 6: Mobile Optimization & Polish (Day 8)
- [ ] Responsive CSS for phone/iPad
- [ ] Touch-friendly buttons
- [ ] G Drive status banner
- [ ] Error states and loading indicators
- [ ] Test: Wizard works on mobile browser

## Milestone 7: Integration Testing (Day 9)
- [ ] End-to-end test: CLI → G Drive outputs
- [ ] End-to-end test: Wizard → G Drive outputs
- [ ] Budget/cache verification
- [ ] Coherence validation verification
- [ ] Documentation

---

# E) Data Contracts

## RunConfig (Input)

```python
# pipeline/models/run_config.py

@dataclass
class RunConfig:
    # Identifiers
    run_id: str                     # Auto-generated: "run-001"
    timestamp: str                  # ISO format

    # Presets (from /presets)
    niche: str                      # "motivation", "fun_facts"
    style: str                      # "affirming", "aggressive_energy"
    voice_preset: str               # "deep_motivational", "text_only"
    visual_mode: str                # "nanobanana", "stock", "both"
    realism_mode: str               # "standard", "photorealistic"

    # Budget
    budget_mode: bool = False
    max_calls: int = 10
    max_regens: int = 2

    # Features
    generate_shot_list: bool = True
    align_audio: bool = False
    dry_run: bool = False

    # Optional overrides
    topic: str | None = None
    custom_hook: str | None = None

    def to_json(self) -> str
    def to_dict(self) -> dict

    @classmethod
    def from_wizard(cls, form_data: dict) -> "RunConfig"

    @classmethod
    def from_cli(cls, args) -> "RunConfig"
```

## RunConfig JSON Example

```json
{
  "run_id": "run-001",
  "timestamp": "2026-02-23T14:30:00Z",
  "niche": "motivation",
  "style": "affirming",
  "voice_preset": "deep_motivational",
  "visual_mode": "both",
  "realism_mode": "standard",
  "budget_mode": false,
  "max_calls": 10,
  "max_regens": 2,
  "generate_shot_list": true,
  "align_audio": false,
  "dry_run": false,
  "topic": null,
  "custom_hook": null
}
```

## Output Contract (Guaranteed Files)

**Output folder:** `{gdrive_mount}/content_engine/{niche}/{style}/{date}/{run_id}/`

| File | Always Present | Description |
|------|----------------|-------------|
| `config.json` | Yes | RunConfig used for this run |
| `script.txt` | Yes | Plain text script (voiceover) |
| `script_meta.json` | Yes | Hook, body, keywords, hashtags, script_type |
| `shot_list.json` | If --shot-list | Full structured shot list |
| `shot_list.md` | If --shot-list | Human-readable shot list |
| `nanobanana_prompts.txt` | If visual_mode includes nanobanana | Copy-paste ready prompts |
| `stock_queries.txt` | If visual_mode includes stock | Search queries (tight/broad/negative) |
| `timeline.json` | If --shot-list | Timeline with layers |
| `voiceover.mp3` | If voice_preset != text_only AND not dry_run | ElevenLabs audio |
| `word_timing.json` | If voiceover generated | Word-level timing from ElevenLabs |
| `timeline_aligned.json` | If --align-audio AND voiceover exists | Timing adjusted to audio |
| `run_log.txt` | Yes | Timestamps, model calls, cache hits |
| `coherence_report.json` | If --shot-list | Match scores, flagged scenes |

## Output Structure Example

```
~/gdrive_mount/content_engine/
└── motivation/
    └── affirming/
        └── 2026-02-23/
            └── run-001/
                ├── config.json
                ├── script.txt
                ├── script_meta.json
                ├── shot_list.json
                ├── shot_list.md
                ├── nanobanana_prompts.txt
                ├── stock_queries.txt
                ├── timeline.json
                ├── voiceover.mp3
                ├── word_timing.json
                ├── timeline_aligned.json
                ├── run_log.txt
                └── coherence_report.json
```

---

# F) API Endpoints & UI Flow

## API Endpoints

```python
# app/api/routes.py

# === Presets ===
GET  /api/presets/niches          # List available niches
GET  /api/presets/styles          # List styles for selected niche
GET  /api/presets/voices          # List voice presets
GET  /api/presets/visuals         # List visual modes
GET  /api/presets/realism         # List realism modes

# === Drive ===
GET  /api/drive/status            # DriveGuard check result
POST /api/drive/remount           # Attempt remount

# === Pipeline ===
POST /api/pipeline/start          # Start pipeline with RunConfig
GET  /api/pipeline/status/{run_id}  # Get current status
POST /api/pipeline/approve/script/{run_id}  # Approve script, continue
POST /api/pipeline/regenerate/script/{run_id}  # Regenerate script
POST /api/pipeline/edit/script/{run_id}  # Submit edited script
POST /api/pipeline/approve/voiceover/{run_id}  # Approve voiceover settings
POST /api/pipeline/change-voice/{run_id}  # Change voice preset
POST /api/pipeline/rewrite-pacing/{run_id}  # Rewrite script for pacing
POST /api/pipeline/finalize/{run_id}  # Generate final outputs

# === Outputs ===
GET  /api/outputs/{run_id}        # List output files
GET  /api/outputs/{run_id}/open   # Get path/link to output folder
```

## WebSocket Events

```python
# app/api/websocket.py

# Server → Client events
{
  "event": "stage_start",
  "data": {"stage": 1, "name": "Research", "model": "gemini+grok"}
}

{
  "event": "stage_complete",
  "data": {"stage": 1, "duration_ms": 3200, "cache_hit": false}
}

{
  "event": "approval_required",
  "data": {"gate": "script", "preview": {...}}
}

{
  "event": "error",
  "data": {"message": "G Drive not mounted", "recoverable": true}
}

{
  "event": "complete",
  "data": {"run_id": "run-001", "output_path": "/path/to/output"}
}
```

## UI Screen Flow

```
┌─────────────────────────────────────────────────────────────┐
│  SCREEN 1: SETTINGS                                         │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ Niche ▼         │  │ Style ▼         │                  │
│  │ [Motivation   ] │  │ [Affirming    ] │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ Voice ▼         │  │ Visual Mode ▼   │                  │
│  │ [Deep Motiv.  ] │  │ [Both         ] │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  ┌─────────────────┐  ☐ Budget Mode  ☐ Dry Run            │
│  │ Realism ▼       │                                       │
│  │ [Standard     ] │  Max Calls: [10]                      │
│  └─────────────────┘                                        │
│                                                             │
│  [ Topic (optional): ______________________________ ]       │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │              🚀 START GENERATION                  │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
│  ⚠️ G Drive Status: ✅ Connected                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Click Start)
┌─────────────────────────────────────────────────────────────┐
│  SCREEN 2: SCRIPT APPROVAL GATE                             │
│                                                             │
│  ═══════════════════════════════════════════════════════   │
│  PROGRESS: ████████░░░░░░░░░░░░░░░░░░░░  Stage 5/6         │
│  ═══════════════════════════════════════════════════════   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  HOOK (highlighted)                                  │   │
│  │  ┌─────────────────────────────────────────────────┐ │   │
│  │  │ "You did good today. Really good."              │ │   │
│  │  └─────────────────────────────────────────────────┘ │   │
│  │                                                       │   │
│  │  FULL SCRIPT                                         │   │
│  │  ┌─────────────────────────────────────────────────┐ │   │
│  │  │ You did good today. Really good.                │ │   │
│  │  │ You woke up when you didn't want to.            │ │   │
│  │  │ You kept going when everything felt heavy...     │ │   │
│  │  │ ...                                              │ │   │
│  │  └─────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────┐ │
│  │ ✅ Approve │ │ 🔄 Regen   │ │ ✏️ Edit    │ │ ❌ Cancel│ │
│  └────────────┘ └────────────┘ └────────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Click Approve)
┌─────────────────────────────────────────────────────────────┐
│  SCREEN 3: SHOT LIST & PROMPTS PREVIEW                      │
│                                                             │
│  TABS: [ Shot List | NanoBanana | Stock Queries | Timeline ]│
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  BEAT 1: HOOK (0:00 - 0:03)                         │   │
│  │  ────────────────────────────────────────────────── │   │
│  │  VO: "You did good today. Really good."             │   │
│  │  Visual: Person by window at sunset, soft light...  │   │
│  │  Overlay: "You did good" (scale_pop, center)        │   │
│  │  Match Score: ████████░░ 0.92                       │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  BEAT 2: TENSION (0:03 - 0:08)                      │   │
│  │  ...                                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Coherence Score: 0.88  |  Flagged: 0 scenes               │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │              ➡️ CONTINUE TO VOICEOVER             │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Click Continue)
┌─────────────────────────────────────────────────────────────┐
│  SCREEN 4: VOICEOVER APPROVAL GATE                          │
│                                                             │
│  Current Voice Preset: Deep Motivational                    │
│  Estimated Duration: 45s                                    │
│  ElevenLabs Cost: ~500 characters                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Script Preview (for pacing review)                  │   │
│  │  "You did good today. [pause] Really good..."        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ ✅ Generate  │ │ 🔄 Change    │ │ ✏️ Rewrite for    │  │
│  │   Voiceover  │ │   Voice      │ │    Pacing          │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
│                                                             │
│  ☐ Enable Audio Alignment (--align-audio)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Click Generate)
┌─────────────────────────────────────────────────────────────┐
│  SCREEN 5: FINAL OUTPUT                                     │
│                                                             │
│  ✅ GENERATION COMPLETE                                     │
│                                                             │
│  Run ID: run-001                                            │
│  Duration: 2m 34s                                           │
│  API Calls: 6 (2 cache hits)                                │
│                                                             │
│  OUTPUT FILES:                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📄 config.json                                       │   │
│  │ 📄 script.txt                                        │   │
│  │ 📄 shot_list.json                                    │   │
│  │ 📄 shot_list.md                                      │   │
│  │ 📄 nanobanana_prompts.txt                            │   │
│  │ 📄 stock_queries.txt                                 │   │
│  │ 🎵 voiceover.mp3                                     │   │
│  │ 📄 timeline_aligned.json                             │   │
│  │ 📄 run_log.txt                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌────────────────────┐  ┌────────────────────┐            │
│  │ 📂 Open in Finder  │  │ 🔗 Open in G Drive │            │
│  └────────────────────┘  └────────────────────┘            │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │              🔄 START NEW RUN                     │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

# G) Budget & Caching Rules

## Cache Keys

```python
# services/cache_manager.py

def generate_cache_key(stage: str, inputs: dict) -> str:
    """
    Generate deterministic cache key.

    Keys based on:
    - Stage name
    - Input content hash (topic, niche, style)
    - Preset versions (hash of preset file content)
    """
    content = json.dumps(inputs, sort_keys=True)
    return f"{stage}:{hashlib.sha256(content.encode()).hexdigest()[:16]}"
```

## Cache Rules

| Stage | Cached? | TTL | Invalidated By |
|-------|---------|-----|----------------|
| Stage 1 (Research) | Yes | 4 hours | Same niche/topic |
| Stage 2 (Draft) | Yes | 24 hours | Same topic + niche + style |
| Stage 3 (Hook) | Yes | 24 hours | Same draft hash |
| Stage 4 (Relevance) | Yes | 4 hours | Same draft + topic |
| Stage 5 (Finalize) | Yes | 24 hours | Same inputs |
| Stage 6 (Shot List) | Yes | 24 hours | Same script hash + visual_mode |
| NanoBanana prompts | Yes | 7 days | Same scene text + style |
| Coherence scores | No | - | Always recalculate |

## Budget Tracking

```python
# services/budget_tracker.py

@dataclass
class BudgetState:
    max_calls: int
    calls_used: int
    cache_hits: int
    remaining: int

    def can_call(self) -> bool:
        return self.remaining > 0

    def record_call(self, cache_hit: bool = False):
        if cache_hit:
            self.cache_hits += 1
        else:
            self.calls_used += 1
            self.remaining -= 1

    def to_log(self) -> str:
        return f"API: {self.calls_used}/{self.max_calls} | Cache: {self.cache_hits}"
```

## Budget Mode Behavior

| Mode | max_calls | Behavior |
|------|-----------|----------|
| Normal | 10 | Standard operation |
| Budget | 3 | Batch scenes in single calls, aggressive caching |
| Unlimited | 50 | For development/testing |

**Budget mode optimizations:**
- Batch all 6 scenes into 1 Claude call for shot list
- Skip coherence regeneration
- Use cached research if <4 hours old
- Combine NanoBanana prompts into single generation

---

# H) Stage 6 Details (Beat-Based Shot List)

## Beat Types

```python
class BeatType(Enum):
    HOOK = "hook"           # 0-3s: Attention grab
    TENSION = "tension"     # Build stakes/conflict
    SHIFT = "shift"         # Pivot/turn moment
    CLIMB = "climb"         # Escalation/intensity
    RESOLUTION = "resolution"  # Payoff/answer
    CTA = "cta"             # Call to action (optional)
```

## Beat Allocation by Script Type

| Script Type | Beats Used |
|-------------|------------|
| affirming | hook → tension → resolution → CTA |
| aggressive_energy | hook → tension → shift → climb → resolution |
| future_accountability | hook → tension → climb → resolution → CTA |
| calm_minimal | hook → resolution (minimal beats) |

## ShotListItem (Full Structure)

```python
@dataclass
class ShotListItem:
    scene_number: int
    beat_type: BeatType

    # Timing (adjustable)
    start_time: float
    end_time: float
    duration: float
    pace: str                       # "slow", "medium", "fast"
    padding_before: float
    padding_after: float

    # Content
    voiceover_segment: str
    mood_tone: str

    # Stock Search (dual queries)
    search_tight: List[str]         # Specific: "man window sunset golden hour"
    search_broad: List[str]         # General: "contemplative person, warm light"
    negative_search: List[str]      # Exclude: "business", "office", "thumbs up"

    # Visual Direction
    visual_description: str
    lighting_notes: str
    suggested_camera: str
    b_roll_ideas: List[str]

    # NanoBanana Prompts
    nano_prompt: str                # Positive prompt
    nano_negative: str              # Negative prompt
    nano_style_tags: List[str]      # ["cinematic", "4k", "soft lighting"]

    # Overlay (constrained)
    overlay: Optional[OverlayConfig]

    # Coherence
    match_score: float              # 0-1, set during validation
    needs_regeneration: bool
```

## Overlay Constraints

```python
@dataclass
class OverlayConfig:
    text: str                       # Max 6 words
    display_start: float            # Relative to scene start
    display_duration: float
    animation: str                  # "scale_pop", "fade_in", etc.
    position: str                   # "center", "lower_third", "upper_safe"
    safe_area: bool = True          # Must be True

# Enforced constraints:
# - Max 6 words per overlay
# - Max 4-6 overlays per video
# - Position must be in safe area (10% margins)
```

## Timing System

### Option A: Adjustable Pace + Padding (Default)

```python
PACE_CONFIG = {
    "slow": {"wps": 2.0, "padding": 0.5},   # Calm, reflective
    "medium": {"wps": 2.8, "padding": 0.3}, # Standard
    "fast": {"wps": 3.5, "padding": 0.2},   # High energy
}

BEAT_PACE_MAP = {
    BeatType.HOOK: "fast",
    BeatType.TENSION: "medium",
    BeatType.SHIFT: "slow",
    BeatType.CLIMB: "fast",
    BeatType.RESOLUTION: "slow",
    BeatType.CTA: "medium",
}
```

### Option B: ElevenLabs Audio Alignment (--align-audio)

```python
def align_to_audio(shots: List[ShotListItem], word_timing: List[dict]) -> List[ShotListItem]:
    """
    Second pass: Adjust shot timings to match actual ElevenLabs audio.
    """
    # Map voiceover segments to word timing
    # Adjust start/end times to actual audio boundaries
    # Preserve padding ratios
```

## Coherence Validation

```python
def validate_coherence(shots: List[ShotListItem], global_style: str) -> List[ShotListItem]:
    """
    Check each scene matches global style and beat expectations.
    """
    for shot in shots:
        shot.match_score = calculate_match(shot, global_style)
        shot.needs_regeneration = shot.match_score < 0.7
    return shots

# Match Score Criteria:
# - Visual matches beat mood: 0.3
# - Search terms specific enough: 0.2
# - NanoBanana prompt coherent: 0.2
# - Overlay within constraints: 0.15
# - Timing reasonable for beat: 0.15
```

---

# Verification Plan

## Unit Tests
- [ ] `test_drive_guard.py`: Mount detection, write test, remount logic
- [ ] `test_preset_loader.py`: All presets load, schema validation
- [ ] `test_stage6.py`: Beat parsing, overlay constraints, coherence scoring
- [ ] `test_cache.py`: Cache hit/miss, TTL expiration
- [ ] `test_budget.py`: Call counting, budget enforcement

## Integration Tests
- [ ] CLI: `python -m cli.main generate motivation --shot-list --dry-run`
- [ ] CLI: `python -m cli.main generate motivation --shot-list --budget-mode --max-calls 3`
- [ ] Wizard: Start → Settings → Generate → Approve → Voiceover → Finalize
- [ ] Wizard on mobile: Same flow, verify responsive

## End-to-End
- [ ] Full run produces all expected files in G Drive
- [ ] Second run with same settings hits cache
- [ ] DriveGuard blocks if G Drive unmounted
- [ ] Approval gates pause and wait for user input

---

# Key Files Reference

| File | Responsibility |
|------|----------------|
| `config.yaml` | External paths (G Drive mount) |
| `services/drive_guard.py` | Mount detection, write test, remount |
| `services/output_writer.py` | Structured output to G Drive |
| `services/preset_loader.py` | Load JSON presets |
| `services/cache_manager.py` | Response caching |
| `services/budget_tracker.py` | API call limits |
| `pipeline/stages/stage6_shotlist.py` | Beat parsing, shot generation |
| `pipeline/models/run_config.py` | RunConfig dataclass |
| `app/main.py` | FastAPI entry |
| `app/api/routes.py` | All API endpoints |
| `cli/main.py` | Unified CLI |
