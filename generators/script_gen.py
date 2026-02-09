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
        prompt = (
            "Generate a short, powerful Stoic/motivational quote for a social media video. "
            "Respond in JSON: {\"quote\": \"...\", \"author\": \"...\", \"caption\": \"...\", "
            "\"hashtags\": [\"#...\"], \"category\": \"stoicism|motivation|discipline\"}"
        )
    elif content_type == "health":
        prompt = (
            "Generate an informative health/nutrition fact for a short social media video. "
            "Focus on a specific food, nutrient, or health benefit that's surprising but true.\n\n"
            "Format:\n"
            "- Hook: A surprising claim that makes viewers stay (desire/curiosity type)\n"
            "- Benefits: 3-4 short bullet points about the topic\n"
            "- Each benefit should mention a specific food/nutrient\n"
            "- CTA: Follow for more health tips\n\n"
            "Respond in JSON:\n"
            "{\n"
            "  \"hook\": \"This one fruit can lower your blood pressure by 20%\",\n"
            "  \"topic\": \"Bananas and blood pressure\",\n"
            "  \"benefits\": [\n"
            "    \"Bananas are rich in potassium\",\n"
            "    \"Potassium helps regulate blood pressure\",\n"
            "    \"One banana provides 9% of daily potassium\",\n"
            "    \"Studies show regular intake reduces stroke risk\"\n"
            "  ],\n"
            "  \"keywords\": [\"banana\", \"potassium\", \"blood pressure\", \"heart\"],\n"
            "  \"visual_cues\": [\"banana\", \"heart\", \"blood pressure monitor\"],\n"
            "  \"caption\": \"...\",\n"
            "  \"hashtags\": [\"#health\", \"#nutrition\", ...],\n"
            "  \"category\": \"nutrition|vitamins|superfoods|wellness\"\n"
            "}"
        )
    else:
        prompt = (
            "Generate a surprising, true fun fact for a 'Did You Know?' social media video. "
            "Respond in JSON: {\"fact\": \"...\", \"source\": \"...\", \"caption\": \"...\", "
            "\"hashtags\": [\"#...\"], \"category\": \"science|history|nature|space\"}"
        )

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=500,
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
