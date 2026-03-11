"""
Enhanced Scene Builder

SCENE STRUCTURE RULES:
1. Scene number starts at 1 for each video
2. On-screen text: FULL text, no ellipses, no abbreviations
3. Voiceover text: May remove filler words but keep message
4. Visual direction: Specific, detailed descriptions
5. Text animation direction: Dynamic, matches tone
6. Duration estimate: Based on reading speed + pacing

TEXT RULES:
- Do NOT abbreviate text
- Do NOT use ellipses (...)
- Provide complete on-screen text
- Text must fit within 9:16 frame
- Prioritize clarity and legibility
- Max 4 words per line, max 2 lines (8 words total)

TEXT ANIMATION TYPES:
- slide_in_fast: Fast slide for energetic moments
- fade_in: Fade for calm moments
- scale_pop: Slight scale pop for emphasis
- slide_up: Slide up from bottom
- typewriter: Character by character reveal
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class TextAnimation(Enum):
    """Text animation types with tone matching."""
    SLIDE_IN_FAST = "slide_in_fast"      # Energetic, exciting
    FADE_IN = "fade_in"                   # Calm, thoughtful
    SCALE_POP = "scale_pop"               # Emphasis, surprise
    SLIDE_UP = "slide_up"                 # Standard, neutral
    TYPEWRITER = "typewriter"             # Building tension
    BOUNCE_IN = "bounce_in"               # Playful, fun
    ZOOM_IN = "zoom_in"                   # Dramatic reveal


# Map tones to animations
TONE_ANIMATIONS = {
    "energetic": [TextAnimation.SLIDE_IN_FAST, TextAnimation.BOUNCE_IN],
    "calm": [TextAnimation.FADE_IN, TextAnimation.SLIDE_UP],
    "dramatic": [TextAnimation.SCALE_POP, TextAnimation.ZOOM_IN],
    "playful": [TextAnimation.BOUNCE_IN, TextAnimation.SLIDE_IN_FAST],
    "educational": [TextAnimation.FADE_IN, TextAnimation.SLIDE_UP],
    "mysterious": [TextAnimation.FADE_IN, TextAnimation.TYPEWRITER],
    "urgent": [TextAnimation.SLIDE_IN_FAST, TextAnimation.SCALE_POP],
    "inspiring": [TextAnimation.SCALE_POP, TextAnimation.FADE_IN],
}


@dataclass
class Scene:
    """
    Enhanced scene structure with all required fields.

    REQUIRED FIELDS:
    - scene_number: Starting at 1 for each video
    - on_screen_text: FULL text, no ellipses
    - voiceover_text: Full narration
    - visual_direction: Specific visual description
    - text_animation: Animation type for text
    - duration: Estimated duration in seconds
    """
    scene_number: int
    on_screen_text: str
    voiceover_text: str
    visual_direction: str
    text_animation: TextAnimation
    duration: float

    # Optional fields
    keywords: List[str] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    tone: str = "neutral"
    asset_path: Optional[str] = None
    is_placeholder: bool = False

    def __post_init__(self):
        """Validate scene data after initialization."""
        # Ensure no ellipses in on-screen text
        if "..." in self.on_screen_text or "…" in self.on_screen_text:
            self.on_screen_text = self.on_screen_text.replace("...", "").replace("…", "")

        # Validate text length (max 8 words for readability)
        words = self.on_screen_text.split()
        if len(words) > 8:
            # Truncate to 8 words, keeping complete message
            self.on_screen_text = " ".join(words[:8])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scene_number": self.scene_number,
            "on_screen_text": self.on_screen_text,
            "voiceover_text": self.voiceover_text,
            "visual_direction": self.visual_direction,
            "text_animation": self.text_animation.value,
            "duration": self.duration,
            "keywords": self.keywords,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "tone": self.tone,
            "asset_path": self.asset_path,
            "is_placeholder": self.is_placeholder,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Scene":
        """Create from dictionary."""
        return cls(
            scene_number=data["scene_number"],
            on_screen_text=data["on_screen_text"],
            voiceover_text=data["voiceover_text"],
            visual_direction=data["visual_direction"],
            text_animation=TextAnimation(data.get("text_animation", "fade_in")),
            duration=data["duration"],
            keywords=data.get("keywords", []),
            start_time=data.get("start_time", 0.0),
            end_time=data.get("end_time", 0.0),
            tone=data.get("tone", "neutral"),
            asset_path=data.get("asset_path"),
            is_placeholder=data.get("is_placeholder", False),
        )


def determine_text_animation(scene_text: str, voiceover_text: str,
                              scene_index: int, total_scenes: int) -> TextAnimation:
    """
    Determine the best text animation based on content and position.

    RULES:
    - Fast slide-in for energetic moments
    - Fade-in for calm moments
    - Scale pop for emphasis
    - Motion matches tone of script
    """
    text = (scene_text + " " + voiceover_text).lower()

    # Detect tone from content
    if any(word in text for word in ['shocking', 'incredible', 'unbelievable', 'wow', 'amazing']):
        tone = "dramatic"
    elif any(word in text for word in ['actually', 'fact', 'learn', 'know', 'means']):
        tone = "educational"
    elif any(word in text for word in ['weird', 'strange', 'funny', 'crazy']):
        tone = "playful"
    elif any(word in text for word in ['calm', 'peace', 'quiet', 'gentle']):
        tone = "calm"
    elif any(word in text for word in ['fast', 'quick', 'now', 'immediately', 'urgent']):
        tone = "urgent"
    elif any(word in text for word in ['mystery', 'secret', 'hidden', 'unknown']):
        tone = "mysterious"
    else:
        tone = "neutral"

    # Position-based adjustments
    if scene_index == 0:
        # First scene - make it impactful
        return TextAnimation.SCALE_POP
    elif scene_index == total_scenes - 1:
        # Last scene - dramatic finish
        return TextAnimation.ZOOM_IN
    elif tone in TONE_ANIMATIONS:
        # Use first animation for the detected tone
        return TONE_ANIMATIONS[tone][0]
    else:
        # Default: alternate between slide and fade
        return TextAnimation.SLIDE_UP if scene_index % 2 == 0 else TextAnimation.FADE_IN


def extract_on_screen_text(voiceover_text: str, max_words: int = 8) -> str:
    """
    Extract on-screen text from voiceover.

    RULES:
    - Remove filler words
    - Keep core message
    - Max 8 words (4 per line, 2 lines)
    - No ellipses or abbreviations
    """
    # Remove filler words
    filler_words = {
        'um', 'uh', 'like', 'you know', 'basically', 'actually', 'literally',
        'so', 'well', 'i mean', 'right', 'okay', 'just', 'really', 'very',
    }

    text = voiceover_text.lower()
    for filler in filler_words:
        text = re.sub(r'\b' + filler + r'\b', '', text, flags=re.IGNORECASE)

    # Clean up
    text = re.sub(r'\s+', ' ', text).strip()

    # Extract key words (nouns, verbs, numbers)
    words = text.split()

    # Remove common words if text is too long
    if len(words) > max_words:
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be',
                       'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by'}
        words = [w for w in words if w.lower() not in common_words or len(w) > 4]

    # Take first max_words
    result = " ".join(words[:max_words])

    # Capitalize properly
    result = result.capitalize()

    # Ensure no ellipses
    result = result.replace("...", "").replace("…", "")

    return result


def create_visual_direction(scene_text: str, keywords: List[str],
                             scene_index: int, total_scenes: int) -> str:
    """
    Create detailed visual direction for a scene.

    RULES:
    - Be specific about what visual is expected
    - Include subject, action, context, framing, lighting
    - No vague notes
    """
    text_lower = scene_text.lower()

    # Determine subject
    subjects = {
        'planet': 'planet surface with atmospheric details',
        'space': 'deep space with stars and nebulae',
        'earth': 'Earth from space, showing continents',
        'sun': 'sun with solar flares and corona',
        'moon': 'moon surface with craters',
        'star': 'stellar formation with bright light',
        'ocean': 'ocean waves with light reflections',
        'forest': 'dense forest with sunlight filtering through',
        'city': 'modern city skyline with lights',
        'mountain': 'majestic mountain peak',
        'chess': 'chess board with pieces in strategic position',
        'game': 'board game pieces in action',
        'paper': 'sheet of paper being folded',
        'book': 'open book with pages turning',
        'science': 'laboratory with scientific equipment',
        'technology': 'modern tech devices with glowing screens',
        'brain': 'brain visualization with neural connections',
        'heart': 'anatomical heart or heart symbol',
        'time': 'clock face or hourglass',
        'money': 'currency symbols or coins',
        'number': 'numbers floating in abstract space',
    }

    # Find matching subject
    subject_desc = None
    for keyword, description in subjects.items():
        if keyword in text_lower or keyword in [k.lower() for k in keywords]:
            subject_desc = description
            break

    if not subject_desc:
        # Use keywords to build description
        if keywords:
            subject_desc = f"{keywords[0]} concept visualization"
        else:
            subject_desc = "abstract background with subtle motion"

    # Determine framing based on position
    if scene_index == 0:
        framing = "Wide establishing shot"
    elif scene_index == total_scenes - 1:
        framing = "Close-up for impact"
    elif scene_index % 3 == 0:
        framing = "Medium shot"
    elif scene_index % 3 == 1:
        framing = "Close-up detail"
    else:
        framing = "Tracking shot"

    # Determine lighting/mood
    if any(word in text_lower for word in ['dark', 'night', 'mystery', 'shadow']):
        lighting = "low-key dramatic lighting"
    elif any(word in text_lower for word in ['bright', 'happy', 'sun', 'light']):
        lighting = "bright natural lighting"
    elif any(word in text_lower for word in ['warm', 'sunset', 'golden']):
        lighting = "warm golden hour lighting"
    else:
        lighting = "neutral balanced lighting"

    # Determine motion
    if scene_index == 0:
        motion = "slow zoom in"
    elif scene_index == total_scenes - 1:
        motion = "slow push in for emphasis"
    else:
        motions = ["subtle parallax", "gentle drift", "slow pan", "slight zoom"]
        motion = motions[scene_index % len(motions)]

    return f"{framing} of {subject_desc}, {lighting}, {motion}"


# Zack D Films style 3D visual mappings
ZACK_D_VISUAL_MAPPINGS = {
    # Space & Astronomy - 3D animated versions
    'planet': '3D animated planet with volumetric atmosphere, dynamic surface textures, camera slowly orbiting',
    'earth': '3D Earth globe with animated cloud layers, city lights twinkling, slow rotation',
    'moon': '3D lunar surface with dramatic crater shadows, earthrise in background, dust particles floating',
    'sun': '3D animated sun with plasma eruptions, solar flares, volumetric corona rays',
    'space': '3D deep space environment with animated nebulae, twinkling star fields, cosmic dust',
    'star': '3D stellar formation with animated particle effects, lens flares, volumetric light rays',
    'galaxy': '3D spiral galaxy with animated rotation, glowing core, dust lane particles',
    'asteroid': '3D asteroid tumbling through space, surface detail with craters, debris particles',
    'venus': '3D Venus with thick swirling atmosphere, volcanic surface glowing beneath clouds',
    'mars': '3D Mars surface with red dust storms, Olympus Mons in distance, rover tracks',
    'comet': '3D comet with animated ice tail, particle debris, dramatic lighting',

    # Nature - 3D animated
    'ocean': '3D animated ocean with volumetric waves, underwater caustics, light rays penetrating surface',
    'forest': '3D forest scene with animated foliage swaying, volumetric light shafts, particle dust motes',
    'mountain': '3D mountain landscape with volumetric clouds, snow particles, epic scale',
    'volcano': '3D volcano with animated lava flow, glowing magma, smoke particle simulation',
    'desert': '3D desert dunes with animated sand particles, heat distortion, golden hour light',
    'ice': '3D arctic scene with animated aurora borealis, ice crystal reflections, snow particles',
    'waterfall': '3D waterfall with volumetric mist, rainbow light refraction, rushing water particles',
    'lightning': '3D storm clouds with animated lightning bolts, volumetric rain, dramatic lighting',

    # Science & Technology - 3D animated
    'brain': '3D brain visualization with glowing neural network pulses, synaptic connections firing, translucent layers',
    'dna': '3D DNA double helix with animated base pair connections, particle effects, scientific aesthetic',
    'atom': '3D atomic model with animated electron orbits, glowing nucleus, energy particles',
    'cell': '3D biological cell with animated organelles, membrane dynamics, microscopic detail',
    'circuit': '3D circuit board with animated data flow, glowing traces, electronic pulses traveling',
    'robot': '3D cartoon robot with smooth mechanical movements, friendly design, glowing elements',
    'computer': '3D holographic interface with animated data streams, floating displays, futuristic UI',
    'rocket': '3D rocket launch with animated exhaust plume, particle thrust, dramatic ascent',

    # Objects - 3D animated
    'paper': '3D animated paper with realistic folding motion, soft shadows, light transmission through material',
    'book': '3D book with animated page turns, text reveals, floating particles around pages',
    'clock': '3D ornate clock with animated moving hands, visible gears turning, time particles',
    'money': '3D animated currency with floating coins, paper bills, golden particle effects',
    'chess': '3D chess pieces on elegant board, dramatic lighting, strategic positioning',
    'game': '3D animated game board with moving pieces, colorful elements, playful energy',
    'magnifying': '3D magnifying glass with light refraction, zooming effect, discovery moment',
    'key': '3D golden key with animated unlock motion, glowing keyhole, particle burst',

    # Abstract concepts - 3D animated
    'time': '3D abstract time visualization with flowing clock elements, hourglass sand particles, temporal distortion',
    'number': '3D animated numbers floating in space, mathematical symbols orbiting, glowing equations',
    'data': '3D data visualization with animated bars and graphs, particle data points, holographic display',
    'energy': '3D animated energy waves, plasma effects, particle field dynamics',
    'light': '3D animated light rays with volumetric scattering, prism rainbow effects, god rays',
    'idea': '3D lightbulb with animated filament glow, idea particles bursting outward, eureka moment',
    'growth': '3D animated plant growing from seed, time-lapse style, particle nutrients',
    'connection': '3D network nodes with animated connection lines, data pulses traveling, web structure',

    # Human concepts (faceless) - 3D animated
    'mind': '3D abstract mind visualization, neural pathways lighting up, thought bubbles emerging',
    'heart': '3D anatomical heart with animated blood flow, pulsing rhythm, life energy particles',
    'hand': '3D faceless hand reaching, interaction with objects, clean minimal style',
    'silhouette': '3D faceless humanoid silhouette, abstract form, dynamic pose',

    # Insects & Small Creatures - 3D animated
    'butterfly': '3D animated monarch butterfly with iridescent shimmering wings, delicate flapping motion, landing on colorful flower, extreme macro detail, bokeh background',
    'butterflies': '3D animated group of colorful butterflies with iridescent wings, graceful flight pattern, garden scene with flowers, magical particle dust',
    'caterpillar': '3D animated fuzzy caterpillar crawling on green leaf, transformation cocoon nearby, nature macro shot, soft lighting',
    'insect': '3D animated insect with detailed exoskeleton, compound eyes glistening, natural movement on plant, macro photography style',
    'bee': '3D animated honeybee with fuzzy golden body, transparent wing blur, collecting pollen from flower, golden pollen particles floating',
    'ant': '3D animated ant carrying leaf piece, detailed mandibles, colony tunnel in background, underground cross-section view',
    'spider': '3D animated spider weaving intricate web, morning dew drops on silk threads, backlit dramatic lighting',
    'dragonfly': '3D animated dragonfly with iridescent wings hovering over pond, water reflection, reed plants, golden hour lighting',
    'moth': '3D animated luna moth with pale green wings, night scene with moonlight, attracted to soft glowing light',
    'ladybug': '3D animated red ladybug with black spots, crawling on green leaf edge, dewdrop nearby, cheerful macro shot',
    'wing': '3D extreme close-up of butterfly wing scales, iridescent color patterns, microscopic detail, scientific visualization',
    'metamorphosis': '3D animated cocoon transformation sequence, butterfly emerging, wings unfolding, time-lapse style, magical particles',
    'taste': '3D animated butterfly landing on flower, proboscis unfurling, feet sensors detecting nectar, educational cutaway view',
    'feet': '3D animated butterfly feet close-up showing taste receptors, landing on fruit surface, sensory visualization',
}


def create_zack_d_visual_direction(
    scene_text: str,
    keywords: List[str],
    scene_index: int,
    total_scenes: int,
    tone: str = "neutral",
) -> str:
    """
    Create Zack D Films-style visual direction optimized for AI video generation.

    Transforms generic directions into 3D animated prompts with:
    - Volumetric effects
    - Particle animations
    - Dynamic camera movements
    - Cinematic lighting

    Args:
        scene_text: The voiceover/narration text for this scene
        keywords: Extracted keywords from the scene
        scene_index: Current scene number (0-indexed)
        total_scenes: Total scenes in video
        tone: Content tone (dramatic, calm, energetic, etc.)

    Returns:
        Enhanced visual direction for AI video generation
    """
    text_lower = scene_text.lower()

    # Find matching 3D visual from mappings
    visual_desc = None
    matched_topic = None

    # Check keywords first (higher priority)
    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in ZACK_D_VISUAL_MAPPINGS:
            visual_desc = ZACK_D_VISUAL_MAPPINGS[keyword_lower]
            matched_topic = keyword_lower
            break

    # Then check scene text
    if not visual_desc:
        for topic, description in ZACK_D_VISUAL_MAPPINGS.items():
            if topic in text_lower:
                visual_desc = description
                matched_topic = topic
                break

    # Fallback to abstract visualization
    if not visual_desc:
        if keywords:
            visual_desc = f"3D animated {keywords[0]} concept with floating elements, volumetric lighting, particle effects"
            matched_topic = keywords[0]
        else:
            visual_desc = "3D abstract geometric shapes with smooth motion, volumetric lighting, particle trails"
            matched_topic = "abstract"

    # Add camera movement based on scene position
    camera_movements = {
        0: "camera pushing in smoothly",  # Opening
        -1: "camera slowly pulling back",  # Closing (use total_scenes - 1)
    }

    mid_scene_cameras = [
        "camera orbiting left",
        "camera drifting right with parallax",
        "slow zoom revealing details",
        "subtle Dutch angle with movement",
        "crane shot moving upward",
    ]

    if scene_index == 0:
        camera = camera_movements[0]
    elif scene_index == total_scenes - 1:
        camera = camera_movements[-1]
    else:
        camera = mid_scene_cameras[scene_index % len(mid_scene_cameras)]

    # Add tone-based lighting
    tone_lighting = {
        "dramatic": "dramatic rim lighting with deep shadows",
        "calm": "soft ambient lighting with gentle gradients",
        "energetic": "vibrant neon glow with high saturation",
        "mysterious": "moody low-key lighting with fog",
        "educational": "clean three-point studio lighting",
        "playful": "bright colorful lighting with soft shadows",
        "inspiring": "volumetric god rays with warm tones",
    }

    lighting = tone_lighting.get(tone, "cinematic balanced lighting")

    # Build final direction
    direction = f"{visual_desc}, {camera}, {lighting}"

    return direction


def get_tone_from_text(text: str) -> str:
    """
    Detect content tone from text for visual style matching.

    Args:
        text: Scene text or voiceover

    Returns:
        Detected tone string
    """
    text_lower = text.lower()

    tone_keywords = {
        "dramatic": ['shocking', 'incredible', 'unbelievable', 'amazing', 'mind-blowing', 'insane'],
        "educational": ['actually', 'fact', 'learn', 'know', 'means', 'because', 'how', 'why'],
        "playful": ['weird', 'strange', 'funny', 'crazy', 'hilarious', 'wild'],
        "calm": ['calm', 'peace', 'quiet', 'gentle', 'soft', 'slow'],
        "energetic": ['fast', 'quick', 'now', 'immediately', 'explosive', 'powerful'],
        "mysterious": ['mystery', 'secret', 'hidden', 'unknown', 'ancient', 'lost'],
        "inspiring": ['imagine', 'dream', 'possible', 'future', 'hope', 'believe'],
    }

    for tone, keywords in tone_keywords.items():
        if any(kw in text_lower for kw in keywords):
            return tone

    return "neutral"


def build_scenes_from_word_timing(
    word_timing: List[Dict],
    total_duration: float,
    voiceover_text: str = "",
    target_scenes: int = 10,
) -> List[Scene]:
    """
    Build enhanced scenes from word timing data.

    SCENE NUMBER RULE: Always starts at 1 for each video.

    Args:
        word_timing: List of {"word": "hello", "start": 0.0, "end": 0.5}
        total_duration: Total video duration
        voiceover_text: Full voiceover text for context
        target_scenes: Target number of scenes

    Returns:
        List of Scene objects with all required fields
    """
    if not word_timing:
        # Create minimal scenes if no timing data
        scene_duration = total_duration / target_scenes
        return [
            Scene(
                scene_number=i + 1,  # Start at 1
                on_screen_text="",
                voiceover_text="",
                visual_direction=create_visual_direction("", [], i, target_scenes),
                text_animation=TextAnimation.FADE_IN,
                duration=scene_duration,
                start_time=i * scene_duration,
                end_time=(i + 1) * scene_duration,
            )
            for i in range(target_scenes)
        ]

    # Find natural break points (sentence/clause ends)
    break_points = []
    for i, word_info in enumerate(word_timing):
        word = word_info["word"].rstrip()
        if word.endswith(('.', '!', '?', ',', ';', ':')):
            break_points.append({
                "idx": i,
                "time": word_info["end"],
                "strength": 3 if word.endswith(('.', '!', '?')) else 2,
            })

    # Build scenes targeting 2-4 second duration
    scenes = []
    current_start_idx = 0
    current_start_time = 0
    scene_number = 1  # Always start at 1

    MIN_SCENE_DURATION = 2.0
    MAX_SCENE_DURATION = 5.0

    for bp in break_points:
        scene_duration = bp["time"] - current_start_time

        should_split = (
            (bp["strength"] >= 3 and scene_duration >= MIN_SCENE_DURATION) or
            scene_duration >= MAX_SCENE_DURATION
        )

        if should_split:
            # Collect words for this scene
            scene_words = word_timing[current_start_idx:bp["idx"] + 1]
            scene_voiceover = " ".join(w["word"] for w in scene_words)

            # Extract keywords
            keywords = extract_keywords(scene_words)

            # Determine on-screen text
            on_screen = extract_on_screen_text(scene_voiceover)

            # Determine animation
            animation = determine_text_animation(
                on_screen, scene_voiceover, len(scenes), target_scenes
            )

            # Create visual direction
            visual = create_visual_direction(
                scene_voiceover, keywords, len(scenes), target_scenes
            )

            scenes.append(Scene(
                scene_number=scene_number,
                on_screen_text=on_screen,
                voiceover_text=scene_voiceover,
                visual_direction=visual,
                text_animation=animation,
                duration=scene_duration,
                keywords=keywords,
                start_time=current_start_time,
                end_time=bp["time"],
            ))

            scene_number += 1
            current_start_idx = bp["idx"] + 1
            current_start_time = bp["time"]

    # Handle remaining words
    if current_start_idx < len(word_timing):
        scene_words = word_timing[current_start_idx:]
        scene_voiceover = " ".join(w["word"] for w in scene_words)
        scene_duration = total_duration - current_start_time

        keywords = extract_keywords(scene_words)
        on_screen = extract_on_screen_text(scene_voiceover)
        animation = determine_text_animation(on_screen, scene_voiceover, len(scenes), target_scenes)
        visual = create_visual_direction(scene_voiceover, keywords, len(scenes), target_scenes)

        scenes.append(Scene(
            scene_number=scene_number,
            on_screen_text=on_screen,
            voiceover_text=scene_voiceover,
            visual_direction=visual,
            text_animation=animation,
            duration=scene_duration,
            keywords=keywords,
            start_time=current_start_time,
            end_time=total_duration,
        ))

    return scenes


def extract_keywords(scene_words: List[Dict]) -> List[str]:
    """Extract keywords from scene words."""
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'to', 'of', 'in', 'for', 'on',
        'with', 'at', 'by', 'from', 'up', 'about', 'into', 'through',
        'and', 'but', 'or', 'so', 'yet', 'this', 'that', 'these', 'those',
        'it', 'its', 'you', 'your', 'we', 'our', 'they', 'their', 'them',
    }

    keywords = []
    for word_info in scene_words:
        word = word_info.get("word", "")
        clean = re.sub(r'[^\w]', '', word.lower())

        if len(clean) >= 3 and clean not in stop_words:
            keywords.append(clean)

    return keywords[:5]  # Return top 5


def format_scene_report(scenes: List[Scene]) -> str:
    """Format scenes as a readable report."""
    lines = [
        "# Scene Breakdown",
        "",
        f"Total Scenes: {len(scenes)}",
        f"Total Duration: {sum(s.duration for s in scenes):.1f}s",
        "",
    ]

    for scene in scenes:
        lines.extend([
            f"## Scene {scene.scene_number}",
            f"**Duration:** {scene.duration:.1f}s ({scene.start_time:.1f}s - {scene.end_time:.1f}s)",
            f"**On-Screen Text:** {scene.on_screen_text}",
            f"**Voiceover:** {scene.voiceover_text[:100]}{'...' if len(scene.voiceover_text) > 100 else ''}",
            f"**Visual Direction:** {scene.visual_direction}",
            f"**Text Animation:** {scene.text_animation.value}",
            f"**Keywords:** {', '.join(scene.keywords)}",
            "",
        ])

    return "\n".join(lines)


# =============================================================================
# CONTEXT-AWARE VEO PROMPT GENERATION
# =============================================================================
# Generates prompts based on MEANING, not individual nouns.
# Core rules:
# 1. Scene Analysis: Extract PRIMARY SUBJECT, ACTION, CONTEXT
# 2. Subject Consistency: Primary subject appears in EVERY scene
# 3. Style Lock: Same style prefix in EVERY scene prompt
# 4. Scene Continuity: Same subject looks the same across scenes
# =============================================================================


def _call_claude_simple(prompt: str, max_tokens: int = 50) -> str:
    """
    Simple Claude API call for extracting short text responses.

    Uses anthropic client directly for minimal overhead.
    """
    try:
        import anthropic
        import os

        # Try to import from config, fall back to env var
        try:
            from config.settings import ANTHROPIC_API_KEY
        except ImportError:
            ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

        if not ANTHROPIC_API_KEY:
            return ""

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"  Warning: Claude API call failed: {e}")
        return ""


def _extract_primary_subject(full_script: str) -> str:
    """
    Use Claude to identify the PRIMARY subject of the entire video.

    Returns specific subject like "monarch butterfly" not just "butterfly".
    """
    prompt = f"""Identify the PRIMARY SUBJECT of this educational script.

