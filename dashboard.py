#!/usr/bin/env python3
"""
Social Maker Dashboard
Mobile-friendly web interface for content pipeline with voice input.

Run with: streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
"""
import streamlit as st
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

# Page config - must be first
st.set_page_config(
    page_title="Social Maker",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for mobile-friendly dark theme
st.markdown("""
<style>
    /* Dark theme */
    .stApp {
        background-color: #0e1117;
    }

    /* Mobile-friendly buttons */
    .stButton > button {
        width: 100%;
        padding: 0.75rem 1rem;
        font-size: 1.1rem;
        border-radius: 10px;
        margin: 0.25rem 0;
    }

    /* Content cards */
    .content-card {
        background: #1e2130;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        border: 1px solid #2d3348;
    }

    /* Section headers */
    .section-header {
        color: #4ecdc4;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.5rem;
    }

    /* Result sections */
    .result-section {
        background: #161b22;
        border-left: 3px solid #4ecdc4;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }

    /* Scene cards */
    .scene-card {
        background: #21262d;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    /* Library item cards */
    .library-card {
        background: linear-gradient(135deg, #1a1f2e 0%, #252b3d 100%);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.75rem 0;
        border: 1px solid #3d4663;
    }

    .library-card:hover {
        border-color: #4ecdc4;
    }

    .library-card .type-badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: bold;
        text-transform: uppercase;
    }

    .library-card .type-fact { background: #2d5a27; color: #7ee787; }
    .library-card .type-motivation { background: #5a2d27; color: #ff7b72; }
    .library-card .type-story { background: #2d2757; color: #a371f7; }

    .library-card .hook-text {
        font-size: 1.1rem;
        color: #f0f6fc;
        margin: 0.5rem 0;
        font-weight: 500;
    }

    .library-card .meta-info {
        color: #8b949e;
        font-size: 0.85rem;
    }

    .library-card .file-list {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-top: 0.5rem;
    }

    .library-card .file-badge {
        background: #30363d;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        color: #8b949e;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Stats cards */
    .stat-card {
        background: #21262d;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }

    .stat-card .number {
        font-size: 2rem;
        font-weight: bold;
        color: #4ecdc4;
    }

    .stat-card .label {
        color: #8b949e;
        font-size: 0.85rem;
    }

    /* Mobile responsive */
    @media (max-width: 768px) {
        .stButton > button {
            font-size: 1rem;
            padding: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)


def get_output_dir():
    """Get the output directory from settings."""
    try:
        from config.settings import OUTPUT_DIR
        return OUTPUT_DIR
    except:
        return Path(__file__).parent / "output"


def scan_library():
    """Scan output directory and return organized content list."""
    output_dir = get_output_dir()
    items = []

    if not output_dir.exists():
        return items

    # Scan directories
    for folder in sorted(output_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if folder.is_dir() and not folder.name.startswith('.'):
            item = parse_output_folder(folder)
            if item:
                items.append(item)

    # Scan standalone JSON files (like last_quick_create.json)
    for json_file in output_dir.glob("*.json"):
        if json_file.name.startswith("last_"):
            item = parse_standalone_json(json_file)
            if item:
                items.append(item)

    return items


def parse_output_folder(folder: Path) -> dict:
    """Parse an output folder into a library item."""
    content_file = folder / "content.json"

    # Determine type from folder name
    folder_name = folder.name.lower()
    if "fact" in folder_name:
        content_type = "fact"
    elif "motivation" in folder_name:
        content_type = "motivation"
    elif "stor" in folder_name:
        content_type = "story"
    else:
        content_type = "unknown"

    # Get content data
    content = {}
    if content_file.exists():
        try:
            with open(content_file) as f:
                content = json.load(f)
        except:
            pass

    # If no content.json, folder might be empty
    if not content and not any(folder.glob("*.mp4")):
        return None

    # Find files
    files = {
        "video": list(folder.glob("*.mp4")),
        "audio": list(folder.glob("*.mp3")),
        "image": list(folder.glob("*.png")) + list(folder.glob("*.jpg")),
        "subtitles": list(folder.glob("*.ass")),
        "scenes": list(folder.glob("scene*.json")) + list(folder.glob("scene*.md")),
    }

    # Get hook/main text
    hook = content.get("hook", "")
    main_text = content.get("fact") or content.get("quote") or content.get("voiceover", "")

    # Get creation date from folder
    try:
        mtime = datetime.fromtimestamp(folder.stat().st_mtime)
        date_str = mtime.strftime("%b %d, %Y %I:%M %p")
    except:
        date_str = "Unknown date"

    return {
        "id": folder.name,
        "type": content_type,
        "path": str(folder),
        "hook": hook[:100] if hook else (main_text[:100] if main_text else folder.name),
        "full_text": main_text,
        "caption": content.get("caption", ""),
        "hashtags": content.get("hashtags", []),
        "date": date_str,
        "files": files,
        "content": content,
        "has_video": bool(files["video"]),
        "has_audio": bool(files["audio"]),
    }


def parse_standalone_json(json_path: Path) -> dict:
    """Parse a standalone JSON file (like last_quick_create.json)."""
    try:
        with open(json_path) as f:
            content = json.load(f)
    except:
        return None

    # Determine type from content
    metadata = content.get("metadata", {})
    niche = metadata.get("niche", "")

    if "motivation" in niche.lower():
        content_type = "motivation"
    elif "fact" in niche.lower():
        content_type = "fact"
    else:
        content_type = "motivation"  # default for quick create

    hook = content.get("hook", "")
    full_script = content.get("full_script", "")

    try:
        mtime = datetime.fromtimestamp(json_path.stat().st_mtime)
        date_str = mtime.strftime("%b %d, %Y %I:%M %p")
    except:
        date_str = "Unknown date"

    return {
        "id": json_path.stem,
        "type": content_type,
        "path": str(json_path),
        "hook": hook[:100] if hook else "Quick Create",
        "full_text": full_script,
        "caption": content.get("caption", ""),
        "hashtags": content.get("hashtags", []),
        "visual_direction": content.get("visual_direction", ""),
        "voice_direction": content.get("voice_direction", ""),
        "date": date_str,
        "files": {},
        "content": content,
        "has_video": False,
        "has_audio": False,
        "is_script_only": True,
    }


def render_header():
    """Render the app header."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🎬 Social Maker")
        st.caption("Content Pipeline Dashboard")
    with col2:
        st.markdown(f"**{datetime.now().strftime('%I:%M %p')}**")


def render_content_type_selector():
    """Render content type selection."""
    st.markdown("### What do you want to create?")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🧠 Fun Fact", use_container_width=True, key="btn_fact"):
            st.session_state.content_type = "fact"
            st.session_state.page = "configure"
            st.rerun()

    with col2:
        if st.button("💪 Motivation", use_container_width=True, key="btn_motivation"):
            st.session_state.content_type = "motivation"
            st.session_state.page = "configure"
            st.rerun()

    with col3:
        if st.button("📖 Story", use_container_width=True, key="btn_story"):
            st.session_state.content_type = "short_stories"
            st.session_state.page = "configure"
            st.rerun()


def render_configure_page():
    """Render configuration options based on content type."""
    content_type = st.session_state.get("content_type", "fact")

    st.markdown(f"### Configure: {content_type.replace('_', ' ').title()}")

    # Back button
    if st.button("← Back", key="back_btn"):
        st.session_state.page = "home"
        st.rerun()

    st.divider()

    # Content type specific options
    if content_type == "fact":
        st.markdown("**Category** (optional)")
        category = st.selectbox(
            "Category",
            ["Random", "Science", "History", "Nature", "Space", "Human Body", "Technology"],
            label_visibility="collapsed"
        )
        st.session_state.category = category

    elif content_type == "motivation":
        st.markdown("**Tone**")
        tone = st.selectbox(
            "Tone",
            ["Generic Affirmation", "Aggressive / Gym", "Calm Reflective", "Spiritual", "Business Focused"],
            label_visibility="collapsed"
        )
        st.session_state.tone = tone.lower().replace(" / ", "_").replace(" ", "_")

        st.markdown("**Voice Style**")
        voice = st.selectbox(
            "Voice",
            ["Deep Motivational", "Neutral AI", "Energetic", "Text Only"],
            label_visibility="collapsed"
        )
        st.session_state.voice_style = voice.lower().replace(" ", "_")

    elif content_type == "short_stories":
        st.markdown("**Genre**")
        genre = st.selectbox(
            "Genre",
            ["Thriller", "Mystery", "Horror", "Drama", "Romance", "Comedy"],
            label_visibility="collapsed"
        )
        st.session_state.genre = genre.lower()

        st.markdown("**Topic** (optional)")
        topic = st.text_input("Topic", placeholder="e.g., a haunted lighthouse...", label_visibility="collapsed")
        st.session_state.topic = topic if topic else None

    # Additional instructions
    st.divider()
    st.markdown("**Additional Instructions** (optional)")

    # Note about speech
    st.info("💡 **Tip:** Speech input requires HTTPS. For now, type your instructions below.")

    instructions = st.text_area(
        "Additional instructions",
        placeholder="Type any specific requests...",
        height=100,
        label_visibility="collapsed"
    )
    st.session_state.instructions = instructions

    st.divider()

    # Generate buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🎬 Generate (Preview)", use_container_width=True, type="secondary"):
            st.session_state.dry_run = True
            st.session_state.page = "generating"
            st.rerun()

    with col2:
        if st.button("🚀 Generate & Post", use_container_width=True, type="primary"):
            st.session_state.dry_run = False
            st.session_state.page = "generating"
            st.rerun()


def run_pipeline_with_progress():
    """Run the pipeline and show progress."""
    from pipeline import run_pipeline

    content_type = st.session_state.get("content_type", "fact")
    dry_run = st.session_state.get("dry_run", True)

    # Build parameters
    kwargs = {
        "content_type": content_type,
        "dry_run": dry_run,
        "platforms": [] if dry_run else ["youtube"],
    }

    # Add story-specific params
    if content_type == "short_stories":
        kwargs["genre"] = st.session_state.get("genre", "thriller")
        kwargs["topic"] = st.session_state.get("topic")
        kwargs["orchestration_mode"] = "quick"

    # Run pipeline
    result = run_pipeline(**kwargs)
    return result


def render_generating_page():
    """Show generation progress."""
    st.markdown("### Generating Content...")

    content_type = st.session_state.get("content_type", "fact")

    progress_bar = st.progress(0, text="Starting pipeline...")
    status_text = st.empty()

    import time

    steps = [
        (10, "Generating script..."),
        (25, "Creating voiceover..."),
        (40, "Building scenes..."),
        (60, "Generating subtitles..."),
        (75, "Assembling video..."),
        (90, "Finalizing..."),
    ]

    result = None

    try:
        for progress, text in steps[:2]:
            progress_bar.progress(progress, text=text)
            time.sleep(0.5)

        status_text.markdown("*Running pipeline - this may take a minute...*")
        result = run_pipeline_with_progress()

        progress_bar.progress(100, text="Complete!")

        if result:
            st.session_state.result = result
            st.session_state.page = "result"
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Pipeline failed. Check logs for details.")
            if st.button("← Try Again"):
                st.session_state.page = "configure"
                st.rerun()

    except Exception as e:
        st.error(f"Error: {str(e)}")
        if st.button("← Back"):
            st.session_state.page = "configure"
            st.rerun()


def render_result_page():
    """Display generation results."""
    result = st.session_state.get("result", {})

    if not result:
        st.warning("No results to display")
        if st.button("← Home"):
            st.session_state.page = "home"
            st.rerun()
        return

    st.markdown("### ✅ Content Generated!")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
    with col2:
        if st.button("🔄 Generate Another", use_container_width=True):
            st.session_state.page = "configure"
            st.rerun()

    st.divider()

    content = result.get("content", {})

    # Hook
    hook = content.get("hook", "")
    if hook:
        st.markdown("#### 🎣 Hook")
        st.markdown(f"""
        <div class="result-section">
            <strong style="font-size: 1.2rem; color: #ff6b6b;">"{hook}"</strong>
        </div>
        """, unsafe_allow_html=True)

    # Script
    main_text = content.get("fact") or content.get("quote") or content.get("voiceover", "")
    if main_text:
        st.markdown("#### 📝 Script")
        st.markdown(f"""
        <div class="result-section">
            {main_text}
        </div>
        """, unsafe_allow_html=True)

    # Caption
    caption = content.get("caption", "")
    if caption:
        st.markdown("#### 💬 Caption")
        st.code(caption, language=None)

    # Hashtags
    hashtags = content.get("hashtags", [])
    if hashtags:
        st.markdown("#### #️⃣ Hashtags")
        st.code(" ".join(hashtags), language=None)

    # Scenes
    scenes = result.get("scenes", [])
    if scenes:
        st.markdown("#### 🎬 Scenes")
        with st.expander(f"View {len(scenes)} scenes", expanded=False):
            for i, scene in enumerate(scenes):
                st.markdown(f"""
                <div class="scene-card">
                    <strong>Scene {i+1}</strong> ({scene.get('start', 0):.1f}s - {scene.get('end', 0):.1f}s)<br>
                    <small style="color: #8b949e;">{scene.get('on_screen_text', '')[:100]}</small><br>
                    <em style="color: #4ecdc4;">{scene.get('visual_direction', '')[:150]}</em>
                </div>
                """, unsafe_allow_html=True)

    # Output info
    st.divider()
    st.markdown("#### 📁 Files")
    st.markdown(f"""
    - **Video ID:** `{result.get('video_id', 'N/A')}`
    - **Output:** `{result.get('output_dir', 'N/A')}`
    """)


def render_library_page():
    """Show content library with organized view."""
    st.markdown("### 📚 Content Library")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("← Home"):
            st.session_state.page = "home"
            st.rerun()

    st.divider()

    # Scan library
    items = scan_library()

    if not items:
        st.info("No content generated yet. Create your first piece!")
        return

    # Stats row
    total = len(items)
    facts = len([i for i in items if i["type"] == "fact"])
    motivations = len([i for i in items if i["type"] == "motivation"])
    stories = len([i for i in items if i["type"] == "story"])
    with_video = len([i for i in items if i.get("has_video")])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="number">{total}</div>
            <div class="label">Total</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="number">{facts}</div>
            <div class="label">Facts</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="number">{motivations}</div>
            <div class="label">Motivation</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="stat-card">
            <div class="number">{with_video}</div>
            <div class="label">Videos</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Filter
    filter_type = st.selectbox(
        "Filter by type",
        ["All", "Facts", "Motivation", "Stories", "With Video"],
        label_visibility="collapsed"
    )

    # Apply filter
    if filter_type == "Facts":
        items = [i for i in items if i["type"] == "fact"]
    elif filter_type == "Motivation":
        items = [i for i in items if i["type"] == "motivation"]
    elif filter_type == "Stories":
        items = [i for i in items if i["type"] == "story"]
    elif filter_type == "With Video":
        items = [i for i in items if i.get("has_video")]

    # Display items
    for item in items:
        type_class = f"type-{item['type']}"
        type_label = item["type"].upper()

        # File badges
        file_badges = []
        if item.get("has_video"):
            file_badges.append("🎬 Video")
        if item.get("has_audio"):
            file_badges.append("🔊 Audio")
        if item.get("is_script_only"):
            file_badges.append("📝 Script Only")

        files_html = " ".join([f'<span class="file-badge">{b}</span>' for b in file_badges])

        st.markdown(f"""
        <div class="library-card">
            <span class="type-badge {type_class}">{type_label}</span>
            <div class="hook-text">"{item['hook'][:80]}{'...' if len(item['hook']) > 80 else ''}"</div>
            <div class="meta-info">{item['date']}</div>
            <div class="file-list">{files_html}</div>
        </div>
        """, unsafe_allow_html=True)

        # Expandable details
        with st.expander(f"View details: {item['id']}", expanded=False):
            # Full content
            if item.get("full_text"):
                st.markdown("**Full Script:**")
                st.markdown(f"> {item['full_text']}")

            if item.get("caption"):
                st.markdown("**Caption:**")
                st.code(item["caption"], language=None)

            if item.get("hashtags"):
                st.markdown("**Hashtags:**")
                st.code(" ".join(item["hashtags"]), language=None)

            if item.get("visual_direction"):
                st.markdown("**Visual Direction:**")
                st.markdown(f"*{item['visual_direction']}*")

            if item.get("voice_direction"):
                st.markdown("**Voice Direction:**")
                st.markdown(f"*{item['voice_direction']}*")

            # File paths
            st.markdown("**Location:**")
            st.code(item["path"], language=None)

            # Video player if available
            files = item.get("files", {})
            if files.get("video"):
                video_path = files["video"][0]
                try:
                    st.video(str(video_path))
                except:
                    st.markdown(f"Video: `{video_path}`")


def render_settings_page():
    """Render settings page."""
    st.markdown("### ⚙️ Settings")

    if st.button("← Home"):
        st.session_state.page = "home"
        st.rerun()

    st.divider()

    # Output directory
    output_dir = get_output_dir()
    st.markdown("**Output Directory:**")
    st.code(str(output_dir), language=None)

    # API Status
    st.markdown("**API Status:**")

    env_vars = ["ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY"]
    for var in env_vars:
        value = os.environ.get(var, "")
        status = "✅ Set" if value else "❌ Not set"
        st.markdown(f"- `{var}`: {status}")

    st.divider()

    # HTTPS for speech
    st.markdown("**Speech Input:**")
    st.warning("""
    Speech-to-text requires HTTPS. To enable:

    1. Set up a domain pointing to this server
    2. Install Caddy: `sudo apt install caddy`
    3. Create `/etc/caddy/Caddyfile`:
    ```
    yourdomain.com {
        reverse_proxy localhost:8501
    }
    ```
    4. Run: `sudo systemctl restart caddy`
    """)


def main():
    """Main app entry point."""
    if "page" not in st.session_state:
        st.session_state.page = "home"

    render_header()
    st.divider()

    page = st.session_state.page

    if page == "home":
        render_content_type_selector()
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📚 Library", use_container_width=True):
                st.session_state.page = "library"
                st.rerun()
        with col2:
            if st.button("⚙️ Settings", use_container_width=True):
                st.session_state.page = "settings"
                st.rerun()

    elif page == "configure":
        render_configure_page()

    elif page == "generating":
        render_generating_page()

    elif page == "result":
        render_result_page()

    elif page == "library":
        render_library_page()

    elif page == "settings":
        render_settings_page()


if __name__ == "__main__":
    main()
