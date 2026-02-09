"""
Multi-Model Script Pipeline

Orchestrates multiple AI models for viral short-form content:

1. RESEARCH (Gemini + Grok) → Find trending topics, current relevance
2. DRAFT (ChatGPT) → Write initial script based on research
3. HOOK REVIEW (Grok) → Sharpen the hook, add edge
4. RELEVANCE REVIEW (Gemini) → Check trend alignment, suggest updates
5. FINAL ASSEMBLY (Claude) → Ensure structure, polish, finalize

Each model plays to its strengths for maximum content quality.
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import ANTHROPIC_API_KEY
from training.niche_config import NicheConfig


@dataclass
class PipelineState:
    """Tracks state through the multi-model pipeline."""
    content_type: str = "fact"
    niche: str = "fun_facts"

    # Stage 1: Research
    trending_topics: list = field(default_factory=list)
    selected_topic: str = ""
    research_notes: str = ""

    # Stage 2: Draft
    initial_script: dict = field(default_factory=dict)

    # Stage 3: Hook Review
    improved_hook: str = ""
    hook_feedback: str = ""

    # Stage 4: Relevance Review
    relevance_score: int = 0
    relevance_feedback: str = ""
    suggested_updates: list = field(default_factory=list)

    # Stage 5: Final
    final_script: dict = field(default_factory=dict)

    # Metadata
    created_at: str = ""
    models_used: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class MultiModelPipeline:
    """
    Orchestrates multiple AI models for script generation.

    Flow:
    Gemini+Grok (research) → ChatGPT (draft) → Grok (hook) →
    Gemini (relevance) → Claude (final)
    """

    def __init__(
        self,
        anthropic_key: str = None,
        openai_key: str = None,
        google_key: str = None,
        xai_key: str = None,
    ):
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY", "")
        self.google_key = google_key or os.getenv("GOOGLE_API_KEY", "")
        self.xai_key = xai_key or os.getenv("XAI_API_KEY", "")

        # Lazy-loaded clients
        self._anthropic = None
        self._openai = None
        self._gemini = None
        self._grok = None

        # Niche configuration (lazy-loaded)
        self._niche_config = None
        self._current_niche = None

    def _load_style_guide(self, niche: str = "fun_facts") -> NicheConfig:
        """Load niche-specific style guide."""
        if self._niche_config is None or self._current_niche != niche:
            self._niche_config = NicheConfig(niche)
            self._current_niche = niche
        return self._niche_config

    # === Client Properties ===

    @property
    def anthropic(self):
        if self._anthropic is None:
            import anthropic
            self._anthropic = anthropic.Anthropic(api_key=self.anthropic_key)
        return self._anthropic

    @property
    def openai(self):
        if self._openai is None:
            from openai import OpenAI
            self._openai = OpenAI(api_key=self.openai_key)
        return self._openai

    @property
    def gemini(self):
        if self._gemini is None:
            from google import genai
            self._gemini = genai.Client(api_key=self.google_key)
        return self._gemini

    @property
    def grok(self):
        """Grok uses OpenAI-compatible API."""
        if self._grok is None:
            from openai import OpenAI
            self._grok = OpenAI(
                api_key=self.xai_key,
                base_url="https://api.x.ai/v1"
            )
        return self._grok

    # === Stage 1: Research (Gemini + Grok) ===

    def research_topics(
        self,
        niche: str,
        content_type: str = "motivation",
    ) -> dict:
        """
        Use Gemini and Grok to find trending topics.

        Gemini: General trends, what's relevant now
        Grok: What's hot on X/Twitter, viral angles
        """
        results = {
            "gemini_topics": [],
            "grok_topics": [],
            "combined": [],
        }

        # Gemini: Research current trends
        gemini_prompt = f"""Find 5 trending topics in the "{niche}" space that would work well
for short-form video content ({content_type} style).

For each topic, provide:
1. The topic/angle
2. Why it's relevant right now
3. A potential hook angle

Focus on what's currently being discussed, searched for, or debated.

Respond in JSON:
{{
    "topics": [
        {{"topic": "...", "relevance": "...", "hook_angle": "..."}}
    ],
    "trending_context": "Brief overview of what's hot in this space right now"
}}"""

        try:
            response = self.gemini.models.generate_content(
                model="gemini-2.0-flash",
                contents=gemini_prompt,
            )
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            gemini_data = json.loads(text.strip())
            results["gemini_topics"] = gemini_data.get("topics", [])
            results["gemini_context"] = gemini_data.get("trending_context", "")
        except Exception as e:
            print(f"  Gemini research error: {e}")
            results["gemini_error"] = str(e)

        # Grok: Find viral/edgy angles from X
        grok_prompt = f"""You have access to real-time X/Twitter trends. Find 5 viral content angles
