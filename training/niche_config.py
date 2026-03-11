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
COMPETITOR_DATA_FILE = TRAINING_DIR / "competitor_data.json"

# Niche-specific style guide files
STYLE_GUIDE_FILES = {
    "fun_facts": TRAINING_DIR / "style_guide.json",
    "motivation": TRAINING_DIR / "motivation_style_guide.json",
    "brand": TRAINING_DIR / "brand_style_guide.json",
    "short_stories": TRAINING_DIR / "short_stories_style_guide.json",
}


class NicheConfig:
    """Load and combine niche configuration for prompt injection."""

    def __init__(self, niche: str = "fun_facts"):
        self.niche = niche
        self.style_guide = self._load_style_guide()
        self.competitor_data = self._load_competitor_data()
        self.examples = self._load_examples()

    def _load_style_guide(self) -> dict:
        """Load the niche-specific style guide JSON."""
        style_file = STYLE_GUIDE_FILES.get(self.niche)
        if style_file and style_file.exists():
            with open(style_file) as f:
                return json.load(f)
        # Fallback to default
        default = TRAINING_DIR / "style_guide.json"
        if default.exists():
            with open(default) as f:
                return json.load(f)
        return {}

    def _load_examples(self) -> list:
        """Load example scripts for this niche."""
        examples_file = TRAINING_DIR / f"{self.niche}_examples.txt"
        if examples_file.exists():
            with open(examples_file) as f:
                return f.read()
        return ""

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

    def get_script_types(self) -> dict:
        """Get script types for motivation niche."""
        return self.style_guide.get("script_types", {})

    def get_content_rules(self) -> dict:
        """Get content rules including topics to avoid."""
        return self.style_guide.get("content_rules", {})

    def get_prompt_additions(self, script_type: str = None, genre: str = None) -> str:
        """
        Generate prompt additions to inject into AI prompts.

        This is the main method - returns a formatted string with all
        style/pattern rules that should be added to generation prompts.
        """
        if self.niche == "motivation":
            return self._get_motivation_prompt_additions(script_type)

        if self.niche == "brand":
            return self._get_brand_prompt_additions(script_type)

        if self.niche == "short_stories":
            return self._get_short_stories_prompt_additions(genre)

        return self._get_facts_prompt_additions()

    def _get_motivation_prompt_additions(self, script_type: str = None) -> str:
        """Generate prompt additions for motivation niche."""
        voice = self.get_voice()
        structure = self.get_structure_rules()
        power_words = self.get_power_words()
        forbidden = self.get_forbidden_words()
        hook_templates = self.get_hook_templates()
        hooks_config = self.style_guide.get("hooks", {})
        script_types = self.get_script_types()
        content_rules = self.get_content_rules()

        # Script type specific info
        script_type_info = ""
        if script_type and script_type in script_types:
            st = script_types[script_type]
            script_type_info = f"""
SCRIPT TYPE: {script_type.upper()}
- Description: {st.get('description', '')}
- Voice style: {st.get('voice_style', '')}
- Energy level: {st.get('energy', '')}
- Themes: {', '.join(st.get('themes', []))}
- Example openers:
{chr(10).join(f'  - "{o}"' for o in st.get('example_openers', []))}
"""
        else:
            # Show available types
            script_type_info = f"""
AVAILABLE SCRIPT TYPES (pick one that fits):
{chr(10).join(f'- {k}: {v.get("description", "")}' for k, v in script_types.items())}
"""

        # Topics to avoid
        avoid_topics = content_rules.get("topics_to_avoid", [])
        allowed_themes = content_rules.get("allowed_themes", [])

        # Include example scripts
        examples_section = ""
        if self.examples:
            examples_section = f"""

REAL VIRAL EXAMPLES (study these patterns):
{self.examples[:2000]}
"""

        additions = f"""
=== NICHE STYLE GUIDE: MOTIVATION ===

VOICE & TONE:
- Tone: {voice.get('tone', 'direct-personal')}
- Personality: {voice.get('personality', 'supportive friend who tells it like it is')}
- Reading level: {voice.get('reading_level', 'conversational')}
- Speak directly TO the viewer using "you"
{script_type_info}

HOOK RULES:
- Hook must grab emotion in first 3 seconds
- Use direct address - speak to ONE person
- Hook types: {', '.join(hooks_config.get('types', {}).keys())}
- Example hooks:
{chr(10).join(f'  - "{t}"' for t in hook_templates[:5])}

THINGS TO AVOID (CRITICAL):
{chr(10).join(f'- {a}' for a in hooks_config.get('avoid', []))}
- NEVER use these topics: {', '.join(avoid_topics)}

ALLOWED THEMES:
{', '.join(allowed_themes)}

VOCABULARY:
- Power words: {', '.join(power_words[:15])}
- NEVER use: {', '.join(forbidden)}
- Emphasis phrases: {', '.join(self.style_guide.get('vocabulary', {}).get('emphasis_phrases', []))}

STRUCTURE:
- Max {structure.get('max_sentence_words', 15)} words per sentence
- Target duration: {structure.get('target_duration', 45)} seconds
- Hook (3s) -> Body (30s) -> Landing (10s)

CONTENT RULES:
- Must feel PERSONAL, not preachy
- Acknowledge real struggles (pain, doubt, exhaustion)
- No toxic positivity - be real
- End with affirmation, not lecture
{examples_section}
=== END STYLE GUIDE ===
"""
        return additions.strip()

    def _get_facts_prompt_additions(self) -> str:
        """Generate prompt additions for fun_facts niche."""
        voice = self.get_voice()
        structure = self.get_structure_rules()
        power_words = self.get_power_words()
        forbidden = self.get_forbidden_words()
        hook_templates = self.get_hook_templates()
        hooks_config = self.style_guide.get("hooks", {})

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

    def _get_brand_prompt_additions(self, script_type: str = None) -> str:
        """Generate prompt additions for brand/UGC niche."""
        voice = self.get_voice()
        structure = self.get_structure_rules()
        power_words = self.get_power_words()
        forbidden = self.get_forbidden_words()
        hook_templates = self.get_hook_templates()
        hooks_config = self.style_guide.get("hooks", {})
        script_types = self.get_script_types()
        content_rules = self.get_content_rules()
        visual_style = self.style_guide.get("visual_style", {})

        # Script type specific info
        script_type_info = ""
        if script_type and script_type in script_types:
            st = script_types[script_type]
            script_type_info = f"""
SCRIPT TYPE: {script_type.upper()}
- Description: {st.get('description', '')}
- Voice style: {st.get('voice_style', '')}
- Energy level: {st.get('energy', '')}
- Structure: {st.get('structure', '')}
- Example openers:
{chr(10).join(f'  - "{o}"' for o in st.get('example_openers', []))}
"""
        else:
            # Show available types
            script_type_info = f"""
AVAILABLE SCRIPT TYPES (pick one that fits):
{chr(10).join(f'- {k}: {v.get("description", "")}' for k, v in script_types.items())}
"""

        # Visual requirements
        visual_reqs = visual_style.get("requirements", [])

        additions = f"""
=== NICHE STYLE GUIDE: BRAND/UGC CONTENT ===

VOICE & TONE:
- Tone: {voice.get('tone', 'authentic-conversational')}
- Personality: {voice.get('personality', 'trusted friend recommending product')}
- Reading level: {voice.get('reading_level', 'conversational')}
- Energy: {voice.get('energy', 'enthusiastic but genuine')}
{script_type_info}

HOOK RULES:
- Hook must feel authentic and relatable
- NO hard sell in the hook
- Hook types: {', '.join(hooks_config.get('types', {}).keys())}
- Example hooks:
{chr(10).join(f'  - "{t}"' for t in hook_templates[:5])}

THINGS TO AVOID (CRITICAL):
{chr(10).join(f'- {a}' for a in hooks_config.get('avoid', []))}

VISUAL STYLE:
- Aesthetic: {visual_style.get('aesthetic', 'photorealistic')}
- Camera style: {visual_style.get('camera_style', 'iPhone-quality UGC')}
- Format: {visual_style.get('format', 'vertical 9:16')}
- Requirements:
{chr(10).join(f'  - {r}' for r in visual_reqs)}

VOCABULARY:
- Power words: {', '.join(power_words[:15])}
- Authentic phrases: {', '.join(self.style_guide.get('vocabulary', {}).get('authentic_phrases', []))}
- NEVER use: {', '.join(forbidden)}

STRUCTURE:
- Max {structure.get('max_sentence_words', 15)} words per sentence
- Target duration: {structure.get('target_duration', 30)} seconds
- Hook (3s) -> Problem (5s) -> Solution (10s) -> Demo (8s) -> CTA (4s)

CONTENT RULES:
- Must feel AUTHENTIC, not scripted
- Show genuine reaction/emotion
- Include specific benefit mentioned
- Natural environment, not over-produced
- Soft CTA, not pushy

REQUIRED ELEMENTS:
{chr(10).join(f'- {e}' for e in content_rules.get('required_elements', []))}

=== END STYLE GUIDE ===
"""
        return additions.strip()

    def _get_short_stories_prompt_additions(self, genre: str = None) -> str:
        """Generate prompt additions for short_stories niche."""
        voice = self.get_voice()
        structure = self.get_structure_rules()
        power_words = self.get_power_words()
        forbidden = self.get_forbidden_words()
        hook_templates = self.get_hook_templates()
        hooks_config = self.style_guide.get("hooks", {})
        genres = self.style_guide.get("genres", {})
        story_structure = self.style_guide.get("story_structure", {})
        ending_types = self.style_guide.get("ending_types", {})

        # Genre-specific info
        genre_info = ""
        if genre and genre in genres:
            g = genres[genre]
            genre_info = f"""
GENRE: {genre.upper()}
- Description: {g.get('description', '')}
- Voice style: {g.get('voice_style', '')}
- Energy level: {g.get('energy', '')}
- Pacing: {g.get('pacing', '')}
- Recommended voice: {g.get('recommended_voice', 'Ethan')}
- Music style: {g.get('music_style', '')}
- Visual style: {g.get('visual_style', '')}
- Themes: {', '.join(g.get('themes', []))}
"""
        else:
            # Show available genres
            genre_info = f"""
AVAILABLE GENRES (pick one that fits):
{chr(10).join(f'- {k}: {v.get("description", "")}' for k, v in genres.items())}
"""

        # Story structure breakdown
        hook_info = story_structure.get("hook", {})
        buildup_info = story_structure.get("buildup", {})
        twist_info = story_structure.get("twist", {})

        # Include example scripts
        examples_section = ""
        if self.examples:
            examples_section = f"""

EXAMPLE STORIES (study these patterns):
{self.examples[:2000]}
"""

        additions = f"""
=== NICHE STYLE GUIDE: SHORT STORIES ===

VOICE & TONE:
- Tone: {voice.get('tone', 'narrative-immersive')}
- Personality: {voice.get('personality', 'masterful storyteller')}
- Reading level: {voice.get('reading_level', 'conversational')}
- Energy: {voice.get('energy', 'varies by genre')}
{genre_info}

STORY STRUCTURE:
1. HOOK ({hook_info.get('duration', 5)}s, ~{hook_info.get('word_count', 15)} words)
   Purpose: {hook_info.get('purpose', 'Grab attention')}
   Techniques:
{chr(10).join(f'   - {t}' for t in hook_info.get('techniques', []))}

2. BUILDUP ({buildup_info.get('duration', 35)}s, ~{buildup_info.get('word_count', 150)} words)
   Purpose: {buildup_info.get('purpose', 'Develop tension')}
   Elements:
{chr(10).join(f'   - {e}' for e in buildup_info.get('elements', []))}

3. TWIST ({twist_info.get('duration', 15)}s, ~{twist_info.get('word_count', 50)} words)
   Purpose: {twist_info.get('purpose', 'Deliver payoff')}
   Types:
{chr(10).join(f'   - {t}' for t in twist_info.get('types', []))}

HOOK RULES:
- Hook must create immediate intrigue or tension
- Use one of these hook types: {', '.join(hooks_config.get('types', {}).keys())}
- Example templates:
{chr(10).join(f'  - "{t}"' for t in hook_templates[:5])}

THINGS TO AVOID:
{chr(10).join(f'- {a}' for a in hooks_config.get('avoid', []))}

ENDING TYPES:
{chr(10).join(f'- {k}: {v}' for k, v in ending_types.items())}

VOCABULARY:
- Power words: {', '.join(power_words[:15])}
- NEVER use: {', '.join(forbidden)}

STRUCTURE:
- Max {structure.get('max_sentence_words', 20)} words per sentence
- Target duration: {structure.get('target_duration', 60)} seconds
- Target word count: {structure.get('target_word_count', 250)} words
- Target scenes: {structure.get('scenes_target', 10)}

CHARACTER CONSISTENCY:
- Create detailed character description FIRST
- Include: age, gender, hair, clothing, distinctive features
- Use same description for all scenes with that character
- Track which characters appear in which scenes

CONTENT RULES:
- Story must have a clear beginning, middle, and end
- Each scene should advance the plot
- Show, don't tell
- Use sensory details
- End with impact (twist, cliffhanger, or resolution)
{examples_section}
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
