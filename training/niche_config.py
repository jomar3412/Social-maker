"""
Niche Configuration Loader

Loads and combines style guide + competitor patterns to inject into AI prompts.
This is the bridge between training data and content generation.

Usage:
    from training.niche_config import NicheConfig

    config = NicheConfig("fun_facts")
    prompt_additions = config.get_prompt_additions()
    # Inject into your AI prompts for niche-specific generation
"""

import json
from pathlib import Path
from typing import Optional

TRAINING_DIR = Path(__file__).parent
STYLE_GUIDE_FILE = TRAINING_DIR / "style_guide.json"
COMPETITOR_DATA_FILE = TRAINING_DIR / "competitor_data.json"


class NicheConfig:
    """Load and combine niche configuration for prompt injection."""

    def __init__(self, niche: str = "fun_facts"):
        self.niche = niche
        self.style_guide = self._load_style_guide()
        self.competitor_data = self._load_competitor_data()

    def _load_style_guide(self) -> dict:
        """Load the style guide JSON."""
        if STYLE_GUIDE_FILE.exists():
            with open(STYLE_GUIDE_FILE) as f:
                return json.load(f)
        return {}

    def _load_competitor_data(self) -> dict:
        """Load competitor patterns."""
        if COMPETITOR_DATA_FILE.exists():
            with open(COMPETITOR_DATA_FILE) as f:
                return json.load(f)
        return {}

    def get_voice(self) -> dict:
        """Get voice/tone configuration."""
        return self.style_guide.get("voice", {})

    def get_hook_templates(self) -> list:
        """Get hook templates from style guide + competitor patterns."""
        templates = []

        # From style guide
        hooks = self.style_guide.get("hooks", {})
        templates.extend(hooks.get("templates", []))

        # From competitor patterns
        patterns = self.competitor_data.get("patterns", {})
        hook_patterns = patterns.get("hook_patterns", {})
        if isinstance(hook_patterns, dict):
            templates.extend(hook_patterns.get("templates", []))

        return list(set(templates))  # Deduplicate

    def get_power_words(self) -> list:
        """Get power words from style guide + competitor analysis."""
        words = []

        # From style guide
        vocab = self.style_guide.get("vocabulary", {})
        words.extend(vocab.get("power_words", []))

        # From competitor patterns
        patterns = self.competitor_data.get("patterns", {})
        pattern_vocab = patterns.get("vocabulary", {})
        if isinstance(pattern_vocab, dict):
            top_words = pattern_vocab.get("top_power_words", [])
            words.extend([w[0] if isinstance(w, (list, tuple)) else w for w in top_words])

        return list(set(words))

    def get_forbidden_words(self) -> list:
        """Get words to avoid."""
        vocab = self.style_guide.get("vocabulary", {})
        return vocab.get("forbidden", [])

    def get_structure_rules(self) -> dict:
        """Get structure constraints."""
        return self.style_guide.get("structure", {})

    def get_hashtags(self, category: str = None) -> list:
        """Get relevant hashtags."""
        hashtags_config = self.style_guide.get("hashtags", {})
        tags = []

        tags.extend(hashtags_config.get("primary", []))
        tags.extend(hashtags_config.get("secondary", []))

        if category:
            cat_tags = hashtags_config.get("category_specific", {})
            tags.extend(cat_tags.get(category, []))

        return tags

    def get_prompt_additions(self) -> str:
        """
        Generate prompt additions to inject into AI prompts.

        This is the main method - returns a formatted string with all
        style/pattern rules that should be added to generation prompts.
        """
        voice = self.get_voice()
        structure = self.get_structure_rules()
        power_words = self.get_power_words()
        forbidden = self.get_forbidden_words()
        hook_templates = self.get_hook_templates()
        hooks_config = self.style_guide.get("hooks", {})

        # Build prompt additions
        additions = f"""
=== NICHE STYLE GUIDE: {self.niche.upper()} ===

VOICE & TONE:
- Tone: {voice.get('tone', 'friendly-authoritative')}
- Personality: {voice.get('personality', 'knowledgeable but approachable')}
- Reading level: {voice.get('reading_level', '8th grade')}
- Energy: {voice.get('energy', 'medium-high')}

HOOK RULES:
- Hook must be 5 seconds or less (~12 words)
- Use one of these hook types: {', '.join(hooks_config.get('types', {}).keys())}
- Example templates:
{chr(10).join(f'  - "{t}"' for t in hook_templates[:5])}

VOCABULARY:
- Power words to USE: {', '.join(power_words[:15])}
- Words to AVOID: {', '.join(forbidden)}
- Use emphasis sparingly: {', '.join(self.style_guide.get('vocabulary', {}).get('emphasis_words', []))}

STRUCTURE:
- Max {structure.get('max_sentence_words', 10)} words per sentence
- Target duration: {structure.get('target_duration', 45)} seconds
- Sections: Hook (5s) -> Setup (10s) -> Reveal (20s) -> Kicker (10s)

CONTENT RULES:
- Facts must be TRUE and verifiable
- Include source/proof when possible
- Make it visual - describe what viewers should see
- End with engagement hook (save, comment, follow)

=== END STYLE GUIDE ===
"""
        return additions.strip()

    def get_draft_prompt_additions(self) -> str:
        """Get additions specifically for the draft stage."""
        voice = self.get_voice()
        structure = self.get_structure_rules()

        return f"""
STYLE: {voice.get('tone', 'friendly-authoritative')}
PERSONALITY: {voice.get('personality', 'curious science teacher')}
MAX WORDS PER SENTENCE: {structure.get('max_sentence_words', 10)}
TARGET DURATION: {structure.get('target_duration', 45)} seconds
ENERGY: {voice.get('energy', 'medium-high')}
""".strip()

    def get_hook_prompt_additions(self) -> str:
        """Get additions specifically for hook review stage."""
        hooks_config = self.style_guide.get("hooks", {})
        templates = self.get_hook_templates()

        return f"""
HOOK TYPES TO CONSIDER:
{chr(10).join(f'- {k}: {v}' for k, v in hooks_config.get('types', {}).items())}

PROVEN TEMPLATES:
{chr(10).join(f'- "{t}"' for t in templates[:8])}

AVOID:
{chr(10).join(f'- {a}' for a in hooks_config.get('avoid', []))}
""".strip()

    def get_final_prompt_additions(self) -> str:
        """Get additions specifically for final assembly stage."""
        power_words = self.get_power_words()
        forbidden = self.get_forbidden_words()
        structure = self.get_structure_rules()

        return f"""
FINAL POLISH CHECKLIST:
1. Hook is under 12 words and impossible to scroll past
2. Every sentence is under {structure.get('max_sentence_words', 10)} words
3. Total duration ~{structure.get('target_duration', 45)} seconds
4. Uses power words: {', '.join(power_words[:10])}
5. ZERO filler words: {', '.join(forbidden[:5])}
6. Facts are accurate and provable
7. Visual cues for every key point
8. Strong ending with engagement hook
""".strip()

    def validate_content(self, content: dict) -> dict:
        """
        Validate generated content against style guide.

        Returns:
            Validation results with score and issues found
        """
        issues = []
        score = 100

        # Check hook length
        hook = content.get("hook", "")
        hook_words = len(hook.split())
        if hook_words > 15:
            issues.append(f"Hook too long: {hook_words} words (max 12)")
            score -= 10

        # Check for forbidden words
        forbidden = set(w.lower() for w in self.get_forbidden_words())
        full_text = hook + " " + " ".join(content.get("body", []))
        found_forbidden = [w for w in full_text.lower().split() if w in forbidden]
        if found_forbidden:
            issues.append(f"Forbidden words found: {found_forbidden}")
            score -= 5 * len(found_forbidden)

        # Check sentence length
        structure = self.get_structure_rules()
        max_words = structure.get("max_sentence_words", 10)
        for i, sentence in enumerate(content.get("body", [])):
            word_count = len(sentence.split())
            if word_count > max_words:
                issues.append(f"Sentence {i+1} too long: {word_count} words (max {max_words})")
                score -= 5

        # Check duration
        word_count = content.get("word_count", 0)
        expected_duration = word_count / 2.5  # ~2.5 words per second
        target = structure.get("target_duration", 45)
        if expected_duration > structure.get("max_duration", 59):
            issues.append(f"Too long: ~{expected_duration:.0f}s (max 59s)")
            score -= 15
        elif expected_duration < structure.get("min_duration", 30):
            issues.append(f"Too short: ~{expected_duration:.0f}s (min 30s)")
            score -= 10

        return {
            "score": max(0, score),
            "issues": issues,
            "passed": score >= 70,
        }


