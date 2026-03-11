# Google VEO 3 Prompting Guide
## Comprehensive Research-Based Reference for Social Media Content Creation

Last updated: 2026-02-12

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [VEO 3 vs VEO 2 Key Differences](#veo-3-vs-veo-2-key-differences)
3. [Official Prompt Structure](#official-prompt-structure)
4. [Camera Movements and Angles](#camera-movements-and-angles)
5. [Visual Styles and Aesthetics](#visual-styles-and-aesthetics)
6. [Character Consistency Techniques](#character-consistency-techniques)
7. [Duration and Pacing Control](#duration-and-pacing-control)
8. [Vertical Video (9:16) for Social Media](#vertical-video-916-for-social-media)
9. [Audio Prompting (VEO 3 Native)](#audio-prompting-veo-3-native)
10. [What Works vs What Doesn't](#what-works-vs-what-doesnt)
11. [Ready-to-Use Prompt Templates](#ready-to-use-prompt-templates)
12. [Advanced Techniques](#advanced-techniques)
13. [API Access and Python Integration](#api-access-and-python-integration)

---

## Executive Summary

Google VEO 3 (released 2025) represents a significant leap over VEO 2. Key improvements:

- **Treats prompt details as explicit instructions** rather than approximate suggestions
- **Native audio generation** — dialogue, SFX, music, ambient sound from the same prompt
- **Better cinematic language adherence** — professional terms like "dolly zoom" and "rack focus" are executed accurately
- **Fewer generation attempts needed** to reach desired output
- **Available via**: Google AI Studio (paid preview July 2025), Vertex AI, Gemini API
- **Pricing**: $0.75 per second of video+audio output
- **Clip limit**: 4–8 seconds per generation (stitch clips in post for longer videos)

The single most important principle: **think like a director, not a poet.** Specific actionable instructions outperform flowery description.

---

## VEO 3 vs VEO 2 Key Differences

| Feature | VEO 2 | VEO 3 |
|---|---|---|
| Prompt interpretation | Approximate | Literal / explicit |
| Audio output | Silent | Native audio (dialogue, SFX, music) |
| Cinematic language | Generic results | Accurate execution |
| Iteration needed | Many attempts | Fewer attempts |
| Action sequences | Limited fidelity | Authentic motion |
| Character consistency | Poor | Better (with techniques) |

---

## Official Prompt Structure

Based on Google's official "Ultimate prompting guide for Veo 3.1" (Google Cloud Blog, October 2025), the recommended formula follows a **director's mindset**:

### Formula (in order)

```
[CINEMATOGRAPHY] + [SUBJECT] + [ACTION] + [ENVIRONMENT] + [STYLE/MOOD] + [AUDIO]
```

### Component Breakdown

| Component | What to include |
|---|---|
| **Cinematography** | Shot type, camera angle, camera movement |
| **Subject** | Age, clothing, expression, distinguishing features |
| **Action** | What the subject does and how they move |
| **Environment** | Location, background, time of day, weather |
| **Style / Mood** | Aesthetic, lighting, color palette, film era |
| **Audio** | Dialogue, SFX, music genre, ambience |

### Official Example Prompts

**Corporate Worker Scene (from official docs):**
```
Medium shot, a tired corporate worker, rubbing his temples in exhaustion,
in front of a bulky 1980s computer in a cluttered office late at night.
The scene is lit by harsh fluorescent overhead lights and the green glow
of the monochrome monitor. Retro aesthetic, shot as if on 1980s color film.
```

**Melancholic Bus Scene (from official docs):**
```
Close-up with very shallow depth of field, a young woman's face, looking
out a bus window at the passing city lights with her reflection faintly
visible on the glass, inside a bus at night during a rainstorm, melancholic
mood with cool blue tones, moody, cinematic.
```

**Cinematic City Street (from official docs):**
```
Handheld push-in down a busy city street at dusk, neon reflections on wet
asphalt. Shallow depth of field bokeh. People silhouettes crossing frame.
Subtle camera shake, warm tungsten shop lights. Ambience: traffic, soft
chatter. Filmic color with gentle halation.
```

**Forest Macro with Rack Focus (from official docs):**
```
Extreme macro of dew on moss in a morning forest. Start with foreground in
crisp focus, then a slow rack focus to a tiny mushroom in the midground.
Soft god rays through trees, delicate particles floating. Ambience: birds
and gentle leaves rustling. Naturalistic, understated.
```

---

## Camera Movements and Angles

VEO 3 understands professional cinematic terminology. Use these exact terms.

### Camera Movements

| Term | Effect | Example Prompt Fragment |
|---|---|---|
| **Dolly-in** | Camera smoothly moves toward subject | `A slow dolly-in on a character's face as they receive surprising news` |
| **Dolly-out** | Camera pulls back from subject | `A slow dolly-out revealing the full scale of the ancient ruins` |
| **Pan** | Horizontal rotation from fixed point | `A slow pan across a mountain range at sunset` |
| **Tilt** | Vertical rotation from fixed point | `A tilt up from the base of a skyscraper to the top` |
| **Tracking shot** | Camera moves alongside subject | `A tracking shot following a runner through a dense forest` |
| **Aerial shot** | High altitude looking down | `An aerial shot of a car driving along a winding coastal road` |
| **Crane shot** | Vertical camera rise revealing scene | `A crane shot starting at street level and rising to reveal a bustling city square` |
| **Orbit / 360** | Circular path around subject | `A 360-degree orbit shot around a levitating crystal` |
| **Handheld** | Subtle natural camera shake | `Handheld push-in down a busy city street` |
| **Steadicam** | Smooth moving shot | `A steadicam shot following the subject through crowded hallways` |
| **Rack focus** | Shifts focus between subjects | `A rack focus from a glass on a table to a person walking in the background` |
| **Dolly zoom** | Hitchcock effect, background zooms | `A dramatic dolly zoom on the protagonist's shocked expression` |

### Camera Angles and Shot Types

| Term | Description | Example Fragment |
|---|---|---|
| **Extreme close-up (ECU)** | Single detail — eye, lips, fingertip | `An extreme close-up of a blinking eye with a reflection of a computer screen` |
| **Close-up (CU)** | Face or specific object | `A close-up of a chef meticulously garnishing a dish` |
| **Medium shot (MS)** | Subject from waist up | `Medium shot, a tired corporate worker rubbing his temples` |
| **Wide shot (WS)** | Full subject and environment | `A wide shot of a deserted beach with a lone figure walking` |
| **Establishing shot** | Sets location context | `An establishing shot of Tokyo at night` |
| **Point of view (POV)** | What character sees | `A POV shot of a person riding a rollercoaster` |
| **Low angle** | Camera looks up — subject appears powerful | `A low-angle shot of a superhero standing on a rooftop` |
| **High angle** | Camera looks down — subject appears small | `A high-angle shot of a person lost in a maze` |
| **Eye-level** | Natural conversational angle | `An eye-level shot of two people having a conversation at a cafe` |
| **Dutch angle** | Tilted frame — tension/unease | `A dutch angle shot of the villain entering the room` |

### Depth of Field and Lens Effects

| Term | Effect |
|---|---|
| `shallow depth of field` | Subject sharp, background blurred (bokeh) |
| `deep depth of field` | Everything sharp foreground to background |
| `fisheye lens` | Wide distorted spherical view |
| `anamorphic widescreen` | Wide cinematic look with lens flares |
| `macro` or `extreme macro` | Extreme close-up detail |
| `telephoto compression` | Flattens distance between objects |

---

## Visual Styles and Aesthetics

### Film Styles

| Style Keyword | Look | Example Fragment |
|---|---|---|
| `cinematic` | High-quality film look | `cinematic, shot on 35mm film, anamorphic widescreen` |
| `documentary` | Realistic, observational | `documentary-style, handheld camera` |
| `film noir` | B&W, high contrast, shadows | `film noir, deep shadows and stark highlights, smoke curling` |
| `found footage` | Amateur shaky cam | `found footage, shaky camera` |
| `nature documentary` | BBC Earth / National Geographic | `National Geographic style, BBC Earth quality` |
| `hyperrealistic` | Ultra-detailed, lifelike | `hyperrealistic, 4K, photorealistic` |

### Color Grading

| Term | Effect |
|---|---|
| `warm tones` | Yellows, oranges — cozy, nostalgic |
| `cool tones` | Blues, greens — calm, melancholic |
| `desaturated / muted` | Washed out, subdued palette |
| `highly saturated` | Vibrant, intense colors |
| `Technicolor` | 1950s vibrant early color film look |
| `golden hour` | Soft warm sunset/sunrise light |
| `cinematic color grade` | Professional film color treatment |
| `moody color grade` | Dark, atmospheric treatment |
| `halation` | Soft glow bleeding around bright areas |

### Lighting Descriptors

| Term | Effect |
|---|---|
| `golden hour lighting` | Warm, soft, directional sun |
| `volumetric lighting` | Visible light rays / god rays |
| `Rembrandt lighting` | Triangle highlight on cheek (portrait) |
| `neon lighting` | Cyberpunk, colorful nighttime |
| `chiaroscuro` | Extreme contrast dark/light (Baroque) |
| `soft diffused light` | Even, shadow-free flattering light |
| `dramatic side lighting` | Strong shadows, moody |
| `practical lighting` | Room lamps, candles as light sources |

### Artistic and Aesthetic Styles

| Style | Example Fragment |
|---|---|
| Anime | `Japanese anime style, speed lines, dramatic angles` |
| Studio Ghibli | `Studio Ghibli aesthetic, hand-drawn feel, lush backgrounds` |
| Watercolor | `watercolor painting style, soft blended strokes` |
| Claymation | `claymation stop-motion style, tactile texture` |
| Cyberpunk | `cyberpunk aesthetic, neon lights, rain-slicked streets` |
| Steampunk | `steampunk aesthetic, brass gears, Victorian machinery` |
| 1980s retro-futurism | `1980s retro-futurism, neon grids, chrome spaceships` |
| Art Deco | `Art Deco style, geometric patterns, gold and black` |
| Vaporwave | `vaporwave aesthetic, pastel palette, 80s neon, surreal` |

### Mood Keywords

`epic`, `serene`, `melancholic`, `mysterious`, `hopeful`, `tense`, `dreamlike`,
`contemplative`, `energetic`, `majestic`, `cozy`, `unsettling`, `awe-inspiring`

---

## Character Consistency Techniques

Maintaining a consistent character across multiple VEO clips is the biggest challenge. Use this layered approach.

### Technique 1: The Character Slug

Create a reusable block of specific descriptors and paste it verbatim into every scene.

**Bad (too vague):**
```
a man walking in a forest
```

**Good (character slug):**
```
Marcus, a botanist in his mid-30s with messy dark brown hair, wire-rimmed
glasses, a worn olive green field jacket, and a canvas messenger bag,
walking in a sun-dappled forest.
```

Always include:
- Name
- Age range
- Hair color and style
- Distinguishing feature (glasses, scar, tattoo, beard)
- Specific clothing colors and type
- Any accessories

### Technique 2: Reference Image Chaining (Most Effective)

This is the community-proven most effective workflow for character consistency:

1. Generate a clear portrait image of your character using Imagen or another image model
2. Use that image as a reference input for your first VEO clip
3. Export the last clear frame from that clip
4. Use that frame (not the original portrait) as the reference for your next clip
5. Continue chaining end-frames as references throughout your sequence

Why end-frame chaining works: each new reference captures the exact lighting and angle from the previous clip, creating visual continuity.

### Technique 3: Community Keywords

These keywords reported by users to reinforce character consistency:

```
(consistent character), character lock
```

**Combined example:**
```
[Reference: frame_from_scene1.png]
Marcus, a botanist in his mid-30s with messy dark brown hair, wire-rimmed
glasses, and worn olive green field jacket, holds up a glowing specimen.
(consistent character), character lock.
Negative: different hair color, different clothing, different person, morphing.
```

### Technique 4: Negative Prompting for Character Drift

Describe what you DON'T want explicitly (do not use "no" or "don't"):

```
Negative: changing hair color, different clothing, morphing face,
inconsistent features, different person
```

---

## Duration and Pacing Control

### Video Length

- VEO 3 generates clips of **4–8 seconds** per generation
- For longer content, generate multiple clips and stitch in post (FFmpeg)
- You can request a duration explicitly:
  - `"a 6-second video of..."`
  - `"duration: 8s"`
  - Describing more actions naturally extends length

### Pacing Keywords

**Fast / Energetic:**
```
fast-paced, quick cuts, montage, action sequence, dynamic camera movement,
hyperlapse, time-lapse, energetic, rapid
```

**Slow / Deliberate:**
```
slow motion, leisurely pace, serene, long take, slow panning shot,
tranquil, unhurried, meditative
```

### Multi-Scene Sequences

Structure prompts like a shot list for multi-scene videos:

```
A 45-second cinematic nature documentary.
Scene 1: Wide shot of a majestic eagle soaring over mountain range at sunrise.
Scene 2: Close-up of the eagle's intense eyes.
Scene 3: The eagle dives, wings tucked, toward a river below.
Scene 4: Slow motion — it snatches a fish from the water.
Style throughout: dramatic orchestral music, sweeping aerial cinematography.
```

### Scene Transitions

Request specific transitions explicitly:

| Transition | Prompt Fragment |
|---|---|
| Cut | `cut to` (default if not specified) |
| Dissolve | `dissolves to` |
| Fade | `fade to black, then` |
| Match cut | `match cut to` |
| Wipe | `wipe transition to` |

### First and Last Frame Control

Anchor your clip with precise start/end descriptions:

```
The video begins with a close-up on a vintage pocket watch, its hands
ticking at golden hour. [main action] ...the video ends with a wide shot
of the protagonist walking away into sunset, casting long shadows.
```

---

## Vertical Video (9:16) for Social Media

### Aspect Ratio Specification

Always include one of these phrases:

- `vertical 9:16 aspect ratio`
- `vertical format, 9:16`
- `portrait mode, vertical`
- `optimized for TikTok/Instagram Reels/YouTube Shorts`

### Composition Principles for Vertical

**What works in vertical 9:16:**

1. **Tall subjects** — skyscrapers, waterfalls, trees, standing people
2. **Centered subjects** — places subject in strongest position
3. **Vertical movement** — tilt up, crane rise, falling water, rising objects
4. **Close-ups** — fill the tall frame with facial detail
5. **Rule of thirds vertically** — place subject on left or right vertical third
6. **Leading lines** — paths, corridors, roads leading toward camera

**Composition keywords to add:**
```
subject centered in frame, portrait orientation, fill the frame,
vertical leading lines, top-to-bottom reveal
```

### Vertical Video Prompt Examples

**Nature B-roll (education / background):**
```
Cinematic drone shot flying slowly through a misty morning in a redwood
forest. Sunbeams cut through the fog and tall trees. Serene, majestic,
peaceful mood. Vertical 9:16 aspect ratio, photorealistic, 4K.
```

**Motivational hook shot:**
```
Aerial drone footage of a lone hiker reaching the summit of a snow-capped
mountain at sunrise. The clouds are below the peak. Epic, hopeful, majestic
mood. Stunning slow motion as they take the final step. Vertical 9:16
aspect ratio, hyperrealistic, 4K.
```

**Educational fact visual (text overlay friendly):**
```
An extreme close-up, slow-motion video of a bee collecting pollen from a
sunflower. The background is a soft-focus green field. The bee is framed
using the rule of thirds, leaving negative space on the left for text
overlay. Bright natural sunlight. Vertical 9:16 aspect ratio,
National Geographic style, high detail.
```

**Abstract loop background:**
```
A mesmerizing, seamlessly looping abstract video of soft glowing white and
gold particles drifting slowly upwards on a dark navy blue background.
Gentle, calm, and elegant mood. Minimal detail for text readability.
Vertical 9:16 aspect ratio.
```

**Urban mood (ambient music):**
```
View from inside a car driving through a city at night. The streetlights
and neon signs blur into beautiful bokeh. Windshield wipers clearing light
rain. Dreamlike and contemplative mood. Vertical 9:16 aspect ratio,
cinematic color grade.
```

---

## Audio Prompting (VEO 3 Native)

VEO 3 generates synchronized audio from text description. This is absent in VEO 2.

### Dialogue

Enclose spoken words in quotation marks with speaker context:

```
A woman, speaking directly to the camera, says: "The universe is 13.8
billion years old. And yet here we are."
```

### Sound Effects

Use `SFX:` label for clarity:

```
SFX: A loud thunder clap in the distance, followed by heavy rain.
SFX: The screech of tires on wet pavement.
SFX: A single drop of water echoing in a vast cave.
```

### Music

Describe genre, tempo, mood:

```
Music: A low pulsing synth track with a sense of mystery and suspense.
Audio: A cheerful, optimistic orchestral score with prominent woodwinds.
Music: Epic cinematic strings building to a crescendo.
```

### Ambient Sound

```
Ambience: The quiet hum of a busy city far below.
Ambience: Dawn chorus of birds in a tropical rainforest.
Ambient: Crackling fire, distant wind through pine trees.
```

### Combined Audio Example

```
Close-up of a scientist examining a glowing sample in a dark lab.
SFX: The soft hum of laboratory equipment.
Music: Tense, minimal electronic score.
Ambience: Air conditioning, distant beeping instruments.
```

---

## What Works vs What Doesn't

### What Works Well

- Short high-quality clips (4–8 seconds)
- Specific detailed prompts using cinematic director language
- Artistic and surreal visuals
- Nature scenes, abstract visuals, sci-fi environments
- Strong single-subject compositions
- Slow motion effects
- Macro and extreme close-up shots
- Audio generation for ambient scenes

### What Fails or Produces Poor Results

| Problem Area | Details |
|---|---|
| **Complex multi-action scenes** | Too many distinct actions in one prompt produces chaos |
| **Vague generic prompts** | "A beautiful forest" = generic unusable output |
| **Contradictory instructions** | "dark noir scene with bright sunny colors" = confused output |
| **Specific real people** | Celebrity likenesses blocked by content filters |
| **IP characters** | Movie characters, brand logos blocked |
| **Cross-prompt memory** | Model has NO memory between separate generations |
| **Long continuous sequences** | Cannot generate coherent 60s videos in one shot |
| **Complex hand/finger detail** | Common AI failure point |
| **Realistic crowd scenes** | Individual faces in crowds inconsistent |

### Community-Reported Limitations (Reddit/YouTube 2025)

- **Low daily generation limits** on paid plans: 3–20 videos per day depending on tier
- **High cost per video** makes iteration expensive at $0.75/second
- **Low success rate** for complex prompts — many outputs have garbled speech or poor lip-sync
- **Uncanny valley** effect on photorealistic human subjects
- **Aggressive content filters** — legitimate prompts sometimes blocked with vague error messages
- **No cross-prompt continuity** — each generation is completely independent

### The "Poet vs Director" Problem

The most common mistake from new users. Compare:

**Poet (ineffective):**
```
A beautiful, ethereal journey through the mystical realm of an ancient
forgotten land where the whispers of time echo through golden leaves...
```

**Director (effective):**
```
Slow dolly forward through a misty ancient forest. Golden autumn leaves
fall. Shafts of morning light cut through the canopy. Wide angle,
shallow depth of field. Cinematic, 4K. Ambience: wind, falling leaves.
```

---

## Ready-to-Use Prompt Templates

### For Motivational / Stoic Quote Videos

**Perseverance / Achievement:**
```
Aerial drone footage of a lone hiker reaching the summit of a snow-capped
mountain at sunrise. The clouds are below the peak. Epic, hopeful, majestic.
Stunning slow motion as they take the final step. Vertical 9:16, hyperrealistic, 4K.
```

**Strength / Resilience:**
```
Extreme close-up of a blacksmith's hammer striking glowing hot metal on an
anvil, sending sparks flying. Dramatic high-contrast lighting in a dark
workshop. Powerful slow motion on impact. Vertical 9:16, photorealistic, 4K.
```

**New Beginnings:**
```
Timelapse of a vibrant sunrise over a calm ocean horizon. The sky transitions
from deep purple to bright orange. Serene and hopeful. Vertical 9:16,
photorealistic, 4K. Music: soft swelling orchestral strings.
```

**Solitude / Focus:**
```
Low angle shot of a solitary figure sitting in meditation on a mountain
cliff edge at golden hour. Soft wind moves their clothing. Deep blue sky,
lens flare from the sun. Cinematic, contemplative. Vertical 9:16, 4K.
```

### For Educational "Did You Know?" Videos

**Template for any fact subject:**
```
[Documentary shot type] of [subject]. Clean composition with soft
out-of-focus background. Bright even lighting. [Subject position, e.g.,
lower third] leaving negative space at top for text overlay. Vertical 9:16
aspect ratio, [National Geographic / BBC Earth] style, high detail, 4K.
```

**Biology fact:**
```
An extreme close-up, slow-motion video of a bee collecting pollen from a
sunflower. Soft-focus green field background. Rule of thirds composition.
Bright natural sunlight. Negative space on left for text. Vertical 9:16,
National Geographic style, high detail.
```

**History/archaeology fact:**
```
A hyper-detailed macro shot of an ancient Roman coin spinning slowly on a
dark reflective surface. The coin is positioned on the lower left. Clean
minimalist composition, dark blurred background. Bright studio lighting.
Negative space at top right for text. Vertical 9:16, 4K.
```

**Space/science fact:**
```
3D-style cinematic visualization of the Milky Way galaxy slowly rotating,
with our solar system highlighted by a subtle glowing dot. Deep space
background with nebulae. Epic and awe-inspiring. Vertical 9:16,
photorealistic, 4K. Music: ethereal ambient pad.
```

**Animal behavior fact:**
```
Documentary close-up of an octopus changing color and texture on a coral
reef. The transformation is in slow motion with dramatic underwater
lighting. Rays of sunlight filter from above. Vertical 9:16,
BBC Blue Planet style, high detail.
```

### For Abstract / Ambient Backgrounds

**Gold particles (luxury/motivation):**
```
Mesmerizing seamlessly looping abstract video of soft glowing gold and
white light particles drifting slowly upward on a deep navy background.
Calm, elegant, minimal. Vertical 9:16 aspect ratio. No text elements.
```

**Dark cosmic (mystery/deep topics):**
```
Seamlessly looping slow drift through a deep space nebula, subtle purple
and blue gas clouds with distant star points. Meditative and vast.
Vertical 9:16. Music: deep ambient drone.
```

**Liquid gradient (modern/clean):**
```
Slow-moving fluid dynamics of pastel colors — soft pink, lavender, light
blue — mixing in gentle swirling motion. Abstract, calming, seamless loop.
Vertical 9:16 aspect ratio.
```

**Fire (energy/passion):**
```
Close-up slow-motion shot of a crackling fire in a stone fireplace. Flames
dance hypnotically. Warm, comforting, cozy. Dark surroundings. Vertical
9:16, 4K. SFX: crackling fire.
```

### Nature B-Roll Templates

**Forest:**
```
Cinematic drone shot flying slowly through a misty morning in a redwood
forest. Sunbeams cut through the fog. Serene, majestic, peaceful.
Vertical 9:16, photorealistic, 4K. Ambience: birds, gentle wind.
```

**Ocean:**
```
Underwater shot of a sea turtle gliding through crystal clear turquoise
water, sunlight filtering down from the surface. Calm and beautiful.
Vertical 9:16, BBC Blue Planet style, hyperrealistic.
```

**Mountain:**
```
10-second timelapse of dramatic fast-moving clouds flowing over a rugged
mountain range at dusk. Last light colors the peaks gold and red.
Epic and awe-inspiring. Vertical 9:16, 8K, cinematic.
```

**Rain / Moody:**
```
Interior shot looking out a large cafe window on a rainy day. Raindrops
run down the glass, blurring city lights outside. Warm lamp visible
inside, creating a reflection. Moody, relaxing, melancholic.
Vertical 9:16, cinematic, soft focus.
```

---

## Advanced Techniques

### Negative Prompting Syntax

VEO 3 does not have a separate negative prompt field — weave exclusions directly into your prompt or use a `Negative:` label:

```
Negative: blurry, low quality, cartoon, distorted, morphing, watermark
```

Or phrase exclusions as descriptions of the opposite:
```
instead of "no blur" write: "sharp, crisp, in-focus"
```

### Seed Numbers for Reproducibility

Include seed values to reproduce similar outputs during iteration:

```
[Your prompt here], seed: 1234
```

### Iterative Refinement Strategy

1. Start with a clear structured prompt (cinematography + subject + action + style)
2. Generate and identify what works and what fails
3. Add more specific detail to failing elements
4. Use negative prompting to suppress unwanted outputs
5. Keep winning elements exactly as-is in the next iteration
6. Repeat 2–4 times maximum before redesigning the shot concept

### Style Combination (Cinematic Fusion)

You can blend multiple style references:

```
Shot in the style of a 1970s Italian neo-noir film, with desaturated
earth tones, shallow depth of field, and handheld naturalistic camerawork.
Moody, tense. Cinematic.
```

```
Documentary realism meets science fiction — photorealistic but with
subtle holographic overlays, like a near-future National Geographic special.
```

### Prompt Template for Consistent Branded Style

For all videos in a series, define a style block you always append:

```
[STYLE BLOCK - append to every prompt in this series]
Visual style: cinematic 4K, warm golden tones, shallow depth of field,
soft vignette. Vertical 9:16. Audio: gentle ambient piano.
Mood: calm, curious, educational. Quality: photorealistic, high detail.
```

---

## API Access and Python Integration

### Access Methods (as of 2025)

| Platform | Notes |
|---|---|
| **Google AI Studio** | Paid preview from July 17, 2025 |
| **Vertex AI** | Enterprise access via google-cloud-aiplatform SDK |
| **Gemini API** | Accessible via google-generativeai SDK |

### Pricing

- $0.75 per second of generated video + audio output
- A faster/cheaper "Veo 3 Fast" variant was announced

### Python SDK Example (Vertex AI)

```python
import vertexai
from vertexai.preview.vision_models import VideoGenerationModel

# Configuration
PROJECT_ID = "your-google-cloud-project-id"
LOCATION = "us-central1"

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Model ID — check Google Cloud docs for current model string
# Common identifiers seen in practice:
# "video-generation-001" (Veo 2 era)
# "veo-3.0-generate-preview" (check official docs for current)
VEO_MODEL_ID = "veo-3.0-generate-preview"

# Define prompt
prompt = (
    "Aerial drone footage of a lone hiker reaching the summit of a "
    "snow-capped mountain at sunrise. The clouds are below the peak. "
    "Epic, hopeful, majestic mood. Stunning slow motion as they take "
    "the final step. Vertical 9:16 aspect ratio, hyperrealistic, 4K. "
    "Music: swelling orchestral strings building to a climax."
)

output_file = "output_video.mp4"

# Load model
model = VideoGenerationModel.from_pretrained(VEO_MODEL_ID)

# Generate video
response = model.generate(
    prompt=prompt,
    aspect_ratio="9:16",    # Vertical for social media
    # seed=1234             # Uncomment for reproducible results
)

# Save result
response.save(location=output_file)
print(f"Video saved to: {output_file}")
```

### Integration with This Project

The existing `generators/veo_gen.py` and `generators/veo_integration.py` files in this project handle VEO integration. Key config values in `config/settings.py`:

- `VEO_PROJECT_ID` — your GCP project ID
- `VEO_LOCATION` — typically `us-central1`
- `VEO_CACHE_DIR` — defaults to `.veo_cache/`

VEO modes available in this project:
- `full` — all clips generated by VEO
- `hybrid` — combine VEO clips with existing asset library (recommended)
- `fallback` — try VEO, fall back to static assets on failure

Generate with VEO using the CLI:
```bash
python cli.py generate fact --veo --veo-mode hybrid
```

---

## Quick Reference Card

### The Five Essential Prompt Elements

```
1. SHOT:     Close-up / Medium / Wide / Aerial / Macro
2. SUBJECT:  Specific description with name, age, clothing, features
3. ACTION:   Exact motion, direction, speed
4. SETTING:  Location, time of day, weather, lighting
5. STYLE:    Film aesthetic + color grade + mood + audio
```

### Must-Have Modifiers for Quality

```
cinematic, 4K, photorealistic, hyperrealistic, high detail,
shallow depth of field, vertical 9:16, slow motion (when applicable)
```

### Words That Hurt Results

```
beautiful (too vague), amazing, incredible, nice, good
Don't use: "no", "don't", "without" — describe what you WANT instead
```

### Fastest Path to Good Social Media Content

```
[Shot type] of [specific subject doing specific action].
[Lighting description]. [Mood]. Vertical 9:16 aspect ratio,
photorealistic, 4K. [Audio description].
```

---

*Research compiled from: Google Cloud Blog "Ultimate prompting guide for Veo 3.1" (Oct 2025),
Vertex AI documentation, community findings from Reddit, YouTube tutorials, and user experiments.*
