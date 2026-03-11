"""
Music Matcher - Intelligent music selection based on script tone and energy.

RULES:
- Analyze script tone before choosing music
- Assign emotion category (calm, educational, dramatic, playful, urgent, etc.)
- Assign energy level from 1-10
- Music must match emotion category
- Music energy must be within ±1 of script's energy score
- Must not overpower narration
- Flag if no appropriate music available
"""
import json
import random
import re
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

from config.settings import MUSIC_DIR


@dataclass
class ToneAnalysis:
    """Result of script tone analysis."""
    emotion: str  # calm, educational, dramatic, playful, urgent, inspirational, mysterious
    energy: int   # 1-10 scale
    keywords: list  # Keywords that influenced the analysis
    confidence: float  # 0-1 confidence in analysis


@dataclass
class MusicMatch:
    """Result of music matching."""
    path: Optional[Path]
    matched: bool
    score: float
    emotion_match: bool
    energy_match: bool
    reason: str


# Emotion categories and their indicators
EMOTION_KEYWORDS = {
    "calm": {
        "keywords": ["peace", "relax", "gentle", "soft", "quiet", "still", "serene", "tranquil"],
        "energy_range": (1, 3),
    },
    "educational": {
        "keywords": ["learn", "fact", "know", "discover", "science", "study", "research", "understand"],
        "energy_range": (3, 5),
    },
    "dramatic": {
        "keywords": ["shock", "incredible", "unbelievable", "amazing", "blow", "mind", "crazy", "insane"],
        "energy_range": (6, 8),
    },
    "playful": {
        "keywords": ["fun", "funny", "laugh", "joke", "silly", "weird", "strange", "quirky"],
        "energy_range": (4, 6),
    },
    "urgent": {
        "keywords": ["now", "immediately", "quick", "fast", "hurry", "danger", "warning", "critical"],
        "energy_range": (7, 9),
    },
    "inspirational": {
        "keywords": ["inspire", "dream", "achieve", "success", "believe", "power", "strength", "overcome"],
        "energy_range": (5, 7),
    },
    "mysterious": {
        "keywords": ["mystery", "secret", "hidden", "unknown", "strange", "unexplained", "ancient"],
        "energy_range": (3, 5),
    },
    "thoughtful": {
        "keywords": ["think", "wonder", "consider", "reflect", "imagine", "question", "ponder"],
        "energy_range": (2, 4),
    },
}

# Music file naming conventions (for auto-categorization)
MUSIC_EMOTION_HINTS = {
    "calm": ["ambient", "peaceful", "relaxing", "chill", "soft", "gentle"],
    "educational": ["curious", "discovery", "explore", "learn", "science"],
    "dramatic": ["epic", "cinematic", "intense", "powerful", "dramatic"],
    "playful": ["fun", "quirky", "happy", "upbeat", "bouncy", "cheerful"],
    "urgent": ["tension", "suspense", "action", "fast", "driving"],
    "inspirational": ["inspire", "motivate", "uplifting", "hopeful", "triumph"],
    "mysterious": ["mystery", "dark", "eerie", "suspense", "wonder"],
    "thoughtful": ["contemplative", "reflective", "piano", "minimal"],
}


def analyze_script_tone(script: str, hook: str = "") -> ToneAnalysis:
    """
    Analyze script to determine emotion category and energy level.

    Args:
        script: Full script text
        hook: Hook text (often sets the tone)

    Returns:
        ToneAnalysis with emotion, energy, keywords, and confidence
    """
    text = f"{hook} {script}".lower()

    # Count keyword matches for each emotion
    emotion_scores = {}
    matched_keywords = {}

    for emotion, data in EMOTION_KEYWORDS.items():
        matches = []
        for keyword in data["keywords"]:
            if keyword in text:
                matches.append(keyword)
        emotion_scores[emotion] = len(matches)
        matched_keywords[emotion] = matches

    # Find dominant emotion
    if max(emotion_scores.values()) == 0:
        # No clear matches - default to educational for facts
        dominant_emotion = "educational"
        confidence = 0.5
        keywords_found = []
    else:
        dominant_emotion = max(emotion_scores, key=emotion_scores.get)
        total_matches = sum(emotion_scores.values())
        confidence = emotion_scores[dominant_emotion] / max(total_matches, 1)
        keywords_found = matched_keywords[dominant_emotion]

    # Calculate energy level based on text characteristics
    energy = _calculate_energy(text, dominant_emotion)

    return ToneAnalysis(
        emotion=dominant_emotion,
        energy=energy,
        keywords=keywords_found,
        confidence=confidence,
    )


