import random
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config.settings import (
    VIDEO_WIDTH, VIDEO_HEIGHT, FONTS_DIR, BACKGROUNDS_DIR, OUTPUT_DIR,
)


# Colors for gradient backgrounds when no stock images are available
GRADIENT_PALETTES = [
    [(20, 20, 40), (60, 20, 80)],       # dark purple
    [(10, 10, 30), (30, 60, 90)],        # deep blue
    [(30, 10, 10), (80, 30, 30)],        # dark red
    [(10, 30, 20), (20, 70, 50)],        # dark green
    [(40, 20, 10), (90, 60, 20)],        # dark gold
    [(15, 15, 25), (50, 40, 70)],        # midnight purple
    [(20, 10, 30), (70, 30, 60)],        # magenta dark
    [(10, 20, 30), (40, 80, 100)],       # ocean blue
]


def _get_font(size, bold=False):
    """Load a font, falling back to default if no custom fonts available."""
    if FONTS_DIR.exists():
        font_files = list(FONTS_DIR.glob("*.ttf")) + list(FONTS_DIR.glob("*.otf"))
        if font_files:
            # Prefer bold fonts for quotes
            if bold:
                bold_fonts = [f for f in font_files if "bold" in f.name.lower()]
                if bold_fonts:
                    return ImageFont.truetype(str(bold_fonts[0]), size)
            return ImageFont.truetype(str(font_files[0]), size)
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _create_gradient(width, height, color1, color2):
    """Create a vertical gradient image."""
    img = Image.new("RGB", (width, height))
    for y in range(height):
        ratio = y / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        for x in range(width):
            img.putpixel((x, y), (r, g, b))
    return img


def _get_background(content_type="motivation"):
    """Get a background image matched to content mood."""
    # Try mood-specific subfolder first
    mood_dir = BACKGROUNDS_DIR / content_type
    search_dirs = [mood_dir, BACKGROUNDS_DIR] if mood_dir.exists() else [BACKGROUNDS_DIR]

    for search_dir in search_dirs:
        bg_files = (
            list(search_dir.glob("*.jpg"))
            + list(search_dir.glob("*.jpeg"))
            + list(search_dir.glob("*.png"))
            + list(search_dir.glob("*.JPG"))
        )
        if bg_files:
            bg_path = random.choice(bg_files)
            img = Image.open(bg_path).convert("RGB")
            img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)
            # Darken the image so text is readable
            overlay = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0))
            img = Image.blend(img, overlay, 0.5)
            return img

    # Fallback: gradient background
    palette = random.choice(GRADIENT_PALETTES)
    return _create_gradient(VIDEO_WIDTH, VIDEO_HEIGHT, palette[0], palette[1])


def _draw_text_with_shadow(draw, position, text, font, fill, shadow_color=(0, 0, 0), offset=3):
    """Draw text with a drop shadow for readability."""
    x, y = position
    # Shadow
    draw.text((x + offset, y + offset), text, font=font, fill=shadow_color)
    # Main text
    draw.text((x, y), text, font=font, fill=fill)


def _wrap_text(text, font, max_width, draw):
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def create_motivation_image(quote_text, author="Unknown", output_path=None):
    """Create a 1080x1920 motivational quote card."""
    img = _get_background("motivation")
    draw = ImageDraw.Draw(img)

    # Quote text
    quote_font = _get_font(52, bold=True)
    max_text_width = VIDEO_WIDTH - 160  # 80px padding on each side

    # Add quotation marks
    display_text = f'"{quote_text}"'
    lines = _wrap_text(display_text, quote_font, max_text_width, draw)

    # Calculate total text height
    line_height = 70
    total_text_height = len(lines) * line_height

    # Center vertically (slightly above center)
    start_y = (VIDEO_HEIGHT - total_text_height) // 2 - 80

    # Draw each line centered
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=quote_font)
        text_width = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - text_width) // 2
        y = start_y + i * line_height
        _draw_text_with_shadow(draw, (x, y), line, quote_font, fill=(255, 255, 255))

    # Author line
    author_font = _get_font(36)
    author_text = f"— {author}"
    bbox = draw.textbbox((0, 0), author_text, font=author_font)
    author_width = bbox[2] - bbox[0]
    author_x = (VIDEO_WIDTH - author_width) // 2
    author_y = start_y + total_text_height + 40
    _draw_text_with_shadow(
        draw, (author_x, author_y), author_text, author_font,
        fill=(200, 200, 200)
    )

    # Decorative line above and below quote
    line_y_top = start_y - 40
    line_y_bottom = author_y + 60
    line_margin = 200
    draw.line(
        [(line_margin, line_y_top), (VIDEO_WIDTH - line_margin, line_y_top)],
        fill=(255, 255, 255, 100), width=2,
    )
    draw.line(
        [(line_margin, line_y_bottom), (VIDEO_WIDTH - line_margin, line_y_bottom)],
        fill=(255, 255, 255, 100), width=2,
    )

    # Save
    if output_path is None:
        output_path = OUTPUT_DIR / "quote_card.png"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), quality=95)
    return output_path


