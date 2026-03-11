"""
Knowledge Context - builds run-scoped knowledge context from external specs and internal insights.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
import logging
import re

from .registry import KnowledgeRegistry, get_registry, DocumentEntry

logger = logging.getLogger(__name__)


@dataclass
class DopamineLevelRequirement:
    """Requirement for a dopamine level."""
    level: int
    name: str
    goal: str
    required_outputs: list[str]
    validation_rules: list[str]
    failure_conditions: list[str]


@dataclass
class KnowledgeContext:
    """
    Run-scoped knowledge context.

    Contains:
    - External rules to apply (from specs)
    - Internal insights to apply (from learning)
    - Conflicts between external and internal
    - Dopamine ladder requirements
    """
    run_id: str
    niche: str
    style: str
    visual_mode: str
    content_mode: str = "ai_generated"  # ai_generated, real_shoot, hybrid

    # From external specs
    dopamine_requirements: list[DopamineLevelRequirement] = field(default_factory=list)
    external_rules: list[dict] = field(default_factory=list)
    mode_requirements: dict = field(default_factory=dict)

    # From internal learning
    internal_insights: list[dict] = field(default_factory=list)
    applicable_patterns: list[dict] = field(default_factory=list)
    rule_overrides: list[dict] = field(default_factory=list)

    # Conflicts
    conflicts: list[dict] = field(default_factory=list)

    # Metadata
    sample_sizes: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "niche": self.niche,
            "style": self.style,
            "visual_mode": self.visual_mode,
            "content_mode": self.content_mode,
            "dopamine_requirements": [
                {
                    "level": r.level,
                    "name": r.name,
                    "goal": r.goal,
                    "required_outputs": r.required_outputs,
                    "validation_rules": r.validation_rules,
                    "failure_conditions": r.failure_conditions,
                }
                for r in self.dopamine_requirements
            ],
            "external_rules": self.external_rules,
            "mode_requirements": self.mode_requirements,
            "internal_insights": self.internal_insights,
            "applicable_patterns": self.applicable_patterns,
            "rule_overrides": self.rule_overrides,
            "conflicts": self.conflicts,
            "sample_sizes": self.sample_sizes,
            "created_at": self.created_at,
        }

    def to_markdown(self) -> str:
        """Generate human-readable markdown summary."""
        lines = [
            "# Knowledge Context",
            "",
            f"**Run ID:** {self.run_id}",
            f"**Created:** {self.created_at}",
            "",
            "## Run Configuration",
            "",
            f"- **Niche:** {self.niche}",
            f"- **Style:** {self.style}",
            f"- **Visual Mode:** {self.visual_mode}",
            f"- **Content Mode:** {self.content_mode}",
            "",
            "---",
            "",
            "## External Rules Applied",
            "",
            "### Dopamine Ladder Requirements",
            "",
        ]

        for req in self.dopamine_requirements:
            lines.append(f"#### Level {req.level} - {req.name}")
            lines.append(f"**Goal:** {req.goal}")
            lines.append("")
            lines.append("**Required Outputs:**")
            for output in req.required_outputs:
                lines.append(f"- {output}")
            lines.append("")
            if req.validation_rules:
                lines.append("**Validation Rules:**")
                for rule in req.validation_rules:
                    lines.append(f"- {rule}")
                lines.append("")
            if req.failure_conditions:
                lines.append("**Failure Conditions:**")
                for cond in req.failure_conditions:
                    lines.append(f"- {cond}")
                lines.append("")

        if self.mode_requirements:
            lines.append("### Content Mode Requirements")
            lines.append("")
            lines.append(f"**Mode:** {self.content_mode}")
            lines.append("")
            lines.append("**Required Outputs:**")
            for output in self.mode_requirements.get("required_outputs", []):
                lines.append(f"- {output}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## Internal Insights Applied")
        lines.append("")

        if self.internal_insights:
            for insight in self.internal_insights:
                lines.append(f"### {insight.get('title', 'Insight')}")
                lines.append(f"{insight.get('description', '')}")
                lines.append(f"- **Source:** {insight.get('source', 'internal learning')}")
                lines.append(f"- **Confidence:** {insight.get('confidence', 'unknown')}")
                lines.append("")
        else:
            lines.append("*No internal insights applicable for this run configuration.*")
            lines.append("")

        if self.applicable_patterns:
            lines.append("### Applicable Patterns")
            lines.append("")
            for pattern in self.applicable_patterns:
                ptype = pattern.get("type", "neutral")
                emoji = {"positive": "+", "negative": "-", "neutral": "~"}.get(ptype, "~")
                lines.append(f"- [{emoji}] {pattern.get('description', 'Pattern')}")
            lines.append("")

        if self.rule_overrides:
            lines.append("### Rule Overrides")
            lines.append("")
            for override in self.rule_overrides:
                lines.append(f"- **{override.get('id', 'Override')}:** {override.get('internal_override', {}).get('reason', '')}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## Conflicts Detected")
        lines.append("")

        if self.conflicts:
            for conflict in self.conflicts:
                lines.append(f"### {conflict.get('id', 'Conflict')}")
                lines.append(f"**External:** {conflict.get('external_value', '')}")
                lines.append(f"**Internal:** {conflict.get('internal_value', '')}")
                lines.append(f"**Resolution:** {conflict.get('resolution', 'pending')}")
                lines.append("")
        else:
            lines.append("*No conflicts detected between external specs and internal learning.*")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## Sample Sizes")
        lines.append("")
        if self.sample_sizes:
            for key, count in self.sample_sizes.items():
                lines.append(f"- **{key}:** {count} runs")
        else:
            lines.append("*No sample size data available.*")

        return "\n".join(lines)

    def save_to_run_folder(self, run_folder: Path) -> tuple[Path, Path]:
        """
        Save knowledge context to run folder.

        Returns:
            (json_path, md_path) - paths to saved files
        """
        run_folder.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = run_folder / "knowledge_context.json"
        with open(json_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        # Save Markdown
        md_path = run_folder / "knowledge_context.md"
        with open(md_path, "w") as f:
            f.write(self.to_markdown())

        logger.info(f"Saved knowledge context to {run_folder}")
        return json_path, md_path


def _parse_dopamine_spec(spec_content: str) -> list[DopamineLevelRequirement]:
    """Parse dopamine ladder requirements from spec markdown."""
    requirements = []

    # Level patterns
    level_patterns = [
        (1, "Stimulation", r"### Level 1.*?(?=### Level 2|## 3\.)"),
        (2, "Captivation", r"### Level 2.*?(?=### Level 3|## 3\.)"),
        (3, "Anticipation", r"### Level 3.*?(?=### Level 4|## 3\.)"),
        (4, "Validation", r"### Level 4.*?(?=### Level 5|## 3\.)"),
        (5, "Affection", r"### Level 5.*?(?=### Level 6|## 3\.)"),
        (6, "Revelation", r"### Level 6.*?(?=## 3\.|$)"),
    ]

    for level, name, pattern in level_patterns:
        match = re.search(pattern, spec_content, re.DOTALL)
        if match:
            section = match.group(0)

            # Extract goal
            goal_match = re.search(r"\*\*Goal:\*\*\s*(.+?)(?:\n|$)", section)
            goal = goal_match.group(1).strip() if goal_match else ""

            # Extract required outputs
            required = []
            req_match = re.search(r"\*\*Required Output.*?:\*\*\s*\n((?:- .+\n?)+)", section)
            if req_match:
                required = [
                    line.strip("- ").strip()
                    for line in req_match.group(1).strip().split("\n")
                    if line.strip().startswith("-")
                ]

            # Extract validation rules
            validation = []
            val_match = re.search(r"\*\*Validation Rule.*?:\*\*\s*\n?((?:- .+\n?|[^*\n].+\n?)+)", section)
            if val_match:
                text = val_match.group(1).strip()
                if text.startswith("-"):
                    validation = [
                        line.strip("- ").strip()
                        for line in text.split("\n")
                        if line.strip().startswith("-")
                    ]
                else:
                    validation = [text]

            # Extract failure conditions
            failures = []
            fail_match = re.search(r"\*\*Failure Conditions?:\*\*\s*\n((?:- .+\n?)+)", section)
            if fail_match:
                failures = [
                    line.strip("- ").strip()
                    for line in fail_match.group(1).strip().split("\n")
                    if line.strip().startswith("-")
                ]

            requirements.append(DopamineLevelRequirement(
                level=level,
                name=name,
                goal=goal,
                required_outputs=required,
                validation_rules=validation,
                failure_conditions=failures,
            ))

    return requirements


def _parse_mode_requirements(spec_content: str, mode: str) -> dict:
    """Parse content mode requirements from spec."""
    mode_map = {
        "ai_generated": "Mode A",
        "real_shoot": "Mode B",
        "hybrid": "Mode C",
    }

    mode_name = mode_map.get(mode, "Mode A")

    # Find mode section
    pattern = rf"### {mode_name}.*?(?=### Mode [ABC]|## 4\.|---)"
    match = re.search(pattern, spec_content, re.DOTALL)

    if not match:
        return {"mode": mode, "required_outputs": []}

    section = match.group(0)

    # Extract required outputs
    outputs = []
    out_match = re.search(r"\*\*Outputs Required:\*\*\s*\n((?:- .+\n?)+)", section)
    if out_match:
        outputs = [
            line.strip("- ").strip()
            for line in out_match.group(1).strip().split("\n")
            if line.strip().startswith("-")
        ]

    return {"mode": mode, "required_outputs": outputs}


def build_knowledge_context(
    run_id: str,
    niche: str,
    style: str,
    visual_mode: str,
    content_mode: str = "ai_generated",
    registry: Optional[KnowledgeRegistry] = None,
) -> KnowledgeContext:
    """
    Build a knowledge context for a run.

    Loads:
    - External dopamine spec requirements
    - Internal learning insights
    - Applicable patterns and rule overrides
    - Detects conflicts

    Args:
        run_id: The run identifier
        niche: Content niche (e.g., "motivation", "fun_facts")
        style: Content style (e.g., "affirming", "edgy")
        visual_mode: Visual mode (e.g., "ai_generated", "stock", "hybrid")
        content_mode: Content creation mode
        registry: Optional registry instance

    Returns:
        KnowledgeContext with all applicable knowledge
    """
    registry = registry or get_registry()

    context = KnowledgeContext(
        run_id=run_id,
        niche=niche,
        style=style,
        visual_mode=visual_mode,
        content_mode=content_mode,
    )

    # Load dopamine spec
    try:
        dopamine_spec = registry.get_dopamine_spec()
        spec_content = dopamine_spec.read_content()

        # Parse dopamine requirements
        context.dopamine_requirements = _parse_dopamine_spec(spec_content)

        # Parse mode requirements
        context.mode_requirements = _parse_mode_requirements(spec_content, content_mode)

        # Add external rule reference
        context.external_rules.append({
            "source": dopamine_spec.id,
            "title": dopamine_spec.title,
            "priority": dopamine_spec.priority,
            "applied": True,
        })

        logger.info(f"Loaded dopamine spec with {len(context.dopamine_requirements)} levels")

    except Exception as e:
        logger.warning(f"Failed to load dopamine spec: {e}")

    # Load internal learning
    learning_summary = registry.read_learning_summary()

    # Get niche-specific insights
    niche_data = learning_summary.get("niches", {}).get(niche, {})
    if niche_data:
        context.internal_insights.append({
            "title": f"Niche Performance: {niche}",
            "description": f"Based on {niche_data.get('run_count', 0)} runs",
            "source": "internal/insights/learning_summary.json",
            "confidence": "high" if niche_data.get("run_count", 0) >= registry.config.sample_size_threshold else "low",
            "data": niche_data,
        })
        context.sample_sizes[f"niche:{niche}"] = niche_data.get("run_count", 0)

    # Get style-specific insights
    style_data = learning_summary.get("styles", {}).get(style, {})
    if style_data:
        context.internal_insights.append({
            "title": f"Style Performance: {style}",
            "description": f"Based on {style_data.get('run_count', 0)} runs",
            "source": "internal/insights/learning_summary.json",
            "confidence": "high" if style_data.get("run_count", 0) >= registry.config.sample_size_threshold else "low",
            "data": style_data,
        })
        context.sample_sizes[f"style:{style}"] = style_data.get("run_count", 0)

    # Load applicable patterns
    patterns_data = registry.read_patterns()
    for pattern in patterns_data.get("positive_patterns", []) + patterns_data.get("negative_patterns", []):
        scope = pattern.get("scope", {})

        # Check if pattern applies
        niche_match = scope.get("niche") is None or scope.get("niche") == niche
        style_match = scope.get("style") is None or scope.get("style") == style
        visual_match = scope.get("visual_mode") is None or scope.get("visual_mode") == visual_mode

        if niche_match and style_match and visual_match:
            context.applicable_patterns.append(pattern)

    # Load rule overrides
    context.rule_overrides = registry.get_applicable_overrides(
        niche=niche,
        style=style,
        visual_mode=visual_mode,
    )

    # Detect conflicts (basic implementation - compare will do deeper analysis)
    # For now, just flag if internal has different recommendations than external
    for override in context.rule_overrides:
        context.conflicts.append({
            "id": f"override_{override.get('id', 'unknown')}",
            "type": "rule_override",
            "external_value": override.get("external_rule", {}).get("original_value"),
            "internal_value": override.get("internal_override", {}).get("new_value"),
            "resolution": "internal_preferred" if override.get("status") == "active" else "pending",
        })

    return context


def get_learning_context_prompt(context: KnowledgeContext) -> str:
    """
    Generate a prompt injection for script generation.

    This is injected into the AI prompt to inform generation.
    """
    lines = [
        "## Learning Context (Auto-Injected)",
        "",
        "The following rules and insights must be applied to this generation:",
        "",
        "### Dopamine Ladder Requirements",
        "",
    ]

    for req in context.dopamine_requirements:
        lines.append(f"**Level {req.level} ({req.name}):** {req.goal}")
        if req.validation_rules:
            lines.append(f"  - Validation: {'; '.join(req.validation_rules)}")

    lines.append("")
    lines.append("### Internal Insights")
    lines.append("")

    if context.internal_insights:
        for insight in context.internal_insights:
            if insight.get("confidence") == "high":
                lines.append(f"- {insight.get('title')}: {insight.get('description')}")
    else:
        lines.append("- No high-confidence internal insights available yet.")

    if context.applicable_patterns:
        lines.append("")
        lines.append("### Patterns to Consider")
        lines.append("")
        for pattern in context.applicable_patterns[:5]:  # Limit to top 5
            ptype = pattern.get("type", "neutral")
            if ptype == "positive":
                lines.append(f"- DO: {pattern.get('description', '')}")
            elif ptype == "negative":
                lines.append(f"- AVOID: {pattern.get('description', '')}")

    if context.rule_overrides:
        lines.append("")
        lines.append("### Rule Adjustments (Based on Performance)")
        lines.append("")
        for override in context.rule_overrides:
            reason = override.get("internal_override", {}).get("reason", "")
            lines.append(f"- {reason}")

    return "\n".join(lines)
