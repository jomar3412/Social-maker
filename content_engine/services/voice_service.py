"""
VoiceService: Audio generation for content_engine.

Handles:
- ElevenLabs TTS generation
- Per-scene audio segmentation (timestamps)
- Audio file management and cleanup
- Voice preset configuration
"""

import os
import json
import logging
import time
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


def _load_env_if_needed():
    import os
    from pathlib import Path
    if not os.environ.get('ELEVENLABS_API_KEY'):
        env_path = Path(__file__).parents[3] / '.env'
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    os.environ.setdefault(k.strip(), v.strip())

_load_env_if_needed()


def _get_mp3_duration(path) -> float:
    try:
        data = path.read_bytes()
        total_dur = 0.0
        frames = 0
        i = 0
        sr_map = {0: 44100, 1: 48000, 2: 32000}
        bitrates_tbl = [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0]
        while i < len(data) - 4:
            if data[i] == 0xFF and (data[i+1] & 0xE0) == 0xE0:
                b1, b2 = data[i+1], data[i+2]
                layer = (b1 >> 1) & 0x03
                bi = (b2 >> 4) & 0x0F
                si = (b2 >> 2) & 0x03
                if layer == 1 and 0 < bi < 15 and si < 3:
                    br = bitrates_tbl[bi] * 1000
                    sr = sr_map[si]
                    pad = (b2 >> 1) & 0x01
                    fs = 144 * br // sr + pad
                    if fs > 4:
                        total_dur += 1152 / sr
                        frames += 1
                        i += fs
                        if frames > 300:
                            avg = i / frames
                            return (len(data) / avg) * (1152 / sr)
                        continue
            i += 1
        return total_dur
    except Exception:
        return 0.0


class VoiceProvider(Enum):
    """Available voice providers."""
    ELEVENLABS = "elevenlabs"
    STUB = "stub"  # For testing without API


@dataclass
class VoiceSettings:
    """Voice generation settings."""
    provider: VoiceProvider = VoiceProvider.ELEVENLABS
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel (default ElevenLabs)
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True
    model_id: str = "eleven_v3"
    speed: float = 1.0
    language_code: str = "en"

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceSettings":
        provider = data.get("provider", "elevenlabs")
        return cls(
            provider=VoiceProvider(provider) if isinstance(provider, str) else provider,
            voice_id=data.get("voice_id", "21m00Tcm4TlvDq8ikWAM"),
            stability=data.get("stability", 0.5),
            similarity_boost=data.get("similarity_boost", 0.75),
            style=data.get("style", 0.0),
            use_speaker_boost=data.get("use_speaker_boost", True),
            model_id=data.get("model_id", "eleven_v3"),
            speed=data.get("speed", 1.0),
            language_code=data.get("language_code", "en"),
        )

    def to_dict(self) -> dict:
        return {
            "provider": self.provider.value,
            "voice_id": self.voice_id,
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "use_speaker_boost": self.use_speaker_boost,
            "model_id": self.model_id,
            "speed": self.speed,
            "language_code": self.language_code,
        }


@dataclass
class SceneTimestamp:
    """Timestamp data for a scene in the audio."""
    scene_number: int
    start_time: float  # seconds
    end_time: float  # seconds
    text: str
    beat_type: str = ""

    def to_dict(self) -> dict:
        return {
            "scene_number": self.scene_number,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.end_time - self.start_time,
            "text": self.text,
            "beat_type": self.beat_type,
        }


@dataclass
class VoiceGenerationResult:
    """Result of voice generation."""
    success: bool
    audio_path: Optional[Path] = None
    duration_seconds: float = 0.0
    scene_timestamps: list[SceneTimestamp] = field(default_factory=list)
    error_message: Optional[str] = None
    settings_used: Optional[VoiceSettings] = None
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "audio_path": str(self.audio_path) if self.audio_path else None,
            "duration_seconds": self.duration_seconds,
            "scene_timestamps": [s.to_dict() for s in self.scene_timestamps],
            "error_message": self.error_message,
            "settings_used": self.settings_used.to_dict() if self.settings_used else None,
            "version": self.version,
            "created_at": self.created_at,
        }


