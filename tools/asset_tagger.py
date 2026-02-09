#!/usr/bin/env python3
"""
Asset Tagger CLI - Manage keyword tags for assets.

Commands:
    auto-tag - AI-powered auto-tagging using Google Cloud Vision/Video Intelligence
    scan     - Scan for untagged assets and prompt for tags
    add      - Add/update tags for a specific asset
    list     - List all tagged assets
    remove   - Remove an asset from the manifest
    search   - Search assets by keyword

Usage:
    python tools/asset_tagger.py auto-tag              # Auto-tag all with AI
    python tools/asset_tagger.py auto-tag --file x.mp4 # Auto-tag specific file
    python tools/asset_tagger.py scan
    python tools/asset_tagger.py add backgrounds/health/banana.mp4 "banana,fruit,yellow,potassium"
    python tools/asset_tagger.py list
    python tools/asset_tagger.py search banana
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generators.asset_matcher import (
    load_manifest,
    save_manifest,
    add_asset,
    remove_asset,
    list_untagged_assets,
    match_assets,
    MANIFEST_PATH,
)
from config.settings import ASSETS_DIR


def cmd_scan(args):
    """Scan for untagged assets and prompt for tags."""
    untagged = list_untagged_assets()

    if not untagged:
        print("All assets are tagged!")
        return

    print(f"Found {len(untagged)} untagged assets:\n")

    for asset_path in untagged:
        rel_path = asset_path.relative_to(ASSETS_DIR)
        print(f"\nAsset: {rel_path}")

        # Determine type from extension
        ext = asset_path.suffix.lower()
        asset_type = "video" if ext in {".mp4", ".mov", ".webm", ".avi", ".mkv"} else "image"

        if args.auto:
            # Auto-suggest keywords from path
            path_parts = str(rel_path).lower().replace("_", " ").replace("-", " ")
            suggested = [p for p in path_parts.split("/") if p and "." not in p]
            print(f"  Auto-suggested: {suggested}")
            keywords = suggested
            mood = "neutral"
        else:
            # Interactive mode
            keywords_input = input("  Enter keywords (comma-separated, or 'skip'): ").strip()
            if keywords_input.lower() == "skip":
                continue

            keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
            mood = input("  Enter mood (bright/calm/medical/energetic/neutral): ").strip() or "neutral"

        if keywords:
            add_asset(str(rel_path), keywords, asset_type, mood)
            print(f"  Tagged: {rel_path}")

    print(f"\nManifest saved to: {MANIFEST_PATH}")


def cmd_add(args):
    """Add or update tags for a specific asset."""
    asset_path = args.path
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    if not keywords:
        print("Error: No keywords provided")
        sys.exit(1)

    # Determine type from extension
    ext = Path(asset_path).suffix.lower()
    asset_type = "video" if ext in {".mp4", ".mov", ".webm", ".avi", ".mkv"} else "image"

    add_asset(asset_path, keywords, asset_type, args.mood or "neutral")
    print(f"Added/updated: {asset_path}")
    print(f"  Keywords: {keywords}")
    print(f"  Type: {asset_type}")
    print(f"  Mood: {args.mood or 'neutral'}")


def cmd_list(args):
    """List all tagged assets."""
    manifest = load_manifest()
    assets = manifest.get("assets", {})

    if not assets:
        print("No assets tagged yet.")
        print(f"Run: python tools/asset_tagger.py scan")
        return

    print(f"Tagged assets ({len(assets)}):\n")

    # Group by content type
    by_type = {}
    for path, info in assets.items():
        # Extract content type from path
        parts = path.split("/")
        content_type = parts[1] if len(parts) > 1 else "other"
        if content_type not in by_type:
            by_type[content_type] = []
        by_type[content_type].append((path, info))

    for content_type, items in sorted(by_type.items()):
        print(f"[{content_type.upper()}]")
        for path, info in sorted(items):
            keywords = ", ".join(info.get("keywords", []))
            mood = info.get("mood", "?")
            asset_type = info.get("type", "?")
            print(f"  {path}")
            print(f"    Keywords: {keywords}")
            print(f"    Type: {asset_type}, Mood: {mood}")
        print()


def cmd_remove(args):
    """Remove an asset from the manifest."""
    if remove_asset(args.path):
        print(f"Removed: {args.path}")
    else:
        print(f"Asset not found in manifest: {args.path}")
        sys.exit(1)


def cmd_search(args):
    """Search assets by keyword."""
    keywords = [k.strip() for k in args.query.split(",") if k.strip()]

    if not keywords:
        print("Error: No search keywords provided")
        sys.exit(1)

    matches = match_assets(keywords, count=args.limit, content_type=args.type or "")

    if not matches:
        print(f"No matches found for: {keywords}")
        return

    print(f"Matches for '{', '.join(keywords)}':\n")

    for i, match in enumerate(matches, 1):
        rel_path = match["path"].relative_to(ASSETS_DIR) if match["path"].is_relative_to(ASSETS_DIR) else match["path"]
        score = match["score"]
        match_kw = ", ".join(match["keywords"])

        print(f"  {i}. {rel_path}")
        print(f"     Score: {score:.2f} | Keywords: {match_kw}")


def cmd_auto_tag(args):
    """AI-powered auto-tagging using Google Cloud APIs."""
    try:
        from tools.auto_tagger import auto_tag_all, auto_tag_asset, check_credentials, load_manifest, save_manifest
    except ImportError as e:
        print(f"Error importing auto_tagger: {e}")
        print("Make sure google-cloud-videointelligence and google-cloud-vision are installed:")
        print("  pip install google-cloud-videointelligence google-cloud-vision")
        sys.exit(1)

    # Check credentials first
    if not check_credentials():
        sys.exit(1)

    if args.file:
        # Tag specific file
        file_path = Path(args.file)
        if not file_path.exists():
            # Try relative to ASSETS_DIR
            file_path = ASSETS_DIR / args.file
            if not file_path.exists():
                print(f"File not found: {args.file}")
                sys.exit(1)

        manifest = load_manifest()
        auto_tag_asset(file_path, manifest, force=args.reprocess)
        save_manifest(manifest)
    else:
        # Tag all assets
        auto_tag_all(force=args.reprocess)


def cmd_validate(args):
    """Validate that all manifest entries point to existing files."""
    manifest = load_manifest()
    assets = manifest.get("assets", {})

    missing = []
    valid = 0

    for path in assets:
        full_path = ASSETS_DIR / path
        if full_path.exists():
            valid += 1
        else:
            missing.append(path)

    print(f"Manifest validation:")
    print(f"  Valid: {valid}")
    print(f"  Missing: {len(missing)}")

    if missing:
        print("\nMissing files:")
        for path in missing:
            print(f"  - {path}")

        if args.fix:
            for path in missing:
                del manifest["assets"][path]
            save_manifest(manifest)
            print(f"\nRemoved {len(missing)} missing entries from manifest.")


def main():
    parser = argparse.ArgumentParser(description="Asset Tagger CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # auto-tag (AI-powered)
    autotag_parser = subparsers.add_parser("auto-tag", help="AI-powered auto-tagging (Google Cloud)")
    autotag_parser.add_argument("--file", help="Tag a specific file only")
    autotag_parser.add_argument("--reprocess", action="store_true", help="Re-tag already tagged assets")

    # scan
    scan_parser = subparsers.add_parser("scan", help="Scan for untagged assets")
    scan_parser.add_argument("--auto", action="store_true", help="Auto-suggest keywords from path")

    # add
    add_parser = subparsers.add_parser("add", help="Add/update asset tags")
    add_parser.add_argument("path", help="Path to asset (relative to assets/)")
    add_parser.add_argument("keywords", help="Comma-separated keywords")
    add_parser.add_argument("--mood", help="Asset mood (bright/calm/medical/etc)")

    # list
    subparsers.add_parser("list", help="List all tagged assets")

    # remove
    remove_parser = subparsers.add_parser("remove", help="Remove asset from manifest")
    remove_parser.add_argument("path", help="Path to asset")

    # search
    search_parser = subparsers.add_parser("search", help="Search assets by keyword")
    search_parser.add_argument("query", help="Comma-separated keywords to search")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results")
    search_parser.add_argument("--type", help="Content type filter (health/nutrition)")

    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate manifest entries")
    validate_parser.add_argument("--fix", action="store_true", help="Remove missing entries")

    args = parser.parse_args()

    if args.command == "auto-tag":
        cmd_auto_tag(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "validate":
        cmd_validate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
