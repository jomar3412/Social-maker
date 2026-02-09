"""
Premiere Pro Export Package Generator

Creates an export package that can be imported into Premiere Pro on a different machine.
The package includes:
- manifest.json: All timing, scene, and asset metadata
- rebuild_edit.jsx: ExtendScript to recreate the sequence
- voiceover.mp3: Audio file
- subtitles.ass: Subtitle file
- assets/: Copies of all backgrounds and music used
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from config.settings import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, MUSIC_VOLUME


# Crossfade duration must match video_gen.py
CROSSFADE_DURATION = 0.5
VOICEOVER_DELAY = 1.0  # 1 second delay before voiceover starts


def create_premiere_package(
    output_dir: Path,
    scenes: list,
    backgrounds_used: list,
    music_file: Path | None,
    voiceover_path: Path,
    subtitle_path: Path | None,
    word_timing: list,
    content: dict,
    total_duration: float,
) -> Path:
    """
    Create a Premiere Pro import package with all assets and metadata.

    Args:
        output_dir: Directory where video was generated (contains voiceover, subtitles)
        scenes: List of scene dicts with start, end, words
        backgrounds_used: List of Path objects for each scene's background
        music_file: Path to the background music file (or None)
        voiceover_path: Path to the voiceover audio
        subtitle_path: Path to the ASS subtitle file (or None)
        word_timing: List of word timing dicts
        content: Content dict with quote/fact, author, caption, etc.
        total_duration: Total video duration in seconds

    Returns:
        Path to the created premiere_package directory
    """
    output_dir = Path(output_dir)
    package_dir = output_dir / "premiere_package"
    assets_dir = package_dir / "assets"

    # Clean up any existing package
    if package_dir.exists():
        shutil.rmtree(package_dir)

    package_dir.mkdir(parents=True)
    assets_dir.mkdir()

    print("Creating Premiere Pro package...")

    # Copy voiceover
    voiceover_dest = package_dir / "voiceover.mp3"
    shutil.copy2(voiceover_path, voiceover_dest)
    print(f"  Copied voiceover: {voiceover_dest.name}")

    # Copy subtitles if they exist
    subtitle_dest = None
    if subtitle_path and Path(subtitle_path).exists():
        subtitle_dest = package_dir / "subtitles.ass"
        shutil.copy2(subtitle_path, subtitle_dest)
        print(f"  Copied subtitles: {subtitle_dest.name}")

    # Copy music if it exists
    music_dest = None
    if music_file and Path(music_file).exists():
        music_dest = assets_dir / Path(music_file).name
        shutil.copy2(music_file, music_dest)
        print(f"  Copied music: {music_dest.name}")

    # Copy backgrounds and build scene metadata
    scene_data = []
    for i, (scene, bg_path) in enumerate(zip(scenes, backgrounds_used)):
        bg_path = Path(bg_path)
        is_video = bg_path.suffix.lower() in {".mp4", ".mov", ".webm", ".avi", ".mkv"}

        # Copy background to assets folder
        bg_dest = assets_dir / bg_path.name
        if not bg_dest.exists():  # Avoid duplicate copies
            shutil.copy2(bg_path, bg_dest)
            print(f"  Copied background: {bg_dest.name}")

        # Determine zoom effect for images
        effect = "none"
        if not is_video:
            zoom_effects = ["zoom_in", "pan_left_right", "pan_right_left", "zoom_out"]
            effect = zoom_effects[i % len(zoom_effects)]

        # Build scene entry
        scene_entry = {
            "index": i,
            "start": scene["start"],
            "end": scene["end"],
            "background": f"assets/{bg_path.name}",
            "background_type": "video" if is_video else "image",
            "effect": effect,
        }

        # Add crossfade transition (except for first scene)
        if i > 0:
            scene_entry["transition_in"] = {
                "type": "crossfade",
                "duration": CROSSFADE_DURATION,
            }

        scene_data.append(scene_entry)

    # Extract keywords from content or word timing
    keywords = content.get("keywords", [])
    if not keywords and word_timing:
        # Try to extract from content
        text = content.get("voiceover", content.get("quote", content.get("fact", "")))
        keywords = _extract_keywords(text)

    # Build manifest
    manifest = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "project_name": output_dir.name,
        "resolution": {
            "width": VIDEO_WIDTH,
            "height": VIDEO_HEIGHT,
        },
        "fps": VIDEO_FPS,
        "total_duration": total_duration,
        "voiceover": {
            "file": "voiceover.mp3",
            "delay": VOICEOVER_DELAY,
            "duration": total_duration - (VOICEOVER_DELAY + 1),  # Minus intro/outro padding
        },
        "music": None,
        "scenes": scene_data,
        "subtitles": None,
        "word_timing": word_timing,
        "content": {
            "type": content.get("content_type", "motivation"),
            "quote": content.get("quote"),
            "fact": content.get("fact"),
            "author": content.get("author"),
            "caption": content.get("caption"),
            "hook": content.get("hook"),
        },
    }

    # Add music metadata if present
    if music_dest:
        manifest["music"] = {
            "file": f"assets/{music_dest.name}",
            "volume": MUSIC_VOLUME,
            "fade_in": 1.0,
            "fade_out": 1.0,
        }

    # Add subtitle metadata if present
    if subtitle_dest:
        manifest["subtitles"] = {
            "file": "subtitles.ass",
            "keywords": keywords,
        }

    # Write manifest
    manifest_path = package_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Created manifest: {manifest_path.name}")

    # Copy the rebuild script
    rebuild_script = _generate_rebuild_script()
    script_path = package_dir / "rebuild_edit.jsx"
    with open(script_path, "w") as f:
        f.write(rebuild_script)
    print(f"  Created rebuild script: {script_path.name}")

    # Create a README for the package
    readme = _generate_package_readme()
    readme_path = package_dir / "README.txt"
    with open(readme_path, "w") as f:
        f.write(readme)

    print(f"\nPremiere package created: {package_dir}")
    print(f"  {len(scene_data)} scenes, {len(word_timing)} words")

    return package_dir


def _extract_keywords(text: str, max_keywords: int = 5) -> list:
    """Extract potential keywords from text (simple heuristic)."""
    # Common stopwords to skip
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "to", "of", "in", "for", "on", "with",
        "at", "by", "from", "as", "into", "through", "during", "before", "after",
        "above", "below", "between", "under", "again", "further", "then", "once",
        "here", "there", "when", "where", "why", "how", "all", "each", "few",
        "more", "most", "other", "some", "such", "no", "nor", "not", "only",
        "own", "same", "so", "than", "too", "very", "just", "and", "but", "if",
        "or", "because", "until", "while", "this", "that", "these", "those",
        "i", "you", "he", "she", "it", "we", "they", "what", "which", "who",
        "whom", "your", "his", "her", "its", "our", "their", "my",
    }

    # Clean and split text
    import re
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

    # Filter and get unique meaningful words
    keywords = []
    seen = set()
    for word in words:
        if word not in stopwords and word not in seen and len(word) > 3:
            keywords.append(word)
            seen.add(word)
        if len(keywords) >= max_keywords:
            break

    return keywords


def _generate_rebuild_script() -> str:
    """Generate the ExtendScript for rebuilding the edit in Premiere Pro."""
    return '''/**
 * Social Media Content Factory - Rebuild Edit Script
 * Version: 1.0
 * Compatible with: Premiere Pro 2024-2026 (v24.0+)
 *
 * This script recreates a video edit from the pipeline's export package.
 *
 * HOW TO RUN:
 * 1. Open Premiere Pro
 * 2. Create a new project or open an existing one
 * 3. Go to File > Scripts > Run Script File...
 * 4. Select this file (rebuild_edit.jsx)
 * 5. Select the premiere_package folder when prompted
 */

// ============================================================
// CONFIGURATION
// ============================================================

var CONFIG = {
    // Will be populated from manifest.json
    manifest: null,
    packagePath: "",

    // Track settings
    videoTrack: 1,
    voiceTrack: 1,
    musicTrack: 2,

    // Ticks per second for Premiere timeline
    ticksPerSecond: 254016000000
};

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

function log(message) {
    $.writeln("[RebuildEdit] " + message);
}

function alertUser(message) {
    alert(message, "Rebuild Edit");
}

function secondsToTicks(seconds) {
    return Math.round(seconds * CONFIG.ticksPerSecond);
}

function readJSON(filePath) {
    var file = new File(filePath);
    if (!file.exists) {
        throw new Error("File not found: " + filePath);
    }
    file.open("r");
    var content = file.read();
    file.close();

    // Parse JSON (ExtendScript doesn't have native JSON)
    return eval("(" + content + ")");
}

function getSequencePreset() {
    /**
     * Returns a sequence preset path for vertical video
     * This varies by Premiere version, so we try common locations
     */
    var presetPaths = [
        // Windows paths
        "C:/Program Files/Adobe/Adobe Premiere Pro 2026/Settings/SequencePresets/AVCHD/1080p/AVCHD 1080p30.sqpreset",
        "C:/Program Files/Adobe/Adobe Premiere Pro 2025/Settings/SequencePresets/AVCHD/1080p/AVCHD 1080p30.sqpreset",
        "C:/Program Files/Adobe/Adobe Premiere Pro 2024/Settings/SequencePresets/AVCHD/1080p/AVCHD 1080p30.sqpreset",
        // Mac paths
        "/Applications/Adobe Premiere Pro 2026/Adobe Premiere Pro 2026.app/Contents/Settings/SequencePresets/AVCHD/1080p/AVCHD 1080p30.sqpreset",
        "/Applications/Adobe Premiere Pro 2025/Adobe Premiere Pro 2025.app/Contents/Settings/SequencePresets/AVCHD/1080p/AVCHD 1080p30.sqpreset",
        "/Applications/Adobe Premiere Pro 2024/Adobe Premiere Pro 2024.app/Contents/Settings/SequencePresets/AVCHD/1080p/AVCHD 1080p30.sqpreset"
    ];

    for (var i = 0; i < presetPaths.length; i++) {
        var presetFile = new File(presetPaths[i]);
        if (presetFile.exists) {
            return presetPaths[i];
        }
    }

    return null;
}

// ============================================================
// IMPORT FUNCTIONS
// ============================================================

function importFile(project, filePath, targetBin) {
    /**
     * Import a single file into the project
     */
    try {
        var file = new File(filePath);
        if (!file.exists) {
            log("File not found: " + filePath);
            return null;
        }

        var importArray = [file.fsName];
        var suppressUI = true;

        if (project.importFiles(importArray, suppressUI, targetBin, false)) {
            // Find the imported item
            for (var i = targetBin.children.numItems - 1; i >= 0; i--) {
                var item = targetBin.children[i];
                if (item.name === file.name) {
                    log("Imported: " + file.name);
                    return item;
                }
            }
        }
    } catch (e) {
        log("Error importing " + filePath + ": " + e.message);
    }
    return null;
}

function createBin(project, name) {
    /**
     * Create a bin in the project root
     */
    return project.rootItem.createBin(name);
}

// ============================================================
// SEQUENCE BUILDING
// ============================================================

function createSequence(project, name, width, height, fps) {
    /**
     * Create a new sequence with specified settings
     */
    // Try to use a preset
    var presetPath = getSequencePreset();

    if (presetPath) {
        // Create from preset, then modify settings
        project.createNewSequenceFromPreset(name, presetPath);
    } else {
        // Fallback: create empty sequence
        // Note: This may require manual adjustment
        log("No preset found, creating default sequence");
        project.createNewSequence(name);
    }

    // Get the newly created sequence
    var sequence = project.activeSequence;

    if (sequence) {
        // Modify frame size for vertical video
        // Note: Some properties may not be settable via script
        log("Created sequence: " + name);
        log("Please manually verify settings: " + width + "x" + height + " @ " + fps + "fps");
    }

    return sequence;
}

function addClipToTrack(sequence, projectItem, trackIndex, startTime, endTime, isVideo) {
    /**
     * Add a clip to the timeline
     */
    var startTicks = secondsToTicks(startTime);
    var endTicks = secondsToTicks(endTime);

    if (isVideo) {
        var videoTrack = sequence.videoTracks[trackIndex];
        if (videoTrack) {
            videoTrack.insertClip(projectItem, startTicks);
            log("Added video clip at " + startTime.toFixed(2) + "s");
            return true;
        }
    } else {
        var audioTrack = sequence.audioTracks[trackIndex];
        if (audioTrack) {
            audioTrack.insertClip(projectItem, startTicks);
            log("Added audio clip at " + startTime.toFixed(2) + "s");
            return true;
        }
    }

    return false;
}

function addCrossfadeTransition(sequence, trackIndex, time, duration) {
    /**
     * Add a crossfade transition between clips
     * Note: Transition application via script is limited
     */
    log("Transition needed at " + time.toFixed(2) + "s (apply manually: Cross Dissolve)");
}

// ============================================================
// MAIN REBUILD FUNCTION
// ============================================================

function rebuildEdit() {
    var project = app.project;

    if (!project) {
        alertUser("Please create or open a project first!");
        return;
    }

    // Step 1: Select the package folder
    alertUser(
        "Select the premiere_package folder\\n\\n" +
        "This folder should contain:\\n" +
        "- manifest.json\\n" +
        "- voiceover.mp3\\n" +
        "- assets/ folder"
    );

    var packageFolder = Folder.selectDialog("Select the premiere_package folder");

    if (!packageFolder) {
        alertUser("No folder selected. Cancelled.");
        return;
    }

    CONFIG.packagePath = packageFolder.fsName;

    // Step 2: Read manifest
    var manifestPath = CONFIG.packagePath + "/manifest.json";

    try {
        CONFIG.manifest = readJSON(manifestPath);
        log("Loaded manifest: " + CONFIG.manifest.project_name);
    } catch (e) {
        alertUser("Error reading manifest.json:\\n" + e.message);
        return;
    }

    var m = CONFIG.manifest;

    // Step 3: Create import bin
    var importBin = createBin(project, m.project_name + "_Assets");
    log("Created bin: " + importBin.name);

    // Step 4: Import all assets
    var importedAssets = {};

    // Import voiceover
    var voPath = CONFIG.packagePath + "/" + m.voiceover.file;
    importedAssets.voiceover = importFile(project, voPath, importBin);

    // Import music
    if (m.music && m.music.file) {
        var musicPath = CONFIG.packagePath + "/" + m.music.file;
        importedAssets.music = importFile(project, musicPath, importBin);
    }

    // Import backgrounds
    importedAssets.backgrounds = [];
    for (var i = 0; i < m.scenes.length; i++) {
        var scene = m.scenes[i];
        var bgPath = CONFIG.packagePath + "/" + scene.background;
        var bgItem = importFile(project, bgPath, importBin);
        importedAssets.backgrounds.push(bgItem);
    }

    // Step 5: Create sequence
    var seqName = m.project_name + "_Edit";
    var sequence = createSequence(project, seqName, m.resolution.width, m.resolution.height, m.fps);

    if (!sequence) {
        alertUser("Failed to create sequence. Please create one manually.");
        return;
    }

    // Step 6: Place clips on timeline
    log("Building timeline...");

    // Add background clips
    for (var i = 0; i < m.scenes.length; i++) {
        var scene = m.scenes[i];
        var bgItem = importedAssets.backgrounds[i];

        if (bgItem) {
            addClipToTrack(sequence, bgItem, 0, scene.start, scene.end, true);

            // Note transition points
            if (scene.transition_in) {
                addCrossfadeTransition(
                    sequence,
                    0,
                    scene.start,
                    scene.transition_in.duration
                );
            }
        }
    }

    // Add voiceover (with delay)
    if (importedAssets.voiceover) {
        addClipToTrack(
            sequence,
            importedAssets.voiceover,
            0,  // Audio track 1
            m.voiceover.delay,
            m.voiceover.delay + m.voiceover.duration,
            false
        );
    }

    // Add music (if present)
    if (importedAssets.music) {
        addClipToTrack(
            sequence,
            importedAssets.music,
            1,  // Audio track 2
            0,
            m.total_duration,
            false
        );
        log("Music added. Manually adjust volume to " + (m.music.volume * 100).toFixed(0) + "%");
    }

    // Step 7: Summary
    var summary =
        "Rebuild Complete!\\n\\n" +
        "Sequence: " + seqName + "\\n" +
        "Duration: " + m.total_duration.toFixed(1) + " seconds\\n" +
        "Scenes: " + m.scenes.length + "\\n\\n" +
        "Manual steps needed:\\n" +
        "1. Verify sequence is " + m.resolution.width + "x" + m.resolution.height + "\\n" +
        "2. Add Cross Dissolve transitions between scenes\\n" +
        "3. Adjust music volume to " + (m.music ? (m.music.volume * 100).toFixed(0) + "%" : "N/A") + "\\n" +
        "4. Add fade in/out to music\\n" +
        "5. Import subtitles if needed (subtitles.ass)";

    alertUser(summary);
    log("Rebuild complete!");
}

// ============================================================
// RUN SCRIPT
// ============================================================

try {
    rebuildEdit();
} catch (e) {
    alertUser("Error: " + e.message);
    log("Error: " + e.message);
}
'''


def _generate_package_readme() -> str:
    """Generate README for the export package."""
    return """PREMIERE PRO EXPORT PACKAGE
