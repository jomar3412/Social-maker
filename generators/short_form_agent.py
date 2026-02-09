"""
Short-Form Content Script Agent

Generates viral short-form scripts following proven frameworks:
- Strong hook (first 5 seconds) with desire/social proof/controversy
- Fast-paced, concise body content
- "Show not tell" visual cues for editing
- Scene structure with timing
- Sound design and text overlay suggestions

Based on research from successful short-form creators.
"""
import json
import random
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# Add project root to path for imports when run directly
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import ANTHROPIC_API_KEY, HISTORY_FILE


@dataclass
class VisualCue:
    """A visual element to show on screen."""
    timestamp: float  # When to show (seconds)
    duration: float  # How long to show
    type: str  # "text", "icon", "stock_footage", "zoom_in", "zoom_out"
    content: str  # What to show
    style: Optional[str] = None  # "highlight", "glow", "animate_in", etc.


@dataclass
class SoundCue:
    """A sound effect cue for editing."""
    timestamp: float
    type: str  # "whoosh", "hit", "transition", "riser", "cash_register"
    note: str = ""


@dataclass
class Scene:
    """A scene in the video."""
    start: float
    end: float
    text: str  # What's being said
    visuals: list = field(default_factory=list)
    sounds: list = field(default_factory=list)
    camera: str = "neutral"  # "zoom_in", "zoom_out", "track"


@dataclass
class ShortFormScript:
    """Complete short-form video script with all metadata."""
    # Core content
    hook: str  # First 5 seconds - must grab attention
    body: list[str]  # Main content as sentences
    cta: Optional[str] = None  # Call to action (optional)

    # Hook analysis
    hook_type: str = ""  # "desire", "social_proof", "controversy", "curiosity"
    hook_claim: str = ""  # The attractive claim being made

    # Metadata
    content_type: str = "motivation"  # or "fact"
    estimated_duration: float = 0  # seconds
    word_count: int = 0

    # Visual/audio guidance
    keywords: list[str] = field(default_factory=list)  # Words to highlight
    visual_cues: list[dict] = field(default_factory=list)  # VisualCue as dicts
    sound_cues: list[dict] = field(default_factory=list)  # SoundCue as dicts
    scenes: list[dict] = field(default_factory=list)  # Scene as dicts

    # For posting
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)

    # Source content (for motivation/fact type)
    quote: Optional[str] = None
    author: Optional[str] = None
    fact: Optional[str] = None
    source: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    def get_full_voiceover(self) -> str:
        """Get the complete voiceover text."""
        parts = [self.hook] + self.body
        if self.cta:
            parts.append(self.cta)
        return " ".join(parts)


# Hook templates by type
HOOK_TEMPLATES = {
    "desire": [
        "What if I told you that {claim}...",
        "Here's how to {claim} in just 30 seconds.",
        "The secret to {claim} that nobody talks about.",
        "I discovered how to {claim}, and it changed everything.",
        "Want to know the fastest way to {claim}?",
    ],
    "social_proof": [
        "After studying {authority} for years, I found this.",
        "This is the exact {thing} used by {authority}.",
        "I've been doing this for {time}, here's what works.",
        "{number} people have already used this to {result}.",
        "The top 1% all do this one thing.",
    ],
    "controversy": [
        "Stop believing the lie that {common_belief}.",
        "Everything you've been told about {topic} is wrong.",
        "Here's why {popular_thing} is actually hurting you.",
        "Nobody wants you to know this about {topic}.",
        "I'm going to tell you something controversial.",
    ],
    "curiosity": [
        "Did you know that {surprising_fact}?",
        "This simple trick will blow your mind.",
        "Most people don't realize this about {topic}.",
        "The answer to {question} will surprise you.",
        "Wait until you hear what happens next.",
    ],
}

# Sound cue recommendations by visual action
SOUND_RECOMMENDATIONS = {
    "text_appear": ["whoosh", "hit"],
    "zoom_in": ["whoosh", "riser"],
    "zoom_out": ["whoosh"],
    "transition": ["whoosh", "transition"],
    "emphasis": ["hit", "impact"],
    "question": ["riser", "suspense"],
    "answer_reveal": ["hit", "cash_register", "success"],
}


class ShortFormScriptAgent:
    """
    Agent for generating and analyzing short-form video scripts.

    Follows viral content principles:
    1. Hook in first 5 seconds (desire, social proof, controversy)
    2. Fast pace - no filler words
    3. Show don't tell - visual cues throughout
    4. Strategic sound design
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("anthropic SDK required: pip install anthropic")
        return self._client

    def generate_viral_ideas(
        self,
        niche: str,
        count: int = 10,
        include_trending: bool = True,
    ) -> list[dict]:
        """
        Generate viral video ideas for a niche.

        Args:
            niche: The content niche (e.g., "stoicism", "science facts")
            count: Number of ideas to generate
            include_trending: Whether to reference current trends

        Returns:
            List of idea dicts with title, hook_type, and description
        """
        prompt = f"""Generate {count} viral short-form video ideas for the "{niche}" niche.

