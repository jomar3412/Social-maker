import json
import random
from pathlib import Path
from config.settings import ANTHROPIC_API_KEY, HISTORY_FILE

PROJECT_ROOT = Path(__file__).parent.parent
CONTENT_BANK_FILE = PROJECT_ROOT / "content_bank.json"


def _load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"motivation": [], "fact": [], "health": []}


def _save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def _add_to_history(content_type, content):
    history = _load_history()
    if content_type not in history:
        history[content_type] = []
    history[content_type].append(content)
    _save_history(history)


def _load_content_bank():
    if CONTENT_BANK_FILE.exists():
        with open(CONTENT_BANK_FILE) as f:
            return json.load(f)
    return {"motivation": [], "fact": [], "health": []}


def _save_content_bank(bank):
    with open(CONTENT_BANK_FILE, "w") as f:
        json.dump(bank, f, indent=2)


def _get_used_content(content_type):
    """Get set of previously used content to avoid repeats."""
    history = _load_history()
    items = history.get(content_type, [])
    if content_type == "motivation":
        return {item.get("quote", "") for item in items}
    elif content_type == "health":
        return {item.get("topic", "") for item in items}
    else:
        return {item.get("fact", "") for item in items}


def _pick_from_bank(content_type):
    """Pick unused content from the bank. Returns None if bank is empty."""
    bank = _load_content_bank()
    available = bank.get(content_type, [])

    if not available:
        return None

    used = _get_used_content(content_type)

    # Filter out already-used content
    if content_type == "motivation":
        key = "quote"
    elif content_type == "health":
        key = "topic"
    else:
        key = "fact"
    unused = [item for item in available if item.get(key, "") not in used]

    if not unused:
        return None

    # Pick random unused item
    content = random.choice(unused)
    content["type"] = content_type
    _add_to_history(content_type, content)
    return content


def _generate_via_api(content_type):
    """Fall back to Claude API if content bank is empty."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "Content bank is empty and anthropic SDK not installed.\n"
            "Either add content to content_bank.json or: pip install anthropic"
        )

    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "Content bank is empty and no ANTHROPIC_API_KEY set.\n"
            "Add content to content_bank.json or set your API key in .env"
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    if content_type == "motivation":
        # Load style guide for motivation
        try:
            from training.niche_config import NicheConfig
            config = NicheConfig("motivation")
            style_additions = config.get_prompt_additions()
        except Exception:
            style_additions = ""

        prompt = f"""Generate a motivational script for a 45-60 second TikTok/YouTube Short.

CRITICAL RULES:
- NO historical figures or quotes (no Seneca, Marcus Aurelius, etc.)
- NO sensitive topics (slavery, holocaust, abuse, suicide, tragedies)
- Speak directly to "you" - make it personal
- Acknowledge real human struggles (exhaustion, doubt, pain)
- NOT preachy or lecturing - like a supportive friend

SCRIPT TYPES (pick one):
1. AFFIRMING: "You did good today" - validating the viewer's unseen struggles
2. FUTURE_ACCOUNTABILITY: "One year from now..." - connecting today's choices to future
3. AGGRESSIVE_ENERGY: High energy wake-up call, demanding action
4. CALM_MINIMAL: Short, peaceful, reflective
5. EDGY_FUNNY: Personality-driven, can use mild profanity, humor

{style_additions}

EXAMPLES OF GOOD HOOKS:
- "You did good today. Really good."
- "One year from today, you're either going to thank yourself or kick yourself."
- "Seems like you forgot again, so let me remind you."
- "Good morning, you gorgeous ray of sunshine."

Respond in JSON:
{{
  "script_type": "affirming|future_accountability|aggressive_energy|calm_minimal|edgy_funny",
  "hook": "First 3 seconds - emotional grab",
  "voiceover": "Full 100-130 word script (hook + body + landing)",
  "voice_direction": "e.g. calm and low, or yelling with energy, etc.",
  "caption": "Short caption for post",
  "hashtags": ["#motivation", "#mindset", ...],
  "keywords": ["key", "visual", "words"],
  "category": "self_worth|future_self|action|rest|growth"
}}"""
    elif content_type == "health":
        prompt = (
            "Generate an informative health/nutrition fact for a 65-second social media video.\n\n"
            "Requirements:\n"
            "- Hook: A surprising claim that makes viewers stay\n"
            "- Benefits: 5-6 bullet points about the topic (more detail than usual)\n"
            "- Each benefit should be a complete sentence\n"
            "- Voiceover: Complete script (~160 words)\n\n"
            "Respond in JSON:\n"
            "{\n"
            "  \"hook\": \"This one fruit can lower your blood pressure by 20%\",\n"
            "  \"topic\": \"Bananas and blood pressure\",\n"
            "  \"benefits\": [\n"
            "    \"Bananas are rich in potassium, an essential mineral.\",\n"
            "    \"Potassium helps regulate blood pressure naturally.\",\n"
            "    \"One banana provides 9% of your daily potassium needs.\",\n"
            "    \"Studies show regular intake can reduce stroke risk by 27%.\",\n"
            "    \"The fiber in bananas also supports heart health.\",\n"
            "    \"Eating one banana daily is an easy health habit.\"\n"
            "  ],\n"
            "  \"voiceover\": \"Full 160-word script combining hook, benefits, and CTA...\",\n"
            "  \"keywords\": [\"banana\", \"potassium\", \"blood pressure\", \"heart\"],\n"
            "  \"visual_cues\": [\"banana\", \"heart\", \"blood pressure monitor\"],\n"
            "  \"caption\": \"...\",\n"
            "  \"hashtags\": [\"#health\", \"#nutrition\", ...],\n"
            "  \"category\": \"nutrition|vitamins|superfoods|wellness\"\n"
            "}"
        )
    else:
        prompt = (
            "Generate a surprising, true fun fact for a 65-second 'Did You Know?' video.\n\n"
            "Requirements:\n"
            "- Hook: Attention-grabbing opening question or statement\n"
            "- Fact: The main surprising fact\n"
            "- Expansion: 3-4 sentences with more detail, context, or related facts\n"
            "- Voiceover: Complete script (~160 words) combining all elements\n\n"
            "Respond in JSON:\n"
            "{\"fact\": \"...\", \"hook\": \"...\", \"voiceover\": \"Full 160-word script...\", "
            "\"source\": \"...\", \"caption\": \"...\", \"keywords\": [\"key\", \"words\"], "
            "\"hashtags\": [\"#...\"], \"category\": \"science|history|nature|space\"}"
        )

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1000,  # Increased for longer ~160 word scripts
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    content = json.loads(response_text.strip())
    content["type"] = content_type
    _add_to_history(content_type, content)
    return content


def generate_content(content_type="motivation"):
    """
    Generate content. Tries the content bank first (free),
    falls back to Claude API if bank is empty.
    """
    # Try content bank first
    content = _pick_from_bank(content_type)
    if content:
        print(f"  (pulled from content bank)")
        return content

    # Fall back to API
    print(f"  (content bank empty, using Claude API)")
    return _generate_via_api(content_type)


if __name__ == "__main__":
    import sys
    content_type = sys.argv[1] if len(sys.argv) > 1 else "motivation"
    result = generate_content(content_type)
    print(json.dumps(result, indent=2))