in the "{niche}" space for short-form video.

Look for:
- Hot debates or controversies
- Viral tweets or threads getting engagement
- "Too good to be true" claims getting attention
- Counter-intuitive takes that are blowing up

For each, provide:
1. The angle/topic
2. Why it's going viral
3. A controversial or attention-grabbing hook

Respond in JSON:
{{
    "viral_angles": [
        {{"angle": "...", "why_viral": "...", "hook": "..."}}
    ],
    "x_context": "What's the overall vibe on X right now for this niche"
}}"""

        try:
            response = self.grok.chat.completions.create(
                model="grok-2-latest",
                messages=[{"role": "user", "content": grok_prompt}],
                max_tokens=1500,
            )
            text = response.choices[0].message.content
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            grok_data = json.loads(text.strip())
            results["grok_topics"] = grok_data.get("viral_angles", [])
            results["grok_context"] = grok_data.get("x_context", "")
        except Exception as e:
            print(f"  Grok research error: {e}")
            results["grok_error"] = str(e)

        # Combine and rank topics
        all_topics = []
        for t in results.get("gemini_topics", []):
            all_topics.append({
                "topic": t.get("topic", ""),
                "source": "gemini",
                "hook_angle": t.get("hook_angle", ""),
                "context": t.get("relevance", ""),
            })
        for t in results.get("grok_topics", []):
            all_topics.append({
                "topic": t.get("angle", ""),
                "source": "grok",
                "hook_angle": t.get("hook", ""),
                "context": t.get("why_viral", ""),
            })

        results["combined"] = all_topics
        return results

    # === Stage 2: Draft Script (ChatGPT) ===

    def draft_script(
        self,
        topic: str,
        research_context: str,
        content_type: str = "fact",
        target_duration: float = 45.0,
        niche: str = "fun_facts",
    ) -> dict:
        """
        Use ChatGPT to write the initial script draft.
        """
        words_target = int(target_duration * 2.5)

        # Load style guide additions
        style_config = self._load_style_guide(niche)
        style_additions = style_config.get_draft_prompt_additions()

        prompt = f"""Write a short-form video script for this topic:

TOPIC: {topic}

RESEARCH CONTEXT: {research_context}

CONTENT TYPE: {content_type}

{style_additions}

Requirements:
1. HOOK (first 5 seconds, ~12 words): Must immediately grab attention
2. BODY (~{words_target - 20} words): Short punchy sentences, no filler, fast pace
3. Include visual cues: moments where we can show something on screen

Script rules:
- No filler words (um, like, basically, actually, you know, so, just)
- Each sentence 5-10 words max
- Get straight to the point
- Make every word count

Respond in JSON:
{{
    "hook": "First 5 seconds...",
    "hook_type": "desire|social_proof|controversy|curiosity",
    "body": ["Sentence 1.", "Sentence 2.", ...],
    "visual_cues": [
        {{"at_sentence": 0, "type": "text|icon|stock", "content": "what to show"}}
    ],
    "keywords": ["words", "to", "highlight"],
    "caption": "Social media caption",
    "hashtags": ["#tag1", "#tag2"]
}}"""

        try:
            response = self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            text = response.choices[0].message.content
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except Exception as e:
            print(f"  ChatGPT draft error: {e}")
            return {"error": str(e)}

    # === Stage 3: Hook Review (Grok) ===

    def review_hook(self, script: dict, topic: str, niche: str = "fun_facts") -> dict:
        """
        Use Grok to sharpen the hook - make it edgier, more attention-grabbing.
        """
        current_hook = script.get("hook", "")

        # Load style guide for hook templates
        style_config = self._load_style_guide(niche)
        hook_additions = style_config.get_hook_prompt_additions()

        prompt = f"""Review this hook for a short-form video and make it MORE attention-grabbing:

CURRENT HOOK: "{current_hook}"
TOPIC: {topic}
HOOK TYPE: {script.get("hook_type", "unknown")}

{hook_additions}

Your job: Make this hook IMPOSSIBLE to scroll past.