For each idea, provide:
1. A compelling title (under 60 chars) that makes people stop scrolling
2. The hook type: "desire", "social_proof", "controversy", or "curiosity"
3. A brief description of the content (2-3 sentences)
4. A "too good to be true" angle that creates intrigue

Focus on ideas that:
- Have low competition but high interest
- Can be explained in 30-60 seconds
- Have a clear "wow" factor or transformation
- Would make someone think "how is that possible?"

{"Consider current trends and timely topics." if include_trending else ""}

Respond in JSON format:
{{
    "ideas": [
        {{
            "title": "...",
            "hook_type": "desire|social_proof|controversy|curiosity",
            "description": "...",
            "intrigue_angle": "..."
        }}
    ]
}}"""

        message = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        result = json.loads(response_text.strip())
        return result.get("ideas", [])

    def generate_script(
        self,
        content_type: str = "motivation",
        topic: str = None,
        target_duration: float = 45.0,
        hook_type: str = None,
    ) -> ShortFormScript:
        """
        Generate a complete short-form video script.

        Args:
            content_type: "motivation" or "fact"
            topic: Optional specific topic/quote/fact
            target_duration: Target video duration in seconds
            hook_type: Force a specific hook type

        Returns:
            ShortFormScript with all elements for video production
        """
        words_target = int(target_duration * 2.5)  # ~2.5 words/second for energetic delivery

        hook_instruction = ""
        if hook_type:
            hook_instruction = f"Use a {hook_type} hook style."

        if content_type == "motivation":
            content_prompt = f"""Generate a motivational/Stoic philosophy short-form video script.
{"Based on this topic/quote: " + topic if topic else "Choose a powerful concept."}

The script MUST follow this structure:

