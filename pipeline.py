#!/usr/bin/env python3
"""
Social Media Content Pipeline
Generates and posts motivational/fact content to social platforms.

Features:
- Multi-scene videos with crossfade transitions
- Word-synced subtitles with keyword highlighting
- Video and image background support
- Hook-first content for better retention

Usage:
    python pipeline.py --type motivation
    python pipeline.py --type fact
    python pipeline.py --type motivation --platforms youtube,instagram
    python pipeline.py --type fact --dry-run
"""
import argparse
import sys
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import OUTPUT_DIR, ASSETS_DIR, BACKGROUNDS_DIR, MUSIC_DIR, DEFAULT_HASHTAGS_MOTIVATION, DEFAULT_HASHTAGS_FACTS, DEFAULT_HASHTAGS_HEALTH
from generators.script_gen import generate_content
from generators.image_gen import create_image
from generators.voice_gen import generate_voice
from generators.video_gen import assemble_video, segment_into_scenes
from generators.subtitle_gen import generate_subtitles, extract_keywords_auto


def check_assets_available():
    """
    Verify that assets are accessible (Google Drive mounted if using cloud storage).
    Returns True if ready, False if not.
    """
    errors = []

    # Check if assets directory exists
    if not ASSETS_DIR.exists():
        errors.append(f"Assets directory not found: {ASSETS_DIR}")

    # Check for backgrounds
    if not BACKGROUNDS_DIR.exists():
        errors.append(f"Backgrounds directory not found: {BACKGROUNDS_DIR}")
    else:
        bg_files = list(BACKGROUNDS_DIR.glob("**/*.*"))
        if not bg_files:
            errors.append(f"No background files found in: {BACKGROUNDS_DIR}")

    # Check for music
    if not MUSIC_DIR.exists():
        errors.append(f"Music directory not found: {MUSIC_DIR}")
    else:
        music_files = list(MUSIC_DIR.glob("**/*.mp3")) + list(MUSIC_DIR.glob("**/*.wav"))
        if not music_files:
            errors.append(f"No music files found in: {MUSIC_DIR}")

    if errors:
        print("\n" + "=" * 50)
        print("  ERROR: Assets not accessible!")
        print("=" * 50)
        for err in errors:
            print(f"  - {err}")
        print("")

        # Check if this looks like a mount issue
        if "/mnt/gdrive" in str(ASSETS_DIR) or "/mnt/" in str(ASSETS_DIR):
            print("  Looks like Google Drive may not be mounted.")
            print("  Run: ./scripts/mount_gdrive.sh mount")
            print("  Or:  rclone mount gdrive:Social_Maker /mnt/gdrive --daemon --vfs-cache-mode full")
        print("=" * 50 + "\n")
        return False

    return True


