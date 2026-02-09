/**
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
        "Select the premiere_package folder\n\n" +
        "This folder should contain:\n" +
        "- manifest.json\n" +
        "- voiceover.mp3\n" +
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
        alertUser("Error reading manifest.json:\n" + e.message);
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
        "Rebuild Complete!\n\n" +
        "Sequence: " + seqName + "\n" +
        "Duration: " + m.total_duration.toFixed(1) + " seconds\n" +
        "Scenes: " + m.scenes.length + "\n\n" +
        "Manual steps needed:\n" +
        "1. Verify sequence is " + m.resolution.width + "x" + m.resolution.height + "\n" +
        "2. Add Cross Dissolve transitions between scenes\n" +
        "3. Adjust music volume to " + (m.music ? (m.music.volume * 100).toFixed(0) + "%" : "N/A") + "\n" +
        "4. Add fade in/out to music\n" +
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