1. HOOK (first 5 seconds, ~12 words):
   - Must immediately grab attention
   - Use one of: desire (what they'll gain), social proof (authority/results),
     controversy (challenge beliefs), or curiosity (surprising fact)
   {hook_instruction}

2. BODY (main content, ~{words_target - 20} words):
   - Short, punchy sentences (5-10 words each)
   - Get straight to the point
   - No filler words (um, like, basically, actually, you know)
   - Each sentence should move the story forward
   - Include 2-3 "visual moment" cues where we can show something on screen

3. Keywords to highlight on screen (3-5 power words)

4. Visual cues: What to show on screen at key moments (stock footage, text, icons)

Respond in JSON:
{{
    "hook": "First 5 seconds text...",
    "hook_type": "desire|social_proof|controversy|curiosity",
    "hook_claim": "The attractive claim being made",
    "body": ["Sentence 1.", "Sentence 2.", ...],
    "keywords": ["power", "words", "to", "highlight"],
    "visual_cues": [
        {{"at_sentence": 0, "type": "text|icon|stock", "content": "what to show", "style": "glow|animate"}}
    ],
    "quote": "The actual quote if applicable",
    "author": "Author name",
    "caption": "Social media caption",
    "hashtags": ["#stoicism", "#motivation", ...]
}}"""
        else:  # fact
            content_prompt = f"""Generate a "Did You Know?" fun fact short-form video script.
{"Based on this fact: " + topic if topic else "Choose a surprising, verified fact."}

The script MUST follow this structure:

1. HOOK (first 5 seconds, ~12 words):
   - Must immediately grab attention with the surprising part
   - Lead with the most unbelievable aspect
   - Create a "wait, what?" reaction
   {hook_instruction}

2. BODY (explanation, ~{words_target - 20} words):
   - Explain why this is true
   - Add context that makes it even more impressive
   - Short, punchy sentences
   - No filler words
   - Include 2-3 moments for visual elements

3. Keywords to highlight on screen (3-5 key terms)

4. Visual cues for editing

Respond in JSON:
{{
    "hook": "First 5 seconds text...",
    "hook_type": "curiosity",
    "hook_claim": "The surprising claim",
    "body": ["Sentence 1.", "Sentence 2.", ...],
    "keywords": ["scientific", "terms", "to", "highlight"],
    "visual_cues": [
        {{"at_sentence": 0, "type": "text|icon|stock", "content": "what to show"}}
    ],
    "fact": "The core fact",
    "source": "Source/verification",
    "caption": "Social media caption",
    "hashtags": ["#didyouknow", "#facts", ...]
}}"""

        message = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": content_prompt}],
        )

        response_text = message.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        data = json.loads(response_text.strip())

        # Calculate duration and word count
        full_text = data["hook"] + " " + " ".join(data["body"])
        word_count = len(full_text.split())
        estimated_duration = word_count / 2.5  # ~2.5 words/sec

        # Build sound cues based on visual cues
        sound_cues = []
        for i, vc in enumerate(data.get("visual_cues", [])):
            vc_type = vc.get("type", "text")
            if vc_type in ["text", "icon"]:
                sound_cues.append({
                    "at_sentence": vc.get("at_sentence", i),
                    "type": "whoosh",
                    "note": f"For {vc.get('content', 'visual element')}"
                })

        # Create script object
        script = ShortFormScript(
            hook=data["hook"],
            body=data["body"],
            hook_type=data.get("hook_type", "curiosity"),
            hook_claim=data.get("hook_claim", ""),
            content_type=content_type,
            estimated_duration=estimated_duration,
            word_count=word_count,
            keywords=data.get("keywords", []),
            visual_cues=data.get("visual_cues", []),
            sound_cues=sound_cues,
            caption=data.get("caption", ""),
            hashtags=data.get("hashtags", []),
            quote=data.get("quote"),
            author=data.get("author"),
            fact=data.get("fact"),
            source=data.get("source"),
        )

        return script

    def analyze_script(self, script_text: str) -> dict:
        """
        Analyze an existing script for viral potential.

        Returns a report with:
        - Hook strength score (1-10)
        - Pacing analysis
        - Filler word detection
        - Improvement suggestions
        """
        prompt = f"""Analyze this short-form video script for viral potential:

---
{script_text}
---

Evaluate based on these criteria:

1. HOOK STRENGTH (first 5 seconds):
   - Does it grab attention immediately?
   - Does it use desire, social proof, controversy, or curiosity?
   - Score 1-10

2. PACING:
   - Are sentences short and punchy?
   - Is there filler/wasted time?
   - Does it get straight to the point?
   - Score 1-10

3. FILLER WORDS:
   - List any filler words found (um, like, basically, actually, you know, so, just, really)

4. SHOW NOT TELL:
   - Are there opportunities for visual storytelling?
   - Score 1-10

5. OVERALL VIRAL POTENTIAL:
   - Combined score 1-10
   - Top 3 improvements needed

Respond in JSON:
{{
    "hook_score": 8,
    "hook_type_detected": "desire|social_proof|controversy|curiosity|weak",
    "hook_feedback": "...",
    "pacing_score": 7,
    "pacing_feedback": "...",
    "filler_words": ["word1", "word2"],
    "show_not_tell_score": 6,
    "visual_opportunities": ["moment 1", "moment 2"],
    "overall_score": 7,
    "improvements": ["1. ...", "2. ...", "3. ..."],
    "rewritten_hook": "Suggested improved hook..."
}}"""

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

        return json.loads(response_text.strip())

    def improve_script(self, script: ShortFormScript) -> ShortFormScript:
        """
        Take an existing script and improve it for viral potential.
        """
        current_text = script.get_full_voiceover()

        prompt = f"""Improve this short-form video script for maximum viral potential:

Current script:
---
{current_text}
---

Content type: {script.content_type}
Current hook type: {script.hook_type}

Rewrite to:
1. Make the hook more attention-grabbing (first 5 seconds)
2. Remove ALL filler words
3. Make sentences shorter and punchier
4. Ensure it gets to the point faster
5. Add 3-5 moments for visual elements (show not tell)

Keep the core message but make it more engaging.

Respond in JSON (same format as generate_script):
{{
    "hook": "Improved first 5 seconds...",
    "hook_type": "desire|social_proof|controversy|curiosity",
    "hook_claim": "The attractive claim",
    "body": ["Short sentence 1.", "Punchy sentence 2.", ...],
    "keywords": ["power", "words"],
    "visual_cues": [...],
    "caption": "...",
    "hashtags": [...]
}}"""

        message = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        data = json.loads(response_text.strip())

        # Preserve original metadata, update content
        full_text = data["hook"] + " " + " ".join(data["body"])
        word_count = len(full_text.split())

        improved = ShortFormScript(
            hook=data["hook"],
            body=data["body"],
            hook_type=data.get("hook_type", script.hook_type),
            hook_claim=data.get("hook_claim", script.hook_claim),
            content_type=script.content_type,
            estimated_duration=word_count / 2.5,
            word_count=word_count,
            keywords=data.get("keywords", script.keywords),
            visual_cues=data.get("visual_cues", []),
            sound_cues=script.sound_cues,
            caption=data.get("caption", script.caption),
            hashtags=data.get("hashtags", script.hashtags),
            quote=script.quote,
            author=script.author,
            fact=script.fact,
            source=script.source,
        )

        return improved

    def generate_for_pipeline(self, content_type: str = "motivation") -> dict:
        """
        Generate script in format compatible with existing pipeline.

        Returns dict with: quote/fact, author/source, caption, hashtags,
        plus new fields: hook, voiceover, keywords, visual_cues
        """
        script = self.generate_script(content_type=content_type)

        result = {
            "type": content_type,
            "hook": script.hook,
            "voiceover": script.get_full_voiceover(),
            "keywords": script.keywords,
            "visual_cues": script.visual_cues,
            "caption": script.caption,
            "hashtags": script.hashtags,
            "estimated_duration": script.estimated_duration,
            "hook_type": script.hook_type,
        }

        if content_type == "motivation":
            result["quote"] = script.quote or script.hook
            result["author"] = script.author or "Unknown"
        else:
            result["fact"] = script.fact or script.hook
            result["source"] = script.source or "Verified"

        return result


def generate_content(content_type: str = "motivation", use_agent: bool = True) -> dict:
    """
    Drop-in replacement for script_gen.generate_content().
    Uses the short-form agent for better viral content.
    """
    if not use_agent:
        # Fall back to original simple generator
        from generators.script_gen import generate_content as simple_generate
        return simple_generate(content_type)

    agent = ShortFormScriptAgent()
    return agent.generate_for_pipeline(content_type)


# CLI for testing
if __name__ == "__main__":
    import sys

    agent = ShortFormScriptAgent()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "ideas":
            niche = sys.argv[2] if len(sys.argv) > 2 else "stoicism"
            ideas = agent.generate_viral_ideas(niche, count=5)
            print(f"\nViral Ideas for '{niche}':")
            print("-" * 40)
            for i, idea in enumerate(ideas, 1):
                print(f"\n{i}. {idea['title']}")
                print(f"   Hook type: {idea['hook_type']}")
                print(f"   {idea['description']}")

        elif command == "script":
            content_type = sys.argv[2] if len(sys.argv) > 2 else "motivation"
            script = agent.generate_script(content_type=content_type)
            print(f"\nGenerated {content_type.upper()} Script:")
            print("=" * 50)
            print(f"\nHOOK ({script.hook_type}):")
            print(f"  \"{script.hook}\"")
            print(f"\nBODY:")
            for i, sentence in enumerate(script.body, 1):
                print(f"  {i}. {sentence}")
            print(f"\nKeywords: {', '.join(script.keywords)}")
            print(f"Duration: ~{script.estimated_duration:.1f}s ({script.word_count} words)")
            print(f"\nVisual Cues:")
            for vc in script.visual_cues:
                print(f"  - [{vc.get('type')}] {vc.get('content')}")

        elif command == "analyze":
            if len(sys.argv) > 2:
                script_text = " ".join(sys.argv[2:])
            else:
                script_text = input("Paste script to analyze:\n")

            analysis = agent.analyze_script(script_text)
            print(f"\nScript Analysis:")
            print("=" * 50)
            print(f"Overall Score: {analysis['overall_score']}/10")
            print(f"Hook Score: {analysis['hook_score']}/10 ({analysis['hook_type_detected']})")
            print(f"Pacing Score: {analysis['pacing_score']}/10")
            print(f"Show-Not-Tell: {analysis['show_not_tell_score']}/10")
            if analysis.get('filler_words'):
                print(f"\nFiller words found: {', '.join(analysis['filler_words'])}")
            print(f"\nImprovements:")
            for imp in analysis['improvements']:
                print(f"  {imp}")
            print(f"\nSuggested Hook: \"{analysis['rewritten_hook']}\"")

        elif command == "pipeline":
            content_type = sys.argv[2] if len(sys.argv) > 2 else "motivation"
            result = generate_content(content_type)
            print(json.dumps(result, indent=2))

        else:
            print(f"Unknown command: {command}")
            print("Usage: python short_form_agent.py [ideas|script|analyze|pipeline] [args]")

    else:
        print("Short-Form Script Agent")
        print("=" * 40)
        print("\nCommands:")
        print("  ideas [niche]     - Generate viral video ideas")
        print("  script [type]     - Generate full script (motivation/fact)")
        print("  analyze [text]    - Analyze script for viral potential")
        print("  pipeline [type]   - Generate in pipeline-compatible format")
        print("\nExamples:")
        print("  python short_form_agent.py ideas stoicism")
        print("  python short_form_agent.py script motivation")
        print("  python short_form_agent.py analyze 'Your script here...'")