# Common ElevenLabs voice presets
VOICE_PRESETS = {
    "deep_motivational": {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel
        "display_name": "Deep Motivational",
        "description": "Rich, inspiring voice",
        "stability": 0.6,
        "similarity_boost": 0.8,
    },
    "neutral_ai": {
        "voice_id": "EXAVITQu4vr4xnSDxMaL",  # Sarah
        "display_name": "Neutral AI",
        "description": "Clean, professional",
        "stability": 0.7,
        "similarity_boost": 0.7,
    },
    "energetic": {
        "voice_id": "jBpfuIE2acCO8z3wKNLl",  # Gigi
        "display_name": "Energetic",
        "description": "Fast-paced, high energy",
        "stability": 0.4,
        "similarity_boost": 0.85,
    },
    "calm_reflective": {
        "voice_id": "onwK4e9ZLuTAKqWW03F9",  # Daniel
        "display_name": "Calm Reflective",
        "description": "Peaceful, thoughtful",
        "stability": 0.8,
        "similarity_boost": 0.6,
    },
}


class VoiceService:
    """
    Service for generating voiceover audio.

    Supports ElevenLabs API (v2.x client) and stub mode for testing.
    Uses client.text_to_speech.convert() — compatible with SDK v2.34.0+
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_settings: Optional[VoiceSettings] = None,
    ):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        self.default_settings = default_settings or VoiceSettings()
        self._elevenlabs_available = bool(self.api_key)

    def get_available_voices(self) -> list[dict]:
        """Get list of available voice presets."""
        return [
            {"name": name, **preset}
            for name, preset in VOICE_PRESETS.items()
        ]

    def generate_voiceover(
        self,
        script: str,
        output_dir: Path,
        settings: Optional[VoiceSettings] = None,
        scenes: Optional[list[dict]] = None,
        version: int = 1,
    ) -> VoiceGenerationResult:
        """
        Generate voiceover audio from script.

        Args:
            script: Full script text
            output_dir: Directory to save audio file
            settings: Voice settings (uses defaults if not provided)
            scenes: Scene breakdown for timestamp calculation
            version: Version number for this generation

        Returns:
            VoiceGenerationResult with audio path and timestamps
        """
        settings = settings or self.default_settings

        if not self._elevenlabs_available or settings.provider == VoiceProvider.STUB:
            return self._generate_stub(script, output_dir, settings, scenes, version)

        return self._generate_elevenlabs(script, output_dir, settings, scenes, version)

    def _generate_elevenlabs(
        self,
        script: str,
        output_dir: Path,
        settings: VoiceSettings,
        scenes: Optional[list[dict]],
        version: int,
    ) -> VoiceGenerationResult:
        """Generate audio using ElevenLabs API v2 (client.text_to_speech.convert)."""
        try:
            from elevenlabs.client import ElevenLabs
            from elevenlabs import VoiceSettings as ELVoiceSettings

            client = ElevenLabs(api_key=self.api_key)

            logger.info(
                "[voice] convert() → model=%s voice=%s script_preview=%r",
                settings.model_id, settings.voice_id, script[:100],
            )

            is_v3 = settings.model_id == "eleven_v3"

            # v3 accepts speed inside VoiceSettings but NOT language_code.
            # v2/flash accept language_code but NOT speed inside VoiceSettings.
            if is_v3:
                el_voice_settings = ELVoiceSettings(
                    stability=settings.stability,
                    similarity_boost=settings.similarity_boost,
                    style=settings.style,
                    use_speaker_boost=settings.use_speaker_boost,
                    speed=settings.speed,
                )
            else:
                el_voice_settings = ELVoiceSettings(
                    stability=settings.stability,
                    similarity_boost=settings.similarity_boost,
                    style=settings.style,
                    use_speaker_boost=settings.use_speaker_boost,
                )

            convert_kwargs = dict(
                voice_id=settings.voice_id,
                text=script,
                model_id=settings.model_id,
                voice_settings=el_voice_settings,
                apply_text_normalization="auto",
                output_format="mp3_44100_128",
            )
            if not is_v3:
                convert_kwargs["language_code"] = settings.language_code

            try:
                audio_iter = client.text_to_speech.convert(**convert_kwargs)
            except Exception as api_err:
                logger.error("[voice] convert() raised %s: %s", type(api_err).__name__, api_err, exc_info=True)
                raise

            output_dir.mkdir(parents=True, exist_ok=True)
            audio_filename = f"voiceover_v{version}.mp3"
            audio_path = output_dir / audio_filename

            bytes_written = 0
            with open(audio_path, "wb") as f:
                for chunk in audio_iter:
                    if chunk:
                        f.write(chunk)
                        bytes_written += len(chunk)

            logger.info(
                "[voice] %s written — %d bytes (%.1f KB), version=%d, model=%s, voice=%s",
                audio_filename, bytes_written, bytes_written / 1024,
                version, settings.model_id, settings.voice_id,
            )
            if bytes_written == 0:
                logger.error("[voice] ElevenLabs returned 0 bytes — API may have rejected the request")

            duration_seconds = _get_mp3_duration(audio_path)
            if duration_seconds < 1.0:
                duration_seconds = (len(script.split()) / 150) * 60

            timestamps = self._calculate_scene_timestamps(script, scenes, duration_seconds)

            return VoiceGenerationResult(
                success=True,
                audio_path=audio_path,
                duration_seconds=round(duration_seconds, 2),
                scene_timestamps=timestamps,
                settings_used=settings,
                version=version,
            )

        except Exception as e:
            return VoiceGenerationResult(
                success=False,
                error_message=f"ElevenLabs API error: {str(e)}",
            )

    def _generate_stub(
        self,
        script: str,
        output_dir: Path,
        settings: VoiceSettings,
        scenes: Optional[list[dict]],
        version: int,
    ) -> VoiceGenerationResult:
        """Generate stub audio for testing."""
        word_count = len(script.split())
        duration_seconds = (word_count / 150) * 60

        output_dir.mkdir(parents=True, exist_ok=True)

        audio_filename = f"voiceover_v{version}_stub.json"
        audio_path = output_dir / audio_filename

        timestamps = self._calculate_scene_timestamps(script, scenes, duration_seconds)

        stub_data = {
            "stub": True,
            "script": script,
            "word_count": word_count,
            "estimated_duration": duration_seconds,
            "settings": settings.to_dict(),
            "scene_timestamps": [t.to_dict() for t in timestamps],
            "message": "Stub mode - no actual audio generated. Set ELEVENLABS_API_KEY to generate real audio.",
        }
        audio_path.write_text(json.dumps(stub_data, indent=2))

        return VoiceGenerationResult(
            success=True,
            audio_path=audio_path,
            duration_seconds=duration_seconds,
            scene_timestamps=timestamps,
            settings_used=settings,
            version=version,
        )

    def _calculate_scene_timestamps(
        self,
        script: str,
        scenes: Optional[list[dict]],
        total_duration: float,
    ) -> list[SceneTimestamp]:
        """Calculate approximate timestamps for each scene."""
        if not scenes:
            return [
                SceneTimestamp(
                    scene_number=1,
                    start_time=0,
                    end_time=total_duration,
                    text=script,
                    beat_type="FULL",
                )
            ]

        timestamps = []
        current_time = 0
        total_words = sum(len(s.get("voiceover_segment", "").split()) for s in scenes)

        for scene in scenes:
            segment = scene.get("voiceover_segment", "")
            scene_words = len(segment.split())

            if total_words > 0:
                scene_duration = (scene_words / total_words) * total_duration
            else:
                scene_duration = total_duration / len(scenes)

            timestamps.append(
                SceneTimestamp(
                    scene_number=scene.get("scene_number", len(timestamps) + 1),
                    start_time=current_time,
                    end_time=current_time + scene_duration,
                    text=segment,
                    beat_type=scene.get("beat_type", ""),
                )
            )

            current_time += scene_duration

        return timestamps

    def regenerate_voiceover(
        self,
        script: str,
        output_dir: Path,
        settings: Optional[VoiceSettings] = None,
        scenes: Optional[list[dict]] = None,
        notes: Optional[str] = None,
    ) -> VoiceGenerationResult:
        """Regenerate voiceover, incrementing version number automatically."""
        existing_versions = list(output_dir.glob("voiceover_v*.mp3")) + \
                           list(output_dir.glob("voiceover_v*.json"))
        version = len(existing_versions) + 1

        result = self.generate_voiceover(script, output_dir, settings, scenes, version)

        if result.success and notes:
            notes_path = output_dir / f"voiceover_v{version}_notes.txt"
            notes_path.write_text(notes)

        return result


# Singleton instance
_voice_service: Optional[VoiceService] = None


def get_voice_service(api_key: Optional[str] = None) -> VoiceService:
    """Get or create the voice service singleton."""
    global _voice_service

    if _voice_service is None or api_key is not None:
        _voice_service = VoiceService(api_key=api_key)

    return _voice_service
