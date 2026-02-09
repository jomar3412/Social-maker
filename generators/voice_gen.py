import subprocess
import re
from pathlib import Path
import requests as http_requests
from config.settings import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, OUTPUT_DIR

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


def _build_voiceover_text(content):
    """Build the text to be spoken based on content type."""
    # Use expanded voiceover script if available (longer, better for video)
    if "voiceover" in content:
        return content["voiceover"]

    # Fallback to basic quote/fact
    if content["type"] == "motivation":
        quote = content["quote"]
        author = content.get("author", "Unknown")
        if author and author != "Unknown":
            return f"{quote}... {author}."
        return quote
    elif content["type"] == "health":
        # Build voiceover from hook + benefits + CTA
        hook = content.get("hook", "")
        benefits = content.get("benefits", [])
        parts = [hook] if hook else []
        parts.extend(benefits)
        parts.append("Follow for more health tips.")
        return " ".join(parts)
    elif content["type"] == "fact":
        fact = content["fact"]
        return f"Did you know? {fact}"
    return content.get("quote", content.get("fact", ""))


def _chars_to_words(characters, text):
    """
    Convert character-level timing from ElevenLabs to word-level timing.

    Args:
        characters: List of {"character": "x", "start_time": 0.0, "end_time": 0.1}
        text: The original text

    Returns:
        List of {"word": "hello", "start": 0.0, "end": 0.5}
    """
    if not characters:
        return []

    words = []
    current_word = ""
    word_start = None
    word_end = None

    for char_info in characters:
        char = char_info.get("character", "")
        start = char_info.get("start_time", 0)
        end = char_info.get("end_time", 0)

        # Check if character is a word boundary (space or punctuation at word end)
        if char in " \t\n" or char == "":
            if current_word:
                words.append({
                    "word": current_word,
                    "start": word_start,
                    "end": word_end,
                })
                current_word = ""
                word_start = None
                word_end = None
        else:
            if word_start is None:
                word_start = start
            current_word += char
            word_end = end

    # Don't forget the last word
    if current_word:
        words.append({
            "word": current_word,
            "start": word_start,
            "end": word_end,
        })

    return words


def _estimate_word_timing(text, total_duration):
    """
    Fallback: estimate word timing based on word count and total duration.
    Used when ElevenLabs timestamps fail or for pyttsx3.

    Args:
        text: The voiceover text
        total_duration: Total audio duration in seconds

    Returns:
        List of {"word": "hello", "start": 0.0, "end": 0.5}
    """
    # Split text into words, preserving punctuation attached to words
    words_raw = text.split()
    if not words_raw:
        return []

    # Calculate time per word (simple linear distribution)
    time_per_word = total_duration / len(words_raw)

    words = []
    for i, word in enumerate(words_raw):
        words.append({
            "word": word,
            "start": i * time_per_word,
            "end": (i + 1) * time_per_word,
        })

    return words


def generate_voice_elevenlabs(text, output_path, with_timestamps=False):
    """
    Generate voiceover using ElevenLabs REST API.

    Args:
        text: Text to convert to speech
        output_path: Path to save the audio file
        with_timestamps: If True, use the timestamps endpoint and return timing data

    Returns:
        If with_timestamps=False: output_path
        If with_timestamps=True: (output_path, word_timing_list)
    """
    if with_timestamps:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/with-timestamps"
    else:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.6,
            "similarity_boost": 0.75,
            "style": 0.4,
            "use_speaker_boost": True,
        },
    }

    response = http_requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs error {response.status_code}: {response.text[:300]}")

    if with_timestamps:
        # Response is JSON with audio (base64) and alignment data
        import base64
        result = response.json()

        # Extract and save audio
        audio_b64 = result.get("audio_base64", "")
        if audio_b64:
            audio_bytes = base64.b64decode(audio_b64)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)

        # Extract character-level alignment and convert to word-level
        alignment = result.get("alignment", {})
        characters = alignment.get("characters", [])
        char_start_times = alignment.get("character_start_times_seconds", [])
        char_end_times = alignment.get("character_end_times_seconds", [])

        # Build character info list
        char_info_list = []
        for i, char in enumerate(characters):
            char_info_list.append({
                "character": char,
                "start_time": char_start_times[i] if i < len(char_start_times) else 0,
                "end_time": char_end_times[i] if i < len(char_end_times) else 0,
            })

        word_timing = _chars_to_words(char_info_list, text)
        return output_path, word_timing
    else:
        # Standard response is raw audio bytes
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path