Consider:
- Is it controversial enough?
- Does it create instant curiosity?
- Would YOU stop scrolling?
- Can we add more "wait, what?" factor?

Provide 3 alternative hooks, ranked from safe to spicy.

Respond in JSON:
{{
    "current_score": 7,
    "feedback": "Why the current hook works or doesn't",
    "alternatives": [
        {{"hook": "...", "style": "safe", "why_better": "..."}},
        {{"hook": "...", "style": "medium", "why_better": "..."}},
        {{"hook": "...", "style": "spicy", "why_better": "..."}}
    ],
    "recommended": "The hook you'd use (copy one of the alternatives or current)",
    "hook_type": "desire|social_proof|controversy|curiosity"
}}"""

        try:
            response = self.grok.chat.completions.create(
                model="grok-2-latest",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )
            text = response.choices[0].message.content
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except Exception as e:
            print(f"  Grok hook review error: {e}")
            return {"error": str(e), "recommended": current_hook}

    # === Stage 4: Relevance Review (Gemini) ===

    def review_relevance(self, script: dict, topic: str, research_context: str) -> dict:
        """
        Use Gemini to check if the script is relevant to current trends.
        """
        full_script = script.get("hook", "") + " " + " ".join(script.get("body", []))

        prompt = f"""Review this short-form video script for relevance to current trends:

SCRIPT:
{full_script}

ORIGINAL TOPIC: {topic}

RESEARCH CONTEXT: {research_context}

Evaluate:
1. Is this still relevant to what's trending NOW?
2. Are there any outdated references?
3. Could we tie it better to current events/trends?
4. What's missing that would make it more timely?

Score 1-10 on relevance and provide specific suggestions.

Respond in JSON:
{{
    "relevance_score": 8,
    "feedback": "Overall assessment...",
    "outdated_elements": ["anything that feels old"],
    "missing_connections": ["trends we could tie in"],
    "suggested_updates": [
        {{"original": "sentence or phrase", "updated": "more relevant version", "reason": "why"}}
    ],
    "trending_tie_ins": ["specific current events/trends to reference"]
}}"""

        try:
            response = self.gemini.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except Exception as e:
            print(f"  Gemini relevance review error: {e}")
            return {"error": str(e), "relevance_score": 5}

    # === Stage 5: Final Assembly (Claude) ===

    def finalize_script(
        self,
        draft_script: dict,
        hook_review: dict,
        relevance_review: dict,
        content_type: str = "fact",
        niche: str = "fun_facts",
    ) -> dict:
        """
        Use Claude to bring everything together with consistent structure.
        """
        # Load style guide for final polish
        style_config = self._load_style_guide(niche)
        final_additions = style_config.get_final_prompt_additions()

        prompt = f"""You are the final editor for a short-form video script pipeline.

DRAFT SCRIPT:
Hook: {draft_script.get("hook", "")}
Body: {" ".join(draft_script.get("body", []))}

HOOK REVIEW (from Grok):
Recommended hook: {hook_review.get("recommended", "")}
Hook type: {hook_review.get("hook_type", "")}
Feedback: {hook_review.get("feedback", "")}

RELEVANCE REVIEW (from Gemini):
Score: {relevance_review.get("relevance_score", "N/A")}/10
Feedback: {relevance_review.get("feedback", "")}
Suggested updates: {json.dumps(relevance_review.get("suggested_updates", []))}

