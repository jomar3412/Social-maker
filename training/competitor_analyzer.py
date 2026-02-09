"""
Competitor Content Analyzer

Analyze viral content from successful accounts to extract patterns:
- Hook structures and types
- Vocabulary and phrasing
- Content structure
- Engagement patterns

Usage:
    from training.competitor_analyzer import CompetitorAnalyzer

    analyzer = CompetitorAnalyzer()
    analyzer.add_competitor("@factspage", "tiktok")
    analyzer.analyze_content("Did you know octopuses have 3 hearts?", "tiktok")
    patterns = analyzer.extract_patterns("fun_facts")
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
COMPETITOR_DATA_FILE = Path(__file__).parent / "competitor_data.json"


class CompetitorAnalyzer:
    """Analyze competitor content to extract viral patterns."""

    def __init__(self, anthropic_key: str = None):
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        self.data = self._load_data()

    def _load_data(self) -> dict:
        """Load competitor data from JSON file."""
        if COMPETITOR_DATA_FILE.exists():
            with open(COMPETITOR_DATA_FILE) as f:
                return json.load(f)
        return {
            "competitors": [],
            "samples": [],
            "patterns": {
                "hook_patterns": [],
                "vocabulary_frequency": {},
                "structure_analysis": {},
                "engagement_notes": [],
            },
            "last_updated": None,
        }

    def _save_data(self):
        """Save competitor data to JSON file."""
        self.data["last_updated"] = datetime.now().isoformat()
        with open(COMPETITOR_DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.anthropic_key)
        return self._client

    def add_competitor(self, handle: str, platform: str, notes: str = "") -> dict:
        """
        Register a competitor account to study.

        Args:
            handle: Account handle (e.g., @factspage)
            platform: Platform name (tiktok, instagram, youtube)
            notes: Optional notes about the account

        Returns:
            The competitor entry that was added
        """
        # Clean handle
        if not handle.startswith("@"):
            handle = f"@{handle}"

        # Check for duplicates
        existing = [c for c in self.data["competitors"]
                   if c["handle"] == handle and c["platform"] == platform]
        if existing:
            return {"error": "Competitor already registered", "existing": existing[0]}

        entry = {
            "handle": handle,
            "platform": platform.lower(),
            "notes": notes,
            "added_at": datetime.now().isoformat(),
            "samples_analyzed": 0,
        }

        self.data["competitors"].append(entry)
        self._save_data()

        return entry

    def remove_competitor(self, handle: str, platform: str = None) -> bool:
        """Remove a competitor from tracking."""
        if not handle.startswith("@"):
            handle = f"@{handle}"

        original_count = len(self.data["competitors"])

        if platform:
            self.data["competitors"] = [
                c for c in self.data["competitors"]
                if not (c["handle"] == handle and c["platform"] == platform.lower())
            ]
        else:
            self.data["competitors"] = [
                c for c in self.data["competitors"] if c["handle"] != handle
            ]

        removed = len(self.data["competitors"]) < original_count
        if removed:
            self._save_data()
        return removed

    def list_competitors(self) -> list:
        """List all registered competitors."""
        return self.data["competitors"]

    def analyze_content(
        self,
        text: str,
        platform: str,
        competitor: str = None,
        engagement: dict = None,
    ) -> dict:
        """
        Analyze a piece of content using Claude to extract patterns.

        Args:
            text: The content text (hook + script)
            platform: Source platform
            competitor: Optional competitor handle this came from
            engagement: Optional engagement metrics {views, likes, comments, shares}

        Returns:
            Analysis results including hook type, structure, vocabulary
        """
        prompt = f"""Analyze this short-form video content for viral patterns:

CONTENT:
\"\"\"{text}\"\"\"

PLATFORM: {platform}
{f'COMPETITOR: {competitor}' if competitor else ''}
{f'ENGAGEMENT: {json.dumps(engagement)}' if engagement else ''}

