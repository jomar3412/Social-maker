"""
OutputWriter: Structured output to Google Drive.

Creates organized folder structure:
{mount}/{output_root}/{niche}/{style}/{date}/{run_id}/

Writes all pipeline outputs with consistent naming.
"""

from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import json
import os

from .drive_guard import DriveGuard, DriveNotAvailableError


@dataclass
class OutputPaths:
    """Paths for all output files in a run."""
    base_dir: Path
    config: Path
    script: Path
    script_meta: Path
    shot_list_json: Path
    shot_list_md: Path
    nanobanana_prompts: Path
    stock_queries: Path
    timeline: Path
    timeline_aligned: Path
    voiceover: Path
    word_timing: Path
    run_log: Path
    coherence_report: Path

    def all_files(self) -> list[Path]:
        """Return list of all potential output file paths."""
        return [
            self.config, self.script, self.script_meta,
            self.shot_list_json, self.shot_list_md,
            self.nanobanana_prompts, self.stock_queries,
            self.timeline, self.timeline_aligned,
            self.voiceover, self.word_timing,
            self.run_log, self.coherence_report
        ]

    def existing_files(self) -> list[Path]:
        """Return list of output files that actually exist."""
        return [p for p in self.all_files() if p.exists()]


@dataclass
class RunLogEntry:
    """Single log entry for run tracking."""
    timestamp: str
    event: str
    details: dict[str, Any] = field(default_factory=dict)