Script:
{full_script}

Return ONLY the specific subject (e.g., "monarch butterfly", "honey bee", "great white shark", "human brain").
- Be specific, not generic (not just "animal" or "nature")
- Use the exact species/type mentioned if available
- Return 1-3 words maximum
"""
    response = _call_claude_simple(prompt, max_tokens=20)

    # Fallback: extract primary noun from first sentence if API fails
    if not response:
        # Clean and split first sentence
        first_sentence = full_script.split('.')[0].lower()
        words = first_sentence.split()

        # Skip common words to find the main subject noun
        skip_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'to', 'of', 'in', 'for', 'on',
            'with', 'at', 'by', 'from', 'their', 'they', 'them', 'this', 'that',
            'it', 'its', 'you', 'your', 'we', 'our', 'taste', 'feet',
        }

        # Find first significant noun (usually the subject)
        for i, word in enumerate(words[:10]):
            clean_word = word.strip('.,!?\'\"')
            if clean_word not in skip_words and len(clean_word) > 2:
                # Check for compound noun (word + next word)
                if i + 1 < len(words):
                    next_word = words[i + 1].strip('.,!?\'\"')
                    if next_word not in skip_words and len(next_word) > 2:
                        # Common compound patterns
                        if clean_word in ['monarch', 'honey', 'great', 'blue', 'red', 'golden']:
                            return f"{clean_word} {next_word}"
                return clean_word

        return "subject"

    return response.lower().strip('"\'.,!?')


def _create_style_lock(subject: str, tone: str) -> str:
    """
    Create the locked visual style used in ALL scene prompts.

    This ensures visual consistency across the entire video.
    """
    tone_lighting = {
        "educational": "soft natural lighting, realistic but slightly stylized",
        "dramatic": "dramatic rim lighting, high contrast, cinematic",
        "playful": "bright cheerful lighting, vibrant saturated colors",
        "calm": "soft diffused lighting, gentle color palette",
        "energetic": "dynamic lighting with high saturation",
        "mysterious": "moody low-key lighting with atmospheric haze",
        "inspiring": "volumetric god rays with warm golden tones",
        "neutral": "balanced three-point lighting, clean aesthetic",
    }

    lighting = tone_lighting.get(tone, tone_lighting["educational"])

    return f"3D animated {subject}, macro nature documentary style, {lighting}, vertical 9:16 format"


def _extract_action(scene_text: str) -> str:
    """
    Extract the ACTION from scene voiceover.
    """
    prompt = f"""What ACTION is happening in this sentence?

