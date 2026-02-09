# Short-Form Video Content Framework

Reference guide based on proven viral content strategies.

## The 3-Part Script Structure

### 1. Hook (First 5 Seconds) - CRITICAL

You have a **5-second window** to grab attention. The hook determines whether the viewer stays or scrolls.

**Hook Types:**

| Type | Description | Example |
|------|-------------|---------|
| **Desire** | Promise something they want | "Here's how to make $10K/month passively" |
| **Social Proof** | Authority/credibility claim | "After 10 years of studying millionaires..." |
| **Controversy** | Challenge common beliefs | "Everything you've been told about success is wrong" |
| **Curiosity** | Surprising fact/question | "Did you know that 90% of people..." |

**Hook Formula:**
- Extract the most attractive claim from your content
- Lead with the "too good to be true" angle
- Make them think "how is that even possible?"

### 2. Body (Main Content)

**Pacing Rules:**
- Short, punchy sentences (5-10 words max)
- Get straight to the point
- Move at a fast pace
- Remove anything that wastes the viewer's time

**Filler Words to ELIMINATE:**
- um, like, basically, actually, you know
- so, just, really, honestly, literally
- I mean, you see, kind of, sort of

### 3. Visual Elements (Show, Don't Tell)

The secret that elevates short-form content: **show the idea visually, not just verbally**.

When someone mentions:
- Money → Show stock footage of cash/success
- Question → Animate a question mark
- A person → Show an icon or silhouette
- Numbers → Display them on screen with animation
- Key concepts → Text overlay with glow effect

---

## Editing Framework

### Movement
- **Zoom ins**: Highlight important statements
- **Zoom outs**: Transition between ideas
- **Tracking**: Follow movement in the frame

### Cuts
- Cut right before silence
- Cut right before speaking starts
- Overlap cuts to maintain constant engagement

### Text Overlays
- 2 words per subtitle (max)
- Animate text in (move from bottom, pop up)
- Highlight key words with color/glow

### Sound Design

Think of content moving through "thick air" - everything needs whooshes and impacts.

| Action | Sound Effect |
|--------|--------------|
| Text appearing | Whoosh |
| Zoom in | Whoosh + riser |
| Transition | Transition SFX |
| Important word | Hit/impact |
| Question reveal | Riser (anticipation) |
| Answer reveal | Hit + cash register |

---

## Viral Idea Generation

### Method 1: Trend Riding
- Find what's currently trending in your niche
- Put your spin on successful formats
- Brings new audience from trending topic

### Method 2: AI-Assisted Research
Use specific prompts:
```
Give me 10 viral short form ideas in [NICHE]
that are trending now and have low competition
```

### Method 3: "Too Good to Be True" Claims
Think of claims that make people ask "how is that possible?"
- "How I made $300K from a faceless account at 14"
- "The one habit that changed my entire life in 30 days"
- "Why successful people wake up at 4am (it's not what you think)"

---

## Content Checklist

Before publishing, verify:

- [ ] Hook grabs attention in first 5 seconds
- [ ] No filler words
- [ ] Sentences under 10 words each
- [ ] Visual elements support every key point
- [ ] Sound design on all movements
- [ ] Subtitles with 2-word max segments
- [ ] Key words highlighted/emphasized
- [ ] Fast pace throughout
- [ ] Clear value delivered

---

## Quick Reference: Sentence Transformations

**Before (weak):**
> "So basically, I'm going to tell you about something that I think is really important that you should probably know about."

**After (strong):**
> "This one thing changed everything."

**Before (weak):**
> "Um, you know, a lot of people don't actually realize that this is something that can help them."

**After (strong):**
> "Most people miss this. Here's what they don't see."

---

## Integration with Pipeline

Use `generators/short_form_agent.py`:

```python
from generators.short_form_agent import ShortFormScriptAgent

agent = ShortFormScriptAgent()

# Generate viral ideas
ideas = agent.generate_viral_ideas("stoicism", count=10)

# Generate complete script
script = agent.generate_script(content_type="motivation")

# Analyze existing script
analysis = agent.analyze_script("Your script text here...")

# Improve weak script
improved = agent.improve_script(script)

# For pipeline integration
content = agent.generate_for_pipeline("motivation")
```

CLI usage:
```bash
python generators/short_form_agent.py ideas stoicism
python generators/short_form_agent.py script motivation
python generators/short_form_agent.py analyze "Your script..."
python generators/short_form_agent.py pipeline fact
```
