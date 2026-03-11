"""
Content Engine CLI - Unified command-line interface.

Usage:
    python -m content_engine.cli.main generate motivation --dry-run
    python -m content_engine.cli.main generate fun_facts --style energetic
    python -m content_engine.cli.main status
    python -m content_engine.cli.main history
    python -m content_engine.cli.main open-output RUN_ID
    python -m content_engine.cli.main --wizard
"""

import argparse
import sys
from pathlib import Path

from content_engine.pipeline.orchestrator import PipelineOrchestrator
from content_engine.pipeline.models.run_config import RunConfig
from content_engine.services.drive_guard import DriveGuard
from content_engine.services.preset_loader import PresetLoader
from content_engine.services.run_store import RunStore
from content_engine.services.output_writer import OutputWriter


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="content-engine",
        description="Content Engine - Automated short-form video content generation",
    )

    # Top-level wizard flag
    parser.add_argument(
        "--wizard",
        action="store_true",
        help="Start wizard web UI",
    )
    parser.add_argument(
        "--wizard-host",
        default="127.0.0.1",
        help="Wizard bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--wizard-port",
        type=int,
        default=8080,
        help="Wizard port (default: 8080)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # === generate command ===
    gen_parser = subparsers.add_parser("generate", help="Generate content")
    gen_parser.add_argument(
        "niche",
        choices=["motivation", "fun_facts"],
        help="Content niche",
    )
    gen_parser.add_argument(
        "--style",
        default="affirming",
        help="Content style (default: affirming)",
    )
    gen_parser.add_argument(
        "--voice",
        default="deep_motivational",
        help="Voice preset (default: deep_motivational)",
    )
    gen_parser.add_argument(
        "--visual",
        default="hybrid",
        choices=["nanobanana", "stock", "hybrid"],
        help="Visual mode (default: hybrid)",
    )
    gen_parser.add_argument(
        "--realism",
        default="standard",
        choices=["standard", "photorealistic"],
        help="Realism mode (default: standard)",
    )
    gen_parser.add_argument(
        "--topic",
        help="Optional specific topic",
    )
    gen_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without external API calls",
    )
    gen_parser.add_argument(
        "--shot-list",
        action="store_true",
        default=True,
        help="Generate shot list (default: True)",
    )
    gen_parser.add_argument(
        "--no-shot-list",
        action="store_false",
        dest="shot_list",
        help="Skip shot list generation",
    )
    gen_parser.add_argument(
        "--budget-mode",
        action="store_true",
        help="Minimize API calls",
    )
    gen_parser.add_argument(
        "--max-calls",
        type=int,
        default=10,
        help="Maximum API calls (default: 10)",
    )
    gen_parser.add_argument(
        "--align-audio",
        action="store_true",
        help="Align timeline to word-level audio timing",
    )
    gen_parser.add_argument(
        "--align-duration",
        action="store_true",
        help="Align timeline to total audio duration only",
    )

    # === status command ===
    subparsers.add_parser("status", help="Check G Drive and system status")

    # === history command ===
    hist_parser = subparsers.add_parser("history", help="Show recent runs")
    hist_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of runs to show (default: 10)",
    )

    # === open-output command ===
    open_parser = subparsers.add_parser("open-output", help="Open output folder for a run")
    open_parser.add_argument("run_id", help="Run ID to open")

    # === presets command ===
    presets_parser = subparsers.add_parser("presets", help="List available presets")
    presets_parser.add_argument(
        "category",
        nargs="?",
        choices=["niches", "styles", "voices", "visuals", "realism"],
        help="Preset category to list",
    )

    return parser


def cmd_generate(args) -> int:
    """Handle generate command."""
    print(f"\n{'='*60}")
    print(f"  Content Engine - Generate")
    print(f"{'='*60}\n")

    # Create config from CLI args
    config = RunConfig.from_cli(args)
    print(f"Run ID: {config.run_id}")
    print(f"Niche: {config.niche}")
    print(f"Style: {config.style}")
    print(f"Visual: {config.visual_mode}")
    print(f"Dry Run: {config.dry_run}")
    print()

    # Create orchestrator with log callback
    def on_log(msg: str):
        print(f"  {msg}")

    orchestrator = PipelineOrchestrator(on_log=on_log)

    # Run pipeline
    print("Starting pipeline...\n")
    success, paths, message = orchestrator.run(config)

    print()
    if success:
        print(f"{'='*60}")
        print(f"  SUCCESS")
        print(f"{'='*60}")
        print(f"\nOutput: {paths.base_dir}")
        print(f"\nFiles created:")
        for f in paths.existing_files():
            size = f.stat().st_size
            print(f"  - {f.name} ({size} bytes)")
        print()
        return 0
    else:
        print(f"{'='*60}")
        print(f"  FAILED")
        print(f"{'='*60}")
        print(f"\nError: {message}")
        return 1