===========================

This package was created by the Social Media Content Pipeline.
Use it to continue editing the video in Adobe Premiere Pro.

CONTENTS
--------
- manifest.json    : All timing and metadata
- rebuild_edit.jsx : Script to recreate the sequence
- voiceover.mp3    : Voiceover audio
- subtitles.ass    : Subtitle file (if generated)
- assets/          : Background videos/images and music

HOW TO USE
----------
1. Open Adobe Premiere Pro
2. Create a new project (or open existing)
3. File > Scripts > Run Script File...
4. Select "rebuild_edit.jsx" from this folder
5. When prompted, select THIS folder (premiere_package)
6. The script will import assets and create a sequence

AFTER RUNNING THE SCRIPT
------------------------
The script creates the basic timeline structure.
You may need to manually:
- Add Cross Dissolve transitions between scenes
- Adjust music volume (see manifest.json for target level)
- Add audio fade in/out effects
- Import subtitles.ass if you want captions
- Verify the sequence is 1080x1920 (vertical)

MANIFEST REFERENCE
------------------
The manifest.json file contains all timing data:
- scenes[].start/end : Scene cut points (in seconds)
- voiceover.delay    : Delay before voiceover starts
- music.volume       : Target music volume (0.0-1.0)
- word_timing        : Per-word timestamps for subtitles

For subtitle import, you can use a third-party tool or
manually create text layers based on word_timing.

SUPPORT
-------
Generated by: Social Media Content Factory
https://github.com/yourusername/socal_maker
"""


if __name__ == "__main__":
    # Test the module
    print("Premiere Export Module")
    print("=" * 40)
    print("This module creates export packages for Premiere Pro.")
    print("Use it via the pipeline or import create_premiere_package().")