class OutputWriter:
    """
    Write pipeline outputs to structured Google Drive folders.

    Output structure:
    {mount}/{output_root}/{niche}/{style}/{YYYY-MM-DD}/{run_id}/
        config.json
        script.txt
        script_meta.json
        shot_list.json
        shot_list.md
        nanobanana_prompts.txt
        stock_queries.txt
        timeline.json
        timeline_aligned.json
        voiceover.mp3
        word_timing.json
        run_log.txt
        coherence_report.json
    """

    def __init__(self, drive_guard: DriveGuard | None = None):
        """
        Initialize OutputWriter.

        Args:
            drive_guard: DriveGuard instance. If None, creates one with default config.
        """
        self.drive_guard = drive_guard or DriveGuard()
        self._log_entries: list[RunLogEntry] = []

    def create_run_directory(
        self,
        run_id: str,
        niche: str,
        style: str,
        date: str | None = None
    ) -> OutputPaths:
        """
        Create output directory structure for a run.

        Args:
            run_id: Unique run identifier (e.g., "run-001")
            niche: Niche name (e.g., "motivation")
            style: Style name (e.g., "affirming")
            date: Date string YYYY-MM-DD (defaults to today)

        Returns:
            OutputPaths with all file paths

        Raises:
            DriveNotAvailableError: If G Drive is not writable
        """
        # Ensure drive is writable
        self.drive_guard.require_writable()

        # Use today's date if not provided
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Build path: {mount}/{output_root}/{niche}/{style}/{date}/{run_id}/
        base_dir = (
            self.drive_guard.get_output_base() /
            niche /
            style /
            date /
            run_id
        )

        # Create directory structure
        base_dir.mkdir(parents=True, exist_ok=True)

        # Return paths for all output files
        return OutputPaths(
            base_dir=base_dir,
            config=base_dir / "config.json",
            script=base_dir / "script.txt",
            script_meta=base_dir / "script_meta.json",
            shot_list_json=base_dir / "shot_list.json",
            shot_list_md=base_dir / "shot_list.md",
            nanobanana_prompts=base_dir / "nanobanana_prompts.txt",
            stock_queries=base_dir / "stock_queries.txt",
            timeline=base_dir / "timeline.json",
            timeline_aligned=base_dir / "timeline_aligned.json",
            voiceover=base_dir / "voiceover.mp3",
            word_timing=base_dir / "word_timing.json",
            run_log=base_dir / "run_log.txt",
            coherence_report=base_dir / "coherence_report.json",
        )

    def write_config(self, paths: OutputPaths, config: dict) -> Path:
        """Write run configuration JSON."""
        with open(paths.config, "w") as f:
            json.dump(config, f, indent=2)
        self._log("config_written", {"path": str(paths.config)})
        return paths.config

    def write_script(self, paths: OutputPaths, script_text: str) -> Path:
        """Write plain text script."""
        paths.script.write_text(script_text)
        self._log("script_written", {"path": str(paths.script), "length": len(script_text)})
        return paths.script

    def write_script_meta(self, paths: OutputPaths, meta: dict) -> Path:
        """Write script metadata (hook, keywords, hashtags, etc.)."""
        with open(paths.script_meta, "w") as f:
            json.dump(meta, f, indent=2)
        self._log("script_meta_written", {"path": str(paths.script_meta)})
        return paths.script_meta

    def write_shot_list(self, paths: OutputPaths, shot_list: list[dict]) -> Path:
        """Write shot list JSON."""
        with open(paths.shot_list_json, "w") as f:
            json.dump(shot_list, f, indent=2)
        self._log("shot_list_written", {"path": str(paths.shot_list_json), "scenes": len(shot_list)})
        return paths.shot_list_json

    def write_shot_list_markdown(self, paths: OutputPaths, markdown: str) -> Path:
        """Write human-readable shot list markdown."""
        paths.shot_list_md.write_text(markdown)
        self._log("shot_list_md_written", {"path": str(paths.shot_list_md)})
        return paths.shot_list_md

    def write_nanobanana_prompts(self, paths: OutputPaths, prompts: str) -> Path:
        """Write NanoBanana prompts (copy-paste ready)."""
        paths.nanobanana_prompts.write_text(prompts)
        self._log("nanobanana_written", {"path": str(paths.nanobanana_prompts)})
        return paths.nanobanana_prompts

    def write_stock_queries(self, paths: OutputPaths, queries: str) -> Path:
        """Write stock footage search queries."""
        paths.stock_queries.write_text(queries)
        self._log("stock_queries_written", {"path": str(paths.stock_queries)})
        return paths.stock_queries

    def write_timeline(self, paths: OutputPaths, timeline: dict) -> Path:
        """Write timeline JSON."""
        with open(paths.timeline, "w") as f:
            json.dump(timeline, f, indent=2)
        self._log("timeline_written", {"path": str(paths.timeline)})
        return paths.timeline

    def write_timeline_aligned(self, paths: OutputPaths, timeline: dict) -> Path:
        """Write audio-aligned timeline JSON."""
        with open(paths.timeline_aligned, "w") as f:
            json.dump(timeline, f, indent=2)
        self._log("timeline_aligned_written", {"path": str(paths.timeline_aligned)})
        return paths.timeline_aligned

    def write_voiceover(self, paths: OutputPaths, audio_data: bytes) -> Path:
        """Write voiceover audio file."""
        with open(paths.voiceover, "wb") as f:
            f.write(audio_data)
        self._log("voiceover_written", {"path": str(paths.voiceover), "size": len(audio_data)})
        return paths.voiceover

    def write_word_timing(self, paths: OutputPaths, timing: dict) -> Path:
        """Write word-level timing JSON from ElevenLabs."""
        with open(paths.word_timing, "w") as f:
            json.dump(timing, f, indent=2)
        self._log("word_timing_written", {"path": str(paths.word_timing)})
        return paths.word_timing

    def write_coherence_report(self, paths: OutputPaths, report: dict) -> Path:
        """Write coherence validation report."""
        with open(paths.coherence_report, "w") as f:
            json.dump(report, f, indent=2)
        self._log("coherence_report_written", {"path": str(paths.coherence_report)})
        return paths.coherence_report

    def _log(self, event: str, details: dict[str, Any] | None = None):
        """Add entry to run log."""
        entry = RunLogEntry(
            timestamp=datetime.now().isoformat(),
            event=event,
            details=details or {}
        )
        self._log_entries.append(entry)

    def log_event(self, event: str, details: dict[str, Any] | None = None):
        """Public method to add custom log entries."""
        self._log(event, details)

    def write_run_log(self, paths: OutputPaths) -> Path:
        """Write accumulated run log to file."""
        lines = []
        for entry in self._log_entries:
            details_str = json.dumps(entry.details) if entry.details else ""
            lines.append(f"[{entry.timestamp}] {entry.event} {details_str}")

        paths.run_log.write_text("\n".join(lines))
        return paths.run_log

    def clear_log(self):
        """Clear accumulated log entries (start fresh for new run)."""
        self._log_entries.clear()

    def get_output_summary(self, paths: OutputPaths) -> dict:
        """
        Get summary of output files.

        Returns:
            Dict with file info, sizes, and counts
        """
        existing = paths.existing_files()

        return {
            "base_dir": str(paths.base_dir),
            "total_files": len(existing),
            "files": [
                {
                    "name": p.name,
                    "size": p.stat().st_size,
                    "path": str(p)
                }
                for p in existing
            ]
        }

    def open_output_folder(self, paths: OutputPaths) -> str:
        """
        Get command to open output folder.

        Returns:
            Shell command appropriate for the platform
        """
        import platform

        system = platform.system()
        folder = str(paths.base_dir)

        if system == "Darwin":  # macOS
            return f"open '{folder}'"
        elif system == "Windows":
            return f"explorer '{folder}'"
        else:  # Linux
            return f"xdg-open '{folder}'"

    @staticmethod
    def find_run_output(
        drive_guard: DriveGuard,
        run_id: str,
        niche: str | None = None,
        style: str | None = None,
        date: str | None = None
    ) -> OutputPaths | None:
        """
        Find existing run output directory.

        Args:
            drive_guard: DriveGuard instance
            run_id: Run ID to find
            niche: Optional niche filter
            style: Optional style filter
            date: Optional date filter

        Returns:
            OutputPaths if found, None otherwise
        """
        base = drive_guard.get_output_base()

        # Build search pattern
        niche_pattern = niche or "*"
        style_pattern = style or "*"
        date_pattern = date or "*"

        # Search for matching directories
        pattern = f"{niche_pattern}/{style_pattern}/{date_pattern}/{run_id}"
        matches = list(base.glob(pattern))

        if not matches:
            return None

        # Return first match
        found_dir = matches[0]
        return OutputPaths(
            base_dir=found_dir,
            config=found_dir / "config.json",
            script=found_dir / "script.txt",
            script_meta=found_dir / "script_meta.json",
            shot_list_json=found_dir / "shot_list.json",
            shot_list_md=found_dir / "shot_list.md",
            nanobanana_prompts=found_dir / "nanobanana_prompts.txt",
            stock_queries=found_dir / "stock_queries.txt",
            timeline=found_dir / "timeline.json",
            timeline_aligned=found_dir / "timeline_aligned.json",
            voiceover=found_dir / "voiceover.mp3",
            word_timing=found_dir / "word_timing.json",
            run_log=found_dir / "run_log.txt",
            coherence_report=found_dir / "coherence_report.json",
        )
