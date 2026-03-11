"""
Asset Matcher - Intelligent visual-to-script matching for content generation.

Matches script keywords to tagged assets in the manifest for contextually
relevant video backgrounds (e.g., "bananas" in script -> banana footage).

KEY FEATURES:
- Scene-by-scene analysis
- Vision/Video Intelligence tag matching
- Confidence threshold enforcement
- Fallback flagging for unmatched scenes
"""
import json
import random
import re
from pathlib import Path
from typing import Optional

from config.settings import ASSETS_DIR

MANIFEST_PATH = ASSETS_DIR / "manifest.json"

# Matching thresholds - raised to prevent mismatches (e.g., butterfly -> mountain)
MIN_CONFIDENCE_THRESHOLD = 0.40  # Minimum score to use an asset (was 0.30, 0.15 originally)
STRONG_MATCH_THRESHOLD = 0.50    # Score for high-confidence matches (was 0.45)
VEO_HYBRID_THRESHOLD = 0.40      # Use VEO if asset score below this


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


def extract_scene_keywords(scene_words: list) -> list:
    """
    Extract meaningful keywords from scene words for matching.

    Filters out common stop words and extracts nouns/verbs that
    are likely to match visual content.

    Args:
        scene_words: List of word dicts from scene timing

    Returns:
        List of extracted keywords
    """
    STOP_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'to', 'of', 'in', 'for', 'on',
        'with', 'at', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'under', 'again',
        'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
        'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
        'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
        'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'this',
        'that', 'these', 'those', 'what', 'which', 'who', 'whom', 'its', 'it',
        'you', 'your', 'we', 'our', 'they', 'their', 'them', 'one', 'two',
        'three', 'first', 'second', 'know', 'think', 'make', 'see', 'come',
        'take', 'want', 'look', 'use', 'find', 'give', 'tell', 'say', 'get',
        'go', 'put', 'also', 'back', 'now', 'even', 'way', 'well', 'thing',
    }

    keywords = []

    for word_info in scene_words:
        word = word_info.get("word", "")
        # Clean punctuation
        clean = re.sub(r'[^\w\s]', '', word.lower())

        if len(clean) >= 3 and clean not in STOP_WORDS:
            keywords.append(clean)

    return keywords