def _calculate_energy(text: str, emotion: str) -> int:
    """Calculate energy level (1-10) based on text and emotion."""
    # Start with emotion's base energy range
    min_energy, max_energy = EMOTION_KEYWORDS[emotion]["energy_range"]
    base_energy = (min_energy + max_energy) // 2

    # Adjust based on text characteristics
    energy = base_energy

    # Exclamation marks increase energy
    exclamations = text.count('!')
    energy += min(exclamations, 2)

    # Question marks slightly increase (curiosity)
    questions = text.count('?')
    energy += min(questions // 2, 1)

    # ALL CAPS words increase energy
    caps_words = len(re.findall(r'\b[A-Z]{2,}\b', text))
    energy += min(caps_words, 2)

    # Certain words boost energy
    high_energy_words = ["incredible", "amazing", "shocking", "unbelievable", "mind-blowing"]
    for word in high_energy_words:
        if word in text:
            energy += 1

    # Certain words reduce energy
    low_energy_words = ["calm", "peaceful", "gentle", "slowly", "quietly"]
    for word in low_energy_words:
        if word in text:
            energy -= 1

    # Clamp to valid range
    return max(1, min(10, energy))


def categorize_music_file(music_path: Path) -> Tuple[str, int]:
    """
    Categorize a music file based on its filename.

    Returns:
        Tuple of (emotion_category, estimated_energy)
    """
    filename = music_path.stem.lower()

    # Check for emotion hints in filename
    for emotion, hints in MUSIC_EMOTION_HINTS.items():
        for hint in hints:
            if hint in filename:
                min_e, max_e = EMOTION_KEYWORDS[emotion]["energy_range"]
                return emotion, (min_e + max_e) // 2

    # Default: educational/neutral
    return "educational", 4


def load_music_catalog() -> list:
    """
    Load and categorize all available music files.

    Returns:
        List of {"path": Path, "emotion": str, "energy": int}
    """
    catalog = []

    if not MUSIC_DIR.exists():
        return catalog

    extensions = {".mp3", ".wav", ".m4a", ".aac"}

    for ext in extensions:
        for music_file in MUSIC_DIR.rglob(f"*{ext}"):
            emotion, energy = categorize_music_file(music_file)
            catalog.append({
                "path": music_file,
                "emotion": emotion,
                "energy": energy,
                "name": music_file.stem,
            })

    return catalog


def match_music(tone: ToneAnalysis, catalog: list = None) -> MusicMatch:
    """
    Find music that matches the script's tone and energy.

    RULES:
    - Music must match emotion category
    - Music energy must be within ±1 of script's energy
    - If no match, flag it instead of guessing

    Args:
        tone: ToneAnalysis from analyze_script_tone()
        catalog: Music catalog (auto-loaded if None)

    Returns:
        MusicMatch with path and match details
    """
    if catalog is None:
        catalog = load_music_catalog()

    if not catalog:
        return MusicMatch(
            path=None,
            matched=False,
            score=0,
            emotion_match=False,
            energy_match=False,
            reason="No music files available in library",
        )

    # Score each track
    scored_tracks = []

    for track in catalog:
        score = 0
        emotion_match = False
        energy_match = False

        # Emotion match (primary criterion)
        if track["emotion"] == tone.emotion:
            score += 5
            emotion_match = True
        elif track["emotion"] in _get_similar_emotions(tone.emotion):
            score += 2  # Partial credit for similar emotions

        # Energy match (within ±1)
        energy_diff = abs(track["energy"] - tone.energy)
        if energy_diff <= 1:
            score += 3
            energy_match = True
        elif energy_diff <= 2:
            score += 1  # Partial credit

        scored_tracks.append({
            "track": track,
            "score": score,
            "emotion_match": emotion_match,
            "energy_match": energy_match,
        })

    # Sort by score
    scored_tracks.sort(key=lambda x: x["score"], reverse=True)

    # Get best match
    best = scored_tracks[0]

    # Determine if it's a good enough match
    if best["score"] >= 6:  # Both emotion and energy match
        return MusicMatch(
            path=best["track"]["path"],
            matched=True,
            score=best["score"],
            emotion_match=best["emotion_match"],
            energy_match=best["energy_match"],
            reason=f"Good match: {best['track']['name']} ({best['track']['emotion']}, energy {best['track']['energy']})",
        )
    elif best["score"] >= 3:  # Partial match
        return MusicMatch(
            path=best["track"]["path"],
            matched=True,
            score=best["score"],
            emotion_match=best["emotion_match"],
            energy_match=best["energy_match"],
            reason=f"Partial match: {best['track']['name']} - consider adding better music for '{tone.emotion}' emotion",
        )
    else:
        # No good match - FLAG instead of guessing
        return MusicMatch(
            path=None,
            matched=False,
            score=best["score"],
            emotion_match=False,
            energy_match=False,
            reason=f"NO MATCH: Need '{tone.emotion}' music with energy level {tone.energy}±1. Best available was '{best['track']['emotion']}' with energy {best['track']['energy']}.",
        )


def _get_similar_emotions(emotion: str) -> list:
    """Get emotions that are similar/compatible."""
    similar_map = {
        "calm": ["thoughtful", "peaceful"],
        "educational": ["thoughtful", "mysterious"],
        "dramatic": ["urgent", "inspirational"],
        "playful": ["educational"],
        "urgent": ["dramatic"],
        "inspirational": ["dramatic", "educational"],
        "mysterious": ["thoughtful", "educational"],
        "thoughtful": ["calm", "mysterious"],
    }
    return similar_map.get(emotion, [])


def get_music_for_content(script: str, hook: str = "", content_type: str = "fact") -> Tuple[Optional[Path], str]:
    """
    Main entry point: Get appropriate music for content.

    Args:
        script: Full script text
        hook: Hook text
        content_type: Type of content (fact, motivation, etc.)

    Returns:
        Tuple of (music_path or None, status_message)
    """
    # Analyze script tone
    tone = analyze_script_tone(script, hook)

    print(f"\n  Music Matching:")
    print(f"    Script tone: {tone.emotion} (confidence: {tone.confidence:.0%})")
    print(f"    Energy level: {tone.energy}/10")
    if tone.keywords:
        print(f"    Keywords: {', '.join(tone.keywords)}")

    # Find matching music
    match = match_music(tone)

    if match.matched:
        print(f"    Match: {match.reason}")
        return match.path, match.reason
    else:
        print(f"    WARNING: {match.reason}")
        return None, match.reason


if __name__ == "__main__":
    # Test the music matcher
    test_scripts = [
        ("Did you know that lightning strikes the Earth 8 million times per day?",
         "This will shock you..."),
        ("Finding peace in chaos is an ancient art that few have mastered.",
         "In the silence, you'll find strength..."),
        ("Scientists just discovered something that changes everything!",
         "Breaking: This discovery will blow your mind!"),
    ]

    print("Music Matcher Test")
    print("=" * 50)

    catalog = load_music_catalog()
    print(f"Loaded {len(catalog)} music files\n")

    for script, hook in test_scripts:
        print(f"Script: {script[:50]}...")
        path, msg = get_music_for_content(script, hook)
        print(f"Result: {msg}")
        print()
