#!/usr/bin/env python3
"""
Social Media Content Pipeline
Generates and posts motivational/fact content to social platforms.

NEW FEATURES (Updated):
1. VIDEO ID SYSTEM: VIDEO-[TOPIC]-[YYYYMMDD]-[3 digit]
2. VERSION CONTROL: v1, v2, v3 with change logs
3. FILE NAMING: [VIDEO-ID]_v[number].mp4
4. SCRIPT REUSE: Specify existing Video ID to reuse script
5. ENHANCED SCENES: Full text, visual direction, text animation
6. FEEDBACK MEMORY: Track likes/dislikes per version

Usage:
    python pipeline.py --type fact --dry-run
    python pipeline.py --type fact --video-id VIDEO-VENUS_DAY-20260210-001 --version 2
    python pipeline.py --type motivation --platforms youtube,tiktok
"""
import argparse
import sys
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    OUTPUT_DIR, ASSETS_DIR, BACKGROUNDS_DIR, MUSIC_DIR,
    DEFAULT_HASHTAGS_MOTIVATION, DEFAULT_HASHTAGS_FACTS, DEFAULT_HASHTAGS_HEALTH,
    DEFAULT_HASHTAGS_STORIES,
    VISUAL_STYLE, KINETIC_TEXT_ENABLED, COLOR_GRADING_ENABLED,
    HOOK_FONT_SIZE, BODY_FONT_SIZE,
)
from generators.script_gen import generate_content
from generators.image_gen import create_image
from generators.voice_gen import generate_voice
from generators.video_gen import assemble_video, segment_into_scenes
from generators.subtitle_gen import generate_subtitles, extract_keywords_auto
from generators.video_id_manager import (
    generate_video_id, get_output_folder, get_video_filename,
    VideoRecord, VideoVersion, generate_change_log,
)
from generators.scene_builder import (
    build_scenes_from_word_timing, format_scene_report, Scene,
    create_zack_d_visual_direction, get_tone_from_text,
    generate_narrative_prompts,
)

# Import Zack D Films style components
try:
    from generators.visual_style import get_style, enhance_visual_direction
    from generators.kinetic_text import (
        generate_kinetic_subtitles, KineticTextConfig,
    )
    STYLE_COMPONENTS_AVAILABLE = True
except ImportError:
    STYLE_COMPONENTS_AVAILABLE = False


