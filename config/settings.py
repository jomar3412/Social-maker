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
VIDEO_MAX_DURATION = 75  # seconds (just over 1 min for longer engagement)
VIDEO_TARGET_DURATION = 65  # target duration for script generation (~1:05)
MUSIC_VOLUME = 0.15  # background music volume (0.0 - 1.0)

# === Zack D Films Style Settings ===
# Visual style for content generation
# Options: "zack_d_films" (3D cartoon), "minimal", "cinematic", "documentary"
VISUAL_STYLE = os.getenv("VISUAL_STYLE", "zack_d_films")

# Enable kinetic typography with large animated text
KINETIC_TEXT_ENABLED = os.getenv("KINETIC_TEXT_ENABLED", "True").lower() == "true"

# Enable color grading (saturation boost, contrast, warmth, sharpening)
COLOR_GRADING_ENABLED = os.getenv("COLOR_GRADING_ENABLED", "True").lower() == "true"

# Hook font size (140pt for Zack D Films style)
HOOK_FONT_SIZE = int(os.getenv("HOOK_FONT_SIZE", "140"))

# Body text font size (100pt for Zack D Films style)
BODY_FONT_SIZE = int(os.getenv("BODY_FONT_SIZE", "100"))

# === Content Settings ===
CONTENT_TYPES = ["motivation", "fact", "health", "short_stories"]
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
DEFAULT_HASHTAGS_STORIES = [
    "#storytime", "#shortfilm", "#thriller", "#mystery",
    "#plot_twist", "#storytelling", "#scary", "#drama",
    "#fyp", "#viral"
]

# === Story Settings ===
STORY_TARGET_DURATION = 60  # seconds
STORY_WORD_COUNT = 250  # target word count for stories
STORY_SCENES_TARGET = 10  # target number of scenes

# === Schedule Settings ===
POSTING_TIMES = ["09:00", "18:00"]  # post at 9am and 6pm
TIMEZONE = "America/Los_Angeles"
