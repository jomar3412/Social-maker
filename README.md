# SoCal Maker - Automated Content Factory

Automated faceless content generation for social media (YouTube Shorts, TikTok, Instagram Reels).

## Features

- **Multi-Model AI Pipeline**: Uses Gemini, Grok, ChatGPT, and Claude for viral content generation
- **Niche Training System**: Analyze competitors and build custom style guides
- **Auto-Tagging**: Google Cloud Vision/Video Intelligence for automatic asset tagging
- **Multi-Platform Posting**: YouTube, TikTok, and Instagram support
- **Automated Scheduling**: Systemd service for hands-off content creation

## Quick Start

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/socal_maker.git
cd socal_maker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp config/.env.example .env
# Edit .env with your API keys

# Generate content
python cli.py generate fact --dry-run
```

## CLI Commands

```bash
# Training
python cli.py train add-competitor @factspage tiktok
python cli.py train analyze "Did you know..."
python cli.py train patterns
python cli.py train style-guide

# Generation
python cli.py generate fact --dry-run
python cli.py generate fact --platforms youtube,tiktok

# Scheduling
python cli.py schedule status
python cli.py schedule once fact --platforms youtube
```

## Project Structure

```
socal_maker/
├── cli.py                    # Unified CLI interface
├── pipeline.py               # Main generation pipeline
├── scheduler.py              # Automated scheduling
├── generators/
│   ├── multi_model_pipeline.py   # AI orchestration
│   ├── script_gen.py             # Script generation
│   ├── voice_gen.py              # ElevenLabs TTS
│   ├── image_gen.py              # Pillow image generation
│   └── video_gen.py              # FFmpeg video assembly
├── posters/
│   ├── youtube.py            # YouTube Data API
│   ├── tiktok.py             # TikTok Content API
│   └── instagram.py          # Instagram Graph API
├── training/
│   ├── style_guide.json      # Brand voice config
│   ├── competitor_analyzer.py # Pattern extraction
│   └── niche_config.py       # Style injection
└── tools/
    └── auto_tagger.py        # Google Cloud Vision tagging
```

## Required API Keys

Add to `.env`:

```bash
ANTHROPIC_API_KEY=           # Claude (final assembly)
OPENAI_API_KEY=              # ChatGPT (drafting)
GOOGLE_API_KEY=              # Gemini (research)
XAI_API_KEY=                 # Grok (hooks)
ELEVENLABS_API_KEY=          # Voice generation
GOOGLE_APPLICATION_CREDENTIALS=  # Vision/Video Intelligence
```

## Documentation

- [SHORT_FORM_GUIDE.md](SHORT_FORM_GUIDE.md) - Viral content principles
- [GOOGLE_CLOUD_VISION_RESEARCH.md](GOOGLE_CLOUD_VISION_RESEARCH.md) - Auto-tagging setup
- [training/style_guide.md](training/style_guide.md) - Fun Facts style guide

## License

MIT