def run_story_pipeline(
    genre: str = "thriller",
    mode: str = "quick",
    topic: str = None,
    platforms: list = None,
    dry_run: bool = True,
):
    """
    Run the short stories pipeline via the story orchestrator.

    This is a dedicated pipeline for short story content that uses the
    5-agent orchestration system:
    1. Story Creator - Generate story with characters
    2. Voice Script Generator - Add pacing and emotional markers
    3. Scene Planner - Create visual scene breakdown
    4. Visual Prompt Builder - Generate Midjourney prompts
    5. QA Reviewer - Validate consistency

    Args:
        genre: Story genre (thriller, mystery, comedy, horror, drama, romance)
        mode: "quick" for automated, "detailed" for step-by-step with manual visuals
        topic: Optional topic/seed for the story
        platforms: List of platforms to post to
        dry_run: If True, generate without posting

    Returns:
        dict with story_id, output_dir, and other results
    """
    from generators.story_orchestrator import StoryOrchestrator

    print(f"\n{'='*50}")
    print(f"  Short Stories Pipeline — {genre.upper()}")
    print(f"  Mode: {mode}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    orchestrator = StoryOrchestrator()

    if mode == "detailed":
        result = orchestrator.run_detailed(
            genre=genre,
            topic=topic,
            visual_mode="manual",
            verbose=True,
        )
    else:
        result = orchestrator.run_quick(
            genre=genre,
            topic=topic,
            verbose=True,
        )

    if not result.success:
        print(f"\nStory generation failed: {result.errors}")
        return None

    # Handle posting if not dry_run
    if not dry_run and platforms:
        print(f"\n[POST] Posting to platforms: {', '.join(platforms)}")
        # Note: Video assembly from Midjourney images would happen here
        # For now, we just generate the story and prompts
        print("  Note: Full video assembly requires manual Midjourney image generation")
        print(f"  See: {result.output_dir}/Visuals-Midjourney.md")

    return {
        "story_id": result.story_id,
        "output_dir": result.output_dir,
        "story": result.story.to_dict() if result.story else None,
        "voice_script": result.voice_script.to_dict() if result.voice_script else None,
        "scene_plan": result.scene_plan.to_dict() if result.scene_plan else None,
        "files_created": result.files_created,
        "success": result.success,
    }


def check_gdrive_mounted():
    """
    Verify Google Drive is mounted. Stop if not available.

    Returns True if gdrive is mounted OR if OUTPUT_DIR is local (not on gdrive).
    Returns False and prints error if gdrive is expected but not mounted.
    """
    import subprocess

    # Check if OUTPUT_DIR is supposed to be on gdrive
    if "/mnt/gdrive" not in str(OUTPUT_DIR) and "/mnt/" not in str(OUTPUT_DIR):
        # Using local storage, no mount check needed
        return True

    # Check if gdrive is mounted
    try:
        result = subprocess.run(["mount"], capture_output=True, text=True)
        if "gdrive" not in result.stdout and "/mnt/gdrive" not in result.stdout:
            print("\n" + "=" * 50)
            print("  ERROR: Google Drive not mounted!")
            print("=" * 50)
            print("  OUTPUT_DIR is set to Google Drive but it's not mounted.")
            print("")
            print("  To mount, run:")
            print("    ./scripts/mount_gdrive.sh mount")
            print("")
            print("  Or use local storage by changing .env:")
            print("    OUTPUT_DIR=/home/markhuerta/Project/socal_maker/output")
            print("=" * 50 + "\n")
            return False
    except Exception as e:
        print(f"  Warning: Could not check mount status: {e}")
        # Continue anyway - might work

    return True


def check_assets_available():
    """
    Verify that assets are accessible (Google Drive mounted if using cloud storage).
    Returns True if ready, False if not.
    """
    errors = []

    # First, check gdrive mount if using cloud storage
    if not check_gdrive_mounted():
        return False

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


def run_pipeline(content_type="motivation", platforms=None, dry_run=False,
                 video_id=None, version_num=None, changes=None,
                 genre=None, orchestration_mode=None, topic=None):
    """
    Run the full content pipeline with VIDEO ID and VERSION CONTROL.

    PIPELINE STEPS:
    1. Generate/reuse script (quote/fact + caption + hashtags + hook)
    2. Create image (quote card / fact graphic)
    3. Generate voiceover WITH timestamps
    4. Generate ASS subtitle file with text animations
    5. Calculate enhanced scene structure
    6. Assemble multi-scene video with subtitles
    7. Post to platforms (unless dry_run)
    8. Save version record with change log

    VIDEO ID FORMAT: VIDEO-[TOPIC]-[YYYYMMDD]-[3 digit]
    VERSION FORMAT: v1, v2, v3, etc.
    FILE NAMING: [VIDEO-ID]_v[number].mp4

    Args:
        content_type: "motivation", "fact", "health", or "short_stories"
        platforms: List of platforms to post to
        dry_run: If True, generate without posting
        video_id: Existing Video ID to reuse script from
        version_num: Specific version to create (auto-increments if None)
        changes: List of changes for this version's change log
        genre: Story genre (for short_stories)
        orchestration_mode: "quick" or "detailed" (for short_stories)
        topic: Story topic/seed (for short_stories)
    """
    # Handle short_stories via dedicated orchestrator
    if content_type == "short_stories":
        return run_story_pipeline(
            genre=genre or "thriller",
            mode=orchestration_mode or "quick",
            topic=topic,
            platforms=platforms,
            dry_run=dry_run,
        )

    # Check assets are accessible before starting
    if not check_assets_available():
        return None

    # Handle script reuse if video_id provided
    existing_record = None
    if video_id:
        existing_record = VideoRecord.load(video_id)
        if existing_record:
            print(f"\n  Reusing script from: {video_id}")
        else:
            print(f"\n  Warning: Video ID {video_id} not found, generating new content")

    # Create run directory (will use Video ID naming)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_run_dir = OUTPUT_DIR / f"{content_type}_{timestamp}"
    temp_run_dir.mkdir(parents=True, exist_ok=True)
    run_dir = temp_run_dir  # Will be updated after Video ID is generated

    # Track content for intelligent naming later
    intelligent_dir_name = None

    print(f"\n{'='*50}")
    print(f"  Content Pipeline — {content_type.upper()}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if VISUAL_STYLE == "zack_d_films":
        print(f"  Style: Zack D Films (3D Animation)")
        print(f"  Kinetic Text: {'Enabled' if KINETIC_TEXT_ENABLED else 'Disabled'}")
        print(f"  Color Grading: {'Enabled' if COLOR_GRADING_ENABLED else 'Disabled'}")
    print(f"{'='*50}\n")

    # Step 1: Generate or reuse script
    print("[1/8] Generating script...")
    video_record = None
    current_version = None

    try:
        if existing_record and existing_record.script:
            # REUSE existing script
            content = existing_record.script
            video_record = existing_record
            print(f"  (reusing script from {video_id})")
        else:
            # Generate new content
            content = generate_content(content_type)

        # Save content metadata
        with open(run_dir / "content.json", "w") as f:
            json.dump(content, f, indent=2)

        # Display content info
        if content_type == "motivation":
            print(f'  Quote: "{content.get("quote", content.get("fact", ""))}"')
            print(f'  Author: {content.get("author", "Unknown")}')
        elif content_type == "health":
            print(f'  Hook: "{content.get("hook", "")}"')
            print(f'  Topic: {content.get("topic", "")}')
            benefits = content.get("benefits", [])
            print(f'  Benefits: {len(benefits)} items')
            keywords = content.get("keywords", [])
            print(f'  Keywords: {keywords}')
        else:
            print(f'  Fact: "{content.get("fact", "")}"')
        print(f'  Caption: {content.get("caption", "")}')
        if "hook" in content and content_type != "health":
            print(f'  Hook: "{content["hook"]}"')

        # Generate Video ID if not reusing
        script_text = content.get("voiceover", "") or content.get("fact", "") or content.get("quote", "")
        hook_text = content.get("hook", "")

        if not video_id:
            video_id = generate_video_id(script_text, hook_text)
            print(f"\n  VIDEO ID: {video_id}")

        # Create or update video record
        if not video_record:
            video_record = VideoRecord(video_id)
            video_record.set_script(
                fact=content.get("fact", content.get("quote", "")),
                hook=hook_text,
                caption=content.get("caption", ""),
                voiceover_text=script_text,
                scenes=[],  # Will be updated after scene building
            )

        # Create new version
        current_version = video_record.create_version()
        if changes:
            for change in changes:
                current_version.add_change(change)
        else:
            current_version.add_change("Initial generation" if video_record.current_version == 1 else "New version created")

        print(f"  Version: v{current_version.version_number}")

        # Set up output directory with Video ID naming
        run_dir = get_output_folder(video_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        # Clean up temp directory if different
        if temp_run_dir != run_dir and temp_run_dir.exists():
            import shutil
            for item in temp_run_dir.iterdir():
                shutil.move(str(item), str(run_dir / item.name))
            temp_run_dir.rmdir()

    except Exception as e:
        print(f"  ERROR generating script: {e}")
        import traceback
        traceback.print_exc()
        return None

    # Step 2: Create image (for thumbnail/poster)
    print("\n[2/8] Creating image...")
    try:
        image_path = create_image(content, output_path=run_dir / "image.png")
        print(f"  Saved: {image_path}")
    except Exception as e:
        print(f"  ERROR creating image: {e}")
        return None

    # Step 3: Generate voiceover WITH timestamps
    print("\n[3/8] Generating voiceover with timestamps...")
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

    # Step 4: Generate subtitles (clean, stable captions)
    print("\n[4/8] Generating subtitles...")
    try:
        # Get keywords from content or auto-extract
        keywords = content.get("keywords", [])
        if not keywords:
            keywords = extract_keywords_auto(voiceover_text, content)
            print(f"  Auto-extracted keywords: {keywords}")
        else:
            print(f"  Using content keywords: {keywords}")

        # Get hook text for kinetic subtitles
        hook_text = content.get("hook", "")

        # Use clean subtitle generator for stability
        # Rules: max 6 words/line, max 2 lines, no overlap, fade only
        print(f"  Using clean captions (stable, no overlap)")
        subtitle_path = generate_subtitles(
            word_timing,
            keywords=keywords,
            output_path=run_dir / "subtitles.ass",
        )
        print(f"  Saved: {subtitle_path}")
    except Exception as e:
        print(f"  ERROR generating subtitles: {e}")
        import traceback
        traceback.print_exc()
        subtitle_path = None  # Continue without subtitles

    # Step 5: Calculate enhanced scene structure (with Zack D Films style if enabled)
    print("\n[5/8] Building enhanced scene structure...")
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
        total_duration = voice_duration + 4  # 1s intro + 3s outro padding

        # Detect content tone for visual style
        content_tone = get_tone_from_text(voiceover_text)
        print(f"  Detected tone: {content_tone}")
        print(f"  Visual style: {VISUAL_STYLE}")

        # Calculate target scenes based on duration (~5s per scene)
        target_scene_count = max(8, min(15, int(total_duration / 5)))
        print(f"  Target scenes: {target_scene_count} (for {total_duration:.1f}s video)")

        # Build enhanced scenes with all required fields
        enhanced_scenes = build_scenes_from_word_timing(
            word_timing=word_timing,
            total_duration=total_duration,
            voiceover_text=voiceover_text,
            target_scenes=target_scene_count,
        )

        # Convert to dict format for video_gen compatibility
        scenes = []
        total_scenes = len(enhanced_scenes)

        for idx, es in enumerate(enhanced_scenes):
            # Use Zack D Films keyword-based visual direction
            if VISUAL_STYLE == "zack_d_films":
                visual_direction = create_zack_d_visual_direction(
                    scene_text=es.voiceover_text,
                    keywords=es.keywords,
                    scene_index=idx,
                    total_scenes=total_scenes,
                    tone=content_tone,
                )
            else:
                visual_direction = es.visual_direction

            scenes.append({
                "start": es.start_time,
                "end": es.end_time,
                "words": [],  # Populated separately
                "keywords": es.keywords,
                "on_screen_text": es.on_screen_text,
                "voiceover_text": es.voiceover_text,
                "visual_direction": visual_direction,
                "text_animation": es.text_animation.value,
                "tone": content_tone,
            })

        # Print scene breakdown
        print(f"  Created {len(scenes)} scenes (starting at Scene 1):")
        for i, scene in enumerate(scenes):
            duration = scene['end'] - scene['start']
            print(f"    Scene {i+1}: {scene['start']:.1f}s - {scene['end']:.1f}s ({duration:.1f}s)")
            if scene.get('on_screen_text'):
                print(f"      Text: \"{scene['on_screen_text'][:50]}\"")
            if scene.get('text_animation'):
                print(f"      Animation: {scene['text_animation']}")

        # Save enhanced scene report (markdown for machine parsing)
        scene_report = format_scene_report(enhanced_scenes)
        with open(run_dir / "scene_breakdown.md", "w") as f:
            f.write(scene_report)
        print(f"  Scene report: {run_dir / 'scene_breakdown.md'}")

        # Also save styled DOCX (for human reading)
        try:
            from generators.document_gen import generate_scene_breakdown_docx
            docx_path = generate_scene_breakdown_docx(
                output_path=run_dir / "scene_breakdown.md",
                scenes=enhanced_scenes,
                video_id=video_id,
                total_duration=total_duration,
            )
            if docx_path:
                print(f"  Scene report (styled): {docx_path}")
        except ImportError:
            pass  # python-docx not installed

        # Update version with scene count
        if current_version:
            current_version.scene_count = len(scenes)

    except Exception as e:
        print(f"  ERROR building scenes: {e}")
        import traceback
        traceback.print_exc()
        scenes = None  # Will use default in video_gen

    # Step 6: Assemble multi-scene video with version naming
    print("\n[6/8] Assembling multi-scene video...")
    try:
        # Extract script text for file naming
        script_text = voiceover_text if voiceover_text else content.get("voiceover", "")
        hook_text = content.get("hook", "")

        # Generate versioned filename: [VIDEO-ID]_v[number].mp4
        version_num = current_version.version_number if current_version else 1
        video_filename = get_video_filename(video_id, version_num)
        video_output_path = run_dir / video_filename

        print(f"  Output file: {video_filename}")

        video_result = assemble_video(
            voice_path=voice_path,
            output_path=video_output_path,
            content_type=content_type,
            word_timing=word_timing,
            keywords=keywords if 'keywords' in dir() else None,
            subtitle_path=subtitle_path,
            scenes=scenes,
            script_text=script_text,
            hook_text=hook_text,
            validate=True,  # Run pre-export validation
            strict_matching=True,  # Enforce visual matching threshold
        )
        # Handle both new dict return and legacy path return
        if isinstance(video_result, dict):
            video_path = video_result["video_path"]
            backgrounds_used = video_result["backgrounds_used"]
            music_file = video_result["music_file"]
            total_duration = video_result["total_duration"]
            scenes = video_result["scenes"]
            match_results = video_result.get("match_results", [])
            flagged_scenes = video_result.get("flagged_scenes", [])

            # Report flagged scenes
            if flagged_scenes:
                print(f"\n  NOTE: Scenes {flagged_scenes} need better visual matching")
                print("  Consider adding relevant footage to assets folder")
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

    # Step 7: Post to platforms
    if dry_run:
        print("\n[7/8] DRY RUN — skipping posting")
        print(f"  Content ready in: {run_dir}")
    else:
        print("\n[7/8] Posting to platforms...")
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

    # Step 8: Save version record and change log
    print("\n[8/8] Saving version record...")
    try:
        if current_version:
            current_version.duration = total_duration if total_duration else 0
            current_version.video_path = str(video_path)

        if video_record:
            # Update script with scene data
            video_record.script["scenes"] = [
                {"scene": i + 1, **s} for i, s in enumerate(scenes or [])
            ]
            video_record.save()

            # Generate and save change log
            change_log = generate_change_log(video_record)
            with open(run_dir / "CHANGELOG.md", "w") as f:
                f.write(change_log)
            print(f"  Change log: {run_dir / 'CHANGELOG.md'}")
            print(f"  Version record saved for: {video_id}")

    except Exception as e:
        print(f"  Warning: Could not save version record: {e}")

    # Summary
    print(f"\n{'='*50}")
    print(f"  Pipeline complete!")
    print(f"  VIDEO ID: {video_id}")
    print(f"  Version: v{current_version.version_number if current_version else 1}")
    print(f"  Output: {run_dir}")
    print(f"  Video: {video_filename if 'video_filename' in dir() else 'video.mp4'}")
    print(f"{'='*50}\n")

    return {
        "video_id": video_id,
        "version": current_version.version_number if current_version else 1,
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
    parser = argparse.ArgumentParser(
        description="Social Media Content Pipeline with Video ID and Version Control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py --type fact --dry-run
  python pipeline.py --type fact --video-id VIDEO-VENUS_DAY-20260210-001 --version 2
  python pipeline.py --type motivation --platforms youtube,tiktok
  python pipeline.py --type fact --changes "Improved pacing" "New visuals"
        """
    )
    parser.add_argument(
        "--type", choices=["motivation", "fact", "health"], default="fact",
        help="Type of content to generate (default: fact)",
    )
    parser.add_argument(
        "--platforms", type=str, default="",
        help="Comma-separated platforms to post to (youtube,instagram,tiktok)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate content without posting",
    )
    parser.add_argument(
        "--video-id", type=str, default=None,
        help="Existing Video ID to reuse script from (e.g., VIDEO-VENUS_DAY-20260210-001)",
    )
    parser.add_argument(
        "--version", type=int, default=None,
        help="Specific version number to create (auto-increments if not specified)",
    )
    parser.add_argument(
        "--changes", nargs="+", type=str, default=None,
        help="List of changes for this version's change log",
    )
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    result = run_pipeline(
        content_type=args.type,
        platforms=platforms if platforms else None,
        dry_run=args.dry_run or not platforms,
        video_id=args.video_id,
        version_num=args.version,
        changes=args.changes,
    )

    if result is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