"{scene_text}"

Return only the action verb phrase (e.g., "tasting with feet", "laying eggs", "landing on flower", "swimming through water").
If no clear action, return "in natural pose".
Maximum 4 words.
"""
    response = _call_claude_simple(prompt, max_tokens=20)

    # Fallback: extract action verb from text
    if not response:
        text_lower = scene_text.lower()

        # Map verbs to their -ing forms and contextual phrases
        action_patterns = {
            'taste': 'tasting',
            'eat': 'eating',
            'fly': 'flying',
            'land': 'landing',
            'swim': 'swimming',
            'run': 'running',
            'walk': 'walking',
            'jump': 'jumping',
            'crawl': 'crawling',
            'move': 'moving',
            'detect': 'detecting',
            'sense': 'sensing',
            'have': 'showing',  # "have sensors" -> "showing sensors"
            'tell': 'detecting',  # "can tell if it's food" -> "detecting"
        }

        # Look for action verbs in text
        for verb, action in action_patterns.items():
            if verb in text_lower:
                # Try to find context words after the verb
                idx = text_lower.find(verb)
                context_words = text_lower[idx:].split()[:4]
                if len(context_words) > 1:
                    # Include relevant context (e.g., "taste with feet")
                    relevant_words = [w.strip('.,!?') for w in context_words[1:3]
                                     if w.strip('.,!?') not in ['the', 'a', 'an', 'is', 'are']]
                    if relevant_words:
                        return f"{action} {' '.join(relevant_words)}"
                return action

        return "in natural pose"

    return response.lower().strip('"\'.,!?')


def _extract_context(scene_text: str) -> str:
    """
    Extract the CONTEXT/SETTING from scene voiceover.
    """
    prompt = f"""What is the CONTEXT or SETTING in this sentence?