# Convenience function
def get_prompt_additions(niche: str = "fun_facts") -> str:
    """Quick access to prompt additions for a niche."""
    config = NicheConfig(niche)
    return config.get_prompt_additions()


# CLI
if __name__ == "__main__":
    import sys

    niche = sys.argv[1] if len(sys.argv) > 1 else "fun_facts"
    config = NicheConfig(niche)

    print(f"Niche Configuration: {niche}")
    print("=" * 50)

    if len(sys.argv) > 2:
        command = sys.argv[2]

        if command == "prompt":
            print(config.get_prompt_additions())
        elif command == "hooks":
            print("Hook Templates:")
            for t in config.get_hook_templates():
                print(f"  - {t}")
        elif command == "words":
            print("Power Words:", ", ".join(config.get_power_words()[:20]))
            print("\nForbidden:", ", ".join(config.get_forbidden_words()))
        elif command == "validate":
            # Quick test validation
            test_content = {
                "hook": "Did you know this one fact?",
                "body": ["Short sentence.", "Another one.", "This is the reveal."],
                "word_count": 50,
            }
            result = config.validate_content(test_content)
            print(json.dumps(result, indent=2))
        else:
            print(f"Unknown command: {command}")
    else:
        print("\nPrompt Additions Preview:")
        print("-" * 50)
        print(config.get_prompt_additions()[:500] + "...")
        print("\nCommands:")
        print("  python niche_config.py [niche] prompt   - Full prompt additions")
        print("  python niche_config.py [niche] hooks    - Hook templates")
        print("  python niche_config.py [niche] words    - Vocabulary")
        print("  python niche_config.py [niche] validate - Test validation")