def run_pipeline(content_type="motivation", platforms=None, dry_run=False):
    """
    Run the full content pipeline:
    1. Generate script (quote/fact + caption + hashtags + hook)
    2. Create image (quote card / fact graphic)
    3. Generate voiceover WITH timestamps
    4. Generate ASS subtitle file
    5. Calculate scene boundaries
    6. Assemble multi-scene video with subtitles
    7. Post to platforms (unless dry_run)
    """
    # Check assets are accessible before starting
    if not check_assets_available():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{content_type}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"  Content Pipeline — {content_type.upper()}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    # Step 1: Generate script
    print("[1/6] Generating script...")
    try:
        content = generate_content(content_type)
        # Save content metadata
        with open(run_dir / "content.json", "w") as f:
            json.dump(content, f, indent=2)
        if content_type == "motivation":
            print(f'  Quote: "{content["quote"]}"')
            print(f'  Author: {content.get("author", "Unknown")}')
        elif content_type == "health":
            print(f'  Hook: "{content.get("hook", "")}"')
            print(f'  Topic: {content.get("topic", "")}')
            benefits = content.get("benefits", [])
            print(f'  Benefits: {len(benefits)} items')
            keywords = content.get("keywords", [])
            print(f'  Keywords: {keywords}')
        else:
            print(f'  Fact: "{content["fact"]}"')
        print(f'  Caption: {content["caption"]}')
        if "hook" in content and content_type != "health":
            print(f'  Hook: "{content["hook"]}"')
    except Exception as e:
        print(f"  ERROR generating script: {e}")
        return None

    # Step 2: Create image (for thumbnail/poster)
    print("\n[2/6] Creating image...")
    try:
        image_path = create_image(content, output_path=run_dir / "image.png")
        print(f"  Saved: {image_path}")
    except Exception as e:
        print(f"  ERROR creating image: {e}")
        return None

    # Step 3: Generate voiceover WITH timestamps
    print("\n[3/6] Generating voiceover with timestamps...")
    try:
        result = generate_voice(content, output_path=run_dir / "voiceover.mp3", with_timestamps=True)
        if isinstance(result, tuple):
            voice_path, word_timing, voiceover_text = result
            print(f"  Saved: {voice_path}")
            print(f"  Word timing: {len(word_timing)} words captured")
        else:
            # Fallback if timestamps not available
            voice_path = result
            word_timing = []
            voiceover_text = content.get("voiceover", "")
            print(f"  Saved: {voice_path}")
            print(f"  Warning: No word timing available")

        # Save timing data for debugging
        with open(run_dir / "word_timing.json", "w") as f:
            json.dump(word_timing, f, indent=2)

    except Exception as e:
        print(f"  ERROR generating voiceover: {e}")
        return None

    # Step 4: Generate subtitles
    print("\n[4/6] Generating subtitles...")
    try:
        # Get keywords from content or auto-extract
        keywords = content.get("keywords", [])
        if not keywords:
            keywords = extract_keywords_auto(voiceover_text, content)
            print(f"  Auto-extracted keywords: {keywords}")
        else:
            print(f"  Using content keywords: {keywords}")

        subtitle_path = generate_subtitles(
            word_timing,
            keywords=keywords,
            output_path=run_dir / "subtitles.ass",
        )
        print(f"  Saved: {subtitle_path}")
    except Exception as e:
        print(f"  ERROR generating subtitles: {e}")
        subtitle_path = None  # Continue without subtitles

    # Step 5: Calculate scene boundaries
    print("\n[5/6] Calculating scene boundaries...")
    try:
        # Get voice duration for scene calculation
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(voice_path)],
            capture_output=True, text=True,
        )
        info = json.loads(result.stdout)
        voice_duration = float(info["format"]["duration"])
        total_duration = voice_duration + 2  # 1s intro + 1s outro padding

        scenes = segment_into_scenes(word_timing, total_duration, target_scenes=4)
        print(f"  Created {len(scenes)} scenes:")
        for i, scene in enumerate(scenes):
            print(f"    Scene {i+1}: {scene['start']:.1f}s - {scene['end']:.1f}s")
    except Exception as e:
        print(f"  ERROR calculating scenes: {e}")
        scenes = None  # Will use default in video_gen

    # Step 6: Assemble multi-scene video
    print("\n[6/7] Assembling multi-scene video...")
    try:
        video_result = assemble_video(
            voice_path=voice_path,
            output_path=run_dir / "video.mp4",
            content_type=content_type,
            word_timing=word_timing,
            keywords=keywords if 'keywords' in dir() else None,
            subtitle_path=subtitle_path,
            scenes=scenes,
        )
        # Handle both new dict return and legacy path return
        if isinstance(video_result, dict):
            video_path = video_result["video_path"]
            backgrounds_used = video_result["backgrounds_used"]
            music_file = video_result["music_file"]
            total_duration = video_result["total_duration"]
            scenes = video_result["scenes"]
        else:
            video_path = video_result
            backgrounds_used = []
            music_file = None
            total_duration = None
        print(f"  Saved: {video_path}")
    except Exception as e:
        print(f"  ERROR assembling video: {e}")
        return None

    # Step 7: Optional Premiere Pro export
    premiere_package_path = None
    if not dry_run and backgrounds_used and total_duration:
        try:
            export_premiere = input("\nCreate Premiere Pro version? (y/n): ").strip().lower()
            if export_premiere == 'y':
                print("\n[7/8] Creating Premiere Pro package...")
                from generators.premiere_export import create_premiere_package
                premiere_package_path = create_premiere_package(
                    output_dir=run_dir,
                    scenes=scenes,
                    backgrounds_used=backgrounds_used,
                    music_file=music_file,
                    voiceover_path=voice_path,
                    subtitle_path=subtitle_path,
                    word_timing=word_timing,
                    content=content,
                    total_duration=total_duration,
                )
                print(f"  Premiere package: {premiere_package_path}")
            else:
                print("\n[7/8] Skipping Premiere export")
        except Exception as e:
            print(f"  ERROR creating Premiere package: {e}")
    elif dry_run and backgrounds_used and total_duration:
        # In dry-run mode, auto-create premiere package without prompting
        print("\n[7/8] Creating Premiere Pro package (dry-run mode)...")
        try:
            from generators.premiere_export import create_premiere_package
            premiere_package_path = create_premiere_package(
                output_dir=run_dir,
                scenes=scenes,
                backgrounds_used=backgrounds_used,
                music_file=music_file,
                voiceover_path=voice_path,
                subtitle_path=subtitle_path,
                word_timing=word_timing,
                content=content,
                total_duration=total_duration,
            )
            print(f"  Premiere package: {premiere_package_path}")
        except Exception as e:
            print(f"  ERROR creating Premiere package: {e}")

    # Step 8: Post to platforms
    if dry_run:
        print("\n[8/8] DRY RUN — skipping posting")
        print(f"  Content ready in: {run_dir}")
    else:
        print("\n[8/8] Posting to platforms...")
        if platforms is None:
            platforms = []

        # Build posting metadata
        if content_type == "motivation":
            default_hashtags = DEFAULT_HASHTAGS_MOTIVATION
        elif content_type == "health":
            default_hashtags = DEFAULT_HASHTAGS_HEALTH
        else:
            default_hashtags = DEFAULT_HASHTAGS_FACTS
        all_hashtags = content.get("hashtags", []) + default_hashtags
        hashtag_str = " ".join(all_hashtags[:15])  # max 15 hashtags

        post_title = content.get("quote", content.get("fact", ""))[:100]
        post_description = f"{content['caption']}\n\n{hashtag_str}"

        for platform in platforms:
            try:
                if platform == "youtube":
                    from posters.youtube import upload_to_youtube
                    url = upload_to_youtube(video_path, post_title, post_description)
                    print(f"  YouTube: {url}")
                elif platform == "instagram":
                    from posters.instagram import upload_to_instagram
                    url = upload_to_instagram(video_path, post_description)
                    print(f"  Instagram: {url}")
                elif platform == "tiktok":
                    from posters.tiktok import upload_to_tiktok
                    url = upload_to_tiktok(video_path, post_description)
                    print(f"  TikTok: {url}")
                else:
                    print(f"  Unknown platform: {platform}")
            except Exception as e:
                print(f"  ERROR posting to {platform}: {e}")

    # Summary
    print(f"\n{'='*50}")
    print(f"  Pipeline complete!")
    print(f"  Output: {run_dir}")
    print(f"{'='*50}\n")

    return {
        "content": content,
        "image": str(image_path),
        "voice": str(voice_path),
        "video": str(video_path),
        "subtitles": str(subtitle_path) if subtitle_path else None,
        "word_timing": word_timing,
        "scenes": scenes,
        "output_dir": str(run_dir),
        "premiere_package": str(premiere_package_path) if premiere_package_path else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Social Media Content Pipeline")
    parser.add_argument(
        "--type", choices=["motivation", "fact", "health"], default="motivation",
        help="Type of content to generate",
    )
    parser.add_argument(
        "--platforms", type=str, default="",
        help="Comma-separated platforms to post to (youtube,instagram,tiktok)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate content without posting",
    )
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    result = run_pipeline(
        content_type=args.type,
        platforms=platforms if platforms else None,
        dry_run=args.dry_run or not platforms,
    )

    if result is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
