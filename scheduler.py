#!/usr/bin/env python3
"""
Automated content scheduler.
Runs the pipeline on a schedule to generate and post content.

Usage:
    python scheduler.py                    # Run with default schedule
    python scheduler.py --once motivation  # Run once immediately
    python scheduler.py --once fact        # Run once for facts

Default schedule: 2 posts/day
    - 9:00 AM: Motivation quote
    - 6:00 PM: Fun fact
"""
import argparse
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

import schedule

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import POSTING_TIMES
from pipeline import run_pipeline

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "scheduler.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def scheduled_motivation():
    """Generate and save a motivation video (dry-run by default, add platforms to post)."""
    log.info("Starting scheduled motivation content...")
    try:
        result = run_pipeline(content_type="motivation", dry_run=True)
        if result:
            log.info(f"Motivation content saved to: {result['output_dir']}")
        else:
            log.error("Motivation pipeline failed")
    except Exception as e:
        log.error(f"Motivation pipeline error: {e}")


def scheduled_fact():
    """Generate and save a fun fact video."""
    log.info("Starting scheduled fact content...")
    try:
        result = run_pipeline(content_type="fact", dry_run=True)
        if result:
            log.info(f"Fact content saved to: {result['output_dir']}")
        else:
            log.error("Fact pipeline failed")
    except Exception as e:
        log.error(f"Fact pipeline error: {e}")


def setup_schedule():
    """Set up the posting schedule."""
    morning_time = POSTING_TIMES[0] if len(POSTING_TIMES) > 0 else "09:00"
    evening_time = POSTING_TIMES[1] if len(POSTING_TIMES) > 1 else "18:00"

    schedule.every().day.at(morning_time).do(scheduled_motivation)
    schedule.every().day.at(evening_time).do(scheduled_fact)

    log.info(f"Schedule set:")
    log.info(f"  {morning_time} — Motivation quote")
    log.info(f"  {evening_time} — Fun fact")
    log.info(f"Next run: {schedule.next_run()}")


def run_scheduler():
    """Run the scheduler loop."""
    setup_schedule()
    log.info("Scheduler started. Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Scheduler stopped.")


def main():
    parser = argparse.ArgumentParser(description="Content Scheduler")
    parser.add_argument(
        "--once", choices=["motivation", "fact"],
        help="Run pipeline once immediately instead of scheduling",
    )
    parser.add_argument(
        "--platforms", type=str, default="",
        help="Comma-separated platforms to post to",
    )
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    if args.once:
        log.info(f"Running {args.once} pipeline once...")
        run_pipeline(
            content_type=args.once,
            platforms=platforms if platforms else None,
            dry_run=not platforms,
        )
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