YOUR JOB:
1. Use the best hook (from Grok's review or original)
2. Apply relevant updates from Gemini's suggestions
3. Ensure consistent structure and flow
4. Remove ANY filler words
5. Keep sentences short and punchy (5-10 words max)
6. Add visual cues for editing
7. Ensure total duration ~45 seconds (~110 words)

Content type: {content_type}

{final_additions}

Respond in JSON:
{{
    "hook": "Final hook (5 seconds)...",
    "hook_type": "desire|social_proof|controversy|curiosity",
    "body": ["Sentence 1.", "Sentence 2.", ...],
    "visual_cues": [
        {{"at_sentence": 0, "type": "text|icon|stock", "content": "what to show", "style": "glow|animate"}}
    ],
    "sound_cues": [
        {{"at_sentence": 0, "type": "whoosh|hit|riser", "note": "why"}}
    ],
    "keywords": ["power", "words", "to", "highlight"],
    "caption": "Social media caption",
    "hashtags": ["#tag1", "#tag2", ...],
    "voiceover": "Complete script as one text block for TTS",
    "estimated_duration": 45,
    "word_count": 110,
    "changes_made": ["List of significant changes from draft"]
}}"""

        try:
            message = self.anthropic.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            result = json.loads(text.strip())
            result["type"] = content_type
            return result
        except Exception as e:
            print(f"  Claude finalize error: {e}")
            # Return draft with hook update as fallback
            draft_script["hook"] = hook_review.get("recommended", draft_script.get("hook", ""))
            draft_script["error"] = str(e)
            return draft_script

    # === Full Pipeline ===

    def run(
        self,
        niche: str = "fun_facts",
        content_type: str = "fact",
        topic: str = None,  # Optional: skip research and use this topic
        verbose: bool = True,
    ) -> dict:
        """
        Run the full multi-model pipeline.

        Returns the final script plus all intermediate results.
        """
        state = PipelineState(
            content_type=content_type,
            niche=niche,
            created_at=datetime.now().isoformat(),
        )

        if verbose:
            print(f"\n{'='*60}")
            print(f"  Multi-Model Script Pipeline")
            print(f"  Niche: {niche} | Type: {content_type}")
            print(f"{'='*60}\n")

        # Stage 1: Research (unless topic provided)
        if topic:
            state.selected_topic = topic
            state.research_notes = "Topic provided directly, skipping research."
            if verbose:
                print(f"[1/5] Using provided topic: {topic}\n")
        else:
            if verbose:
                print("[1/5] Researching trending topics (Gemini + Grok)...")

            research = self.research_topics(niche, content_type)
            state.trending_topics = research.get("combined", [])

            # Select best topic (first from Grok if available, else Gemini)
            grok_topics = research.get("grok_topics", [])
            gemini_topics = research.get("gemini_topics", [])

            if grok_topics:
                selected = grok_topics[0]
                state.selected_topic = selected.get("angle", "")
                state.research_notes = f"Grok context: {research.get('grok_context', '')}\n"
                state.research_notes += f"Why viral: {selected.get('why_viral', '')}"
            elif gemini_topics:
                selected = gemini_topics[0]
                state.selected_topic = selected.get("topic", "")
                state.research_notes = f"Gemini context: {research.get('gemini_context', '')}\n"
                state.research_notes += f"Relevance: {selected.get('relevance', '')}"
            else:
                # Fallback
                state.selected_topic = f"The power of {niche}"
                state.research_notes = "No research results, using fallback topic."

            state.models_used["research"] = ["gemini", "grok"]

            if verbose:
                print(f"  Found {len(state.trending_topics)} topics")
                print(f"  Selected: {state.selected_topic}\n")

        # Stage 2: Draft (ChatGPT)
        if verbose:
            print("[2/5] Drafting script (ChatGPT)...")

        draft = self.draft_script(
            topic=state.selected_topic,
            research_context=state.research_notes,
            content_type=content_type,
            niche=niche,
        )
        state.initial_script = draft
        state.models_used["draft"] = "chatgpt"

        if verbose:
            print(f"  Hook: \"{draft.get('hook', 'N/A')[:50]}...\"")
            print(f"  Body: {len(draft.get('body', []))} sentences\n")

        # Stage 3: Hook Review (Grok)
        if verbose:
            print("[3/5] Reviewing hook (Grok)...")

        hook_review = self.review_hook(draft, state.selected_topic, niche=niche)
        state.improved_hook = hook_review.get("recommended", draft.get("hook", ""))
        state.hook_feedback = hook_review.get("feedback", "")
        state.models_used["hook_review"] = "grok"

        if verbose:
            print(f"  Original score: {hook_review.get('current_score', 'N/A')}/10")
            print(f"  Recommended: \"{state.improved_hook[:50]}...\"\n")

        # Stage 4: Relevance Review (Gemini)
        if verbose:
            print("[4/5] Checking relevance (Gemini)...")

        relevance = self.review_relevance(draft, state.selected_topic, state.research_notes)
        state.relevance_score = relevance.get("relevance_score", 0)
        state.relevance_feedback = relevance.get("feedback", "")
        state.suggested_updates = relevance.get("suggested_updates", [])
        state.models_used["relevance_review"] = "gemini"

        if verbose:
            print(f"  Relevance: {state.relevance_score}/10")
            print(f"  Updates suggested: {len(state.suggested_updates)}\n")

        # Stage 5: Final Assembly (Claude)
        if verbose:
            print("[5/5] Finalizing script (Claude)...")

        final = self.finalize_script(draft, hook_review, relevance, content_type, niche=niche)
        state.final_script = final
        state.models_used["finalize"] = "claude"

        if verbose:
            print(f"  Final hook: \"{final.get('hook', 'N/A')[:50]}...\"")
            print(f"  Duration: ~{final.get('estimated_duration', 'N/A')}s")
            print(f"  Changes: {len(final.get('changes_made', []))}")

        # Build result
        result = {
            "script": state.final_script,
            "pipeline_state": state.to_dict(),
            "success": "error" not in state.final_script,
        }

        if verbose:
            print(f"\n{'='*60}")
            print(f"  Pipeline Complete!")
            print(f"{'='*60}\n")

        return result

    def generate_for_pipeline(self, content_type: str = "fact", niche: str = "fun_facts") -> dict:
        """
        Generate script in format compatible with existing video pipeline.
        """
        result = self.run(niche=niche, content_type=content_type, verbose=False)
        script = result.get("script", {})

        # Ensure required fields exist
        if content_type == "motivation":
            script.setdefault("quote", script.get("hook", ""))
            script.setdefault("author", "Unknown")
        else:
            script.setdefault("fact", script.get("hook", ""))
            script.setdefault("source", "Verified")

        script["type"] = content_type
        return script


def check_api_keys() -> dict:
    """Check which API keys are configured."""
    keys = {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY", "")),
        "openai": bool(os.getenv("OPENAI_API_KEY", "")),
        "google": bool(os.getenv("GOOGLE_API_KEY", "")),
        "xai": bool(os.getenv("XAI_API_KEY", "")),
    }
    return keys


# CLI
if __name__ == "__main__":
    import sys

    # Check keys first
    keys = check_api_keys()
    missing = [k for k, v in keys.items() if not v]

    if missing:
        print("Missing API keys:")
        for k in missing:
            env_var = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "google": "GOOGLE_API_KEY",
                "xai": "XAI_API_KEY",
            }[k]
            print(f"  {k}: Set {env_var} in .env")
        print("\nContinuing anyway (some stages may fail)...\n")

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "run":
            niche = sys.argv[2] if len(sys.argv) > 2 else "fun_facts"
            content_type = sys.argv[3] if len(sys.argv) > 3 else "fact"

            pipeline = MultiModelPipeline()
            result = pipeline.run(niche=niche, content_type=content_type)

            print("\nFinal Script:")
            print("-" * 40)
            script = result["script"]
            print(f"Hook: {script.get('hook', 'N/A')}")
            print(f"\nBody:")
            for i, s in enumerate(script.get("body", []), 1):
                print(f"  {i}. {s}")
            print(f"\nKeywords: {', '.join(script.get('keywords', []))}")

        elif command == "research":
            niche = sys.argv[2] if len(sys.argv) > 2 else "fun_facts"

            pipeline = MultiModelPipeline()
            print(f"Researching trending topics in '{niche}'...")
            research = pipeline.research_topics(niche)

            print("\nGemini Topics:")
            for t in research.get("gemini_topics", []):
                print(f"  - {t.get('topic', 'N/A')}")

            print("\nGrok Viral Angles:")
            for t in research.get("grok_topics", []):
                print(f"  - {t.get('angle', 'N/A')}")

        elif command == "keys":
            print("API Key Status:")
            for k, v in keys.items():
                status = "✓ Set" if v else "✗ Missing"
                print(f"  {k}: {status}")

        else:
            print(f"Unknown command: {command}")

    else:
        print("Multi-Model Script Pipeline")
        print("=" * 40)
        print("\nCommands:")
        print("  run [niche] [type]  - Run full pipeline")
        print("  research [niche]    - Research topics only")
        print("  keys                - Check API key status")
        print("\nExamples:")
        print("  python multi_model_pipeline.py run stoicism motivation")
        print("  python multi_model_pipeline.py research productivity")
        print("  python multi_model_pipeline.py keys")
        print("\nRequired API keys in .env:")
        print("  ANTHROPIC_API_KEY  - Claude (final assembly)")
        print("  OPENAI_API_KEY     - ChatGPT (drafting)")
        print("  GOOGLE_API_KEY     - Gemini (research + relevance)")
        print("  XAI_API_KEY        - Grok (research + hooks)")