"{scene_text}"

Return only the context (e.g., "on a colorful flower petal", "near a leaf", "in a garden", "underwater").
If no clear context, return "in natural environment".
Maximum 6 words.
"""
    response = _call_claude_simple(prompt, max_tokens=30)

    # Fallback: extract location/setting from text
    if not response:
        text_lower = scene_text.lower()

        # Look for preposition phrases that indicate location
        prepositions = ['on', 'in', 'at', 'near', 'under', 'over', 'by', 'around', 'through']

        for prep in prepositions:
            # Find preposition followed by noun
            pattern = f" {prep} "
            if pattern in text_lower:
                idx = text_lower.find(pattern)
                # Get words after preposition, stop at pronouns/verbs
                after_prep = text_lower[idx + len(pattern):].split()
                stop_words = {'they', 'it', 'can', 'will', 'is', 'are', 'the', 'a', 'an', 'and', 'but', 'or'}
                context_words = []
                for w in after_prep[:4]:
                    clean_w = w.strip('.,!?')
                    if clean_w in stop_words:
                        break
                    context_words.append(clean_w)
                if context_words:
                    context_phrase = ' '.join(context_words)
                    if len(context_phrase) > 2:
                        return f"{prep} {context_phrase}"

        # Check for specific context keywords
        context_keywords = {
            'flower': 'on a colorful flower',
            'leaf': 'on a green leaf',
            'water': 'near water',
            'tree': 'on a tree branch',
            'ground': 'on the ground',
            'air': 'in the air',
            'feet': 'close-up on feet',
            'sensor': 'showing sensor detail',
        }

        for keyword, context in context_keywords.items():
            if keyword in text_lower:
                return context

        return "in natural environment"

    return response.lower().strip('"\'.,!?')


def _build_scene_prompt(
    style_lock: str,
    primary_subject: str,
    action: str,
    context: str,
    scene_index: int,
    total_scenes: int,
) -> str:
    """
    Build final VEO prompt for one scene.

    Combines style lock + subject + action + context + camera movement.
    """
    # Camera varies by scene position for visual variety
    if scene_index == 0:
        camera = "wide establishing shot slowly pushing in"
    elif scene_index == total_scenes - 1:
        camera = "close-up shot slowly pulling back"
    else:
        cameras = [
            "medium shot with subtle movement",
            "close-up detail shot",
            "macro shot revealing texture",
            "tracking shot following subject",
            "orbital shot around subject",
        ]
        camera = cameras[scene_index % len(cameras)]

    return f"{style_lock}, {primary_subject} {action} {context}, {camera}"


def generate_narrative_prompts(
    full_script: str,
    scenes: List["Scene"],
    tone: str = "educational",
) -> List[str]:
    """
    Generate VEO prompts for all scenes based on narrative meaning.

    This is the CORE function for context-aware prompt generation.

    Steps:
    1. Analyze full script to identify PRIMARY SUBJECT
    2. Define STYLE LOCK for entire video
    3. For each scene: extract ACTION + CONTEXT
    4. Build cohesive prompt with consistent subject + style

    Args:
        full_script: The complete voiceover/script text
        scenes: List of Scene objects with voiceover_text
        tone: Content tone (educational, dramatic, playful, etc.)

    Returns:
        List of VEO prompts, one per scene, all with consistent style

    Example:
        Input: "Butterflies taste with their feet. Their feet have sensors..."
        Output: [
            "3D animated monarch butterfly, macro documentary style..., tasting with feet on flower, wide establishing shot",
            "3D animated monarch butterfly, macro documentary style..., showing foot sensors in detail, close-up detail shot",
        ]
    """
    print("  Generating narrative VEO prompts...")

    # Step 1: Identify primary subject from full script
    primary_subject = _extract_primary_subject(full_script)
    print(f"    Primary subject: {primary_subject}")

    # Step 2: Define style lock (used in ALL scenes)
    style_lock = _create_style_lock(primary_subject, tone)
    print(f"    Style lock: {style_lock[:60]}...")

    prompts = []
    total_scenes = len(scenes)

    for i, scene in enumerate(scenes):
        # Step 3: Extract action and context from this scene
        scene_text = scene.voiceover_text if hasattr(scene, 'voiceover_text') else str(scene)

        action = _extract_action(scene_text)
        context = _extract_context(scene_text)

        # Step 4: Build scene prompt
        prompt = _build_scene_prompt(
            style_lock=style_lock,
            primary_subject=primary_subject,
            action=action,
            context=context,
            scene_index=i,
            total_scenes=total_scenes,
        )

        prompts.append(prompt)
        print(f"    Scene {i + 1}: {action} {context}")

    return prompts


def generate_narrative_prompts_from_dicts(
    full_script: str,
    scenes: List[Dict],
    tone: str = "educational",
) -> List[str]:
    """
    Generate VEO prompts from scene dictionaries (for pipeline compatibility).

    Same as generate_narrative_prompts but accepts dict format scenes.
    """
    print("  Generating narrative VEO prompts...")

    # Step 1: Identify primary subject
    primary_subject = _extract_primary_subject(full_script)
    print(f"    Primary subject: {primary_subject}")

    # Step 2: Define style lock
    style_lock = _create_style_lock(primary_subject, tone)
    print(f"    Style lock: {style_lock[:60]}...")

    prompts = []
    total_scenes = len(scenes)

    for i, scene in enumerate(scenes):
        # Get voiceover text from dict
        scene_text = scene.get("voiceover_text", scene.get("on_screen_text", ""))

        # Extract action and context
        action = _extract_action(scene_text)
        context = _extract_context(scene_text)

        # Build prompt
        prompt = _build_scene_prompt(
            style_lock=style_lock,
            primary_subject=primary_subject,
            action=action,
            context=context,
            scene_index=i,
            total_scenes=total_scenes,
        )

        prompts.append(prompt)
        print(f"    Scene {i + 1}: {action} {context}")

    return prompts


if __name__ == "__main__":
    import sys

    # Test narrative prompt generation
    if len(sys.argv) > 1 and sys.argv[1] == "--narrative":
        print("=" * 60)
        print("TESTING CONTEXT-AWARE VEO PROMPT GENERATION")
        print("=" * 60)

        # Test script about butterflies
        test_script = """Butterflies taste with their feet.