def create_fact_image(fact_text, source="", output_path=None):
    """Create a 1080x1920 fun fact card."""
    img = _get_background("fact")
    draw = ImageDraw.Draw(img)

    # "Did You Know?" header
    header_font = _get_font(64, bold=True)
    header_text = "DID YOU KNOW?"
    bbox = draw.textbbox((0, 0), header_text, font=header_font)
    header_width = bbox[2] - bbox[0]
    header_x = (VIDEO_WIDTH - header_width) // 2
    header_y = VIDEO_HEIGHT // 2 - 300
    _draw_text_with_shadow(
        draw, (header_x, header_y), header_text, header_font,
        fill=(255, 220, 50)  # gold color for header
    )

    # Fact text
    fact_font = _get_font(46, bold=True)
    max_text_width = VIDEO_WIDTH - 160
    lines = _wrap_text(fact_text, fact_font, max_text_width, draw)

    line_height = 65
    total_text_height = len(lines) * line_height
    start_y = header_y + 120

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=fact_font)
        text_width = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - text_width) // 2
        y = start_y + i * line_height
        _draw_text_with_shadow(draw, (x, y), line, fact_font, fill=(255, 255, 255))

    # Source
    if source:
        source_font = _get_font(30)
        source_text = f"Source: {source}"
        bbox = draw.textbbox((0, 0), source_text, font=source_font)
        source_width = bbox[2] - bbox[0]
        source_x = (VIDEO_WIDTH - source_width) // 2
        source_y = start_y + total_text_height + 50
        _draw_text_with_shadow(
            draw, (source_x, source_y), source_text, source_font,
            fill=(180, 180, 180)
        )

    # Save
    if output_path is None:
        output_path = OUTPUT_DIR / "fact_card.png"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), quality=95)
    return output_path


def create_health_image(hook, topic, benefits, output_path=None):
    """Create a 1080x1920 health/nutrition info card."""
    img = _get_background("health")
    draw = ImageDraw.Draw(img)

    # Hook text at top
    hook_font = _get_font(48, bold=True)
    max_text_width = VIDEO_WIDTH - 160
    hook_lines = _wrap_text(hook, hook_font, max_text_width, draw)

    line_height = 60
    hook_y = VIDEO_HEIGHT // 2 - 350

    for i, line in enumerate(hook_lines):
        bbox = draw.textbbox((0, 0), line, font=hook_font)
        text_width = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - text_width) // 2
        y = hook_y + i * line_height
        _draw_text_with_shadow(draw, (x, y), line, hook_font, fill=(50, 255, 150))  # green accent

    # Benefits list
    benefit_font = _get_font(38)
    bullet_start_y = hook_y + len(hook_lines) * line_height + 60

    for i, benefit in enumerate(benefits[:4]):  # Max 4 benefits
        bullet_text = f"• {benefit}"
        benefit_lines = _wrap_text(bullet_text, benefit_font, max_text_width - 40, draw)

        for j, line in enumerate(benefit_lines):
            x = 100  # Left aligned with indent
            y = bullet_start_y + (i * 100) + (j * 50)
            _draw_text_with_shadow(draw, (x, y), line, benefit_font, fill=(255, 255, 255))

    # Topic at bottom
    topic_font = _get_font(32)
    topic_text = f"Topic: {topic}"
    bbox = draw.textbbox((0, 0), topic_text, font=topic_font)
    topic_width = bbox[2] - bbox[0]
    topic_x = (VIDEO_WIDTH - topic_width) // 2
    topic_y = VIDEO_HEIGHT - 200
    _draw_text_with_shadow(draw, (topic_x, topic_y), topic_text, topic_font, fill=(180, 180, 180))

    # Save
    if output_path is None:
        output_path = OUTPUT_DIR / "health_card.png"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), quality=95)
    return output_path


def create_image(content, output_path=None):
    """Create image based on content type."""
    if content["type"] == "motivation":
        return create_motivation_image(
            content["quote"],
            content.get("author", "Unknown"),
            output_path,
        )
    elif content["type"] == "health":
        return create_health_image(
            content.get("hook", ""),
            content.get("topic", "Health Tip"),
            content.get("benefits", []),
            output_path,
        )
    elif content["type"] == "fact":
        return create_fact_image(
            content["fact"],
            content.get("source", ""),
            output_path,
        )
    else:
        raise ValueError(f"Unknown content type: {content['type']}")


if __name__ == "__main__":
    # Test with sample data
    test_quote = {
        "type": "motivation",
        "quote": "The impediment to action advances action. What stands in the way becomes the way.",
        "author": "Marcus Aurelius",
    }
    path = create_image(test_quote)
    print(f"Created quote image: {path}")

    test_fact = {
        "type": "fact",
        "fact": "Octopuses have three hearts and blue blood. Two hearts pump blood to the gills, while the third pumps it to the rest of the body.",
        "source": "Marine Biology",
    }
    path = create_image(test_fact)
    print(f"Created fact image: {path}")
