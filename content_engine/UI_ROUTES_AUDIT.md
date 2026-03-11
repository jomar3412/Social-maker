# Content Engine — UI Routes & Templates Audit
**Date:** 2026-03-11
**Audited files:** `app/main.py`, `app/api/routes.py`, `app/templates/*.html`

---

## Page Routes Overview

| Route | Template | Description | Status |
|---|---|---|---|
| `GET /` | — | Redirects to `/wizard` | ✅ Functional |
| `GET /health` | — | JSON health check for proxy/tunnel monitoring | ✅ Functional |
| `GET /wizard` | `wizard.html` | Preset selector + generate form (Step 1 of workflow) | ✅ Functional |
| `POST /wizard/start` | partials | Submits config, starts background run, HX-Redirect to status page | ✅ Functional |
| `GET /runs/{id}/status` | `run_status.html` | Live-polling progress page during generation (28 lines, thin) | ✅ Functional |
| `GET /runs/{id}` | `run_overview.html` | Full run summary — hook, artifacts list, quick feedback | ✅ Functional |
| `GET /runs/{id}/artifacts` | `run_artifacts.html` | Scene-by-scene prompts with lock/version/regen UI (1573 lines, most complex page) | ✅ Functional |
| `GET /runs/{id}/shot-list` | `shot_list_view.html` | Shot list viewer with JSON and Markdown tabs | ✅ Functional |
| `GET /runs/{id}/voice` | `voice.html` | Voice generation — select preset, generate, approve | ⚠️ Has gaps (see below) |
| `GET /wizard/approve/{id}` | `script_approval.html` | Script preview + approve/reject/regenerate gate | ✅ Functional |
| `GET /wizard/feedback/{id}` | `feedback.html` | Post-publish metrics entry (views, likes, CTR, etc.) | ✅ Functional |
| `GET /wizard/pending` | `pending.html` | Lists all runs awaiting script approval | ✅ Functional |
| `GET /queue` | `queue.html` | In-progress runs not yet posted | ✅ Functional |
| `GET /reviews` | `reviews.html` | Posted runs and feedback history | ✅ Functional |
| `GET /reviews/import` | `reviews_import.html` | Upload analytics screenshot for OCR parsing | ✅ Functional |
| `GET /reviews/import/{draft_id}` | `reviews_import_draft.html` | Verify OCR-extracted metrics before saving | ✅ Functional |
| `GET /library` | `library.html` | All runs with filter tabs (pending / approved / reviewed) | ✅ Functional |
| `GET /wizard/presets` | `presets.html` | List all presets — niches, styles, voices, visuals | ✅ Functional |
| `GET /wizard/presets/{type}/{name}` | `preset_stats.html` | Preset usage stats and tuning memo editor | ✅ Functional |
| `GET /wizard/presets/{cat}/{name}/edit` | `preset_editor.html` | Raw JSON preset editor with backup history | ✅ Functional |
| `GET /settings` | `settings.html` | Storage config, cleanup controls | ✅ Functional |
| `GET /knowledge` | `knowledge_base.html` | Knowledge base documents and learning summary | ✅ Functional |

---

## API Routes (Backend Only — No Templates)

Over 70 JSON API endpoints under `/api/...` handled in `routes.py`. Key groups:

| Group | Endpoints | Notes |
|---|---|---|
| Drive | `/api/drive/status` | Check Google Drive mount |
| Presets | `/api/presets/{type}` | List/read/edit preset JSON files |
| Pipeline | `/api/pipeline/start`, `/approve/script/{id}`, `/regenerate/script/{id}` | Core workflow triggers |
| Runs | `/api/runs/{id}/status-fragment`, `/notes`, `/feedback`, `/voice/*`, `/scenes`, `/scene-context/{key}` | Run data and artifact retrieval |
| Prompts | `/api/runs/{id}/prompts/*` | Sequential generation, lock/unlock, version history |
| Entities | `/api/runs/{id}/entities/*` | Continuity entity management per scene |
| Reviews | `/api/reviews/import-screenshot`, `/drafts/*` | OCR screenshot import workflow |
| Knowledge | `/api/knowledge/status`, `/documents`, `/learning`, `/compare` | Knowledge base read endpoints |
| Storage | `/api/storage/stats`, `/cleanup`, `/cleanup-rejected-images` | Storage management |
| Concurrency | `/api/concurrency/status`, `/provider/info` | System status |

