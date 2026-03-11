"""
Knowledge Comparator - compares internal learning against external specs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
import logging

from .registry import KnowledgeRegistry, get_registry

logger = logging.getLogger(__name__)


@dataclass
class ConflictRecord:
    """Record of a conflict between internal and external knowledge."""
    id: str
    topic: str
    external_source: str
    external_rule: str
    external_value: Any
    internal_source: str
    internal_finding: str
    internal_value: Any
    sample_size: int
    confidence: str  # low, medium, high
    resolution: str  # external_preferred, internal_preferred, pending_review
    scope: dict = field(default_factory=dict)  # niche, style, visual_mode
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "external_source": self.external_source,
            "external_rule": self.external_rule,
            "external_value": self.external_value,
            "internal_source": self.internal_source,
            "internal_finding": self.internal_finding,
            "internal_value": self.internal_value,
            "sample_size": self.sample_size,
            "confidence": self.confidence,
            "resolution": self.resolution,
            "scope": self.scope,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ComparisonResult:
    """Result of comparing internal vs external knowledge."""
    agreements: list[dict] = field(default_factory=list)
    conflicts: list[ConflictRecord] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)  # Insufficient sample size
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "agreements": self.agreements,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "pending": self.pending,
            "timestamp": self.timestamp,
            "summary": {
                "total_agreements": len(self.agreements),
                "total_conflicts": len(self.conflicts),
                "total_pending": len(self.pending),
            }
        }


class KnowledgeComparator:
    """
    Compares internal learning against external specifications.

    Responsibilities:
    - Identify where internal data agrees with external specs
    - Identify conflicts (internal suggests different values)
    - Apply sample size thresholds
    - Generate conflict reports
    - Suggest resolutions
    """

    def __init__(self, registry: Optional[KnowledgeRegistry] = None):
        self.registry = registry or get_registry()
        self.kb_path = self.registry.kb_path

    def compare(self) -> ComparisonResult:
        """
        Run full comparison of internal vs external knowledge.

        Returns:
            ComparisonResult with agreements, conflicts, and pending items
        """
        result = ComparisonResult()

        # Load external dopamine spec rules
        dopamine_rules = self._extract_dopamine_rules()

        # Load internal learning
        learning = self.registry.read_learning_summary()
        patterns = self.registry.read_patterns()
        overrides = self.registry.read_rule_overrides()

        # Compare hook performance
        self._compare_hooks(dopamine_rules, learning, result)

        # Compare dopamine level compliance
        self._compare_dopamine_compliance(dopamine_rules, learning, result)

        # Check existing overrides for validity
        self._validate_overrides(overrides, learning, result)

        return result

    def _extract_dopamine_rules(self) -> dict:
        """Extract testable rules from dopamine spec."""
        rules = {
            "hook_timing": {
                "source": "dopamine_spec_v1",
                "rule": "Level 1 - Interrupt scroll within first 1-2 seconds",
                "max_seconds": 2,
            },
            "curiosity_loop": {
                "source": "dopamine_spec_v1",
                "rule": "Level 2 - Script must contain at least one open loop before 5 seconds",
                "max_seconds": 5,
            },
            "anticipation_gap": {
                "source": "dopamine_spec_v1",
                "rule": "Level 3 - A minimum anticipation gap is required",
                "required": True,
            },
            "resolution_required": {
                "source": "dopamine_spec_v1",
                "rule": "Level 4 - Clear answer or resolution required",
                "required": True,
            },
            "brand_layer": {
                "source": "dopamine_spec_v1",
                "rule": "Level 5 - At least one brand/trust element required",
                "required": True,
            },
        }
        return rules

    def _compare_hooks(
        self,
        external_rules: dict,
        learning: dict,
        result: ComparisonResult,
    ) -> None:
        """Compare hook performance data against external rules."""
        hook_data = learning.get("hook_performance", {})
        avg_word_count = hook_data.get("avg_word_count")
        best_patterns = hook_data.get("best_performing_patterns", [])

        # External rule: hooks should be very short (implied by 1-2 second timing)
        # Typical speaking rate is ~3 words/second, so ~6 words max for hook

        external_implied_max_words = 6  # 2 seconds * 3 words/second

        if avg_word_count is not None:
            total_runs = learning.get("total_runs_analyzed", 0)

            if total_runs >= self.registry.config.sample_size_threshold:
                if avg_word_count <= external_implied_max_words:
                    result.agreements.append({
                        "topic": "hook_word_count",
                        "external_rule": f"Hooks should be <=6 words (implied by 2 second timing)",
                        "internal_finding": f"Average hook word count is {avg_word_count:.1f}",
                        "status": "confirmed",
                        "sample_size": total_runs,
                    })
                else:
                    result.conflicts.append(ConflictRecord(
                        id=f"conflict_hook_length_{datetime.now().strftime('%Y%m%d')}",
                        topic="hook_word_count",
                        external_source="dopamine_spec_v1",
                        external_rule="Hooks should interrupt scroll within 1-2 seconds (~6 words max)",
                        external_value=external_implied_max_words,
                        internal_source="learning_summary.json",
                        internal_finding=f"Best performing hooks average {avg_word_count:.1f} words",
                        internal_value=round(avg_word_count, 1),
                        sample_size=total_runs,
                        confidence="high" if total_runs >= 20 else "medium",
                        resolution=self._determine_resolution(total_runs),
                    ))
            else:
                result.pending.append({
                    "topic": "hook_word_count",
                    "reason": f"Insufficient sample size ({total_runs} < {self.registry.config.sample_size_threshold})",
                    "current_value": avg_word_count,
                })

    def _compare_dopamine_compliance(
        self,
        external_rules: dict,
        learning: dict,
        result: ComparisonResult,
    ) -> None:
        """Compare dopamine level pass rates against requirements."""
        compliance = learning.get("dopamine_compliance", {})
        total_runs = learning.get("total_runs_analyzed", 0)

        if total_runs < self.registry.config.sample_size_threshold:
            return  # Not enough data

        for level in range(1, 7):
            key = f"level_{level}_pass_rate"
            pass_rate = compliance.get(key)

            if pass_rate is not None:
                # External spec requires 100% compliance on all levels
                if pass_rate >= 0.95:  # 95%+ considered compliant
                    result.agreements.append({
                        "topic": f"dopamine_level_{level}",
                        "external_rule": f"Level {level} requirements must be met",
                        "internal_finding": f"{pass_rate*100:.1f}% pass rate",
                        "status": "confirmed",
                        "sample_size": total_runs,
                    })
                elif pass_rate >= 0.70:  # 70-95% = conflict but manageable
                    result.conflicts.append(ConflictRecord(
                        id=f"conflict_dopamine_l{level}_{datetime.now().strftime('%Y%m%d')}",
                        topic=f"dopamine_level_{level}_compliance",
                        external_source="dopamine_spec_v1",
                        external_rule=f"Level {level} requirements must be met (100%)",
                        external_value=1.0,
                        internal_source="learning_summary.json",
                        internal_finding=f"Actual pass rate is {pass_rate*100:.1f}%",
                        internal_value=pass_rate,
                        sample_size=total_runs,
                        confidence="high" if total_runs >= 20 else "medium",
                        resolution="external_preferred",  # Dopamine compliance is critical
                    ))

    def _validate_overrides(
        self,
        overrides: dict,
        learning: dict,
        result: ComparisonResult,
    ) -> None:
        """Validate existing rule overrides still have support."""
        for override in overrides.get("overrides", []):
            if override.get("status") != "active":
                continue

            evidence = override.get("internal_override", {}).get("evidence", {})
            original_run_count = evidence.get("run_count", 0)
            total_now = learning.get("total_runs_analyzed", 0)

            # Check if override is still valid with more data
            if total_now > original_run_count * 1.5:  # 50% more data
                result.pending.append({
                    "topic": f"override_validation_{override.get('id')}",
                    "reason": "Override may need re-validation with new data",
                    "original_runs": original_run_count,
                    "current_runs": total_now,
                })

    def _determine_resolution(self, sample_size: int) -> str:
        """Determine conflict resolution based on sample size."""
        threshold = self.registry.config.sample_size_threshold

        if sample_size >= threshold * 2:
            return "internal_preferred"
        elif sample_size >= threshold:
            return "pending_review"
        else:
            return "external_preferred"

    def save_conflicts_report(self, result: Optional[ComparisonResult] = None) -> Path:
        """
        Save conflicts report to knowledge_base/internal/insights/conflicts.md

        Returns:
            Path to the saved file
        """
        if result is None:
            result = self.compare()

        conflicts_path = self.kb_path / "internal" / "insights" / "conflicts.md"

        lines = [
            "# Internal vs External Conflicts",
            "",
            f"*Auto-generated: {result.timestamp}*",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"| Status | Count |",
            f"|--------|-------|",
            f"| Confirmed (internal agrees with external) | {len(result.agreements)} |",
            f"| Conflicts (internal differs from external) | {len(result.conflicts)} |",
            f"| Pending (insufficient sample size) | {len(result.pending)} |",
            "",
            "---",
            "",
            "## Confirmed Agreements",
            "",
        ]

        if result.agreements:
            for agreement in result.agreements:
                lines.append(f"### {agreement['topic']}")
                lines.append(f"**External:** {agreement['external_rule']}")
                lines.append(f"**Internal:** {agreement['internal_finding']}")
                lines.append(f"**Sample Size:** {agreement['sample_size']} runs")
                lines.append("")
        else:
            lines.append("*No confirmed agreements yet.*")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## Conflicts")
        lines.append("")

        if result.conflicts:
            for conflict in result.conflicts:
                lines.append(f"### {conflict.id} - {conflict.topic}")
                lines.append(f"**External Spec:** {conflict.external_source} says: {conflict.external_rule}")
                lines.append(f"**External Value:** {conflict.external_value}")
                lines.append(f"**Internal Data:** {conflict.internal_finding}")
                lines.append(f"**Internal Value:** {conflict.internal_value}")
                lines.append(f"**Sample Size:** {conflict.sample_size} runs")
                lines.append(f"**Confidence:** {conflict.confidence}")
                lines.append(f"**Resolution:** {conflict.resolution}")
                if conflict.scope:
                    scope_str = ", ".join(f"{k}={v}" for k, v in conflict.scope.items() if v)
                    lines.append(f"**Scope:** {scope_str or 'Global'}")
                lines.append("")
        else:
            lines.append("*No conflicts detected.*")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## Pending Analysis")
        lines.append("")

        if result.pending:
            for pending in result.pending:
                lines.append(f"- **{pending['topic']}:** {pending['reason']}")
        else:
            lines.append("*No items pending.*")
        lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## Resolution Policy")
        lines.append("")
        lines.append("1. External specs are **never modified** by the engine")
        lines.append(f"2. Internal data takes precedence only when sample size >= {self.registry.config.sample_size_threshold}")
        lines.append("3. All conflicts are logged here for manual review")
        lines.append("4. User can override any resolution in `rule_overrides.json`")

        with open(conflicts_path, "w") as f:
            f.write("\n".join(lines))

        logger.info(f"Saved conflicts report to {conflicts_path}")
        return conflicts_path

    def update_learning_from_feedback(
        self,
        run_id: str,
        niche: str,
        style: str,
        visual_mode: str,
        feedback: dict,
    ) -> None:
        """
        Update internal learning from run feedback.

        This should be called after feedback is collected to update:
        - learning_summary.json
        - patterns.json (if patterns detected)
        - Trigger comparison and conflict detection
        """
        summary_path = self.kb_path / "internal" / "insights" / "learning_summary.json"

        # Load current summary
        if summary_path.exists():
            with open(summary_path) as f:
                summary = json.load(f)
        else:
            summary = {
                "version": "1.0.0",
                "last_updated": None,
                "total_runs_analyzed": 0,
                "niches": {},
                "styles": {},
                "visual_modes": {},
                "hook_performance": {},
                "dopamine_compliance": {},
                "insights": [],
            }

        # Update run count
        summary["total_runs_analyzed"] = summary.get("total_runs_analyzed", 0) + 1
        summary["last_updated"] = datetime.now().isoformat()

        # Update niche stats
        if niche not in summary["niches"]:
            summary["niches"][niche] = {"run_count": 0, "avg_rating": None, "total_views": 0}
        summary["niches"][niche]["run_count"] += 1

        # Update style stats
        if style not in summary["styles"]:
            summary["styles"][style] = {"run_count": 0, "avg_rating": None}
        summary["styles"][style]["run_count"] += 1

        # Update visual mode stats
        if visual_mode not in summary["visual_modes"]:
            summary["visual_modes"][visual_mode] = {"run_count": 0}
        summary["visual_modes"][visual_mode]["run_count"] += 1

        # Process feedback metrics
        if feedback:
            script_quality = feedback.get("script_quality")
            hook_strength = feedback.get("hook_strength")
            views = feedback.get("views")
            retention = feedback.get("retention_pct")

            # Update niche performance
            if views:
                niche_stats = summary["niches"][niche]
                niche_stats["total_views"] = niche_stats.get("total_views", 0) + views

            # Update style rating
            if script_quality:
                style_stats = summary["styles"][style]
                current_avg = style_stats.get("avg_rating")
                run_count = style_stats["run_count"]
                if current_avg is None:
                    style_stats["avg_rating"] = script_quality
                else:
                    # Running average
                    style_stats["avg_rating"] = (
                        (current_avg * (run_count - 1) + script_quality) / run_count
                    )

        # Save updated summary
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Update markdown version
        self._update_learning_summary_md(summary)

        # Run comparison and update conflicts
        self.save_conflicts_report()

        logger.info(f"Updated learning from run {run_id}")

    def _update_learning_summary_md(self, summary: dict) -> None:
        """Update the human-readable learning summary."""
        md_path = self.kb_path / "internal" / "insights" / "learning_summary.md"

        lines = [
            "# Learning Summary",
            "",
            "*Auto-generated from run feedback and performance data.*",
            "",
            f"**Last Updated:** {summary.get('last_updated', 'Never')}",
            f"**Total Runs Analyzed:** {summary.get('total_runs_analyzed', 0)}",
            "",
            "---",
            "",
            "## Performance by Niche",
            "",
        ]

        niches = summary.get("niches", {})
        if niches:
            lines.append("| Niche | Runs | Total Views | Avg Views/Run |")
            lines.append("|-------|------|-------------|---------------|")
            for niche, data in niches.items():
                runs = data.get("run_count", 0)
                views = data.get("total_views", 0)
                avg = views / runs if runs > 0 else 0
                lines.append(f"| {niche} | {runs} | {views:,} | {avg:,.0f} |")
        else:
            lines.append("*No niche data yet.*")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Performance by Style")
        lines.append("")

        styles = summary.get("styles", {})
        if styles:
            lines.append("| Style | Runs | Avg Rating |")
            lines.append("|-------|------|------------|")
            for style, data in styles.items():
                runs = data.get("run_count", 0)
                rating = data.get("avg_rating")
                rating_str = f"{rating:.1f}/5" if rating else "-"
                lines.append(f"| {style} | {runs} | {rating_str} |")
        else:
            lines.append("*No style data yet.*")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Key Insights")
        lines.append("")

        insights = summary.get("insights", [])
        if insights:
            for insight in insights:
                lines.append(f"- {insight}")
        else:
            lines.append("*No key insights yet.*")

        with open(md_path, "w") as f:
            f.write("\n".join(lines))


def compare_internal_external(registry: Optional[KnowledgeRegistry] = None) -> ComparisonResult:
    """
    Convenience function to compare internal vs external knowledge.

    Returns:
        ComparisonResult with agreements, conflicts, and pending items
    """
    comparator = KnowledgeComparator(registry)
    return comparator.compare()