def cmd_status(args) -> int:
    """Handle status command."""
    print(f"\n{'='*60}")
    print(f"  Content Engine - Status")
    print(f"{'='*60}\n")

    # Check G Drive
    guard = DriveGuard()
    result = guard.check()

    if result.status.value == "mounted":
        print(f"G Drive: CONNECTED")
        print(f"  Path: {result.mount_path}")
        print(f"  Writable: {result.can_write}")
        print(f"  Detection: {result.detection_method}")
    else:
        print(f"G Drive: NOT CONNECTED")
        print(f"  Status: {result.status.value}")
        print(f"  Error: {result.error_message}")
        if result.mount_command:
            print(f"\n  To mount:\n    {result.mount_command}")

    # Check presets
    print()
    loader = PresetLoader()
    for category in ["niches", "styles", "voices", "visuals", "realism"]:
        presets = loader.list_presets(category)
        print(f"{category.title()}: {len(presets)} presets")

    # Check pending runs
    print()
    store = RunStore()
    pending = store.get_pending_runs()
    if pending:
        print(f"Pending approvals: {len(pending)}")
        for run in pending:
            print(f"  - {run.run_id}: {run.stage.value}")
    else:
        print("No pending approvals")

    print()
    return 0


def cmd_history(args) -> int:
    """Handle history command."""
    print(f"\n{'='*60}")
    print(f"  Content Engine - Run History")
    print(f"{'='*60}\n")

    store = RunStore()
    runs = store.get_recent_runs(limit=args.limit)

    if not runs:
        print("No runs found.")
        return 0

    for run in runs:
        config = run.config
        status_icon = {
            "complete": "",
            "failed": "",
            "cancelled": "",
        }.get(run.stage.value, "")

        print(f"{status_icon} {run.run_id}")
        print(f"   Stage: {run.stage.value}")
        print(f"   Niche: {config.get('niche', 'unknown')}")
        print(f"   Style: {config.get('style', 'unknown')}")
        print(f"   Created: {run.created_at}")
        if run.output_path:
            print(f"   Output: {run.output_path}")
        print()

    return 0


def cmd_open_output(args) -> int:
    """Handle open-output command."""
    guard = DriveGuard()
    paths = OutputWriter.find_run_output(guard, args.run_id)

    if paths is None:
        print(f"Run not found: {args.run_id}")
        return 1

    writer = OutputWriter(guard)
    cmd = writer.open_output_folder(paths)
    print(f"Opening: {paths.base_dir}")
    print(f"Command: {cmd}")

    import subprocess
    subprocess.run(cmd, shell=True)
    return 0


def cmd_presets(args) -> int:
    """Handle presets command."""
    loader = PresetLoader()

    if args.category:
        categories = [args.category]
    else:
        categories = ["niches", "styles", "voices", "visuals", "realism"]

    print(f"\n{'='*60}")
    print(f"  Available Presets")
    print(f"{'='*60}\n")

    for category in categories:
        presets = loader.get_all_presets(category)
        print(f"{category.upper()}:")
        for preset in presets:
            display = preset.data.get("display_name", preset.name)
            desc = preset.data.get("description", "")[:50]
            print(f"  - {preset.name}: {display}")
            if desc:
                print(f"      {desc}")
        print()

    return 0


def cmd_wizard(args) -> int:
    """Launch wizard web UI."""
    print(f"\n{'='*60}")
    print(f"  Content Engine - Wizard")
    print(f"{'='*60}\n")

    host = args.wizard_host
    port = args.wizard_port

    print(f"Starting wizard server...")
    print(f"  URL: http://{host}:{port}")
    print(f"\nPress Ctrl+C to stop.\n")

    try:
        import uvicorn
        from content_engine.app.main import app
        uvicorn.run(app, host=host, port=port, log_level="info")
    except ImportError:
        print("Error: uvicorn not installed.")
        print("Run: pip install uvicorn fastapi jinja2")
        return 1
    except KeyboardInterrupt:
        print("\nWizard stopped.")
        return 0

    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Handle --wizard flag first
    if args.wizard:
        return cmd_wizard(args)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "generate": cmd_generate,
        "status": cmd_status,
        "history": cmd_history,
        "open-output": cmd_open_output,
        "presets": cmd_presets,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
