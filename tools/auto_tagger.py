#!/usr/bin/env python3
"""
AI-Powered Auto-Tagger for Video and Image Assets

Uses Google Cloud APIs to automatically detect and tag content:
- Video Intelligence API for videos (.mp4, .mov, .webm)
- Cloud Vision API for images (.jpg, .png, .webp)

Setup:
1. Create GCP project and enable APIs
2. Create service account and download JSON key
3. Set GOOGLE_APPLICATION_CREDENTIALS in .env

Usage:
    python tools/auto_tagger.py                    # Auto-tag all untagged assets
    python tools/auto_tagger.py --file video.mp4  # Tag specific file
    python tools/auto_tagger.py --reprocess       # Re-tag all assets
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import ASSETS_DIR

# Lazy imports for Google Cloud (only when needed)
videointelligence = None
vision = None

MANIFEST_PATH = ASSETS_DIR / "manifest.json"

# Supported file extensions
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Confidence threshold for including labels
MIN_CONFIDENCE = 0.7


def _load_google_video():
    """Lazy load Google Video Intelligence client."""
    global videointelligence
    if videointelligence is None:
        try:
            from google.cloud import videointelligence as vi
            videointelligence = vi
        except ImportError:
            raise ImportError(
                "google-cloud-videointelligence not installed.\n"
                "Run: pip install google-cloud-videointelligence"
            )
    return videointelligence


def _load_google_vision():
    """Lazy load Google Cloud Vision client."""
    global vision
    if vision is None:
        try:
            from google.cloud import vision as v
            vision = v
        except ImportError:
            raise ImportError(
                "google-cloud-vision not installed.\n"
                "Run: pip install google-cloud-vision"
            )
    return vision


def load_manifest() -> dict:
    """Load the asset manifest."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {"version": "1.0", "assets": {}}


