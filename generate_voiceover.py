#!/usr/bin/env python3
"""
Generate voiceover for a content.json file using ElevenLabs.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from generators.voice_gen import generate_voice_elevenlabs


def main(content_dir: str):
    content_path = Path(content_dir) / "content.json"

    if not content_path.exists():
        print(f"Error: {content_path} not found")
        return None

    with open(content_path) as f:
        content = json.load(f)

    # Get the full script
    script = content.get("full_script", "")
    if not script:
        print("Error: No full_script in content.json")
        return None

    print(f"Script length: {len(script)} chars, ~{len(script.split())} words")
    print(f"Estimated duration: {len(script.split()) / 2.5:.0f}-{len(script.split()) / 2:.0f} seconds")
    print()
    print("Generating voiceover with ElevenLabs...")

    output_path = Path(content_dir) / "voiceover.mp3"

    # Use the generate function - returns (output_path, word_timing)
    audio_path, word_timing = generate_voice_elevenlabs(
        text=script,
        output_path=output_path,
        with_timestamps=True,
    )

    if audio_path and Path(audio_path).exists():
        print(f"\n✓ Voiceover saved: {audio_path}")

        # Save word timing
        if word_timing:
            timing_path = Path(content_dir) / "word_timing.json"
            with open(timing_path, "w") as f:
                json.dump(word_timing, f, indent=2)
            print(f"✓ Word timing saved: {timing_path}")
            print(f"  Words: {len(word_timing)}")

        # Get duration
        import subprocess
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(audio_path)],
            capture_output=True, text=True
        )
        if probe.returncode == 0:
            duration = float(probe.stdout.strip())
            print(f"  Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")

        return {"audio_path": audio_path, "word_timing": word_timing}
    else:
        print("✗ Voiceover generation failed")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_voiceover.py <content_dir>")
        sys.exit(1)

    main(sys.argv[1])