def score_asset(asset_keywords: list, target_keywords: list) -> float:
    """
    Calculate match score between asset keywords and target keywords.

    Uses weighted matching with:
    - Exact matches (1.0 weight)
    - Partial/substring matches (0.5 weight)
    - Semantic similarity for common concepts

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

    # Exact matches (full weight)
    intersection = asset_set & target_set
    exact_score = len(intersection)

    # Partial matches (substring matching)
    partial_score = 0
    for asset_kw in asset_set:
        for target_kw in target_set:
            if asset_kw != target_kw:
                # Substring match
                if asset_kw in target_kw or target_kw in asset_kw:
                    partial_score += 0.5
                # Pluralization (simple heuristic)
                elif asset_kw + 's' == target_kw or target_kw + 's' == asset_kw:
                    partial_score += 0.8
                # Stemming for common suffixes
                elif asset_kw.rstrip('ing') == target_kw.rstrip('ing'):
                    partial_score += 0.7

    # Semantic similarity for common concept pairs
    SEMANTIC_PAIRS = {
        ('moon', 'space'): 0.6, ('moon', 'night'): 0.5, ('moon', 'sky'): 0.4,
        ('paper', 'fold'): 0.6, ('paper', 'origami'): 0.8,
        ('growth', 'plant'): 0.5, ('growth', 'business'): 0.4,
        ('math', 'numbers'): 0.7, ('math', 'calculate'): 0.6,
        ('sun', 'sky'): 0.5, ('sun', 'space'): 0.4,
        ('earth', 'planet'): 0.8, ('earth', 'nature'): 0.5,
        ('water', 'ocean'): 0.7, ('water', 'sea'): 0.7,
        ('mountain', 'nature'): 0.6, ('mountain', 'landscape'): 0.7,
        ('city', 'urban'): 0.8, ('city', 'street'): 0.6,
        ('walk', 'walking'): 0.9, ('run', 'running'): 0.9,
        # Insect/nature pairs - prevent butterfly -> mountain mismatches
        ('butterfly', 'insect'): 0.85, ('butterfly', 'wing'): 0.70,
        ('butterfly', 'nature'): 0.60, ('butterfly', 'flower'): 0.65,
        ('caterpillar', 'insect'): 0.85, ('caterpillar', 'butterfly'): 0.70,
        ('insect', 'nature'): 0.60, ('insect', 'bug'): 0.90,
        ('bee', 'insect'): 0.85, ('bee', 'flower'): 0.65,
        ('ant', 'insect'): 0.85, ('spider', 'insect'): 0.70,
    }

    semantic_score = 0
    for asset_kw in asset_set:
        for target_kw in target_set:
            pair = (asset_kw, target_kw)
            reverse_pair = (target_kw, asset_kw)
            if pair in SEMANTIC_PAIRS:
                semantic_score += SEMANTIC_PAIRS[pair]
            elif reverse_pair in SEMANTIC_PAIRS:
                semantic_score += SEMANTIC_PAIRS[reverse_pair]

    # Combine scores
    total_score = exact_score + partial_score + semantic_score

    # Normalize by size of target keywords
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

        # VERIFY FILE EXISTS before considering it
        full_path = ASSETS_DIR / asset_path
        if not full_path.exists():
            continue  # Skip missing files

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


def match_scene_by_scene(
    scenes: list,
    global_keywords: list,
    content_type: str = "fact",
    min_confidence: float = None,
) -> list[dict]:
    """
    Match assets to each scene individually based on scene content.

    This provides more accurate visual-script matching by analyzing
    each scene's words separately rather than using global keywords.

    Args:
        scenes: List of scene dicts with "words" key containing word timing
        global_keywords: Fallback keywords if scene extraction fails
        content_type: Content type for folder preference
        min_confidence: Minimum match score (default: MIN_CONFIDENCE_THRESHOLD)

    Returns:
        List of match results per scene:
        {
            "scene_idx": 0,
            "asset_path": Path or None,
            "score": 0.45,
            "matched": True/False,
            "keywords_used": ["moon", "space"],
            "asset_keywords": ["space", "galaxy", "stars"],
            "flagged": False  # True if below threshold
        }
    """
    if min_confidence is None:
        min_confidence = MIN_CONFIDENCE_THRESHOLD

    manifest = load_manifest()
    assets = manifest.get("assets", {})

    if not assets:
        print("  Warning: No assets in manifest - run auto_tagger.py first")
        return [{"scene_idx": i, "asset_path": None, "score": 0, "matched": False, "flagged": True}
                for i in range(len(scenes))]

    results = []
    used_paths = set()

    for scene_idx, scene in enumerate(scenes):
        # Extract keywords from this scene's words
        scene_words = scene.get("words", [])
        scene_keywords = extract_scene_keywords(scene_words)

        # Fall back to global keywords if scene extraction fails
        if not scene_keywords:
            scene_keywords = global_keywords

        # Score all assets against scene keywords
        scored_assets = []
        for asset_path, asset_info in assets.items():
            if asset_path in used_paths:
                continue

            # VERIFY FILE EXISTS
            full_path = ASSETS_DIR / asset_path
            if not full_path.exists():
                continue

            asset_keywords = asset_info.get("keywords", [])
            score = score_asset(asset_keywords, scene_keywords)

            # Content type boost
            if content_type in asset_path:
                score *= 1.2

            # Video preference
            if asset_info.get("type") == "video":
                score *= 1.05

            scored_assets.append({
                "path": asset_path,
                "score": score,
                "keywords": asset_keywords,
                "type": asset_info.get("type", "unknown"),
            })

        # Sort by score
        scored_assets.sort(key=lambda x: x["score"], reverse=True)

        # Select best match
        if scored_assets and scored_assets[0]["score"] >= min_confidence:
            best = scored_assets[0]
            full_path = ASSETS_DIR / best["path"]
            used_paths.add(best["path"])

            results.append({
                "scene_idx": scene_idx,
                "asset_path": full_path,
                "score": best["score"],
                "matched": True,
                "keywords_used": scene_keywords,
                "asset_keywords": best["keywords"],
                "flagged": best["score"] < STRONG_MATCH_THRESHOLD,
            })
        else:
            # No match above threshold - FLAG this scene
            results.append({
                "scene_idx": scene_idx,
                "asset_path": None,
                "score": scored_assets[0]["score"] if scored_assets else 0,
                "matched": False,
                "keywords_used": scene_keywords,
                "asset_keywords": [],
                "flagged": True,
                "reason": "No asset meets confidence threshold",
            })

    return results


def get_unmatched_scenes(match_results: list) -> list[int]:
    """Get list of scene indices that failed to match."""
    return [r["scene_idx"] for r in match_results if not r["matched"]]


def get_flagged_scenes(match_results: list) -> list[dict]:
    """Get scenes that matched but with low confidence."""
    return [r for r in match_results if r["matched"] and r["flagged"]]


def report_matching_quality(match_results: list) -> str:
    """Generate a human-readable report of matching quality."""
    lines = ["Visual-Script Matching Report:", "-" * 40]

    matched = sum(1 for r in match_results if r["matched"])
    flagged = sum(1 for r in match_results if r["flagged"])
    total = len(match_results)

    lines.append(f"Scenes matched: {matched}/{total}")
    lines.append(f"Low confidence: {flagged}")

    for r in match_results:
        status = "OK" if r["matched"] and not r["flagged"] else "LOW" if r["matched"] else "MISS"
        asset_name = Path(r["asset_path"]).name if r["asset_path"] else "NONE"
        lines.append(f"  Scene {r['scene_idx']+1}: [{status}] {r['score']:.2f} - {asset_name}")

    if flagged > 0:
        lines.append("\nSuggestions:")
        lines.append("- Add more relevant footage to assets folder")
        lines.append("- Run auto_tagger.py to tag new assets")
        lines.append("- Or manually upload footage for flagged scenes")

    return "\n".join(lines)


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
