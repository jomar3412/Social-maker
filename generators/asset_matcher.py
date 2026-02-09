"""
Asset Matcher - Keyword-based asset selection for content generation.

Matches script keywords to tagged assets in the manifest for contextually
relevant video backgrounds (e.g., "bananas" in script -> banana footage).
"""
import json
import random
from pathlib import Path
from typing import Optional

from config.settings import ASSETS_DIR

MANIFEST_PATH = ASSETS_DIR / "manifest.json"


def load_manifest() -> dict:
    """Load the asset manifest with keyword tags."""
    if not MANIFEST_PATH.exists():
        return {"version": "1.0", "assets": {}}

    with open(MANIFEST_PATH) as f:
        return json.load(f)


def save_manifest(manifest: dict) -> None:
    """Save the asset manifest."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def score_asset(asset_keywords: list, target_keywords: list) -> float:
    """
    Calculate match score between asset keywords and target keywords.
    Uses Jaccard similarity with partial matching boost.

    Args:
        asset_keywords: Keywords tagged on the asset
        target_keywords: Keywords extracted from the script

    Returns:
        Score from 0.0 to 1.0
    """
    if not asset_keywords or not target_keywords:
        return 0.0

    asset_set = set(k.lower() for k in asset_keywords)
    target_set = set(k.lower() for k in target_keywords)

    # Exact matches (Jaccard intersection)
    intersection = asset_set & target_set

    # Partial matches (substring matching)
    partial_matches = 0
    for asset_kw in asset_set:
        for target_kw in target_set:
            if asset_kw != target_kw:
                if asset_kw in target_kw or target_kw in asset_kw:
                    partial_matches += 0.5

    # Combine: full matches count as 1, partial as 0.5
    total_score = len(intersection) + partial_matches

    # Normalize by size of target keywords (what we're looking for)
    max_possible = len(target_set)
    if max_possible == 0:
        return 0.0

    return min(total_score / max_possible, 1.0)


def match_assets(
    keywords: list,
    count: int,
    content_type: str = "health",
    exclude: Optional[set] = None,
) -> list[Path]:
    """
    Find assets that best match the given keywords.

    Args:
        keywords: Keywords to match against
        count: Number of assets to return
        content_type: Content type to prefer (health, nutrition, etc.)
        exclude: Set of asset paths to exclude (already used)

    Returns:
        List of asset paths sorted by match score
    """
    manifest = load_manifest()
    assets = manifest.get("assets", {})

    if not assets:
        return []

    exclude = exclude or set()
    scored_assets = []

    for asset_path, asset_info in assets.items():
        if asset_path in exclude:
            continue

        asset_keywords = asset_info.get("keywords", [])
        score = score_asset(asset_keywords, keywords)

        # Boost score for assets in the target content_type folder
        if content_type in asset_path:
            score *= 1.2

        # Slight boost for videos over images (more engaging)
        if asset_info.get("type") == "video":
            score *= 1.05

        scored_assets.append((asset_path, score, asset_info))

    # Sort by score (highest first)
    scored_assets.sort(key=lambda x: x[1], reverse=True)

    # Select top matches
    selected = []
    for asset_path, score, info in scored_assets[:count]:
        full_path = ASSETS_DIR / asset_path
        selected.append({
            "path": full_path,
            "score": score,
            "keywords": info.get("keywords", []),
            "type": info.get("type", "unknown"),
        })

    return selected


def select_scene_assets(
    scenes: list,
    keywords: list,
    content_type: str = "health",
) -> list[Path]:
    """
    Select unique assets for each scene based on keywords.

    Args:
        scenes: List of scene dicts with timing info
        keywords: Keywords from the script
        content_type: Content type for preference

    Returns:
        List of asset paths, one per scene
    """
    num_scenes = len(scenes)
    matched = match_assets(keywords, num_scenes * 2, content_type)  # Get extras for variety

    if len(matched) < num_scenes:
        # Not enough matches, return what we have
        return [m["path"] for m in matched]

    # Select diverse assets (don't repeat)
    selected = []
    used_paths = set()

    for _ in range(num_scenes):
        for match in matched:
            if match["path"] not in used_paths:
                selected.append(match["path"])
                used_paths.add(match["path"])
                break

    return selected


def get_asset_info(asset_path: str) -> Optional[dict]:
    """Get info for a specific asset from the manifest."""
    manifest = load_manifest()
    # Try both with and without assets/ prefix
    for path_variant in [asset_path, asset_path.replace(str(ASSETS_DIR) + "/", "")]:
        if path_variant in manifest.get("assets", {}):
            return manifest["assets"][path_variant]
    return None


def add_asset(asset_path: str, keywords: list, asset_type: str = "video", mood: str = "neutral") -> None:
    """
    Add or update an asset in the manifest.

    Args:
        asset_path: Relative path from ASSETS_DIR
        keywords: List of keyword tags
        asset_type: "video" or "image"
        mood: Mood/tone of the asset
    """
    manifest = load_manifest()

    # Normalize path
    if asset_path.startswith(str(ASSETS_DIR)):
        asset_path = asset_path.replace(str(ASSETS_DIR) + "/", "")

    manifest["assets"][asset_path] = {
        "keywords": keywords,
        "type": asset_type,
        "mood": mood,
        "duration": None,
    }

    save_manifest(manifest)


def remove_asset(asset_path: str) -> bool:
    """Remove an asset from the manifest."""
    manifest = load_manifest()

    # Normalize path
    if asset_path.startswith(str(ASSETS_DIR)):
        asset_path = asset_path.replace(str(ASSETS_DIR) + "/", "")

    if asset_path in manifest.get("assets", {}):
        del manifest["assets"][asset_path]
        save_manifest(manifest)
        return True

    return False


def list_untagged_assets() -> list[Path]:
    """Find assets in the directory that aren't in the manifest."""
    manifest = load_manifest()
    tagged_paths = set(manifest.get("assets", {}).keys())

    untagged = []

    # Scan for video and image files
    extensions = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".jpg", ".jpeg", ".png", ".webp"}

    for ext in extensions:
        for asset_file in ASSETS_DIR.rglob(f"*{ext}"):
            rel_path = str(asset_file.relative_to(ASSETS_DIR))
            if rel_path not in tagged_paths:
                untagged.append(asset_file)

    return untagged


if __name__ == "__main__":
    # Test the matcher
    test_keywords = ["banana", "potassium", "blood pressure", "heart"]
    print(f"Testing match for keywords: {test_keywords}")

    matches = match_assets(test_keywords, count=4, content_type="health")

    for i, match in enumerate(matches, 1):
        print(f"  {i}. {match['path'].name} (score: {match['score']:.2f})")
        print(f"     Keywords: {match['keywords']}")