def generate_voice_pyttsx3(text, output_path, with_timestamps=False):
    """
    Generate voiceover using pyttsx3 (free, offline fallback).

    Args:
        text: Text to convert to speech
        output_path: Path to save the audio file
        with_timestamps: If True, estimate word timing (pyttsx3 doesn't provide real timestamps)

    Returns:
        If with_timestamps=False: output_path
        If with_timestamps=True: (output_path, word_timing_list)
    """
    engine = pyttsx3.init()
    engine.setProperty("rate", 150)
    engine.setProperty("volume", 1.0)

    wav_path = str(output_path).replace(".mp3", ".wav")
    engine.save_to_file(text, wav_path)
    engine.runAndWait()

    if str(output_path).endswith(".mp3"):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame",
                 "-qscale:a", "2", str(output_path)],
                capture_output=True, check=True,
            )
            Path(wav_path).unlink(missing_ok=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            output_path = Path(wav_path)

    if with_timestamps:
        # Get audio duration for timing estimation
        import json
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(output_path)],
            capture_output=True, text=True,
        )
        info = json.loads(result.stdout)
        duration = float(info["format"]["duration"])
        word_timing = _estimate_word_timing(text, duration)
        return output_path, word_timing

    return output_path


def generate_voice(content, output_path=None, with_timestamps=False):
    """
    Generate voiceover audio from content.

    Args:
        content: Content dict with "voiceover", "quote", or "fact" key
        output_path: Path to save the audio file
        with_timestamps: If True, return word-level timing data for subtitles

    Returns:
        If with_timestamps=False: output_path
        If with_timestamps=True: (output_path, word_timing_list, text)
            word_timing_list = [{"word": "hello", "start": 0.0, "end": 0.5}, ...]
    """
    text = _build_voiceover_text(content)

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / "voiceover.mp3"

    if ELEVENLABS_API_KEY:
        print("Using ElevenLabs for voiceover...")
        result = generate_voice_elevenlabs(text, output_path, with_timestamps=with_timestamps)
        if with_timestamps:
            audio_path, word_timing = result
            return audio_path, word_timing, text
        return result
    elif PYTTSX3_AVAILABLE:
        print("Using pyttsx3 (offline) for voiceover...")
        result = generate_voice_pyttsx3(text, output_path, with_timestamps=with_timestamps)
        if with_timestamps:
            audio_path, word_timing = result
            return audio_path, word_timing, text
        return result
    else:
        raise RuntimeError(
            "No TTS engine available. Set ELEVENLABS_API_KEY or install pyttsx3."
        )


if __name__ == "__main__":
    test_content = {
        "type": "motivation",
        "voiceover": "We suffer more often in imagination than in reality. Seneca wrote this nearly two thousand years ago, and it's still the most important lesson you'll ever learn. Think about it. How many nights have you lost sleep over something that never happened? How many opportunities did you miss because you were afraid of a future that didn't exist? Your mind is your greatest weapon, but it can also be your worst enemy. Stop fighting battles that aren't real. The present moment is all you have. Use it.",
    }

    # Test with timestamps
    print("Testing with timestamps...")
    result = generate_voice(test_content, with_timestamps=True)
    if isinstance(result, tuple):
        path, word_timing, text = result
        print(f"Generated voiceover: {path}")
        print(f"Word timing entries: {len(word_timing)}")
        if word_timing:
            print(f"First 5 words: {word_timing[:5]}")
            print(f"Last 5 words: {word_timing[-5:]}")
    else:
        print(f"Generated voiceover: {result}")
