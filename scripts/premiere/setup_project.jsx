/**
 * Social Media Content Factory - Premiere Pro Setup Script
 * Version: 1.0
 * Compatible with: Premiere Pro 2024-2026 (v24.0+)
 *
 * This script creates an organized project structure and imports your assets.
 *
 * HOW TO RUN:
 * 1. Open Premiere Pro
 * 2. Create a new project (or open existing)
 * 3. Go to File > Scripts > Run Script File...
 * 4. Select this file (setup_project.jsx)
 * 5. Follow the prompts
 */

// ============================================================
// CONFIGURATION - Edit these paths to match your setup
// ============================================================

var CONFIG = {
    // Base path to your assets folder
    // Windows: "C:/Users/YourName/Project/socal_maker/assets"
    // Mac: "/Users/YourName/Project/socal_maker/assets"
    assetsBasePath: "",  // Will be set via dialog

    // Bin structure to create
    bins: {
        "01_FOOTAGE": {
            "Motivation": {
                "Success_Hustle": ["businessman", "laptop", "money", "luxury", "city"],
                "Struggle_Growth": ["workout", "running", "climbing", "gym", "boxing"],
                "Philosophy": ["thinking", "silhouette", "statue", "books", "candle"],
                "Nature_Power": ["storm", "ocean", "lion", "forest", "fire"]
            },
            "Facts": {
                "Space": ["earth", "stars", "planet", "astronaut", "rocket"],
                "Science": ["laboratory", "microscope", "dna", "brain", "robot"],
                "Nature_Animals": ["underwater", "insects", "birds", "volcano", "aurora"],
                "Human_History": ["crowd", "ruins", "pyramid", "ancient", "eye"]
            },
            "Universal": ["background", "abstract", "gradient", "texture", "bokeh"]
        },
        "02_OVERLAYS": {
            "Dust_Grain": ["dust", "grain", "scratch", "film"],
            "Light_Leaks": ["light", "leak", "flare", "glow"],
            "Particles": ["particle", "float", "sparkle"],
            "Glitch_VHS": ["glitch", "vhs", "retro", "distort"]
        },
        "03_TRANSITIONS": ["transition", "zoom", "blur", "ink", "wipe"],
        "04_MUSIC": ["music", "audio", "beat", "ambient"],
        "05_SFX": ["whoosh", "hit", "impact", "riser", "swoosh"],
        "06_GRAPHICS": {
            "Lower_Thirds": [],
            "Text_Templates": [],
            "Icons": []
        },
        "07_EXPORTS": [],
        "08_SEQUENCES": {
            "Templates": [],
            "Work_In_Progress": [],
            "Final": []
        }
    },

    // Color labels for organization
    // 0=None, 1=Red, 2=Orange, 3=Yellow, 4=Green, 5=Cyan, 6=Blue, 7=Purple, 8=Pink
    colorLabels: {
        "Motivation": 4,      // Green
        "Facts": 6,           // Blue
        "Universal": 3,       // Yellow
        "Overlays": 7,        // Purple
        "Transitions": 2,     // Orange
        "Music": 5,           // Cyan
        "SFX": 1              // Red
    },

    // Supported file extensions
    videoExtensions: [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"],
    audioExtensions: [".mp3", ".wav", ".aac", ".m4a", ".ogg"],
    imageExtensions: [".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".psd"]
};

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

function log(message) {
    $.writeln("[SocialMaker] " + message);
}

function alert_user(message) {
    alert(message, "Social Media Content Factory");
}

function getBinByPath(project, path) {
    /**
     * Get or create a bin by path (e.g., "01_FOOTAGE/Motivation/Success_Hustle")
     */
    var parts = path.split("/");
    var currentBin = project.rootItem;

    for (var i = 0; i < parts.length; i++) {
        var binName = parts[i];
        var found = false;

        for (var j = 0; j < currentBin.children.numItems; j++) {
            var child = currentBin.children[j];
            if (child.name === binName && child.type === ProjectItemType.BIN) {
                currentBin = child;
                found = true;
                break;
            }
        }

        if (!found) {
            // Create the bin
            currentBin = currentBin.createBin(binName);
            log("Created bin: " + path);
        }
    }

    return currentBin;
}

function createBinStructure(project, bins, parentPath) {
    /**
     * Recursively create bin structure
     */
    parentPath = parentPath || "";

    for (var binName in bins) {
        if (!bins.hasOwnProperty(binName)) continue;

        var currentPath = parentPath ? parentPath + "/" + binName : binName;
        var bin = getBinByPath(project, currentPath);

        var binContent = bins[binName];

        if (typeof binContent === "object" && !Array.isArray(binContent)) {
            // Nested bins
            createBinStructure(project, binContent, currentPath);
        }
        // Arrays are just keywords for future import matching, bins already created
    }
}

function getFilesInFolder(folderPath, extensions) {
    /**
     * Get all files in a folder matching given extensions
     */
    var folder = new Folder(folderPath);
    var files = [];

    if (!folder.exists) {
        log("Folder does not exist: " + folderPath);
        return files;
    }

    var allFiles = folder.getFiles();

    for (var i = 0; i < allFiles.length; i++) {
        var file = allFiles[i];

        if (file instanceof Folder) {
            // Recursively get files from subfolders
            var subFiles = getFilesInFolder(file.fsName, extensions);
            files = files.concat(subFiles);
        } else {
            var fileName = file.name.toLowerCase();
            for (var j = 0; j < extensions.length; j++) {
                if (fileName.indexOf(extensions[j]) === fileName.length - extensions[j].length) {
                    files.push(file);
                    break;
                }
            }
        }
    }

    return files;
}

function importFileToBin(project, file, bin) {
    /**
     * Import a file into a specific bin
     */
    try {
        var importArray = [file.fsName];
        var suppressUI = true;
        var targetBin = bin;

        project.importFiles(importArray, suppressUI, targetBin, false);
        log("Imported: " + file.name);
        return true;
    } catch (e) {
        log("Error importing " + file.name + ": " + e.message);
        return false;
    }
}

function matchFileToBin(fileName, bins, basePath) {
    /**
     * Match a filename to the best bin based on keywords
     */
    fileName = fileName.toLowerCase();

    function searchBins(binObj, currentPath) {
        for (var binName in binObj) {
            if (!binObj.hasOwnProperty(binName)) continue;

            var newPath = currentPath ? currentPath + "/" + binName : binName;
            var content = binObj[binName];

            if (Array.isArray(content)) {
                // Check keywords
                for (var i = 0; i < content.length; i++) {
                    if (fileName.indexOf(content[i].toLowerCase()) !== -1) {
                        return newPath;
                    }
                }
            } else if (typeof content === "object") {
                var result = searchBins(content, newPath);
                if (result) return result;
            }
        }
        return null;
    }

    return searchBins(bins, basePath || "");
}

function createSequenceTemplate(project, name, width, height, fps) {
    /**
     * Create a sequence with specified settings
     */
    // Get the sequences bin
    var seqBin = getBinByPath(project, "08_SEQUENCES/Templates");

    // Create sequence settings
    // Note: This creates a basic sequence. For custom settings,
    // you may need to use a preset file.

    log("Sequence creation: Use Premiere's New Sequence dialog for best results");
    log("Recommended settings: " + width + "x" + height + " @ " + fps + "fps");
}

// ============================================================
// MAIN FUNCTIONS
// ============================================================

function setupProject() {
    /**
     * Main function to set up the project
     */
    var project = app.project;

    if (!project) {
        alert_user("Please create or open a project first!");
        return;
    }

    log("Starting project setup...");

    // Step 1: Create bin structure
    alert_user(
        "Step 1 of 3: Creating bin structure\n\n" +
        "This will create organized folders for your assets."
    );

    createBinStructure(project, CONFIG.bins);
    log("Bin structure created successfully");

    // Step 2: Ask for assets folder
    alert_user(
        "Step 2 of 3: Select your assets folder\n\n" +
        "Choose the folder containing your downloaded Envato assets.\n" +
        "(e.g., socal_maker/assets)"
    );

    var assetsFolder = Folder.selectDialog("Select your assets folder");

    if (!assetsFolder) {
        alert_user("No folder selected. You can import assets manually later.");
        log("Assets import skipped");
    } else {
        CONFIG.assetsBasePath = assetsFolder.fsName;
        log("Assets folder: " + CONFIG.assetsBasePath);

        // Import assets
        importAssets(project);
    }

    // Step 3: Done
    alert_user(
        "Setup Complete!\n\n" +
        "Your project is now organized with:\n" +
        "- 01_FOOTAGE: Video clips by category\n" +
        "- 02_OVERLAYS: Effects overlays\n" +
        "- 03_TRANSITIONS: Transition clips\n" +
        "- 04_MUSIC: Background music\n" +
        "- 05_SFX: Sound effects\n" +
        "- 06_GRAPHICS: Text and graphics\n" +
        "- 07_EXPORTS: For final renders\n" +
        "- 08_SEQUENCES: Your edits\n\n" +
        "Tip: Create a 1080x1920 sequence for vertical shorts!"
    );

    log("Project setup complete!");
}

function importAssets(project) {
    /**
     * Import all assets from the selected folder
     */
    log("Scanning for assets...");

    var allExtensions = CONFIG.videoExtensions
        .concat(CONFIG.audioExtensions)
        .concat(CONFIG.imageExtensions);

    var files = getFilesInFolder(CONFIG.assetsBasePath, allExtensions);

    log("Found " + files.length + " files to import");

    if (files.length === 0) {
        alert_user("No media files found in the selected folder.");
        return;
    }

    var imported = 0;
    var skipped = 0;

    for (var i = 0; i < files.length; i++) {
        var file = files[i];
        var fileName = file.name.toLowerCase();

        // Determine target bin based on file type and name
        var targetPath = "";

        // Check file extension to determine category
        var isVideo = false, isAudio = false, isImage = false;

        for (var v = 0; v < CONFIG.videoExtensions.length; v++) {
            if (fileName.indexOf(CONFIG.videoExtensions[v]) !== -1) {
                isVideo = true;
                break;
            }
        }
        for (var a = 0; a < CONFIG.audioExtensions.length; a++) {
            if (fileName.indexOf(CONFIG.audioExtensions[a]) !== -1) {
                isAudio = true;
                break;
            }
        }

        if (isAudio) {
            // Check if it's music or SFX
            if (fileName.indexOf("sfx") !== -1 ||
                fileName.indexOf("whoosh") !== -1 ||
                fileName.indexOf("hit") !== -1 ||
                fileName.indexOf("impact") !== -1) {
                targetPath = "05_SFX";
            } else {
                targetPath = "04_MUSIC";
            }
        } else if (isVideo) {
            // Try to match to a specific bin
            var matchedPath = matchFileToBin(fileName, CONFIG.bins, "");

            if (matchedPath) {
                targetPath = matchedPath;
            } else {
                // Default based on keywords
                if (fileName.indexOf("overlay") !== -1 ||
                    fileName.indexOf("dust") !== -1 ||
                    fileName.indexOf("grain") !== -1 ||
                    fileName.indexOf("leak") !== -1) {
                    targetPath = "02_OVERLAYS";
                } else if (fileName.indexOf("transition") !== -1) {
                    targetPath = "03_TRANSITIONS";
                } else {
                    targetPath = "01_FOOTAGE/Universal";
                }
            }
        } else {
            targetPath = "06_GRAPHICS";
        }

        // Get or create target bin
        var targetBin = getBinByPath(project, targetPath);

        // Import file
        if (importFileToBin(project, file, targetBin)) {
            imported++;
        } else {
            skipped++;
        }

        // Update progress every 10 files
        if (i % 10 === 0) {
            log("Progress: " + (i + 1) + "/" + files.length);
        }
    }

    log("Import complete: " + imported + " imported, " + skipped + " skipped");
    alert_user(
        "Import Complete!\n\n" +
        "Imported: " + imported + " files\n" +
        "Skipped: " + skipped + " files\n\n" +
        "Check the bins for your organized assets."
    );
}

function importAssetsOnly() {
    /**
     * Import assets without creating bin structure (assumes it exists)
     */
    var project = app.project;

    if (!project) {
        alert_user("Please create or open a project first!");
        return;
    }

    var assetsFolder = Folder.selectDialog("Select your assets folder");

    if (!assetsFolder) {
        alert_user("No folder selected.");
        return;
    }

    CONFIG.assetsBasePath = assetsFolder.fsName;
    importAssets(project);
}

function createShortTemplate() {
    /**
     * Show settings for creating a YouTube Shorts / TikTok / Reels sequence
     */
    alert_user(
        "YouTube Shorts / TikTok / Reels Template\n\n" +
        "Create a new sequence with these settings:\n\n" +
        "Resolution: 1080 x 1920 (9:16 vertical)\n" +
        "Frame Rate: 30 fps\n" +
        "Duration: Under 60 seconds\n\n" +
        "Go to: File > New > Sequence\n" +
        "Choose 'Digital SLR > 1080p > DSLR 1080p30'\n" +
        "Then go to Sequence > Sequence Settings\n" +
        "Change Frame Size to 1080 x 1920"
    );
}

// ============================================================
// RUN SCRIPT
// ============================================================

// Show main menu
var menuChoice = confirm(
    "Social Media Content Factory\n" +
    "Premiere Pro Setup Script\n\n" +
    "Click OK to set up your project\n" +
    "(creates bins + imports assets)\n\n" +
    "Click Cancel for more options"
);

if (menuChoice) {
    setupProject();
} else {
    var option = prompt(
        "Enter option number:\n\n" +
        "1 = Create bin structure only\n" +
        "2 = Import assets only (bins must exist)\n" +
        "3 = Show Shorts sequence settings\n" +
        "4 = Cancel",
        "1"
    );

    switch (option) {
        case "1":
            createBinStructure(app.project, CONFIG.bins);
            alert_user("Bin structure created!");
            break;
        case "2":
            importAssetsOnly();
            break;
        case "3":
            createShortTemplate();
            break;
        default:
            log("Script cancelled");
    }
}
