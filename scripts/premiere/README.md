# Premiere Pro Scripts

Two scripts for Adobe Premiere Pro integration:
1. **setup_project.jsx** - Initial project setup with bins and asset import
2. **rebuild_edit.jsx** - Recreate an edit from the pipeline's export package

---

## 1. Setup Project Script (setup_project.jsx)

Automatically organizes your project with bins and imports your Envato assets.

## How to Run

1. Open **Premiere Pro 2026** (v26.0.0)
2. Create a new project or open an existing one
3. Go to **File > Scripts > Run Script File...**
4. Navigate to `scripts/premiere/setup_project.jsx`
5. Click **Open**
6. Follow the prompts

## What It Does

### Creates This Bin Structure:

```
Project
├── 01_FOOTAGE
│   ├── Motivation
│   │   ├── Success_Hustle     (businessman, laptop, money, luxury)
│   │   ├── Struggle_Growth    (workout, running, climbing, gym)
│   │   ├── Philosophy         (thinking, silhouette, statue, books)
│   │   └── Nature_Power       (storm, ocean, lion, forest, fire)
│   ├── Facts
│   │   ├── Space              (earth, stars, planet, astronaut)
│   │   ├── Science            (laboratory, microscope, dna, brain)
│   │   ├── Nature_Animals     (underwater, insects, birds, volcano)
│   │   └── Human_History      (crowd, ruins, pyramid, ancient)
│   └── Universal              (backgrounds, abstract, gradients)
├── 02_OVERLAYS
│   ├── Dust_Grain
│   ├── Light_Leaks
│   ├── Particles
│   └── Glitch_VHS
├── 03_TRANSITIONS
├── 04_MUSIC
├── 05_SFX
├── 06_GRAPHICS
│   ├── Lower_Thirds
│   ├── Text_Templates
│   └── Icons
├── 07_EXPORTS
└── 08_SEQUENCES
    ├── Templates
    ├── Work_In_Progress
    └── Final
```

### Auto-Imports Your Assets

The script scans your assets folder and automatically:
- Detects file types (video, audio, image)
- Matches filenames to appropriate bins using keywords
- Places overlays in overlay bins, music in music bins, etc.

## Sequence Settings for Shorts

For YouTube Shorts / TikTok / Reels:

| Setting | Value |
|---------|-------|
| Resolution | 1080 x 1920 |
| Aspect Ratio | 9:16 (vertical) |
| Frame Rate | 30 fps |
| Max Duration | 59 seconds |

**Quick Setup:**
1. File > New > Sequence
2. Choose: Digital SLR > 1080p > DSLR 1080p30
3. Sequence > Sequence Settings
4. Change Frame Size to **1080 horizontal, 1920 vertical**

## File Naming Tips

For best auto-organization, name your files with keywords:

| Type | Example Names |
|------|---------------|
| Motivation | `businessman_walking.mp4`, `gym_workout_01.mp4` |
| Facts | `space_earth_orbit.mp4`, `microscope_cells.mp4` |
| Overlays | `dust_overlay_4k.mp4`, `light_leak_warm.mp4` |
| Transitions | `zoom_transition_fast.mp4` |
| SFX | `whoosh_fast.wav`, `hit_impact_01.wav` |
| Music | `ambient_motivation.mp3` |

## Troubleshooting

**Script won't run:**
- Make sure you have a project open
- Try: Edit > Preferences > Scripting > Enable "Allow Scripts to Write Files"

**Files not importing:**
- Check that files are in supported formats (.mp4, .mov, .mp3, .wav, etc.)
- Ensure the assets folder path is correct

**Wrong bin assignments:**
- Rename files with clearer keywords
- Manually drag clips to correct bins after import

---

## 2. Rebuild Edit Script (rebuild_edit.jsx)

Recreates a video edit from the pipeline's export package. Use this to continue editing on a different machine (e.g., your MacBook).

### How to Run

1. Run the pipeline with `--dry-run` to generate content
2. A `premiere_package/` folder is created in the output directory
3. Sync to your Mac via Google Drive
4. Open **Premiere Pro** on your Mac
5. Create a new project
6. Go to **File > Scripts > Run Script File...**
7. Select `rebuild_edit.jsx` from the package folder
8. When prompted, select the `premiere_package` folder
9. The script imports assets and creates a sequence

### What It Creates

```
Premiere Project
├── [project_name]_Assets/       (bin with imported files)
│   ├── voiceover.mp3
│   ├── ambient_motivation.mp3
│   ├── businessman_walking.mp4
│   └── ...
└── [project_name]_Edit          (sequence with timeline)
    ├── V1: Background clips at correct times
    ├── A1: Voiceover with 1s delay
    └── A2: Background music (adjust volume manually)
```

### Manual Steps After Running

The script creates the basic structure. You'll need to:

1. **Verify sequence settings** - Should be 1080x1920 @ 30fps
2. **Add transitions** - Apply "Cross Dissolve" between scene cuts
3. **Adjust music volume** - Set to level specified in manifest (usually 15%)
4. **Add audio fades** - Fade in/out on music track
5. **Import subtitles** - Optional: import `subtitles.ass` using a caption plugin

### Package Contents

```
premiere_package/
├── manifest.json          # All timing and metadata
├── rebuild_edit.jsx       # This script (also available here)
├── voiceover.mp3          # Voiceover audio
├── subtitles.ass          # Subtitle file (if generated)
├── README.txt             # Quick reference
└── assets/                # All backgrounds and music used
    ├── businessman_walking.mp4
    ├── mountain_sunrise.jpg
    └── ambient_motivation.mp3
```

### Manifest Reference

The `manifest.json` contains all edit data:

```json
{
  "version": "1.0",
  "project_name": "motivation_20260207_143000",
  "resolution": {"width": 1080, "height": 1920},
  "fps": 30,
  "total_duration": 47.5,
  "voiceover": {
    "file": "voiceover.mp3",
    "delay": 1.0,
    "duration": 45.5
  },
  "music": {
    "file": "assets/ambient_motivation.mp3",
    "volume": 0.15
  },
  "scenes": [
    {"index": 0, "start": 0.0, "end": 12.5, "background": "assets/..."},
    {"index": 1, "start": 12.0, "end": 25.0, "transition_in": {...}}
  ],
  "word_timing": [...]
}
```

---

## Workflow: Server to Mac

```
Hostinger Server                    MacBook
─────────────────                   ────────
python pipeline.py --dry-run
        ↓
Video generated
        ↓
premiere_package/ created
        ↓
Google Drive syncs  ─────────────→  Drive folder updates
                                          ↓
                                    Open Premiere Pro
                                          ↓
                                    Run rebuild_edit.jsx
                                          ↓
                                    Edit and polish
                                          ↓
                                    Export final video
```
