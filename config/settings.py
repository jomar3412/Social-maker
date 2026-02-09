import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# === API Keys ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# YouTube
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")

# Instagram
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

# TikTok
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")

# === Paths ===
# Support Google Drive mount or other external storage
# Set ASSETS_DIR in .env to use mounted cloud storage (e.g., /mnt/gdrive/socal_maker/assets)
# Set OUTPUT_DIR in .env to save outputs to cloud storage (e.g., /mnt/gdrive/socal_maker/output)

_assets_env = os.getenv("ASSETS_DIR", "")
_output_env = os.getenv("OUTPUT_DIR", "")

ASSETS_DIR = Path(_assets_env) if _assets_env else PROJECT_ROOT / "assets"
OUTPUT_DIR = Path(_output_env) if _output_env else PROJECT_ROOT / "output"

FONTS_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
HISTORY_FILE = PROJECT_ROOT / "content_history.json"

# === Video Settings ===
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_MAX_DURATION = 59  # seconds (under 60 for Shorts)
MUSIC_VOLUME = 0.15  # background music volume (0.0 - 1.0)

# === Content Settings ===
CONTENT_TYPES = ["motivation", "fact", "health"]
DEFAULT_HASHTAGS_MOTIVATION = [
    "#motivation", "#stoic", "#wisdom", "#mindset", "#quotes",
    "#motivationalquotes", "#stoicism", "#dailymotivation",
    "#inspiration", "#selfimprovement"
]
DEFAULT_HASHTAGS_FACTS = [
    "#didyouknow", "#facts", "#funfacts", "#interesting",
    "#knowledge", "#learn", "#education", "#mindblown",
    "#amazingfacts", "#dailyfacts"
]
DEFAULT_HASHTAGS_HEALTH = [
    "#health", "#nutrition", "#wellness", "#healthtips",
    "#healthylifestyle", "#nutritionfacts", "#healthyfood",
    "#vitamins", "#healthyliving", "#wellnesstips"
]

# === Schedule Settings ===
POSTING_TIMES = ["09:00", "18:00"]  # post at 9am and 6pm
TIMEZONE = "America/Los_Angeles"