Their feet have special sensors called chemoreceptors.
When they land on a flower, they can instantly tell if it's food."""

        # Create mock scenes
        test_scenes = [
            Scene(
                scene_number=1,
                on_screen_text="Butterflies taste with feet",
                voiceover_text="Butterflies taste with their feet.",
                visual_direction="",
                text_animation=TextAnimation.SCALE_POP,
                duration=2.5,
            ),
            Scene(
                scene_number=2,
                on_screen_text="Chemoreceptors in feet",
                voiceover_text="Their feet have special sensors called chemoreceptors.",
                visual_direction="",
                text_animation=TextAnimation.FADE_IN,
                duration=3.0,
            ),
            Scene(
                scene_number=3,
                on_screen_text="Instant food detection",
                voiceover_text="When they land on a flower, they can instantly tell if it's food.",
                visual_direction="",
                text_animation=TextAnimation.ZOOM_IN,
                duration=3.5,
            ),
        ]

        print(f"\nScript: {test_script}\n")
        print("-" * 60)

        # Generate narrative prompts
        prompts = generate_narrative_prompts(test_script, test_scenes, tone="educational")

        print("\n" + "=" * 60)
        print("GENERATED VEO PROMPTS:")
        print("=" * 60)
        for i, prompt in enumerate(prompts):
            print(f"\nScene {i + 1}:")
            print(f"  {prompt}")

        print("\n" + "=" * 60)
        print("VERIFICATION CHECKLIST:")
        print("=" * 60)
        print("[ ] Same subject in every prompt?")
        print("[ ] Same style prefix in every prompt?")
        print("[ ] Different actions matching voiceover?")
        print("[ ] NO random abstract imagery?")
        print("[ ] NO keyword-based mismatches?")

    else:
        # Original test: scene building from word timing
        print("Testing scene building from word timing...")
        print("(Use --narrative to test VEO prompt generation)")
        print()

        test_timing = [
            {"word": "On", "start": 0.0, "end": 0.2},
            {"word": "Venus,", "start": 0.2, "end": 0.5},
            {"word": "a", "start": 0.5, "end": 0.6},
            {"word": "day", "start": 0.6, "end": 0.9},
            {"word": "is", "start": 0.9, "end": 1.0},
            {"word": "longer", "start": 1.0, "end": 1.4},
            {"word": "than", "start": 1.4, "end": 1.6},
            {"word": "a", "start": 1.6, "end": 1.7},
            {"word": "year.", "start": 1.7, "end": 2.2},
            {"word": "That", "start": 2.5, "end": 2.7},
            {"word": "means", "start": 2.7, "end": 3.0},
            {"word": "time", "start": 3.0, "end": 3.3},
            {"word": "works", "start": 3.3, "end": 3.6},
            {"word": "differently.", "start": 3.6, "end": 4.2},
        ]

        scenes = build_scenes_from_word_timing(test_timing, 5.0)
        print(format_scene_report(scenes))