---

## Gaps and Unfinished Areas

### 1. Voice Page — Script Never Loads ⚠️
**File:** `main.py` line 324
**Severity:** High — functional breakage

The voice page route reads the script from `script.json`:
```python
script_path = output_dir / "script.json"
```
But the pipeline writes `script.txt` and `script_meta.json` — not `script.json`. The artifacts and script approval pages handle this correctly by checking both formats. The voice page doesn't, so `script_text` and `hook_text` are always empty.

**Fix needed:** Update `main.py` voice route to check `script.txt` first, fall back to `script.json`.

---

### 2. Voice Page — No Result Partial Template ⚠️
**File:** `voice.html` line 161
**Severity:** Medium — HTMX response renders into empty div with no structure

After clicking "Generate Voice," the HTMX response targets `<div id="voice-result">` but there is no `partials/voice_result.html` template. The endpoint at `/api/runs/{id}/voice/generate` returns a response but has nowhere structured to render it.

**Fix needed:** Create `partials/voice_result.html` to show generation success, duration, playback, and timestamps.

---

### 3. New Pipeline Stage Not Handled in UI ⚠️
**File:** `run_status.html`, `run_overview.html`
**Severity:** Low — display only

The new `AWAITING_VIDEO_CLIPS` stage (added in the NanoBanana/pause-point fix) is not listed in the UI's stage display mapping. Runs paused at this stage will show as an unknown or raw enum string instead of a human-readable label.

**Fix needed:** Add `awaiting_video_clips` → "Waiting for Video Clips" to the stage display name mapping in the templates and/or `RunStore.STAGE_INFO`.

---

### 4. index.html — Never Seen ℹ️
**File:** `index.html` (25 lines)
**Severity:** None — informational only

`GET /` immediately redirects to `/wizard`, so `index.html` is never rendered in the normal flow. It contains a basic splash screen with links to `/wizard` and `/wizard/pending`. Not broken, just unreachable.

---

## False Positives (Not Gaps)

The following files had grep hits for words like "placeholder" or "stub" but are fully functional:

| File | Reason |
|---|---|
| `feedback.html` | All hits are `placeholder=` attributes on input fields |
| `run_artifacts.html` | All 11 hits are `placeholder=` on inputs and a CSS comment |
| `preset_stats.html` | `placeholder=` on tuning memo textarea — functional |
| `reviews_import.html` | `placeholder=` on URL input — functional |
| `reviews_import_draft.html` | `placeholder=` on form fields and a fallback image path — functional |
| `wizard.html` | `<!-- Result placeholder -->` comment labels the HTMX target div — partials exist and work |
| `run_overview.html` | `placeholder=` on notes textarea — functional |
| `script_approval.html` | `placeholder=` on notes field — functional |

---

## Partial Templates

Located in `app/templates/partials/`:

| File | Used By | Description |
|---|---|---|
| `approve_success.html` | `script_approval.html` | HTMX swap after script approved |
| `generation_error.html` | `wizard.html` | Error state after failed pipeline start |
| `generation_success.html` | `wizard.html` | Success state after pipeline starts |
| `regenerating.html` | `script_approval.html` | Loading state during script regeneration |
| `run_status_fragment.html` | `run_status.html` | Polled fragment for live progress updates |

**Missing partial:** `voice_result.html` — needed for the voice generation result display (see Gap #2).

---

## Summary

- **21 page routes** total, **20 fully functional**, **1 with gaps** (voice page)
- **3 real issues** to fix: voice script loading, voice result partial, new stage UI label
- **No routes** exist in the router without a corresponding template
- **No templates** exist that are unreachable from the router (except `index.html` which is bypassed by redirect)
