#!/usr/bin/env python3
"""
SoCal Maker CLI

Unified command-line interface for niche training, content generation, and scheduling.

Usage:
    python cli.py train add-competitor @factspage tiktok
    python cli.py train analyze "Did you know octopuses have 3 hearts?"
    python cli.py train patterns
    python cli.py train style-guide --generate

    python cli.py generate fact --dry-run
    python cli.py generate fact --platforms youtube,tiktok

    python cli.py schedule status
    python cli.py schedule once fact --platforms youtube
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def cmd_train(args):
    """Handle training subcommands."""
    from training.competitor_analyzer import CompetitorAnalyzer
    from training.niche_config import NicheConfig

    analyzer = CompetitorAnalyzer()

    if args.action == "add-competitor":
        if not args.handle or not args.platform:
            print("Usage: cli.py train add-competitor <handle> <platform>")
            print("  Example: cli.py train add-competitor @factspage tiktok")
            return 1

        result = analyzer.add_competitor(args.handle, args.platform)
        if "error" in result:
            print(f"Error: {result['error']}")
            return 1
        print(f"Added {result['handle']} ({result['platform']})")
        return 0

    elif args.action == "remove-competitor":
        if not args.handle:
            print("Usage: cli.py train remove-competitor <handle>")
            return 1

        removed = analyzer.remove_competitor(args.handle)
        if removed:
            print(f"Removed {args.handle}")
        else:
            print(f"Not found: {args.handle}")
        return 0 if removed else 1

    elif args.action == "list-competitors":
        competitors = analyzer.list_competitors()
        if competitors:
            print(f"\nTracking {len(competitors)} competitors:\n")
            for c in competitors:
                print(f"  {c['handle']} ({c['platform']}) - {c.get('samples_analyzed', 0)} samples")
        else:
            print("No competitors registered yet.")
            print("Add one with: cli.py train add-competitor @handle platform")
        return 0

    elif args.action == "analyze":
        if not args.text:
            print("Usage: cli.py train analyze <text> [--platform tiktok] [--competitor @handle]")
            return 1

        platform = args.platform or "tiktok"
        competitor = args.competitor

        print(f"Analyzing content from {platform}...")
        result = analyzer.analyze_content(args.text, platform, competitor)

        if "error" in result:
            print(f"Error: {result['error']}")
            return 1

        print("\nAnalysis Results:")
        print("-" * 40)
        print(f"Hook Type: {result.get('hook', {}).get('type', 'N/A')}")
        print(f"Hook Technique: {result.get('hook', {}).get('technique', 'N/A')}")
        print(f"Category: {result.get('content_elements', {}).get('category', 'N/A')}")

        virality = result.get("virality_factors", {})
        print(f"\nVirality Scores:")
        print(f"  Scroll Stopper: {virality.get('scroll_stopper_score', 'N/A')}/10")
        print(f"  Shareability: {virality.get('shareability_score', 'N/A')}/10")
        print(f"  Comment Bait: {virality.get('comment_bait_score', 'N/A')}/10")
        print(f"  Save Worthy: {virality.get('save_worthiness', 'N/A')}/10")

        print(f"\nPower Words: {', '.join(result.get('vocabulary', {}).get('power_words', []))}")
        return 0

    elif args.action == "patterns":
        print("Extracting patterns from analyzed samples...")
        patterns = analyzer.extract_patterns()

        if "error" in patterns:
            print(f"Error: {patterns['error']}")
            return 1

        print(f"\nPatterns from {patterns.get('sample_count', 0)} samples:")
        print("-" * 40)

        hook_patterns = patterns.get("hook_patterns", {})
        print("\nTop Hook Types:")
        for hook_type, count in hook_patterns.get("most_common_types", [])[:5]:
            print(f"  {hook_type}: {count}")

        print("\nTop Power Words:")
        top_words = patterns.get("vocabulary", {}).get("top_power_words", [])[:10]
        for word, count in top_words:
            print(f"  {word}: {count}")

        print("\nCategories:")
        for cat, count in patterns.get("categories", {}).items():
            print(f"  {cat}: {count}")

        return 0

    elif args.action == "recommend":
        print("Generating recommendations from patterns...")
        recommendations = analyzer.get_recommendations()

        if "error" in recommendations:
            print(f"Error: {recommendations['error']}")
            return 1

        print("\nRecommendations:")
        print("-" * 40)
        print(f"Based on {recommendations.get('based_on_samples', 0)} samples\n")

        print("Preferred Hook Types:")
        for hook_type in recommendations.get("hooks", {}).get("preferred_types", []):
            print(f"  - {hook_type}")

        print("\nSuggested Power Words to Add:")
        for word in recommendations.get("vocabulary", {}).get("add_power_words", []):
            print(f"  - {word}")

        print("\nFocus Categories:")
        for cat in recommendations.get("focus_categories", []):
            print(f"  - {cat}")

        return 0

    elif args.action == "style-guide":
        niche = args.niche or "fun_facts"
        config = NicheConfig(niche)

        if args.generate:
            print("Generating style guide from patterns...")
            recommendations = analyzer.get_recommendations()
            print(json.dumps(recommendations, indent=2))
        else:
            print(f"\nStyle Guide: {niche}")
            print("=" * 50)
            print(config.get_prompt_additions())

        return 0

    elif args.action == "clear":
        analyzer.clear_samples()
        print("All samples cleared.")
        return 0

    else:
        print(f"Unknown training action: {args.action}")
        print("\nAvailable actions:")
        print("  add-competitor    - Add competitor to track")
        print("  remove-competitor - Remove competitor")
        print("  list-competitors  - List all competitors")
        print("  analyze           - Analyze content text")
        print("  patterns          - Extract patterns from samples")
        print("  recommend         - Get style guide recommendations")
        print("  style-guide       - View or generate style guide")
        print("  clear             - Clear all samples")
        return 1


def cmd_generate(args):
    """Handle generation subcommands."""
    from pipeline import run_pipeline

    content_type = args.type or "fact"
    platforms = [p.strip() for p in args.platforms.split(",")] if args.platforms else []
    dry_run = args.dry_run or not platforms

    # Handle short_stories specially
    if content_type == "short_stories":
        return cmd_story_generate(args)

    print(f"\nGenerating {content_type} content...")
    if dry_run:
        print("(Dry run - not posting to platforms)")
    else:
        print(f"Platforms: {', '.join(platforms)}")

    print("-" * 40)

    result = run_pipeline(
        content_type=content_type,
        platforms=platforms if platforms else None,
        dry_run=dry_run,
    )

    if result:
        print(f"\nContent generated successfully!")
        print(f"Output: {result.get('output_dir', 'N/A')}")

        script = result.get("script", {})
        print(f"\nHook: {script.get('hook', 'N/A')}")

        if not dry_run:
            print(f"\nPosted to: {', '.join(platforms)}")
        return 0
    else:
        print("\nGeneration failed.")
        return 1


def cmd_story_generate(args):
    """Handle short_stories generation via orchestrator."""
    from generators.story_orchestrator import StoryOrchestrator

    genre = getattr(args, 'genre', None) or "thriller"
    mode = getattr(args, 'orchestration_mode', None) or "quick"
    topic = getattr(args, 'topic', None)
    dry_run = args.dry_run

    print(f"\nGenerating {genre} short story...")
    print(f"Mode: {mode}")
    if topic:
        print(f"Topic: {topic}")
    print("-" * 40)

    orchestrator = StoryOrchestrator()

    if mode == "detailed":
        result = orchestrator.run_detailed(
            genre=genre,
            topic=topic,
            visual_mode="manual",
        )
    else:
        result = orchestrator.run_quick(
            genre=genre,
            topic=topic,
        )

    if result.success:
        print(f"\nStory generated successfully!")
        print(f"Story ID: {result.story_id}")
        print(f"Output: {result.output_dir}")
        return 0
    else:
        print(f"\nGeneration failed: {result.errors}")
        return 1


def cmd_story(args):
    """Handle story subcommand for detailed story operations."""
    from generators.story_orchestrator import StoryOrchestrator
    from generators.story_registry import StoryRegistry, format_story_list, format_series_list

    action = args.action if hasattr(args, 'action') else "generate"

    if action == "list":
        registry = StoryRegistry()
        if args.series:
            series_list = registry.list_series()
            print("\nAll Series:")
            print("-" * 50)
            print(format_series_list(series_list))
        else:
            stories = registry.list_stories()
            print("\nAll Stories:")
            print("-" * 50)
            print(format_story_list(stories))
        return 0

    elif action == "info":
        if not args.story_id:
            print("Usage: cli.py story info STORY-ID")
            return 1

        registry = StoryRegistry()
        try:
            data = registry.get_story_for_continuation(args.story_id)
            print(json.dumps(data, indent=2))
            return 0
        except ValueError as e:
            print(f"Error: {e}")
            return 1

    elif action == "continue":
        if not args.story_id:
            print("Usage: cli.py story continue STORY-ID")
            return 1

        from generators.story_gen import StoryGenerator
        generator = StoryGenerator()

        print(f"\nContinuing story {args.story_id}...")
        story = generator.generate_continuation(args.story_id)

        print(f"\nTitle: {story.title}")
        print(f"\n--- CONTINUATION ---\n")
        print(story.full_story)
        return 0

    elif action == "generate":
        genre = args.genre or "thriller"
        mode = getattr(args, 'visual_mode', 'manual')
        topic = getattr(args, 'topic', None)
        series = getattr(args, 'series', None)

        orchestrator = StoryOrchestrator()

        if mode == "manual":
            result = orchestrator.run_detailed(
                genre=genre,
                topic=topic,
                visual_mode="manual",
            )
        else:
            result = orchestrator.run_quick(
                genre=genre,
                topic=topic,
                series_name=series,
            )

        return 0 if result.success else 1

    else:
        print(f"Unknown story action: {action}")
        return 1


def cmd_schedule(args):
    """Handle scheduler subcommands."""
    if args.action == "status":
        print("\nScheduler Status")
        print("-" * 40)

        # Check if scheduler.log exists
        log_file = PROJECT_ROOT / "scheduler.log"
        if log_file.exists():
            # Show last 10 lines
            with open(log_file) as f:
                lines = f.readlines()[-10:]
            print("Recent activity:")
            for line in lines:
                print(f"  {line.strip()}")
        else:
            print("No scheduler log found.")
            print("Start the scheduler with: python scheduler.py")
        return 0

    elif args.action == "once":
        content_type = args.type or "fact"
        platforms = [p.strip() for p in args.platforms.split(",")] if args.platforms else []

        from scheduler import scheduled_motivation, scheduled_fact
        from pipeline import run_pipeline

        print(f"Running {content_type} pipeline once...")

        if platforms:
            result = run_pipeline(
                content_type=content_type,
                platforms=platforms,
                dry_run=False,
            )
        else:
            if content_type == "motivation":
                scheduled_motivation()
            else:
                scheduled_fact()
            result = {"success": True}

        return 0 if result else 1

    elif args.action == "start":
        print("Starting scheduler...")
        print("Run: python scheduler.py")
        print("Or install as service: sudo systemctl start socal_maker")
        return 0

    else:
        print(f"Unknown schedule action: {args.action}")
        print("\nAvailable actions:")
        print("  status  - Show scheduler status")
        print("  once    - Run pipeline once")
        print("  start   - Start the scheduler")
        return 1


def cmd_validate(args):
    """Validate generated content against style guide."""
    from training.niche_config import NicheConfig

    if not args.file:
        print("Usage: cli.py validate <json_file>")
        return 1

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return 1

    with open(file_path) as f:
        content = json.load(f)

    niche = args.niche or "fun_facts"
    config = NicheConfig(niche)

    result = config.validate_content(content)

    print(f"\nValidation Results ({niche})")
    print("-" * 40)
    print(f"Score: {result['score']}/100")
    print(f"Passed: {'Yes' if result['passed'] else 'No'}")

    if result["issues"]:
        print("\nIssues:")
        for issue in result["issues"]:
            print(f"  - {issue}")
    else:
        print("\nNo issues found!")

    return 0 if result["passed"] else 1


def cmd_create(args):
    """
    Interactive content creation with clarification gate.

    This implements the structured clarification flow:
    1. Identify niche
    2. Trigger niche-specific question set if required
    3. Confirm all required inputs
    4. Ask for final clarification
    5. Generate structured output
    """
    from generators.clarification_gate import (
        ClarificationGate,
        run_interactive_clarification,
        Niche,
    )
    from generators.structured_generator import (
        generate_with_clarification,
        StructuredContentGenerator,
    )

    print("\n" + "=" * 60)
    print("INTERACTIVE CONTENT CREATION")
    print("With Structured Clarification Gate")
    print("=" * 60)

    # Run the interactive clarification flow
    gate = run_interactive_clarification()

    if not gate.is_ready():
        print("\nClarification incomplete. Cannot generate.")
        missing = gate.request.get_missing_inputs()
        print(f"Missing inputs: {json.dumps(missing, indent=2)}")
        return 1

    # Generate structured content
    print("\n" + "=" * 60)
    print("GENERATING CONTENT...")
    print("=" * 60)

    try:
        output = generate_with_clarification(gate)

        # Display the structured output
        print(output.to_formatted_string())

        # Save to file
        output_dir = PROJECT_ROOT / "output"
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / "last_created.json"
        with open(output_file, "w") as f:
            f.write(output.to_json())

        print(f"\nSaved to: {output_file}")

        # Ask if user wants to proceed with video generation
        if not args.script_only:
            proceed = input("\nProceed to video generation? (y/n): ").strip().lower()
            if proceed == "y":
                from pipeline import run_pipeline

                # Map the structured output back to pipeline format
                content_data = {
                    "type": "motivation" if "motivation" in output.niche else "fact",
                    "quote": output.hook,
                    "hook": output.hook,
                    "voiceover": output.full_script,
                    "caption": output.caption,
                    "hashtags": output.hashtags,
                    "keywords": output.full_script.split()[:5],
                    "voice_direction": output.voice_direction,
                }

                platforms = []
                if not args.dry_run:
                    platform_input = input("Platforms to post to (comma-separated, or Enter to skip): ").strip()
                    if platform_input:
                        platforms = [p.strip() for p in platform_input.split(",")]

                run_pipeline(
                    content_type=content_data["type"],
                    platforms=platforms if platforms else None,
                    dry_run=not platforms,
                    content_override=content_data,
                )

        return 0

    except Exception as e:
        print(f"\nError during generation: {e}")
        return 1


def cmd_create_quick(args):
    """
    Quick create with pre-specified parameters (non-interactive).

    Example:
        cli.py create-quick --niche motivation --tone aggressive_gym --voiceover energetic
    """
    from generators.clarification_gate import (
        ClarificationGate,
        Niche,
        TimeSlot,
        MotivationTone,
        QuoteType,
        VoiceoverStyle,
        MotivationConfig,
    )
    from generators.structured_generator import generate_with_clarification

    gate = ClarificationGate()

    # Set niche
    niche = args.niche or "motivation"
    gate.set_niche(niche)

    # Set motivation-specific options if applicable
    if niche == "motivation":
        gate.set_motivation_config(
            time_slot=args.time_slot or "auto",
            tone=args.tone or "generic_affirmation",
            quote_type=args.quote_type or "original",
            voiceover_style=args.voiceover or "neutral_ai",
        )

    # Set final clarification
    gate.set_final_clarification(args.constraints)

    if not gate.is_ready():
        print("Error: Could not configure gate with provided parameters.")
        print(json.dumps(gate.get_status(), indent=2))
        return 1

    # Generate
    output = generate_with_clarification(gate)
    print(output.to_formatted_string())

    # Save
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "last_quick_create.json"
    with open(output_file, "w") as f:
        f.write(output.to_json())

    print(f"\nSaved to: {output_file}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="SoCal Maker - Content Automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Training:
    %(prog)s train add-competitor @factspage tiktok
    %(prog)s train analyze "Did you know..."
    %(prog)s train patterns
    %(prog)s train style-guide

  Generation:
    %(prog)s generate fact --dry-run
    %(prog)s generate fact --platforms youtube,tiktok
    %(prog)s generate motivation --platforms youtube

  Scheduling:
    %(prog)s schedule status
    %(prog)s schedule once fact --platforms youtube
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Train command
    train_parser = subparsers.add_parser("train", help="Training and competitor analysis")
    train_parser.add_argument("action", help="Training action")
    train_parser.add_argument("handle", nargs="?", help="Competitor handle")
    train_parser.add_argument("platform", nargs="?", help="Platform (tiktok/instagram/youtube)")
    train_parser.add_argument("--text", "-t", help="Content text to analyze")
    train_parser.add_argument("--competitor", "-c", help="Competitor handle for attribution")
    train_parser.add_argument("--niche", "-n", default="fun_facts", help="Niche name")
    train_parser.add_argument("--generate", "-g", action="store_true", help="Generate from patterns")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate content")
    gen_parser.add_argument(
        "type", nargs="?", default="fact",
        choices=["fact", "motivation", "health", "short_stories"],
        help="Content type"
    )
    gen_parser.add_argument("--platforms", "-p", default="", help="Comma-separated platforms")
    gen_parser.add_argument("--dry-run", "-d", action="store_true", help="Don't post, just generate")
    gen_parser.add_argument("--niche", "-n", default="fun_facts", help="Niche name")
    gen_parser.add_argument(
        "--genre", "-g",
        choices=["thriller", "mystery", "comedy", "horror", "drama", "romance"],
        default="thriller",
        help="Story genre (for short_stories)"
    )
    gen_parser.add_argument(
        "--orchestration-mode",
        choices=["quick", "detailed"],
        default="quick",
        help="Story production mode (for short_stories)"
    )
    gen_parser.add_argument("--topic", "-t", help="Story topic/seed (for short_stories)")
    # Schedule command
    sched_parser = subparsers.add_parser("schedule", help="Scheduler management")
    sched_parser.add_argument("action", default="status", nargs="?", help="Scheduler action")
    sched_parser.add_argument("type", nargs="?", default="fact", help="Content type for 'once'")
    sched_parser.add_argument("--platforms", "-p", default="", help="Comma-separated platforms")

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validate content against style guide")
    val_parser.add_argument("file", nargs="?", help="JSON file to validate")
    val_parser.add_argument("--niche", "-n", default="fun_facts", help="Niche name")

    # Create command (interactive with clarification gate)
    create_parser = subparsers.add_parser(
        "create",
        help="Interactive content creation with clarification gate"
    )
    create_parser.add_argument(
        "--script-only", "-s",
        action="store_true",
        help="Only generate script, skip video creation"
    )
    create_parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Don't post to platforms"
    )

    # Create-quick command (non-interactive with parameters)
    quick_parser = subparsers.add_parser(
        "create-quick",
        help="Quick create with pre-specified parameters"
    )
    quick_parser.add_argument(
        "--niche", "-n",
        default="motivation",
        choices=["motivation", "facts", "finance", "fitness", "brand", "random", "custom"],
        help="Content niche"
    )
    quick_parser.add_argument(
        "--tone", "-t",
        default="generic_affirmation",
        choices=["generic_affirmation", "aggressive_gym", "calm_reflective", "spiritual", "business_focused"],
        help="Content tone (motivation niche)"
    )
    quick_parser.add_argument(
        "--time-slot",
        default="auto",
        choices=["morning", "midday", "after_work", "night", "auto"],
        help="Posting time slot"
    )
    quick_parser.add_argument(
        "--quote-type",
        default="original",
        choices=["original", "real_person", "mix"],
        help="Quote type"
    )
    quick_parser.add_argument(
        "--voiceover", "-v",
        default="neutral_ai",
        choices=["neutral_ai", "deep_motivational", "energetic", "text_only"],
        help="Voiceover style"
    )
    quick_parser.add_argument(
        "--constraints", "-c",
        default=None,
        help="Additional constraints or instructions"
    )

    # Story command (detailed story operations)
    story_parser = subparsers.add_parser(
        "story",
        help="Short story production commands"
    )
    story_parser.add_argument(
        "action",
        nargs="?",
        default="generate",
        choices=["generate", "list", "info", "continue"],
        help="Story action"
    )
    story_parser.add_argument(
        "story_id",
        nargs="?",
        help="Story ID (for info/continue)"
    )
    story_parser.add_argument(
        "--genre", "-g",
        choices=["thriller", "mystery", "comedy", "horror", "drama", "romance"],
        default="thriller",
        help="Story genre"
    )
    story_parser.add_argument(
        "--visual-mode",
        choices=["manual", "stock"],
        default="manual",
        help="Visual generation mode"
    )
    story_parser.add_argument(
        "--topic", "-t",
        help="Story topic/seed"
    )
    story_parser.add_argument(
        "--series", "-s",
        help="Series name to add story to"
    )
    story_parser.add_argument(
        "--continue",
        dest="continue_from",
        help="Story ID to continue from"
    )
    story_parser.add_argument(
        "--series-list",
        dest="series",
        action="store_true",
        help="List series instead of stories (for list action)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\n" + "=" * 50)
        print("SoCal Maker - Automated Content Factory")
        print("=" * 50)
        print("\nQuick start:")
        print("  1. Train on competitors: cli.py train add-competitor @factspage tiktok")
        print("  2. Analyze their content: cli.py train analyze \"Did you know...\"")
        print("  3. Generate your own: cli.py generate fact --dry-run")
        print("  4. Post when ready: cli.py generate fact --platforms youtube,tiktok")
        print("\nNew Interactive Mode:")
        print("  cli.py create              # Interactive with clarification questions")
        print("  cli.py create-quick        # Quick create with parameters")
        print("\nShort Stories:")
        print("  cli.py generate short_stories --genre thriller --dry-run")
        print("  cli.py story --genre mystery --visual-mode manual")
        print("  cli.py story list           # List all stories")
        print("  cli.py story list --series  # List all series")
        print("  cli.py story info STORY-001 # Show story details")
        print("  cli.py story continue STORY-001  # Create Part 2")
        return 0

    if args.command == "train":
        return cmd_train(args)
    elif args.command == "generate":
        return cmd_generate(args)
    elif args.command == "schedule":
        return cmd_schedule(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "create":
        return cmd_create(args)
    elif args.command == "create-quick":
        return cmd_create_quick(args)
    elif args.command == "story":
        return cmd_story(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