def save_manifest(manifest: dict) -> None:
    """Save the asset manifest."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def detect_mood(tags: list) -> str:
    """Infer mood from detected tags."""
    mood_mapping = {
        "dark": ["dark", "night", "fog", "mist", "shadow", "moody", "dramatic"],
        "bright": ["bright", "sunny", "light", "yellow", "colorful", "vibrant"],
        "calm": ["calm", "peaceful", "serene", "nature", "water", "sky"],
        "energetic": ["action", "running", "sport", "exercise", "fast", "dynamic"],
        "medical": ["medical", "health", "doctor", "hospital", "anatomy", "body"],
        "warm": ["warm", "cozy", "home", "family", "love", "together"],
        "epic": ["mountain", "landscape", "aerial", "cinematic", "epic", "sunrise"],
        "urban": ["city", "street", "urban", "building", "traffic", "crowd"],
    }

    tag_set = set(t.lower() for t in tags)

    for mood, keywords in mood_mapping.items():
        if tag_set & set(keywords):
            return mood

    return "neutral"


def analyze_video(video_path: Path) -> dict:
    """
    Analyze a video using Google Video Intelligence API.

    Returns:
        dict with 'tags', 'objects', 'confidence_scores'
    """
    # Check file size - API limit is 10MB for direct upload
    MAX_VIDEO_SIZE = 10 * 1024 * 1024  # 10MB
    file_size = video_path.stat().st_size

    if file_size > MAX_VIDEO_SIZE:
        print(f"  Skipping - video too large ({file_size // (1024*1024)}MB > 10MB limit)")
        return {"tags": [], "objects": [], "confidence_scores": {}, "skipped": "too_large"}

    vi = _load_google_video()
    client = vi.VideoIntelligenceServiceClient()

    # Read video file
    with open(video_path, "rb") as f:
        input_content = f.read()

    # Configure features to detect
    features = [
        vi.Feature.LABEL_DETECTION,
        vi.Feature.OBJECT_TRACKING,
    ]

    # Configure label detection
    config = vi.LabelDetectionConfig(
        label_detection_mode=vi.LabelDetectionMode.SHOT_AND_FRAME_MODE,
        stationary_camera=False,
    )

    video_context = vi.VideoContext(label_detection_config=config)

    print(f"  Analyzing video with Google AI... (this may take 30-60 seconds)")

    # Make the request
    operation = client.annotate_video(
        request={
            "features": features,
            "input_content": input_content,
            "video_context": video_context,
        }
    )

    # Wait for completion
    result = operation.result(timeout=180)

    # Extract labels
    tags = []
    confidence_scores = {}
    objects_detected = []

    # Process segment labels (whole video)
    for label in result.annotation_results[0].segment_label_annotations:
        entity = label.entity.description.lower()
        confidence = label.segments[0].confidence if label.segments else 0

        if confidence >= MIN_CONFIDENCE:
            tags.append(entity)
            confidence_scores[entity] = round(confidence, 2)

    # Process object tracking
    for obj in result.annotation_results[0].object_annotations:
        entity = obj.entity.description.lower()
        confidence = obj.confidence

        if confidence >= MIN_CONFIDENCE and entity not in tags:
            objects_detected.append(entity)
            confidence_scores[entity] = round(confidence, 2)

    # Combine tags and objects
    all_tags = list(set(tags + objects_detected))

    return {
        "tags": all_tags,
        "objects": objects_detected,
        "confidence_scores": confidence_scores,
    }


def analyze_image(image_path: Path) -> dict:
    """
    Analyze an image using Google Cloud Vision API.

    Returns:
        dict with 'tags', 'objects', 'confidence_scores'
    """
    v = _load_google_vision()
    client = v.ImageAnnotatorClient()

    # Read image file
    with open(image_path, "rb") as f:
        content = f.read()

    image = v.Image(content=content)

    # Request multiple feature types
    features = [
        v.Feature(type_=v.Feature.Type.LABEL_DETECTION, max_results=20),
        v.Feature(type_=v.Feature.Type.OBJECT_LOCALIZATION, max_results=10),
    ]

    request = v.AnnotateImageRequest(image=image, features=features)

    print(f"  Analyzing image with Google AI...")

    response = client.annotate_image(request=request)

    tags = []
    objects_detected = []
    confidence_scores = {}

    # Process labels
    for label in response.label_annotations:
        entity = label.description.lower()
        confidence = label.score

        if confidence >= MIN_CONFIDENCE:
            tags.append(entity)
            confidence_scores[entity] = round(confidence, 2)

    # Process objects
    for obj in response.localized_object_annotations:
        entity = obj.name.lower()
        confidence = obj.score

        if confidence >= MIN_CONFIDENCE and entity not in tags:
            objects_detected.append(entity)
            confidence_scores[entity] = round(confidence, 2)

    all_tags = list(set(tags + objects_detected))

    return {
        "tags": all_tags,
        "objects": objects_detected,
        "confidence_scores": confidence_scores,
    }


def analyze_asset(asset_path: Path) -> dict:
    """
    Analyze an asset (video or image) and return tags.

    Returns:
        dict with 'keywords', 'type', 'mood', 'auto_tagged', 'confidence_scores'
        Returns None if asset was skipped (e.g., too large)
    """
    ext = asset_path.suffix.lower()

    if ext in VIDEO_EXTENSIONS:
        result = analyze_video(asset_path)
        asset_type = "video"
    elif ext in IMAGE_EXTENSIONS:
        result = analyze_image(asset_path)
        asset_type = "image"
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Handle skipped files
    if result.get("skipped"):
        return None

    mood = detect_mood(result["tags"])

    return {
        "keywords": result["tags"],
        "type": asset_type,
        "mood": mood,
        "auto_tagged": True,
        "confidence_scores": result["confidence_scores"],
    }


def auto_tag_asset(asset_path: Path, manifest: dict, force: bool = False) -> bool:
    """
    Auto-tag a single asset and update manifest.

    Args:
        asset_path: Path to the asset file
        manifest: Manifest dict to update
        force: If True, re-tag even if already tagged

    Returns:
        True if asset was tagged, False if skipped
    """
    # Get relative path from assets dir
    try:
        rel_path = str(asset_path.relative_to(ASSETS_DIR))
    except ValueError:
        rel_path = str(asset_path)

    # Check if already tagged
    if rel_path in manifest.get("assets", {}) and not force:
        existing = manifest["assets"][rel_path]
        if existing.get("auto_tagged"):
            print(f"  Skipping (already auto-tagged): {asset_path.name}")
            return False

    print(f"\n[{asset_path.name}]")

    try:
        result = analyze_asset(asset_path)

        # Handle skipped files (e.g., too large)
        if result is None:
            return False

        manifest["assets"][rel_path] = result

        print(f"  Tags: {', '.join(result['keywords'][:10])}")
        if len(result['keywords']) > 10:
            print(f"        (+{len(result['keywords']) - 10} more)")
        print(f"  Mood: {result['mood']}")
        print(f"  Type: {result['type']}")

        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def auto_tag_all(assets_dir: Path = None, force: bool = False) -> dict:
    """
    Auto-tag all untagged assets in the assets directory.

    Args:
        assets_dir: Directory to scan (defaults to ASSETS_DIR)
        force: If True, re-tag all assets

    Returns:
        Summary dict with counts
    """
    if assets_dir is None:
        assets_dir = ASSETS_DIR

    manifest = load_manifest()

    # Find all video and image files
    all_assets = []
    for ext in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS:
        all_assets.extend(assets_dir.rglob(f"*{ext}"))
        all_assets.extend(assets_dir.rglob(f"*{ext.upper()}"))

    # Filter to backgrounds folder primarily
    bg_assets = [a for a in all_assets if "backgrounds" in str(a)]
    other_assets = [a for a in all_assets if "backgrounds" not in str(a)]

    # Prioritize backgrounds
    assets_to_process = bg_assets + other_assets

    print(f"Found {len(assets_to_process)} assets to process")
    print(f"  Videos: {len([a for a in assets_to_process if a.suffix.lower() in VIDEO_EXTENSIONS])}")
    print(f"  Images: {len([a for a in assets_to_process if a.suffix.lower() in IMAGE_EXTENSIONS])}")

    tagged_count = 0
    skipped_count = 0
    error_count = 0

    for i, asset_path in enumerate(assets_to_process, 1):
        print(f"\n[{i}/{len(assets_to_process)}] Processing {asset_path.name}...")

        try:
            if auto_tag_asset(asset_path, manifest, force=force):
                tagged_count += 1
                # Save after each successful tag (in case of interruption)
                save_manifest(manifest)
            else:
                skipped_count += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            error_count += 1

    print(f"\n{'='*50}")
    print(f"Auto-tagging complete!")
    print(f"  Tagged: {tagged_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    print(f"  Manifest: {MANIFEST_PATH}")
    print(f"{'='*50}")

    return {
        "tagged": tagged_count,
        "skipped": skipped_count,
        "errors": error_count,
    }


def check_credentials():
    """Check if Google Cloud credentials are configured."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

    if not creds_path:
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS not set")
        print("")
        print("Setup instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project (or select existing)")
        print("3. Enable 'Cloud Video Intelligence API' and 'Cloud Vision API'")
        print("4. Go to IAM & Admin > Service Accounts")
        print("5. Create a service account with 'Cloud Vision API User' role")
        print("6. Create and download a JSON key")
        print("7. Add to your .env file:")
        print("   GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-key.json")
        return False

    if not Path(creds_path).exists():
        print(f"ERROR: Credentials file not found: {creds_path}")
        return False

    print(f"Using credentials: {creds_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="AI-powered auto-tagging for video and image assets"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Tag a specific file instead of all assets",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Re-tag assets even if already tagged",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check if credentials are configured",
    )

    args = parser.parse_args()

    # Check credentials
    if not check_credentials():
        if not args.check:
            sys.exit(1)
        return

    if args.check:
        print("Credentials OK!")
        return

    # Tag specific file
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"File not found: {file_path}")
            sys.exit(1)

        manifest = load_manifest()
        auto_tag_asset(file_path, manifest, force=args.reprocess)
        save_manifest(manifest)
        return

    # Tag all assets
    auto_tag_all(force=args.reprocess)


if __name__ == "__main__":
    main()