Analyze and respond in JSON:
{{
    "hook": {{
        "text": "The first sentence/hook",
        "type": "curiosity|controversy|revelation|impossibility|desire|social_proof",
        "technique": "What makes this hook work",
        "template": "Abstract template like 'Did you know that {{fact}}?'"
    }},
    "structure": {{
        "sections": ["hook", "setup", "reveal", "kicker"],
        "sentence_count": 0,
        "avg_sentence_length": 0,
        "has_cta": true,
        "pacing": "fast|medium|slow"
    }},
    "vocabulary": {{
        "power_words": ["list", "of", "impactful", "words"],
        "forbidden_words_found": ["any", "filler", "words"],
        "emphasis_patterns": ["ALL CAPS words", "Numbers used"]
    }},
    "content_elements": {{
        "category": "science|history|nature|space|human_body|animals|technology|psychology|food|other",
        "claim_type": "fact|myth_bust|comparison|discovery|mystery",
        "proof_provided": true,
        "emotional_trigger": "awe|curiosity|surprise|disbelief"
    }},
    "virality_factors": {{
        "scroll_stopper_score": 8,
        "shareability_score": 7,
        "comment_bait_score": 6,
        "save_worthiness": 9,
        "notes": "Why this content works or doesn't"
    }}
}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            analysis = json.loads(response_text.strip())

            # Store the sample
            sample = {
                "text": text,
                "platform": platform.lower(),
                "competitor": competitor,
                "engagement": engagement,
                "analysis": analysis,
                "analyzed_at": datetime.now().isoformat(),
            }
            self.data["samples"].append(sample)

            # Update competitor sample count
            if competitor:
                for c in self.data["competitors"]:
                    if c["handle"] == competitor:
                        c["samples_analyzed"] = c.get("samples_analyzed", 0) + 1
                        break

            self._save_data()
            return analysis

        except Exception as e:
            return {"error": str(e)}

    def extract_patterns(self, niche: str = "fun_facts") -> dict:
        """
        Aggregate patterns across all analyzed samples.

        Args:
            niche: The niche to focus on

        Returns:
            Aggregated patterns and recommendations
        """
        samples = self.data.get("samples", [])

        if not samples:
            return {"error": "No samples analyzed yet. Add some content first."}

        # Aggregate hook types
        hook_types = {}
        hook_templates = []
        power_words = {}
        categories = {}
        virality_scores = []

        for sample in samples:
            analysis = sample.get("analysis", {})

            # Hook analysis
            hook = analysis.get("hook", {})
            hook_type = hook.get("type", "unknown")
            hook_types[hook_type] = hook_types.get(hook_type, 0) + 1

            if hook.get("template"):
                hook_templates.append(hook["template"])

            # Vocabulary
            vocab = analysis.get("vocabulary", {})
            for word in vocab.get("power_words", []):
                word_lower = word.lower()
                power_words[word_lower] = power_words.get(word_lower, 0) + 1

            # Categories
            content = analysis.get("content_elements", {})
            cat = content.get("category", "other")
            categories[cat] = categories.get(cat, 0) + 1

            # Virality
            virality = analysis.get("virality_factors", {})
            if virality.get("scroll_stopper_score"):
                virality_scores.append({
                    "scroll_stopper": virality.get("scroll_stopper_score", 0),
                    "shareability": virality.get("shareability_score", 0),
                    "comment_bait": virality.get("comment_bait_score", 0),
                    "save_worthy": virality.get("save_worthiness", 0),
                })

        # Calculate averages
        avg_virality = {}
        if virality_scores:
            for key in ["scroll_stopper", "shareability", "comment_bait", "save_worthy"]:
                avg_virality[key] = sum(s[key] for s in virality_scores) / len(virality_scores)

        # Sort by frequency
        sorted_power_words = sorted(power_words.items(), key=lambda x: x[1], reverse=True)
        sorted_hook_types = sorted(hook_types.items(), key=lambda x: x[1], reverse=True)

        patterns = {
            "sample_count": len(samples),
            "hook_patterns": {
                "most_common_types": sorted_hook_types[:5],
                "templates": list(set(hook_templates))[:10],
            },
            "vocabulary": {
                "top_power_words": sorted_power_words[:20],
            },
            "categories": categories,
            "average_virality_scores": avg_virality,
            "extracted_at": datetime.now().isoformat(),
        }

        # Store patterns
        self.data["patterns"] = patterns
        self._save_data()

        return patterns

    def get_recommendations(self) -> dict:
        """
        Generate style guide recommendations from extracted patterns.

        Returns:
            Recommendations to update the style guide
        """
        patterns = self.data.get("patterns", {})

        if not patterns or patterns.get("sample_count", 0) == 0:
            patterns = self.extract_patterns()

        if "error" in patterns:
            return patterns

        recommendations = {
            "hooks": {
                "preferred_types": [t[0] for t in patterns.get("hook_patterns", {}).get("most_common_types", [])[:3]],
                "new_templates": patterns.get("hook_patterns", {}).get("templates", [])[:5],
            },
            "vocabulary": {
                "add_power_words": [w[0] for w in patterns.get("vocabulary", {}).get("top_power_words", [])[:10]],
            },
            "focus_categories": [
                cat for cat, count in patterns.get("categories", {}).items()
                if count >= 2
            ],
            "target_scores": patterns.get("average_virality_scores", {}),
            "based_on_samples": patterns.get("sample_count", 0),
        }

        return recommendations

    def clear_samples(self):
        """Clear all analyzed samples (keep competitors)."""
        self.data["samples"] = []
        self.data["patterns"] = {
            "hook_patterns": [],
            "vocabulary_frequency": {},
            "structure_analysis": {},
            "engagement_notes": [],
        }
        self._save_data()


# CLI
if __name__ == "__main__":
    import sys

    analyzer = CompetitorAnalyzer()

    if len(sys.argv) < 2:
        print("Competitor Analyzer")
        print("=" * 40)
        print("\nCommands:")
        print("  add <handle> <platform>     - Add competitor to track")
        print("  remove <handle>             - Remove competitor")
        print("  list                        - List all competitors")
        print("  analyze <text> <platform>   - Analyze content text")
        print("  patterns                    - Extract patterns from samples")
        print("  recommend                   - Get style guide recommendations")
        print("  clear                       - Clear all samples")
        print("\nExamples:")
        print("  python competitor_analyzer.py add @factspage tiktok")
        print('  python competitor_analyzer.py analyze "Did you know..." tiktok')
        sys.exit(0)

    command = sys.argv[1]

    if command == "add":
        if len(sys.argv) < 4:
            print("Usage: add <handle> <platform>")
            sys.exit(1)
        handle = sys.argv[2]
        platform = sys.argv[3]
        result = analyzer.add_competitor(handle, platform)
        print(json.dumps(result, indent=2))

    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: remove <handle>")
            sys.exit(1)
        handle = sys.argv[2]
        removed = analyzer.remove_competitor(handle)
        print(f"Removed: {removed}")

    elif command == "list":
        competitors = analyzer.list_competitors()
        if competitors:
            print(f"Tracking {len(competitors)} competitors:\n")
            for c in competitors:
                print(f"  {c['handle']} ({c['platform']}) - {c['samples_analyzed']} samples")
        else:
            print("No competitors registered yet.")

    elif command == "analyze":
        if len(sys.argv) < 4:
            print("Usage: analyze <text> <platform> [competitor]")
            sys.exit(1)
        text = sys.argv[2]
        platform = sys.argv[3]
        competitor = sys.argv[4] if len(sys.argv) > 4 else None

        print(f"Analyzing content from {platform}...")
        result = analyzer.analyze_content(text, platform, competitor)
        print(json.dumps(result, indent=2))

    elif command == "patterns":
        print("Extracting patterns from samples...")
        patterns = analyzer.extract_patterns()
        print(json.dumps(patterns, indent=2))

    elif command == "recommend":
        print("Generating recommendations...")
        recommendations = analyzer.get_recommendations()
        print(json.dumps(recommendations, indent=2))

    elif command == "clear":
        analyzer.clear_samples()
        print("Samples cleared.")

    else:
        print(f"Unknown command: {command}")
