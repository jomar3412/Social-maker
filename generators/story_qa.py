"""
Story QA Reviewer

Validates story production for consistency and quality:
- Timing consistency between voice script and scenes
- Character consistency across files
- Word count and duration checks
- Missing elements detection

Maps to the "QA Reviewer" agent in the 5-agent orchestration.

Usage:
    from generators.story_qa import StoryQA, QAReport

    qa = StoryQA()
    report = qa.run_full_qa(
        story=story_output,
        voice_script=voice_script,
        scene_plan=scene_plan,
        visual_prompts=visual_prompts
    )
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum

from config.settings import STORY_TARGET_DURATION, STORY_WORD_COUNT, STORY_SCENES_TARGET


class IssueSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class QAIssue:
    """A single QA issue found."""
    category: str = ""
    severity: IssueSeverity = IssueSeverity.WARNING
    message: str = ""
    details: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass
class QAReport:
    """Complete QA report for a story."""
    story_id: str = ""
    score: int = 100
    passed: bool = True
    issues: List[QAIssue] = field(default_factory=list)
    checks_performed: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["issues"] = [i.to_dict() for i in self.issues]
        return data

    def add_issue(self, issue: QAIssue):
        """Add an issue and adjust score."""
        self.issues.append(issue)

        # Deduct points based on severity
        deductions = {
            IssueSeverity.INFO: 0,
            IssueSeverity.WARNING: 5,
            IssueSeverity.ERROR: 15,
            IssueSeverity.CRITICAL: 30,
        }
        self.score = max(0, self.score - deductions.get(issue.severity, 5))

        # Mark as failed if critical or too many errors
        if issue.severity == IssueSeverity.CRITICAL:
            self.passed = False
        if self.score < 60:
            self.passed = False

    def to_markdown(self) -> str:
        """Export as markdown report."""
        lines = [
            "# QA Report",
            "",
            f"**Story ID:** {self.story_id}",
            f"**Score:** {self.score}/100",
            f"**Status:** {'PASSED' if self.passed else 'FAILED'}",
            "",
            "---",
            "",
            "## Summary",
            "",
            self.summary,
            "",
            "## Checks Performed",
            "",
        ]

        for check in self.checks_performed:
            lines.append(f"- {check}")

        lines.extend([
            "",
            "## Issues Found",
            ""
        ])

        if not self.issues:
            lines.append("No issues found!")
        else:
            # Group by severity
            for severity in [IssueSeverity.CRITICAL, IssueSeverity.ERROR,
                           IssueSeverity.WARNING, IssueSeverity.INFO]:
                severity_issues = [i for i in self.issues if i.severity == severity]
                if severity_issues:
                    lines.extend([
                        f"### {severity.value.upper()}",
                        ""
                    ])
                    for issue in severity_issues:
                        lines.extend([
                            f"**{issue.category}:** {issue.message}",
                            f"- Details: {issue.details}",
                            f"- Suggestion: {issue.suggestion}",
                            ""
                        ])

        return "\n".join(lines)


class StoryQA:
    """
    Quality assurance for story production.

    Checks:
    - Word count and duration
    - Timing consistency
    - Character consistency
    - Scene coverage
    - Missing elements
    """

    def __init__(self):
        self.target_duration = STORY_TARGET_DURATION
        self.target_word_count = STORY_WORD_COUNT
        self.target_scenes = STORY_SCENES_TARGET

    def check_word_count(self, story) -> List[QAIssue]:
        """Check if word count is in acceptable range."""
        issues = []
        word_count = getattr(story, 'word_count', 0)

        min_words = self.target_word_count * 0.7
        max_words = self.target_word_count * 1.3

        if word_count < min_words:
            issues.append(QAIssue(
                category="Word Count",
                severity=IssueSeverity.WARNING,
                message=f"Story too short: {word_count} words",
                details=f"Target is {self.target_word_count} words (±30%)",
                suggestion=f"Add {int(min_words - word_count)} more words to reach minimum",
            ))
        elif word_count > max_words:
            issues.append(QAIssue(
                category="Word Count",
                severity=IssueSeverity.WARNING,
                message=f"Story too long: {word_count} words",
                details=f"Target is {self.target_word_count} words (±30%)",
                suggestion=f"Cut {int(word_count - max_words)} words to reach maximum",
            ))

        return issues

    def check_duration(self, story, voice_script) -> List[QAIssue]:
        """Check if estimated duration is appropriate."""
        issues = []

        story_duration = getattr(story, 'estimated_duration', 0)
        voice_duration = getattr(voice_script, 'estimated_duration', 0) if voice_script else 0

        min_duration = self.target_duration * 0.75
        max_duration = self.target_duration * 1.5

        duration_to_check = voice_duration or story_duration

        if duration_to_check < min_duration:
            issues.append(QAIssue(
                category="Duration",
                severity=IssueSeverity.WARNING,
                message=f"Duration too short: ~{duration_to_check:.1f}s",
                details=f"Target is {self.target_duration}s (±25%)",
                suggestion="Add more content or slower pacing",
            ))
        elif duration_to_check > max_duration:
            issues.append(QAIssue(
                category="Duration",
                severity=IssueSeverity.WARNING,
                message=f"Duration too long: ~{duration_to_check:.1f}s",
                details=f"Target is {self.target_duration}s, max {max_duration}s",
                suggestion="Trim content or increase pacing",
            ))

        # Check discrepancy between story and voice estimates
        if story_duration and voice_duration:
            diff = abs(story_duration - voice_duration)
            if diff > 10:
                issues.append(QAIssue(
                    category="Duration",
                    severity=IssueSeverity.INFO,
                    message=f"Duration estimates differ by {diff:.1f}s",
                    details=f"Story: {story_duration:.1f}s, Voice: {voice_duration:.1f}s",
                    suggestion="Voice script estimate is usually more accurate",
                ))

        return issues

    def check_characters(self, story, scene_plan, visual_prompts) -> List[QAIssue]:
        """Check character consistency across all outputs."""
        issues = []

        story_chars = set(getattr(story, 'characters', {}).keys()) if story else set()

        # Check scene plan characters
        if scene_plan:
            scene_chars = set()
            for scene in getattr(scene_plan, 'scenes', []):
                chars = scene.characters_present if hasattr(scene, 'characters_present') else scene.get('characters_present', [])
                scene_chars.update(chars)

            # Characters in scenes but not in story
            extra_chars = scene_chars - story_chars
            if extra_chars:
                issues.append(QAIssue(
                    category="Character Consistency",
                    severity=IssueSeverity.WARNING,
                    message=f"Characters in scenes not defined in story",
                    details=f"Extra: {', '.join(extra_chars)}",
                    suggestion="Add character descriptions to story or remove from scenes",
                ))

            # Characters in story but not in scenes
            unused_chars = story_chars - scene_chars
            if unused_chars:
                issues.append(QAIssue(
                    category="Character Consistency",
                    severity=IssueSeverity.INFO,
                    message=f"Characters defined but not appearing in scenes",
                    details=f"Unused: {', '.join(unused_chars)}",
                    suggestion="Remove unused character definitions or add to scenes",
                ))

        # Check visual prompts have character refs
        if visual_prompts:
            char_prompts = getattr(visual_prompts, 'character_prompts', [])
            prompt_chars = {p.character_name for p in char_prompts if p.character_name}

            missing_visuals = story_chars - prompt_chars
            if missing_visuals:
                issues.append(QAIssue(
                    category="Visual Prompts",
                    severity=IssueSeverity.WARNING,
                    message=f"Missing character reference prompts",
                    details=f"No prompts for: {', '.join(missing_visuals)}",
                    suggestion="Add character reference prompts for consistency",
                ))

        return issues

    def check_scene_coverage(self, story, scene_plan) -> List[QAIssue]:
        """Check if scenes adequately cover the story."""
        issues = []

        if not scene_plan:
            issues.append(QAIssue(
                category="Scene Coverage",
                severity=IssueSeverity.ERROR,
                message="No scene plan available",
                details="Scene plan is required for video production",
                suggestion="Generate scene plan before proceeding",
            ))
            return issues

        scene_count = getattr(scene_plan, 'scene_count', 0)
        scenes = getattr(scene_plan, 'scenes', [])

        # Check scene count
        min_scenes = self.target_scenes * 0.6
        max_scenes = self.target_scenes * 1.5

        if scene_count < min_scenes:
            issues.append(QAIssue(
                category="Scene Coverage",
                severity=IssueSeverity.WARNING,
                message=f"Too few scenes: {scene_count}",
                details=f"Target is {self.target_scenes} scenes",
                suggestion="Add more scene breaks for visual variety",
            ))
        elif scene_count > max_scenes:
            issues.append(QAIssue(
                category="Scene Coverage",
                severity=IssueSeverity.INFO,
                message=f"Many scenes: {scene_count}",
                details=f"Target is {self.target_scenes} scenes",
                suggestion="Consider combining some scenes",
            ))

        # Check for very short or long scenes
        for scene in scenes:
            duration = scene.duration if hasattr(scene, 'duration') else scene.get('duration', 0)
            scene_num = scene.scene_number if hasattr(scene, 'scene_number') else scene.get('scene_number', 0)

            if duration < 2:
                issues.append(QAIssue(
                    category="Scene Duration",
                    severity=IssueSeverity.WARNING,
                    message=f"Scene {scene_num} very short: {duration:.1f}s",
                    details="Scenes under 2s may feel rushed",
                    suggestion="Combine with adjacent scene or add content",
                ))
            elif duration > 12:
                issues.append(QAIssue(
                    category="Scene Duration",
                    severity=IssueSeverity.INFO,
                    message=f"Scene {scene_num} is long: {duration:.1f}s",
                    details="Long scenes may need visual variety",
                    suggestion="Consider adding camera movement or B-roll",
                ))

        return issues

    def check_timing_consistency(self, scene_plan) -> List[QAIssue]:
        """Check if scene timings are consistent and non-overlapping."""
        issues = []

        if not scene_plan:
            return issues

        scenes = getattr(scene_plan, 'scenes', [])
        if not scenes:
            return issues

        # Sort by start time
        sorted_scenes = sorted(scenes,
            key=lambda s: s.start_time if hasattr(s, 'start_time') else s.get('start_time', 0))

        prev_end = 0
        for scene in sorted_scenes:
            start = scene.start_time if hasattr(scene, 'start_time') else scene.get('start_time', 0)
            end = scene.end_time if hasattr(scene, 'end_time') else scene.get('end_time', 0)
            scene_num = scene.scene_number if hasattr(scene, 'scene_number') else scene.get('scene_number', 0)

            # Check for overlap
            if start < prev_end:
                issues.append(QAIssue(
                    category="Timing",
                    severity=IssueSeverity.ERROR,
                    message=f"Scene {scene_num} overlaps with previous scene",
                    details=f"Starts at {start:.1f}s but previous ends at {prev_end:.1f}s",
                    suggestion="Adjust scene timing to prevent overlap",
                ))

            # Check for gaps
            gap = start - prev_end
            if gap > 2:
                issues.append(QAIssue(
                    category="Timing",
                    severity=IssueSeverity.WARNING,
                    message=f"Gap before scene {scene_num}: {gap:.1f}s",
                    details=f"Previous scene ends at {prev_end:.1f}s, this starts at {start:.1f}s",
                    suggestion="Add transition or adjust timing",
                ))

            prev_end = end

        return issues

    def check_story_structure(self, story) -> List[QAIssue]:
        """Check if story has proper structure."""
        issues = []

        if not story:
            issues.append(QAIssue(
                category="Structure",
                severity=IssueSeverity.CRITICAL,
                message="No story available",
                details="Story is required for production",
                suggestion="Generate story first",
            ))
            return issues

        # Check for hook
        hook = getattr(story, 'hook', '')
        if not hook or len(hook.split()) < 5:
            issues.append(QAIssue(
                category="Structure",
                severity=IssueSeverity.ERROR,
                message="Missing or weak hook",
                details=f"Hook: '{hook[:50]}...' ({len(hook.split())} words)",
                suggestion="Hook should be 10-15 words that grab attention",
            ))

        # Check for twist
        twist = getattr(story, 'twist', '')
        if not twist or len(twist.split()) < 10:
            issues.append(QAIssue(
                category="Structure",
                severity=IssueSeverity.WARNING,
                message="Missing or weak twist/ending",
                details=f"Twist: '{twist[:50]}...' ({len(twist.split())} words)",
                suggestion="Ending should be impactful (twist, cliffhanger, or resolution)",
            ))

        # Check for characters
        characters = getattr(story, 'characters', {})
        if not characters:
            issues.append(QAIssue(
                category="Structure",
                severity=IssueSeverity.WARNING,
                message="No character descriptions",
                details="Character descriptions are needed for visual consistency",
                suggestion="Add character descriptions for Midjourney prompts",
            ))

        return issues

    def run_full_qa(
        self,
        story=None,
        voice_script=None,
        scene_plan=None,
        visual_prompts=None,
    ) -> Dict[str, Any]:
        """
        Run all QA checks and return a complete report.

        Args:
            story: StoryOutput from story generator
            voice_script: VoiceScript from voice generator
            scene_plan: ScenePlan from scene planner
            visual_prompts: VisualPromptSet from visual generator

        Returns:
            QA report as dictionary
        """
        report = QAReport(
            story_id=getattr(story, 'story_id', '') if story else "",
        )

        # Run all checks
        checks = [
            ("Word Count", lambda: self.check_word_count(story)),
            ("Duration", lambda: self.check_duration(story, voice_script)),
            ("Story Structure", lambda: self.check_story_structure(story)),
            ("Character Consistency", lambda: self.check_characters(story, scene_plan, visual_prompts)),
            ("Scene Coverage", lambda: self.check_scene_coverage(story, scene_plan)),
            ("Timing Consistency", lambda: self.check_timing_consistency(scene_plan)),
        ]

        for check_name, check_fn in checks:
            report.checks_performed.append(check_name)
            try:
                issues = check_fn()
                for issue in issues:
                    report.add_issue(issue)
            except Exception as e:
                report.add_issue(QAIssue(
                    category=check_name,
                    severity=IssueSeverity.ERROR,
                    message=f"Check failed: {str(e)}",
                    details="An error occurred during this check",
                    suggestion="Review the input data",
                ))

        # Generate summary
        error_count = len([i for i in report.issues if i.severity in [IssueSeverity.ERROR, IssueSeverity.CRITICAL]])
        warning_count = len([i for i in report.issues if i.severity == IssueSeverity.WARNING])
        info_count = len([i for i in report.issues if i.severity == IssueSeverity.INFO])

        report.summary = (
            f"QA completed with score {report.score}/100. "
            f"Found {error_count} errors, {warning_count} warnings, {info_count} info notes. "
            f"{'PASSED - ready for production.' if report.passed else 'FAILED - address critical issues before proceeding.'}"
        )

        return report.to_dict()


# CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Story QA Reviewer")
        print("=" * 50)
        print("\nCommands:")
        print("  python story_qa.py check <story_dir>")
        print("  python story_qa.py severities")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "check":
        if len(sys.argv) < 3:
            print("Usage: python story_qa.py check <story_dir>")
            sys.exit(1)

        from pathlib import Path
        story_dir = Path(sys.argv[2])

        # Load available files
        story = None
        voice_script = None
        scene_plan = None
        visual_prompts = None

        story_file = story_dir / "story.json"
        if story_file.exists():
            with open(story_file) as f:
                from generators.story_gen import StoryOutput
                story = StoryOutput.from_dict(json.load(f))

        # Run QA
        qa = StoryQA()
        report = qa.run_full_qa(
            story=story,
            voice_script=voice_script,
            scene_plan=scene_plan,
            visual_prompts=visual_prompts,
        )

        # Print report
        qa_report = QAReport(**{k: v for k, v in report.items() if k != 'issues'})
        qa_report.issues = [QAIssue(**{k: IssueSeverity(v) if k == 'severity' else v for k, v in i.items()})
                           for i in report.get('issues', [])]
        print(qa_report.to_markdown())

    elif cmd == "severities":
        print("Issue Severities:")
        print("-" * 30)
        for sev in IssueSeverity:
            print(f"  - {sev.value}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
